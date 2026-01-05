# Reflective Resonance — MVP PRD: 3‑Turn Inter‑Agent Workflow (with TTS)

**Document status**: Draft (implementation-ready)  
**Owner**: Backend + Frontend teams  
**Last updated**: 2026-01-04  
**Repo**: `reflective_resonance/`  
**Depends on**: `mvp-front-end-prd.md`, `mvp-back-end-prd.md`, `mvp_voice_profiles.md`  

---

## 1) Summary

We will extend the current MVP (user → 6 parallel agent responses with TTS) into a **3‑turn narrative workflow** where agents also interact with each other:

1) **Turn 1 (Respond)**: User sends a message. Each agent responds independently.  
2) **Turn 2 (Comment)**: Each agent sees the other 5 responses and writes a short audible comment on exactly one.  
3) **Turn 3 (Reply)**: Each agent receives up to 3 comments about their Turn 1 response and replies.

All text outputs are converted to **WAV audio** using the existing ElevenLabs multi‑voice profiles, and saved as artifacts in a deterministic session directory.

Playback/ordering in TouchDesigner is **out of scope**; the system must reliably **generate and expose audio files** and emit sufficient metadata via SSE for downstream orchestration.

---

## 2) Goals

- Implement a deterministic, reliable 3‑turn workflow using **RawAgents** (`Conversation`, `AsyncLLM.complete_structured`) and existing SSE infrastructure.
- Ensure each turn produces:
  - structured text output with `voice_profile`
  - a WAV audio file written to disk
  - SSE events containing turn metadata + `audioPath`
- Keep responses concise and conversational (1–3 sentences), including Turn 2 comments.
- Maintain per-slot conversation continuity across turns (in-memory).
- Provide a UI that can display all turns **without overcrowding** the Responses panel.

---

## 3) Non-goals

- TouchDesigner playback logic, scheduling, and mixing.
- STT / microphone input.
- Persistent database for sessions or conversations.
- Multi-user sessions (assume single kiosk user).
- Agent personalities per slot beyond model + voice profile (can be added later).
- “No comment” option (Turn 2 always comments on exactly one other response).

---

## 4) Current baseline (what already exists)

### Backend
- `POST /v1/chat` streams SSE events:
  - `slot.start`
  - `slot.done` (structured: `text`, `voiceProfile`)
  - `slot.audio` (WAV ready: `audioPath`)
  - `slot.error` (includes `tts_error`)
  - `done`
- Per-slot in-memory `Conversation` keyed by `slotId`.
- TTS generates WAV artifacts under `artifacts/tts/sessions/<session_id>/...`.

### Frontend
- Consumes SSE via `frontend/src/lib/utils/streaming.ts`.
- Treats `slot.done` as the full text for that slot; logs `slot.audio`.
- Responses panel currently shows the **latest** agent message per slot (single turn).

---

## 5) User experience / narrative intent

The 3-turn workflow should feel like:
- Turn 1: Six distinct “voices” respond to the user.
- Turn 2: Each voice briefly reacts to another voice (audible).
- Turn 3: Voices respond to comments they received (audible).

All turns are played **sequentially by turn** (TouchDesigner responsibility), but the system should generate all assets and metadata for each turn.

---

## 6) Backend requirements

### 6.1 New concept: Workflow execution model

The backend will implement a **single request → three sequential turns** workflow:

- Turn 1 must complete (LLM text ready for all participating slots) before Turn 2 begins.
- Turn 2 must complete (comment selections ready) before Turn 3 begins.
- TTS work for Turn N may run in parallel with LLM work for Turn N+1, but artifacts must be stored under the correct turn directory.

### 6.2 Participation rules (robustness)

- A slot participates in Turn 2 only if it produced a valid Turn 1 response.
- A slot participates in Turn 3 only if:
  - it produced a valid Turn 1 response, and
  - it received at least one comment (after capping).
- When building “other 5 responses” for Turn 2, exclude:
  - the agent’s own response
  - any slots that failed Turn 1

### 6.3 Comment routing + cap

- Each Turn 2 agent must select **exactly one** target response to comment on.
- Agents cannot comment on their own slot (`targetSlotId != selfSlotId`).
- After collecting all comments:
  - if a target slot receives more than **3** comments, randomly select **3** to pass into Turn 3
  - dropped comments are still stored as artifacts if their TTS was generated, but are not forwarded to the reply prompt

