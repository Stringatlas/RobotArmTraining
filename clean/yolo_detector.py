"""
Object detection via a remote YOLO server.

Posts frames to the remote server and polls for detections in a background
thread, exposing the latest detections and a `detection_at(u, v)` lookup so a
single click can be snapped to the object under the cursor.

Detection format (per object): {name, conf, x1, y1, x2, y2, cx, cy}
"""

import threading
import time

import cv2
import requests


class YoloDetector:
    def __init__(self, camera, base_url, refresh_sec=0.85,
                 poll_sec=0.05, detection_timeout=1.0):
        self.camera = camera
        self.base_url = base_url.rstrip("/")
        self.refresh_sec = refresh_sec
        self.poll_sec = poll_sec
        self.detection_timeout = detection_timeout

        self._lock = threading.Lock()
        self.latest_detections = []
        self._filter = ""
        self._thread = None

    # ----- Lifecycle -----
    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def set_filter(self, name):
        with self._lock:
            self._filter = (name or "").strip().lower()

    def get_detections(self):
        with self._lock:
            return list(self.latest_detections)

    # ----- Remote server I/O -----
    def _url(self, path):
        return self.base_url + (path if path.startswith("/") else "/" + path)

    def _post_frame(self, color_image, timeout=5.0):
        try:
            ok, buf = cv2.imencode(".jpg", color_image, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ok:
                return None
            files = {"file": ("frame.jpg", buf.tobytes(), "image/jpeg")}
            resp = requests.post(self._url("/upload_image"), files=files, timeout=timeout)
            resp.raise_for_status()
            return float(resp.json().get("ts", time.time()))
        except Exception as exc:
            print("YOLO post_frame error:", exc)
            return None

    def _get_remote(self, timeout=5.0):
        try:
            resp = requests.get(self._url("/detections"), timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    @staticmethod
    def _map_remote(remote):
        out = []
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

    # ----- Background loop -----
    def _loop(self):
        while True:
            color = self.camera.latest_color_copy()
            if color is None:
                time.sleep(0.05)
                continue

            detections = []
            post_ts = self._post_frame(color)
            if post_ts is not None:
                start = time.time()
                while time.time() - start < self.detection_timeout:
                    remote = self._get_remote()
                    if remote is not None:
                        rts = float(remote.get("timestamp", 0.0))
                        if rts >= post_ts - 10.0:
                            detections = self._map_remote(remote)
                            break
                    time.sleep(self.poll_sec)

            with self._lock:
                self.latest_detections = detections
            time.sleep(self.refresh_sec)

    # ----- Click -> object lookup -----
    def detection_at(self, u, v):
        """Return the detection whose bbox contains (u, v). If several overlap, prefer
        (respecting any active class filter) the smallest box, then highest confidence."""
        with self._lock:
            dets = list(self.latest_detections)
            flt = self._filter

        hits = [d for d in dets if d["x1"] <= u <= d["x2"] and d["y1"] <= v <= d["y2"]]
        if not hits:
            return None

        if flt:
            filtered = [d for d in hits if flt in d["name"].lower()]
            if filtered:
                hits = filtered

        def box_area(d):
            return max(1, (d["x2"] - d["x1"]) * (d["y2"] - d["y1"]))

        # smallest box first (most specific), then highest confidence
        hits.sort(key=lambda d: (box_area(d), -d["conf"]))
        return hits[0]
