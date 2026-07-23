import os

class Settings:
    robot_telemetry_url = "ws://localhost:5000/telemetry/ws/robot"
    camera_frames_url = "ws://localhost:5000/telemetry/ws/frames"
    camera_single_frame_url = "http://localhost:5000/camera/frame"
    frontend_url = "http://localhost:5173"

    yolo_server_url = "http://192.168.10.201:8000"
    yolo_poll_sec = 0.05
    yolo_timeout_sec = 2

    # Hand-eye calibration: 4x4 camera→base transform
    t_base_camera_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "services", "object_detection", "T_base_camera.npy",
    )

settings = Settings();
