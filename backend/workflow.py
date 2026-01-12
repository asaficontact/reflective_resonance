"""3-Turn Workflow Orchestrator for Reflective Resonance.

Implements the sequential turn execution:
1. Turn 1 (Respond): All slots respond to user message in parallel
2. Turn 2 (Comment): Each slot comments on exactly one peer response
3. Turn 3 (Reply): Slots that received comments reply to them

SSE events are emitted throughout for frontend consumption.
"""

import asyncio
import logging
import random
from collections.abc import AsyncGenerator
from typing import Any

from sse_starlette.sse import ServerSentEvent

from backend.agents import get_llm, get_model_for_agent
from backend.config import settings
from backend.conversations import get_or_create_conversation
from backend.models import (
    CommentSelection,
    DoneEvent,
    ErrorDetail,
    ReceivedComment,
    SlotAudioEvent,
    SlotDoneEvent,
    SlotErrorEvent,
    SlotRequest,
    SlotStartEvent,
    SummaryResult,
    Turn1Result,
    Turn2Result,
    Turn3Result,
    TurnDoneEvent,
    TurnStartEvent,
    WorkflowState,
    SpokenResponse,
)
from backend.prompts import (
    render_turn1_prompt,
    render_turn2_prompt,
    render_turn3_prompt,
    render_turn4_prompt,
)
from backend.sentiment import analyze_sentiment, SentimentResult
from backend.sessions import TTSSession
from backend.tts import MultiVoiceAgentTTS
from backend.waves import DecomposeJob, get_worker_pool, tts_path_to_waves_dir
from backend.events import get_orchestrator, SlotMeta, DialogueSpec

logger = logging.getLogger(__name__)

# Maximum comments any single slot can receive in Turn 3
MAX_COMMENTS_PER_TARGET = 3


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
# Wave Decomposition Helper
# =============================================================================


def _submit_decomposition_job(
    audio_path: "Path",
    session_id: str,
    turn_index: int,
    *,
    slot_id: int,
    agent_id: str,
    voice_profile: str,
    target_slot_id: int | None = None,
    summary_text: str | None = None,
    n_waves: int = 2,
) -> None:
    """Submit a decomposition job (non-blocking, best-effort).

    Called after TTS completes and slot.audio is emitted.
    Failures are logged but do not affect the workflow.

    Args:
        audio_path: Absolute path to the TTS WAV file
        session_id: The workflow session ID
        turn_index: Turn number (1, 2, 3, or -1 for summary)
        summary_text: For turn_index=-1, the summary text to include in the event
        n_waves: Number of wave files to produce (default: 2, use 6 for summary)
    """
    if not settings.waves_enabled:
        return

    try:
        from pathlib import Path

        output_dir = tts_path_to_waves_dir(audio_path, session_id, turn_index)
        tts_basename = (Path(audio_path) if not isinstance(audio_path, Path) else audio_path).stem
        job = DecomposeJob(
            session_id=session_id,
            turn_index=turn_index,
            slot_id=slot_id,
            agent_id=agent_id,
            voice_profile=voice_profile,
            tts_basename=tts_basename,
            input_path=Path(audio_path) if not isinstance(audio_path, Path) else audio_path,
            output_dir=output_dir,
            target_slot_id=target_slot_id,
            summary_text=summary_text,
            n_waves=n_waves,
        )

        pool = get_worker_pool()
        if not pool.submit_job(job):
            logger.warning(f"Waves queue full, dropped: {audio_path.name}")
    except Exception as e:
        logger.error(f"Failed to submit decomposition job: {e}")


# =============================================================================
# Events Orchestrator Helpers
# =============================================================================


def _compute_dialogues(state: WorkflowState) -> list[DialogueSpec]:
    """Compute dialogue specifications from Turn 2/3 results.

    A dialogue is created for each slot that has a successful Turn 3 reply.
    The commenters are the Turn 2 slots that commented on that slot.

    Args:
        state: Workflow state with turn2_results, turn3_results, and comments_by_target

    Returns:
        List of DialogueSpec for all valid dialogues
    """
    dialogues = []

    for slot_id, turn3_result in state.turn3_results.items():
        if not turn3_result.success:
            continue

        # Get the comments received by this slot
        comments = state.comments_by_target.get(slot_id, [])
        if not comments:
            continue

        # Build commenter SlotMetas from Turn 2 results
        commenters = []
        for comment in comments:
            turn2_result = state.turn2_results.get(comment.from_slot_id)
            if turn2_result and turn2_result.success:
                # Extract tts_basename from audio_path
                tts_basename = ""
                if turn2_result.audio_path:
                    from pathlib import Path
                    tts_basename = Path(turn2_result.audio_path).stem

                commenters.append(SlotMeta(
                    slot_id=turn2_result.slot_id,
                    agent_id=turn2_result.agent_id,
                    voice_profile=turn2_result.voice_profile,
                    tts_basename=tts_basename,
                ))

        # Build respondent SlotMeta
        respondent_basename = ""
        if turn3_result.audio_path:
            from pathlib import Path
            respondent_basename = Path(turn3_result.audio_path).stem

        respondent = SlotMeta(
            slot_id=turn3_result.slot_id,
            agent_id=turn3_result.agent_id,
            voice_profile=turn3_result.voice_profile,
            tts_basename=respondent_basename,
        )

        dialogues.append(DialogueSpec(
            dialogue_id=f"turn23-slot{slot_id}",
            target_slot_id=slot_id,
            commenters=commenters,
            respondent=respondent,
        ))

    # Sort by target slot ID for deterministic ordering
    dialogues.sort(key=lambda d: d.target_slot_id)
    return dialogues


