"""Pydantic models for Speech-to-Text (STT) API."""

from pydantic import BaseModel
from typing import Optional, List


class WordTiming(BaseModel):
    """Word-level timing from ElevenLabs Scribe."""

    text: str
    start: float
    end: float
    type: str  # "word" | "spacing" | "audio_event"


class STTResponse(BaseModel):
    """Response from /v1/stt endpoint."""

    stt_session_id: str
    transcript: str
    audio_path: str  # Relative path for retrieval via /v1/audio/
    transcript_path: str  # Relative path for retrieval via /v1/audio/
    duration_ms: int
    mime_type: str
    words: Optional[List[WordTiming]] = None
    language_code: Optional[str] = None


class STTError(BaseModel):
    """Error response for STT endpoint."""

    error: str
    detail: Optional[str] = None
