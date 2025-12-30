# Reflective Resonance — MVP Back-End PRD

**Document status**: Draft (implementation-ready)  
**Owner**: Back-end team  
**Last updated**: 2025-12-30  
**Repo**: `reflective_resonance/`  
**Version**: 1.0  

---

## 0) Relationship to Front-End PRD

This backend PRD is designed to be **API-compatible** with the finalized front-end MVP PRD in `mvp-front-end-prd.md`.

In particular, it aligns with:
- **Slot model**: 6 slots (`SlotId` = 1..6)
- **Agent IDs**: same `AgentId` union used by the front-end
- **Error taxonomy**: `network | timeout | rate_limit | server | unknown`
- **Concurrency requirement**: one user message → parallel responses from all assigned slots
- **Streaming requirement**: token/chunk streaming per slot (frontend renders as it arrives)
- **MVP constraint**: no audio, no TouchDesigner, no text→speaker-params conversion

---

## 1) Overview

The MVP backend provides a minimal, robust system to:
- expose the list of available LLM agents (models)
- manage assignment of agents to 6 speaker slots
- accept a user message and broadcast it to active slots
- return responses per slot (streaming if possible)
- preserve per-slot conversation state across turns (per-slot “thread”)

The backend uses the author’s agent framework **RawAgents** to manage:
- LLM client creation
- per-slot conversation memory
- parallel execution
- optional streaming from providers

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
  - REST endpoints for configuration/state
  - Streaming endpoint(s) for responses
  - CORS configured for local front-end dev

- **AgentRegistry**
  - owns one `AsyncLLM` client per model (reused across requests)

- **SpeakerManager**
  - owns 6 `SpeakerSlot` instances (slot 1..6)
  - manages assignment/unassignment
  - manages per-slot conversation state
  - runs broadcast fan-out

- **SpeakerSlot**
  - has slotId
  - assigned agentId (or None)
  - `Conversation` object (RawAgents) per slot

### 4.2 Runtime assumptions (MVP)

- Single kiosk / single session is the primary use case.
- We still design APIs to optionally include a `sessionId` so future multi-session support is not blocked.

---

## 5) Tech stack

### 5.1 Language/runtime
- **Python**: >= 3.12 (matches repo `pyproject.toml`)
- **Dependency manager**: **uv** (virtualenv `.venv` already created)

### 5.2 Core dependencies
- **FastAPI** (HTTP server)
- **Uvicorn** (ASGI server)
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
- `AgentId`:
  - `claude-sonnet-4-5`
  - `claude-opus-4-5`
  - `gpt-5.2`
  - `gpt-5.1`
  - `gpt-4o`
  - `gemini-3`

### 8.2 ErrorType (must match FE)
- `network`
- `timeout`
- `rate_limit`
- `server`
- `unknown`

### 8.3 Core payloads

#### Agent descriptor

```json
{
  "id": "gpt-5.2",
  "label": "GPT 5.2",
  "provider": "openai",
  "model": "openai/gpt-5.2",
  "description": "Latest OpenAI reasoning",
  "accentColor": "#0EA5E9"
}
```

#### Slot state

```json
{
  "id": 3,
  "agentId": "gpt-5.2",
  "status": "idle",
  "errorType": null,
  "retryCount": 0
}
```

#### Chat turn request (broadcast)

```json
{
  "sessionId": "optional-string",
  "message": "What do you see in the ripples?",
  "slots": [
    { "slotId": 1, "agentId": "claude-sonnet-4-5", "threadId": "optional" },
    { "slotId": 3, "agentId": "gpt-5.2", "threadId": "optional" }
  ]
}
```

---

## 9) LLM model mapping (RawAgents config)

Use the model naming strategy described in `rawagents_for_reflective_resonance.md` (provider-prefixed strings).

Recommended MVP mapping:

| AgentId | Provider | RawAgents/LiteLLM model string |
|--------:|----------|--------------------------------|
| `claude-sonnet-4-5` | anthropic | `anthropic/claude-sonnet-4-20250514` |
| `claude-opus-4-5` | anthropic | `anthropic/claude-opus-4-20250514` |
| `gpt-5.2` | openai | `openai/gpt-5.2` |
| `gpt-5.1` | openai | `openai/gpt-5.1` |
| `gpt-4o` | openai | `openai/gpt-4o` |
| `gemini-3` | google | `google/gemini-3.0-pro` |

