"""Session management for STT audio storage.

Each STT request creates a new session with a UUID. Files
are stored in the session directory:
    artifacts/stt/sessions/<stt_session_id>/
        input.<ext>        # Original uploaded audio
        transcript.json    # Full Scribe response
        transcript.txt     # Plain text transcript
        metadata.json      # Timing, mime type, etc.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

STT_SESSIONS_BASE = Path("artifacts/stt/sessions")


@dataclass
class STTSession:
    """Manages an STT session and its artifacts."""

    session_id: str
    output_dir: Path
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def create(cls) -> "STTSession":
        """Create a new session with UUID."""
        session_id = str(uuid.uuid4())
        output_dir = STT_SESSIONS_BASE / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        return cls(session_id=session_id, output_dir=output_dir)

    def get_input_path(self, ext: str) -> Path:
        """Get absolute path for input audio file."""
        return self.output_dir / f"input.{ext}"

    def get_input_relative_path(self, ext: str) -> str:
        """Get relative path for input audio (for API response)."""
        return f"stt/sessions/{self.session_id}/input.{ext}"

    def get_transcript_json_path(self) -> Path:
        """Get absolute path for transcript.json."""
        return self.output_dir / "transcript.json"

    def get_transcript_txt_path(self) -> Path:
        """Get absolute path for transcript.txt."""
        return self.output_dir / "transcript.txt"

    def get_transcript_relative_path(self) -> str:
        """Get relative path for transcript.txt (for API response)."""
        return f"stt/sessions/{self.session_id}/transcript.txt"

    def get_metadata_path(self) -> Path:
        """Get absolute path for metadata.json."""
        return self.output_dir / "metadata.json"

    def write_metadata(
        self,
        mime_type: str,
        duration_ms: int,
        size_bytes: int,
        user_agent: Optional[str] = None,
    ) -> None:
        """Write metadata.json to disk."""
        metadata: dict[str, Any] = {
            "sessionId": self.session_id,
            "createdAt": self.created_at,
            "mimeType": mime_type,
            "durationMs": duration_ms,
            "sizeBytes": size_bytes,
        }
        if user_agent:
            metadata["userAgent"] = user_agent

        with open(self.get_metadata_path(), "w") as f:
            json.dump(metadata, f, indent=2)

    def write_transcript(self, scribe_response: dict[str, Any], plain_text: str) -> None:
        """Write transcript files to disk.

        Args:
            scribe_response: Full response from ElevenLabs Scribe API
            plain_text: Plain text transcript string
        """
        # Write full JSON response
        with open(self.get_transcript_json_path(), "w") as f:
            json.dump(scribe_response, f, indent=2)

        # Write plain text
        with open(self.get_transcript_txt_path(), "w") as f:
            f.write(plain_text)

    def save_input_audio(self, audio_bytes: bytes, ext: str) -> Path:
        """Save uploaded audio to input file.

        Args:
            audio_bytes: Raw audio bytes
            ext: File extension (webm, ogg, wav, etc.)

        Returns:
            Path to saved file
        """
        input_path = self.get_input_path(ext)
        with open(input_path, "wb") as f:
            f.write(audio_bytes)
        return input_path
