"""Mock robot FastAPI server.

Provides fake telemetry and camera data streams for development/testing
without a physical robot. Matches the wire protocol expected by
backend/services/telemetry/robot_client.py and camera_client.py.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Load the canned camera frame
# ---------------------------------------------------------------------------
with open(HERE / "camera_frame.json") as f:
    _CAMERA_FRAME_DATA = json.load(f)

RGB_JPEG_BYTES = base64.b64decode(_CAMERA_FRAME_DATA["rgb_jpeg_base64"])
DEPTH_PNG16_BYTES = base64.b64decode(_CAMERA_FRAME_DATA["depth_png16_base64"])
CAMERA_INFO = _CAMERA_FRAME_DATA["camera_info"]

# ---------------------------------------------------------------------------
# Mock robot state
# ---------------------------------------------------------------------------
MOCK_JOINT_POS = [0.00, -1.00, 2.40, -1.40, 1.57, 0.00]
MOCK_TCP_POSE = {"x": -0.438, "y": -0.121, "z": 0.097, "rx": 1.571, "ry": 0.000, "rz": -1.570}
MOCK_GRIPPER = {"force": 0.0, "amplitude": 0.0, "weight": 0.0, "hold_on": False}

app = FastAPI(title="Mock Robot Server")


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock_robot"}

@app.get("/state")
async def get_state():
    return {"state": "idle"}

@app.get("/camera/frame")
async def get_camera_frame():
    """Return a single camera frame as a multipart-like JSON blob.

    The real robot may serve this differently, but for testing we return
    the base64-encoded data so the client can decode as needed.
    """
    return {
        "rgb_jpeg_base64": _CAMERA_FRAME_DATA["rgb_jpeg_base64"],
        "depth_png16_base64": _CAMERA_FRAME_DATA["depth_png16_base64"],
        "camera_info": CAMERA_INFO,
    }


# ---------------------------------------------------------------------------
# WebSocket: robot telemetry
# ---------------------------------------------------------------------------
@app.websocket("/telemetry/ws/robot")
async def robot_telemetry_ws(ws: WebSocket):
    await ws.accept()
    logger.info("Robot telemetry WS connected")
    try:
        while True:
            sample = {
                "joint_pos": MOCK_JOINT_POS,
                "tcp_pose": MOCK_TCP_POSE,
                "gripper_status": MOCK_GRIPPER,
                "state": "running",
                "ts": time.time(),
            }
            await ws.send_json(sample)
            await asyncio.sleep(0.1)  # 10 Hz
    except WebSocketDisconnect:
        logger.info("Robot telemetry WS disconnected")


# ---------------------------------------------------------------------------
# WebSocket: camera frames (3-part message protocol)
# ---------------------------------------------------------------------------
@app.websocket("/telemetry/ws/frames")
async def camera_frames_ws(ws: WebSocket):
    await ws.accept()
    logger.info("Camera frames WS connected")
    try:
        while True:
            # Part 1: JSON text header
            header = json.dumps({"type": "rgbd_frame", "ts": time.time()})
            await ws.send_text(header)

            # Part 2: RGB JPEG binary
            await ws.send_bytes(RGB_JPEG_BYTES)

            # Part 3: Depth PNG16 binary
            await ws.send_bytes(DEPTH_PNG16_BYTES)

            await asyncio.sleep(0.1)  # 10 Hz
    except WebSocketDisconnect:
        logger.info("Camera frames WS disconnected")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)