### 6.4 Audio artifact layout

Store audio artifacts under a per-request session directory, with turn subdirectories:

```
artifacts/tts/sessions/<session_id>/
  turn_1/
    slot-1_<agentId>_<voiceProfile>.wav
    ...
  turn_2/
    slot-1_comment_to_slot-<target>_<agentId>_<voiceProfile>.wav
    ...
  turn_3/
    slot-<target>_reply_<agentId>_<voiceProfile>.wav
    ...
```

Notes:
- Filenames must be deterministic, filesystem-safe, and include enough metadata to debug.
- Backend must continue serving artifacts via the existing static mount: `GET /v1/audio/<audioPath>`.

### 6.5 RawAgents usage requirements

Use RawAgents primitives:
- `Conversation` per slot (`slotId → Conversation`)
- `AsyncLLM.complete_structured()` for all three turns
- Prompts generated via `PromptManager` (Jinja2 templates) are recommended for maintainability.

### 6.6 Structured models (Pydantic)

#### Turn 1 / Turn 3 output (existing)
- `SpokenResponse`:
  - `text: str`
  - `voice_profile: VoiceProfileName`

#### Turn 2 output (new)
- `CommentSelection`:
  - `targetSlotId: SlotId` (must be one of the other participating slots)
  - `comment: str` (short, 1 sentence, ≤ 200 chars recommended)
  - `voice_profile: VoiceProfileName`

#### Turn 3 input (constructed by orchestrator)
For each slot, the orchestrator builds:
- the slot’s Turn 1 text
- a list of up to 3 comments directed at that slot:
  - `{ fromSlotId, fromAgentId, comment }`

### 6.7 Prompt templates (recommended)

Use RawAgents `PromptManager` with templates such as:
- `turn1_response.j2`
- `turn2_comment_select.j2`
- `turn3_reply.j2`

Variables you will pass into templates:
- `slot_id`, `agent_id`
- `user_message`
- `peer_responses` (Turn 2): list of `{ slotId, agentId, text }` (shuffled per slot)
- `received_comments` (Turn 3): list of `{ fromSlotId, fromAgentId, comment }`
- `voice_profiles_table` (optional string block, or embed in system prompt)

Guidance:
- Keep the global system prompt stable (poetic constraints + “JSON only”).
- Use templates for per-turn user instructions and injected peer/comment context.

### 6.8 Length and tone constraints (hard requirements)

To prevent drift and keep the “friends chatting” vibe:
- Turn 1 `text`: 1–3 sentences (cap ~400 chars recommended)
- Turn 2 `comment`: exactly 1 sentence (cap ~200 chars recommended)
- Turn 3 `text`: 1–2 sentences (cap ~300–400 chars recommended)

The backend should enforce caps by:
- instructing models strongly, and
- applying a final truncation guardrail server-side if needed (last-resort).

---

## 7) SSE event protocol updates

We must support multiple turns without breaking existing consumers.

### 7.1 Required fields added to events

Add these fields to relevant payloads:
- `sessionId: string`
- `turnIndex: 1 | 2 | 3`
- `kind: "response" | "comment" | "reply"`

### 7.2 Updated event payloads (recommended)

#### `slot.start`
```json
{
  "sessionId": "...",
  "turnIndex": 1,
  "kind": "response",
  "slotId": 1,
  "agentId": "gpt-4o"
}
```

#### `slot.done`
Turn 1 / Turn 3:
```json
{
  "sessionId": "...",
  "turnIndex": 1,
  "kind": "response",
  "slotId": 1,
  "agentId": "gpt-4o",
  "text": "...",
  "voiceProfile": "confident_charming"
}
```

Turn 2 (comment):
```json
{
  "sessionId": "...",
  "turnIndex": 2,
  "kind": "comment",
  "slotId": 4,
  "agentId": "claude-sonnet-4-5",
  "targetSlotId": 2,
  "comment": "...",
  "voiceProfile": "playful_expressive"
}
```

#### `slot.audio`
```json
{
  "sessionId": "...",
  "turnIndex": 2,
  "kind": "comment",
  "slotId": 4,
  "agentId": "claude-sonnet-4-5",
  "voiceProfile": "playful_expressive",
  "audioFormat": "wav",
  "audioPath": "tts/sessions/<session_id>/turn_2/slot-4_comment_to_slot-2_claude-sonnet-4-5_playful_expressive.wav"
}
```

