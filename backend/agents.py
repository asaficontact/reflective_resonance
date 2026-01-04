"""Agent registry with LLM client management."""

from rawagents import AsyncLLM, LLMConfig

from backend.config import settings
from backend.models import Agent, AgentId

# =============================================================================
# AgentId → LiteLLM Model String Mapping
# =============================================================================

AGENT_MODEL_MAP: dict[str, str] = {
    "claude-sonnet-4-5": "anthropic/claude-sonnet-4-20250514",
    "claude-opus-4-5": "anthropic/claude-opus-4-20250514",
    "gpt-5.2": "openai/gpt-4.1",
    "gpt-5.1": "openai/gpt-4o",
    "gpt-4o": "openai/gpt-4o",
    "gemini-3": "gemini/gemini-2.0-flash",
}

# =============================================================================
# Agent Display Information (for GET /v1/agents)
# =============================================================================

AGENTS: list[Agent] = [
    Agent(
        id="claude-sonnet-4-5",
        name="Claude Sonnet 4.5",
        provider="anthropic",
        description="Anthropic's fast, capable model",
        color="#7c3aed",
    ),
    Agent(
        id="claude-opus-4-5",
        name="Claude Opus 4.5",
        provider="anthropic",
        description="Anthropic's most capable model",
        color="#a855f7",
    ),
    Agent(
        id="gpt-5.2",
        name="GPT 5.2",
        provider="openai",
        description="Latest GPT-4 series model",
        color="#10b981",
    ),
    Agent(
        id="gpt-5.1",
        name="GPT 5.1",
        provider="openai",
        description="Advanced GPT-4o model",
        color="#06b6d4",
    ),
    Agent(
        id="gpt-4o",
        name="GPT 4o",
        provider="openai",
        description="OpenAI's multimodal flagship",
        color="#0ea5e9",
    ),
    Agent(
        id="gemini-3",
        name="Gemini 3",
        provider="google",
        description="Google's fast Gemini model",
        color="#f59e0b",
    ),
]

# =============================================================================
# LLM Client Registry (lazy-initialized)
# =============================================================================

_llm_clients: dict[str, AsyncLLM] = {}


def get_llm(agent_id: AgentId) -> AsyncLLM:
    """Get or create AsyncLLM client for an agent.

    Clients are cached by model string to reuse connections.
    """
    model = AGENT_MODEL_MAP[agent_id]

    if model not in _llm_clients:
        _llm_clients[model] = AsyncLLM(
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
