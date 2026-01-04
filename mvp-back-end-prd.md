# Reflective Resonance — MVP Back-End PRD

**Document status**: Draft (implementation-ready)
**Owner**: Back-end team
**Last updated**: 2025-12-30
**Repo**: `reflective_resonance/`
**Version**: 1.1  

---

## 0) Relationship to Front-End PRD

This backend PRD is designed to be **API-compatible** with the finalized front-end MVP PRD in `mvp-front-end-prd.md`.

In particular, it aligns with:
- **Slot model**: 6 slots (`SlotId` = 1..6)
- **Agent IDs**: same `AgentId` union used by the front-end
- **Error taxonomy**: `network | timeout | rate_limit | server_error | unknown`
- **Concurrency requirement**: one user message → parallel responses from all assigned slots
- **Streaming requirement**: token/chunk streaming per slot (frontend renders as it arrives)
- **MVP constraint**: no audio, no TouchDesigner, no text→speaker-params conversion

---

## 1) Overview

The MVP backend provides a minimal, robust system to:
- expose the list of available LLM agents (models)
- accept a user message and broadcast it to active slots (slot assignments come from frontend)
- stream responses per slot via SSE (Server-Sent Events)
- preserve per-slot conversation state across turns (in-memory)

**Architecture principle**: The **frontend is the source of truth** for slot assignments. The backend does not persist or manage slot state—it receives slot assignments as part of each chat request and streams responses back.

The backend uses the author's agent framework **RawAgents** to manage:
- LLM client creation via LiteLLM
- per-slot conversation memory (in-process)
- parallel execution with `asyncio.gather()`
- streaming from providers (where supported)

---

## 2) Goals (MVP must achieve)

- **API contract stability** so the front-end can ship and iterate quickly
- **Parallel fan-out**: one message → N slot responses (N = #assigned slots)
- **Per-slot state**: each slot keeps its own conversation history
- **Streaming**: emit incremental tokens/chunks per slot when possible
- **Resilience**: one slot failing must not block the others
- **Lean and maintainable**: minimal dependencies and a simple architecture

---

## 3) Non-goals (explicitly out of scope)

- Voice input / STT
- Audio signal generation
- TouchDesigner / OSC integration
- ML conversion of text → speaker parameters
- Multi-user accounts, auth, persistence DB
- Agent-to-agent conversation

---

## 4) High-level architecture

### 4.1 Components

- **API server** (FastAPI)
  - REST endpoint for agents list
  - SSE streaming endpoint for chat responses
  - CORS configured for local front-end dev

- **AgentRegistry**
  - owns one `AsyncLLM` client per model (lazy-initialized, reused across requests)
  - maps `AgentId` → LiteLLM model string

- **ConversationStore**
  - in-memory dictionary keyed by `slotId`
  - stores `Conversation` object (RawAgents) per slot
  - provides conversation continuity across turns

### 4.2 Runtime assumptions (MVP)

- Single kiosk / single session is the primary use case
- No persistence beyond process memory
- Frontend manages slot assignments; backend receives them per-request

---

## 5) Tech stack

### 5.1 Language/runtime
- **Python**: >= 3.13 (required by RawAgents dependency)
- **Dependency manager**: **uv** (virtualenv `.venv` already created)

### 5.2 Core dependencies
- **FastAPI** (HTTP server)
- **Uvicorn** (ASGI server)
- **sse-starlette** (Server-Sent Events support)
- **Pydantic v2** (data models / validation)
- **python-dotenv** (optional; load `.env` in dev)
- **RawAgents** (local/private dependency; see installation options below)

### 5.3 Optional dependencies (recommended)
- **httpx** + **pytest** + **pytest-asyncio** (tests)
- **structlog** or stdlib `logging` (structured logs)

---

## 6) Environment management (uv + .venv)

### 6.1 Local setup (backend dev)

Assumptions:
- You are in repo root: `reflective_resonance/`
- `.venv` exists (already created)

Recommended workflow:

1) **Activate** environment (optional, but useful):

