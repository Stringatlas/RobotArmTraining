"""Tests for POST /api/detect/world using mock data from output.json.

Strategy:
  - Mock the HTTP call to the robot's camera/frame endpoint so we serve
    the real RGB + depth + intrinsics from backend/services/object_detection/output.json.
  - Mock the Grounding DINO detector so we don't need the model loaded.
  - Mock the hand-eye calibration transform so we don't need T_base_camera.npy.
  - This lets us exercise the full pipeline: frame fetch → depth backprojection
    → camera-relative 3D → base-frame transform, without any real hardware.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

# ── Patch config BEFORE importing the app ──────────────────────────────────
# Point the camera URL to a dummy (we'll mock the HTTP call anyway).
# The real T_base_camera.npy calibration file exists and will be used.
with patch("config.settings") as mock_settings:
    mock_settings.camera_single_frame_url = "http://mock/camera/frame"
    mock_settings.t_base_camera_path = str(
        Path(__file__).resolve().parents[1] / "services" / "object_detection" / "T_base_camera.npy"
    )

    from main import app
    from api.detect import router as detect_router
    from services.object_detection.detector import detector as dino_detector
    from services.object_detection.calibration import camera_to_base_point

client = TestClient(app)

# ── Load the mock frame data ───────────────────────────────────────────────
_OUTPUT_JSON = Path(__file__).resolve().parents[1] / "services" / "object_detection" / "output.json"
with open(_OUTPUT_JSON) as f:
    MOCK_FRAME = json.load(f)


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _mock_httpx_get():
    """Mock the HTTP GET to the robot's camera/frame endpoint.

    Returns the real RGB JPEG, depth PNG16, and camera intrinsics from
    output.json so the depth backprojection code runs on real data.
    """
    mock_resp = MagicMock()
    mock_resp.json.return_value = MOCK_FRAME
    mock_resp.raise_for_status.return_value = None

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp
        yield mock_get


@pytest.fixture(autouse=True)
def _mock_detector():
    """Mock the Grounding DINO detector to return a known detection.

    The detection center (cx, cy) is chosen to fall on a valid-depth region
    of the real depth map so that median_depth_at returns a real depth value.
    """
    mock_detections = [
        {
            "name": "test_object",
            "conf": 0.95,
            "x1": 200, "y1": 150, "x2": 300, "y2": 250,
            "cx": 250, "cy": 200,
        },
    ]

    with patch.object(dino_detector, "detect", return_value=mock_detections):
        yield


# ── Tests ──────────────────────────────────────────────────────────────────

class TestDetectWorld:
    """Integration-style tests for POST /api/detect/world."""

    def test_detect_world_returns_valid_structure(self):
        """The endpoint returns a 200 with the expected response model."""
        resp = client.post("/api/detect/world")
        assert resp.status_code == 200, resp.text

        body = resp.json()
        assert "detections" in body
        assert "n_detections" in body
        assert body["n_detections"] == 1
        assert len(body["detections"]) == 1

    def test_detect_world_includes_camera_xyz(self):
        """Each detection should have a camera_xyz_m computed from depth."""
        resp = client.post("/api/detect/world")
        assert resp.status_code == 200
        det = resp.json()["detections"][0]

        assert det["depth_m"] is not None
        assert det["depth_m"] > 0
        assert det["camera_xyz_m"] is not None
        assert len(det["camera_xyz_m"]) == 3

    def test_detect_world_includes_base_xyz(self):
        """Each detection should have a base_xyz_m from the real T_base_camera.npy."""
        resp = client.post("/api/detect/world")
        assert resp.status_code == 200
        det = resp.json()["detections"][0]

        assert det["base_xyz_m"] is not None
        assert len(det["base_xyz_m"]) == 3

        # The real calibration transforms camera → base frame coordinates.
        # We can't predict exact values, but the transform should change the point.
        cam = det["camera_xyz_m"]
        base = det["base_xyz_m"]
        # At minimum, the transform should produce a different point than camera-space
        assert base != cam

    def test_detect_world_bbox_and_center(self):
        """Bounding box and center pixel should match the mock detection."""
        resp = client.post("/api/detect/world")
        assert resp.status_code == 200
        det = resp.json()["detections"][0]

        assert det["name"] == "test_object"
        assert det["confidence"] == 0.95
        assert det["bbox"] == {"x1": 200, "y1": 150, "x2": 300, "y2": 250}
        assert det["center_px"] == {"cx": 250, "cy": 200}

    def test_detect_world_no_detections(self):
        """When the detector returns nothing, the response should be empty."""
        with patch.object(dino_detector, "detect", return_value=[]):
            resp = client.post("/api/detect/world")
        assert resp.status_code == 200
        body = resp.json()
        assert body["n_detections"] == 0
        assert body["detections"] == []

    def test_detect_world_http_failure(self):
        """When the robot service is unreachable, return 502."""
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            resp = client.post("/api/detect/world")
        assert resp.status_code == 502

    def test_detect_world_incomplete_frame(self):
        """When the frame data is missing fields, return 503."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"rgb_jpeg_base64": None}
        mock_resp.raise_for_status.return_value = None

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_resp
            resp = client.post("/api/detect/world")
        assert resp.status_code == 503

    def test_detect_world_calibration_failure(self):
        """When camera_to_base_point returns None, base_xyz_m should be None."""
        with patch(
            "api.detect.camera_to_base_point",
            return_value=None,
        ):
            resp = client.post("/api/detect/world")
        assert resp.status_code == 200
        det = resp.json()["detections"][0]
        assert det["base_xyz_m"] is None
        # Camera-relative data should still be present
        assert det["camera_xyz_m"] is not None
        assert det["depth_m"] is not None