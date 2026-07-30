import os
import tempfile
import numpy as np
import pytest

from db import init_db
from models.episode import (
    RawEpisodeData,
    BatchRecord,
    EpisodeRecord,
)
from storage.hdf5_writer import (
    write_raw_episode_hdf5,
    write_resampled_group,
    read_episode_hdf5,
)
from storage.batch_repo import (
    create_batch,
    get_batch,
    update_batch_status,
    increment_completed_episodes,
    list_batches,
)
from storage.episode_repo import (
    create_episode,
    get_episode,
    update_episode_label,
    list_episodes,
)
from services.resampler import resample_raw_episode


def test_sqlite_db_and_repos():
    """Test SQLite initialization, batch_repo, and episode_repo CRUD operations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_metadata.db")
        init_db(db_path)

        # 1. Test Batch Repo
        batch = BatchRecord(
            batch_id="batch_001",
            object_class="red_mug",
            created_at="2026-07-26T12:00:00Z",
            target_episodes=10,
            target_hz=30.0,
        )
        create_batch(batch, db_path=db_path)

        fetched_batch = get_batch("batch_001", db_path=db_path)
        assert fetched_batch is not None
        assert fetched_batch.object_class == "red_mug"
        assert fetched_batch.completed_episodes == 0

        # Update batch status and increment count
        assert update_batch_status("batch_001", "running", db_path=db_path)
        new_count = increment_completed_episodes("batch_001", db_path=db_path)
        assert new_count == 1

        batches = list_batches(db_path=db_path)
        assert len(batches) == 1

        # 2. Test Episode Repo
        ep = EpisodeRecord(
            episode_id="ep_001",
            batch_id="batch_001",
            object_class="red_mug",
            language_instruction="Pick up the red mug",
            hdf5_path=os.path.join(tmpdir, "ep_001.h5"),
            duration_s=2.5,
            n_frames=75,
            flagged_gap=False,
            yolo_confidence=0.95,
        )
        create_episode(ep, db_path=db_path)

        fetched_ep = get_episode("ep_001", db_path=db_path)
        assert fetched_ep is not None
        assert fetched_ep.language_instruction == "Pick up the red mug"
        assert fetched_ep.success is True

        # Update label
        assert update_episode_label(
            "ep_001",
            success=False,
            language_instruction="Pick red cup",
            export_split="train",
            db_path=db_path,
        )

        updated_ep = get_episode("ep_001", db_path=db_path)
        assert updated_ep is not None
        assert updated_ep.success is False
        assert updated_ep.success_source == "human_override"
        assert updated_ep.language_instruction == "Pick red cup"
        assert updated_ep.instruction_source == "human_edited"
        assert updated_ep.export_split == "train"

        # List with filter
        filtered = list_episodes(batch_id="batch_001", export_split="train", db_path=db_path)
        assert len(filtered) == 1
        assert filtered[0].episode_id == "ep_001"


def test_raw_hdf5_write_read_and_resample():
    """Test raw HDF5 write/read, post-processing resampling, and resampled dataset group attachment."""
    with tempfile.TemporaryDirectory() as tmpdir:
        h5_path = os.path.join(tmpdir, "test_episode.h5")

        # Create synthetic raw data (100 joint samples @ ~50Hz, 60 frame samples @ ~30Hz)
        joint_ts = np.linspace(0.0, 2.0, 100, dtype=np.float64)
        joint_pos = np.sin(np.outer(joint_ts, np.ones(6, dtype=np.float32)))
        ee_pose = np.ones((100, 7), dtype=np.float32)
        gripper = np.zeros(100, dtype=np.float32)

        frame_ts = np.linspace(0.0, 2.0, 60, dtype=np.float64)
        rgb = np.full((60, 48, 64, 3), 128, dtype=np.uint8)
        depth = np.full((60, 48, 64), 1.0, dtype=np.float32)

        raw_data = RawEpisodeData(
            joint_pos=joint_pos,
            joint_ts=joint_ts,
            ee_pose=ee_pose,
            gripper=gripper,
            rgb=rgb,
            depth=depth,
            frame_ts=frame_ts,
            language_instruction="Pick the block",
            object_class="block",
            success=True,
            camera_intrinsics={"fx": 600.0, "fy": 600.0, "cx": 320.0, "cy": 240.0},
            spline_params={"control_points": [[0, 0, 0], [1, 1, 1]]},
            t_start=0.0,
            t_end=2.0,
        )

        # 1. Write Raw HDF5
        saved_path = write_raw_episode_hdf5(raw_data, h5_path)
        assert os.path.exists(saved_path)

        # Read back raw data
        read_data = read_episode_hdf5(saved_path)
        assert read_data["attrs"]["language_instruction"] == "Pick the block"
        assert read_data["attrs"]["object_class"] == "block"
        assert read_data["attrs"]["success"] is True
        assert read_data["raw"]["joint_pos"].shape == (100, 6)
        assert read_data["raw"]["rgb"].shape == (60, 48, 64, 3)

        # 2. Resample
        resampled = resample_raw_episode(raw_data, target_hz=30.0, gap_threshold_sec=0.1)
        assert resampled.flagged_gap is False
        assert len(resampled.timestamps) == 61  # 2.0s * 30Hz + 1
        assert resampled.joint_pos.shape == (61, 6)
        assert resampled.rgb.shape == (61, 48, 64, 3)
        assert resampled.actions.shape == (61, 6)

        # 3. Write Resampled Group
        write_resampled_group(saved_path, resampled)

        # Verify resampled group present in file
        read_resampled = read_episode_hdf5(saved_path)
        assert "joint_pos" in read_resampled["observations"]
        assert read_resampled["observations"]["joint_pos"].shape == (61, 6)
        assert read_resampled["actions"].shape == (61, 6)


def test_resample_gap_flagging():
    """Test that resampling flags gaps when telemetry delta exceeds threshold."""
    # Joint timestamps with a 0.5s jump in the middle
    ts1 = np.linspace(0.0, 0.5, 25)
    ts2 = np.linspace(1.1, 1.6, 25)  # gap of 0.6s between 0.5 and 1.1
    joint_ts = np.concatenate([ts1, ts2])
    joint_pos = np.zeros((50, 6), dtype=np.float32)
    ee_pose = np.zeros((50, 7), dtype=np.float32)
    gripper = np.zeros(50, dtype=np.float32)

    raw_data = RawEpisodeData(
        joint_pos=joint_pos,
        joint_ts=joint_ts,
        ee_pose=ee_pose,
        gripper=gripper,
        rgb=np.zeros((0, 0, 0, 3), dtype=np.uint8),
        depth=np.zeros((0, 0, 0), dtype=np.float32),
        frame_ts=np.zeros(0),
        t_start=0.0,
        t_end=1.6,
    )

    resampled = resample_raw_episode(raw_data, target_hz=30.0, gap_threshold_sec=0.1)
    assert resampled.flagged_gap is True