def _notify_events_begin_session(state: WorkflowState) -> None:
    """Notify events orchestrator of session start."""
    if not settings.events_ws_enabled:
        return

    try:
        slot_metas = [
            SlotMeta(
                slot_id=slot.slotId,
                agent_id=slot.agentId,
                voice_profile="",  # Set later when TTS completes
                tts_basename="",
            )
            for slot in state.slots
        ]
        get_orchestrator().begin_session(state.session.session_id, slot_metas)
    except Exception as e:
        logger.error(f"Failed to notify events begin_session: {e}")


def _notify_events_turn1_complete(session_id: str) -> None:
    """Notify events orchestrator that Turn 1 is complete."""
    if not settings.events_ws_enabled:
        return

    try:
        get_orchestrator().turn1_complete(session_id)
    except Exception as e:
        logger.error(f"Failed to notify events turn1_complete: {e}")


def _notify_events_turn3_complete(state: WorkflowState) -> None:
    """Notify events orchestrator that Turn 3 is complete with dialogue specs."""
    if not settings.events_ws_enabled:
        return

    try:
        dialogues = _compute_dialogues(state)
        get_orchestrator().turn3_complete(state.session.session_id, dialogues)
    except Exception as e:
        logger.error(f"Failed to notify events turn3_complete: {e}")


async def _run_sentiment_analysis(
    state: WorkflowState,
    user_message: str,
) -> SentimentResult | None:
    """Run sentiment analysis and emit WebSocket event.

    Called in parallel with Turn 1 to provide early mood indication
    for TouchDesigner loading effects.

    Args:
        state: Workflow state with session info
        user_message: The user's message to analyze

    Returns:
        SentimentResult or None if disabled/failed
    """
    if not settings.events_ws_enabled or not settings.sentiment_enabled:
        return None

    result = await analyze_sentiment(user_message)

    if result:
        try:
            orchestrator = get_orchestrator()
            await orchestrator.emit_user_sentiment(
                session_id=state.session.session_id,
                sentiment=result.sentiment,
                justification=result.justification,
            )
        except Exception as e:
            logger.error(f"Failed to emit user_sentiment: {e}")

    return result


# =============================================================================
# Error Mapping
# =============================================================================


def map_exception_to_error_type(e: Exception) -> str:
    """Map exceptions to frontend ErrorType values."""
    error_name = type(e).__name__.lower()

    if "timeout" in error_name or isinstance(e, asyncio.TimeoutError):
        return "timeout"
    if "ratelimit" in error_name or "rate_limit" in error_name:
        return "rate_limit"
    if any(
        term in error_name
        for term in ["connection", "network", "dns", "socket", "refused"]
    ):
        return "network"
    if isinstance(e, (ConnectionError, OSError)):
        return "network"

    return "server_error"


# =============================================================================
# Turn 1: Response
# =============================================================================


