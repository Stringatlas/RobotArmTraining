"""WS endpoint: backend -> frontend live telemetry relay.

Frontend clients connect here to drive the live digital twin. This
module does not talk to the robot directly — it subscribes to the
shared RobotClient instance (see services/robot_client.py) and
rebroadcasts each sample to every connected frontend socket.

Single subscriber-list design here mirrors RobotClient's: one source
of truth (the robot connection) fanned out to N frontend consumers,
rather than N frontend sockets each independently hitting the robot.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from models.pose import TelemetrySample
from services.robot_client import RobotClient

logger = logging.getLogger(__name__)
router = APIRouter()


class TelemetryBroadcaster:
    """Holds the set of connected frontend WS clients and pushes samples to them."""

    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add_client(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def remove_client(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def on_sample(self, sample: TelemetrySample) -> None:
        """Callback registered with RobotClient.subscribe(); fired per sample."""
        if not self._clients:
            return  # no one watching, skip serialization work

        payload = sample.to_dict()
        dead: list[WebSocket] = []

        async with self._lock:
            clients = list(self._clients)

        for client in clients:
            try:
                await client.send_json(payload)
            except Exception:
                dead.append(client)

        if dead:
            async with self._lock:
                for client in dead:
                    self._clients.discard(client)


# Module-level singleton wired up in main.py's startup:
#   broadcaster = TelemetryBroadcaster()
#   robot_client.subscribe(broadcaster.on_sample)
broadcaster = TelemetryBroadcaster()


def get_robot_client(request) -> RobotClient:
    """Placeholder accessor — replace with however app state is wired in main.py,
    e.g. `request.app.state.robot_client`."""
    return request.app.state.robot_client


@router.websocket("/telemetry/ws/robot")
async def telemetry_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    await broadcaster.add_client(websocket)
    logger.info("Frontend telemetry client connected (%d total)", len(broadcaster._clients))

    try:
        while True:
            # Frontend doesn't need to send anything for a pure relay, but
            # we still need to await something to detect disconnects promptly.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await broadcaster.remove_client(websocket)
        logger.info("Frontend telemetry client disconnected (%d total)", len(broadcaster._clients))


# ---------------------------------------------------------------------------
# Camera frame relay — robot's RGB-D stream → frontend (RGB JPEG only)
# ---------------------------------------------------------------------------

class CameraBroadcaster:
    """Holds connected frontend WS clients and pushes camera frames to them.

    Each frame is sent as a JSON text message with frame metadata, followed
    by a binary message containing the RGB JPEG bytes.
    """

    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def add_client(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def remove_client(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def on_frame(self, meta: dict, rgb_jpeg: bytes) -> None:
        """Callback registered with CameraFrameClient.subscribe(); fired per frame."""
        if not self._clients:
            return

        dead: list[WebSocket] = []

        async with self._lock:
            clients = list(self._clients)

        for client in clients:
            try:
                await client.send_json(meta)
                await client.send_bytes(rgb_jpeg)
            except Exception:
                dead.append(client)

        if dead:
            async with self._lock:
                for client in dead:
                    self._clients.discard(client)


camera_broadcaster = CameraBroadcaster()


@router.websocket("/telemetry/ws/camera")
async def camera_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    await camera_broadcaster.add_client(websocket)
    logger.info("Camera client connected (%d total)", len(camera_broadcaster._clients))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await camera_broadcaster.remove_client(websocket)
        logger.info("Camera client disconnected (%d total)", len(camera_broadcaster._clients))