#### `slot.error`
```json
{
  "sessionId": "...",
  "turnIndex": 3,
  "kind": "reply",
  "slotId": 2,
  "agentId": "claude-opus-4-5",
  "error": { "type": "tts_error", "message": "..." }
}
```

#### `turn.start` / `turn.done` (new events, recommended)
These make downstream orchestration simpler (TouchDesigner can gate playback per turn).

`turn.start`:
```json
{ "sessionId": "...", "turnIndex": 2 }
```

`turn.done`:
```json
{ "sessionId": "...", "turnIndex": 2, "slotCount": 6 }
```

#### Final `done` (existing)
Continue to emit `done` after the workflow ends:
```json
{ "completedSlots": 6, "sessionId": "...", "turns": 3 }
```

---

## 8) Frontend requirements (monitoring UI)

The current Responses panel shows only the latest agent message per slot, which will be insufficient with 3 turns.

### 8.1 UX goal

Show all turns **clearly** without overcrowding. The right panel should remain scannable.

### 8.2 Recommended UI pattern (minimal clutter)

**Responses Panel = per-slot cards, with a compact “Turn timeline” inside**

For each slot card:
- Header: `Speaker N · AgentName`
- Body: three compact sections (T1/T2/T3), collapsed by default with small expand affordances:
  - **T1**: response text (always visible preview)
  - **T2**: the comment the slot made (preview) + target indicator (e.g., “→ Speaker 2”)
  - **T3**: reply text (preview), only if that slot received comments
- Optional small badges:
  - “commented on: Speaker X”
  - “received: 2 comments”

**Interaction**:
- Clicking a turn label expands that turn’s full text.
- Keep only one expanded subsection at a time per slot.

This avoids adding 18 cards (6 slots × 3 turns) which would crowd the panel.

### 8.3 State changes needed in the frontend store

Frontend should store events keyed by:
- `sessionId`
- `slotId`
- `turnIndex`
- `kind`

Minimal approach:
- extend `Message` to include `turnIndex` + `kind` + optional `targetSlotId`
- keep the panel rendering derived “per-slot, per-turn latest message”

### 8.4 Audio handling in the UI

UI does not need to play audio. It should:
- display “audio ready” indicator for each turn/slot
- optionally provide a link to `GET /v1/audio/<audioPath>` for debugging

---

## 9) Testing plan

### Backend tests
- Deterministic session creation and directory structure
- Turn sequencing:
  - Turn 2 only starts after Turn 1 texts exist
  - Turn 3 only starts after Turn 2 routing exists
- Comment routing:
  - no self-targeting
  - cap at 3 comments per target
- SSE protocol:
  - events contain `sessionId`, `turnIndex`, `kind`
  - emits `turn.start`/`turn.done` (if implemented)
  - emits final `done`

### Integration tests (manual)
- Send message with 2–6 assigned slots
- Verify:
  - WAVs are created in `turn_1`, `turn_2`, `turn_3`
  - Turn 2 files show “comment_to_slot-X” naming
  - TouchDesigner team can fetch `/v1/audio/...` paths

### Frontend tests (manual)
- Responses panel shows:
  - Turn 1 for all slots
  - Turn 2 comment + target
  - Turn 3 replies where applicable
- No visual clutter (scroll remains usable)

---

## 10) Acceptance criteria

### Backend
- A single `/v1/chat` request triggers **3-turn workflow**.
- For each participating slot, system produces:
  - Turn 1 text + voiceProfile + WAV
  - Turn 2 comment selection (targetSlotId) + voiceProfile + WAV
  - Turn 3 reply (for slots with received comments) + voiceProfile + WAV
- WAV files are stored under `session/turn_<n>/` directories.
- SSE emits events with `sessionId`, `turnIndex`, and `kind`.

### Frontend
- Responses panel displays per-slot turn timeline without overcrowding.
- Each turn’s text is accessible (preview + expand).
- Audio readiness is visible per turn (link or badge).

---

## 11) Open questions (to resolve during implementation)

1) Should Turn 3 run for all slots (even those with zero received comments), or only those that received ≥1 comment?
2) Should we persist a session manifest JSON (e.g., `session.json`) listing all files produced for TouchDesigner convenience?
3) How should errors affect sequencing?
   - e.g., if one slot fails Turn 1, do other agents still comment in Turn 2 (excluding it)? (Recommended: yes.)