async def process_turn1_slot(
    state: WorkflowState,
    slot_id: int,
    agent_id: str,
    queue: asyncio.Queue[ServerSentEvent],
) -> Turn1Result:
    """Process Turn 1 for a single slot: respond to user message.

    Args:
        state: Workflow state with session and user_message
        slot_id: The slot ID (1-6)
        agent_id: The agent ID for this slot
        queue: SSE event queue

    Returns:
        Turn1Result with success status and response data
    """
    session = state.session
    session_id = session.session_id

    try:
        # Emit slot.start
        await queue.put(
            ServerSentEvent(
                event="slot.start",
                data=SlotStartEvent(
                    sessionId=session_id,
                    turnIndex=1,
                    kind="response",
                    slotId=slot_id,
                    agentId=agent_id,
                ).model_dump_json(),
            )
        )

        # Get conversation and LLM
        conv = get_or_create_conversation(slot_id)
        llm = get_llm(agent_id)
        model = get_model_for_agent(agent_id)

        # Render prompt and add to conversation
        prompt = render_turn1_prompt(state.user_message)
        conv.add_user(prompt)

        # Get structured response
        response: SpokenResponse = await llm.complete_structured(
            messages=conv.get_history(),
            model=model,
            response_model=SpokenResponse,
            temperature=settings.temperature,
        )

        # Add to conversation history
        conv.add_assistant(response.model_dump_json())

        # Emit slot.done
        await queue.put(
            ServerSentEvent(
                event="slot.done",
                data=SlotDoneEvent(
                    sessionId=session_id,
                    turnIndex=1,
                    kind="response",
                    slotId=slot_id,
                    agentId=agent_id,
                    text=response.text,
                    voiceProfile=response.voice_profile,
                ).model_dump_json(),
            )
        )

        logger.info(
            f"Turn 1 Slot {slot_id} ({agent_id}) LLM done: "
            f"voice={response.voice_profile}, text={len(response.text)} chars"
        )

        # Generate TTS
        audio_path = None
        relative_path = None
        try:
            tts = get_tts()
            audio_path = session.get_turn1_audio_path(slot_id, agent_id, response.voice_profile)
            relative_path = session.get_turn1_relative_path(slot_id, agent_id, response.voice_profile)

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
                        sessionId=session_id,
                        turnIndex=1,
                        kind="response",
                        slotId=slot_id,
                        agentId=agent_id,
                        voiceProfile=response.voice_profile,
                        audioPath=relative_path,
                    ).model_dump_json(),
                )
            )

            # Submit decomposition job (non-blocking, fire-and-forget)
            _submit_decomposition_job(
                audio_path,
                session_id,
                turn_index=1,
                slot_id=slot_id,
                agent_id=agent_id,
                voice_profile=response.voice_profile,
            )

            # Add to manifest
            session.add_turn1_entry(
                slot_id=slot_id,
                agent_id=agent_id,
                voice_profile=response.voice_profile,
                text=response.text,
                audio_path=relative_path,
            )

            logger.info(f"Turn 1 Slot {slot_id} ({agent_id}) TTS done: {audio_path.name}")

        except Exception as tts_error:
            logger.error(f"Turn 1 Slot {slot_id} ({agent_id}) TTS error: {tts_error}")
            await queue.put(
                ServerSentEvent(
                    event="slot.error",
                    data=SlotErrorEvent(
                        sessionId=session_id,
                        turnIndex=1,
                        kind="response",
                        slotId=slot_id,
                        agentId=agent_id,
                        error=ErrorDetail(type="tts_error", message=str(tts_error)),
                    ).model_dump_json(),
                )
            )

        return Turn1Result(
            slot_id=slot_id,
            agent_id=agent_id,
            text=response.text,
            voice_profile=response.voice_profile,
            success=True,
            audio_path=str(relative_path) if relative_path else None,
        )

    except Exception as e:
        error_type = map_exception_to_error_type(e)
        logger.error(f"Turn 1 Slot {slot_id} ({agent_id}) error: {error_type} - {e}")

        await queue.put(
            ServerSentEvent(
                event="slot.error",
                data=SlotErrorEvent(
                    sessionId=session_id,
                    turnIndex=1,
                    kind="response",
                    slotId=slot_id,
                    agentId=agent_id,
                    error=ErrorDetail(type=error_type, message=str(e)),
                ).model_dump_json(),
            )
        )

        return Turn1Result(
            slot_id=slot_id,
            agent_id=agent_id,
            text="",
            voice_profile="",
            success=False,
        )


async def execute_turn1(
    state: WorkflowState,
    queue: asyncio.Queue[ServerSentEvent],
) -> None:
    """Execute Turn 1 for all slots in parallel.

    Args:
        state: Workflow state (updated with turn1_results)
        queue: SSE event queue
    """
    session_id = state.session.session_id

    # Emit turn.start
    await queue.put(
        ServerSentEvent(
            event="turn.start",
            data=TurnStartEvent(sessionId=session_id, turnIndex=1).model_dump_json(),
        )
    )

    # Process all slots in parallel
    tasks = [
        asyncio.create_task(
            process_turn1_slot(state, slot.slotId, slot.agentId, queue)
        )
        for slot in state.slots
    ]

    results = await asyncio.gather(*tasks)

    # Store results
    for result in results:
        state.turn1_results[result.slot_id] = result

    # Count successful slots
    successful_count = sum(1 for r in results if r.success)

    # Emit turn.done
    await queue.put(
        ServerSentEvent(
            event="turn.done",
            data=TurnDoneEvent(
                sessionId=session_id,
                turnIndex=1,
                slotCount=successful_count,
            ).model_dump_json(),
        )
    )

    # Notify events orchestrator (for TouchDesigner WebSocket)
    _notify_events_turn1_complete(session_id)

    logger.info(f"Turn 1 complete: {successful_count}/{len(state.slots)} slots succeeded")


# =============================================================================
# Turn 2: Comment
# =============================================================================