```bash
source .venv/bin/activate
```

2) **Sync** dependencies from `pyproject.toml`:

```bash
uv sync
```

3) **Run** dev server (example; final module path depends on implementation):

```bash
uv run uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

> Note: this PRD describes the intended structure under `backend/`. The current repo does not yet include that package.

### 6.2 RawAgents installation (important)

RawAgents lives at a private/local path on the author’s machine:
`/Users/tawab/Projects/MediaLab/rawagents`

For a team, we need a reproducible install strategy. Acceptable MVP options:

#### Option A (recommended): git dependency
- Host RawAgents in a private git repo and add as a git dependency via uv.

#### Option B: local editable path dependency
- Each developer sets an env var `RAWAGENTS_REPO_PATH` and installs editable:

```bash
uv add --editable "$RAWAGENTS_REPO_PATH"
```

Document the required location in team onboarding notes.

**PRD requirement**: backend must import and use RawAgents APIs exactly as described in `rawagents_for_reflective_resonance.md`.

---

## 7) Configuration (.env)

### 7.1 Required environment variables

The backend uses multiple LLM providers (via RawAgents/LiteLLM). Support these keys:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`

### 7.2 Backend runtime variables

- `RR_HOST` (default `0.0.0.0`)
- `RR_PORT` (default `8000`)
- `RR_CORS_ORIGINS` (comma-separated; default `http://localhost:5173,http://localhost:4173`)
- `RR_LOG_LEVEL` (default `INFO`)

### 7.3 LLM behavior variables (MVP defaults)

- `RR_DEFAULT_SYSTEM_PROMPT` (string)
- `RR_TEMPERATURE` (default `0.7`)
- `RR_MAX_TOKENS` (default `500`)
- `RR_TIMEOUT_S` (default `60`)
- `RR_RETRIES` (default `3`)

---

## 8) Data model (API-level)

The backend API should use IDs matching the front-end PRD.

### 8.1 Identifiers

- `SlotId`: `1 | 2 | 3 | 4 | 5 | 6`
- `AgentId` (must match frontend exactly):
  - `claude-sonnet-4-5`
  - `claude-opus-4-5`
  - `gpt-5.2`
  - `gpt-5.1`
  - `gpt-4o`
  - `gemini-3`

> Note: These are display identifiers that match the frontend. The actual LLM model strings are defined in section 9.

### 8.2 ErrorType (must match FE)
- `network`
- `timeout`
- `rate_limit`
- `server_error`
- `unknown`

### 8.3 Core payloads

#### Agent descriptor

```json
{
  "id": "claude-sonnet-4-5",
  "name": "Claude Sonnet 4.5",
  "provider": "anthropic",
  "description": "Anthropic's fast, capable model",
  "color": "#7C3AED"
}
```

#### Chat turn request (broadcast)

The frontend sends the user message along with current slot assignments. Backend does not persist slot state.

```json
{
  "message": "What do you see in the ripples?",
  "slots": [
    { "slotId": 1, "agentId": "claude-sonnet-4-5" },
    { "slotId": 3, "agentId": "gpt-4o" }
  ]
}
```

Note: No `sessionId` or `threadId` for MVP. Conversation continuity is maintained by backend via in-memory `Conversation` objects keyed by `slotId`.

---

## 9) LLM model mapping (RawAgents config)

Use the model naming strategy from LiteLLM (provider-prefixed strings). RawAgents uses LiteLLM under the hood.

### 9.1 MVP Model Mapping

