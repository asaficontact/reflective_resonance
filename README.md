# Reflective Resonance

An interactive art installation featuring 6 speaker slots controlled by multiple LLM agents. Users assign AI agents to speaker positions via drag-and-drop, speak via push-to-talk audio input, and receive parallel streaming responses through a 4-turn inter-agent workflow. All responses are converted to speech via ElevenLabs TTS and decomposed into wave components for water-based speaker control.

**Current Stage:** Full audio pipeline with wave decomposition - Voice input (STT) → 4-turn LLM workflow → Voice output (TTS) → Wave decomposition → TouchDesigner integration.

## Quick Start

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env with your API keys:
# - OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY (LLM providers)
# - ELEVENLABS_API_KEY (required for TTS and STT)

# 2. Start backend (requires Python 3.13+)
uv sync
uv run uvicorn backend.main:app --reload --port 8000

# 3. Start frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 - drag agents to slots, hold the mic button to speak, watch the 4-turn workflow run.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (SvelteKit)                           │
│  ┌─────────────┐     ┌──────────────────┐     ┌───────────────────────────┐ │
│  │AgentPalette │     │   SpeakerSlots   │     │    ResponsesPanel         │ │
│  │(drag source)│────▶│ (6 slot grid)    │     │  (T1/T2/T3/T4 turn tabs)  │ │
│  └─────────────┘     └────────┬─────────┘     └───────────────────────────┘ │
│                               │                            ▲                │
│                               ▼                            │                │
│                      ┌────────────────┐                    │                │
│                      │AudioInputDock  │                    │                │
│                      │(push-to-talk)  │──▶ POST /v1/stt    │                │
│                      └───────┬────────┘      (transcribe)  │                │
│                              │                             │                │
│              ┌───────────────▼─────────────────────────────┘                │
│              │         appStore (Svelte 5 Runes)                            │
│              │  - slots[], messages[], turnStatus                           │
│              │  - getTurnsForSlot(), setTurnStatus()                        │
│              └───────────────┬──────────────────────────────────────────────┤
│                              │                                              │
│                    POST /v1/chat + SSE streaming                            │
└──────────────────────────────┼──────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────────────┐
│                              BACKEND (FastAPI)                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        main.py (Routes)                             │    │
│  │  POST /v1/chat ──▶ 4-Turn Workflow (SSE)                            │    │
│  │  POST /v1/stt  ──▶ ElevenLabs Scribe (transcription)                │    │
│  │  WS   /v1/events ──▶ TouchDesigner events (wave completion)         │    │
│  │  GET  /v1/agents, /v1/health, POST /v1/reset                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    workflow.py (4-Turn Orchestrator)                │    │
│  │                                                                     │    │
│  │   Turn 1 (Respond): All slots respond to user in parallel           │    │
│  │   Turn 2 (Comment): Each slot comments on one peer's response       │    │
│  │   Turn 3 (Reply):   Slots that received comments reply              │    │
│  │   Turn 4 (Summary): Single agent synthesizes all dialogue           │    │
│  │                                                                     │    │
│  │   Each turn: LLM generation → TTS audio (WAV) → Wave decomposition  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                               │                                             │
│         ┌─────────────────────┼─────────────────────┬───────────────┐       │
│         ▼                     ▼                     ▼               ▼       │
│  ┌─────────────┐     ┌─────────────────┐    ┌──────────────┐  ┌──────────┐  │
│  │    tts/     │     │     stt/        │    │   waves/     │  │  events/ │  │
│  │ ElevenLabs  │     │ ElevenLabs      │    │ Decompose    │  │ WebSocket│  │
│  │ TTS + voice │     │ Scribe STT      │    │ to waves     │  │ Emitter  │  │
│  │ profiles    │     │ (English only)  │    │ (2 or 6)     │  │          │  │
│  └─────────────┘     └─────────────────┘    └──────────────┘  └──────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                  rawagents (AsyncLLM + LiteLLM)                      │    │
│  │   anthropic/claude-*, openai/gpt-*, gemini/gemini-*                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4-Turn Workflow

The core workflow processes user input through four sequential turns:

| Turn | Name | Description | Waves |
|------|------|-------------|-------|
| 1 | **Respond** | All slots respond to user message in parallel | 2 per agent |
| 2 | **Comment** | Each slot comments on exactly one peer's response | 2 per agent |
| 3 | **Reply** | Slots that received comments reply to them | 2 per agent |
| 4 | **Summary** | Single agent synthesizes the entire dialogue into a poetic summary | 6 (one per slot) |