def build_peer_responses(state: WorkflowState, exclude_slot_id: int) -> list[dict]:
    """Build list of peer responses for Turn 2 prompt.

    Excludes the requesting slot and any failed slots.

    Args:
        state: Workflow state with turn1_results
        exclude_slot_id: Slot to exclude (self)

    Returns:
        List of peer responses with slotId, agentId, text
    """
    peers = []
    for slot_id, result in state.turn1_results.items():
        if slot_id != exclude_slot_id and result.success:
            peers.append({
                "slotId": result.slot_id,
                "agentId": result.agent_id,
                "text": result.text,
            })

    # Shuffle to reduce position bias
    random.shuffle(peers)
    return peers


async def process_turn2_slot(
    state: WorkflowState,
    slot_id: int,
    agent_id: str,
    queue: asyncio.Queue[ServerSentEvent],
) -> Turn2Result:
    """Process Turn 2 for a single slot: comment on a peer response.

    Args:
        state: Workflow state with turn1_results
        slot_id: The slot ID (1-6)
        agent_id: The agent ID for this slot
        queue: SSE event queue

    Returns:
        Turn2Result with comment data
    """
    session = state.session
    session_id = session.session_id

    try:
        # Emit slot.start
        await queue.put(
            ServerSentEvent(
                event="slot.start",
                data=SlotStartEvent(
                    sessionId=session_id,
                    turnIndex=2,
                    kind="comment",
                    slotId=slot_id,
                    agentId=agent_id,
                ).model_dump_json(),
            )
        )

        # Get conversation and LLM
        conv = get_or_create_conversation(slot_id)
        llm = get_llm(agent_id)
        model = get_model_for_agent(agent_id)

        # Build peer responses (excluding self and failed slots)
        peer_responses = build_peer_responses(state, slot_id)

        # Render prompt
        prompt = render_turn2_prompt(slot_id, agent_id, peer_responses)
        conv.add_user(prompt)

        # Get structured response
        response: CommentSelection = await llm.complete_structured(
            messages=conv.get_history(),
            model=model,
            response_model=CommentSelection,
            temperature=settings.temperature,
        )

        # Add to conversation history
        conv.add_assistant(response.model_dump_json())

        # Emit slot.done
        await queue.put(
            ServerSentEvent(
                event="slot.done",
                data=SlotDoneEvent(
                    sessionId=session_id,
                    turnIndex=2,
                    kind="comment",
                    slotId=slot_id,
                    agentId=agent_id,
                    text=response.comment,
                    voiceProfile=response.voice_profile,
                    targetSlotId=response.targetSlotId,
                ).model_dump_json(),
            )
        )

        logger.info(
            f"Turn 2 Slot {slot_id} ({agent_id}) LLM done: "
            f"target={response.targetSlotId}, voice={response.voice_profile}"
        )

        # Generate TTS
        audio_path = None
        relative_path = None
        try:
            tts = get_tts()
            audio_path = session.get_turn2_audio_path(
                slot_id, response.targetSlotId, agent_id, response.voice_profile
            )
            relative_path = session.get_turn2_relative_path(
                slot_id, response.targetSlotId, agent_id, response.voice_profile
            )

            await asyncio.to_thread(
                tts.generate_wav_to_file,
                response.comment,
                response.voice_profile,
                audio_path,
            )

            # Emit slot.audio
            await queue.put(
                ServerSentEvent(
                    event="slot.audio",
                    data=SlotAudioEvent(
                        sessionId=session_id,
                        turnIndex=2,
                        kind="comment",
                        slotId=slot_id,
                        agentId=agent_id,
                        voiceProfile=response.voice_profile,
                        audioPath=relative_path,
                    ).model_dump_json(),
                )
            )

            # Submit decomposition job (non-blocking, fire-and-forget)
            _submit_decomposition_job(
                audio_path,
                session_id,
                turn_index=2,
                slot_id=slot_id,
                agent_id=agent_id,
                voice_profile=response.voice_profile,
                target_slot_id=response.targetSlotId,
            )

            # Add to manifest
            session.add_turn2_entry(
                slot_id=slot_id,
                agent_id=agent_id,
                target_slot_id=response.targetSlotId,
                voice_profile=response.voice_profile,
                comment=response.comment,
                audio_path=relative_path,
            )

            logger.info(f"Turn 2 Slot {slot_id} ({agent_id}) TTS done: {audio_path.name}")

        except Exception as tts_error:
            logger.error(f"Turn 2 Slot {slot_id} ({agent_id}) TTS error: {tts_error}")
            await queue.put(
                ServerSentEvent(
                    event="slot.error",
                    data=SlotErrorEvent(
                        sessionId=session_id,
                        turnIndex=2,
                        kind="comment",
                        slotId=slot_id,
                        agentId=agent_id,
                        error=ErrorDetail(type="tts_error", message=str(tts_error)),
                    ).model_dump_json(),
                )
            )

        return Turn2Result(
            slot_id=slot_id,
            agent_id=agent_id,
            target_slot_id=response.targetSlotId,
            comment=response.comment,
            voice_profile=response.voice_profile,
            success=True,
            audio_path=str(relative_path) if relative_path else None,
        )

    except Exception as e:
        error_type = map_exception_to_error_type(e)
        logger.error(f"Turn 2 Slot {slot_id} ({agent_id}) error: {error_type} - {e}")

        await queue.put(
            ServerSentEvent(
                event="slot.error",
                data=SlotErrorEvent(
                    sessionId=session_id,
                    turnIndex=2,
                    kind="comment",
                    slotId=slot_id,
                    agentId=agent_id,
                    error=ErrorDetail(type=error_type, message=str(e)),
                ).model_dump_json(),
            )
        )

        return Turn2Result(
            slot_id=slot_id,
            agent_id=agent_id,
            target_slot_id=0,
            comment="",
            voice_profile="",
            success=False,
        )


