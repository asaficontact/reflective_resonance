# Reflective Resonance

An interactive art installation featuring 6 speaker slots controlled by multiple LLM agents. Users assign AI agents to speaker positions via drag-and-drop, send messages, and receive parallel streaming responses. The system is designed to eventually transform text responses into water wave parameters for physical speakers.

**Current Stage:** MVP - Text-based interaction with real-time LLM streaming.

## Quick Start

```bash
# 1. Setup environment
cp .env.example .env
# Edit .env with your API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY)

# 2. Start backend (requires Python 3.13+)
uv sync
uv run uvicorn backend.main:app --reload --port 8000

# 3. Start frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 - drag agents to slots, type a message, watch responses stream.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (SvelteKit)                           │
│  ┌─────────────┐     ┌──────────────────┐     ┌───────────────────────────┐ │
│  │AgentPalette │     │   SpeakerSlots   │     │    ResponsesPanel         │ │
│  │(drag source)│────▶│ (6 slot grid)    │     │  (streaming responses)    │ │
│  └─────────────┘     └────────┬─────────┘     └───────────────────────────┘ │
│                               │                            ▲                │
│                               ▼                            │                │
│                      ┌────────────────┐                    │                │
│                      │   ChatDock     │                    │                │
│                      │ (message input)│                    │                │
│                      └───────┬────────┘                    │                │
│                              │                             │                │
│              ┌───────────────▼─────────────────────────────┘                │
│              │         appStore (Svelte 5 Runes)                            │
│              │  - slots[], messages[], selectedSlotId                       │
│              │  - assignAgentToSlot(), addMessage(), appendToMessage()      │
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
│  │  POST /v1/chat ──▶ EventSourceResponse(broadcast_chat(...))         │    │
│  │  GET  /v1/agents, /v1/health, POST /v1/reset                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                               │                                             │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    streaming.py (SSE Multiplexing)                  │    │
│  │                                                                     │    │
│  │   broadcast_chat()                                                  │    │
│  │       │                                                             │    │
│  │       ├──▶ stream_slot(1) ──┐                                       │    │
│  │       ├──▶ stream_slot(2) ──┼──▶ asyncio.Queue ──▶ yield SSE events │    │
│  │       └──▶ stream_slot(N) ──┘                                       │    │
│  │                                                                     │    │
│  │   Events: slot.start → slot.token* → slot.done|slot.error → done    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                               │                                             │
│         ┌─────────────────────┼─────────────────────┐                       │
│         ▼                     ▼                     ▼                       │
│  ┌─────────────┐     ┌─────────────────┐    ┌──────────────┐                │
│  │  agents.py  │     │conversations.py │    │  config.py   │                │
│  │             │     │                 │    │              │                │
│  │ AgentId →   │     │ slotId →        │    │ .env vars    │                │
│  │ LiteLLM     │     │ Conversation    │    │ system       │                │
│  │ model map   │     │ (history)       │    │ prompt       │                │
│  └──────┬──────┘     └─────────────────┘    └──────────────┘                │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                  rawagents (AsyncLLM + LiteLLM)                      │    │
│  │   anthropic/claude-*, openai/gpt-*, gemini/gemini-*                 │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Backend

### Technology Stack

| Package | Version | Purpose |
|---------|---------|---------|
| Python | ≥3.13 | Required by rawagents |
| FastAPI | ≥0.115 | HTTP framework |
| sse-starlette | ≥2.2 | Server-Sent Events |
| rawagents | local | LLM client (AsyncLLM, Conversation) |
| pydantic | ≥2.0 | Request/response validation |
| uvicorn | ≥0.32 | ASGI server |

### File Structure

```
backend/
├── main.py           # FastAPI app, routes, CORS
├── streaming.py      # SSE multiplexing with asyncio.Queue
├── agents.py         # Agent registry, LLM client factory
├── conversations.py  # Per-slot conversation history
├── models.py         # Pydantic models for API + SSE events
└── config.py         # Settings from environment
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/health` | GET | Health check → `{"status": "ok"}` |
| `/v1/agents` | GET | List 6 available agents |
| `/v1/chat` | POST | Stream responses via SSE |
| `/v1/reset` | POST | Clear all conversation history |

### SSE Event Protocol

When POST to `/v1/chat`, the response is a Server-Sent Events stream:

```
event: slot.start
data: {"slotId": 1, "agentId": "claude-sonnet-4-5"}

