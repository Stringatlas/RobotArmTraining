import numpy as np
from services.trajectory.bezier import CubicBezierCurve


class ArcLengthLUT:
    def __init__(self, curve: CubicBezierCurve, resolution: int = 200):
        """
        Build the s -> t lookup table.

        resolution: number of samples used to approximate the curve's
        arc-length profile. 200 is comfortably enough for pick-and-place
        scale trajectories (curves spanning tens of centimeters); raise it
        only if control points are far apart or curvature is extreme.
        """
        self.curve = curve
        t_samples = np.linspace(0.0, 1.0, resolution)
        points = curve.evaluate(t_samples)  # (resolution, 3)

        segment_lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
        cumulative = np.concatenate([[0.0], np.cumsum(segment_lengths)])

        self.total_length = float(cumulative[-1])
        self._t_samples = t_samples
        # Normalize cumulative arc length to [0, 1] for lookup by fraction.
        self._s_normalized = (
            cumulative / self.total_length if self.total_length > 0 else cumulative
        )

    def t_at_arc_fraction(self, s: float | np.ndarray):
        """
        Given normalized arc-length fraction(s) s in [0, 1], return the
        corresponding Bezier t value(s) via linear interpolation on the LUT.
        """
        s = np.clip(s, 0.0, 1.0)
        return np.interp(s, self._s_normalized, self._t_samples)

    def uniform_t_samples(self, n: int) -> np.ndarray:
        """
        Convenience: n values of t such that curve.evaluate(t) are evenly
        spaced by arc length (constant-velocity sampling along the path).
        """
        s_values = np.linspace(0.0, 1.0, n)
        return self.t_at_arc_fraction(s_values)