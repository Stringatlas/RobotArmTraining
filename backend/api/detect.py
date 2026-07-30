"""
POST /api/detect          — Zero-shot detections with camera-relative 3D coordinates
POST /api/detect/world    — Zero-shot detections with robot-base-frame 3D coordinates

Pipeline:
  1. Fetches a frame (RGB + depth + intrinsics) from the robot service
  2. Runs Grounding DINO zero-shot detection locally on the BGR image
  3. For each detection, computes the 3D camera-relative point using
     depth backprojection
  4. (world variant only) Applies the T_base_camera hand-eye calibration
     to transform camera-relative → robot-base-frame coordinates
"""
from __future__ import annotations

import base64
import logging
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from config import settings
from services.object_detection.detector import detector as dino_detector
from services.object_detection.yolo_service import (
    backproject_to_camera,
    median_depth_at,
)

from services.object_detection.calibration import camera_to_base_point

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/detect", tags=["detect"])

# Prompt used for zero-shot detection. Can be changed at runtime.
_current_prompt: str = "coke can"


def set_prompt(prompt: str) -> None:
    global _current_prompt
    _current_prompt = prompt


class Detection3D(BaseModel):
    """One detected object with its 3D camera-relative position."""

    name: str
    confidence: float
    bbox: dict[str, int]  # x1, y1, x2, y2
    center_px: dict[str, int]  # cx, cy
    depth_m: float | None
    camera_xyz_m: list[float] | None  # [x_cam, y_cam, z_cam]


class DetectionWorld(Detection3D):
    """Camera-relative + robot-base-frame 3D coordinates."""

    base_xyz_m: list[float] | None  # [x_base, y_base, z_base]


class DetectResponse(BaseModel):
    detections: list[Detection3D]
    n_detections: int


class DetectWorldResponse(BaseModel):
    detections: list[DetectionWorld]
    n_detections: int


class SetPromptRequest(BaseModel):
    prompt: str = Field(..., description="Zero-shot detection prompt, e.g. 'bottle' or 'rubber duck'")


async def _fetch_frame() -> tuple[np.ndarray, str, dict[str, Any]]:
    """Fetch a frame from the robot service.

    Returns (bgr_image, depth_b64, camera_info).
    Raises HTTPException on failure.
    """
    import httpx

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

    rgb_b64: str | None = frame_pkg.get("rgb_jpeg_base64")
    depth_b64: str | None = frame_pkg.get("depth_png16_base64")
    camera_info: dict[str, Any] | None = frame_pkg.get("camera_info")

    if not rgb_b64 or not depth_b64 or not camera_info:
        raise HTTPException(503, "Incomplete frame data from robot service")

    # Decode RGB JPEG back to BGR numpy array for the local detector
    rgb_jpeg_bytes = base64.b64decode(rgb_b64)
    nparr = np.frombuffer(rgb_jpeg_bytes, np.uint8)
    bgr_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if bgr_image is None:
        raise HTTPException(503, "Failed to decode RGB JPEG frame")

    return bgr_image, depth_b64, camera_info


def _compute_camera_xyz(
    det: dict[str, Any],
    camera_info: dict[str, Any],
    depth_b64: str,
    depth_scale: float,
) -> tuple[float | None, list[float] | None]:
    """Compute depth_m and camera_xyz for a single detection."""
    cx, cy = det["cx"], det["cy"]
    depth_m = median_depth_at(depth_b64, cx, cy, depth_scale, window=7)
    camera_xyz: list[float] | None = None
    if depth_m is not None and depth_m > 0:
        camera_xyz = backproject_to_camera(camera_info, cx, cy, depth_m)
    return depth_m, camera_xyz


@router.post("/prompt")
async def set_detect_prompt(req: SetPromptRequest):
    """Change the zero-shot detection prompt at runtime."""
    set_prompt(req.prompt)
    logger.info("Detection prompt changed to: %s", req.prompt)
    return {"ok": True, "prompt": req.prompt}


@router.post("", response_model=DetectResponse)
async def detect():
    """Run Grounding DINO detection with camera-relative 3D coordinates.

    Uses the current prompt (set via POST /detect/prompt, defaults to 'object').
    """
    bgr_image, depth_b64, camera_info = await _fetch_frame()
    depth_scale = float(camera_info["depth_scale"])

    # Run local detection
    raw_detections = dino_detector.detect(bgr_image, prompt=_current_prompt)
    if not raw_detections:
        return DetectResponse(detections=[], n_detections=0)

    results: list[Detection3D] = []
    for det in raw_detections:
        depth_m, camera_xyz = _compute_camera_xyz(det, camera_info, depth_b64, depth_scale)
        results.append(Detection3D(
            name=det["name"],
            confidence=det["conf"],
            bbox={"x1": det["x1"], "y1": det["y1"], "x2": det["x2"], "y2": det["y2"]},
            center_px={"cx": det["cx"], "cy": det["cy"]},
            depth_m=depth_m,
            camera_xyz_m=camera_xyz,
        ))

    return DetectResponse(detections=results, n_detections=len(results))


@router.post("/world", response_model=DetectWorldResponse)
async def detect_world():
    """Run Grounding DINO detection with robot-base-frame 3D coordinates.

    Same as POST /detect but additionally transforms each detection's
    camera-relative 3D point into the robot base frame using the
    T_base_camera hand-eye calibration matrix.
    """
    bgr_image, depth_b64, camera_info = await _fetch_frame()
    depth_scale = float(camera_info["depth_scale"])

    raw_detections = dino_detector.detect(bgr_image, prompt=_current_prompt)
    if not raw_detections:
        return DetectWorldResponse(detections=[], n_detections=0)

    results: list[DetectionWorld] = []
    for det in raw_detections:
        depth_m, camera_xyz = _compute_camera_xyz(det, camera_info, depth_b64, depth_scale)

        base_xyz: list[float] | None = None
        if camera_xyz is not None:
            base_xyz = camera_to_base_point(camera_xyz)

        results.append(DetectionWorld(
            name=det["name"],
            confidence=det["conf"],
            bbox={"x1": det["x1"], "y1": det["y1"], "x2": det["x2"], "y2": det["y2"]},
            center_px={"cx": det["cx"], "cy": det["cy"]},
            depth_m=depth_m,
            camera_xyz_m=camera_xyz,
            base_xyz_m=base_xyz,
        ))

    return DetectWorldResponse(detections=results, n_detections=len(results))