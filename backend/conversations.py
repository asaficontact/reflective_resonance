"""In-memory conversation store for per-slot history."""

from rawagents import Conversation

from backend.agents import get_persona
from backend.config import settings

# =============================================================================
# Conversation Store (in-memory, keyed by slotId)
# =============================================================================

_conversations: dict[int, Conversation] = {}
_conversation_agents: dict[int, str | None] = {}


def get_or_create_conversation(slot_id: int, agent_id: str | None = None) -> Conversation:
    """Get existing conversation for slot or create new one with system prompt.

    The system prompt is the shared installation prompt plus the persona of the
    agent assigned to the slot. If a different agent is now assigned to the
    slot, its conversation starts fresh with the new persona.

    Args:
        slot_id: The slot ID (1-6)
        agent_id: The agent assigned to the slot

    Returns:
        Conversation object for the slot
    """
    if slot_id in _conversations and _conversation_agents.get(slot_id) != agent_id:
        del _conversations[slot_id]

    if slot_id not in _conversations:
        conv = Conversation()
        system_prompt = settings.default_system_prompt
        persona = get_persona(agent_id) if agent_id else ""
        if persona:
            system_prompt += f"\n\n## Your Voice\n{persona}"
        conv.add_system(system_prompt)
        _conversations[slot_id] = conv
        _conversation_agents[slot_id] = agent_id

    return _conversations[slot_id]


def reset_conversation(slot_id: int) -> bool:
    """Reset conversation for a specific slot.

    Args:
        slot_id: The slot ID to reset

    Returns:
        True if conversation existed and was reset, False otherwise
    """
    if slot_id in _conversations:
        del _conversations[slot_id]
        return True
    return False


def reset_all_conversations() -> list[int]:
    """Clear all conversation history.

    Returns:
        List of slot IDs that were cleared
    """
    cleared = list(_conversations.keys())
    _conversations.clear()

    # Return all slots even if none were active
    return cleared if cleared else [1, 2, 3, 4, 5, 6]


def get_active_slots() -> list[int]:
    """Get list of slots with active conversations."""
    return list(_conversations.keys())
