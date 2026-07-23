"""Hand-eye calibration: camera-frame → robot-base-frame transform.

Loads the 4×4 transformation matrix T_base_camera from a .npy file
(calibrated by fit_camera_to_base.py) and provides a function to
transform 3D points from camera coordinates to robot base coordinates.
"""

from __future__ import annotations

import logging
import os

import numpy as np

from config import settings

logger = logging.getLogger(__name__)

# Lazily loaded 4×4 camera→base transform
_T_base_camera: np.ndarray | None = None


def load_t_base_camera() -> np.ndarray:
    """Load and cache the hand-eye calibration matrix.

    Returns:
        4×4 homogeneous transformation matrix (numpy float64).

    Raises:
        FileNotFoundError: if the .npy file doesn't exist.
    """
    global _T_base_camera
    if _T_base_camera is None:
        path = settings.t_base_camera_path
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"T_base_camera.npy not found at {path}. "
                "Run hand-eye calibration (fit_camera_to_base.py) first."
            )
        mat = np.load(path)
        logger.info("Loaded T_base_camera from %s (shape=%s)", path, mat.shape)
        _T_base_camera = mat
    # Satisfy the type checker: _T_base_camera was just assigned above if it was None.
    assert _T_base_camera is not None
    return _T_base_camera


def camera_to_base_point(xyz_camera: list[float]) -> list[float] | None:
    """Transform a 3D point from camera frame to robot base frame.

    Args:
        xyz_camera: [x_cam, y_cam, z_cam] in meters.

    Returns:
        [x_base, y_base, z_base] in meters, or None if calibration
        matrix is unavailable (file not found).
    """
    try:
        T = load_t_base_camera()
    except FileNotFoundError:
        logger.warning("T_base_camera not loaded — cannot compute base-frame coordinates")
        return None

    p_cam = np.array([xyz_camera[0], xyz_camera[1], xyz_camera[2], 1.0], dtype=np.float64)
    p_base = T @ p_cam
    return [float(p_base[0]), float(p_base[1]), float(p_base[2])]