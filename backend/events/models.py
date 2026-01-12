"""Pydantic models for TouchDesigner WebSocket events."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SlotWaveInfo(BaseModel):
    """Wave file info for a single agent slot."""

    slotId: int = Field(description="Agent's slot ID (1-6)")
    agentId: str = Field(description="Agent ID that produced this response")
    voiceProfile: str = Field(description="Voice profile used for TTS")
    wave1PathAbs: str = Field(description="Absolute path to wave1 file")
    wave1PathRel: str = Field(description="Relative path to wave1 under artifacts/")
    wave1TargetSlotId: int = Field(description="Physical slot ID for wave1 playback")
    wave2PathAbs: str = Field(description="Absolute path to wave2 file")
    wave2PathRel: str = Field(description="Relative path to wave2 under artifacts/")
    wave2TargetSlotId: int = Field(description="Physical slot ID for wave2 playback")


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


class UserSentimentPayload(BaseModel):
    """Payload for user_sentiment event."""

    sentiment: Literal["positive", "neutral", "negative"] = Field(
        description="Detected emotional tone of user input"
    )
    justification: str = Field(
        description="Brief explanation of sentiment determination"
    )


class SummarySlotWave(BaseModel):
    """Wave file info for a single slot in summary."""

    slotId: int = Field(ge=1, le=6, description="Target slot ID (1-6)")
    wavePathAbs: str = Field(description="Absolute path to wave file")
    wavePathRel: str = Field(description="Relative path under artifacts/")


class SummaryWaveInfo(BaseModel):
    """Wave file info for summary (6 waves mapped to 6 slots)."""

    voiceProfile: str = Field(description="Voice profile used for TTS")
    waves: list[SummarySlotWave] = Field(
        min_length=6,
        max_length=6,
        description="6 wave files, one per slot"
    )


class FinalSummaryWavesPayload(BaseModel):
    """Payload for final_summary.ready event."""

    status: Literal["complete", "failed"] = Field(
        description="complete if summary ready, failed if generation failed"
    )
    text: str = Field(description="The summary text")
    waveInfo: SummaryWaveInfo | None = Field(
        default=None, description="Wave file paths (None if failed)"
    )
