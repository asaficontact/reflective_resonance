"""FastAPI application with SSE streaming for Reflective Resonance."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
    """Stream LLM responses to all requested slots via SSE.

    This endpoint broadcasts the user message to all slots specified in the
    request and streams back responses as Server-Sent Events. Each slot
    streams independently and concurrently.

    SSE Events emitted:
    - slot.start: When a slot begins streaming
    - slot.token: For each token/chunk during streaming
    - slot.done: When a slot completes successfully
    - slot.error: When a slot encounters an error
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