Each turn generates LLM text, TTS audio (WAV files via ElevenLabs), and wave decomposition for speaker control.

---

## Wave Decomposition System

TTS audio is decomposed into wave components for driving water-based speakers. Each wave targets a specific speaker slot with a defined frequency range:

### Slot Frequency Mapping

```
         [Slot 1]      [Slot 2]      [Slot 3]
         80-100Hz      50-70Hz       20-40Hz
         (outer)       (middle)      (center)

         [Slot 4]      [Slot 5]      [Slot 6]
         20-40Hz       50-70Hz       80-100Hz
         (center)      (middle)      (outer)
```

The frequency pattern creates a symmetric "dome" effect: higher frequencies at the outer edges, lower frequencies at the center.

### Wave Distribution

**Turns 1-3 (Agent Responses):** Each agent produces 2 waves:
- Wave 1 → Same slot as agent
- Wave 2 → Next slot (wrapping: 6→1)

Example for Agent in Slot 3:
- Wave 1 → Slot 3 (20-40Hz)
- Wave 2 → Slot 4 (20-40Hz)

**Turn 4 (Summary):** Single response produces 6 waves, one for each slot (1-6), creating a unified ripple across all speakers.

### Decomposition Algorithm

The decomposition process (`backend/waves/decompose_v3.py`):

1. **Pitch Extraction:** Use `librosa.pyin` to extract fundamental frequency (f0)
2. **Harmonic Analysis:** Extract amplitude envelopes for N harmonics via STFT
3. **Frequency Mapping:** Map pitch contour to target slot's frequency range (preserves relative pitch)
4. **Wave Synthesis:** Generate cosine waves with mapped frequency and harmonic amplitude
5. **Gain Matching:** Apply dynamic gain curve so the wave mix matches original envelope

---

## Backend

### Technology Stack

| Package | Version | Purpose |
|---------|---------|---------|
| Python | ≥3.13 | Required by rawagents |
| FastAPI | ≥0.115 | HTTP framework |
| sse-starlette | ≥2.2 | Server-Sent Events |
| rawagents | git | LLM client (AsyncLLM, Conversation) |
| elevenlabs | ≥1.0 | TTS audio generation |
| httpx | ≥0.27 | Async HTTP client for STT |
| librosa | ≥0.10 | Audio analysis for wave decomposition |
| soundfile | ≥0.12 | WAV file I/O |
| pydantic | ≥2.0 | Request/response validation |
| uvicorn | ≥0.32 | ASGI server |

### File Structure

```
backend/
├── main.py           # FastAPI app, routes (/v1/chat, /v1/stt, /v1/events, /v1/agents)
├── workflow.py       # 4-turn orchestrator (Turn 1→2→3→4 with parallel LLM + TTS)
├── streaming.py      # SSE event delegation to workflow
├── sessions.py       # TTS session management (artifacts/tts/sessions/)
├── agents.py         # Agent registry, LLM client factory
├── conversations.py  # Per-slot conversation history
├── models.py         # Pydantic models for API + SSE events
├── config.py         # Settings from environment
├── prompts/          # Jinja2 templates for each turn's LLM prompt
│   ├── turn1_response.j2
│   ├── turn2_comment_select.j2
│   ├── turn3_reply.j2
│   └── turn4_summary.j2
├── tts/              # ElevenLabs TTS integration
│   ├── elevenlabs_client.py  # TTS client wrapper
│   ├── profiles.py           # Voice profiles per agent
│   └── wav.py                # PCM to WAV conversion
├── stt/              # ElevenLabs STT integration
│   ├── elevenlabs_stt.py     # Scribe v1 client
│   └── sessions.py           # STT session management
├── waves/            # Audio decomposition for speaker control
│   ├── decompose_v3.py       # Core decomposition algorithm
│   ├── worker.py             # ProcessPoolExecutor worker pool
│   └── paths.py              # Wave file path utilities
└── events/           # WebSocket events for TouchDesigner
    ├── models.py             # Event payload schemas
    ├── state.py              # Per-session wave completion tracking
    └── orchestrator.py       # WebSocket event emitter
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/health` | GET | Health check → `{"status": "ok"}` |
| `/v1/agents` | GET | List 6 available agents |
| `/v1/chat` | POST | Run 4-turn workflow, stream responses via SSE |
| `/v1/stt` | POST | Transcribe audio via ElevenLabs Scribe (multipart/form-data) |
| `/v1/events` | WS | WebSocket for TouchDesigner (wave completion events) |
| `/v1/reset` | POST | Clear all conversation history |
| `/v1/audio/*` | GET | Static file server for TTS/STT/wave artifacts |

