import numpy as np
from dataclasses import dataclass

@dataclass
class Pose:
    position: np.ndarray
    orientation: np.ndarray  # ZYX Euler angle