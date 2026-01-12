"""Pydantic models for API request/response validation."""

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from backend.tts.profiles import VoiceProfileName


# Type aliases matching frontend
AgentId = Literal[
    "claude-sonnet-4-5",
    "claude-opus-4-5",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-4o",
    "gemini-3",
]
SlotId = Literal[1, 2, 3, 4, 5, 6]
ErrorType = Literal["network", "timeout", "rate_limit", "server_error", "tts_error", "unknown"]

# 4-turn workflow types (Turn 4 is summary)
TurnIndex = Literal[1, 2, 3, 4]
MessageKind = Literal["response", "comment", "reply", "summary"]


# =============================================================================
# Request Models
# =============================================================================


class SlotRequest(BaseModel):
    """A slot assignment in a chat request."""

    slotId: SlotId
    agentId: AgentId


class ChatRequest(BaseModel):
    """Request to broadcast a message to multiple slots."""

    message: str = Field(min_length=1, description="User message to send")
    slots: list[SlotRequest] = Field(
        min_length=1, max_length=6, description="Slots to broadcast to"
    )


# =============================================================================
# Structured LLM Output Models
# =============================================================================


class SpokenResponse(BaseModel):
    """Structured output from LLM for Turn 1 and Turn 3.

    The LLM returns this JSON structure, which determines both
    the text to speak and which voice profile to use.
    """

    text: str = Field(
        min_length=1,
        max_length=200,
        description="The spoken response text (1-2 sentences)",
    )
    voice_profile: VoiceProfileName = Field(description="Voice profile for TTS synthesis")


class CommentSelection(BaseModel):
    """Structured output from LLM for Turn 2 comment selection.

    The agent selects exactly one peer response to comment on.
    """

    targetSlotId: int = Field(ge=1, le=6, description="Slot to comment on (1-6, must differ from self)")
    comment: str = Field(min_length=1, max_length=150, description="Single sentence comment")
    voice_profile: VoiceProfileName = Field(description="Voice profile for TTS synthesis")


# =============================================================================
# Response Models
# =============================================================================


class Agent(BaseModel):
    """Agent descriptor for GET /v1/agents."""

    id: AgentId
    name: str
    provider: str
    description: str
    color: str


class AgentsResponse(BaseModel):
    """Response for GET /v1/agents."""

    agents: list[Agent]


class HealthResponse(BaseModel):
    """Response for GET /v1/health."""

    status: str


class ResetResponse(BaseModel):
    """Response for POST /v1/reset."""

    status: str
    clearedSlots: list[int]


# =============================================================================
# SSE Event Data Models (3-Turn Workflow)
# =============================================================================


class TurnStartEvent(BaseModel):
    """Emitted when a turn begins processing."""

    sessionId: str
    turnIndex: TurnIndex


class TurnDoneEvent(BaseModel):
    """Emitted when all slots in a turn complete."""

    sessionId: str
    turnIndex: TurnIndex
    slotCount: int


class SlotStartEvent(BaseModel):
    """Emitted when a slot starts processing."""

    sessionId: str
    turnIndex: TurnIndex
    kind: MessageKind
    slotId: int
    agentId: str


class SlotTokenEvent(BaseModel):
    """Emitted for each token/chunk during streaming (legacy, not used in 3-turn)."""

    slotId: int
    content: str


class SlotDoneEvent(BaseModel):
    """Emitted when a slot completes successfully."""

    sessionId: str
    turnIndex: TurnIndex
    kind: MessageKind
    slotId: int
    agentId: str
    text: str
    voiceProfile: str
    targetSlotId: int | None = None  # Only for Turn 2 (comment)


class SlotAudioEvent(BaseModel):
    """Emitted when TTS audio is ready for a slot."""

    sessionId: str
    turnIndex: TurnIndex
    kind: MessageKind
    slotId: int
    agentId: str
    voiceProfile: str
    audioFormat: Literal["wav"] = "wav"
    audioPath: str  # Relative path: "tts/sessions/<session_id>/turn_<N>/..."


class ErrorDetail(BaseModel):
    """Error information for slot errors."""

    type: ErrorType
    message: str


class SlotErrorEvent(BaseModel):
    """Emitted when a slot encounters an error."""

    sessionId: str
    turnIndex: TurnIndex
    kind: MessageKind
    slotId: int
    agentId: str
    error: ErrorDetail


class DoneEvent(BaseModel):
    """Emitted when the complete 3-turn workflow finishes."""

    sessionId: str
    completedSlots: int
    turns: int = 3


# =============================================================================
# Internal Workflow Data Structures
# =============================================================================


@dataclass
class Turn1Result:
    """Result of Turn 1 for a single slot."""

    slot_id: int
    agent_id: str
    text: str
    voice_profile: str
    success: bool
    audio_path: str | None = None


@dataclass
class Turn2Result:
    """Result of Turn 2 for a single slot."""

    slot_id: int
    agent_id: str
    target_slot_id: int
    comment: str
    voice_profile: str
    success: bool
    audio_path: str | None = None


@dataclass
class Turn3Result:
    """Result of Turn 3 for a single slot."""

    slot_id: int
    agent_id: str
    text: str
    voice_profile: str
    success: bool
    audio_path: str | None = None


@dataclass
class ReceivedComment:
    """A comment received by a slot for Turn 3 input."""

    from_slot_id: int
    from_agent_id: str
    comment: str


@dataclass
class SummaryResult:
    """Result of Turn 4 summary generation."""

    text: str
    voice_profile: str
    success: bool
    audio_path: str | None = None


@dataclass
class WorkflowState:
    """Tracks state across all turns (1-4)."""

    session: "TTSSession"  # Forward reference, actual type from sessions.py
    slots: list[SlotRequest]
    user_message: str = ""
    turn1_results: dict[int, Turn1Result] = field(default_factory=dict)
    turn2_results: dict[int, Turn2Result] = field(default_factory=dict)
    turn3_results: dict[int, Turn3Result] = field(default_factory=dict)
    comments_by_target: dict[int, list[ReceivedComment]] = field(default_factory=dict)
    summary_result: SummaryResult | None = None


# Type hint for forward reference
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from backend.sessions import TTSSession