### SSE Event Protocol

When POST to `/v1/chat`, the response is a Server-Sent Events stream implementing a 4-turn workflow:

```
event: session.start
data: {"sessionId": "abc-123"}

event: turn.start
data: {"turnIndex": 1, "sessionId": "abc-123"}

event: slot.start
data: {"slotId": 1, "agentId": "claude-sonnet-4-5", "turnIndex": 1}

event: slot.done
data: {"slotId": 1, "agentId": "claude-sonnet-4-5", "turnIndex": 1, "kind": "response", "text": "...", "voiceProfile": {...}}

event: slot.audio
data: {"slotId": 1, "turnIndex": 1, "kind": "response", "audioPath": "tts/sessions/.../audio.wav"}

event: turn.done
data: {"turnIndex": 1, "slotCount": 3, "sessionId": "abc-123"}

... (Turn 2: Comments, Turn 3: Replies) ...

event: turn.start
data: {"turnIndex": 4, "sessionId": "abc-123"}

event: summary.start
data: {"sessionId": "abc-123", "turnIndex": 4}

event: summary.done
data: {"sessionId": "abc-123", "turnIndex": 4, "text": "The water held secrets...", "voiceProfile": "calm_soothing"}

event: summary.audio
data: {"sessionId": "abc-123", "turnIndex": 4, "audioPath": "tts/sessions/.../summary.wav"}

event: turn.done
data: {"turnIndex": 4, "slotCount": 1, "sessionId": "abc-123"}

event: done
data: {"completedSlots": 3}
```

**Event Types:**
- `session.start` - New workflow session started (provides sessionId)
- `turn.start` - Turn began (turnIndex: 1=Response, 2=Comment, 3=Reply, 4=Summary)
- `turn.done` - Turn completed for all slots
- `slot.start` - Agent began processing for this slot/turn
- `slot.done` - LLM response complete (includes text, voiceProfile, kind)
- `slot.audio` - TTS audio file ready (includes audioPath)
- `slot.error` - Slot failed (includes `error.type`: `network`|`timeout`|`rate_limit`|`server_error`|`tts_error`)
- `summary.start` - Turn 4 summary generation started
- `summary.done` - Turn 4 summary text complete
- `summary.audio` - Turn 4 summary audio ready
- `done` - All turns finished

**Message Kinds:**
- `response` - Turn 1: Direct response to user
- `comment` - Turn 2: Comment on another agent's response
- `reply` - Turn 3: Reply to received comment
- `summary` - Turn 4: Poetic synthesis of entire dialogue

### WebSocket Events (TouchDesigner)

Connect to `ws://localhost:8000/v1/events` to receive wave completion events:

```json
{
  "type": "turn.waves_ready",
  "sessionId": "abc-123",
  "seq": 1,
  "ts": "2026-01-11T12:00:00.000Z",
  "payload": {
    "turnIndex": 1,
    "slots": [
      {
        "slotId": 1,
        "agentId": "claude-sonnet-4-5",
        "waves": [
          {"waveNum": 1, "targetSlotId": 1, "pathAbs": "/path/to/wave1.wav", "pathRel": "waves/..."},
          {"waveNum": 2, "targetSlotId": 2, "pathAbs": "/path/to/wave2.wav", "pathRel": "waves/..."}
        ]
      }
    ]
  }
}
```

```json
{
  "type": "final_summary.ready",
  "sessionId": "abc-123",
  "seq": 7,
  "ts": "2026-01-11T12:00:30.000Z",
  "payload": {
    "status": "complete",
    "text": "The water held secrets of love unspoken...",
    "waveInfo": {
      "voiceProfile": "calm_soothing",
      "waves": [
        {"slotId": 1, "wavePathAbs": "/path/to/wave1.wav", "wavePathRel": "waves/..."},
        {"slotId": 2, "wavePathAbs": "/path/to/wave2.wav", "wavePathRel": "waves/..."},
        {"slotId": 3, "wavePathAbs": "/path/to/wave3.wav", "wavePathRel": "waves/..."},
        {"slotId": 4, "wavePathAbs": "/path/to/wave4.wav", "wavePathRel": "waves/..."},
        {"slotId": 5, "wavePathAbs": "/path/to/wave5.wav", "wavePathRel": "waves/..."},
        {"slotId": 6, "wavePathAbs": "/path/to/wave6.wav", "wavePathRel": "waves/..."}
      ]
    }
  }
}
```

