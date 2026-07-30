"""API endpoints for manual episode recording (start/stop).

POST /api/recording/start  — Begin buffering telemetry + camera frames
POST /api/recording/stop   — Stop buffering, write HDF5 + SQLite records
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from config import settings
from models.episode import (
    RawEpisodeBuffer,
    RawEpisodeData,
    RawTelemetrySample,
    RawFrameSample,
    BatchRecord,
    EpisodeRecord,
)
from models.pose import TelemetrySample
from storage.hdf5_writer import write_raw_episode_hdf5
from storage.batch_repo import create_batch, get_batch, increment_completed_episodes
from storage.episode_repo import create_episode
from db import init_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recording", tags=["recording"])


# ---------------------------------------------------------------------------
# In-memory recording state
# ---------------------------------------------------------------------------

class _RecordingState:
    """Holds the active buffer and subscription handles while recording."""

    def __init__(self):
        self.buffer: RawEpisodeBuffer | None = None
        self.batch_id: str | None = None
        self.episode_id: str | None = None
        self.t_start: float | None = None
        self._telemetry_unsub: object | None = None
        self._camera_unsub: object | None = None

    @property
    def is_recording(self) -> bool:
        return self.buffer is not None

    def clear(self) -> None:
        self.buffer = None
        self.batch_id = None
        self.episode_id = None
        self.t_start = None
        self._telemetry_unsub = None
        self._camera_unsub = None


_recording = _RecordingState()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class StartRecordingRequest(BaseModel):
    batch_id: str = ""
    object_class: str = ""
    language_instruction: str = ""


class RecordingStatus(BaseModel):
    recording: bool
    batch_id: str = ""
    episode_id: str = ""
    elapsed_s: float = 0.0


class RecordingResult(BaseModel):
    episode_id: str
    batch_id: str
    hdf5_path: str
    duration_s: float
    n_frames: int
    n_telemetry_samples: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _decode_depth_png16(depth_bytes: bytes) -> np.ndarray:
    """Decode PNG16 depth bytes into a float32 numpy array (meters)."""
    nparr = np.frombuffer(depth_bytes, np.uint8)
    depth_img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
    if depth_img is None:
        raise ValueError("Failed to decode depth PNG16")
    # If 16-bit PNG, convert to float32 meters (assuming depth_scale=1000 for mm->m)
    if depth_img.dtype == np.uint16:
        depth_img = depth_img.astype(np.float32) / 1000.0
    return depth_img


def _decode_rgb_jpeg(rgb_bytes: bytes) -> np.ndarray:
    """Decode RGB JPEG bytes into a uint8 numpy array (H, W, 3)."""
    nparr = np.frombuffer(rgb_bytes, np.uint8)
    bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Failed to decode RGB JPEG")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------------------
# Callbacks (subscribed to RobotClient / CameraFrameClient)
# ---------------------------------------------------------------------------

async def _on_telemetry_sample(sample: TelemetrySample) -> None:
    """Buffer one telemetry sample into the active recording."""
    if _recording.buffer is None:
        return
    _recording.buffer.telemetry_samples.append(
        RawTelemetrySample(
            ts=sample.ts,
            joint_pos=list(sample.joint_pos),
            ee_pose=[
                sample.tcp_pose.x, sample.tcp_pose.y, sample.tcp_pose.z,
                sample.tcp_pose.rx, sample.tcp_pose.ry, sample.tcp_pose.rz,
            ],
            gripper=sample.gripper_status.amplitude,
        )
    )


async def _on_camera_frame(meta: dict, rgb_jpeg: bytes, depth_png16: bytes) -> None:
    """Buffer one camera frame into the active recording."""
    if _recording.buffer is None:
        return
    try:
        rgb = _decode_rgb_jpeg(rgb_jpeg)
        depth = _decode_depth_png16(depth_png16)
        ts = meta.get("ts", 0.0)
        _recording.buffer.frame_samples.append(
            RawFrameSample(ts=ts, rgb=rgb, depth=depth)
        )
    except Exception as e:
        logger.warning("Failed to decode camera frame for recording: %s", e)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/start", response_model=RecordingStatus)
async def start_recording(req: StartRecordingRequest, request: Request):
    """Start buffering telemetry and camera frames for a new episode."""
    if _recording.is_recording:
        raise HTTPException(409, "Recording already in progress")

    # Ensure DB is initialized
    init_db()

    # Generate IDs
    batch_id = req.batch_id or f"manual_{uuid.uuid4().hex[:8]}"
    episode_id = f"ep_{uuid.uuid4().hex[:12]}"

    # Ensure batch exists in DB
    existing = get_batch(batch_id)
    if existing is None:
        batch = BatchRecord(
            batch_id=batch_id,
            object_class=req.object_class or "unknown",
            created_at=datetime.now(timezone.utc).isoformat(),
            target_episodes=1,
            target_hz=settings.default_target_hz,
        )
        create_batch(batch)

    # Get app state references from request
    robot_client = request.app.state.robot_client
    camera_client = request.app.state.camera_client

    # Subscribe callbacks
    robot_client.subscribe(_on_telemetry_sample)
    camera_client.subscribe(_on_camera_frame)

    # Initialize buffer
    _recording.buffer = RawEpisodeBuffer()
    _recording.batch_id = batch_id
    _recording.episode_id = episode_id
    _recording.t_start = None  # will be set on first sample

    logger.info(
        "Recording started: batch=%s episode=%s object=%s",
        batch_id, episode_id, req.object_class,
    )

    return RecordingStatus(
        recording=True,
        batch_id=batch_id,
        episode_id=episode_id,
        elapsed_s=0.0,
    )


@router.post("/stop", response_model=RecordingResult)
async def stop_recording(request: Request):
    """Stop recording, build RawEpisodeData, write HDF5, and create SQLite records."""
    if not _recording.is_recording:
        raise HTTPException(409, "No recording in progress")

    buf = _recording.buffer
    assert buf is not None  # guaranteed by is_recording check
    batch_id = _recording.batch_id or ""
    episode_id = _recording.episode_id or ""

    # Unsubscribe callbacks first so no more samples arrive during finalization
    robot_client = request.app.state.robot_client
    camera_client = request.app.state.camera_client
    robot_client.unsubscribe(_on_telemetry_sample)
    camera_client.unsubscribe(_on_camera_frame)

    try:
        # Build arrays from buffered samples
        n_telemetry = len(buf.telemetry_samples)
        n_frames = len(buf.frame_samples)

        if n_telemetry == 0:
            raise HTTPException(400, "No telemetry data collected — nothing to save")

        # Determine t_start / t_end from first/last telemetry timestamps
        t_start = buf.telemetry_samples[0].ts
        t_end = buf.telemetry_samples[-1].ts

        # Build joint arrays
        n_joints = len(buf.telemetry_samples[0].joint_pos)
        joint_pos = np.zeros((n_telemetry, n_joints), dtype=np.float32)
        joint_ts = np.zeros(n_telemetry, dtype=np.float64)
        ee_pose = np.zeros((n_telemetry, 6), dtype=np.float32)
        gripper = np.zeros(n_telemetry, dtype=np.float32)

        for i, s in enumerate(buf.telemetry_samples):
            joint_pos[i] = s.joint_pos
            joint_ts[i] = s.ts
            ee_pose[i] = s.ee_pose
            gripper[i] = s.gripper

        # Build frame arrays
        if n_frames > 0:
            H, W = buf.frame_samples[0].rgb.shape[:2]
            rgb = np.zeros((n_frames, H, W, 3), dtype=np.uint8)
            depth = np.zeros((n_frames, H, W), dtype=np.float32)
            frame_ts = np.zeros(n_frames, dtype=np.float64)

            for i, f in enumerate(buf.frame_samples):
                rgb[i] = f.rgb
                depth[i] = f.depth
                frame_ts[i] = f.ts
        else:
            rgb = np.zeros((0, 0, 0, 3), dtype=np.uint8)
            depth = np.zeros((0, 0, 0), dtype=np.float32)
            frame_ts = np.zeros(0, dtype=np.float64)

        # Build RawEpisodeData
        raw_data = RawEpisodeData(
            joint_pos=joint_pos,
            joint_ts=joint_ts,
            ee_pose=ee_pose,
            gripper=gripper,
            rgb=rgb,
            depth=depth,
            frame_ts=frame_ts,
            language_instruction="",
            object_class="",
            success=True,
            t_start=t_start,
            t_end=t_end,
        )

        # Write HDF5
        hdf5_dir = settings.hdf5_dir
        os.makedirs(hdf5_dir, exist_ok=True)
        hdf5_path = os.path.join(hdf5_dir, f"{episode_id}.h5")
        write_raw_episode_hdf5(raw_data, hdf5_path)

        duration_s = t_end - t_start

        # Create SQLite episode record
        ep = EpisodeRecord(
            episode_id=episode_id,
            batch_id=batch_id,
            object_class="",
            language_instruction="",
            hdf5_path=hdf5_path,
            duration_s=duration_s,
            n_frames=n_frames,
        )
        create_episode(ep)

        # Increment batch completed count
        increment_completed_episodes(batch_id)

        logger.info(
            "Recording saved: episode=%s batch=%s duration=%.2fs frames=%d telemetry=%d",
            episode_id, batch_id, duration_s, n_frames, n_telemetry,
        )

        return RecordingResult(
            episode_id=episode_id,
            batch_id=batch_id,
            hdf5_path=hdf5_path,
            duration_s=duration_s,
            n_frames=n_frames,
            n_telemetry_samples=n_telemetry,
        )

    finally:
        _recording.clear()


@router.get("/status", response_model=RecordingStatus)
async def recording_status():
    """Check if a recording is currently in progress."""
    if not _recording.is_recording:
        return RecordingStatus(recording=False)

    # Estimate elapsed time from first sample
    elapsed = 0.0
    if _recording.buffer and _recording.buffer.telemetry_samples:
        elapsed = (
            _recording.buffer.telemetry_samples[-1].ts
            - _recording.buffer.telemetry_samples[0].ts
        )

    return RecordingStatus(
        recording=True,
        batch_id=_recording.batch_id or "",
        episode_id=_recording.episode_id or "",
        elapsed_s=elapsed,
    )