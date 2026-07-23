"""
Click-to-YOLO-object pick app.

Same trajectory/config pipeline as go_to_click.py, but a single click on the
camera feed snaps to the YOLO-detected object under the cursor (its bbox center),
computes the approach/pick poses there, and "Start Motion" runs the spline
trajectory to it. Object detection comes from a remote YOLO server.
"""

import csv
import math
import os
import time

import numpy as np
import cv2
from flask import Flask, Response, jsonify, request

from config import *  # constants + CurveParams
from camera import Camera
from robot_client import get_lebai_client, start_robot_system
from targeting import compute_click_target
from motion import execute_motion, execute_place, load_current_tcp_pose, move_to_safe_joints
from web_ui import render_page
from yolo_detector import YoloDetector
from command_parser import parse_pick_place, find_best_detection

# ----- YOLO config -----
LOG_PATH = "go_to_click_with_yolo_log.csv"
REMOTE_BASE_URL = "http://192.168.10.201:8000"
YOLO_REFRESH_SEC = 0.4
REMOTE_DETECTION_POLL = 0.05
REMOTE_DETECTION_TIMEOUT = 1.0

# ----- App / camera / detector -----
app = Flask(__name__)
camera = Camera(T_PATH, WIDTH, HEIGHT, FPS, DEPTH_WINDOW, PATCH_WINDOW)
detector = YoloDetector(camera, REMOTE_BASE_URL,
                        refresh_sec=YOLO_REFRESH_SEC,
                        poll_sec=REMOTE_DETECTION_POLL,
                        detection_timeout=REMOTE_DETECTION_TIMEOUT)

selected = {
    "u": WIDTH // 2,
    "v": HEIGHT // 2,
    "camera_xyz": None,
    "base_xyz": None,
    "surface_normal_base": None,
    "approach_pose": None,
    "pick_pose": None,
    "depth_m": None,
}

last_target = None
dropoff_target = {"pixel": None, "base_xyz": None}


# ===== Logging =====

def ensure_log():
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "pixel_u", "pixel_v", "depth_m",
                "x_base_m", "y_base_m", "z_base_m", "object",
            ])


def log_click(target, name):
    ensure_log()
    with open(LOG_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            time.time(), target["pixel"][0], target["pixel"][1], target["depth_m"],
            target["base_xyz_m"][0], target["base_xyz_m"][1], target["base_xyz_m"][2], name,
        ])


# ===== State =====

def store_last_target(target):
    global last_target
    last_target = dict(target)


def get_last_target():
    return dict(last_target) if last_target is not None else None


def ensure_selected_updated(target):
    selected["u"] = target["pixel"][0]
    selected["v"] = target["pixel"][1]
    selected["camera_xyz"] = target["camera_xyz_m"]
    selected["base_xyz"] = target["base_xyz_m"]
    selected["surface_normal_base"] = target["surface_normal_base"]
    selected["approach_pose"] = target["approach_pose"]
    selected["pick_pose"] = target["pick_pose"]
    selected["depth_m"] = target["depth_m"]


# ===== Overlay (draws YOLO boxes + the selected marker) =====

