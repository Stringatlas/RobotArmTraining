"""Async client for the remote YOLO detection server.

Follows the same pattern as the `yolo_detector.py` in `robot_vision/clean/`:
posts a JPEG frame to the remote server and polls for detections.

The remote YOLO server runs at YOLO_SERVER_URL (default http://192.168.10.201:8000)
and exposes:
  - POST /upload_image  — upload a JPEG frame
  - GET  /detections    — retrieve latest detections

Detection format (per object): {name, conf, xmin, ymin, xmax, ymax}
This service normalizes to: {name, conf, x1, y1, x2, y2, cx, cy}
"""
import asyncio
import logging
import time

import cv2
import numpy as np
import httpx

logger = logging.getLogger(__name__)
from config import settings


def _normalize_detections(remote: dict | None) -> list[dict]:
    """Convert remote server detection format to normalized list."""
    out: list[dict] = []
    if not remote:
        return out
    for d in (remote.get("detections") or []):
        try:
            x1 = int(round(d.get("xmin", 0)))
            y1 = int(round(d.get("ymin", 0)))
            x2 = int(round(d.get("xmax", 0)))
            y2 = int(round(d.get("ymax", 0)))
            out.append({
                "name": d.get("label") or "object",
                "conf": float(d.get("confidence", 0.0)),
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "cx": int((x1 + x2) / 2),
                "cy": int((y1 + y2) / 2),
            })
        except Exception:
            continue
    return out


async def detect_on_frame(
    rgb_jpeg_bytes: bytes,
    *,
    server_url: str = settings.yolo_server_url,
    poll_sec: float = settings.yolo_poll_sec,
    timeout_sec: float = settings.yolo_timeout_sec,
) -> list[dict]:
    """Post a JPEG frame to the remote YOLO server and poll for detections.

    Args:
        rgb_jpeg_bytes: JPEG-encoded RGB image bytes.
        server_url: Base URL of the remote YOLO server.
        poll_sec: Seconds between detection polls.
        timeout_sec: Max seconds to wait for a detection result.

    Returns:
        List of detection dicts with keys:
          name, conf, x1, y1, x2, y2, cx, cy
        Empty list if no detections or server unavailable.
    """
    upload_url = server_url.rstrip("/") + "/upload_image"
    detect_url = server_url.rstrip("/") + "/detections"

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Upload the frame
        try:
            files = {"file": ("frame.jpg", rgb_jpeg_bytes, "image/jpeg")}
            resp = await client.post(upload_url, files=files)
            resp.raise_for_status()
            post_ts = float(resp.json().get("ts", time.time()))
        except Exception as exc:
            logger.warning("YOLO upload failed: %s", exc)
            return []

        # Poll for detections matching our upload timestamp
        start = time.time()
        while time.time() - start < timeout_sec:
            try:
                resp = await client.get(detect_url)
                resp.raise_for_status()
                remote = resp.json()
                rts = float(remote.get("timestamp", 0.0))
                if rts >= post_ts - 10.0:
                    return _normalize_detections(remote)
            except Exception:
                pass
            await asyncio.sleep(poll_sec)

        logger.warning("YOLO detection timed out after %.1fs", timeout_sec)
        return []


def backproject_to_camera(intr: dict, u: int, v: int, depth_m: float) -> list[float] | None:
    """Deproject a pixel + depth to 3D camera-frame coordinates.

    Uses the pinhole camera model with intrinsics.

    Args:
        intr: Camera intrinsics dict with keys fx, fy, ppx, ppy.
        u, v: Pixel coordinates.
        depth_m: Depth at the pixel in meters.

    Returns:
        [x_cam, y_cam, z_cam] in meters, or None if invalid.
    """
    if depth_m <= 0:
        return None

    fx = float(intr["fx"])
    fy = float(intr["fy"])
    ppx = float(intr["ppx"])
    ppy = float(intr["ppy"])

    x_cam = (u - ppx) * depth_m / fx
    y_cam = (v - ppy) * depth_m / fy
    z_cam = depth_m

    return [x_cam, y_cam, z_cam]


def median_depth_at(
    depth_png16: str | bytes,
    u: int,
    v: int,
    depth_scale: float,
    window: int = 7,
) -> float | None:
    """Extract median depth (meters) at a pixel from a PNG16-encoded depth map.

    Args:
        depth_png16: PNG-encoded 16-bit depth image — either base64 string or raw bytes.
        u, v: Pixel coordinates.
        depth_scale: Depth scale factor (meters per raw unit).
        window: Half-size of the median filter window.

    Returns:
        Depth in meters, or None if the pixel region is invalid.
    """
    import base64

    # Decode PNG16 to raw bytes if it's a base64 string (JSON transport)
    raw: bytes
    if isinstance(depth_png16, str):
        raw = base64.b64decode(depth_png16)
    else:
        raw = depth_png16

    nparr = np.frombuffer(raw, np.uint8)
    depth_img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
    if depth_img is None:
        return None

    h, w = depth_img.shape
    x1 = max(int(u) - window, 0)
    x2 = min(int(u) + window + 1, w)
    y1 = max(int(v) - window, 0)
    y2 = min(int(v) + window + 1, h)

    patch = depth_img[y1:y2, x1:x2]
    valid = patch[patch > 0]
    if valid.size == 0:
        return None

    return float(np.median(valid)) * float(depth_scale)