| AgentId (display) | Provider | LiteLLM model string | Notes |
|-------------------|----------|----------------------|-------|
| `claude-sonnet-4-5` | Anthropic | `anthropic/claude-sonnet-4-20250514` | Fast, capable |
| `claude-opus-4-5` | Anthropic | `anthropic/claude-opus-4-20250514` | Most capable |
| `gpt-5.2` | OpenAI | `openai/gpt-4.1` | Maps to latest GPT-4 series |
| `gpt-5.1` | OpenAI | `openai/gpt-4o` | Maps to GPT-4o |
| `gpt-4o` | OpenAI | `openai/gpt-4o` | Multimodal flagship |
| `gemini-3` | Google | `gemini/gemini-2.0-flash` | Fast Gemini model |

> **Important**: LiteLLM uses `gemini/` prefix for Google models, not `google/`.

> **Note**: The frontend uses placeholder names like `gpt-5.2` for future models. These are mapped to the best available real models. When newer models become available, update the mapping without changing the AgentId.

### 9.2 Streaming Support by Provider

Not all providers/models support streaming equally. RawAgents abstracts this but be aware:

| Provider | Streaming | Notes |
|----------|-----------|-------|
| Anthropic | ✅ Full | Native streaming support |
| OpenAI | ✅ Full | Native streaming support |
| Google Gemini | ✅ Full | Streaming via `gemini/` prefix |

If a model doesn't support streaming, RawAgents will return the full response at once.

> If provider model strings change, **do not change AgentId**. Update mapping only.

---

## 10) API surface (MVP)

### 10.1 Base principles

- Version APIs under `/v1`
- JSON for REST endpoints
- **SSE (Server-Sent Events)** for streaming responses
- All endpoints return errors in a consistent structure
- CORS enabled for frontend development

### 10.2 Health

#### `GET /v1/health`
- **200**: `{ "status": "ok" }`

### 10.3 Agents

#### `GET /v1/agents`
Returns the list of available agents (6).

Response 200:
```json
{
  "agents": [
    {
      "id": "claude-sonnet-4-5",
      "name": "Claude Sonnet 4.5",
      "provider": "anthropic",
      "description": "Anthropic's fast, capable model",
      "color": "#7C3AED"
    }
    // ... 5 more agents
  ]
}
```

### 10.4 Chat (SSE streaming)

#### `POST /v1/chat`

Broadcasts a message to all provided slots and streams responses via SSE.

**Request:**
```json
{
  "message": "What do you see in the ripples?",
  "slots": [
    { "slotId": 1, "agentId": "claude-sonnet-4-5" },
    { "slotId": 3, "agentId": "gpt-4o" }
  ]
}
```

**Response:** `Content-Type: text/event-stream`

SSE events (JSON in `data` field):

**Slot started:**
```
event: slot.start
data: {"slotId": 1, "agentId": "claude-sonnet-4-5"}
```

**Token/chunk (streaming):**
```
event: slot.token
data: {"slotId": 1, "content": "The ripples "}
```

**Slot completed:**
```
event: slot.done
data: {"slotId": 1, "agentId": "claude-sonnet-4-5", "fullContent": "The ripples dance..."}
```

**Slot error:**
```
event: slot.error
data: {"slotId": 1, "agentId": "claude-sonnet-4-5", "error": {"type": "timeout", "message": "Response timed out"}}
```

**All slots finished:**
```
event: done
data: {"completedSlots": 2}
```

### 10.5 Conversation Reset (optional)

#### `POST /v1/reset`
Clears all in-memory conversation history.

Request:
```json
{}
```

Response 200:
```json
{ "status": "ok", "clearedSlots": [1, 2, 3, 4, 5, 6] }
```

### 10.6 Implementation Notes

**SSE vs WebSocket decision:**
- SSE chosen for MVP simplicity
- Unidirectional (server → client) is sufficient for streaming responses
- Better compatibility with standard HTTP infrastructure
- Frontend uses `EventSource` API or `fetch` with ReadableStream
- Can upgrade to WebSocket post-MVP if bidirectional needs arise

---

## 11) RawAgents integration requirements

### 11.1 Conversation state (per slot)

Use RawAgents `Conversation` per slot and keep it in memory:

