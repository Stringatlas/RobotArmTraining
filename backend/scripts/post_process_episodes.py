import argparse
import glob
import os
import sys
import numpy as np

from config import settings
from models.episode import RawEpisodeData
from storage.hdf5_writer import read_episode_hdf5, write_resampled_group
from services.resampler import resample_raw_episode

def post_process_file(file_path: str, target_hz: float, gap_threshold: float) -> bool:
    """Post-process a single HDF5 episode file, appending resampled grid datasets."""
    data = read_episode_hdf5(file_path)
    if "raw" not in data or not data["raw"]:
        print(f"Skipping {file_path}: No /raw/ group found.")
        return False

    raw_dict = data["raw"]
    attrs = data.get("attrs", {})

    raw_episode = RawEpisodeData(
        joint_pos=raw_dict.get("joint_pos", np.zeros((0, 6))),
        joint_ts=raw_dict.get("joint_ts", np.zeros((0,))),
        ee_pose=raw_dict.get("ee_pose", np.zeros((0, 7))),
        gripper=raw_dict.get("gripper", np.zeros((0,))),
        rgb=raw_dict.get("rgb", np.zeros((0, 0, 0, 3))),
        depth=raw_dict.get("depth", np.zeros((0, 0, 0))),
        frame_ts=raw_dict.get("frame_ts", np.zeros((0,))),
        language_instruction=str(attrs.get("language_instruction", "")),
        object_class=str(attrs.get("object_class", "")),
        success=bool(attrs.get("success", True)),
        camera_intrinsics=attrs.get("camera_intrinsics", {}),
        spline_params=attrs.get("spline_params", {}),
        t_start=float(attrs.get("t_start", 0.0)),
        t_end=float(attrs.get("t_end", 0.0)),
    )

    resampled = resample_raw_episode(raw_episode, target_hz=target_hz, gap_threshold_sec=gap_threshold)
    write_resampled_group(file_path, resampled)
    print(f"Processed {os.path.basename(file_path)}: T={len(resampled.timestamps)} steps @ {target_hz}Hz (flagged_gap={resampled.flagged_gap})")
    return True

def main():
    parser = argparse.ArgumentParser(description="Bulk post-process raw episode HDF5 files to uniform target Hz.")
    parser.add_argument("--episodes-dir", type=str, default=settings.hdf5_dir, help="Directory containing HDF5 episode files")
    parser.add_argument("--target-hz", type=float, default=settings.default_target_hz, help="Target sampling rate (Hz)")
    parser.add_argument("--gap-threshold", type=float, default=0.1, help="Max telemetry gap threshold in seconds")

    args = parser.parse_args()

    if not os.path.exists(args.episodes_dir):
        print(f"Episodes directory '{args.episodes_dir}' does not exist.")
        sys.exit(1)

    pattern = os.path.join(args.episodes_dir, "*.h5")
    files = glob.glob(pattern)

    if not files:
        print(f"No .h5 files found in {args.episodes_dir}")
        return

    print(f"Found {len(files)} episode files in {args.episodes_dir}. Post-processing @ {args.target_hz} Hz...")
    count = 0
    for file_path in files:
        if post_process_file(file_path, args.target_hz, args.gap_threshold):
            count += 1

    print(f"Finished post-processing {count}/{len(files)} episode files.")

if __name__ == "__main__":
    main()
