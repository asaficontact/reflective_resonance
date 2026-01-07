"""FastAPI application with SSE streaming for Reflective Resonance."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
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
from backend.stt import STTResponse, STTSession, ScribeError, get_scribe_client
from backend.waves import shutdown_waves_worker, startup_waves_worker
from backend.events import events_router, shutdown_events, startup_events

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting waves worker pool...")
    await startup_waves_worker()

    logger.info("Starting events orchestrator...")
    await startup_events()

    yield

    # Shutdown
    logger.info("Stopping events orchestrator...")
    await shutdown_events()

    logger.info("Stopping waves worker pool...")
    await shutdown_waves_worker()


app = FastAPI(
    title="Reflective Resonance API",
    description="Backend API for the Reflective Resonance art installation",
    version="1.0.0",
    lifespan=lifespan,
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

# Include WebSocket router for TouchDesigner events
app.include_router(events_router)


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
# Speech-to-Text (STT) Endpoint
# =============================================================================

# MIME type to file extension mapping
MIME_TO_EXT = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/wave": "wav",
    "audio/x-wav": "wav",
    "audio/mp3": "mp3",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/m4a": "m4a",
}

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB limit


@app.post("/v1/stt", response_model=STTResponse)
async def speech_to_text(
    file: UploadFile = File(...),
    language_code: str = Form("en"),  # Default to English
) -> STTResponse:
    """Transcribe uploaded audio using ElevenLabs Scribe v1.

    This endpoint accepts an audio file upload, transcribes it using
    ElevenLabs Scribe v1, and returns the transcript along with metadata.

    All audio files and transcripts are stored in:
        artifacts/stt/sessions/<stt_session_id>/

    Args:
        file: Audio file (webm, ogg, wav, mp3, m4a supported)
        language_code: Optional language code (e.g., "en"). Auto-detect if omitted.

    Returns:
        STTResponse with transcript, session ID, and file paths

    Raises:
        413: File too large (>25MB)
        422: No speech detected
        502: Transcription service error
    """
    # Determine file extension from content type
    content_type = file.content_type or "audio/webm"
    ext = MIME_TO_EXT.get(content_type, "webm")

    logger.info(f"STT request: content_type={content_type}, ext={ext}")

    # Read file and validate size
    audio_bytes = await file.read()
    file_size = len(audio_bytes)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(413, f"File too large ({file_size} bytes). Max: 25MB")

    # Create session and save input audio
    session = STTSession.create()
    input_path = session.save_input_audio(audio_bytes, ext)

    logger.info(
        f"STT session created: session_id={session.session_id}, "
        f"input_path={input_path}, size={file_size}"
    )

    # Transcribe using Scribe
    try:
        client = get_scribe_client()
        result = await client.transcribe(input_path, language_code)
    except ScribeError as e:
        logger.error(f"Scribe error for session {session.session_id}: {e}")
        raise HTTPException(502, "Transcription service error")
    except Exception as e:
        logger.error(f"Unexpected STT error for session {session.session_id}: {e}")
        raise HTTPException(500, "Internal server error")

    # Extract transcript
    transcript = result.get("text", "").strip()
    if not transcript:
        raise HTTPException(422, "No speech detected in audio")

    # Save artifacts
    session.write_transcript(result, transcript)
    session.write_metadata(
        mime_type=content_type,
        duration_ms=0,  # Could estimate from file size if needed
        size_bytes=file_size,
    )

    logger.info(
        f"STT complete: session_id={session.session_id}, "
        f"transcript_length={len(transcript)}"
    )

    # Build response with word timings if available
    words = None
    if "words" in result and result["words"]:
        from backend.stt.models import WordTiming

        words = [
            WordTiming(
                text=w.get("text", ""),
                start=w.get("start", 0.0),
                end=w.get("end", 0.0),
                type=w.get("type", "word"),
            )
            for w in result["words"]
        ]

    return STTResponse(
        stt_session_id=session.session_id,
        transcript=transcript,
        audio_path=session.get_input_relative_path(ext),
        transcript_path=session.get_transcript_relative_path(),
        duration_ms=0,
        mime_type=content_type,
        words=words,
        language_code=result.get("language_code"),
    )


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