def route_comments(state: WorkflowState) -> None:
    """Route Turn 2 comments to their targets, capping at MAX_COMMENTS_PER_TARGET.

    Populates state.comments_by_target with ReceivedComment objects.
    """
    # Group comments by target
    comments_by_target: dict[int, list[ReceivedComment]] = {}

    for result in state.turn2_results.values():
        if not result.success:
            continue

        target_id = result.target_slot_id
        if target_id not in comments_by_target:
            comments_by_target[target_id] = []

        comments_by_target[target_id].append(
            ReceivedComment(
                from_slot_id=result.slot_id,
                from_agent_id=result.agent_id,
                comment=result.comment,
            )
        )

    # Cap comments per target
    for target_id, comments in comments_by_target.items():
        if len(comments) > MAX_COMMENTS_PER_TARGET:
            # Randomly select which comments to keep
            comments_by_target[target_id] = random.sample(comments, MAX_COMMENTS_PER_TARGET)
            logger.info(
                f"Slot {target_id} received {len(comments)} comments, "
                f"capped to {MAX_COMMENTS_PER_TARGET}"
            )

    state.comments_by_target = comments_by_target


async def execute_turn2(
    state: WorkflowState,
    queue: asyncio.Queue[ServerSentEvent],
) -> None:
    """Execute Turn 2 for all eligible slots in parallel.

    Only slots that succeeded in Turn 1 participate.

    Args:
        state: Workflow state (updated with turn2_results and comments_by_target)
        queue: SSE event queue
    """
    session_id = state.session.session_id

    # Filter to slots with successful Turn 1
    eligible_slots = [
        slot for slot in state.slots
        if state.turn1_results.get(slot.slotId, Turn1Result(0, "", "", "", False)).success
    ]

    if not eligible_slots:
        logger.warning("Turn 2: No eligible slots (all Turn 1 failed)")
        return

    # Emit turn.start
    await queue.put(
        ServerSentEvent(
            event="turn.start",
            data=TurnStartEvent(sessionId=session_id, turnIndex=2).model_dump_json(),
        )
    )

    # Process all eligible slots in parallel
    tasks = [
        asyncio.create_task(
            process_turn2_slot(state, slot.slotId, slot.agentId, queue)
        )
        for slot in eligible_slots
    ]

    results = await asyncio.gather(*tasks)

    # Store results
    for result in results:
        state.turn2_results[result.slot_id] = result

    # Route comments to targets
    route_comments(state)

    # Count successful slots
    successful_count = sum(1 for r in results if r.success)

    # Emit turn.done
    await queue.put(
        ServerSentEvent(
            event="turn.done",
            data=TurnDoneEvent(
                sessionId=session_id,
                turnIndex=2,
                slotCount=successful_count,
            ).model_dump_json(),
        )
    )

    logger.info(f"Turn 2 complete: {successful_count}/{len(eligible_slots)} slots succeeded")


# =============================================================================
# Turn 3: Reply
# =============================================================================


