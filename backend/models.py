"""Pydantic models for API request/response validation."""

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
    """Structured output from LLM for TTS generation.

    The LLM returns this JSON structure, which determines both
    the text to speak and which voice profile to use.
    """

    text: str = Field(min_length=1, description="The spoken response text")
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
# SSE Event Data Models
# =============================================================================


class SlotStartEvent(BaseModel):
    """Emitted when a slot starts streaming."""

    slotId: int
    agentId: str


class SlotTokenEvent(BaseModel):
    """Emitted for each token/chunk during streaming."""

    slotId: int
    content: str


class SlotDoneEvent(BaseModel):
    """Emitted when a slot completes successfully."""

    slotId: int
    agentId: str
    text: str
    voiceProfile: str


class SlotAudioEvent(BaseModel):
    """Emitted when TTS audio is ready for a slot."""

    slotId: int
    agentId: str
    voiceProfile: str
    audioFormat: Literal["wav"] = "wav"
    audioPath: str  # Relative path: "tts/sessions/<session_id>/<agent>_<voice>.wav"


class ErrorDetail(BaseModel):
    """Error information for slot errors."""

    type: ErrorType
    message: str


class SlotErrorEvent(BaseModel):
    """Emitted when a slot encounters an error."""

    slotId: int
    agentId: str
    error: ErrorDetail


class DoneEvent(BaseModel):
    """Emitted when all slots have completed or errored."""

    completedSlots: int
