"""
Pose calculation utilities for approach and pick poses.

Computes gripper orientations based on target points and approach angles.
"""

import numpy as np
import math
from typing import List, Dict, Tuple


def normalize(vec):
    """Normalize a vector, return None if zero-length."""
    vec = np.asarray(vec, dtype=np.float64)
    norm = float(np.linalg.norm(vec))
    if norm < 1e-9:
        return None
    return vec / norm


def rotation_matrix_to_euler_zyx(rot):
    """Convert rotation matrix to Euler angles (ZYX convention)."""
    rot = np.asarray(rot, dtype=np.float64)
    sy = math.sqrt(rot[0, 0] ** 2 + rot[1, 0] ** 2)

    singular = sy < 1e-8
    if not singular:
        rx = math.atan2(rot[2, 1], rot[2, 2])
        ry = math.atan2(-rot[2, 0], sy)
        rz = math.atan2(rot[1, 0], rot[0, 0])
    else:
        rx = math.atan2(-rot[1, 2], rot[1, 1])
        ry = math.atan2(-rot[2, 0], sy)
        rz = 0.0

    def _norm(a):
        a = float(a)
        while a <= -math.pi:
            a += 2 * math.pi
        while a > math.pi:
            a -= 2 * math.pi
        if abs(a) < 1e-9:
            return 0.0
        return a

    rx, ry, rz = _norm(rx), _norm(ry), _norm(rz)
    return rx, ry, rz