async def process_turn3_slot(
    state: WorkflowState,
    slot_id: int,
    agent_id: str,
    received_comments: list[ReceivedComment],
    queue: asyncio.Queue[ServerSentEvent],
) -> Turn3Result:
    """Process Turn 3 for a single slot: reply to received comments.

    Args:
        state: Workflow state
        slot_id: The slot ID (1-6)
        agent_id: The agent ID for this slot
        received_comments: Comments received by this slot
        queue: SSE event queue

    Returns:
        Turn3Result with reply data
    """
    session = state.session
    session_id = session.session_id

    try:
        # Emit slot.start
        await queue.put(
            ServerSentEvent(
                event="slot.start",
                data=SlotStartEvent(
                    sessionId=session_id,
                    turnIndex=3,
                    kind="reply",
                    slotId=slot_id,
                    agentId=agent_id,
                ).model_dump_json(),
            )
        )

        # Get conversation and LLM
        conv = get_or_create_conversation(slot_id)
        llm = get_llm(agent_id)
        model = get_model_for_agent(agent_id)

        # Get original Turn 1 response
        turn1_result = state.turn1_results[slot_id]
        original_response = turn1_result.text

        # Format comments for prompt
        comments_list = [
            {
                "fromSlotId": c.from_slot_id,
                "fromAgentId": c.from_agent_id,
                "comment": c.comment,
            }
            for c in received_comments
        ]

        # Render prompt
        prompt = render_turn3_prompt(slot_id, agent_id, original_response, comments_list)
        conv.add_user(prompt)

        # Get structured response
        response: SpokenResponse = await llm.complete_structured(
            messages=conv.get_history(),
            model=model,
            response_model=SpokenResponse,
            temperature=settings.temperature,
        )

        # Add to conversation history
        conv.add_assistant(response.model_dump_json())

        # Emit slot.done
        await queue.put(
            ServerSentEvent(
                event="slot.done",
                data=SlotDoneEvent(
                    sessionId=session_id,
                    turnIndex=3,
                    kind="reply",
                    slotId=slot_id,
                    agentId=agent_id,
                    text=response.text,
                    voiceProfile=response.voice_profile,
                ).model_dump_json(),
            )
        )

        logger.info(
            f"Turn 3 Slot {slot_id} ({agent_id}) LLM done: "
            f"voice={response.voice_profile}, text={len(response.text)} chars"
        )

        # Generate TTS
        audio_path = None
        relative_path = None
        try:
            tts = get_tts()
            audio_path = session.get_turn3_audio_path(slot_id, agent_id, response.voice_profile)
            relative_path = session.get_turn3_relative_path(slot_id, agent_id, response.voice_profile)

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
                        sessionId=session_id,
                        turnIndex=3,
                        kind="reply",
                        slotId=slot_id,
                        agentId=agent_id,
                        voiceProfile=response.voice_profile,
                        audioPath=relative_path,
                    ).model_dump_json(),
                )
            )

            # Submit decomposition job (non-blocking, fire-and-forget)
            _submit_decomposition_job(
                audio_path,
                session_id,
                turn_index=3,
                slot_id=slot_id,
                agent_id=agent_id,
                voice_profile=response.voice_profile,
            )

            # Add to manifest
            session.add_turn3_entry(
                slot_id=slot_id,
                agent_id=agent_id,
                voice_profile=response.voice_profile,
                text=response.text,
                audio_path=relative_path,
                received_comments=comments_list,
            )

            logger.info(f"Turn 3 Slot {slot_id} ({agent_id}) TTS done: {audio_path.name}")

        except Exception as tts_error:
            logger.error(f"Turn 3 Slot {slot_id} ({agent_id}) TTS error: {tts_error}")
            await queue.put(
                ServerSentEvent(
                    event="slot.error",
                    data=SlotErrorEvent(
                        sessionId=session_id,
                        turnIndex=3,
                        kind="reply",
                        slotId=slot_id,
                        agentId=agent_id,
                        error=ErrorDetail(type="tts_error", message=str(tts_error)),
                    ).model_dump_json(),
                )
            )

        return Turn3Result(
            slot_id=slot_id,
            agent_id=agent_id,
            text=response.text,
            voice_profile=response.voice_profile,
            success=True,
            audio_path=str(relative_path) if relative_path else None,
        )

    except Exception as e:
        error_type = map_exception_to_error_type(e)
        logger.error(f"Turn 3 Slot {slot_id} ({agent_id}) error: {error_type} - {e}")

        await queue.put(
            ServerSentEvent(
                event="slot.error",
                data=SlotErrorEvent(
                    sessionId=session_id,
                    turnIndex=3,
                    kind="reply",
                    slotId=slot_id,
                    agentId=agent_id,
                    error=ErrorDetail(type=error_type, message=str(e)),
                ).model_dump_json(),
            )
        )

        return Turn3Result(
            slot_id=slot_id,
            agent_id=agent_id,
            text="",
            voice_profile="",
            success=False,
        )