**WebSocket Event Types:**
- `turn.waves_ready` - All waves for a turn (1, 2, or 3) are ready
- `dialogue.ready` - All waves for turns 1-3 are complete
- `final_summary.ready` - Summary (Turn 4) waves are ready (6 waves for 6 slots)

### Agent Model Mapping

| Agent ID | LiteLLM Model String |
|----------|---------------------|
| `claude-sonnet-4-5` | `anthropic/claude-sonnet-4-20250514` |
| `claude-opus-4-5` | `anthropic/claude-opus-4-20250514` |
| `gpt-5.2` | `openai/gpt-4.1` |
| `gpt-5.1` | `openai/gpt-4o` |
| `gpt-4o` | `openai/gpt-4o` |
| `gemini-3` | `gemini/gemini-2.0-flash` |

### Key Implementation: Concurrent Streaming

The core innovation is multiplexing concurrent LLM streams into a single SSE response:

```python
# streaming.py
async def broadcast_chat(message, slots):
    queue = asyncio.Queue()

    # Launch all slots concurrently
    tasks = [asyncio.create_task(stream_slot(s.slotId, s.agentId, message, queue))
             for s in slots]

    # Monitor completion
    async def monitor():
        await asyncio.gather(*tasks, return_exceptions=True)
        await queue.put(None)  # Sentinel
    asyncio.create_task(monitor())

    # Yield events as they arrive (interleaved from all slots)
    while True:
        event = await queue.get()
        if event is None:
            break
        yield event
```

Each `stream_slot()` task pushes events to the shared queue, which are yielded as they arrive - providing real-time interleaved streaming from all agents.

### Conversation History

Each slot maintains its own conversation history using rawagents' `Conversation` class:

```python
# conversations.py
_conversations: dict[int, Conversation] = {}

def get_or_create_conversation(slot_id: int) -> Conversation:
    if slot_id not in _conversations:
        conv = Conversation()
        conv.add_system(settings.default_system_prompt)
        _conversations[slot_id] = conv
    return _conversations[slot_id]
```

This enables multi-turn conversations per slot - agents remember previous exchanges.

---

## Frontend

### Technology Stack

| Package | Version | Purpose |
|---------|---------|---------|
| SvelteKit | 2.49 | Framework |
| Svelte | 5.45 | UI library (with Runes) |
| Tailwind CSS | 4.1 | Styling |
| bits-ui | 2.14 | Accessible components |
| svelte-dnd-action | 0.9 | Drag and drop |
| svelte-sonner | 1.0 | Toast notifications |

### File Structure

```
frontend/src/
├── routes/
│   └── +page.svelte           # Main orchestrator (handles streaming flow)
├── lib/
│   ├── components/
│   │   ├── AgentPalette.svelte    # Left sidebar - draggable agent list
│   │   ├── SpeakerSlots.svelte    # Center - 3x2 grid of slots
│   │   ├── SpeakerSlotRing.svelte # Individual slot (drop target)
│   │   ├── AudioInputDock.svelte  # Bottom - push-to-talk mic button
│   │   ├── ResponsesPanel.svelte  # Right sidebar - 4-turn response tabs
│   │   ├── ResponseCard.svelte    # Individual response with audio player
│   │   └── ui/                    # Reusable primitives (Button, Input, etc)
│   ├── stores/
│   │   └── app.svelte.ts          # Global state with Svelte 5 Runes
│   ├── utils/
│   │   ├── streaming.ts           # Real SSE client (4-turn workflow support)
│   │   └── mock-responses.ts      # Mock streaming for development
│   ├── config/
│   │   ├── constants.ts           # API_CONFIG, keyboard shortcuts
│   │   └── agents.ts              # Agent display info (colors, icons)
│   └── types/
│       └── index.ts               # TypeScript definitions
└── app.css                        # Global styles + CSS variables
```

### State Management (Svelte 5 Runes)

