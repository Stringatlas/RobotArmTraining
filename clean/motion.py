"""
Motion execution for the pick sequence.

All functions take the arm `client` as an argument (no global client state here),
so this module has no dependency on the camera/Flask app and can't create an
import cycle. Constants and CurveParams come from config; curve geometry from
pose_calculation.
"""

import math
import time

import numpy as np

from config import (
    SAFE_POSE,
    SAFE_JOINTS,
    MOVE_SPEED,
    MOVE_ACCEL,
    STARTING_JOINTS,
    PLACE_LIFT_M,
    ROBOT_MIN_REACH_M,
    PLACE_MIN_REACH_M,
    CurveParams,
)
from pose_calculation import sample_bezier_motion_poses, pose_from_tip_and_direction, pose_dict_to_list, normalize


def load_current_tcp_pose(client):
    """Load current TCP pose from the given arm client."""
    kin_data = client.get_kin_data()
    pose = kin_data.get("actual_tcp_pose")
    if not pose:
        raise RuntimeError("LEBAI pose data is unavailable")
    return {
        "x": float(pose["x"]),
        "y": float(pose["y"]),
        "z": float(pose["z"]),
        "rx": float(pose.get("rx", 0.0)),
        "ry": float(pose.get("ry", 0.0)),
        "rz": float(pose.get("rz", 0.0)),
    }


def gripper_open(client):
    """Open the gripper."""
    try:
        client.set_claw(0, 85)
        print("Gripper open command sent")
        if hasattr(client, "get_claw"):
            for _ in range(20):
                status = client.get_claw()
                hold_on = status.get("hold_on", False)
                amplitude = status.get("amplitude", 0)
                if not hold_on and amplitude > 80:
                    print(f"Gripper opened successfully (amplitude={amplitude})")
                    return
                time.sleep(0.1)
            print(f"Gripper open completed (final amplitude={status.get('amplitude', 0)})")
    except Exception as e:
        print(f"Gripper open error: {e}")


def gripper_close(client):
    """Close the gripper."""
    try:
        client.set_claw(force=0, amplitude=20)
        print("Gripper close command sent")
        if hasattr(client, "get_claw"):
            for _ in range(20):
                status = client.get_claw()
                hold_on = status.get("hold_on", False)
                amplitude = status.get("amplitude", 20)
                if not hold_on:
                    print(f"Gripper closed successfully (amplitude={amplitude})")
                    return
                time.sleep(0.1)
            print(f"Gripper close completed (final amplitude={status.get('amplitude', 100)})")
    except Exception as e:
        print(f"Gripper close error: {e}")


def move_to_safe_joints(client, wait=True):
    """Move to the taught safe/home joint pose directly (no IK)."""
    client.move_joints(SAFE_JOINTS, acc=MOVE_ACCEL, vel=MOVE_SPEED, wait=wait)


def move_to_pose_nearest(client, pose, wait=True):
    """Move to a Cartesian pose by solving IK seeded with the CURRENT joints, then
    movej to that solution. Picks the joint solution nearest where the arm already
    is, so the wrist (joint 6) takes the short way instead of wrapping ~360 deg.
    Falls back to a raw Cartesian movel if seeded IK isn't available.
    """
    if hasattr(client, 'calc_inverse_kinematics') and hasattr(client, 'move_joints'):
        try:
            ref = client.get_actual_joint_pose()
        except Exception as e:
            print(f"    get_actual_joint_pose failed: {e}", flush=True)
            ref = None
        if not ref or len(ref) != 6:
            ref = STARTING_JOINTS
        print(f"    IK ref joints: {ref}", flush=True)
        joints = client.calc_inverse_kinematics(pose, reference_joints=ref)
        print(f"    IK solution: {joints}", flush=True)
        return client.move_joints(joints, acc=MOVE_ACCEL, vel=MOVE_SPEED, wait=wait)
    # Fallback: raw Cartesian move (controller picks IK, may wrap)
    print("    (no seeded-IK; using raw movel)", flush=True)
    client.movel(pose, MOVE_SPEED, MOVE_ACCEL)
    if wait:
        client.wait_move()


