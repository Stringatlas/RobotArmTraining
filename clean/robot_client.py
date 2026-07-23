"""
LEBAI arm client management, shared by the click and YOLO apps.

Owns the lazily-created singleton client (a LebaiArmWrapper when available, else a
raw lebai_sdk connection) and the system startup sequence.
"""

import os
import sys
import time

from config import LEBAI_IP, STARTING_JOINTS

# Put robot_arm/ on the path FIRST so `from arm import ...` works exactly like
# arm_ik_tester.py (which runs from inside robot_arm/).
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_script_dir))
_robot_arm_dir = os.path.join(_project_root, "robot_arm")
for _p in (_robot_arm_dir, _project_root):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

ARM_WRAPPER_AVAILABLE = False
try:
    from arm import LebaiArmWrapper
    ARM_WRAPPER_AVAILABLE = True
    print(f"✓ LebaiArmWrapper loaded from {_robot_arm_dir}")
except Exception as _arm_err:  # catch ANY error so the real cause is visible
    import traceback as _tb
    print("⚠ LebaiArmWrapper FAILED to import — falling back to raw lebai_sdk")
    print(f"  reason: {type(_arm_err).__name__}: {_arm_err}")
    _tb.print_exc()

try:
    import lebai_sdk
except Exception:
    lebai_sdk = None

_lebai = None


def get_lebai_client():
    """Get or create the LEBAI SDK client (wrapped with LebaiArmWrapper if available)."""
    global _lebai
    if lebai_sdk is None:
        raise RuntimeError("lebai_sdk is not installed")
    if _lebai is None:
        if ARM_WRAPPER_AVAILABLE:
            _lebai = LebaiArmWrapper(LEBAI_IP, async_mode=False, starting_joints=STARTING_JOINTS)
        else:
            _lebai = lebai_sdk.connect(LEBAI_IP, False)
    return _lebai


def start_robot_system():
    """Initialize the robot system (start, exit teach mode, init gripper)."""
    client = get_lebai_client()

    if hasattr(client, "start_sys"):
        print("Starting robot system...")
        client.start_sys()

    try:
        if hasattr(client, "end_teach_mode"):
            client.end_teach_mode()
    except Exception as exc:
        print(f"end_teach_mode warning: {exc}")

    time.sleep(1.0)

    try:
        if hasattr(client, "init_claw"):
            print("Initializing gripper...")
            client.init_claw(must=False)
            print("Gripper initialized successfully")
    except Exception as e:
        print(f"Warning: gripper init failed: {e}")

    return client
