from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np

@dataclass
class RawTelemetrySample:
    """A single raw joint & pose telemetry sample with monotonic timestamp."""
    ts: float
    joint_pos: List[float]
    ee_pose: List[float]  # 7D: [x, y, z, qx, qy, qz, qw]
    gripper: float = 0.0

@dataclass
class RawFrameSample:
    """A single raw RGB-D frame sample with monotonic timestamp."""
    ts: float
    rgb: np.ndarray       # (H, W, 3) uint8
    depth: np.ndarray     # (H, W) float32 or uint16

@dataclass
class RawEpisodeBuffer:
    """In-memory buffer collecting raw samples during an active episode."""
    telemetry_samples: List[RawTelemetrySample] = field(default_factory=list)
    frame_samples: List[RawFrameSample] = field(default_factory=list)

    def is_empty(self) -> bool:
        return len(self.telemetry_samples) == 0 and len(self.frame_samples) == 0

    def clear(self) -> None:
        self.telemetry_samples.clear()
        self.frame_samples.clear()

@dataclass
class RawEpisodeData:
    """Complete unaligned raw episode arrays ready for HDF5 persistence."""
    joint_pos: np.ndarray      # (N_joints, n_joints) float32
    joint_ts: np.ndarray       # (N_joints,) float64 (elapsed seconds from t_start)
    ee_pose: np.ndarray        # (N_joints, 7) float32
    gripper: np.ndarray        # (N_joints,) float32
    rgb: np.ndarray            # (N_frames, H, W, 3) uint8
    depth: np.ndarray          # (N_frames, H, W) float32 or uint16
    frame_ts: np.ndarray       # (N_frames,) float64 (elapsed seconds from t_start)
    
    language_instruction: str = ""
    object_class: str = ""
    success: bool = True
    camera_intrinsics: Dict[str, Any] = field(default_factory=dict)
    spline_params: Dict[str, Any] = field(default_factory=dict)
    t_start: float = 0.0
    t_end: float = 0.0
    
    actions: Optional[np.ndarray] = None    # (N_actions, action_dim) float32
    action_ts: Optional[np.ndarray] = None  # (N_actions,) float64

@dataclass
class ResampledEpisodeData:
    """Resampled episode data aligned onto a uniform target_hz timestamp grid."""
    rgb: np.ndarray            # (T, H, W, 3) uint8
    depth: np.ndarray          # (T, H, W) float32/uint16
    joint_pos: np.ndarray      # (T, n_joints) float32
    ee_pose: np.ndarray        # (T, 7) float32
    gripper: np.ndarray        # (T,) float32
    actions: np.ndarray        # (T, action_dim) float32
    timestamps: np.ndarray     # (T,) float64 uniform grid

    language_instruction: str = ""
    object_class: str = ""
    success: bool = True
    camera_intrinsics: Dict[str, Any] = field(default_factory=dict)
    spline_params: Dict[str, Any] = field(default_factory=dict)
    flagged_gap: bool = False

@dataclass
class BatchRecord:
    """Data transfer model representing a row in SQLite batches table."""
    batch_id: str
    object_class: str
    created_at: str
    target_episodes: int
    completed_episodes: int = 0
    status: str = "running"  # running, paused, completed, crashed
    randomization_params: str = "{}"
    target_hz: float = 30.0

@dataclass
class EpisodeRecord:
    """Data transfer model representing a row in SQLite episodes table."""
    episode_id: str
    batch_id: str
    object_class: str
    language_instruction: str
    instruction_source: str = "auto_template"  # auto_template, human_edited
    success: bool = True
    success_source: str = "auto"              # auto, human_override
    hdf5_path: str = ""
    duration_s: float = 0.0
    n_frames: int = 0
    flagged_gap: bool = False
    yolo_confidence: Optional[float] = None
    export_split: str = "unassigned"           # train, val, test, unassigned