> If provider model strings change, **do not change AgentId**. Update mapping only.

---

## 10) API surface (MVP)

### 10.1 Base principles

- Version APIs under `/v1` (recommended).
- JSON everywhere for REST.
- Streaming via **WebSocket** (recommended) and/or **SSE**.
- All endpoints return errors in a consistent structure.

### 10.2 Health

#### `GET /v1/health`
- **200**: `{ "status": "ok" }`

### 10.3 Agents

#### `GET /v1/agents`
Returns the list of available agents (6).

Response 200:
```json
{ "agents": [ /* Agent[] */ ] }
```

### 10.4 Slot configuration

#### `GET /v1/slots`
Returns the server-side view of current slot assignments and status.

Response 200:
```json
{ "slots": [ /* Slot[] */ ] }
```

#### `PUT /v1/slots/{slotId}`
Assign an agent to a slot.

Request:
```json
{ "agentId": "gpt-5.2", "resetThread": false }
```

Semantics:
- If slot was empty → assign.
- If slot occupied → replace.
- If `resetThread=true`, clear conversation history for that slot.

Response 200:
```json
{ "slot": /* Slot */ }
```

#### `DELETE /v1/slots/{slotId}`
Unassign an agent from a slot.

Request (optional):
```json
{ "resetThread": true }
```

Response 200:
```json
{ "slot": /* Slot */ }
```

#### `POST /v1/reset`
Resets all slots and conversations.

Request:
```json
{ "resetSlots": true, "resetConversations": true }
```

Response 200:
```json
{ "status": "ok" }
```

### 10.5 Chat turns (broadcast)

There are two acceptable MVP implementations. Pick one and implement the other only if time permits.

#### Option A (recommended): WebSocket streaming (single connection, best UX)

##### `GET /v1/ws` (WebSocket)

Client → server messages (JSON):

1) **Create a turn (broadcast)**
```json
{
  "type": "turn.create",
  "turnId": "uuid-from-client-or-server",
  "sessionId": "optional",
  "message": "User text here",
  "slots": [
    { "slotId": 1, "agentId": "claude-sonnet-4-5", "threadId": "optional" },
    { "slotId": 3, "agentId": "gpt-5.2", "threadId": "optional" }
  ]
}
```

Server → client streaming messages:

- **Turn ack**
```json
{ "type": "turn.ack", "turnId": "..." }
```

- **Slot started**
```json
{ "type": "slot.start", "turnId": "...", "slotId": 3, "agentId": "gpt-5.2" }
```

- **Token/chunk**
```json
{ "type": "slot.token", "turnId": "...", "slotId": 3, "agentId": "gpt-5.2", "content": "next chunk " }
```

- **Slot done**
```json
{
  "type": "slot.done",
  "turnId": "...",
  "slotId": 3,
  "agentId": "gpt-5.2",
  "fullContent": "full response text...",
  "usage": { "tokens": 123 },
  "latencyMs": 842
}
```

- **Slot error**
```json
{
  "type": "slot.error",
  "turnId": "...",
  "slotId": 3,
  "agentId": "gpt-5.2",
  "error": { "type": "timeout", "message": "Response timed out" }
}
```

- **Turn done**
```json
{ "type": "turn.done", "turnId": "...", "slotCount": 2 }
```

**Backpressure rule**: server must not buffer unbounded tokens; if client is slow, it’s acceptable to coalesce tokens into larger chunks.

#### Option B: HTTP streaming (SSE or fetch streaming)

##### `POST /v1/turns` (streaming response)

Request body = broadcast request.

Response:
- streaming `text/event-stream` (SSE) or chunked NDJSON
- events include `slot.start`, `slot.token`, `slot.done`, `slot.error`, `turn.done`

> Use this if WebSocket is undesirable in the deployment environment.

### 10.6 Per-slot chat (optional compatibility with FE draft contract)

If the front-end wants to call per slot (as described in its “Proposed API contract”), support:

#### `POST /v1/chat`

Request:
```json
{ "slotId": 3, "agentId": "gpt-5.2", "message": "..." , "threadId": "optional" }
```

Response:
- streaming tokens for that slot only
- or non-streaming JSON for MVP fallback

---

## 11) RawAgents integration requirements

### 11.1 Conversation state (per slot)

Use RawAgents `Conversation` per slot and keep it in memory:
- on each user turn: add user message to each active slot conversation
- on completion: add assistant response to that same slot conversation

