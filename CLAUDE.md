# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Reflective Resonance is an interactive art installation with 6 speaker slots controlled by LLM agents. Users drag-and-drop agents onto slots, send messages, and receive parallel streaming responses from all assigned agents. The system is designed to eventually convert text responses into water wave parameters for physical speakers.

## Commands

### Backend (Python 3.13+ with uv)
```bash
uv sync                                    # Install dependencies
uv run uvicorn backend.main:app --reload   # Dev server on :8000
uv run python -m backend.main              # Alternative start
```

### Frontend (Node.js)
```bash
cd frontend
npm install                    # Install dependencies
npm run dev                    # Dev server on :5173
npm run build                  # Production build
npm run check                  # TypeScript/Svelte type checking
```

## Architecture

```
├── backend/                    # FastAPI + SSE streaming
│   ├── main.py                # Routes: /v1/health, /v1/agents, /v1/chat, /v1/reset
│   ├── streaming.py           # asyncio.Queue multiplexes concurrent LLM streams
│   ├── agents.py              # AgentId → LiteLLM model mapping, lazy AsyncLLM clients
│   ├── conversations.py       # In-memory per-slot conversation history
│   ├── models.py              # Pydantic request/response/SSE event models
│   └── config.py              # Settings from .env with RR_ prefix
│
└── frontend/                   # SvelteKit 2 + Svelte 5 + Tailwind
    └── src/
        ├── routes/+page.svelte           # Main orchestrator (streaming, slots, messages)
        ├── lib/stores/app.svelte.ts      # Svelte 5 runes store (slots, messages, status)
        ├── lib/utils/streaming.ts        # Real SSE client (POST + fetch streaming)
        ├── lib/utils/mock-responses.ts   # Mock streaming for dev
        ├── lib/config/constants.ts       # API_CONFIG.useMock toggles real/mock
        └── lib/components/               # AgentPalette, SpeakerSlots, ChatDock, ResponsesPanel
```

## Key Patterns

**SSE Streaming Flow:**
1. Frontend POSTs to `/v1/chat` with message + slots array
2. Backend spawns concurrent `stream_slot()` tasks per agent
3. All tasks push events to shared `asyncio.Queue`
4. Events: `slot.start` → `slot.token`* → `slot.done|slot.error` → `done`

**Agent Model Mapping (backend/agents.py):**
- `claude-sonnet-4-5` → `anthropic/claude-sonnet-4-20250514`
- `claude-opus-4-5` → `anthropic/claude-opus-4-20250514`
- `gpt-5.2` → `openai/gpt-4.1`
- `gpt-5.1`, `gpt-4o` → `openai/gpt-4o`
- `gemini-3` → `gemini/gemini-2.0-flash`

**Frontend State (Svelte 5 runes):**
- `appStore.slots` - 6 slots with agentId, status, retryCount
- `appStore.messages` - conversation history with streaming state
- Derived: `canSend`, `assignedSlots`, `isStreaming`

## Configuration

**.env (root directory):**
```
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
```

**Toggle mock/real streaming:** Edit `frontend/src/lib/config/constants.ts`:
```ts
export const API_CONFIG = {
    baseUrl: 'http://localhost:8000',
    useMock: false  // true = mock streaming, false = real backend
}
```

## Type Definitions

Frontend and backend share these core types (defined separately but aligned):
- `AgentId`: `'claude-sonnet-4-5' | 'claude-opus-4-5' | 'gpt-5.2' | 'gpt-5.1' | 'gpt-4o' | 'gemini-3'`
- `SlotId`: `1 | 2 | 3 | 4 | 5 | 6`
- `SlotStatus`: `'idle' | 'streaming' | 'done' | 'error'`
- `ErrorType`: `'network' | 'timeout' | 'rate_limit' | 'server_error' | 'unknown'`
