"""WebSocket endpoint for TouchDesigner events."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.events.models import HelloAckMessage
from backend.events.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/v1/events")
async def events_websocket(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for TouchDesigner to receive wave-mix ready events.

    Single-client policy: If a new client connects, the previous one is disconnected.

    Optional client messages:
    - {"type": "hello", "client": "touchdesigner", "version": "..."} -> receives hello.ack

    Server events:
    - turn1.waves.ready: Emitted when Turn 1 wave-mix files are ready
    - dialogue.waves.ready: Emitted per dialogue when Turn 2+3 wave-mix files are ready
    """
    await websocket.accept()
    logger.info(f"WebSocket connection accepted from {websocket.client}")

    orchestrator = get_orchestrator()
    await orchestrator.set_client(websocket)

    try:
        while True:
            # Handle optional client messages
            data = await websocket.receive_text()

            try:
                msg = json.loads(data)
                msg_type = msg.get("type")

                if msg_type == "hello":
                    # Respond with hello.ack
                    ack = HelloAckMessage()
                    await websocket.send_text(ack.model_dump_json())
                    logger.info(
                        f"Received hello from {msg.get('client', 'unknown')}, "
                        f"sent hello.ack"
                    )
                else:
                    logger.debug(f"Received unknown message type: {msg_type}")

            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON: {data[:100]}")

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await orchestrator.remove_client()
