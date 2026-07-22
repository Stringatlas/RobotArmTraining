"""Async client for the robot's RGB-D frame WebSocket stream.

Connects to the robot's /telemetry/ws/frames endpoint, which sends
3-part messages per frame:
  1. JSON text: {"type": "rgbd_frame", "ts": <float>}
  2. Binary: RGB JPEG bytes
  3. Binary: Depth PNG16 bytes

This module extracts only the RGB JPEG and forwards it (frame header +
binary jpeg) to the CameraBroadcaster for frontend consumption.
"""

from __future__ import annotations

import asyncio
import json
import logging

from collections.abc import Awaitable, Callable

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

FrameCallback = Callable[[dict, bytes], Awaitable[None]]


class CameraFrameClient:
    """Owns the single connection to the robot's RGB-D frame stream.
    
    Decodes each 3-part frame, discards depth, and forwards
    (frame_meta_dict, rgb_jpeg_bytes) to subscribed callbacks.
    """

    def __init__(
        self,
        frames_url: str,
        *,
        reconnect_delay_s: float = 2.0,
    ):
        self._frames_url = frames_url
        self._reconnect_delay_s = reconnect_delay_s
        self._callbacks: list[FrameCallback] = []
        self._task: asyncio.Task | None = None
        self._running = False

    def subscribe(self, callback: FrameCallback) -> None:
        self._callbacks.append(callback)

    def unsubscribe(self, callback: FrameCallback) -> None:
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run_forever(self) -> None:
        while self._running:
            try:
                await self._consume_once()
            except ConnectionClosed:
                logger.warning(
                    "Camera frames WS closed, reconnecting in %.1fs",
                    self._reconnect_delay_s,
                )
            except OSError as e:
                logger.warning(
                    "Camera frames WS connect failed (%s), retrying in %.1fs",
                    e,
                    self._reconnect_delay_s,
                )
            except Exception:
                logger.exception("Unexpected error in camera frame consumer")

            if self._running:
                await asyncio.sleep(self._reconnect_delay_s)

    async def _consume_once(self) -> None:
        async with websockets.connect(self._frames_url) as ws:
            logger.info("Connected to camera frames at %s", self._frames_url)
            async for raw in ws:
                # The frames endpoint sends: text (JSON header), binary (rgb), binary (depth)
                # `raw` is the first message (text JSON). After receiving it,
                # we need to read the two subsequent binary messages.
                if isinstance(raw, str):
                    try:
                        meta = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.warning("Malformed frame header, skipping")
                        continue

                    # Read the two binary frames that follow
                    try:
                        rgb_jpeg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                        _depth_png16 = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    except asyncio.TimeoutError:
                        logger.warning("Timeout waiting for frame binary data, skipping")
                        continue
                    except ConnectionClosed:
                        logger.warning("Connection closed mid-frame")
                        break

                    if isinstance(rgb_jpeg, bytes):
                        await self._dispatch(meta, rgb_jpeg)
                # If raw is binary, it means we're mid-frame — skip (protocol mismatch)

    async def _dispatch(self, meta: dict, rgb_jpeg: bytes) -> None:
        for callback in list(self._callbacks):
            try:
                await callback(meta, rgb_jpeg)
            except Exception:
                logger.exception("Camera frame subscriber callback raised")