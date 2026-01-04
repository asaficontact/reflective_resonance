"""SSE streaming with asyncio.Queue for multiplexing concurrent LLM streams."""

import asyncio
import logging
from collections.abc import AsyncGenerator

from sse_starlette.sse import ServerSentEvent

from backend.agents import get_llm, get_model_for_agent
from backend.config import settings
from backend.conversations import get_or_create_conversation
from backend.models import (
    DoneEvent,
    ErrorDetail,
    SlotDoneEvent,
    SlotErrorEvent,
    SlotRequest,
    SlotStartEvent,
    SlotTokenEvent,
)

logger = logging.getLogger(__name__)

# =============================================================================
# Error Mapping
# =============================================================================


def map_exception_to_error_type(e: Exception) -> str:
    """Map exceptions to frontend ErrorType values."""
    error_name = type(e).__name__.lower()

    # Timeout errors
    if "timeout" in error_name or isinstance(e, asyncio.TimeoutError):
        return "timeout"

    # Rate limit errors
    if "ratelimit" in error_name or "rate_limit" in error_name:
        return "rate_limit"

    # Network/connection errors
    if any(
        term in error_name
        for term in ["connection", "network", "dns", "socket", "refused"]
    ):
        return "network"

    if isinstance(e, (ConnectionError, OSError)):
        return "network"

    # Default to server error
    return "server_error"


# =============================================================================
# Per-Slot Streaming
# =============================================================================


async def stream_slot(
    slot_id: int,
    agent_id: str,
    message: str,
    queue: asyncio.Queue[ServerSentEvent | None],
) -> None:
    """Stream one slot's LLM response, pushing SSE events to shared queue.

    Args:
        slot_id: The slot ID (1-6)
        agent_id: The agent ID for this slot
        message: User message to send
        queue: Shared queue for multiplexed SSE events
    """
    conv = get_or_create_conversation(slot_id)
    llm = get_llm(agent_id)
    model = get_model_for_agent(agent_id)

    try:
        # Emit slot.start
        await queue.put(
            ServerSentEvent(
                event="slot.start",
                data=SlotStartEvent(slotId=slot_id, agentId=agent_id).model_dump_json(),
            )
        )

        # Add user message to conversation history
        conv.add_user(message)

        # Stream tokens from LLM
        full_content = ""
        async for chunk in llm.stream(
            messages=conv.get_history(),
            model=model,
            temperature=settings.temperature,
            max_tokens=settings.max_tokens,
        ):
            full_content += chunk
            await queue.put(
                ServerSentEvent(
                    event="slot.token",
                    data=SlotTokenEvent(slotId=slot_id, content=chunk).model_dump_json(),
                )
            )

        # Add assistant response to conversation history
        conv.add_assistant(full_content)

        # Emit slot.done
        await queue.put(
            ServerSentEvent(
                event="slot.done",
                data=SlotDoneEvent(
                    slotId=slot_id, agentId=agent_id, fullContent=full_content
                ).model_dump_json(),
            )
        )

        logger.info(f"Slot {slot_id} ({agent_id}) completed: {len(full_content)} chars")

    except Exception as e:
        error_type = map_exception_to_error_type(e)
        logger.error(f"Slot {slot_id} ({agent_id}) error: {error_type} - {e}")

        await queue.put(
            ServerSentEvent(
                event="slot.error",
                data=SlotErrorEvent(
                    slotId=slot_id,
                    agentId=agent_id,
                    error=ErrorDetail(type=error_type, message=str(e)),
                ).model_dump_json(),
            )
        )


# =============================================================================
# Broadcast Chat (Multiplexed SSE)
# =============================================================================


async def broadcast_chat(
    message: str,
    slots: list[SlotRequest],
) -> AsyncGenerator[ServerSentEvent, None]:
    """Broadcast message to all slots, yielding multiplexed SSE events.

    All slots stream concurrently. Events from different slots are interleaved
    as they arrive via a shared asyncio.Queue.

    Args:
        message: User message to broadcast
        slots: List of slot requests with slot ID and agent ID

    Yields:
        SSE events for slot.start, slot.token, slot.done, slot.error, and done
    """
    queue: asyncio.Queue[ServerSentEvent | None] = asyncio.Queue()

    # Launch all slot streams concurrently
    tasks = [
        asyncio.create_task(stream_slot(s.slotId, s.agentId, message, queue))
        for s in slots
    ]

    # Track completions
    completed = 0

    async def monitor_completion() -> None:
        """Wait for all tasks and signal queue end."""
        await asyncio.gather(*tasks, return_exceptions=True)
        await queue.put(None)  # Sentinel to end iteration

    # Start monitoring in background
    asyncio.create_task(monitor_completion())

    # Yield events as they arrive
    while True:
        event = await queue.get()

        if event is None:
            break

        yield event

        # Track slot completions for final event
        if event.event in ("slot.done", "slot.error"):
            completed += 1

    # Emit final done event
    yield ServerSentEvent(
        event="done",
        data=DoneEvent(completedSlots=completed).model_dump_json(),
    )

    logger.info(f"Broadcast complete: {completed}/{len(slots)} slots finished")
