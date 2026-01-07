## MVP PRD: TouchDesigner Events WebSocket (Wave-Mix Ready + Dialogues)

### Context
Reflective Resonance (FastAPI backend) generates:
- **TTS WAV** per slot for a 3-turn workflow (Turn 1 response, Turn 2 comment, Turn 3 reply)
- **Wave decomposition outputs** via `backend/waves/*`, including the key artifact:
  - `*_v3_wave_mix.wav` (the “mixed wave file” TouchDesigner will use)

TouchDesigner runs on the **same machine** as this backend. We want TouchDesigner to connect to the backend over a **WebSocket** and receive **JSON events** containing **local file system paths** to wave-mix files as they are produced.

This PRD defines:
- a WebSocket endpoint TouchDesigner connects to
- a minimal, robust JSON event schema
- the backend orchestration logic to emit:
  1) a **Turn 1 event** when wave-mix files become available (partial allowed)
  2) **Dialogue events** computed from Turn 2 + Turn 3 (one event per dialogue)

This is intentionally separate from the existing frontend SSE stream (`/v1/chat`).

---

## Goals / Non-goals

### Goals
- Provide a **single-client** WebSocket that TouchDesigner can connect to and passively receive events.
- Emit **Turn 1 wave events** as soon as enough wave-mix files are ready:
  - Send one message containing all ready slots.
  - If some fail/never arrive, still send the ready ones (partial allowed).
- After Turn 2 + Turn 3 complete, compute “dialogues” and emit:
  - one message per dialogue, sequentially
  - each message includes commenter wave-mix paths (Turn 2) + respondent wave-mix path (Turn 3)
- Use **worker pool result notifications** (not filesystem polling) to detect when a wave-mix is ready.
- Ensure the system remains **non-blocking** and does not slow the core TTS/SSE pipeline.

### Non-goals (MVP)
- No changes to frontend UI.
- No reliability guarantees if TouchDesigner is disconnected (no persistent queue or replay).
- No authentication/authorization beyond “same machine / trusted environment”.
- No OSC/UDP protocol (WebSocket only).

---

## Existing System Constraints (Relevant)

### TTS storage (existing)
TTS WAV files are written to:
- `artifacts/tts/sessions/<session_id>/turn_<N>/*.wav`

### Wave decomposition (existing)
Wave decomposition is performed by:
- `backend/waves/worker.py` using a `ProcessPoolExecutor`
- outputs under:
  - `artifacts/waves/sessions/<session_id>/turn_<N>/...`
  - including: `<tts_basename>_v3_wave_mix.wav`

### Session + turn orchestration (existing)
`backend/workflow.py`:
- creates a new `session_id` per `/v1/chat` request
- generates TTS per slot for Turn 1/2/3
- submits wave decomposition jobs (fire-and-forget)

---

## Definitions

### Wave-mix file
The file TouchDesigner should load per agent utterance:
- `.../<tts_basename>_v3_wave_mix.wav`

### Dialogue (Turn 2 + Turn 3)
A “dialogue” is defined per **responding slot** in Turn 3:
- **Respondent**: the slot that produced a Turn 3 reply (target slot)
- **Commenters**: the set of Turn 2 slots that commented on that respondent’s Turn 1 response
- A dialogue event contains:
  - all commenter wave-mix files (Turn 2)
  - the respondent’s wave-mix file (Turn 3)
  - an explicit `playOrder` for sequential playback/animation

---

## WebSocket API

### Endpoint
- **URL**: `ws://<host>:<port>/v1/events`
- **Direction**: server → client (TouchDesigner consumes events; client may send optional “hello”)
- **Client count**: single-client

### Single-client policy
When a new client connects:
- backend accepts it
- if another client is connected, backend closes the old connection (“last writer wins”)

### Message format
All outgoing messages are **UTF-8 text frames** containing JSON.

### Optional client messages (MVP)
TouchDesigner may send:
- `{"type":"hello","client":"touchdesigner","version":"..."}`

Backend response:
- `{"type":"hello.ack","server":"reflective-resonance","version":"0.1.0"}`

(Client messages are optional; backend must work even if TD never sends anything.)

---

## Event Schema (JSON)

### Envelope (common fields)
All backend → TouchDesigner events use this envelope:

```json
{
  "type": "turn1.waves.ready",
  "sessionId": "uuid",
  "seq": 1,
  "ts": "RFC3339 timestamp",
  "payload": {}
}
```

#### Field requirements
- `type` (**string**): discriminator for routing in TouchDesigner
- `sessionId` (**string**): workflow session UUID
- `seq` (**int**): monotonically increasing per `sessionId` (starts at 1)
- `ts` (**string**): UTC timestamp for debugging
- `payload` (**object**): event-specific payload

