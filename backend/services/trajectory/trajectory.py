import numpy as np
from dataclasses import dataclass
from typing import Optional

from services.trajectory.bezier import CubicBezierCurve
from services.trajectory.equal_arc_length import ArcLengthLUT
from models.robot import Pose


from dataclasses import dataclass, field
from numpy.typing import NDArray
import numpy as np

@dataclass
class TrajectoryParams:
    lift_height: float = 0.02
    approach_height: float = 0.02
    retreat_direction: NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, 0.0, 1.0])
    )
    approach_direction: NDArray[np.float64] = field(
        default_factory=lambda: np.array([0.0, 0.0, -1.0])
    )
    n_waypoints: int = 3
    arc_length_samples: int = 200

def _slerp(q0: np.ndarray, q1: np.ndarray, t: np.ndarray) -> np.ndarray:
    """
    Spherical linear interpolation between two unit quaternions (xyzw).
    t: scalar or (N,) array. Returns (4,) or (N, 4).
    """
    q0 = q0 / np.linalg.norm(q0)
    q1 = q1 / np.linalg.norm(q1)

    dot = np.dot(q0, q1)
    # Take the shorter path: if dot < 0, negate one end (q and -q represent
    # the same rotation, but naive slerp between them takes the long way).
    if dot < 0.0:
        q1 = -q1
        dot = -dot

    dot = np.clip(dot, -1.0, 1.0)
    theta_0 = np.arccos(dot)

    t = np.atleast_1d(t)
    if theta_0 < 1e-6:
        # Nearly identical orientations: linear interp is numerically safer
        # than dividing by a near-zero sin(theta_0).
        result = q0[None, :] + t[:, None] * (q1 - q0)[None, :]
        result /= np.linalg.norm(result, axis=1, keepdims=True)
    else:
        sin_theta_0 = np.sin(theta_0)
        theta = theta_0 * t
        s0 = np.sin(theta_0 - theta) / sin_theta_0
        s1 = np.sin(theta) / sin_theta_0
        result = s0[:, None] * q0[None, :] + s1[:, None] * q1[None, :]

    return result[0] if result.shape[0] == 1 else result


def build_bezier(current: Pose, target: Pose, params: TrajectoryParams) -> CubicBezierCurve:
    """
    Derive the two Bezier control points from physically meaningful
    parameters rather than exposing them as free per-episode inputs.

    C1 forces departure along retreat_direction (e.g. straight up off the
    table before curving toward the target).
    C2 forces arrival along approach_direction (e.g. straight down into
    the grasp) instead of a shallow, unpredictable final angle.
    """
    p0 = current.position
    p3 = target.position
    c1 = p0 + params.retreat_direction * params.lift_height
    c2 = p3 - params.approach_direction * params.approach_height
    return CubicBezierCurve(p0=p0, p1=c1, p2=c2, p3=p3)


def generate_trajectory(
    current: Pose,
    target: Pose,
    params: Optional[TrajectoryParams] = None,
) -> list[Pose]:
    """
    Generate a constant-velocity-along-path list of waypoint poses from
    current -> target. Position comes from the arc-length-reparameterized
    Bezier curve; rotation comes from a plain slerp sharing the same
    normalized progress value, so both finish together.

    This returns *poses* (position + orientation per waypoint) — full
    poses are what the robot's IK needs at each step, even though rotation
    was generated independently of position.
    """
    params = params or TrajectoryParams()

    curve = build_bezier(current, target, params)
    lut = ArcLengthLUT(curve, resolution=params.arc_length_samples)

    t_values = lut.uniform_t_samples(params.n_waypoints)          # Bezier param, arc-length-even
    s_values = np.linspace(0.0, 1.0, params.n_waypoints)          # normalized progress, for rotation

    positions = curve.evaluate(t_values)                          # (N, 3)
    orientations = _slerp(current.orientation, target.orientation, s_values)  # (N, 4)

    return [
        Pose(position=positions[i], orientation=orientations[i])
        for i in range(params.n_waypoints)
    ]