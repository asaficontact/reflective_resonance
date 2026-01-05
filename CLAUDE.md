# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Reflective Resonance is an interactive art installation with 6 speaker slots controlled by LLM agents. Users assign AI agents to speaker positions, provide input via push-to-talk audio (transcribed via ElevenLabs STT), and receive parallel streaming responses through a 3-turn workflow. Responses are converted to speech via ElevenLabs TTS.

## Commands

### Backend (Python 3.13+ with uv)
```bash
uv sync                                          # Install dependencies
uv run uvicorn backend.main:app --reload --port 8000  # Dev server with hot reload
```

### Frontend (SvelteKit + Svelte 5)
```bash
cd frontend
npm install                                      # Install dependencies
npm run dev                                      # Dev server at localhost:5173
npm run build                                    # Production build
npm run check                                    # TypeScript/Svelte type checking
```

### Testing endpoints
```bash
curl http://localhost:8000/v1/health             # Health check
curl http://localhost:8000/v1/agents             # List agents
# Test SSE stream:
curl -N -X POST http://localhost:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello","slots":[{"slotId":1,"agentId":"gpt-4o"}]}'
```

## Architecture

### 3-Turn Workflow (backend/workflow.py)
The core workflow processes user input through three sequential turns:
1. **Turn 1 (Respond)**: All slots respond to user message in parallel
2. **Turn 2 (Comment)**: Each slot comments on exactly one peer's response
3. **Turn 3 (Reply)**: Slots that received comments reply to them

Each turn generates both LLM text and TTS audio (WAV files via ElevenLabs).

### Backend Structure
```
backend/
├── main.py           # FastAPI routes: /v1/chat (SSE), /v1/stt, /v1/agents, /v1/health
├── workflow.py       # 3-turn orchestrator with parallel LLM + TTS generation
├── streaming.py      # SSE event delegation to workflow
├── sessions.py       # TTS session management (artifacts/tts/sessions/<uuid>/)
├── prompts/          # Jinja2 templates for each turn's LLM prompt
├── tts/              # ElevenLabs TTS client, voice profiles, WAV generation
├── stt/              # ElevenLabs Scribe STT client for audio input
├── agents.py         # Agent registry mapping AgentId → LiteLLM model
└── models.py         # Pydantic models for API requests/responses and SSE events
```

### Frontend Structure
```
frontend/src/
├── routes/+page.svelte           # Main orchestrator (handles SSE streaming flow)
├── lib/
│   ├── stores/app.svelte.ts      # Global state with Svelte 5 Runes ($state, $derived)
│   ├── utils/streaming.ts        # SSE client using fetch + ReadableStream
│   ├── components/
│   │   ├── AudioInputDock.svelte # Push-to-talk microphone input
│   │   ├── SpeakerSlots.svelte   # 3x2 grid of speaker slots
│   │   └── ResponsesPanel.svelte # Turn tabs (T1/T2/T3) with responses
│   └── config/agents.ts          # Agent display info (colors, icons)
```

### SSE Event Protocol
Events flow from backend to frontend during `/v1/chat`:
- `turn.start` / `turn.done` - Turn lifecycle
- `slot.start` / `slot.done` / `slot.error` - Per-slot LLM completion
- `slot.audio` - TTS audio file ready
- `done` - Workflow complete

### Audio Artifacts
```
artifacts/
├── tts/sessions/<session_id>/    # TTS outputs per workflow run
│   ├── turn_1/*.wav
│   ├── turn_2/*.wav
│   ├── turn_3/*.wav
│   └── session.json              # Manifest for TouchDesigner
└── stt/sessions/<session_id>/    # STT inputs
    ├── input.webm
    ├── transcript.json
    └── transcript.txt
```

## Key Patterns

### Concurrent LLM Streaming
`broadcast_chat()` uses `asyncio.Queue` to multiplex parallel LLM streams into a single SSE response, enabling real-time interleaved token streaming from all agents.

### Svelte 5 Runes
Frontend state uses `$state()` for reactive variables and `$derived()` for computed values. The store is a singleton created with `createAppStore()`.

### Voice Profiles
Each agent has multiple voice profiles defined in `backend/tts/profiles.py`. The LLM selects a voice profile per response via structured output.

### Agent Model Mapping
- `claude-sonnet-4-5` → `anthropic/claude-sonnet-4-20250514`
- `claude-opus-4-5` → `anthropic/claude-opus-4-20250514`
- `gpt-5.2` → `openai/gpt-4.1`
- `gpt-5.1`, `gpt-4o` → `openai/gpt-4o`
- `gemini-3` → `gemini/gemini-2.0-flash`

## Environment Variables

Required in `.env`:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
ELEVENLABS_API_KEY=...        # For TTS and STT
```

Optional (RR_ prefix):
- `RR_HOST`, `RR_PORT`, `RR_CORS_ORIGINS`
- `RR_TEMPERATURE`, `RR_MAX_TOKENS`, `RR_TIMEOUT_S`
- `RR_DEFAULT_SYSTEM_PROMPT`

## Type Definitions

Frontend and backend share these core types (defined separately but aligned):
- `AgentId`: `'claude-sonnet-4-5' | 'claude-opus-4-5' | 'gpt-5.2' | 'gpt-5.1' | 'gpt-4o' | 'gemini-3'`
- `SlotId`: `1 | 2 | 3 | 4 | 5 | 6`
- `TurnIndex`: `1 | 2 | 3`
- `MessageKind`: `'response' | 'comment' | 'reply'`
