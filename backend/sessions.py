"""Session management for TTS audio storage.

Each chat request creates a new session with a UUID. Audio files
are stored in the session directory with turn-based subdirectories:
    artifacts/tts/sessions/<session_id>/
        turn_1/
            slot-<N>_<agentId>_<voiceProfile>.wav
        turn_2/
            slot-<N>_comment_to_slot-<target>_<agentId>_<voiceProfile>.wav
        turn_3/
            slot-<N>_reply_<agentId>_<voiceProfile>.wav
        session.json  # Manifest for TouchDesigner
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

SESSIONS_BASE = Path("artifacts/tts/sessions")

TurnIndex = Literal[1, 2, 3]


@dataclass
class TTSSession:
    """Manages a TTS session and its audio files with 3-turn support."""

    session_id: str
    output_dir: Path
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    _manifest: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def create(cls) -> "TTSSession":
        """Create a new session with UUID and turn subdirectories."""
        session_id = str(uuid.uuid4())
        output_dir = SESSIONS_BASE / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create turn subdirectories
        for turn in [1, 2, 3]:
            (output_dir / f"turn_{turn}").mkdir(exist_ok=True)

        session = cls(session_id=session_id, output_dir=output_dir)

        # Initialize manifest structure
        session._manifest = {
            "sessionId": session_id,
            "createdAt": session.created_at,
            "turns": {
                "turn_1": [],
                "turn_2": [],
                "turn_3": [],
            },
        }

        return session

    def get_turn_dir(self, turn_index: TurnIndex) -> Path:
        """Get the directory for a specific turn."""
        return self.output_dir / f"turn_{turn_index}"

    # =========================================================================
    # Turn 1: Response audio paths
    # =========================================================================

    def get_turn1_audio_path(
        self, slot_id: int, agent_id: str, voice_profile: str
    ) -> Path:
        """Get absolute path for Turn 1 WAV file.

        Format: turn_1/slot-<N>_<agentId>_<voiceProfile>.wav
        """
        filename = f"slot-{slot_id}_{agent_id}_{voice_profile}.wav"
        return self.get_turn_dir(1) / filename

    def get_turn1_relative_path(
        self, slot_id: int, agent_id: str, voice_profile: str
    ) -> str:
        """Get relative path for Turn 1 audio (for SSE events)."""
        filename = f"slot-{slot_id}_{agent_id}_{voice_profile}.wav"
        return f"tts/sessions/{self.session_id}/turn_1/{filename}"

    # =========================================================================
    # Turn 2: Comment audio paths
    # =========================================================================

    def get_turn2_audio_path(
        self,
        slot_id: int,
        target_slot_id: int,
        agent_id: str,
        voice_profile: str,
    ) -> Path:
        """Get absolute path for Turn 2 WAV file.

        Format: turn_2/slot-<N>_comment_to_slot-<target>_<agentId>_<voiceProfile>.wav
        """
        filename = f"slot-{slot_id}_comment_to_slot-{target_slot_id}_{agent_id}_{voice_profile}.wav"
        return self.get_turn_dir(2) / filename

    def get_turn2_relative_path(
        self,
        slot_id: int,
        target_slot_id: int,
        agent_id: str,
        voice_profile: str,
    ) -> str:
        """Get relative path for Turn 2 audio (for SSE events)."""
        filename = f"slot-{slot_id}_comment_to_slot-{target_slot_id}_{agent_id}_{voice_profile}.wav"
        return f"tts/sessions/{self.session_id}/turn_2/{filename}"

    # =========================================================================
    # Turn 3: Reply audio paths
    # =========================================================================

    def get_turn3_audio_path(
        self, slot_id: int, agent_id: str, voice_profile: str
    ) -> Path:
        """Get absolute path for Turn 3 WAV file.

        Format: turn_3/slot-<N>_reply_<agentId>_<voiceProfile>.wav
        """
        filename = f"slot-{slot_id}_reply_{agent_id}_{voice_profile}.wav"
        return self.get_turn_dir(3) / filename

    def get_turn3_relative_path(
        self, slot_id: int, agent_id: str, voice_profile: str
    ) -> str:
        """Get relative path for Turn 3 audio (for SSE events)."""
        filename = f"slot-{slot_id}_reply_{agent_id}_{voice_profile}.wav"
        return f"tts/sessions/{self.session_id}/turn_3/{filename}"

    # =========================================================================
    # Summary (Turn 4): Summary audio paths
    # =========================================================================

    def get_summary_audio_path(self, voice_profile: str) -> Path:
        """Get absolute path for summary WAV file.

        Format: summary/summary_<voiceProfile>.wav
        """
        summary_dir = self.output_dir / "summary"
        summary_dir.mkdir(exist_ok=True)
        filename = f"summary_{voice_profile}.wav"
        return summary_dir / filename

    def get_summary_relative_path(self, voice_profile: str) -> str:
        """Get relative path for summary audio (for events)."""
        filename = f"summary_{voice_profile}.wav"
        return f"tts/sessions/{self.session_id}/summary/{filename}"

    # =========================================================================
    # Manifest management
    # =========================================================================

    def add_turn1_entry(
        self,
        slot_id: int,
        agent_id: str,
        voice_profile: str,
        text: str,
        audio_path: str,
    ) -> None:
        """Add a Turn 1 entry to the manifest."""
        self._manifest["turns"]["turn_1"].append({
            "slotId": slot_id,
            "agentId": agent_id,
            "voiceProfile": voice_profile,
            "text": text,
            "audioPath": audio_path,
            "kind": "response",
        })

    def add_turn2_entry(
        self,
        slot_id: int,
        agent_id: str,
        target_slot_id: int,
        voice_profile: str,
        comment: str,
        audio_path: str,
    ) -> None:
        """Add a Turn 2 entry to the manifest."""
        self._manifest["turns"]["turn_2"].append({
            "slotId": slot_id,
            "agentId": agent_id,
            "targetSlotId": target_slot_id,
            "voiceProfile": voice_profile,
            "comment": comment,
            "audioPath": audio_path,
            "kind": "comment",
        })

    def add_turn3_entry(
        self,
        slot_id: int,
        agent_id: str,
        voice_profile: str,
        text: str,
        audio_path: str,
        received_comments: list[dict[str, Any]],
    ) -> None:
        """Add a Turn 3 entry to the manifest."""
        self._manifest["turns"]["turn_3"].append({
            "slotId": slot_id,
            "agentId": agent_id,
            "voiceProfile": voice_profile,
            "text": text,
            "audioPath": audio_path,
            "kind": "reply",
            "receivedComments": received_comments,
        })

    def add_summary_entry(
        self,
        voice_profile: str,
        text: str,
        audio_path: str,
    ) -> None:
        """Add summary (Turn 4) entry to the manifest."""
        self._manifest["summary"] = {
            "voiceProfile": voice_profile,
            "text": text,
            "audioPath": audio_path,
            "kind": "summary",
        }

    def write_manifest(self) -> Path:
        """Write session.json manifest to disk."""
        manifest_path = self.output_dir / "session.json"
        with open(manifest_path, "w") as f:
            json.dump(self._manifest, f, indent=2)
        return manifest_path

    # =========================================================================
    # Legacy methods (kept for backwards compatibility during migration)
    # =========================================================================

    def get_audio_path(self, slot_id: int, agent_id: str, voice_profile: str) -> Path:
        """Legacy method - redirects to Turn 1 path."""
        return self.get_turn1_audio_path(slot_id, agent_id, voice_profile)

    def get_relative_audio_path(self, slot_id: int, agent_id: str, voice_profile: str) -> str:
        """Legacy method - redirects to Turn 1 relative path."""
        return self.get_turn1_relative_path(slot_id, agent_id, voice_profile)
