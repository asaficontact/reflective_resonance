"""Speech-to-Text (STT) module using ElevenLabs Scribe v1."""

from backend.stt.elevenlabs_stt import ScribeClient, ScribeError, get_scribe_client
from backend.stt.models import STTResponse, WordTiming
from backend.stt.sessions import STTSession

__all__ = [
    "ScribeClient",
    "ScribeError",
    "get_scribe_client",
    "STTResponse",
    "WordTiming",
    "STTSession",
]
