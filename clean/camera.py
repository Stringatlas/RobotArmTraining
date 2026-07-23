"""
RealSense camera capture + frame transforms, encapsulated in a Camera class.

Owns the pipeline, the cross-thread frame buffers (guarded by a lock), and the
camera->base calibration. The background capture loop and the Flask request
handlers all talk to the SAME Camera instance, so the shared state lives in one
place instead of as module globals.
"""

import os
import threading
import time

import numpy as np
import cv2
import pyrealsense2 as rs

from pose_calculation import normalize


class Camera:
    def __init__(self, t_path, width, height, fps, depth_window, patch_window):
        self.width = width
        self.height = height
        self.fps = fps
        self.depth_window = depth_window
        self.patch_window = patch_window

        # RealSense pipeline
        self.pipeline = rs.pipeline()
        self.config = rs.config()
        self.config.enable_stream(rs.stream.depth, width, height, rs.format.z16, fps)
        self.config.enable_stream(rs.stream.color, width, height, rs.format.bgr8, fps)
        self.align = rs.align(rs.stream.color)

        # Cross-thread frame buffers
        self.lock = threading.Lock()
        self.latest_color = None
        self.latest_depth = None
        self.latest_intr = None
        self.latest_depth_scale = None
        self.latest_color_bgr = None

        # Camera->base calibration
        if not os.path.exists(t_path):
            raise FileNotFoundError(f"{t_path} not found. Run fit_camera_to_base.py first.")
        self.T_base_camera = np.load(t_path)

        self._thread = None

    # ----- Lifecycle -----
    def start(self, background=True):
        """Start the RealSense pipeline and (optionally) the capture thread."""
        self.pipeline.start(self.config)
        if background:
            self._thread = threading.Thread(target=self._frame_loop, daemon=True)
            self._thread.start()

    def stop(self):
        self.pipeline.stop()

    def _frame_loop(self):
        """Continuously capture frames from RealSense into the latest_* buffers."""
        while True:
            frames = self.pipeline.poll_for_frames()
            if not frames:
                frames = self.pipeline.wait_for_frames()
            aligned = self.align.process(frames)

            depth_frame = aligned.get_depth_frame()
            color_frame = aligned.get_color_frame()
            if not depth_frame or not color_frame:
                continue

            color = np.asanyarray(color_frame.get_data())
            depth = np.asanyarray(depth_frame.get_data())
            intr = depth_frame.profile.as_video_stream_profile().intrinsics
            depth_scale = depth_frame.get_units()

            with self.lock:
                self.latest_color = color
                self.latest_color_bgr = color
                self.latest_depth = depth
                self.latest_intr = intr
                self.latest_depth_scale = depth_scale

    def snapshot(self):
        """Return (depth_copy, intr, depth_scale) under lock, or None if not ready."""
        with self.lock:
            if (self.latest_depth is None or self.latest_intr is None
                    or self.latest_depth_scale is None):
                return None
            return self.latest_depth.copy(), self.latest_intr, self.latest_depth_scale

    def latest_color_copy(self):
        """Return a copy of the latest color frame (BGR), or None."""
        with self.lock:
            if self.latest_color_bgr is not None:
                return self.latest_color_bgr.copy()
            if self.latest_color is not None:
                return self.latest_color.copy()
            return None

    # ----- Frame transforms -----
    def median_depth_m(self, depth_image, u, v, depth_scale, window=None):
        """Get median depth (m) around a pixel."""
        if window is None:
            window = self.depth_window
        h, w = depth_image.shape
        x1 = max(int(u) - window, 0)
        x2 = min(int(u) + window + 1, w)
        y1 = max(int(v) - window, 0)
        y2 = min(int(v) + window + 1, h)

        patch = depth_image[y1:y2, x1:x2]
        valid = patch[patch > 0]
        if valid.size == 0:
            return None
        return float(np.median(valid)) * float(depth_scale)

    @staticmethod
    def backproject_pixel(intr, u, v, depth_m):
        """Deproject pixel to 3D point in camera frame."""
        x_cam, y_cam, z_cam = rs.rs2_deproject_pixel_to_point(
            intr, [float(u), float(v)], float(depth_m))
        return np.array([x_cam, y_cam, z_cam], dtype=np.float64)

    def camera_to_base_point(self, xyz_camera):
        """Transform a point from camera frame to base frame."""
        p_cam = np.array([xyz_camera[0], xyz_camera[1], xyz_camera[2], 1.0], dtype=np.float64)
        p_base = self.T_base_camera @ p_cam
        return p_base[:3]

    def camera_to_base_vector(self, vec_camera):
        """Transform a vector from camera frame to base frame."""
        rot = self.T_base_camera[:3, :3]
        return rot @ vec_camera

    def estimate_surface_normal_camera(self, depth_image, intr, u, v, depth_scale, window=None):
        """Estimate surface normal from a depth patch using SVD."""
        if window is None:
            window = self.patch_window
        points = []
        for yy in range(max(0, int(v) - window), min(self.height, int(v) + window + 1)):
            for xx in range(max(0, int(u) - window), min(self.width, int(u) + window + 1)):
                raw_depth = int(depth_image[yy, xx])
                if raw_depth <= 0:
                    continue
                depth_m = float(raw_depth) * float(depth_scale)
                points.append(self.backproject_pixel(intr, xx, yy, depth_m))

        if len(points) < 6:
            return None

        points = np.asarray(points, dtype=np.float64)
        centroid = np.mean(points, axis=0)
        centered = points - centroid
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        normal = normalize(vh[-1])
        return normal

    def find_dark_spot_in_region(self, color_bgr, x1, y1, x2, y2):
        """Find the darkest pixel in a region (returns {'x','y'} or None)."""
        left = max(0, min(self.width - 1, min(int(x1), int(x2))))
        right = max(0, min(self.width - 1, max(int(x1), int(x2))))
        top = max(0, min(self.height - 1, min(int(y1), int(y2))))
        bottom = max(0, min(self.height - 1, max(int(y1), int(y2))))

        if right <= left or bottom <= top:
            return None

        region = color_bgr[top:bottom + 1, left:right + 1]
        if region.size == 0:
            return None

        gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        ys, xs = np.where(gray == np.min(gray))
        if xs.size == 0:
            return None

        cx = int(np.round(np.mean(xs))) + left
        cy = int(np.round(np.mean(ys))) + top
        return {"x": cx, "y": cy}

    # ----- Streaming -----
    def mjpeg_stream(self, overlay_fn=None, fps=20.0, quality=70, scale=1.0):
        """Yield an MJPEG stream. overlay_fn(color, depth) -> annotated image.

        The overlay is drawn at full resolution, then the transmitted JPEG is
        downscaled (`scale`) and compressed (`quality`) to keep bandwidth low
        for WiFi clients. The browser displays at the original size and maps
        clicks in full-res space, so coordinates are unaffected.
        """
        while True:
            with self.lock:
                if self.latest_color is None or self.latest_depth is None:
                    time.sleep(0.01)
                    continue
                color = self.latest_color.copy()
                depth = self.latest_depth.copy()

            vis = overlay_fn(color, depth) if overlay_fn is not None else color
            if scale != 1.0:
                vis = cv2.resize(vis, None, fx=scale, fy=scale,
                                 interpolation=cv2.INTER_AREA)
            ok, buffer = cv2.imencode(".jpg", vis, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            if not ok:
                continue

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
            )
            time.sleep(1.0 / fps)