async def execute_turn3(
    state: WorkflowState,
    queue: asyncio.Queue[ServerSentEvent],
) -> None:
    """Execute Turn 3 for slots that received comments.

    Only slots that received at least 1 comment participate.

    Args:
        state: Workflow state (updated with turn3_results)
        queue: SSE event queue
    """
    session_id = state.session.session_id

    # Find slots that received comments
    slots_with_comments = []
    for slot in state.slots:
        if slot.slotId in state.comments_by_target:
            comments = state.comments_by_target[slot.slotId]
            if comments:
                slots_with_comments.append((slot, comments))

    if not slots_with_comments:
        logger.info("Turn 3: No slots received comments, skipping")
        return

    # Emit turn.start
    await queue.put(
        ServerSentEvent(
            event="turn.start",
            data=TurnStartEvent(sessionId=session_id, turnIndex=3).model_dump_json(),
        )
    )

    # Process all slots with comments in parallel
    tasks = [
        asyncio.create_task(
            process_turn3_slot(state, slot.slotId, slot.agentId, comments, queue)
        )
        for slot, comments in slots_with_comments
    ]

    results = await asyncio.gather(*tasks)

    # Store results
    for result in results:
        state.turn3_results[result.slot_id] = result

    # Count successful slots
    successful_count = sum(1 for r in results if r.success)

    # Emit turn.done
    await queue.put(
        ServerSentEvent(
            event="turn.done",
            data=TurnDoneEvent(
                sessionId=session_id,
                turnIndex=3,
                slotCount=successful_count,
            ).model_dump_json(),
        )
    )

    # Notify events orchestrator (for TouchDesigner WebSocket)
    _notify_events_turn3_complete(state)

    logger.info(f"Turn 3 complete: {successful_count}/{len(slots_with_comments)} slots succeeded")


# =============================================================================
# Turn 4: Summary
# =============================================================================


def _collect_all_responses(state: WorkflowState) -> list[dict]:
    """Collect all responses from turns 1-3 for summary prompt.

    Args:
        state: Workflow state with turn results

    Returns:
        List of response dicts with slot_id, turn_label, and text
    """
    responses = []

    # Turn 1 responses
    for slot_id, result in sorted(state.turn1_results.items()):
        if result.success:
            responses.append({
                "slot_id": result.slot_id,
                "turn_label": "Turn 1 reflection",
                "text": result.text,
            })

    # Turn 2 comments
    for slot_id, result in sorted(state.turn2_results.items()):
        if result.success:
            responses.append({
                "slot_id": result.slot_id,
                "turn_label": "Turn 2 comment",
                "text": result.comment,
            })

    # Turn 3 replies
    for slot_id, result in sorted(state.turn3_results.items()):
        if result.success:
            responses.append({
                "slot_id": result.slot_id,
                "turn_label": "Turn 3 reply",
                "text": result.text,
            })

    return responses


async def execute_summary(
    state: WorkflowState,
    queue: asyncio.Queue[ServerSentEvent],
) -> SummaryResult:
    """Execute Turn 4: Generate summary of all responses.

    Uses gpt-4o with fresh conversation (no history).

    Args:
        state: Workflow state with turn results
        queue: SSE event queue for frontend updates

    Returns:
        SummaryResult with success status and response data
    """
    session = state.session
    session_id = session.session_id

    # Emit turn.start for Turn 4
    await queue.put(
        ServerSentEvent(
            event="turn.start",
            data=TurnStartEvent(sessionId=session_id, turnIndex=4).model_dump_json(),
        )
    )

    try:
        # Collect all responses for context
        all_responses = _collect_all_responses(state)

        if not all_responses:
            logger.warning("No responses to summarize")
            return SummaryResult(text="", voice_profile="", success=False)

        # Emit slot.start for summary (slotId=0 for summary)
        await queue.put(
            ServerSentEvent(
                event="slot.start",
                data=SlotStartEvent(
                    sessionId=session_id,
                    turnIndex=4,
                    kind="summary",
                    slotId=0,
                    agentId="gpt-4o",
                ).model_dump_json(),
            )
        )

        # Get LLM (gpt-4o, fresh conversation)
        llm = get_llm("gpt-4o")
        model = settings.summary_model

        # Render prompt
        prompt = render_turn4_prompt(state.user_message, all_responses)

        # Fresh conversation - just system prompt + user prompt
        messages = [
            {"role": "system", "content": settings.default_system_prompt},
            {"role": "user", "content": prompt},
        ]

        # Get structured response
        response: SpokenResponse = await llm.complete_structured(
            messages=messages,
            model=model,
            response_model=SpokenResponse,
            temperature=settings.summary_temperature,
        )

        logger.info(
            f"Summary LLM done: voice={response.voice_profile}, "
            f"text={len(response.text)} chars"
        )

        # Emit slot.done for summary
        await queue.put(
            ServerSentEvent(
                event="slot.done",
                data=SlotDoneEvent(
                    sessionId=session_id,
                    turnIndex=4,
                    kind="summary",
                    slotId=0,
                    agentId="gpt-4o",
                    text=response.text,
                    voiceProfile=response.voice_profile,
                ).model_dump_json(),
            )
        )

        # Generate TTS
        audio_path = None
        relative_path = None
        try:
            tts = get_tts()
            audio_path = session.get_summary_audio_path(response.voice_profile)
            relative_path = session.get_summary_relative_path(response.voice_profile)

            await asyncio.to_thread(
                tts.generate_wav_to_file,
                response.text,
                response.voice_profile,
                audio_path,
            )

            logger.info(f"Summary TTS done: {audio_path.name}")

            # Emit slot.audio for summary
            await queue.put(
                ServerSentEvent(
                    event="slot.audio",
                    data=SlotAudioEvent(
                        sessionId=session_id,
                        turnIndex=4,
                        kind="summary",
                        slotId=0,
                        agentId="gpt-4o",
                        voiceProfile=response.voice_profile,
                        audioPath=relative_path,
                    ).model_dump_json(),
                )
            )

            # Submit decomposition job (slot_id=-1 for summary, n_waves=6 for 6 slots)
            _submit_decomposition_job(
                audio_path,
                session_id,
                turn_index=-1,  # Special index for summary
                slot_id=-1,
                agent_id="gpt-4o",
                voice_profile=response.voice_profile,
                summary_text=response.text,  # Pass text for event emission
                n_waves=6,  # 6 waves for 6 speaker slots
            )

            # Add to manifest
            session.add_summary_entry(
                voice_profile=response.voice_profile,
                text=response.text,
                audio_path=relative_path,
            )

        except Exception as tts_error:
            logger.error(f"Summary TTS error: {tts_error}")
            return SummaryResult(
                text=response.text,
                voice_profile=response.voice_profile,
                success=False,
            )

        # Emit turn.done for Turn 4
        await queue.put(
            ServerSentEvent(
                event="turn.done",
                data=TurnDoneEvent(
                    sessionId=session_id,
                    turnIndex=4,
                    slotCount=1,  # Summary is always 1 "slot"
                ).model_dump_json(),
            )
        )

        return SummaryResult(
            text=response.text,
            voice_profile=response.voice_profile,
            success=True,
            audio_path=str(relative_path),
        )

    except Exception as e:
        logger.error(f"Summary generation error: {e}")
        return SummaryResult(text="", voice_profile="", success=False)