def rotation_from_euler_zyx(rx, ry, rz):
    """Build rotation matrix from ZYX Euler angles (R = Rz @ Ry @ Rx)."""
    cx, sx = math.cos(rx), math.sin(rx)
    cy, sy = math.cos(ry), math.sin(ry)
    cz, sz = math.cos(rz), math.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def matrix_to_quaternion(R):
    """Rotation matrix -> unit quaternion [w, x, y, z]."""
    R = np.asarray(R, dtype=np.float64)
    tr = R[0, 0] + R[1, 1] + R[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w = 0.25 * s
        x = (R[2, 1] - R[1, 2]) / s
        y = (R[0, 2] - R[2, 0]) / s
        z = (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w = (R[2, 1] - R[1, 2]) / s
        x = 0.25 * s
        y = (R[0, 1] + R[1, 0]) / s
        z = (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w = (R[0, 2] - R[2, 0]) / s
        x = (R[0, 1] + R[1, 0]) / s
        y = 0.25 * s
        z = (R[1, 2] + R[2, 1]) / s
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w = (R[1, 0] - R[0, 1]) / s
        x = (R[0, 2] + R[2, 0]) / s
        y = (R[1, 2] + R[2, 1]) / s
        z = 0.25 * s
    q = np.array([w, x, y, z], dtype=np.float64)
    return q / np.linalg.norm(q)


def quaternion_to_matrix(q):
    """Unit quaternion [w, x, y, z] -> rotation matrix."""
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ], dtype=np.float64)


def quaternion_slerp(q0, q1, t):
    """Spherical linear interpolation between two unit quaternions (shortest path)."""
    q0 = np.asarray(q0, dtype=np.float64)
    q1 = np.asarray(q1, dtype=np.float64)
    dot = float(np.dot(q0, q1))
    if dot < 0.0:          # take the shortest path
        q1 = -q1
        dot = -dot
    if dot > 0.9995:       # nearly identical -> linear blend
        q = q0 + t * (q1 - q0)
        return q / np.linalg.norm(q)
    theta_0 = math.acos(max(-1.0, min(1.0, dot)))
    theta = theta_0 * t
    q2 = q1 - q0 * dot
    q2 = q2 / np.linalg.norm(q2)
    return q0 * math.cos(theta) + q2 * math.sin(theta)


def slerp_vectors(v0, v1, s):
    """Spherical interpolation between two unit vectors.

    The result lies on the great circle from v0 to v1, at an angle EXACTLY
    s * angle(v0, v1) away from v0. So scaling s scales the angular deviation
    linearly (s=0.5 of a 40deg offset -> 20deg offset), not the raw vector.
    """
    a = normalize(v0)
    b = normalize(v1)
    if a is None or b is None:
        return b if b is not None else a
    dot = float(np.clip(np.dot(a, b), -1.0, 1.0))
    theta = math.acos(dot)
    if theta < 1e-6:
        return b
    sin_t = math.sin(theta)
    return (math.sin((1.0 - s) * theta) / sin_t) * a + (math.sin(s * theta) / sin_t) * b


def compute_approach_direction(target_point, horizontal_direction,
                              vertical_angle_deg=45.0):
    """
    Compute approach direction from vertical angle.

    Args:
        target_point: Target position in base frame (3D)
        horizontal_direction: Horizontal direction from base to target (normalized)
        vertical_angle_deg: Angle from horizontal to vertical (0=flat, 90=vertical)

    Returns:
        Approach direction vector (normalized), pointing INTO the surface
    """
    target = np.asarray(target_point, dtype=np.float64)
    h_dir = normalize(horizontal_direction)

    if h_dir is None:
        h_dir = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    # Convert angle to radians
    v_angle_rad = math.radians(float(vertical_angle_deg))

    # Create approach direction from vertical angle
    # This goes from purely horizontal (h_dir) toward vertical (up)
    horizontal_component = math.cos(v_angle_rad)  # How much along h_dir
    vertical_component = math.sin(v_angle_rad)    # How much upward

    approach = h_dir * horizontal_component + np.array([0.0, 0.0, vertical_component])

    # Normalize to unit vector
    approach = normalize(approach)

    if approach is None:
        approach = np.array([0.0, 0.0, 1.0])

    # The approach direction points INTO the surface (opposite of upward normal)
    approach_dir = -approach

    return approach_dir


def compute_spline_control_offset(horizontal_direction, horizontal_angle_deg=0.0):
    """
    Compute control point offset direction for Bézier spline based on horizontal angle.

    This creates an offset perpendicular to the horizontal direction, which is used
    to position the Bézier curve control points.

    Args:
        horizontal_direction: Horizontal direction from base to target (normalized)
        horizontal_angle_deg: Angle offset (-90 to +90). Determines curve direction.
                             0° = along h_dir, ±90° = perpendicular to h_dir

    Returns:
        Offset direction vector (normalized) for positioning control points
    """
    h_dir = normalize(horizontal_direction)
    if h_dir is None:
        h_dir = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    # Create a perpendicular direction in the xy plane
    # If h_dir points in direction (x, y), perpendicular is (-y, x)
    perp_dir = np.array([-h_dir[1], h_dir[0], 0.0], dtype=np.float64)
    perp_dir = normalize(perp_dir)

    if perp_dir is None:
        perp_dir = np.array([0.0, 1.0, 0.0], dtype=np.float64)

    # Convert angle to radians
    h_angle_rad = math.radians(float(horizontal_angle_deg))

    # Mix between h_dir and perp_dir based on angle
    # At 0°: use h_dir (approach along line to target)
    # At ±90°: use perp_dir (approach perpendicular to line)
    cos_angle = math.cos(h_angle_rad)
    sin_angle = math.sin(h_angle_rad)

    offset_dir = h_dir * cos_angle + perp_dir * sin_angle
    offset_dir = normalize(offset_dir)

    if offset_dir is None:
        offset_dir = np.array([1.0, 0.0, 0.0], dtype=np.float64)

    return offset_dir


def pose_from_tip_and_direction(tip_base, approach_dir, gripper_tip_offset_m=0.0):
    """
    Calculate gripper pose from tip position and approach direction.

    Args:
        tip_base: Gripper tip position in base frame
        approach_dir: Direction the gripper should approach (normalized)
        gripper_tip_offset_m: Distance from wrist to gripper tip

    Returns:
        Pose dict with keys: x, y, z, rx, ry, rz
    """
    approach_dir = normalize(approach_dir)
    if approach_dir is None:
        return None

    # Tool must point INTO surface
    target_z = approach_dir

    # Position of wrist
    wrist_pos = tip_base - approach_dir * gripper_tip_offset_m

    # --- Build orthonormal frame ---
    world_up = np.array([0.0, 0.0, 1.0])
    world_x = np.array([1.0, 0.0, 0.0])

    # Choose a reference vector not parallel to target_z
    if abs(np.dot(target_z, world_up)) > 0.99:
        ref = world_x
    else:
        ref = world_up

    # Tool X axis
    tool_x = np.cross(ref, target_z)
    tool_x = normalize(tool_x)

    # Tool Y axis
    tool_y = np.cross(target_z, tool_x)

    # Rotation matrix: columns = tool axes in world frame
    rot = np.stack([tool_x, tool_y, target_z], axis=1)

    # Convert to Euler
    rx, ry, rz = rotation_matrix_to_euler_zyx(rot)

    return {
        "x": float(wrist_pos[0]),
        "y": float(wrist_pos[1]),
        "z": float(wrist_pos[2]),
        "rx": float(rx),
        "ry": float(ry),
        "rz": float(rz),
    }


def pose_dict_to_list(pose):
    """Convert pose dict to 6-element list [x, y, z, rz, ry, rx]."""
    if pose is None:
        return None

    def _r3(v):
        out = round(float(v), 3)
        return 0.0 if abs(out) < 1e-9 else out

    try:
        return [
            _r3(pose["x"]),
            _r3(pose["y"]),
            _r3(pose["z"]),
            _r3(pose["rz"]),
            _r3(pose["ry"]),
            _r3(pose["rx"]),
        ]
    except Exception:
        return None


def compute_incline_angle(approach_dir):
    """
    Compute the incline angle (0=flat, 90=vertical).

    Args:
        approach_dir: Approach direction vector

    Returns:
        Angle in degrees
    """
    nz = abs(float(approach_dir[2]))
    nz = max(-1.0, min(1.0, nz))
    return math.degrees(math.asin(nz))


def compute_lateral_angle(approach_dir, horizontal_direction):
    """
    Compute the lateral (horizontal) offset angle in degrees.

    Args:
        approach_dir: Approach direction vector
        horizontal_direction: Reference horizontal direction

    Returns:
        Angle in degrees (-180 to 180)
    """
    h_dir = normalize(horizontal_direction)
    if h_dir is None:
        return 0.0

    # Project approach direction onto xy plane
    approach_xy = np.array([approach_dir[0], approach_dir[1], 0.0])
    approach_xy = normalize(approach_xy)

    if approach_xy is None:
        return 0.0

    # Angle between h_dir and approach_xy
    dot_product = np.dot(h_dir, approach_xy)
    dot_product = max(-1.0, min(1.0, dot_product))

    base_angle = math.degrees(math.acos(dot_product))

    # Determine sign using cross product
    cross = np.cross(h_dir, approach_xy)
    if cross[2] < 0:  # Z component of cross product
        base_angle = -base_angle

    return base_angle


def bezier_control_points(start_pos, end_pos, horizontal_angle_deg=0.0,
                          control_length_factor=0.667):
    """
    Compute the two cubic-Bézier control points (p1, p2) for the curved path.

    The lateral SWEEP is set directly by `horizontal_angle_deg`, measured in the
    xy plane against the (xy-projected) straight-line distance between start and
    end -- i.e. exactly what the top-down view shows:

        sweep_ratio = horizontal_angle_deg / 45

    so 45deg -> max sideways bulge ~= the straight-line distance, and 90deg ->
    ~= twice the straight-line distance. The sign of the angle picks the side.

    `control_length_factor` now controls ONLY how far the control points sit
    ALONG the chord (curve roundness/elongation); it no longer affects the
    sweep width. Both control points offset to the same side -> symmetric bulge.

    Returns:
        (p1, p2) as 3D numpy arrays.
    """
    start = np.asarray(start_pos, dtype=np.float64)
    end = np.asarray(end_pos, dtype=np.float64)

    direction = end - start
    length = float(np.linalg.norm(direction))
    d_hat = direction / length if length > 1e-9 else np.array([1.0, 0.0, 0.0])

    # Sweep is measured against the xy-projected chord (the top-down "straight
    # line distance") and applied perpendicular to it in the xy plane.
    chord_xy = float(math.hypot(direction[0], direction[1]))
    perp = normalize(np.array([-direction[1], direction[0], 0.0], dtype=np.float64))
    if perp is None:
        perp = np.array([0.0, 1.0, 0.0], dtype=np.float64)

    # A symmetric cubic with equal perpendicular control-point offsets bulges to
    # exactly 0.75 * offset at its midpoint (t=0.5), independent of the along-chord
    # placement. Invert that so the midpoint sweep hits the requested distance.
    sweep_ratio = float(horizontal_angle_deg) / 45.0
    perp_offset = (sweep_ratio * chord_xy) / 0.75

    arm_along = length * float(control_length_factor)
    p1 = start + arm_along * d_hat + perp_offset * perp
    p2 = end - arm_along * d_hat + perp_offset * perp
    return p1, p2


def orientation_from_direction(direction):
    """
    Build a gripper orientation (rx, ry, rz) whose tool Z axis points along
    `direction`. Uses the same orthonormal-frame convention as
    pose_from_tip_and_direction.

    Returns:
        (rx, ry, rz) Euler angles, or None if direction is degenerate.
    """
    rot = rotation_matrix_from_direction(direction)
    if rot is None:
        return None
    return rotation_matrix_to_euler_zyx(rot)


def rotation_matrix_from_direction(direction):
    """Rotation matrix whose tool-Z points along `direction` (base frame)."""
    target_z = normalize(direction)
    if target_z is None:
        return None

    world_up = np.array([0.0, 0.0, 1.0])
    world_x = np.array([1.0, 0.0, 0.0])

    # Reference vector not parallel to target_z
    if abs(np.dot(target_z, world_up)) > 0.99:
        ref = world_x
    else:
        ref = world_up

    tool_x = normalize(np.cross(ref, target_z))
    if tool_x is None:
        return None
    tool_y = np.cross(target_z, tool_x)

    return np.stack([tool_x, tool_y, target_z], axis=1)


def bezier_tangent_at(start, p1, p2, end, t):
    """Unit tangent (heading) of the cubic Bézier at parameter t."""
    mt = 1.0 - t
    deriv = (3 * mt ** 2) * (p1 - start) + (6 * mt * t) * (p2 - p1) + (3 * t ** 2) * (end - p2)
    n = normalize(deriv)
    return n if n is not None else normalize(end - start)


def sample_bezier_path(start_pos, end_pos, horizontal_angle_deg=0.0,
                       control_length_factor=0.667, num_points=21,
                       with_tangents=False):
    """
    Sample 3D points along the cubic Bézier curve used by the visualizer.

    Returns:
        If with_tangents is False: list of [x, y, z] points.
        If with_tangents is True:  list of (point[x,y,z], tangent[x,y,z]) tuples.
    """
    start = np.asarray(start_pos, dtype=np.float64)
    end = np.asarray(end_pos, dtype=np.float64)
    p1, p2 = bezier_control_points(start, end, horizontal_angle_deg, control_length_factor)

    points = []
    n = max(2, int(num_points))
    for i in range(n):
        t = i / (n - 1)
        mt = 1.0 - t
        pt = (mt ** 3) * start + (3 * mt ** 2 * t) * p1 + (3 * mt * t ** 2) * p2 + (t ** 3) * end
        if with_tangents:
            tan = bezier_tangent_at(start, p1, p2, end, t)
            points.append(([float(pt[0]), float(pt[1]), float(pt[2])],
                           [float(tan[0]), float(tan[1]), float(tan[2])]))
        else:
            points.append([float(pt[0]), float(pt[1]), float(pt[2])])
    return points


def _wrap_angle(a):
    while a <= -math.pi:
        a += 2 * math.pi
    while a > math.pi:
        a -= 2 * math.pi
    return a


def _lerp_angle(a, b, w):
    """Shortest-path interpolation between two angles (radians)."""
    return a + _wrap_angle(b - a) * w


def sample_bezier_motion_poses(start_pos, end_pos, base_orient,
                               horizontal_angle_deg=0.0, control_length_factor=0.667,
                               num_points=21, heading_start_t=0.5,
                               heading_angle_scale=1.0, pitch_deg=None):
    """
    Sample the full commanded poses (x, y, z, rx, ry, rz) along the Bézier curve.

    When pitch_deg is given the gripper holds a constant orientation for the entire
    path: pitch_deg applied to the chord direction (start→end projected to XY).
    Tangent-tracking and heading_start_t are ignored in that mode.

    When pitch_deg is None the orientation is held at base_orient for the first
    heading_start_t fraction, then ramps into tracing the curve tangent.

    heading_angle_scale decouples path width from gripper approach angle: 0 = follow
    the chord, 1 = follow the true bezier tangent.

    Returns:
        List of pose dicts {x, y, z, rx, ry, rz}.
    """
    start = np.asarray(start_pos, dtype=np.float64)
    end = np.asarray(end_pos, dtype=np.float64)
    chord = normalize(end - start)
    if chord is None:
        chord = np.array([1.0, 0.0, 0.0])

    samples = sample_bezier_path(start, end, horizontal_angle_deg,
                                 control_length_factor, num_points, with_tangents=True)

    s = max(0.0, min(1.0, float(heading_angle_scale)))

    # When pitch_deg is given: hold pitch constant, let yaw follow the bezier XY tangent.
    #
    # The base horizontal direction (horiz_base) is the XY direction from the robot
    # origin toward end_pos (approach-tip). This is the gripper's facing direction on
    # a straight-line path (what you'd get with horizontal_angle_deg=0).
    #
    # At each waypoint we measure how much the bezier tangent deviates from the XY
    # chord direction (the "swing angle"), then rotate horiz_base by that deviation
    # scaled by heading_angle_scale. This means:
    #   - horizontal=0  → tangent = chord everywhere → zero deviation → rz constant ✓
    #   - horizontal≠0  → tangent swings sideways  → rz follows the curve swing ✓
    #   - heading_angle_scale=0 → always face horiz_base (no swing)
    #   - heading_angle_scale=1 → full tangent swing
    # rx is always atan2(cos(pitch), -sin(pitch)) — purely a function of pitch_deg, never changes.
    if pitch_deg is not None:
        horiz_base = normalize(np.array([end[0], end[1], 0.0]))
        if horiz_base is None:
            horiz_base = np.array([-1.0, 0.0, 0.0])
        chord_xy = normalize(np.array([chord[0], chord[1], 0.0]))
        if chord_xy is None:
            chord_xy = horiz_base
        p_rad = math.radians(float(pitch_deg))
        n_s = len(samples)
        poses = []
        for i, (pt, tan) in enumerate(samples):
            t = i / (n_s - 1) if n_s > 1 else 0.0
            tan_xy = normalize(np.array([float(tan[0]), float(tan[1]), 0.0]))
            if tan_xy is None:
                tan_xy = chord_xy
            # Signed angle (radians) from chord_xy to tan_xy in the XY plane
            dev = math.atan2(
                chord_xy[0] * tan_xy[1] - chord_xy[1] * tan_xy[0],
                float(np.dot(chord_xy[:2], tan_xy[:2])),
            )
            # Before heading_start_t: hold base direction (no deviation).
            # At/after heading_start_t: directly track the tangent swing.
            a = 0.0 if t < heading_start_t else dev * s
            ca, sa = math.cos(a), math.sin(a)
            hf = np.array([horiz_base[0]*ca - horiz_base[1]*sa,
                           horiz_base[0]*sa + horiz_base[1]*ca, 0.0])
            # Tool-Z: face hf direction, tilted down by pitch_deg
            approach_d = hf * math.cos(p_rad) + np.array([0.0, 0.0, -math.sin(p_rad)])
            R = rotation_matrix_from_direction(approach_d)
            if R is not None:
                rx, ry, rz = rotation_matrix_to_euler_zyx(R)
            else:
                rx = float(base_orient.get("rx", 0.0))
                ry = float(base_orient.get("ry", 0.0))
                rz = float(base_orient.get("rz", 0.0))
            poses.append({"x": float(pt[0]), "y": float(pt[1]), "z": float(pt[2]),
                          "rx": rx, "ry": ry, "rz": rz})
        return poses

    b_rx = float(base_orient.get("rx", 0.0))
    b_ry = float(base_orient.get("ry", 0.0))
    b_rz = float(base_orient.get("rz", 0.0))
    base_q = matrix_to_quaternion(rotation_from_euler_zyx(b_rx, b_ry, b_rz))

    _, tan_end = samples[-1]
    end_dir = slerp_vectors(chord, np.asarray(tan_end, dtype=np.float64), s)
    end_R = rotation_matrix_from_direction(end_dir)
    target_q = matrix_to_quaternion(end_R) if end_R is not None else base_q

    n = len(samples)
    poses = []
    for i, (pt, tan) in enumerate(samples):
        t = i / (n - 1) if n > 1 else 0.0
        if t < heading_start_t:
            w = t / max(1e-9, heading_start_t)
            q = quaternion_slerp(base_q, target_q, w)
        else:
            head_dir = slerp_vectors(chord, np.asarray(tan, dtype=np.float64), s)
            head_R = rotation_matrix_from_direction(head_dir)
            if head_R is not None:
                w = (t - heading_start_t) / max(1e-9, (1.0 - heading_start_t))
                head_q = matrix_to_quaternion(head_R)
                q = quaternion_slerp(target_q, head_q, w)
            else:
                q = target_q
        rx, ry, rz = rotation_matrix_to_euler_zyx(quaternion_to_matrix(q))
        poses.append({"x": pt[0], "y": pt[1], "z": pt[2],
                      "rx": rx, "ry": ry, "rz": rz})
    return poses


def generate_spline_visualization(start_pos: np.ndarray,
                                 end_pos: np.ndarray,
                                 sampled_poses: List[Dict[str, float]],
                                 horizontal_angle_deg: float = 0.0,
                                 control_length_factor: float = 0.667,
                                 base_orient: Dict[str, float] = None,
                                 heading_start_t: float = 0.5,
                                 heading_angle_scale: float = 1.0,
                                 pitch_deg: float = None) -> Dict:
    """
    Generate 2D visualization data for a spline path.

    Projects the 3D path onto the xy plane for visualization.

    Control points are placed a fixed distance (1/3 of the start->end length)
    from their respective endpoints, each rotated by horizontal_angle_deg around
    the vertical (z) axis. Both rotate to the same side, giving a symmetric bulge.

    Args:
        start_pos: Starting position [x, y, z]
        end_pos: Ending position [x, y, z]
        sampled_poses: (unused) kept for backwards compatibility
        horizontal_angle_deg: Angle of the control point arms vs the straight line

    Returns:
        Dict with keys:
        - spline_points: List of [x, y] points along the spline (smooth curve)
        - sample_points: List of [x, y] positions of sampled waypoints
        - start: [x, y] start position
        - end: [x, y] end position
        - bounds: {min_x, max_x, min_y, max_y} for scaling visualization
    """
    start = np.asarray(start_pos, dtype=np.float64)
    end = np.asarray(end_pos, dtype=np.float64)

    # Shared control points (same math the motion uses)
    p1, p2 = bezier_control_points(start, end, horizontal_angle_deg, control_length_factor)

    def bezier_at(t):
        """Evaluate the cubic Bézier (3D) at parameter t."""
        mt = 1.0 - t
        return (mt ** 3) * start + (3 * mt ** 2 * t) * p1 + (3 * mt * t ** 2) * p2 + (t ** 3) * end

    # Sample the Bézier curve densely for the smooth green line ([x, y, z])
    spline_points = []
    num_samples = 100
    for i in range(num_samples + 1):
        point = bezier_at(i / num_samples)
        spline_points.append([float(point[0]), float(point[1]), float(point[2])])

    # Sample sparse waypoints with the SAME commanded orientation the motion uses
    # (so the labels show the actual rx/ry/rz that will be sent to the arm).
    num_waypoints = 21
    orient = base_orient if base_orient is not None else {"rx": 0.0, "ry": 0.0, "rz": 0.0}
    motion_poses = sample_bezier_motion_poses(
        start, end, orient,
        horizontal_angle_deg=horizontal_angle_deg,
        control_length_factor=control_length_factor,
        num_points=num_waypoints,
        heading_start_t=heading_start_t,
        heading_angle_scale=heading_angle_scale,
        pitch_deg=pitch_deg,
    )
    sample_points = []
    sample_points_3d = []
    for p in motion_poses:
        sample_points.append([float(p["x"]), float(p["y"]), float(p["z"])])
        sample_points_3d.append({
            "x": float(p["x"]),
            "y": float(p["y"]),
            "z": float(p["z"]),
            "rx": math.degrees(float(p["rx"])),
            "ry": math.degrees(float(p["ry"])),
            "rz": math.degrees(float(p["rz"])),
        })

    # Compute bounds for visualization scaling (xy and z)
    # Include control points so they are always visible on the canvas
    all_x = ([p[0] for p in spline_points] + [p[0] for p in sample_points]
             + [float(p1[0]), float(p2[0]), float(start[0]), float(end[0])])
    all_y = ([p[1] for p in spline_points] + [p[1] for p in sample_points]
             + [float(p1[1]), float(p2[1]), float(start[1]), float(end[1])])
    all_z = ([p[2] for p in spline_points] + [p[2] for p in sample_points]
             + [float(p1[2]), float(p2[2]), float(start[2]), float(end[2])])

    bounds = {
        "min_x": float(min(all_x)),
        "max_x": float(max(all_x)),
        "min_y": float(min(all_y)),
        "max_y": float(max(all_y)),
        "min_z": float(min(all_z)),
        "max_z": float(max(all_z)),
    }

    # Add padding to bounds
    x_range = bounds["max_x"] - bounds["min_x"]
    y_range = bounds["max_y"] - bounds["min_y"]
    z_range = bounds["max_z"] - bounds["min_z"]
    padding = 0.15

    bounds["min_x"] -= x_range * padding
    bounds["max_x"] += x_range * padding
    bounds["min_y"] -= y_range * padding
    bounds["max_y"] += y_range * padding
    bounds["min_z"] -= z_range * padding
    bounds["max_z"] += z_range * padding

    return {
        "spline_points": spline_points,
        "sample_points": sample_points,
        "sample_points_3d": sample_points_3d,
        "start": [float(start[0]), float(start[1]), float(start[2])],
        "end": [float(end[0]), float(end[1]), float(end[2])],
        "control_p1": [float(p1[0]), float(p1[1]), float(p1[2])],
        "control_p2": [float(p2[0]), float(p2[1]), float(p2[2])],
        "bounds": bounds,
    }