def execute_motion(client, target, curve=None):
    """Execute pick motion sequence with smooth splined trajectory.

    The safe->approach phase follows the SAME Bézier curve as the visualizer,
    parameterized by the CurveParams `curve`.
    """
    if curve is None:
        curve = CurveParams()
    approach_pose = target["approach_pose"]
    pick_pose = target["pick_pose"]
    pitch_deg = target.get("vertical_pitch_deg")
    grab_z = target.get("grab_z")  # fixed Z from bbox height; None falls back to pick_pose Z

    try:
        try:
            curr_pose = load_current_tcp_pose(client)
            print("Current TCP pose:", curr_pose)
        except Exception as _exc:
            print("Warning: could not read current TCP pose:", _exc)

        print("Executing motion sequence with smooth trajectory:")
        print("  safe_pose:", SAFE_POSE)
        print("  approach_pose:", approach_pose)
        print("  pick_pose:", pick_pose)
        print(f"  pick_pose Z: {pick_pose['z']:.4f} m  approach_pose Z: {approach_pose['z']:.4f} m")
        print(f"  curve={curve}")

        # Always use the Bézier curve that matches the visualizer
        _execute_motion_with_splines(client, approach_pose, pick_pose, curve, pitch_deg=pitch_deg, grab_z=grab_z)

    except Exception as exc:
        print(f"✗ Motion execution failed: {exc}")
        import traceback
        traceback.print_exc()
        raise


def _execute_motion_direct(client, approach_pose, pick_pose):
    """Fallback: Direct motion commands without splines."""
    # Helper function to move with wrapper or raw client
    def move_to(pose, wait=True):
        if hasattr(client, 'move_linear'):
            client.move_linear(pose, acc=MOVE_ACCEL, vel=MOVE_SPEED, wait=wait)
        else:
            client.movel(pose, MOVE_SPEED, MOVE_ACCEL)
            if wait:
                client.wait_move()

    move_to(SAFE_POSE)
    move_to(approach_pose)
    gripper_open(client)
    move_to(pick_pose)

    time.sleep(0.5)
    gripper_close(client)
    time.sleep(0.5)

    print("Lifting 5 cm...")
    lift_pose = {**pick_pose, "z": pick_pose["z"] + 0.05}
    move_to(lift_pose)
    print("Returning to safe pose...")
    move_to_safe_joints(client)


