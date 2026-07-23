"""
Endpoints for the remote YOLO / Grounding DINO server.

The detection server polls GET /image for raw JPEG frames and pushes
results to POST /detections. These routes are registered directly on
the app (not under /api) to match the YOLO server's expected paths.

Detection results are stored in-memory so the /api/detect endpoints
can read the latest detections and compute 3D coordinates.
"""

from __future__ import annotations

import logging
import time

import httpx
import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["yolo-server"])

# In-memory store for the latest detection results pushed by the YOLO server.
# Structure: {"timestamp": float, "detections": list[dict]}
_latest_detections: dict | None = None
_latest_detection_ts: float = 0.0


def get_latest_detections() -> dict | None:
    """Return the latest detection payload from the YOLO server, or None."""
    return _latest_detections


# ---------------------------------------------------------------------------
# YOLO server → backend
# ---------------------------------------------------------------------------

@router.get("/image")
async def get_image():
    """Raw JPEG frame for the remote detection server.

    The YOLO server polls this endpoint to get the latest camera frame.
    Returns raw JPEG bytes (not base64) with an X-Timestamp header.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(settings.camera_single_frame_url)
            resp.raise_for_status()
            frame_pkg = resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch frame from robot service: {exc}",
        )

    import base64
    rgb_b64: str | None = frame_pkg.get("rgb_jpeg_base64")
    if not rgb_b64:
        raise HTTPException(503, "No RGB frame available from robot service")

    jpeg_bytes = base64.b64decode(rgb_b64)
    ts = time.time()

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={"X-Timestamp": str(ts)},
    )


class DetectionResult(BaseModel):
    """A single detection from the YOLO server."""
    class_id: int | None = None
    label: str
    confidence: float
    xmin: float
    ymin: float
    xmax: float
    ymax: float


class DetectionsPayload(BaseModel):
    """Payload posted by the YOLO server to /detections."""
    timestamp: float | None = None
    detections: list[DetectionResult]


@router.post("/detections")
async def post_detections(payload: DetectionsPayload):
    """Receive detection results from the remote YOLO server.

    Stores the latest detections in memory for the /api/detect endpoints
    to consume when computing 3D world coordinates.
    """
    global _latest_detections, _latest_detection_ts

    ts = payload.timestamp if payload.timestamp is not None else time.time()
    _latest_detections = {
        "timestamp": ts,
        "detections": [d.model_dump() for d in payload.detections],
    }
    _latest_detection_ts = ts

    logger.info(
        "Received %d detection(s) from YOLO server (ts=%.3f)",
        len(payload.detections), ts,
    )

    return {"ok": True, "n_detections": len(payload.detections)}