event: slot.token
data: {"slotId": 1, "content": "Rip"}

event: slot.token
data: {"slotId": 1, "content": "ples "}

event: slot.done
data: {"slotId": 1, "agentId": "claude-sonnet-4-5", "fullContent": "Ripples greet your flowing soul."}

event: done
data: {"completedSlots": 2}
```

**Event Types:**
- `slot.start` - Agent began streaming for this slot
- `slot.token` - Token chunk (may arrive rapidly)
- `slot.done` - Slot completed successfully
- `slot.error` - Slot failed (includes `error.type`: `network`|`timeout`|`rate_limit`|`server_error`)
- `done` - All slots finished

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
│   │   ├── ChatDock.svelte        # Bottom - message input
│   │   ├── ResponsesPanel.svelte  # Right sidebar - streaming responses
│   │   ├── ResponseCard.svelte    # Individual response display
│   │   └── ui/                    # Reusable primitives (Button, Input, etc)
│   ├── stores/
│   │   └── app.svelte.ts          # Global state with Svelte 5 Runes
│   ├── utils/
│   │   ├── streaming.ts           # Real SSE client (createRealStream)
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
│  │          │  │                                 │  │           │  │
│  │ [Claude] │  │    [1]      [2]      [3]        │  │ [Slot 1]  │  │
│  │ [GPT]    │  │                                 │  │ streaming │  │
│  │ [Gemini] │  │    [4]      [5]      [6]        │  │           │  │
│  │   ...    │  │                                 │  │ [Slot 2]  │  │
│  │          │  │                                 │  │ done      │  │
│  └──────────┘  │   ┌───────────────────────┐     │  │           │  │
│     240px      │   │ Type message... [Send]│     │  └───────────┘  │
│                │   └───────────────────────┘     │     320px       │
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

## Configuration

### Environment Variables

Create `.env` in project root (copy from `.env.example`):

```bash
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

### 1. SSE over WebSocket
- **Decision:** Use Server-Sent Events instead of WebSocket
- **Rationale:** Simpler protocol, one-way streaming is sufficient, better HTTP/2 compatibility, automatic reconnection

### 2. asyncio.Queue for Multiplexing
- **Decision:** Use a shared queue instead of separate SSE streams per slot
- **Rationale:** Single HTTP connection, natural interleaving of events, simpler client code, maintains event ordering within slots

### 3. Svelte 5 Runes
- **Decision:** Use new `$state` and `$derived` runes instead of stores
- **Rationale:** Better TypeScript support, clearer reactive flow, simpler syntax, built-in fine-grained reactivity

### 4. Frontend as Source of Truth for Agent Display
- **Decision:** Frontend maintains its own agent list with colors/icons
- **Rationale:** Backend only needs model mapping, display metadata is UI concern, avoids schema coupling

### 5. Per-Slot Conversation History
- **Decision:** Each slot maintains independent conversation memory
- **Rationale:** Supports multi-turn per agent, conversation context persists, allows different conversation flows per slot

### 6. In-Memory Storage
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
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1-6` | Select speaker slot |
| `Escape` | Clear slot selection |
| `Enter` | Send message |
| `Shift+Enter` | New line in input |

---

## Future Work

- **Audio Input:** Replace text input with STT (Speech-to-Text)
- **Wave Parameters:** Convert responses to speaker control signals
- **Agent Personalities:** Custom system prompts per agent
- **Inter-Agent Communication:** Agents responding to each other
- **TouchDesigner Integration:** Send events to visual system
