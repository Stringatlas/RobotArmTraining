"""
Target computation shared by the click and YOLO apps.

`compute_click_target` turns a clicked pixel into approach/pick poses + the
trajectory visualization, using a Camera instance for depth/deprojection. Pulled
out of go_to_click.py so both entrypoints use the exact same logic.
"""

import math

import numpy as np

from config import (
    SAFE_POSE,
    GRIPPER_TIP_OFFSET_M,
    APPROACH_CLEARANCE_M,
    PICK_CLEARANCE_M,
    GRAB_HEIGHT_FRACTION,
    DEPTH_WINDOW,
    PATCH_WINDOW,
    CurveParams,
)
from pose_calculation import (
    normalize,
    compute_approach_direction,
    pose_from_tip_and_direction,
    pose_dict_to_list,
    generate_spline_visualization,
    sample_bezier_motion_poses,
    rotation_from_euler_zyx,
)


def build_curve_viz(safe_tip_base, approach_tip_base, sampled_poses, curve, pitch_deg=None):
    """Build the trajectory visualization for a safe->approach curve. Centralizes
    the SAFE_POSE base-orientation block. `pitch_deg` forces the final pitch to the
    vertical angle (keeps horizontal yaw)."""
    return generate_spline_visualization(
        start_pos=safe_tip_base,
        end_pos=approach_tip_base,
        sampled_poses=sampled_poses,
        horizontal_angle_deg=curve.horizontal_angle_deg,
        control_length_factor=curve.control_length_factor,
        base_orient={"rx": SAFE_POSE["rx"], "ry": SAFE_POSE["ry"], "rz": SAFE_POSE["rz"]},
        heading_start_t=curve.heading_start_t,
        heading_angle_scale=curve.heading_angle_scale,
        pitch_deg=pitch_deg,
    )