```python
# In-memory conversation store
conversations: dict[int, Conversation] = {}  # slotId → Conversation

def get_or_create_conversation(slot_id: int) -> Conversation:
    if slot_id not in conversations:
        conversations[slot_id] = Conversation()
    return conversations[slot_id]
```

- On each user turn: add user message to each active slot's conversation
- On completion: add assistant response to that same slot's conversation
- **MVP note**: no persistence beyond process memory is required

### 11.2 Parallel execution with streaming

Use `asyncio.gather()` with per-slot streaming tasks:

```python
async def broadcast_message(message: str, slots: list[SlotRequest]):
    async def stream_slot(slot: SlotRequest):
        conv = get_or_create_conversation(slot.slot_id)
        llm = get_llm_for_agent(slot.agent_id)

        conv.add_user_message(message)

        async for chunk in llm.stream(conv):
            yield SSEEvent("slot.token", {"slotId": slot.slot_id, "content": chunk})

        # After streaming completes, add full response to conversation
        full_response = conv.messages[-1].content
        yield SSEEvent("slot.done", {"slotId": slot.slot_id, "fullContent": full_response})

    # Run all slots concurrently
    await asyncio.gather(*[stream_slot(s) for s in slots])
```

**Note**: Each slot streams independently. Use `asyncio.Queue` or similar to multiplex SSE events.

### 11.3 Default system prompt

MVP uses a single shared system prompt across all agents.

Recommended default (editable via `RR_DEFAULT_SYSTEM_PROMPT` env var):

```text
You are one of six voices in the Reflective Resonance art installation.
Your words will be transformed into water vibrations.

Guidelines:
- Respond poetically and metaphorically
- Reference water, waves, reflection, and fluidity
- Keep responses concise (1-3 sentences)
- Express emotional essence over literal meaning
```

### 11.4 RawAgents streaming limitations

Be aware of these RawAgents/LiteLLM behaviors:
- **Streaming availability**: Most major providers support streaming, but some models may not
- **Chunk size variation**: Token chunks vary in size by provider
- **Error mid-stream**: If an error occurs mid-stream, emit `slot.error` and continue other slots
- **Fallback**: If streaming fails, attempt non-streaming call as fallback

---

## 12) Error handling + mapping (must match FE)

### 12.1 Error mapping rules

Map backend exceptions into FE `ErrorType`:

| ErrorType | Trigger Conditions |
|-----------|-------------------|
| `timeout` | Provider timeouts, `asyncio.TimeoutError` |
| `rate_limit` | Provider rate limit errors (429) |
| `network` | DNS, connection errors, transient connectivity issues |
| `server_error` | Unhandled exceptions in backend logic |
| `unknown` | Anything not classifiable |

### 12.2 HTTP error envelope (REST endpoints)

For non-streaming endpoints, use:

```json
{
  "error": {
    "type": "server_error",
    "message": "Human readable message",
    "details": { "optional": "object" }
  }
}
```

### 12.3 Streaming error semantics

Errors must be **per-slot**, not global:
- A slot that errors emits `slot.error` event
- Other slots continue streaming independently
- `done` event fires after all slots have either `slot.done` or `slot.error`

---

## 13) Rate limiting, retries, and timeouts (MVP)

MVP aims for stability over throughput.

Recommended defaults (match FE expectations):
- `RESPONSE_TIMEOUT_MS`: 30000 (per slot)
- `MAX_RETRIES`: 3 (per slot per turn)
- `RETRY_DELAY_MS`: 1000
- `RATE_LIMIT_BACKOFF_MS`: 5000

Retry policy:
- Only retry on: `network`, `timeout`, `rate_limit`
- Do not retry on obvious validation errors

---

## 14) Project structure (recommended)

Simplified structure for MVP:

