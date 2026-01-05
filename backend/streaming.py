"""SSE streaming for the 3-turn workflow.

Phase 3: 3-Turn Inter-Agent Workflow
- Turn 1: All agents respond to user message
- Turn 2: Each agent comments on one peer response
- Turn 3: Agents with comments reply

Delegates to workflow.py for orchestration.
"""

import logging
from collections.abc import AsyncGenerator

from sse_starlette.sse import ServerSentEvent

from backend.models import SlotRequest
from backend.workflow import run_three_turn_workflow

logger = logging.getLogger(__name__)


async def broadcast_chat(
    message: str,
    slots: list[SlotRequest],
) -> AsyncGenerator[ServerSentEvent, None]:
    """Broadcast message to all slots using 3-turn workflow.

    Event flow:
    - turn.start: Turn begins
    - slot.start: Slot begins processing
    - slot.done: LLM response complete (text, voiceProfile, turnIndex, kind)
    - slot.audio: TTS audio file ready
    - slot.error: Error occurred (LLM or TTS)
    - turn.done: Turn complete
    - done: All turns finished

    Args:
        message: User message to broadcast
        slots: List of slot requests with slot ID and agent ID

    Yields:
        SSE events for the complete 3-turn workflow
    """
    async for event in run_three_turn_workflow(message, slots):
        yield event
