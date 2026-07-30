import os
import json
from typing import Dict, Any, Union
import numpy as np
import h5py

from models.episode import RawEpisodeData, ResampledEpisodeData

def write_raw_episode_hdf5(raw_data: RawEpisodeData, file_path: str, compression: str = "lzf") -> str:
    """
    Write raw unaligned episode telemetry and frames directly to HDF5 under /raw/.
    
    Args:
        raw_data: RawEpisodeData instance containing raw arrays and timestamps.
        file_path: Path where the HDF5 file will be written.
        compression: Compression algorithm for frame datasets ('lzf', 'gzip', or None).
        
    Returns:
        Absolute path to the created HDF5 file.
    """
    os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
    
    with h5py.File(file_path, "w") as f:
        # Attributes at root level
        f.attrs["language_instruction"] = raw_data.language_instruction
        f.attrs["object_class"] = raw_data.object_class
        f.attrs["success"] = bool(raw_data.success)
        f.attrs["camera_intrinsics"] = json.dumps(raw_data.camera_intrinsics)
        f.attrs["spline_params"] = json.dumps(raw_data.spline_params)
        f.attrs["t_start"] = float(raw_data.t_start)
        f.attrs["t_end"] = float(raw_data.t_end)
        f.attrs["duration_s"] = float(raw_data.t_end - raw_data.t_start)

        # Raw datasets group
        raw_grp = f.create_group("raw")
        raw_grp.create_dataset("joint_pos", data=raw_data.joint_pos.astype(np.float32))
        raw_grp.create_dataset("joint_ts", data=raw_data.joint_ts.astype(np.float64))
        raw_grp.create_dataset("ee_pose", data=raw_data.ee_pose.astype(np.float32))
        raw_grp.create_dataset("gripper", data=raw_data.gripper.astype(np.float32))
        
        # Frames dataset (compressed if specified)
        if raw_data.rgb.size > 0:
            raw_grp.create_dataset("rgb", data=raw_data.rgb.astype(np.uint8), compression=compression)
        else:
            raw_grp.create_dataset("rgb", shape=(0, 0, 0, 3), dtype=np.uint8)

        if raw_data.depth.size > 0:
            raw_grp.create_dataset("depth", data=raw_data.depth, compression=compression)
        else:
            raw_grp.create_dataset("depth", shape=(0, 0, 0), dtype=np.float32)

        raw_grp.create_dataset("frame_ts", data=raw_data.frame_ts.astype(np.float64))

        if raw_data.actions is not None and raw_data.action_ts is not None:
            raw_grp.create_dataset("actions", data=raw_data.actions.astype(np.float32))
            raw_grp.create_dataset("action_ts", data=raw_data.action_ts.astype(np.float64))

    return os.path.abspath(file_path)

def write_resampled_group(
    h5_target: Union[str, h5py.File],
    resampled_data: ResampledEpisodeData,
    compression: str = "lzf"
) -> None:
    """
    Write or overwrite resampled uniform grid datasets (/observations/ and /actions) in HDF5 file.
    
    Args:
        h5_target: File path string or active h5py.File handle.
        resampled_data: ResampledEpisodeData containing aligned arrays.
        compression: Compression algorithm for RGB/Depth datasets.
    """
    def _write_data(f: h5py.File):
        f.attrs["flagged_gap"] = bool(resampled_data.flagged_gap)

        if "observations" in f:
            del f["observations"]
        if "actions" in f:
            del f["actions"]

        obs_grp = f.create_group("observations")
        obs_grp.create_dataset("rgb", data=resampled_data.rgb.astype(np.uint8), compression=compression)
        obs_grp.create_dataset("depth", data=resampled_data.depth, compression=compression)
        obs_grp.create_dataset("joint_pos", data=resampled_data.joint_pos.astype(np.float32))
        obs_grp.create_dataset("ee_pose", data=resampled_data.ee_pose.astype(np.float32))
        obs_grp.create_dataset("gripper", data=resampled_data.gripper.astype(np.float32))
        obs_grp.create_dataset("timestamps", data=resampled_data.timestamps.astype(np.float64))

        f.create_dataset("actions", data=resampled_data.actions.astype(np.float32))

    if isinstance(h5_target, str):
        with h5py.File(h5_target, "a") as f:
            _write_data(f)
    else:
        _write_data(h5_target)

def read_episode_hdf5(file_path: str) -> Dict[str, Any]:
    """
    Read an episode HDF5 file and return its root attributes, raw datasets, and resampled datasets.
    
    Args:
        file_path: Path to the HDF5 file.
        
    Returns:
        Dict containing attrs, raw datasets dictionary, and observations dictionary (if present).
    """
    result: Dict[str, Any] = {
        "attrs": {},
        "raw": {},
        "observations": {},
        "actions": None,
    }
    
    with h5py.File(file_path, "r") as f:
        # Load attributes
        for key, val in f.attrs.items():
            if isinstance(val, (np.bool_, np.generic)):
                val = val.item()
            if key in ("camera_intrinsics", "spline_params") and isinstance(val, str):
                try:
                    result["attrs"][key] = json.loads(val)
                except Exception:
                    result["attrs"][key] = val
            else:
                result["attrs"][key] = val

        # Load /raw/ if present
        if "raw" in f:
            raw_grp = f["raw"]
            assert isinstance(raw_grp, h5py.Group), "Expected 'raw' to be a Group"
            for ds_name in raw_grp.keys():
                ds = raw_grp[ds_name]
                assert isinstance(ds, h5py.Dataset), f"Expected '{ds_name}' in /raw/ to be a Dataset"
                result["raw"][ds_name] = ds[:]

        # Load /observations/ if present
        if "observations" in f:
            obs_grp = f["observations"]
            assert isinstance(obs_grp, h5py.Group), "Expected 'observations' to be a Group"
            for ds_name in obs_grp.keys():
                ds = obs_grp[ds_name]
                assert isinstance(ds, h5py.Dataset), f"Expected '{ds_name}' in /observations/ to be a Dataset"
                result["observations"][ds_name] = ds[:]

        # Load /actions if present at root
        if "actions" in f:
            actions_ds = f["actions"]
            assert isinstance(actions_ds, h5py.Dataset), "Expected 'actions' to be a Dataset"
            result["actions"] = actions_ds[:]

    return result