def _execute_motion_with_splines(client, approach_pose, pick_pose, curve=None, pitch_deg=None, grab_z=None, mode="pick"):
    """Execute motion using the SAME Bézier curve the visualizer shows.

    Phase 1 (safe->approach) follows the curved Bézier. Phase 2 is a STRAIGHT
    move to the item (holding the end-of-curve orientation). Phase 3 retracts.
    `pitch_deg` forces the final pitch to the vertical angle (ramped via slerp).
    mode="pick":  open gripper → Phase2 push → close gripper → lift Z → safe
    mode="place": Phase2 push (gripper closed) → open gripper → retract to approach → safe
    """
    if curve is None:
        curve = CurveParams()
    horizontal_angle_deg = curve.horizontal_angle_deg
    control_length_factor = curve.control_length_factor
    heading_angle_scale = curve.heading_angle_scale
    heading_start_t = curve.heading_start_t

    approach_pos = np.array([approach_pose["x"], approach_pose["y"], approach_pose["z"]])

    min_reach = PLACE_MIN_REACH_M if mode == "place" else ROBOT_MIN_REACH_M
    pick_pos = np.array([pick_pose["x"], pick_pose["y"], pick_pose["z"]])
    for label, pos in [("approach", approach_pos), ("pick", pick_pos)]:
        xy_reach = math.hypot(pos[0], pos[1])
        if xy_reach < min_reach:
            raise RuntimeError(
                f"{label} pose XY distance {xy_reach:.3f} m is within the robot dead zone "
                f"(min {min_reach} m). Move the robot closer or pick a different target."
            )

    # Align joint 1 to point the arm at the target.
    # joint1=0 corresponds to the -X direction (π rad), CCW positive.
    # So: joint1 = atan2(ty, tx) - π
    target_azimuth = math.atan2(approach_pos[1], approach_pos[0])
    target_joint1 = target_azimuth - math.pi
    # Pick whichever equivalent angle (target ± k·2π) is closest to SAFE_JOINTS[0]
    # to guarantee the minor arc.
    candidates = [target_joint1 + 2 * math.pi * k for k in (-1, 0, 1)]
    joint1_aligned = min(candidates, key=lambda a: abs(a - SAFE_JOINTS[0]))
    rotation_deg = math.degrees(joint1_aligned - SAFE_JOINTS[0])
    print(f"  Joint 1: base→target {math.degrees(target_azimuth):.1f}° "
          f"→ joint1 {joint1_aligned:.3f} rad ({math.degrees(joint1_aligned):.1f}°), "
          f"rotation from safe: {rotation_deg:+.1f}°", flush=True)

    aligned_joints = list(SAFE_JOINTS)
    aligned_joints[0] = joint1_aligned

    # The aligned safe pose is the safe pose XY rotated by the joint 1 delta.
    # Z doesn't change (joint 1 is pure rotation around Z).
    j1_delta = joint1_aligned - SAFE_JOINTS[0]
    safe_xy = math.hypot(SAFE_POSE["x"], SAFE_POSE["y"])
    safe_az = math.atan2(SAFE_POSE["y"], SAFE_POSE["x"])
    new_safe_az = safe_az + j1_delta
    safe_pos = np.array([
        safe_xy * math.cos(new_safe_az),
        safe_xy * math.sin(new_safe_az),
        SAFE_POSE["z"],
    ])
    safe_orient = {
        "rx": SAFE_POSE.get("rx", 0.0),
        "ry": SAFE_POSE.get("ry", 0.0),
        "rz": SAFE_POSE.get("rz", 0.0) + j1_delta,
    }

    print("  Moving to aligned safe pose...", flush=True)
    client.move_joints(aligned_joints, acc=MOVE_ACCEL, vel=MOVE_SPEED, wait=True)

    # Phase 1: Safe pose to approach, sampled from the visualizer's Bézier curve.
    # Orientation: constant (safe) until HEADING_START_T, then ramps into tracing the
    # curve's tangent (heading). Uses the SAME helper the visualizer uses, so what you
    # see in the UI is exactly what is commanded.
    print("  Phase 1: Moving to approach position (Bézier curve)...")
    sampled_poses = sample_bezier_motion_poses(
        safe_pos, approach_pos, safe_orient,
        horizontal_angle_deg=horizontal_angle_deg,
        control_length_factor=control_length_factor,
        num_points=6,
        heading_start_t=heading_start_t,
        heading_angle_scale=heading_angle_scale,
        pitch_deg=pitch_deg,
    )
    curve_points = [[p["x"], p["y"], p["z"]] for p in sampled_poses]  # for spacing calc
    print(f"    Probing IK for {len(sampled_poses)} waypoints...", flush=True)

    if not hasattr(client, 'follow_trajectory'):
        raise RuntimeError(
            "Client has no follow_trajectory method. The arm must be a LebaiArmWrapper "
            "(arm.py). Check ARM_WRAPPER_AVAILABLE / get_lebai_client()."
        )

    # Pre-validate IK for every waypoint so we know exactly which one is unreachable
    # before handing anything to the controller.
    try:
        probe_ref = client.get_actual_joint_pose()
        if not probe_ref or len(probe_ref) != 6:
            probe_ref = list(SAFE_JOINTS)
    except Exception:
        probe_ref = list(SAFE_JOINTS)

    failed = []
    for i, pose in enumerate(sampled_poses):
        try:
            joints = client.calc_inverse_kinematics(pose, reference_joints=probe_ref)
            probe_ref = joints
            print(f"    [{i}] OK  ({pose['x']:+.3f}, {pose['y']:+.3f}, {pose['z']:+.3f}) "
                  f"rx={pose['rx']:.2f} ry={pose['ry']:.2f} rz={pose['rz']:.2f}", flush=True)
        except Exception as e:
            failed.append(i)
            print(f"    [{i}] IK FAIL  ({pose['x']:+.3f}, {pose['y']:+.3f}, {pose['z']:+.3f}) "
                  f"rx={pose['rx']:.2f} ry={pose['ry']:.2f} rz={pose['rz']:.2f}  → {e}", flush=True)

    if failed:
        raise RuntimeError(
            f"IK failed on waypoint(s) {failed} out of {len(sampled_poses)} — "
            "target pose or curve passes through unreachable workspace. "
            "Try adjusting vertical angle or moving the target."
        )

    # Blend radius must be SMALLER than the spacing between waypoints, otherwise the
    # controller rounds the whole curve into a straight line. Use a fraction of the
    # average spacing between consecutive sampled points.
    if len(curve_points) > 1:
        spacings = [
            float(np.linalg.norm(np.array(b) - np.array(a)))
            for a, b in zip(curve_points[:-1], curve_points[1:])
        ]
        avg_spacing = sum(spacings) / len(spacings)
    else:
        avg_spacing = 0.01
    blend_radius = max(0.0005, avg_spacing * 0.4)
    print(f"    avg waypoint spacing={avg_spacing:.4f}m -> blend_radius={blend_radius:.4f}m", flush=True)

    motion_ids = client.follow_trajectory(
        waypoints=sampled_poses,
        acc=MOVE_ACCEL,
        vel=MOVE_SPEED,
        blend_radius=blend_radius,
        wait=True,
    )
    print(f"    follow_trajectory queued {len(motion_ids)} motions", flush=True)

    print("  Phase 1 complete! ✓", flush=True)

    if mode == "pick":
        print("  Opening gripper...", flush=True)
        gripper_open(client)

    # End-of-curve pose (position at approach, orientation = traced/scaled heading).
    end_pose = sampled_poses[-1]
    end_orient = {"rx": end_pose["rx"], "ry": end_pose["ry"], "rz": end_pose["rz"]}

    # Phase 2: straight push to pick/release target.
    # For pick: grab_z is baked into pick_pose["z"] by targeting.py.
    # For place: use pick_pose["z"] directly (the drop-off surface Z, not hover height).
    if mode == "place":
        phase2_z = pick_pose["z"]
    else:
        phase2_z = grab_z if grab_z is not None else pick_pose["z"]
    target_pose = {"x": pick_pose["x"], "y": pick_pose["y"], "z": phase2_z,
                   "rx": end_orient["rx"], "ry": end_orient["ry"], "rz": end_orient["rz"]}

    label = "release" if mode == "place" else "grab"
    print(f"  Phase 2: Reaching to {label} point ({target_pose['x']:.3f}, {target_pose['y']:.3f}, z={phase2_z:.3f})...", flush=True)
    _move_linear(client, target_pose)
    print(f"  Phase 2 complete! ✓ reached ({target_pose['x']:.3f}, {target_pose['y']:.3f}, {target_pose['z']:.3f})", flush=True)

    if mode == "pick":
        time.sleep(0.5)
        print("  Closing gripper...", flush=True)
        gripper_close(client)
        time.sleep(0.5)
        # Phase 3: lift straight up 5 cm, then safe
        lift_pose = {**target_pose, "z": target_pose["z"] + 0.05}
        print(f"  Phase 3: Lifting 5 cm (z {target_pose['z']:.3f} → {lift_pose['z']:.3f})...", flush=True)
        _move_linear(client, lift_pose)
    else:
        print("  Opening gripper (releasing)...", flush=True)
        gripper_open(client)
        time.sleep(0.3)
        # Phase 3: retract up past hover by another PLACE_LIFT_M for clearance
        high_retract = {**end_pose, "z": end_pose["z"] + PLACE_LIFT_M}
        print(f"  Phase 3: Retracting to z={high_retract['z']:.3f}...", flush=True)
        _move_linear(client, high_retract)

    print("  Phase 3 complete! ✓", flush=True)
    print("  Returning to safe pose...", flush=True)
    move_to_safe_joints(client, wait=True)
    print("  Motion sequence complete!")


