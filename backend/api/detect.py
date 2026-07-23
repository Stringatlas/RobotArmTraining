"""
POST /detect          — YOLO detections with camera-relative 3D coordinates
POST /detect/world    — YOLO detections with robot-base-frame 3D coordinates

Pipeline:
  1. Fetches a frame (RGB + depth + intrinsics) from the robot service
  2. Sends the RGB JPEG to the remote YOLO server for object detection
  3. For each detection, computes the 3D camera-relative point using
     depth backprojection
  4. (world variant only) Applies the T_base_camera hand-eye calibration
     to transform camera-relative → robot-base-frame coordinates
"""
import base64
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import settings
from services.object_detection.yolo_service import (
    detect_on_frame,
    backproject_to_camera,
    median_depth_at,
)
from services.object_detection.calibration import camera_to_base_point

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/detect", tags=["detect"])


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


async def _run_detection_pipeline() -> tuple[list[dict], dict, str]:
    """Shared pipeline: fetch frame → YOLO detect.

    Returns (raw_detections, camera_info, depth_b64).
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
    camera_info: dict | None = frame_pkg.get("camera_info")

    if not rgb_b64 or not depth_b64 or not camera_info:
        raise HTTPException(503, "Incomplete frame data from robot service")

    rgb_jpeg_bytes = base64.b64decode(rgb_b64)
    raw_detections = await detect_on_frame(rgb_jpeg_bytes)
    return raw_detections, camera_info, depth_b64


def _compute_camera_xyz(
    det: dict, camera_info: dict, depth_b64: str, depth_scale: float
) -> tuple[float | None, list[float] | None]:
    """Compute depth_m and camera_xyz for a single detection."""
    cx, cy = det["cx"], det["cy"]
    depth_m = median_depth_at(depth_b64, cx, cy, depth_scale, window=7)
    camera_xyz: list[float] | None = None
    if depth_m is not None and depth_m > 0:
        camera_xyz = backproject_to_camera(camera_info, cx, cy, depth_m)
    return depth_m, camera_xyz


@router.post("", response_model=DetectResponse)
async def detect():
    """YOLO detections with camera-relative 3D coordinates.

    Returns all detected objects with their 3D position in the camera
    coordinate frame.  Use POST /detect/world to get robot-base-frame
    coordinates instead.
    """
    raw_detections, camera_info, depth_b64 = await _run_detection_pipeline()
    depth_scale = float(camera_info["depth_scale"])
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
    """YOLO detections with robot-base-frame 3D coordinates.

    Same as POST /detect but additionally transforms each detection's
    camera-relative 3D point into the robot base frame using the
    T_base_camera hand-eye calibration matrix.

    Returns all detected objects with both camera-relative and
    base-frame 3D coordinates.
    """
    raw_detections, camera_info, depth_b64 = await _run_detection_pipeline()
    depth_scale = float(camera_info["depth_scale"])
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
