"""
Configuration constants and shared parameter types for the robot-arm pick UI.

Split out of go_to_click.py so the constants and the CurveParams dataclass can be
imported by both the motion module and the main app without duplication.
"""

import os
from dataclasses import dataclass


# Camera & RealSense settings
WIDTH = 640
HEIGHT = 480
FPS = 30

ROI_X1 = 135
ROI_Y1 = 185
ROI_X2 = 455
ROI_Y2 = 335

# Robot configuration
LEBAI_IP = "192.168.10.200"
T_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "T_base_camera.npy")
LOG_PATH = "go_to_click_log.csv"

# Gripper tip offset is now handled by the controller TCP (set in the LEBAI panel),
# so the software no longer shifts tip->wrist. Keep at 0.0 while the TCP is active.
GRIPPER_TIP_OFFSET_M = 0.0
APPROACH_CLEARANCE_M = 0.06
PICK_CLEARANCE_M = 0.02  # negative = past surface_base along reach_axis (deeper into object)
PLACE_LIFT_M = 0.06      # how far above drop-off the hover pose sits before releasing
GRAB_HEIGHT_FRACTION = 2/3  # fraction of 3D bbox height above surface_base used for grab Z
ROBOT_MIN_REACH_M = 0.50   # minimum XY radius for pick targets
PLACE_MIN_REACH_M = 0.35   # minimum XY radius for place/drop-off targets (can be closer)

# Camera processing
DEPTH_WINDOW = 7
PATCH_WINDOW = 5

# Motion defaults
AUTO_MOVE_DEFAULT = False
PERFORM_PICK_DEFAULT = False
MOVE_SPEED = 0.5
MOVE_ACCEL = 1.0

# Where along the safe->approach curve the end-effector starts tracing the heading
# (0=start, 1=end). Shared by both motion execution and the visualizer.
# Kept >= 0.5 so tracing begins AFTER the curve's sharpest-turning apex, which keeps
# the wrist reorientation smooth (no flips) even for aggressive curves.
HEADING_START_T = 0.6

# Safe/home joint positions — taught by jogging arm to safe pose and reading joints.
# Used for the "Reset Arm" button and as the IK seed for the trajectory.
SAFE_JOINTS = [-0.21, -1.06, 2.59, -1.59, 1.46, 0.07]

# IK seed for move_to_pose_nearest fallback: matches SAFE_JOINTS since that's
# where the arm starts. Kept as a separate copy so mutations don't alias.
STARTING_JOINTS = list(SAFE_JOINTS)

# Safe poses
# Roll convention flipped (wrist rolled 180° about tool-Z) so it matches the
# heading/pick orientation convention -> no wrist flip during the curve trace.
# NOTE: now expressed at the gripper-tip TCP (set in the LEBAI panel). x shifted
# out by ~the old gripper offset. TODO: re-teach by jogging and reading
# actual_tcp_pose with the TCP active to get exact x/y/z.
SAFE_POSE = {
    "x": -0.55, "y": -0.062, "z": 0.179,
    "rx": 1.49, "ry": 0.05, "rz": -1.56,
}

INTER_POSE = {
    "x": -0.362, "y": 0.02, "z": 0.221,
    "rx": -1.59, "ry": 0.0, "rz": 1.55,
}


@dataclass
class CurveParams:
    """Bundles the Bézier curve-shape parameters so they don't have to be threaded
    individually through every function and endpoint. (Vertical/approach-pitch angle
    is kept separate because its default handling differs per endpoint.)"""
    horizontal_angle_deg: float = 0.0
    control_length_factor: float = 0.667
    heading_angle_scale: float = 1.0
    heading_start_t: float = HEADING_START_T

    @classmethod
    def from_request(cls, data):
        """Read curve params from a request dict, falling back to the defaults
        (identical to the old per-field `data.get(name, default)` behavior)."""
        return cls(
            horizontal_angle_deg=data.get("horizontal_angle_deg", 0.0) or 0.0,
            control_length_factor=data.get("control_length_factor", 0.667),
            heading_angle_scale=data.get("heading_angle_scale", 1.0),
            heading_start_t=data.get("heading_start_t", HEADING_START_T),
        )