def _move_linear(client, pose, wait=True):
    if hasattr(client, 'move_linear'):
        client.move_linear(pose, acc=MOVE_ACCEL, vel=MOVE_SPEED, wait=wait)
    else:
        client.movel(pose, MOVE_SPEED, MOVE_ACCEL)
        if wait:
            client.wait_move()


def execute_place(client, dropoff_xyz, grab_z, pitch_deg=None, curve=None):
    """Place sequence: same Bézier spline as pickup aimed at drop-off XY.

    Args:
        dropoff_xyz: [x, y, z] in base frame — drop-off location (Z ignored).
        grab_z:      The exact Z the arm grabbed at — release happens at this same Z.
                     Hover is at grab_z + PLACE_LIFT_M; Phase 2 descends to grab_z.
        pitch_deg:   Approach pitch from the pick (so orientation matches pickup).
        curve:       CurveParams for the Bézier shape (default: straight-in).
    """
    if curve is None:
        curve = CurveParams()
    if pitch_deg is None:
        pitch_deg = 0.0

    dx, dy = float(dropoff_xyz[0]), float(dropoff_xyz[1])

    xy_reach = math.hypot(dx, dy)
    if xy_reach < PLACE_MIN_REACH_M:
        raise RuntimeError(
            f"Drop-off XY distance {xy_reach:.3f} m is within the robot dead zone "
            f"(min {PLACE_MIN_REACH_M} m). Choose a different drop-off location."
        )

    # Same horizontal direction as pickup — keeps arm orientation (rx) matching.
    reach_dir = normalize(np.array([dx, dy, 0.0]))
    if reach_dir is None:
        reach_dir = np.array([1.0, 0.0, 0.0])

    # Hover: PLACE_LIFT_M above grab height. Phase 2 descends to grab height to release.
    hover_z = grab_z + PLACE_LIFT_M
    hover_tip = np.array([dx, dy, hover_z])
    release_tip = np.array([dx, dy, grab_z])

    hover_pose_p = pose_from_tip_and_direction(hover_tip, reach_dir)
    release_pose_p = pose_from_tip_and_direction(release_tip, reach_dir)

    if hover_pose_p is None or release_pose_p is None:
        raise RuntimeError("execute_place: could not compute drop-off poses")

    print(f"[place] hover:   ({dx:.3f}, {dy:.3f}, z={hover_z:.3f})", flush=True)
    print(f"[place] release: ({dx:.3f}, {dy:.3f}, z={grab_z:.3f})", flush=True)

    # Same pitch_deg as pickup → orientation matches. grab_z=None → Phase 2 uses dz.
    _execute_motion_with_splines(
        client, hover_pose_p, release_pose_p,
        curve=curve,
        pitch_deg=pitch_deg,
        grab_z=None,
        mode="place",
    )