**MVP note**: no persistence beyond process memory is required.

### 11.2 Parallel execution

For non-streaming responses:
- run `asyncio.gather()` over active slots (as described in the RawAgents doc)

For streaming responses:
- prefer per-slot `AsyncLLM.stream()` and multiplex chunks into:
  - WebSocket messages (`slot.token`)
  - or SSE events

### 11.3 Default system prompt

MVP requires a single shared system prompt across agents.

Recommended default (editable via env var):

```text
You are one of six voices in the Reflective Resonance art installation.
Your words will be transformed into water vibrations.

Guidelines:
- Respond poetically and metaphorically
- Reference water, waves, reflection, and fluidity
- Keep responses concise (1-3 sentences)
- Express emotional essence over literal meaning
```

---

## 12) Error handling + mapping (must match FE)

### 12.1 Error mapping rules

Map backend exceptions into FE `ErrorType`:

- `timeout`
  - provider timeouts, `asyncio.TimeoutError`
- `rate_limit`
  - provider rate limit errors
- `network`
  - DNS, connection errors, transient connectivity issues
- `server`
  - unhandled exceptions in backend logic
- `unknown`
  - anything not classifiable

### 12.2 HTTP error envelope (REST endpoints)

For non-streaming endpoints, use:

```json
{
  "error": {
    "type": "server",
    "message": "Human readable message",
    "details": { "optional": "object" }
  }
}
```

### 12.3 Streaming error semantics

Errors must be **per-slot**, not global:
- a slot that errors sends `slot.error`
- other slots continue streaming
- `turn.done` fires after all slots have either `slot.done` or `slot.error`

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

This PRD assumes a `backend/` package is created:

```
reflective_resonance/
├── backend/
│   ├── __init__.py
│   ├── api.py                 # FastAPI routes (v1)
│   ├── settings.py            # env parsing + defaults
│   ├── models.py              # Pydantic request/response models
│   ├── agents.py              # AgentId → provider/model mapping
│   ├── registry.py            # AgentRegistry (AsyncLLM per model)
│   ├── speaker.py             # SpeakerSlot
│   ├── manager.py             # SpeakerManager
│   ├── streaming.py           # SSE/WS multiplex helpers
│   └── errors.py              # ErrorType mapping helpers
└── main.py                    # optional: starts uvicorn in dev
```

---

## 15) Testing plan

### 15.1 Unit tests (pytest)

- Agent mapping is correct and stable (`AgentId` → model string)
- SpeakerManager:
  - assign/unassign
  - reset behaviors
  - conversation state isolation per slot
  - broadcast concurrency doesn’t cross-contaminate slot states
- Error mapping function maps representative exceptions correctly

### 15.2 Integration tests (httpx + pytest-asyncio)

REST:
- `GET /v1/agents` returns 6 agents with required fields
- slot CRUD endpoints work and validate input

Streaming:
- WebSocket:
  - `turn.create` yields `turn.ack`
  - emits `slot.start` then `slot.token*` then `slot.done` per active slot
  - emits `slot.error` for forced failures
  - emits `turn.done` at end

### 15.3 Local manual testing (developer checklist)

- Start server
- Assign 2–6 slots
- Send a message and watch streaming
- Force an error (e.g., invalid API key) and ensure per-slot error semantics hold

---

## 16) Acceptance criteria (definition of done)

Backend MVP is “done” when:

- **Agents**
  - `GET /v1/agents` returns 6 agents with stable `AgentId`s matching FE PRD

- **Slots**
  - Can assign/unassign agents to slots 1..6 via REST
  - Slot state is queryable (`GET /v1/slots`)

- **Chat**
  - A broadcast turn fans out to all assigned slots
  - Responses are returned per slot
  - Streaming is supported (WebSocket recommended)
  - One slot failure does not block others

- **State**
  - Each slot maintains independent conversation memory across multiple turns

- **Dev workflow**
  - Works with uv + `.venv`
  - Documented `.env` variables for provider keys

---

## 17) Open questions (confirm before implementation)

1) **Frontend integration mode**
   - Will FE call Python backend directly, or via a SvelteKit “BFF” proxy?
   - If direct, prefer WebSocket or HTTP streaming?

2) **Session model**
   - Single kiosk session is assumed; do we need multiple simultaneous sessions?
   - If yes, should `sessionId` be client-provided or server-issued?

3) **Where should backend live**
   - `backend/` inside this repo, or a separate service repo?


