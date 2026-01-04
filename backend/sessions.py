"""Session management for TTS audio storage.

Each chat request creates a new session with a UUID. Audio files
are stored in the session directory with the naming convention:
    artifacts/tts/sessions/<session_id>/<agent_id>_<voice_profile>.wav
"""

import uuid
from dataclasses import dataclass
from pathlib import Path

SESSIONS_BASE = Path("artifacts/tts/sessions")


@dataclass
class TTSSession:
    """Manages a TTS session and its audio files."""

    session_id: str
    output_dir: Path

    @classmethod
    def create(cls) -> "TTSSession":
        """Create a new session with UUID."""
        session_id = str(uuid.uuid4())
        output_dir = SESSIONS_BASE / session_id
        output_dir.mkdir(parents=True, exist_ok=True)
        return cls(session_id=session_id, output_dir=output_dir)

    def get_audio_path(self, slot_id: int, agent_id: str, voice_profile: str) -> Path:
        """Get absolute path for WAV file: <session>/<slot>_<agent_id>_<voice_profile>.wav"""
        return self.output_dir / f"{slot_id}_{agent_id}_{voice_profile}.wav"

    def get_relative_audio_path(self, slot_id: int, agent_id: str, voice_profile: str) -> str:
        """Get path relative to artifacts/ for SSE event and URL retrieval."""
        return f"tts/sessions/{self.session_id}/{slot_id}_{agent_id}_{voice_profile}.wav"