### Path representation
Because TouchDesigner runs on the same machine, each wave reference should include:
- `waveMixPathAbs`: absolute filesystem path (preferred for TD)
- `waveMixPathRel`: relative path under `artifacts/` (useful for debugging / HTTP fetch)

Example:
- `waveMixPathRel`: `waves/sessions/<session_id>/turn_1/<file>_v3_wave_mix.wav`
- `waveMixPathAbs`: `/Users/.../Projects/reflective_resonance/artifacts/waves/sessions/<session_id>/turn_1/...`

---

## Event Types

### 1) Turn 1 waves ready (partial allowed)

#### Event type
- `type = "turn1.waves.ready"`

#### Trigger condition
Emit once per session when Turn 1 wave-mix readiness reaches a barrier:
- Preferred: emit when **all 6 are ready**
- If partial failure occurs: emit after a configurable timeout (e.g. 10–20s) with whatever is ready

#### Payload
```json
{
  "turnIndex": 1,
  "status": "complete|partial",
  "slotsExpected": 6,
  "slotsReady": 5,
  "slots": [
    {
      "slotId": 1,
      "agentId": "gpt-5.1",
      "voiceProfile": "playful_expressive",
      "waveMixPathAbs": "/abs/path/..._v3_wave_mix.wav",
      "waveMixPathRel": "waves/sessions/<session>/turn_1/..._v3_wave_mix.wav"
    }
  ],
  "missingSlotIds": [6]
}
```

Notes:
- `voiceProfile` is included because it is available at TTS generation time and is useful metadata for TD.
- The backend should not send 6 separate events; it sends **one aggregated Turn 1 event**.

### 2) Dialogue waves ready (Turn 2 + Turn 3)

#### Event type
- `type = "dialogue.waves.ready"`

#### Trigger condition
After Turn 3 completes, compute dialogues. For each dialogue:
- wait until all required wave-mix files for that dialogue are ready
- then emit a dialogue event

No dialogues case:
- if no Turn 3 replies exist, emit **nothing** (MVP requirement).

#### Payload
```json
{
  "dialogueId": "turn23-slot2",
  "turns": [2, 3],
  "targetSlotId": 2,
  "commenters": [
    {
      "slotId": 1,
      "agentId": "gpt-5.1",
      "voiceProfile": "calm_soothing",
      "waveMixPathAbs": "/abs/path/...turn_2/..._v3_wave_mix.wav",
      "waveMixPathRel": "waves/sessions/<session>/turn_2/..._v3_wave_mix.wav"
    }
  ],
  "respondent": {
    "slotId": 2,
    "agentId": "claude-opus-4-5",
    "voiceProfile": "calm_soothing",
    "waveMixPathAbs": "/abs/path/...turn_3/..._v3_wave_mix.wav",
    "waveMixPathRel": "waves/sessions/<session>/turn_3/..._v3_wave_mix.wav"
  },
  "playOrder": [
    { "role": "commenter", "slotId": 1 },
    { "role": "respondent", "slotId": 2 }
  ]
}
```

Ordering:
- The backend must emit dialogues sequentially in a deterministic order (recommended):
  - increasing `targetSlotId`, then increasing `from_slot_id` inside `commenters`

---

## Worker Pool Result Notifications (Required)

### Objective
We must know that `*_v3_wave_mix.wav` exists **without polling the filesystem**.

### Required changes
Extend `backend/waves/worker.py` so that when a job completes it emits a result notification into an in-process async channel.

#### Data to include per completion
Create an internal model (dataclass or Pydantic) like:
- `WavesJobResult`:
  - `job: DecomposeJob` (includes `session_id`, `turn_index`, input path)
  - `result: DecomposeResult` (includes `wave_mix_path`, `success`, `error`, `duration_ms`, `rmse`)

#### Notification mechanism
Provide one of:
- **Async queue**: `asyncio.Queue[WavesJobResult]` with an async consumer loop (recommended)
- or **callback registration**: allow adding listeners invoked on completion (must be async-safe)

Implementation note:
- The Python docs recommend `Future.add_done_callback()` for result notifications and document constraints on `ProcessPoolExecutor` usage. See: `https://docs.python.org/3.14/library/concurrent.futures.html` (callbacks, futures, process pool).

---

## Backend Event Orchestrator (Required)

### Responsibilities
Implement a backend component (module) that:
1) Manages the WebSocket connection (single client)
2) Consumes wave decomposition completion notifications
3) Tracks per-session readiness state
4) Emits aggregated Turn 1 and dialogue events at the right time

