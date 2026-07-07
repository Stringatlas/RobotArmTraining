import numpy as np
from dataclasses import dataclass


@dataclass
class CubicBezierCurve:
    """Represents a 3D cubic Bezier curve defined by 4 control points."""
    p0: np.ndarray  # Start point
    p1: np.ndarray  # Control point 1
    p2: np.ndarray  # Control point 2
    p3: np.ndarray  # End point

    def evaluate(self, t):
        """
        Evaluate the curve at parameter t in [0, 1].

        t may be a scalar or a 1D array of shape (N,). Returns shape (3,)
        for scalar t, or (N, 3) for array t.
        """
        t = np.clip(np.asarray(t, dtype=float), 0.0, 1.0)
        mt = 1.0 - t

        # Cubic Bezier formula: B(t) = (1-t)^3*P0 + 3*(1-t)^2*t*P1 + 3*(1-t)*t^2*P2 + t^3*P3
        coeff0 = mt**3
        coeff1 = 3 * mt**2 * t
        coeff2 = 3 * mt * t**2
        coeff3 = t**3

        if t.ndim == 0:
            return coeff0 * self.p0 + coeff1 * self.p1 + coeff2 * self.p2 + coeff3 * self.p3

        # Broadcast (N,) coeffs against (3,) points -> (N, 3)
        return (
            np.outer(coeff0, self.p0) +
            np.outer(coeff1, self.p1) +
            np.outer(coeff2, self.p2) +
            np.outer(coeff3, self.p3)
        )

    def derivative(self, t):
        """
        Evaluate the first derivative (velocity) at parameter t.
        Same scalar/array shape behavior as evaluate().
        """
        t = np.clip(np.asarray(t, dtype=float), 0.0, 1.0)
        mt = 1.0 - t

        # B'(t) = 3*(1-t)^2*(P1-P0) + 6*(1-t)*t*(P2-P1) + 3*t^2*(P3-P2)
        d0, d1, d2 = (self.p1 - self.p0), (self.p2 - self.p1), (self.p3 - self.p2)

        if t.ndim == 0:
            return 3 * mt**2 * d0 + 6 * mt * t * d1 + 3 * t**2 * d2

        return (
            3 * np.outer(mt**2, d0) +
            6 * np.outer(mt * t, d1) +
            3 * np.outer(t**2, d2)
        )

    def arc_length(self, t_start: float = 0.0, t_end: float = 1.0, samples: int = 100) -> float:
        """Approximate arc length between t_start and t_end using polyline integration."""
        t_start = float(np.clip(t_start, 0.0, 1.0))
        t_end = float(np.clip(t_end, 0.0, 1.0))
        if t_start >= t_end:
            return 0.0

        t_values = np.linspace(t_start, t_end, samples)
        points = self.evaluate(t_values)  # (samples, 3)
        segment_lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
        return float(np.sum(segment_lengths))

    def total_arc_length(self, samples: int = 100) -> float:
        """Get total arc length of the entire curve."""
        return self.arc_length(0.0, 1.0, samples)