The `appStore` uses Svelte 5's new Runes API for reactive state:

```typescript
// app.svelte.ts
function createAppStore() {
    // Reactive state
    let slots = $state<Slot[]>(INITIAL_SLOTS);
    let messages = $state<Message[]>([]);
    let isSending = $state(false);

    // Derived state (auto-computed)
    const assignedSlots = $derived(slots.filter(s => s.agentId !== null));
    const canSend = $derived(
        inputValue.trim().length > 0 &&
        assignedSlots.length > 0 &&
        !isSending &&
        isOnline
    );

    // Actions
    function assignAgentToSlot(slotId, agentId) { ... }
    function appendToMessage(messageId, content) { ... }

    return { slots, messages, canSend, assignAgentToSlot, ... };
}
```

### SSE Client Implementation

The frontend uses `fetch` with streaming body reader (not EventSource, which doesn't support POST):

```typescript
// streaming.ts
export function createRealStream(options): { cancel: () => void } {
    const abortController = new AbortController();

    (async () => {
        const response = await fetch(`${API_CONFIG.baseUrl}/v1/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, slots }),
            signal: abortController.signal
        });

        const reader = response.body.getReader();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            // Parse SSE format: "event: xxx\ndata: {...}\n\n"
            // Route to callbacks: onToken, onSlotComplete, onSlotError
        }
    })();

    return { cancel: () => abortController.abort() };
}
```

### UI Layout

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  ┌──────────┐  ┌─────────────────────────────────┐  ┌───────────┐  │
│  │  AGENTS  │  │         SPEAKER SLOTS           │  │ RESPONSES │  │
│  │          │  │                                 │  │T1│T2│T3│T4│  │
│  │ [Claude] │  │    [1]      [2]      [3]        │  │ ─────────  │  │
│  │ [GPT]    │  │                                 │  │ [Slot 1]  │  │
│  │ [Gemini] │  │    [4]      [5]      [6]        │  │  ▶ Play   │  │
│  │   ...    │  │                                 │  │           │  │
│  │          │  │                                 │  │ [Slot 2]  │  │
│  └──────────┘  │         ┌─────────┐             │  │  ▶ Play   │  │
│     240px      │         │  🎤 MIC │             │  │           │  │
│                │         │(hold)   │             │  └───────────┘  │
│                │         └─────────┘             │     320px       │
│                └─────────────────────────────────┘                 │
└────────────────────────────────────────────────────────────────────┘
```

### Mock vs Real Streaming

Toggle in `frontend/src/lib/config/constants.ts`:

```typescript
export const API_CONFIG = {
    baseUrl: 'http://localhost:8000',
    useMock: false  // true = simulated responses, false = real backend
} as const;
```

---

## Audio Artifacts

```
artifacts/
├── tts/sessions/<session_id>/    # TTS outputs per workflow run
│   ├── turn_1/*.wav
│   ├── turn_2/*.wav
│   ├── turn_3/*.wav
│   ├── summary/*.wav             # Turn 4 summary audio
│   └── session.json              # Manifest for TouchDesigner
├── waves/sessions/<session_id>/  # Wave decomposition outputs
│   ├── turn_1/                   # 2 waves per agent
│   │   ├── slot-1_*_v3_wave1.wav
│   │   ├── slot-1_*_v3_wave2.wav
│   │   └── ...
│   ├── turn_2/
│   ├── turn_3/
│   └── summary/                  # 6 waves (one per slot)
│       ├── summary_*_v3_wave1.wav
│       ├── summary_*_v3_wave2.wav
│       └── ... (through wave6)
└── stt/sessions/<session_id>/    # STT inputs
    ├── input.webm
    ├── transcript.json
    └── transcript.txt
```

---

## Configuration

### Environment Variables

Create `.env` in project root (copy from `.env.example`):

```bash
# Required - ElevenLabs for TTS and STT
ELEVENLABS_API_KEY=...

# Required - at least one LLM provider
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Optional server config (RR_ prefix)
RR_HOST=0.0.0.0
RR_PORT=8000
RR_CORS_ORIGINS=["http://localhost:5173","http://localhost:4173"]
RR_LOG_LEVEL=INFO

# Optional LLM behavior
RR_TEMPERATURE=0.7
RR_MAX_TOKENS=500
RR_TIMEOUT_S=60
RR_RETRIES=3

# Optional wave decomposition
RR_WAVES_ENABLED=true
RR_WAVES_MAX_WORKERS=2
RR_WAVES_QUEUE_MAX_SIZE=100
RR_WAVES_JOB_TIMEOUT_S=60

# Optional custom system prompt
RR_DEFAULT_SYSTEM_PROMPT="You are one of six voices..."
```

