"""Thin async client for the robot-side FastAPI service.

This module owns the connection to the robot's /telemetry/ws and
get_joint_angles / follow_trajectory REST calls. For the live-relay
slice, only the telemetry side is wired up: connect, parse each raw
sample, and hand it to whoever has subscribed (currently just
ws_telemetry.py's frontend broadcaster).

Buffering raw samples for post-episode resampling is NOT done here —
that's a separate concern for episode_runner.py to add later by
subscribing its own callback alongside the frontend relay.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

import websockets
from websockets.exceptions import ConnectionClosed
from models.pose import TelemetrySample

logger = logging.getLogger(__name__)

TelemetryCallback = Callable[[TelemetrySample], Awaitable[None]]


class RobotClient:
    """Owns the single connection to the robot's telemetry stream.

    Multiple consumers (frontend relay, future buffering) subscribe via
    `subscribe()` rather than each opening their own connection to the
    robot — see the earlier discussion on why we don't want two
    independent consumers of that stream.
    """

    def __init__(self, telemetry_url: str, *, reconnect_delay_s: float = 2.0):
        self._telemetry_url = telemetry_url
        self._reconnect_delay_s = reconnect_delay_s
        self._subscribers: list[TelemetryCallback] = []
        self._task: asyncio.Task | None = None
        self._running = False

    def subscribe(self, callback: TelemetryCallback) -> None:
        """Register a callback invoked with each TelemetrySample as it arrives."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: TelemetryCallback) -> None:
        if callback in self._subscribers:
            self._subscribers.remove(callback)

    def start(self) -> None:
        """Begin the background connect/consume loop. Call once at app startup."""
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
        """Reconnect loop. The robot service can be restarted independently
        of the backend, so a dropped connection is expected, not fatal."""
        while self._running:
            try:
                await self._consume_once()
            except ConnectionClosed:
                logger.warning("Robot telemetry WS closed, reconnecting in %.1fs", self._reconnect_delay_s)
            except OSError as e:
                logger.warning("Robot telemetry WS connect failed (%s), retrying in %.1fs", e, self._reconnect_delay_s)
            except Exception:
                logger.exception("Unexpected error in robot telemetry consumer")

            if self._running:
                await asyncio.sleep(self._reconnect_delay_s)

    async def _consume_once(self) -> None:
        async with websockets.connect(self._telemetry_url) as ws:
            logger.info("Connected to robot telemetry at %s", self._telemetry_url)
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                    sample = TelemetrySample.from_wire(msg)
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    logger.warning("Malformed telemetry message, skipping: %s", e)
                    continue

                await self._dispatch(sample)

    async def _dispatch(self, sample: TelemetrySample) -> None:
        for callback in list(self._subscribers):
            try:
                await callback(sample)
            except Exception:
                # One bad subscriber (e.g. a frontend socket mid-disconnect)
                # shouldn't kill telemetry consumption for everyone else.
                logger.exception("Telemetry subscriber callback raised")