def compute_click_target(camera, u, v, vertical_angle_deg=None, curve=None, bbox_width_px=None, bbox_height_px=None):
    """
    Compute approach and pick poses from a clicked pixel.

    Args:
        camera: Camera instance (depth snapshot + deprojection + calibration)
        u, v: Pixel coordinates
        vertical_angle_deg: Vertical approach angle (0=flat, 90=vertical); None -> surface normal
        curve: CurveParams bundling horizontal angle / control length / heading scale / start
        bbox_width_px: YOLO bounding-box width in pixels. When provided, the 3D point is
            shifted inward (toward the camera) by half the estimated 3D object width so the
            gripper targets the object's near face rather than its center.

    Returns:
        Dict with target info and poses, or None if invalid.
    """
    if curve is None:
        curve = CurveParams()
    horizontal_angle_deg = curve.horizontal_angle_deg  # used for pose/return metadata

    snap = camera.snapshot()
    if snap is None:
        return None
    depth, intr, depth_scale = snap

    # Get depth at pixel
    depth_m = camera.median_depth_m(depth, u, v, depth_scale, window=DEPTH_WINDOW)
    if depth_m is None or depth_m <= 0:
        return None

    # Backproject to 3D
    xyz_cam = camera.backproject_pixel(intr, u, v, depth_m)
    xyz_cam_raw = xyz_cam.copy()

    # When a YOLO bbox is available, depth_m lands on the near face of the object.
    # Shift the target by half the estimated 3D bbox width along the camera ray so
    # surface_base ends up at the geometric center of the object (not the near face).
    if bbox_width_px is not None and intr.fx > 0:
        width_3d = (float(bbox_width_px) / intr.fx) * depth_m
        cam_to_obj = normalize(xyz_cam)
        if cam_to_obj is not None:
            xyz_cam = xyz_cam + cam_to_obj * (0.75 * width_3d)

    xyz_base_raw = camera.camera_to_base_point(xyz_cam_raw)
    xyz_base = camera.camera_to_base_point(xyz_cam)
    surface_base = xyz_base

    # Grab Z: fixed height above surface_base derived from the bbox height in 3D.
    # Only phases in XY during approach — Z stays constant at this level.
    grab_z = None
    if bbox_height_px is not None and intr.fy > 0:
        height_3d = (float(bbox_height_px) / intr.fy) * depth_m
        # surface_base is the YOLO bbox CENTER (≈ mid-height of object, i.e. 0.5 * height from bottom).
        # GRAB_HEIGHT_FRACTION is the desired grab fraction from the BOTTOM of the object.
        # So we only need to add (GRAB_HEIGHT_FRACTION - 0.5) * height above the detected center.
        grab_z = float(surface_base[2]) + (GRAB_HEIGHT_FRACTION - 0.5) * height_3d
        print(f"  grab_z debug: center_z={surface_base[2]:.4f} height_3d={height_3d:.4f} "
              f"offset={(GRAB_HEIGHT_FRACTION - 0.5) * height_3d:.4f} grab_z={grab_z:.4f}", flush=True)
        # Lift the surface target to grab_z BEFORE computing approach/pick standoffs so the
        # geometry is correct for any approach angle (not just horizontal).
        surface_base = np.array([surface_base[0], surface_base[1], grab_z], dtype=np.float64)

    # Horizontal direction from base to target (in xy plane)
    horizontal = np.array([-surface_base[0], -surface_base[1], 0.0], dtype=np.float64)
    h_dir = normalize(horizontal)
    if h_dir is None:
        h_dir = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    # Compute approach direction with vertical angle only
    v_angle = vertical_angle_deg if vertical_angle_deg is not None else 45.0

    # Use surface normal if vertical angle not specified
    if v_angle is None or vertical_angle_deg is None:
        normal_cam = camera.estimate_surface_normal_camera(
            depth, intr, u, v, depth_scale, window=PATCH_WINDOW
        )
        if normal_cam is None:
            normal_cam = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        normal_base = camera.camera_to_base_vector(normal_cam)
        normal_base = normalize(normal_base)
        if normal_base is None:
            normal_base = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        if normal_base[2] < 0:
            normal_base = -normal_base
        approach_dir = -normal_base
    else:
        approach_dir = compute_approach_direction(surface_base, h_dir, v_angle)

    # Resolved final pitch (vertical tilt) of the approach direction, in degrees.
    resolved_pitch_deg = math.degrees(math.asin(max(-1.0, min(1.0, -float(approach_dir[2])))))

    # Final-approach axis: the gripper's SCALED heading (tool-Z) at the END of the
    # safe->approach Bézier curve. Backing the standoff off along THIS axis (rather
    # than the surface normal) makes the final straight reach come IN at the same
    # scaled curve angle the gripper is actually pointing -- so heading_angle_scale
    # now affects the approach pose (scale 0 -> along the chord, scale 1 -> full
    # curve heading). The heading depends on where the curve ends, so refine the
    # axis a few times to resolve the mild circular dependency.
    safe_tip_base = np.array([SAFE_POSE["x"], SAFE_POSE["y"], SAFE_POSE["z"]], dtype=np.float64)
    safe_orient = {"rx": SAFE_POSE["rx"], "ry": SAFE_POSE["ry"], "rz": SAFE_POSE["rz"]}
    reach_axis = approach_dir
    for _ in range(3):
        standoff = surface_base - reach_axis * APPROACH_CLEARANCE_M
        end_pose = sample_bezier_motion_poses(
            safe_tip_base, standoff, safe_orient,
            horizontal_angle_deg=curve.horizontal_angle_deg,
            control_length_factor=curve.control_length_factor,
            num_points=21,
            heading_start_t=curve.heading_start_t,
            heading_angle_scale=curve.heading_angle_scale,
            pitch_deg=resolved_pitch_deg,
        )[-1]
        R = rotation_from_euler_zyx(end_pose["rx"], end_pose["ry"], end_pose["rz"])
        refined = normalize(R[:, 2])
        if refined is not None:
            reach_axis = refined

    # Approach/pick standoffs along the scaled-heading reach axis.
    approach_tip_base = surface_base - reach_axis * APPROACH_CLEARANCE_M
    pick_tip_base = surface_base - reach_axis * PICK_CLEARANCE_M

    approach_pose = pose_from_tip_and_direction(approach_tip_base, reach_axis, GRIPPER_TIP_OFFSET_M)
    pick_pose = pose_from_tip_and_direction(pick_tip_base, reach_axis, GRIPPER_TIP_OFFSET_M)

    if approach_pose is None or pick_pose is None:
        return None

    approach_pose_cmd = pose_dict_to_list(approach_pose)
    pick_pose_cmd = pose_dict_to_list(pick_pose)

    h_angle = horizontal_angle_deg if horizontal_angle_deg is not None else 0.0

    # Direction from approach to pick (trajectory direction)
    traj_direction = normalize(pick_tip_base - approach_tip_base)
    if traj_direction is None:
        traj_direction = np.array([0.0, 0.0, -1.0], dtype=np.float64)

    # Perpendicular direction in xy plane for curve offset
    perp_dir = normalize(np.array([-traj_direction[1], traj_direction[0], 0.0], dtype=np.float64))
    if perp_dir is None:
        perp_dir = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    control_offset_dir = perp_dir * math.sin(math.radians(h_angle))

    # Sample points along curved spline path (safe->approach) for the visualization
    safe_tip_base = np.array([SAFE_POSE["x"], SAFE_POSE["y"], SAFE_POSE["z"]], dtype=np.float64)
    num_samples = 15
    sampled_poses = []
    for i in range(num_samples + 1):
        t = i / num_samples
        sampled_pos = safe_tip_base * (1 - t) + approach_tip_base * t
        curve_strength = 4 * t * (1 - t)
        sampled_pos = sampled_pos + control_offset_dir * (0.15 * curve_strength)
        sampled_pose = pose_from_tip_and_direction(sampled_pos, approach_dir, GRIPPER_TIP_OFFSET_M)
        if sampled_pose is not None:
            sampled_poses.append(sampled_pose)

    viz_data = build_curve_viz(safe_tip_base, approach_tip_base, sampled_poses, curve,
                               pitch_deg=resolved_pitch_deg)

    return {
        "pixel": [int(u), int(v)],
        "vertical_pitch_deg": float(resolved_pitch_deg),
        "depth_m": float(depth_m),
        "camera_xyz_m": [float(xyz_cam[0]), float(xyz_cam[1]), float(xyz_cam[2])],
        "base_xyz_m": [float(xyz_base[0]), float(xyz_base[1]), float(xyz_base[2])],
        "raw_target_base_m": [float(xyz_base_raw[0]), float(xyz_base_raw[1]), float(xyz_base_raw[2])],
        "surface_normal_base": [float(approach_dir[0]), float(approach_dir[1]), float(approach_dir[2])],
        "approach_tip_base_m": [float(approach_tip_base[0]), float(approach_tip_base[1]), float(approach_tip_base[2])],
        "target_pose_m": [float(surface_base[0]), float(surface_base[1]), float(surface_base[2])],
        "grab_z": grab_z,
        "approach_vertical_deg": float(vertical_angle_deg if vertical_angle_deg is not None else 45.0),
        "approach_horizontal_deg": float(horizontal_angle_deg if horizontal_angle_deg is not None else 0.0),
        "approach_pose": approach_pose,
        "pick_pose": pick_pose,
        "wrist_command_pose": approach_pose,
        "approach_pose_cmd": approach_pose_cmd,
        "pick_pose_cmd": pick_pose_cmd,
        "wrist_command_pose_cmd": approach_pose_cmd,
        "visualization": viz_data,
    }
