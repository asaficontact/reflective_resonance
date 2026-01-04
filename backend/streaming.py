"""SSE streaming with asyncio.Queue for multiplexing concurrent LLM responses.

Phase 2: Structured output + TTS integration.
- LLM returns SpokenResponse(text, voice_profile) via complete_structured()
- TTS generates WAV files in session directories
- No more token streaming (structured output doesn't support it)
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from sse_starlette.sse import ServerSentEvent

from backend.agents import get_llm, get_model_for_agent
from backend.config import settings
from backend.conversations import get_or_create_conversation
from backend.models import (
    DoneEvent,
    ErrorDetail,
    SlotAudioEvent,
    SlotDoneEvent,
    SlotErrorEvent,
    SlotRequest,
    SlotStartEvent,
    SpokenResponse,
)
from backend.sessions import TTSSession
from backend.tts import MultiVoiceAgentTTS

logger = logging.getLogger(__name__)

# =============================================================================
# Lazy TTS Singleton
# =============================================================================

_tts_client: MultiVoiceAgentTTS | None = None


def get_tts() -> MultiVoiceAgentTTS:
    """Get or create TTS client (lazy singleton)."""
    global _tts_client
    if _tts_client is None:
        _tts_client = MultiVoiceAgentTTS()
        logger.info("MultiVoiceAgentTTS initialized")
    return _tts_client


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
# Per-Slot Processing (Structured Output + TTS)
# =============================================================================


async def process_slot(
    slot_id: int,
    agent_id: str,
    message: str,
    session: TTSSession,
    queue: asyncio.Queue[ServerSentEvent | None],
) -> None:
    """Process one slot: get structured LLM response, generate TTS.

    Args:
        slot_id: The slot ID (1-6)
        agent_id: The agent ID for this slot
        message: User message to send
        session: TTS session for audio file storage
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

        # Get structured response from LLM (no streaming with structured output)
        response: SpokenResponse = await llm.complete_structured(
            messages=conv.get_history(),
            model=model,
            response_model=SpokenResponse,
            temperature=settings.temperature,
        )

        # Add assistant response to conversation history (as JSON for context)
        conv.add_assistant(response.model_dump_json())

        # Emit slot.done with structured data
        await queue.put(
            ServerSentEvent(
                event="slot.done",
                data=SlotDoneEvent(
                    slotId=slot_id,
                    agentId=agent_id,
                    text=response.text,
                    voiceProfile=response.voice_profile,
                ).model_dump_json(),
            )
        )

        logger.info(
            f"Slot {slot_id} ({agent_id}) LLM done: "
            f"voice={response.voice_profile}, text={len(response.text)} chars"
        )

        # Generate TTS audio (in thread to avoid blocking event loop)
        try:
            tts = get_tts()
            audio_path = session.get_audio_path(slot_id, agent_id, response.voice_profile)

            await asyncio.to_thread(
                tts.generate_wav_to_file,
                response.text,
                response.voice_profile,
                audio_path,
            )

            # Emit slot.audio
            await queue.put(
                ServerSentEvent(
                    event="slot.audio",
                    data=SlotAudioEvent(
                        slotId=slot_id,
                        agentId=agent_id,
                        voiceProfile=response.voice_profile,
                        audioPath=session.get_relative_audio_path(
                            slot_id, agent_id, response.voice_profile
                        ),
                    ).model_dump_json(),
                )
            )

            logger.info(
                f"Slot {slot_id} ({agent_id}) TTS done: {audio_path.name}"
            )

        except Exception as tts_error:
            # TTS failed, but LLM succeeded - emit tts_error
            logger.error(f"Slot {slot_id} ({agent_id}) TTS error: {tts_error}")

            await queue.put(
                ServerSentEvent(
                    event="slot.error",
                    data=SlotErrorEvent(
                        slotId=slot_id,
                        agentId=agent_id,
                        error=ErrorDetail(type="tts_error", message=str(tts_error)),
                    ).model_dump_json(),
                )
            )

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

    All slots process concurrently. Events from different slots are interleaved
    as they arrive via a shared asyncio.Queue.

    Phase 2 event flow:
    - slot.start: Slot begins processing
    - slot.done: LLM response complete (text + voiceProfile)
    - slot.audio: TTS audio file ready
    - slot.error: Error occurred (LLM or TTS)
    - done: All slots finished

    Args:
        message: User message to broadcast
        slots: List of slot requests with slot ID and agent ID

    Yields:
        SSE events for slot.start, slot.done, slot.audio, slot.error, and done
    """
    # Create session for this broadcast
    session = TTSSession.create()
    logger.info(f"Created TTS session: {session.session_id}")

    queue: asyncio.Queue[ServerSentEvent | None] = asyncio.Queue()

    # Launch all slot processing concurrently
    tasks = [
        asyncio.create_task(
            process_slot(s.slotId, s.agentId, message, session, queue)
        )
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

    # Track which slots have been counted (to avoid double-counting TTS errors)
    counted_slots: set[int] = set()

    # Yield events as they arrive
    while True:
        event = await queue.get()

        if event is None:
            break

        yield event

        # Track slot completions for final event
        # Only count each slot once (slot.done or first slot.error)
        if event.event == "slot.done":
            data = json.loads(event.data)
            slot_id = data.get("slotId")
            if slot_id not in counted_slots:
                counted_slots.add(slot_id)
                completed += 1
        elif event.event == "slot.error":
            data = json.loads(event.data)
            slot_id = data.get("slotId")
            # Only count LLM errors (slot not already counted from slot.done)
            if slot_id not in counted_slots:
                counted_slots.add(slot_id)
                completed += 1

    # Emit final done event
    yield ServerSentEvent(
        event="done",
        data=DoneEvent(completedSlots=completed).model_dump_json(),
    )

    logger.info(
        f"Broadcast complete: {completed}/{len(slots)} slots, "
        f"session={session.session_id}"
    )
