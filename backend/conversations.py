"""In-memory conversation store for per-slot history."""

from rawagents import Conversation

from backend.config import settings

# =============================================================================
# Conversation Store (in-memory, keyed by slotId)
# =============================================================================

_conversations: dict[int, Conversation] = {}


def get_or_create_conversation(slot_id: int) -> Conversation:
    """Get existing conversation for slot or create new one with system prompt.

    Args:
        slot_id: The slot ID (1-6)

    Returns:
        Conversation object for the slot
    """
    if slot_id not in _conversations:
        conv = Conversation()
        conv.add_system(settings.default_system_prompt)
        _conversations[slot_id] = conv

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