### Data model (in-memory)
For each `sessionId`, maintain:
- `turn1_expected`: set of slotIds expected (1..6)
- `turn1_ready`: map slotId → waveMixPathAbs + metadata
- `dialogues`: list of computed dialogue definitions (commenters + respondent)
- `dialogues_ready`: which dialogues have been emitted
- `seq_counter`: event sequence for this session

### Session lifecycle integration points
The orchestrator needs “session boundaries” to know what to expect. Add explicit hooks in `backend/workflow.py`:
- On session creation: `events.begin_session(session_id, slots=...)`
- After Turn 1 completes (turn.done): `events.turn1_complete(session_state)`
- After Turn 3 completes: `events.turn3_complete(session_state)` (compute dialogues)

These hooks should be non-blocking and should not affect SSE behavior.

---

## Computing Dialogues (Turn 2 + Turn 3)

### Inputs available in current workflow
From `backend/workflow.py` state:
- Turn 2 results include:
  - commenter slot id
  - target slot id (`targetSlotId`)
  - agent id + voice profile
  - TTS audio filename base is derivable from the known naming convention
- Turn 3 results include:
  - respondent slot id
  - agent id + voice profile

### Dialogue construction algorithm (required)
1) Identify all respondent slots:
   - slots that have a successful Turn 3 result
2) For each respondent slot `T`, gather commenters:
   - all successful Turn 2 results where `targetSlotId == T`
3) Build a `Dialogue` object:
   - `targetSlotId = T`
   - `commenters = [slot ids that commented on T]`
   - `respondent = T`
4) Derive expected wave-mix paths for each utterance using:
   - `sessionId`, `turnIndex`, and the known file naming convention

### Preprocessing / sequencing requirement
The backend sends dialogues one-by-one as distinct websocket events:
- it must only emit a dialogue when all its required wave-mix files are ready
- if a commenter’s wave decomposition fails, emit the dialogue with `status="partial"` and omit that commenter (rare case)

---

## Error Handling

### If TouchDesigner is not connected
- Backend should log and drop events (no buffering for MVP).

### If wave decomposition fails
- The core chat workflow must remain unaffected (already true today).
- Orchestrator behavior:
  - Turn 1: include only successful slots in `slots[]`, mark `status="partial"`.
  - Dialogues: include only successful commenters/respondent; if respondent missing, drop the dialogue (since TD can’t play it).

### WebSocket disconnects mid-session
- Stop sending until reconnected.
- On reconnect, backend sends a `hello.ack` but does not replay missed events (MVP).

---

## Configuration

Add settings in `backend/config.py`:
- `events_ws_enabled: bool = True`
- `events_ws_path: str = "/v1/events"`
- `events_ws_single_client: bool = True` (always true for MVP)
- `events_turn1_timeout_s: float = 15.0` (how long to wait after Turn 1 completion before sending partial)
- `events_dialogue_timeout_s: float = 30.0` (max wait per dialogue after Turn 3 completion)

---

## Acceptance Criteria

- **AC1: TouchDesigner can connect**
  - A TD WebSocket client can connect to `ws://localhost:8000/v1/events` and receive JSON text messages.

- **AC2: Turn 1 aggregated event**
  - For each session, backend emits exactly one `turn1.waves.ready` event.
  - Event includes `waveMixPathAbs` for each ready slot and is `status="complete"` when all 6 are available.

- **AC3: Dialogue events**
  - After Turn 3 completion, backend emits one `dialogue.waves.ready` event per dialogue.
  - Each includes the commenter wave-mix paths (Turn 2) and respondent wave-mix path (Turn 3).

- **AC4: Non-blocking**
  - WebSocket event emission does not delay SSE events (`slot.audio`, `turn.done`, `done`) and does not block the worker pool.

- **AC5: Single-client behavior**
  - If a second client connects, the first is disconnected and the second receives subsequent events.

---

## Testing Plan (MVP)

### Local test harness
- Use a simple websocket client (python or `wscat`) to connect and print messages.
- Trigger `/v1/chat` and verify:
  - Turn 1 aggregated event arrives with correct absolute paths
  - Dialogue events arrive after Turn 3 completes

### Failure simulation
- Intentionally break one decomposition job (e.g., invalid input path in a controlled test) and confirm:
  - Turn 1 event is emitted with `status="partial"` and `missingSlotIds`
  - No crash in workflow

---

## References
- Python `concurrent.futures` docs (ProcessPoolExecutor, Future callbacks): `https://docs.python.org/3.14/library/concurrent.futures.html`
- ProcessPoolExecutor callback patterns: `https://superfastpython.com/processpoolexecutor-usage-patterns/`