# =============================================================================
# Main Workflow
# =============================================================================


async def run_three_turn_workflow(
    message: str,
    slots: list[SlotRequest],
) -> AsyncGenerator[ServerSentEvent, None]:
    """Run the complete 3-turn workflow.

    Args:
        message: User message to broadcast
        slots: List of slot requests

    Yields:
        SSE events for all turns
    """
    # Create session
    session = TTSSession.create()
    logger.info(f"Created TTS session: {session.session_id}")

    # Initialize workflow state
    state = WorkflowState(
        session=session,
        slots=slots,
        user_message=message,
    )

    # Notify events orchestrator of session start (for TouchDesigner WebSocket)
    _notify_events_begin_session(state)

    # Create event queue
    queue: asyncio.Queue[ServerSentEvent] = asyncio.Queue()

    # Run workflow in background task
    async def run_workflow():
        try:
            # Run sentiment analysis in parallel with Turn 1
            # Sentiment is fast (~1s) and emits user_sentiment event early
            sentiment_task = asyncio.create_task(
                _run_sentiment_analysis(state, message)
            )

            # Turn 1: All slots respond to user
            await execute_turn1(state, queue)

            # Ensure sentiment completes (don't block if failed)
            try:
                await asyncio.wait_for(sentiment_task, timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("Sentiment task didn't complete in time after Turn 1")

            # Turn 2: Each slot comments on one peer
            await execute_turn2(state, queue)

            # Turn 3: Slots with comments reply
            await execute_turn3(state, queue)

            # Turn 4: Summary (runs after Turn 3)
            if settings.summary_enabled:
                state.summary_result = await execute_summary(state, queue)
                logger.info(
                    f"Summary complete: success={state.summary_result.success}"
                )

            # Write manifest
            manifest_path = session.write_manifest()
            logger.info(f"Manifest written: {manifest_path}")

        except Exception as e:
            logger.error(f"Workflow error: {e}")
        finally:
            # Signal completion
            await queue.put(None)

    # Start workflow
    asyncio.create_task(run_workflow())

    # Track completion stats
    completed_slots = 0
    counted_slots: set[int] = set()

    # Yield events as they arrive
    while True:
        event = await queue.get()

        if event is None:
            break

        yield event

        # Track slot completions (for final event)
        if event.event == "slot.done":
            import json
            data = json.loads(event.data)
            slot_id = data.get("slotId")
            turn_index = data.get("turnIndex")
            # Only count Turn 1 completions for total
            if turn_index == 1 and slot_id not in counted_slots:
                counted_slots.add(slot_id)
                completed_slots += 1

    # Emit final done event
    turn_count = 4 if settings.summary_enabled else 3
    yield ServerSentEvent(
        event="done",
        data=DoneEvent(
            sessionId=session.session_id,
            completedSlots=completed_slots,
            turns=turn_count,
        ).model_dump_json(),
    )

    logger.info(
        f"Workflow complete: {completed_slots}/{len(slots)} slots, "
        f"turns={turn_count}, session={session.session_id}"
    )
