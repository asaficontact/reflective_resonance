"""Prompt templates for the 3-turn workflow.

Uses rawagents PromptManager for Jinja2 template rendering.
"""

from pathlib import Path

from rawagents.prompts import PromptManager

# Initialize PromptManager with templates in this directory
_PROMPTS_DIR = Path(__file__).parent
_manager = PromptManager(_PROMPTS_DIR)


# Voice profile table for inclusion in prompts
VOICE_PROFILES_TABLE = """
| Profile | Character | Use For |
|---------|-----------|---------|
| friendly_casual | Young female, American, warm | Casual greetings, friendly chat |
| warm_professional | Male, American, helpful | Advice, thoughtful answers |
| energetic_upbeat | Young female, energetic | Excited responses, fun |
| calm_soothing | Female, calm, gentle | Reassurance, patience |
| confident_charming | Male, British, witty | Clever remarks, charm |
| playful_expressive | Female, dynamic range | Playful banter, emotions |
""".strip()


def render_turn1_prompt(user_message: str) -> str:
    """Render the Turn 1 (response) prompt.

    Args:
        user_message: The user's message to respond to.

    Returns:
        Rendered prompt string for Turn 1 LLM call.
    """
    return _manager.render(
        "turn1_response.j2",
        user_message=user_message,
        voice_profiles_table=VOICE_PROFILES_TABLE,
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
        voice_profiles_table=VOICE_PROFILES_TABLE,
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
        voice_profiles_table=VOICE_PROFILES_TABLE,
    )
