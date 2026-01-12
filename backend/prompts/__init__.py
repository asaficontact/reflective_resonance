"""Prompt templates for the 3-turn workflow.

Uses rawagents PromptManager for Jinja2 template rendering.

Note: Voice profiles are defined in the system prompt (config.py),
not repeated in individual turn prompts.
"""

from pathlib import Path

from rawagents.prompts import PromptManager

# Initialize PromptManager with templates in this directory
_PROMPTS_DIR = Path(__file__).parent
_manager = PromptManager(_PROMPTS_DIR)


def render_turn1_prompt(user_message: str) -> str:
    """Render the Turn 1 (response) prompt.

    Args:
        user_message: The user's whispered message to reflect on.

    Returns:
        Rendered prompt string for Turn 1 LLM call.
    """
    return _manager.render(
        "turn1_response.j2",
        user_message=user_message,
    )


def render_turn2_prompt(
    slot_id: int,
    agent_id: str,
    peer_responses: list[dict],
) -> str:
    """Render the Turn 2 (comment selection) prompt.

    Args:
        slot_id: This slot's ID (1-6).
        agent_id: This slot's agent ID.
        peer_responses: List of peer responses with keys:
            - slotId: int
            - agentId: str
            - text: str

    Returns:
        Rendered prompt string for Turn 2 LLM call.
    """
    return _manager.render(
        "turn2_comment_select.j2",
        slot_id=slot_id,
        agent_id=agent_id,
        peer_responses=peer_responses,
    )


def render_turn3_prompt(
    slot_id: int,
    agent_id: str,
    original_response: str,
    received_comments: list[dict],
) -> str:
    """Render the Turn 3 (reply) prompt.

    Args:
        slot_id: This slot's ID (1-6).
        agent_id: This slot's agent ID.
        original_response: This slot's Turn 1 response text.
        received_comments: List of comments received with keys:
            - fromSlotId: int
            - fromAgentId: str
            - comment: str

    Returns:
        Rendered prompt string for Turn 3 LLM call.
    """
    return _manager.render(
        "turn3_reply.j2",
        slot_id=slot_id,
        agent_id=agent_id,
        original_response=original_response,
        received_comments=received_comments,
    )


def render_sentiment_prompt(user_message: str) -> str:
    """Render the sentiment analysis prompt.

    Args:
        user_message: The user's message to analyze.

    Returns:
        Rendered prompt string for sentiment analysis LLM call.
    """
    return _manager.render(
        "sentiment_analysis.j2",
        user_message=user_message,
    )
