"""Events orchestrator for TouchDesigner WebSocket notifications.

This module manages the coordination between:
- Wave decomposition job completions (from waves/worker.py)
- Session lifecycle events (from workflow.py)
- WebSocket event emission (to TouchDesigner)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Callable

from starlette.websockets import WebSocket, WebSocketState

from backend.events.models import (
    DialogueWavesPayload,
    EventEnvelope,
    PlayOrderItem,
    SlotWaveInfo,
    Turn1WavesPayload,
    UserSentimentPayload,
)
from backend.events.state import DialogueSpec, SessionEventsState, SlotMeta

if TYPE_CHECKING:
    from backend.waves.worker import WavesJobResult

logger = logging.getLogger(__name__)


class EventsOrchestrator:
    """
    Orchestrates wave-mix readiness tracking and WebSocket event emission.

    Single-client policy: Only one TouchDesigner client is supported.
    When a new client connects, the old one is disconnected.
    """

    def __init__(
        self,
        turn1_timeout_s: float = 15.0,
        dialogue_timeout_s: float = 30.0,
        workflow_timeout_s: float = 60.0,
    ):
        """Initialize the orchestrator.

        Args:
            turn1_timeout_s: Timeout for Turn 1 partial event emission (legacy)
            dialogue_timeout_s: Timeout for dialogue partial event emission (legacy)
            workflow_timeout_s: Overall timeout for batch emission of all events
        """
        self._turn1_timeout_s = turn1_timeout_s
        self._dialogue_timeout_s = dialogue_timeout_s
        self._workflow_timeout_s = workflow_timeout_s

        # Session state tracking
        self._sessions: dict[str, SessionEventsState] = {}

        # WebSocket client (single-client)
        self._ws_client: WebSocket | None = None
        self._ws_lock = asyncio.Lock()

        # Results notification queue
        self._results_queue: asyncio.Queue[WavesJobResult] = asyncio.Queue()
        self._consumer_task: asyncio.Task | None = None
        self._running = False

        # Timeout tasks per session
        self._timeout_tasks: dict[str, asyncio.Task] = {}

    async def start(self) -> None:
        """Start the orchestrator. Call on app startup."""
        if self._running:
            logger.warning("EventsOrchestrator already running")
            return

        logger.info("Starting EventsOrchestrator")
        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_results())
        logger.info("EventsOrchestrator started")

    async def stop(self) -> None:
        """Stop the orchestrator. Call on app shutdown."""
        if not self._running:
            return

        logger.info("Stopping EventsOrchestrator...")
        self._running = False

        # Cancel timeout tasks
        for task in self._timeout_tasks.values():
            task.cancel()
        self._timeout_tasks.clear()

        # Stop consumer
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None

        # Close WebSocket
        await self.remove_client()

        self._sessions.clear()
        logger.info("EventsOrchestrator stopped")

    # -------------------------------------------------------------------------
    # WebSocket client management
    # -------------------------------------------------------------------------

    async def set_client(self, ws: WebSocket) -> None:
        """Set the WebSocket client (single-client policy).

        If another client is connected, it will be disconnected.
        """
        async with self._ws_lock:
            if self._ws_client is not None:
                logger.info("Disconnecting previous WebSocket client (new client connected)")
                try:
                    await self._ws_client.close(code=1000, reason="New client connected")
                except Exception as e:
                    logger.warning(f"Error closing previous WebSocket: {e}")
            self._ws_client = ws
            logger.info("WebSocket client connected")

    async def remove_client(self) -> None:
        """Remove the current WebSocket client."""
        async with self._ws_lock:
            if self._ws_client is not None:
                try:
                    if self._ws_client.client_state == WebSocketState.CONNECTED:
                        await self._ws_client.close()
                except Exception as e:
                    logger.warning(f"Error closing WebSocket: {e}")
                self._ws_client = None
                logger.info("WebSocket client disconnected")

    # -------------------------------------------------------------------------
    # Workflow hooks (called from workflow.py)
    # -------------------------------------------------------------------------

    def begin_session(self, session_id: str, slots: list[SlotMeta]) -> None:
        """Initialize session state when a new workflow session begins.

        Args:
            session_id: The workflow session UUID
            slots: List of slot metadata (slot_id, agent_id, voice_profile, tts_basename)
        """
        if session_id in self._sessions:
            logger.warning(f"Session {session_id} already exists, resetting state")

        slot_ids = {s.slot_id for s in slots}
        state = SessionEventsState(
            session_id=session_id,
            turn1_expected=slot_ids,
            turn2_expected=slot_ids,  # Same slots participate in Turn 2
        )
        self._sessions[session_id] = state
        logger.info(f"Session {session_id} initialized with {len(slots)} slots")

    def turn1_complete(self, session_id: str) -> None:
        """Mark Turn 1 LLM/TTS as complete. Waves tracked but NOT emitted yet.

        Called after Turn 1 turn.done event in workflow.
        Note: Batch emission handles overall timeout, no individual timeout needed.
        """
        state = self._sessions.get(session_id)
        if not state:
            logger.warning(f"turn1_complete: Session {session_id} not found")
            return

        logger.info(f"Session {session_id}: Turn 1 LLM/TTS complete, awaiting batch")

    def turn3_complete(
        self, session_id: str, dialogues: list[DialogueSpec]
    ) -> None:
        """Mark Turn 3 complete, compute expectations, start batch timeout.

        Called after Turn 3 turn.done event in workflow.

        Args:
            session_id: The workflow session UUID
            dialogues: List of computed dialogue specifications
        """
        state = self._sessions.get(session_id)
        if not state:
            logger.warning(f"turn3_complete: Session {session_id} not found")
            return

        state.dialogues = dialogues
        state.workflow_complete = True

        # Compute Turn 3 expected slots from dialogues (respondents)
        turn3_expected = {d.respondent.slot_id for d in dialogues if d.respondent}
        state.turn3_expected = turn3_expected

        logger.info(
            f"Session {session_id}: Turn 3 complete, "
            f"{len(dialogues)} dialogues, Turn 3 slots: {turn3_expected}"
        )

        # Start workflow timeout for batch emission
        task_key = f"{session_id}_workflow"
        if task_key not in self._timeout_tasks:
            self._timeout_tasks[task_key] = asyncio.create_task(
                self._workflow_timeout_handler(session_id)
            )

        # Check if already ready (wave jobs may have completed during Turn 3)
        asyncio.create_task(self._check_and_emit_batch(session_id))

    def register_slot_metadata(
        self,
        session_id: str,
        turn_index: int,
        slot_id: int,
        agent_id: str,
        voice_profile: str,
        tts_basename: str,
    ) -> None:
        """Register slot metadata after TTS completes.

        Called from workflow.py after slot.audio event.
        This provides the metadata needed to construct event payloads.
        """
        state = self._sessions.get(session_id)
        if not state:
            return

        meta = SlotMeta(
            slot_id=slot_id,
            agent_id=agent_id,
            voice_profile=voice_profile,
            tts_basename=tts_basename,
        )

        # Store metadata by turn for later use
        if turn_index == 1:
            # Turn 1 metadata stored in turn1_ready when wave decomposition completes
            pass  # Will be set when notify_result is called
        elif turn_index == 2:
            # Store Turn 2 metadata for dialogue construction
            pass  # Will be set when notify_result is called
        elif turn_index == 3:
            # Store Turn 3 metadata for dialogue construction
            pass  # Will be set when notify_result is called

    # -------------------------------------------------------------------------
    # Result notification (called from waves worker)
    # -------------------------------------------------------------------------

    def notify_result(self, result: WavesJobResult) -> None:
        """Notify the orchestrator of a wave decomposition result.

        This is called from the waves worker when a job completes.
        Thread-safe: uses asyncio queue.
        """
        try:
            self._results_queue.put_nowait(result)
        except asyncio.QueueFull:
            logger.warning(f"Results queue full, dropping result for {result.job.session_id}")

    # -------------------------------------------------------------------------
    # Internal: Results consumer
    # -------------------------------------------------------------------------

    async def _consume_results(self) -> None:
        """Consume wave decomposition results and update session state."""
        logger.debug("Results consumer started")

        while self._running:
            try:
                # Wait for results with timeout to check _running flag
                try:
                    result = await asyncio.wait_for(
                        self._results_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                await self._handle_result(result)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error consuming result: {e}")

        logger.debug("Results consumer stopped")

    async def _handle_result(self, result: WavesJobResult) -> None:
        """Handle a single wave decomposition result."""
        job = result.job
        decompose_result = result.result

        session_id = job.session_id
        turn_index = job.turn_index

        state = self._sessions.get(session_id)
        if not state or state.batch_emitted:
            # Unknown session or already emitted
            if not state:
                logger.debug(f"Result for unknown session {session_id}, ignoring")
            return

        if not decompose_result.success:
            logger.warning(
                f"Wave decomposition failed: session={session_id}, "
                f"turn={turn_index}, error={decompose_result.error}"
            )
            return

        # Use metadata carried through the job (source of truth from workflow/LLM output).
        # Do NOT parse agent/voice from filename because Turn 2/3 names include extra tokens.
        slot_id = job.slot_id
        agent_id = job.agent_id
        voice_profile = job.voice_profile
        tts_basename = job.tts_basename or job.input_path.stem

        meta = SlotMeta(
            slot_id=slot_id,
            agent_id=agent_id,
            voice_profile=voice_profile,
            tts_basename=tts_basename,
        )

        # Update state based on turn
        if turn_index == 1:
            state.turn1_ready[slot_id] = meta
            logger.debug(
                f"Turn 1 slot {slot_id} ready: "
                f"{len(state.turn1_ready)}/{len(state.turn1_expected)}"
            )
        elif turn_index == 2:
            state.turn2_ready[slot_id] = meta
            logger.debug(
                f"Turn 2 slot {slot_id} ready: "
                f"{len(state.turn2_ready)}/{len(state.turn2_expected)}"
            )
        elif turn_index == 3:
            state.turn3_ready[slot_id] = meta
            logger.debug(
                f"Turn 3 slot {slot_id} ready: "
                f"{len(state.turn3_ready)}/{len(state.turn3_expected)}"
            )

        # Check batch readiness (unified check replaces individual checks)
        await self._check_and_emit_batch(session_id)

    # -------------------------------------------------------------------------
    # Internal: Event emission
    # -------------------------------------------------------------------------

    def _compute_target_slots(self, agent_slot_id: int) -> tuple[int, int]:
        """Compute physical target slots for wave1 and wave2.

        wave1 → same slot as agent
        wave2 → next slot (wrapping 6→1)
        """
        wave1_target = agent_slot_id
        wave2_target = (agent_slot_id % 6) + 1
        return wave1_target, wave2_target

    async def _check_and_emit_turn1(self, session_id: str) -> None:
        """Check if Turn 1 event should be emitted and emit if ready."""
        state = self._sessions.get(session_id)
        if not state or state.turn1_emitted:
            return

        if state.is_turn1_complete():
            await self._emit_turn1_event(session_id, partial=False)

    async def _emit_turn1_event(self, session_id: str, partial: bool) -> None:
        """Emit the turn1.waves.ready event."""
        state = self._sessions.get(session_id)
        if not state or state.turn1_emitted:
            return

        state.turn1_emitted = True

        # Cancel timeout if it's running
        task_key = f"{session_id}_turn1"
        if task_key in self._timeout_tasks:
            self._timeout_tasks[task_key].cancel()
            del self._timeout_tasks[task_key]

        # Build slot info list
        slots = []
        for slot_id, meta in sorted(state.turn1_ready.items()):
            wave1_abs, wave1_rel, wave2_abs, wave2_rel = meta.derive_wave_paths(session_id, 1)
            wave1_target, wave2_target = self._compute_target_slots(meta.slot_id)
            slots.append(
                SlotWaveInfo(
                    slotId=meta.slot_id,
                    agentId=meta.agent_id,
                    voiceProfile=meta.voice_profile,
                    wave1PathAbs=wave1_abs,
                    wave1PathRel=wave1_rel,
                    wave1TargetSlotId=wave1_target,
                    wave2PathAbs=wave2_abs,
                    wave2PathRel=wave2_rel,
                    wave2TargetSlotId=wave2_target,
                )
            )

        payload = Turn1WavesPayload(
            status="partial" if partial else "complete",
            slotsExpected=len(state.turn1_expected),
            slotsReady=len(state.turn1_ready),
            slots=slots,
            missingSlotIds=state.get_missing_turn1_slots(),
        )

        event = EventEnvelope.create(
            event_type="turn1.waves.ready",
            session_id=session_id,
            seq=state.next_seq(),
            payload=payload,
        )

        await self._send_event(event)
        logger.info(
            f"Emitted turn1.waves.ready: session={session_id}, "
            f"status={payload.status}, slots={payload.slotsReady}/{payload.slotsExpected}"
        )

    async def _check_and_emit_dialogues(self, session_id: str) -> None:
        """Check if any dialogue events should be emitted and emit them."""
        state = self._sessions.get(session_id)
        if not state or not state.dialogues:
            return

        for dialogue in state.dialogues:
            if dialogue.dialogue_id in state.dialogues_emitted:
                continue

            if state.is_dialogue_ready(dialogue):
                await self._emit_dialogue_event(session_id, dialogue)

    async def _emit_dialogue_event(
        self, session_id: str, dialogue: DialogueSpec
    ) -> None:
        """Emit a dialogue.waves.ready event."""
        state = self._sessions.get(session_id)
        if not state:
            return

        state.dialogues_emitted.add(dialogue.dialogue_id)

        # Build commenters list
        commenters = []
        play_order = []

        for commenter in dialogue.commenters:
            # Get the actual metadata from turn2_ready
            meta = state.turn2_ready.get(commenter.slot_id, commenter)
            wave1_abs, wave1_rel, wave2_abs, wave2_rel = meta.derive_wave_paths(session_id, 2)
            wave1_target, wave2_target = self._compute_target_slots(meta.slot_id)
            commenters.append(
                SlotWaveInfo(
                    slotId=meta.slot_id,
                    agentId=meta.agent_id,
                    voiceProfile=meta.voice_profile,
                    wave1PathAbs=wave1_abs,
                    wave1PathRel=wave1_rel,
                    wave1TargetSlotId=wave1_target,
                    wave2PathAbs=wave2_abs,
                    wave2PathRel=wave2_rel,
                    wave2TargetSlotId=wave2_target,
                )
            )
            play_order.append(PlayOrderItem(role="commenter", slotId=meta.slot_id))

        # Build respondent
        resp_meta = state.turn3_ready.get(
            dialogue.respondent.slot_id, dialogue.respondent
        )
        wave1_abs, wave1_rel, wave2_abs, wave2_rel = resp_meta.derive_wave_paths(session_id, 3)
        wave1_target, wave2_target = self._compute_target_slots(resp_meta.slot_id)
        respondent = SlotWaveInfo(
            slotId=resp_meta.slot_id,
            agentId=resp_meta.agent_id,
            voiceProfile=resp_meta.voice_profile,
            wave1PathAbs=wave1_abs,
            wave1PathRel=wave1_rel,
            wave1TargetSlotId=wave1_target,
            wave2PathAbs=wave2_abs,
            wave2PathRel=wave2_rel,
            wave2TargetSlotId=wave2_target,
        )
        play_order.append(PlayOrderItem(role="respondent", slotId=resp_meta.slot_id))

        payload = DialogueWavesPayload(
            dialogueId=dialogue.dialogue_id,
            targetSlotId=dialogue.target_slot_id,
            commenters=commenters,
            respondent=respondent,
            playOrder=play_order,
        )

        event = EventEnvelope.create(
            event_type="dialogue.waves.ready",
            session_id=session_id,
            seq=state.next_seq(),
            payload=payload,
        )

        await self._send_event(event)
        logger.info(
            f"Emitted dialogue.waves.ready: session={session_id}, "
            f"dialogue={dialogue.dialogue_id}"
        )

    async def _check_and_emit_batch(self, session_id: str) -> None:
        """Check if all waves ready and emit batch of events."""
        state = self._sessions.get(session_id)
        if not state or state.batch_emitted or not state.workflow_complete:
            return

        if not state.is_all_waves_ready():
            return

        await self._emit_batch(session_id, partial=False)

    async def _emit_batch(self, session_id: str, partial: bool) -> None:
        """Emit turn1.waves.ready + all dialogue.waves.ready as batch."""
        state = self._sessions.get(session_id)
        if not state or state.batch_emitted:
            return

        state.batch_emitted = True

        # Cancel workflow timeout
        task_key = f"{session_id}_workflow"
        if task_key in self._timeout_tasks:
            self._timeout_tasks[task_key].cancel()
            del self._timeout_tasks[task_key]

        # 1. Emit Turn 1 event
        await self._emit_turn1_event(session_id, partial)

        # 2. Emit all ready dialogues immediately after
        for dialogue in state.get_ready_dialogues():
            if dialogue.dialogue_id not in state.dialogues_emitted:
                await self._emit_dialogue_event(session_id, dialogue)

        logger.info(
            f"Batch emission complete: session={session_id}, "
            f"partial={partial}, dialogues={len(state.get_ready_dialogues())}"
        )

    async def _send_event(self, event: EventEnvelope) -> None:
        """Send an event to the WebSocket client."""
        async with self._ws_lock:
            if self._ws_client is None:
                logger.debug(f"No WebSocket client, dropping event: {event.type}")
                return

            try:
                if self._ws_client.client_state == WebSocketState.CONNECTED:
                    await self._ws_client.send_text(event.model_dump_json())
                else:
                    logger.warning("WebSocket not connected, dropping event")
            except Exception as e:
                logger.error(f"Error sending WebSocket event: {e}")

    async def emit_user_sentiment(
        self,
        session_id: str,
        sentiment: str,
        justification: str,
    ) -> None:
        """Emit user_sentiment event to TouchDesigner.

        Called early in the workflow (parallel with Turn 1) to enable
        loading effects based on user mood.

        Args:
            session_id: The workflow session UUID
            sentiment: Detected sentiment (positive/neutral/negative)
            justification: Brief explanation of the sentiment
        """
        state = self._sessions.get(session_id)
        if not state:
            logger.warning(f"emit_user_sentiment: Session {session_id} not found")
            return

        payload = UserSentimentPayload(
            sentiment=sentiment,
            justification=justification,
        )

        event = EventEnvelope.create(
            event_type="user_sentiment",
            session_id=session_id,
            seq=state.next_seq(),
            payload=payload,
        )

        await self._send_event(event)
        logger.info(f"Emitted user_sentiment: {session_id}, sentiment={sentiment}")

    # -------------------------------------------------------------------------
    # Internal: Timeout handlers
    # -------------------------------------------------------------------------

    async def _workflow_timeout_handler(self, session_id: str) -> None:
        """Emit partial batch if timeout reached before all ready."""
        try:
            await asyncio.sleep(self._workflow_timeout_s)

            state = self._sessions.get(session_id)
            if state and not state.batch_emitted:
                logger.warning(
                    f"Workflow timeout for {session_id}, emitting partial batch"
                )
                await self._emit_batch(session_id, partial=True)
        except asyncio.CancelledError:
            pass


# -----------------------------------------------------------------------------
# Module-level singleton
# -----------------------------------------------------------------------------

_orchestrator: EventsOrchestrator | None = None


def get_orchestrator() -> EventsOrchestrator:
    """Get or create the events orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        from backend.config import settings

        _orchestrator = EventsOrchestrator(
            turn1_timeout_s=settings.events_turn1_timeout_s,
            dialogue_timeout_s=settings.events_dialogue_timeout_s,
            workflow_timeout_s=settings.events_workflow_timeout_s,
        )
    return _orchestrator


async def startup_events() -> None:
    """Initialize and start the events orchestrator."""
    from backend.config import settings

    if not settings.events_ws_enabled:
        logger.info("Events WebSocket disabled (events_ws_enabled=False)")
        return

    orchestrator = get_orchestrator()
    await orchestrator.start()

    # Wire up the waves worker callback
    from backend.waves.worker import get_worker_pool

    pool = get_worker_pool()
    pool.set_result_callback(orchestrator.notify_result)
    logger.info("Events orchestrator wired to waves worker")


async def shutdown_events() -> None:
    """Shutdown the events orchestrator."""
    global _orchestrator
    if _orchestrator is not None:
        await _orchestrator.stop()
        _orchestrator = None
