from typing import Tuple, Dict, Any, Optional
import numpy as np
from backend.models.episode import RawEpisodeData, ResampledEpisodeData

def resample_raw_episode(
    raw_data: RawEpisodeData,
    target_hz: float = 30.0,
    gap_threshold_sec: float = 0.1,
) -> ResampledEpisodeData:
    """
    Post-process unaligned raw episode data into a uniform target_hz grid.
    
    Linear interpolation is applied to joint_pos, ee_pose, and gripper.
    Nearest-neighbor matching (via hardware-adjacent timestamps) is applied to RGB & Depth.
    Target actions are derived as future joint targets q_{t+1}.
    Telemetry gap tolerance check sets flagged_gap=True if max gap > gap_threshold_sec.
    """
    if len(raw_data.joint_ts) == 0:
        raise ValueError("Cannot resample episode with empty joint_ts array.")

    t_start = float(raw_data.joint_ts[0])
    t_end = float(raw_data.joint_ts[-1])
    duration = t_end - t_start

    if duration <= 0:
        # Single sample or zero duration edge case
        timestamps = np.array([0.0], dtype=np.float64)
    else:
        dt = 1.0 / target_hz
        num_steps = max(1, int(np.round(duration * target_hz)) + 1)
        timestamps = np.linspace(0.0, duration, num_steps, dtype=np.float64)

    # Normalize raw timestamps to start at 0.0
    norm_joint_ts = raw_data.joint_ts - t_start

    # 1. Resample joint_pos (N, n_joints)
    n_joints = raw_data.joint_pos.shape[1] if raw_data.joint_pos.ndim > 1 else 1
    resampled_joint_pos = np.zeros((len(timestamps), n_joints), dtype=np.float32)
    for j in range(n_joints):
        col = raw_data.joint_pos[:, j] if raw_data.joint_pos.ndim > 1 else raw_data.joint_pos
        resampled_joint_pos[:, j] = np.interp(timestamps, norm_joint_ts, col)

    # 2. Resample ee_pose (N, 7)
    n_pose_dims = raw_data.ee_pose.shape[1] if raw_data.ee_pose.ndim > 1 else 7
    resampled_ee_pose = np.zeros((len(timestamps), n_pose_dims), dtype=np.float32)
    for p in range(n_pose_dims):
        col = raw_data.ee_pose[:, p] if raw_data.ee_pose.ndim > 1 else raw_data.ee_pose
        resampled_ee_pose[:, p] = np.interp(timestamps, norm_joint_ts, col)

    # 3. Resample gripper (N,)
    resampled_gripper = np.interp(timestamps, norm_joint_ts, raw_data.gripper).astype(np.float32)

    # 4. Nearest-neighbor matching for RGB and Depth frames
    if len(raw_data.frame_ts) > 0 and raw_data.rgb.size > 0:
        norm_frame_ts = raw_data.frame_ts - t_start
        frame_indices = [
            int(np.argmin(np.abs(norm_frame_ts - t))) for t in timestamps
        ]
        resampled_rgb = raw_data.rgb[frame_indices]
        resampled_depth = raw_data.depth[frame_indices]
    else:
        resampled_rgb = np.zeros((len(timestamps), 0, 0, 3), dtype=np.uint8)
        resampled_depth = np.zeros((len(timestamps), 0, 0), dtype=np.float32)

    # 5. Derive actions (target q_{t+1})
    resampled_actions = np.zeros_like(resampled_joint_pos, dtype=np.float32)
    if len(resampled_joint_pos) > 1:
        resampled_actions[:-1] = resampled_joint_pos[1:]
        resampled_actions[-1] = resampled_joint_pos[-1]
    else:
        resampled_actions[0] = resampled_joint_pos[0]

    # 6. Check for telemetry gaps
    flagged_gap = False
    if len(norm_joint_ts) > 1:
        max_joint_gap = float(np.max(np.diff(norm_joint_ts)))
        if max_joint_gap > gap_threshold_sec:
            flagged_gap = True

    if len(raw_data.frame_ts) > 1:
        norm_frame_ts = raw_data.frame_ts - t_start
        max_frame_gap = float(np.max(np.diff(norm_frame_ts)))
        if max_frame_gap > gap_threshold_sec:
            flagged_gap = True

    return ResampledEpisodeData(
        rgb=resampled_rgb,
        depth=resampled_depth,
        joint_pos=resampled_joint_pos,
        ee_pose=resampled_ee_pose,
        gripper=resampled_gripper,
        actions=resampled_actions,
        timestamps=timestamps,
        language_instruction=raw_data.language_instruction,
        object_class=raw_data.object_class,
        success=raw_data.success,
        camera_intrinsics=raw_data.camera_intrinsics,
        spline_params=raw_data.spline_params,
        flagged_gap=flagged_gap,
    )