def draw_overlay(color, depth):
    vis = color.copy()
    cv2.rectangle(vis, (ROI_X1, ROI_Y1), (ROI_X2, ROI_Y2), (0, 255, 255), 2)

    for d in detector.get_detections():
        cv2.rectangle(vis, (d["x1"], d["y1"]), (d["x2"], d["y2"]), (0, 255, 255), 2)
        cv2.putText(vis, f"{d['name']} {d['conf']:.2f}",
                    (d["x1"], max(d["y1"] - 5, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    u, v = int(selected["u"]), int(selected["v"])
    cv2.circle(vis, (u, v), 6, (0, 0, 255), -1)

    if selected["base_xyz"] is not None:
        xb, yb, zb = selected["base_xyz"]
        cv2.putText(vis, f"base: x={xb:.3f}, y={yb:.3f}, z={zb:.3f}",
                    (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

    if dropoff_target["pixel"] is not None:
        du, dv = dropoff_target["pixel"]
        cv2.drawMarker(vis, (du, dv), (255, 128, 0), cv2.MARKER_CROSS, 20, 2)
        cv2.putText(vis, "drop-off", (du + 8, dv - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 128, 0), 1)

    return vis


# ===== Flask routes =====

@app.route("/")
def index():
    return render_page()


@app.route("/video")
def video():
    return Response(
        camera.mjpeg_stream(draw_overlay),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate",
                 "Pragma": "no-cache", "Expires": "0"},
    )


@app.route("/set_filter", methods=["POST"])
def set_filter():
    data = request.get_json(force=True)
    detector.set_filter(data.get("filter", ""))
    return jsonify({"ok": True})


@app.route("/current_pose")
def current_pose():
    try:
        return jsonify({"ok": True, "tcp_pose": load_current_tcp_pose(get_lebai_client())})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 503


@app.route("/reset_arm", methods=["POST"])
def reset_arm():
    try:
        move_to_safe_joints(get_lebai_client(), wait=True)
        return jsonify({"ok": True, "message": "arm moved to safe pose"})
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        print(tb, flush=True)
        return jsonify({"ok": False, "error": str(exc), "traceback": tb}), 500


@app.route("/pause_motion", methods=["POST"])
def pause_motion():
    try:
        client = get_lebai_client()
        if hasattr(client, "pause_move"):
            client.pause_move()
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "pause_move unsupported"}), 501
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/resume_motion", methods=["POST"])
def resume_motion():
    try:
        client = get_lebai_client()
        if hasattr(client, "resume_move"):
            client.resume_move()
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "resume_move unsupported"}), 501
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/stop_motion", methods=["POST"])
def stop_motion():
    try:
        client = get_lebai_client()
        if hasattr(client, "stop_move"):
            client.stop_move()
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": "stop_move unsupported"}), 501
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/select_region", methods=["POST"])
def select_region():
    """Shift-drag fallback: pick the YOLO object whose center lies in the region."""
    try:
        data = request.get_json(force=True)
        x1, y1 = int(data["x1"]), int(data["y1"])
        x2, y2 = int(data["x2"]), int(data["y2"])
        left, right = min(x1, x2), max(x1, x2)
        top, bottom = min(y1, y2), max(y1, y2)

        hits = [d for d in detector.get_detections()
                if left <= d["cx"] <= right and top <= d["cy"] <= bottom]
        if not hits:
            return jsonify({"ok": False, "error": "No YOLO object in region"}), 404
        best = max(hits, key=lambda d: d["conf"])
        return jsonify({"ok": True, "x": best["cx"], "y": best["cy"], "detection": best})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/click", methods=["POST"])
def click():
    """Single click -> snap to the YOLO object under the cursor, compute, optionally move."""
    try:
        data = request.get_json(force=True)
        u = max(0, min(WIDTH - 1, int(data["u"])))
        v = max(0, min(HEIGHT - 1, int(data["v"])))
        auto_move = bool(data.get("auto_move", AUTO_MOVE_DEFAULT))
        perform_pick = bool(data.get("perform_pick", PERFORM_PICK_DEFAULT))
        vertical_angle_deg = data.get("vertical_angle_deg", None)
        curve = CurveParams.from_request(data)

        # Snap the click to the detected object's center, if one is under the cursor.
        det = detector.detection_at(u, v)
        obj_name = None
        bbox_width_px = None
        bbox_height_px = None
        if det is not None:
            u, v = int(det["cx"]), int(det["cy"])
            obj_name = det["name"]
            bbox_width_px = det["x2"] - det["x1"]
            bbox_height_px = det["y2"] - det["y1"]

        target = compute_click_target(camera, u, v, vertical_angle_deg=vertical_angle_deg, curve=curve, bbox_width_px=bbox_width_px, bbox_height_px=bbox_height_px)
        if target is None:
            return jsonify({"ok": False, "error": "invalid depth", "pixel": [u, v]}), 400

        target["object"] = obj_name
        ensure_selected_updated(target)
        log_click(target, obj_name)
        store_last_target(target)

        motion_status = {"moved": False, "performed_pick": False}
        if auto_move:
            client = get_lebai_client()
            execute_motion(client, target, curve=curve)
            motion_status["moved"] = True
            if perform_pick:
                if hasattr(client, 'move_joints'):
                    client.move_joints(target["pick_pose"], acc=MOVE_ACCEL, vel=MOVE_SPEED, wait=True)
                else:
                    client.movej(target["pick_pose"], MOVE_SPEED, MOVE_ACCEL)
                    client.wait_move()
                motion_status["performed_pick"] = True

        return jsonify({"ok": True, **target, "saved_to": LOG_PATH, "motion_status": motion_status})
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/recompute_target", methods=["POST"])
def recompute_target():
    try:
        data = request.get_json(force=True)
        v_angle = data.get("vertical_angle_deg", None)
        curve = CurveParams.from_request(data)
        last = get_last_target()
        if last is None:
            return jsonify({"ok": False, "error": "no saved target to recompute"}), 400

        u, v = last["pixel"]
        new_t = compute_click_target(camera, u, v, vertical_angle_deg=v_angle, curve=curve)
        if new_t is None:
            return jsonify({"ok": False, "error": "recompute failed"}), 500

        ensure_selected_updated(new_t)
        store_last_target(new_t)
        return jsonify({"ok": True, **new_t})
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/set_dropoff_region", methods=["POST"])
def set_dropoff_region():
    """Shift-drag: find the darkest pixel in the selected region, backproject to 3D,
    and store it as the drop-off target."""
    global dropoff_target
    try:
        data = request.get_json(force=True)
        x1, y1 = int(data["x1"]), int(data["y1"])
        x2, y2 = int(data["x2"]), int(data["y2"])
        left, right = min(x1, x2), max(x1, x2)
        top, bottom = min(y1, y2), max(y1, y2)

        color = camera.latest_color_copy()
        if color is None:
            return jsonify({"ok": False, "error": "no camera frame available"}), 500

        snap = camera.snapshot()
        if snap is None:
            return jsonify({"ok": False, "error": "no depth frame available"}), 500
        depth, intr, depth_scale = snap

        gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
        region = gray[top:bottom + 1, left:right + 1]
        if region.size == 0:
            return jsonify({"ok": False, "error": "selection region is empty"}), 400

        _, _, min_loc, _ = cv2.minMaxLoc(region)
        u = left + min_loc[0]
        v = top + min_loc[1]

        depth_m = camera.median_depth_m(depth, u, v, depth_scale, window=DEPTH_WINDOW)
        if depth_m is None or depth_m <= 0:
            return jsonify({"ok": False, "error": "invalid depth at darkest pixel"}), 400

        xyz_cam = camera.backproject_pixel(intr, u, v, depth_m)
        xyz_base = camera.camera_to_base_point(xyz_cam)

        dropoff_target["pixel"] = [u, v]
        dropoff_target["base_xyz"] = [float(xyz_base[0]), float(xyz_base[1]), float(xyz_base[2])]

        return jsonify({
            "ok": True,
            "pixel": [u, v],
            "base_xyz": dropoff_target["base_xyz"],
        })
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/get_dropoff", methods=["GET"])
def get_dropoff():
    return jsonify({"ok": True, **dropoff_target})


