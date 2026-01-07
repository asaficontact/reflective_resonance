"""TouchDesigner events WebSocket module.

This module provides real-time notifications to TouchDesigner when
wave decomposition files become available.

Usage:
    from backend.events import get_orchestrator, startup_events, shutdown_events

    # In workflow.py
    orchestrator = get_orchestrator()
    orchestrator.begin_session(session_id, slot_metas)
    orchestrator.turn1_complete(session_id)
    orchestrator.turn3_complete(session_id, dialogues)
"""

from backend.events.models import (
    DialogueWavesPayload,
    EventEnvelope,
    HelloAckMessage,
    HelloMessage,
    PlayOrderItem,
    SlotWaveInfo,
    Turn1WavesPayload,
)
from backend.events.orchestrator import (
    EventsOrchestrator,
    get_orchestrator,
    shutdown_events,
    startup_events,
)
from backend.events.state import DialogueSpec, SessionEventsState, SlotMeta
from backend.events.websocket import router as events_router

__all__ = [
    # Orchestrator
    "EventsOrchestrator",
    "get_orchestrator",
    "startup_events",
    "shutdown_events",
    # State
    "SlotMeta",
    "DialogueSpec",
    "SessionEventsState",
    # Models
    "EventEnvelope",
    "SlotWaveInfo",
    "Turn1WavesPayload",
    "DialogueWavesPayload",
    "PlayOrderItem",
    "HelloMessage",
    "HelloAckMessage",
    # Router
    "events_router",
]