```
reflective_resonance/
├── backend/
│   ├── __init__.py
│   ├── main.py                # FastAPI app + uvicorn entry
│   ├── config.py              # Settings + env parsing
│   ├── models.py              # Pydantic request/response models
│   ├── agents.py              # AgentId → LiteLLM model mapping
│   ├── conversations.py       # In-memory conversation store
│   └── streaming.py           # SSE event generation + multiplexing
├── pyproject.toml             # Dependencies (including rawagents)
└── .env.example               # Template for env vars
```

Key simplifications from earlier draft:
- No separate `registry.py`, `speaker.py`, `manager.py` — combined into simpler modules
- `main.py` contains FastAPI app directly
- `conversations.py` handles both conversation storage and RawAgents integration

---

## 15) Testing plan

### 15.1 Unit tests (pytest)

- Agent mapping is correct and stable (`AgentId` → model string)
- Conversation store:
  - Creates new conversation for new slot
  - Reuses existing conversation for same slot
  - Reset clears all conversations
- Error mapping function maps representative exceptions correctly

### 15.2 Integration tests (httpx + pytest-asyncio)

REST:
- `GET /v1/agents` returns 6 agents with required fields
- `GET /v1/health` returns `{ "status": "ok" }`

SSE Streaming:
- `POST /v1/chat`:
  - Emits `slot.start` for each slot
  - Emits `slot.token` chunks during streaming
  - Emits `slot.done` when slot completes
  - Emits `slot.error` for forced failures (per-slot)
  - Emits final `done` event after all slots complete/error

### 15.3 Local manual testing (developer checklist)

- Start server: `uv run uvicorn backend.main:app --reload`
- Call `GET /v1/agents` to verify agent list
- Use curl or httpie to test SSE streaming:
  ```bash
  curl -X POST http://localhost:8000/v1/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello", "slots": [{"slotId": 1, "agentId": "claude-sonnet-4-5"}]}'
  ```
- Force an error (e.g., invalid API key) and verify per-slot error semantics

---

## 16) Acceptance criteria (definition of done)

Backend MVP is "done" when:

- **Agents**
  - `GET /v1/agents` returns 6 agents with stable `AgentId`s matching FE PRD

- **Chat (SSE Streaming)**
  - `POST /v1/chat` accepts message + slot assignments from frontend
  - Fans out to all provided slots in parallel
  - Streams responses per slot via SSE
  - One slot failure does not block others (`slot.error` per slot)
  - Emits `done` event when all slots complete

- **Conversation State**
  - Each slot maintains independent conversation memory across multiple turns
  - Conversations persist in-memory for session duration
  - `POST /v1/reset` clears all conversation history

- **Dev workflow**
  - Works with uv + `.venv`
  - Requires Python >= 3.13
  - Documented `.env` variables for provider keys
  - Single command to start: `uv run uvicorn backend.main:app --reload`

---

## 17) Decisions made

These questions from the original draft have been resolved:

1) **Frontend integration mode** → ✅ Decided
   - Frontend calls Python backend directly (no SvelteKit BFF proxy for MVP)
   - Using SSE for streaming (simpler than WebSocket, sufficient for unidirectional streaming)

2) **Session model** → ✅ Simplified for MVP
   - Single kiosk session assumed
   - No `sessionId` or `threadId` — removed to reduce complexity
   - Conversations keyed by `slotId` only

3) **Slot management** → ✅ Frontend is source of truth
   - Backend does not persist slot assignments
   - Frontend sends slot assignments with each chat request
   - Removes need for `PUT/DELETE /v1/slots/{slotId}` endpoints

4) **Where should backend live** → `backend/` inside this repo

## 18) Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2025-12-30 | Major revision based on RawAgents analysis: Python >=3.13, SSE-only streaming (removed WebSocket), frontend as slot source of truth (removed slot CRUD endpoints), simplified API and project structure, correct LiteLLM model strings (gemini/ prefix), `server_error` ErrorType (was `server`), added streaming limitations note |
| 1.0 | 2025-12-30 | Initial draft |