### Default System Prompt

Agents use a poetic water-themed prompt:

> You are one of six voices in the Reflective Resonance art installation.
> Your words will be transformed into water vibrations.
>
> Guidelines:
> - Respond poetically and metaphorically
> - Reference water, waves, reflection, and fluidity
> - Keep responses concise (1-3 sentences)
> - Express emotional essence over literal meaning

---

## Key Design Decisions

### 1. SSE over WebSocket (Frontend)
- **Decision:** Use Server-Sent Events for frontend streaming
- **Rationale:** Simpler protocol, one-way streaming is sufficient, better HTTP/2 compatibility, automatic reconnection

### 2. WebSocket for TouchDesigner
- **Decision:** Use WebSocket for wave completion events to TouchDesigner
- **Rationale:** TouchDesigner needs push notifications, persistent connection for real-time sync

### 3. asyncio.Queue for Multiplexing
- **Decision:** Use a shared queue instead of separate SSE streams per slot
- **Rationale:** Single HTTP connection, natural interleaving of events, simpler client code, maintains event ordering within slots

### 4. ProcessPoolExecutor for Wave Decomposition
- **Decision:** Run decomposition in separate processes, not async tasks
- **Rationale:** CPU-bound librosa operations would block the event loop; process pool enables true parallelism

### 5. Slot-Aware Frequency Mapping
- **Decision:** Map wave frequencies to target slot ranges instead of fixed harmonic frequencies
- **Rationale:** Creates predictable "dome" pattern for water installation; outer speakers high (80-100Hz), center low (20-40Hz)

### 6. Svelte 5 Runes
- **Decision:** Use new `$state` and `$derived` runes instead of stores
- **Rationale:** Better TypeScript support, clearer reactive flow, simpler syntax, built-in fine-grained reactivity

### 7. Frontend as Source of Truth for Agent Display
- **Decision:** Frontend maintains its own agent list with colors/icons
- **Rationale:** Backend only needs model mapping, display metadata is UI concern, avoids schema coupling

### 8. Per-Slot Conversation History
- **Decision:** Each slot maintains independent conversation memory
- **Rationale:** Supports multi-turn per agent, conversation context persists, allows different conversation flows per slot

### 9. In-Memory Storage
- **Decision:** Conversations stored in Python dict, not database
- **Rationale:** MVP simplicity, no persistence needed for art installation, easily reset between sessions

---

## Development

### Commands

```bash
# Backend
uv sync                                         # Install dependencies
uv run uvicorn backend.main:app --reload        # Dev server with hot reload
uv run python -m backend.main                   # Alternative entry point

# Frontend
cd frontend
npm install                                     # Install dependencies
npm run dev                                     # Dev server (Vite)
npm run build                                   # Production build
npm run check                                   # TypeScript checking

# Testing
curl http://localhost:8000/v1/health            # Health check
curl http://localhost:8000/v1/agents            # List agents
curl -N -X POST http://localhost:8000/v1/chat \ # Test SSE stream
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","slots":[{"slotId":1,"agentId":"gpt-4o"}]}'

# WebSocket testing
wscat -c ws://localhost:8000/v1/events          # Connect to wave events
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1-6` | Select speaker slot |
| `Escape` | Clear slot selection |

### Audio Input

| Gesture | Action |
|---------|--------|
| Hold mic button | Start recording |
| Release mic button | Stop & transcribe |
| Auto-stop at 15s | Max recording length |

---

## Future Work

- ~~**Audio Input:** Replace text input with STT (Speech-to-Text)~~ Implemented
- ~~**Inter-Agent Communication:** Agents responding to each other~~ Implemented (4-turn workflow)
- ~~**Wave Parameters:** Convert responses to speaker control signals~~ Implemented (wave decomposition)
- ~~**TouchDesigner Integration:** Send events to visual system~~ Implemented (WebSocket events)
- **Agent Personalities:** Custom system prompts per agent
- **Audio Playback Sequencing:** Auto-play TTS audio in turn order
- **Conversation Persistence:** Save/restore conversation history
- **Multi-Session Support:** Multiple concurrent installations