@app.route("/command", methods=["POST"])
def command():
    """Execute a natural language pick-and-place command.

    Expects {"text": "pick up coke can and put at point 8"}.
    Finds the matching YOLO detection, picks it up, then places it at the
    stored drop-off target.
    """
    try:
        data = request.get_json(force=True)
        text = str(data.get("text", "")).strip()
        if not text:
            return jsonify({"ok": False, "error": "no command text provided"}), 400

        parsed = parse_pick_place(text)
        if parsed is None:
            return jsonify({"ok": False,
                            "error": f"could not parse command: '{text}'"}), 400

        obj_label = parsed["object"]
        detections = detector.get_detections()
        det = find_best_detection(obj_label, detections)
        if det is None:
            return jsonify({"ok": False,
                            "error": f"no detection matching '{obj_label}' (visible: {[d['name'] for d in detections]})"}), 404

        if dropoff_target["base_xyz"] is None:
            return jsonify({"ok": False,
                            "error": "no drop-off target set — shift+drag a region first"}), 400

        vertical_angle_deg = data.get("vertical_angle_deg", None)
        curve = CurveParams.from_request(data)

        u, v = int(det["cx"]), int(det["cy"])
        bbox_width_px = det["x2"] - det["x1"]
        bbox_height_px = det["y2"] - det["y1"]
        target = compute_click_target(camera, u, v,
                                      vertical_angle_deg=vertical_angle_deg,
                                      curve=curve,
                                      bbox_width_px=bbox_width_px,
                                      bbox_height_px=bbox_height_px)
        if target is None:
            return jsonify({"ok": False, "error": "invalid depth at detection center"}), 400

        target["object"] = det["name"]
        ensure_selected_updated(target)
        store_last_target(target)

        client = get_lebai_client()

        print(f"[command] picking '{det['name']}' at pixel ({u}, {v})", flush=True)
        execute_motion(client, target, curve=curve)

        grab_z = float(target.get("grab_z") or target["approach_tip_base_m"][2])
        pick_pitch_deg = float(target.get("vertical_pitch_deg") or 0.0)
        print(f"[command] placing at {dropoff_target['base_xyz']} (grab_z={grab_z:.3f}, pitch={pick_pitch_deg:.1f}°)", flush=True)
        execute_place(client, dropoff_target["base_xyz"], grab_z, pitch_deg=pick_pitch_deg)

        return jsonify({
            "ok": True,
            "parsed": parsed,
            "detection": det,
            "pick_target": target,
            "dropoff_base_xyz": dropoff_target["base_xyz"],
        })
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    try:
        ensure_log()
        print("Loading camera-to-base transform:")
        print(camera.T_base_camera)
        print("Starting RealSense pipeline...")
        camera.start()
        print("RealSense started.")

        start_robot_system()
        print("LEBAI connected and ready.")

        detector.start()
        print(f"YOLO detector polling {REMOTE_BASE_URL}")

        print("Open browser: http://<ubuntu_ip>:5000")
        print(f"Logging to: {LOG_PATH}")

        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        print("Stopping RealSense pipeline...")
        camera.stop()
