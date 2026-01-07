"""Pydantic models for TouchDesigner WebSocket events."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SlotWaveInfo(BaseModel):
    """Wave-mix file info for a single slot."""

    slotId: int = Field(description="Slot ID (1-6)")
    agentId: str = Field(description="Agent ID that produced this response")
    voiceProfile: str = Field(description="Voice profile used for TTS")
    waveMixPathAbs: str = Field(description="Absolute filesystem path to wave-mix file")
    waveMixPathRel: str = Field(description="Relative path under artifacts/")


class Turn1WavesPayload(BaseModel):
    """Payload for turn1.waves.ready event."""

    turnIndex: Literal[1] = 1
    status: Literal["complete", "partial"] = Field(
        description="complete if all slots ready, partial if some missing"
    )
    slotsExpected: int = Field(description="Number of slots expected")
    slotsReady: int = Field(description="Number of slots with wave-mix files ready")
    slots: list[SlotWaveInfo] = Field(description="Ready slot wave info")
    missingSlotIds: list[int] = Field(
        default_factory=list, description="Slot IDs that failed or timed out"
    )


class PlayOrderItem(BaseModel):
    """Single item in dialogue playback order."""

    role: Literal["commenter", "respondent"]
    slotId: int


class DialogueWavesPayload(BaseModel):
    """Payload for dialogue.waves.ready event."""

    dialogueId: str = Field(description="Unique dialogue identifier (e.g., turn23-slot2)")
    turns: list[int] = Field(default=[2, 3], description="Turn indices involved")
    targetSlotId: int = Field(description="Slot ID being commented on / responding")
    commenters: list[SlotWaveInfo] = Field(description="Turn 2 commenters' wave info")
    respondent: SlotWaveInfo = Field(description="Turn 3 respondent's wave info")
    playOrder: list[PlayOrderItem] = Field(
        description="Ordered list for sequential playback"
    )


class EventEnvelope(BaseModel):
    """Common envelope for all WebSocket events."""

    type: str = Field(description="Event type discriminator")
    sessionId: str = Field(description="Workflow session UUID")
    seq: int = Field(description="Monotonically increasing sequence per session")
    ts: str = Field(description="UTC timestamp in RFC3339 format")
    payload: dict = Field(description="Event-specific payload")

    @classmethod
    def create(
        cls,
        event_type: str,
        session_id: str,
        seq: int,
        payload: BaseModel,
    ) -> "EventEnvelope":
        """Create an envelope with the current timestamp."""
        return cls(
            type=event_type,
            sessionId=session_id,
            seq=seq,
            ts=datetime.utcnow().isoformat() + "Z",
            payload=payload.model_dump(),
        )


class HelloMessage(BaseModel):
    """Optional hello message from TouchDesigner client."""

    type: Literal["hello"] = "hello"
    client: str = Field(default="touchdesigner")
    version: str = Field(default="")


class HelloAckMessage(BaseModel):
    """Hello acknowledgment from server."""

    type: Literal["hello.ack"] = "hello.ack"
    server: str = Field(default="reflective-resonance")
    version: str = Field(default="0.1.0")
