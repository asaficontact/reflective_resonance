"""FastAPI application with SSE streaming for Reflective Resonance."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from backend.agents import AGENTS
from backend.config import settings
from backend.conversations import reset_all_conversations
from backend.models import (
    AgentsResponse,
    ChatRequest,
    HealthResponse,
    ResetResponse,
)
from backend.streaming import broadcast_chat

# =============================================================================
# Logging Configuration
# =============================================================================

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="Reflective Resonance API",
    description="Backend API for the Reflective Resonance art installation",
    version="1.0.0",
)

# CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount artifacts directory for audio file retrieval
# Audio files served at: GET /v1/audio/tts/sessions/{session_id}/{filename}.wav
ARTIFACTS_DIR = Path("artifacts")
ARTIFACTS_DIR.mkdir(exist_ok=True)
app.mount("/v1/audio", StaticFiles(directory=str(ARTIFACTS_DIR)), name="audio")


# =============================================================================
# API Routes
# =============================================================================


@app.get("/v1/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok")


@app.get("/v1/agents", response_model=AgentsResponse)
async def get_agents() -> AgentsResponse:
    """Get list of available agents."""
    return AgentsResponse(agents=AGENTS)


@app.post("/v1/chat")
async def chat(request: ChatRequest):
    """Broadcast message to all slots and generate TTS audio via SSE.

    This endpoint broadcasts the user message to all slots specified in the
    request. Each slot gets a structured LLM response (text + voice_profile)
    and TTS audio is generated. All processing happens concurrently.

    SSE Events emitted:
    - slot.start: When a slot begins processing
    - slot.done: When LLM response complete (includes text + voiceProfile)
    - slot.audio: When TTS audio file is ready (includes audioPath)
    - slot.error: When an error occurs (LLM or TTS)
    - done: When all slots have completed or errored
    """
    logger.info(
        f"Chat request: message='{request.message[:50]}...', "
        f"slots={[(s.slotId, s.agentId) for s in request.slots]}"
    )

    return EventSourceResponse(
        broadcast_chat(request.message, request.slots),
        headers={"X-Accel-Buffering": "no"},  # Disable nginx buffering
    )


@app.post("/v1/reset", response_model=ResetResponse)
async def reset() -> ResetResponse:
    """Clear all conversation history."""
    cleared = reset_all_conversations()
    logger.info(f"Reset conversations for slots: {cleared}")
    return ResetResponse(status="ok", clearedSlots=cleared)


# =============================================================================
# Development Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
