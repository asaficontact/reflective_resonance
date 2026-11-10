"""Agent registry with LLM client management.

All six agents run on Claude. They differ by persona (a short system-prompt
addition), not by provider, so the six voices stay distinct.
"""

from typing import Any, TypeVar

import instructor
from litellm import acompletion
from pydantic import BaseModel
from rawagents import AsyncLLM, LLMConfig

from backend.config import settings
from backend.models import Agent, AgentId

T = TypeVar("T", bound=BaseModel)

# =============================================================================
# Model selection
# =============================================================================

# One place to change the model every agent uses.
CLAUDE_MODEL = "anthropic/claude-opus-5-5"

AGENT_MODEL_MAP: dict[str, str] = {
    "claude-sage": CLAUDE_MODEL,
    "claude-poet": CLAUDE_MODEL,
    "claude-wonder": CLAUDE_MODEL,
    "claude-scientist": CLAUDE_MODEL,
    "claude-questioner": CLAUDE_MODEL,
    "claude-trickster": CLAUDE_MODEL,
}

# Agent used for the Turn 4 summary events (the summary model itself comes
# from settings.summary_model).
SUMMARY_AGENT_ID: AgentId = "claude-sage"

# =============================================================================
# Personas (appended to the shared system prompt for each slot)
# =============================================================================

AGENT_PERSONAS: dict[str, str] = {
    "claude-sage": (
        "You are the Sage, an old well that has heard centuries of whispers. "
        "Your angle is the long view: what will still matter in years, and what "
        "they value underneath the problem. Plain, slow, like a proverb."
    ),
    "claude-poet": (
        "You are the Poet. Your angle is the feeling inside their words: you name "
        "it more precisely than they could, with one fresh, musical image. "
        "Avoid cliches."
    ),
    "claude-wonder": (
        "You are Wonder, a childlike voice. Your angle is the hopeful or delightful "
        "possibility hidden in their situation. Small, simple words; curious and "
        "gentle, never naive about pain."
    ),
    "claude-scientist": (
        "You are the Scientist. Your angle is one grounded insight about how minds, "
        "feelings, or decisions actually work, sometimes told through the physics "
        "of water and sound. Precise and warm, never lecturing."
    ),
    "claude-questioner": (
        "You are the Questioner. Your angle is one gentle, open question about "
        "their situation that helps them see it more clearly. "
        "Curious, tender, never probing or clinical."
    ),
    "claude-trickster": (
        "You are the Trickster. Your angle is the unexpected one: flip their "
        "situation around or find its funny side so it feels lighter. "
        "Never mock the whisperer; your play is a form of care."
    ),
}


def get_persona(agent_id: str) -> str:
    """Return the persona text for an agent ('' if unknown)."""
    return AGENT_PERSONAS.get(agent_id, "")


# =============================================================================
# Agent Display Information (for GET /v1/agents)
# =============================================================================

AGENTS: list[Agent] = [
    Agent(
        id="claude-sage",
        name="Sage",
        provider="anthropic",
        description="Claude: slow, deep, proverb-like",
        color="#7c3aed",
    ),
    Agent(
        id="claude-poet",
        name="Poet",
        provider="anthropic",
        description="Claude: vivid, musical imagery",
        color="#a855f7",
    ),
    Agent(
        id="claude-wonder",
        name="Wonder",
        provider="anthropic",
        description="Claude: childlike, curious, gentle",
        color="#10b981",
    ),
    Agent(
        id="claude-scientist",
        name="Scientist",
        provider="anthropic",
        description="Claude: the physics of water and sound",
        color="#06b6d4",
    ),
    Agent(
        id="claude-questioner",
        name="Questioner",
        provider="anthropic",
        description="Claude: answers with an open question",
        color="#0ea5e9",
    ),
    Agent(
        id="claude-trickster",
        name="Trickster",
        provider="anthropic",
        description="Claude: playful, warm humor",
        color="#f59e0b",
    ),
]

# =============================================================================
# Claude-compatible LLM client
# =============================================================================


class ClaudeLLM(AsyncLLM):
    """AsyncLLM adapted to current Claude models.

    Current Claude models reject two things rawagents sends by default:
    - forced tool_choice, which instructor's default TOOLS mode relies on
      (so structured output uses instructor's JSON mode instead);
    - the `temperature` sampling parameter (so it is ignored here).
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._instructor = instructor.from_litellm(acompletion, mode=instructor.Mode.JSON)

    async def complete_structured(  # type: ignore[override]
        self,
        messages: list[dict[str, Any]],
        response_model: type[T],
        model: str | None = None,
        *,
        temperature: float | None = None,  # accepted for call-site compatibility, not sent
        reasoning_effort: Any = None,
        include_metadata: bool = False,
    ) -> T:
        if include_metadata:
            raise NotImplementedError("ClaudeLLM does not support include_metadata")
        return await self._instructor.chat.completions.create(
            model=model or self.config.model,
            messages=messages,
            response_model=response_model,
            max_retries=self.config.structured_validation_retries,
            timeout=self.config.timeout,
        )


# =============================================================================
# LLM Client Registry (lazy-initialized)
# =============================================================================

_llm_clients: dict[str, AsyncLLM] = {}


def get_llm(agent_id: AgentId) -> AsyncLLM:
    """Get or create the LLM client for an agent.

    Clients are cached by model string to reuse connections.
    """
    model = AGENT_MODEL_MAP[agent_id]

    if model not in _llm_clients:
        _llm_clients[model] = ClaudeLLM(
            config=LLMConfig(
                model=model,
                retries=settings.retries,
                timeout=settings.timeout_s,
            )
        )

    return _llm_clients[model]


def get_model_for_agent(agent_id: AgentId) -> str:
    """Get the LiteLLM model string for an agent ID."""
    return AGENT_MODEL_MAP[agent_id]
