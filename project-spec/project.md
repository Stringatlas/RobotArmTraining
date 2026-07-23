# Project: Robot Arm VLA Data Collection Platform

## Goal
Collect vision-language-action (VLA) training data for robotic pick-and-place across varied objects. A robot arm with a RealSense RGB-D camera executes auto-generated spline trajectories toward YOLO-detected objects; a separate web app orchestrates, captures, labels, and exports the resulting episodes as training data.

## Hardware / Responsibility Split
- **Robot side**: Lebai physical arm + RealSense camera (camera physically mounted on/plugged into the arm — both live under one `robot-service` process, one host). Exposes a FastAPI service: `get_joint_angles`, `follow_trajectory`, `GET /camera/frame` (single-shot HTTP capture for pre-trajectory YOLO), `GET /camera/info` (intrinsics, called once per batch), and telemetry WebSocket(s) streaming joint state and RGB-D frames during execution. No local training-data storage.
- **Web app side**: separate machine. Owns YOLO inference, trajectory generation, all data capture/storage, labeling UI, and dataset export ("training platform").

## Stack
- **Backend**: Python + FastAPI. Async, native WebSocket support.
- **Frontend**: Svelte + Three.js. `urdf-loader` drives a live digital twin from joint state; Svelte stores hold live WebSocket state.
- **Episode storage**: HDF5 (`h5py`), one file per episode (raw depth isn't first-class in LeRobot's format). Internal `Episode` abstraction in the write pipeline so a LeRobot-format exporter can be added later.
- **Metadata DB**: SQLite, pointers only (no heavy arrays). One-line swap to Postgres later if multi-rig.
- **Repo**: monorepo (`backend/`, `frontend/`, `robot-service/`).

## Concurrency Model
No task queue — single async state machine inside the FastAPI process (`idle → executing → capturing → writing → idle`). Batch progress persisted to SQLite after every episode so a crash mid-batch resumes.

`robot-service` side of this is implemented: `POST /follow_trajectory` (202/409) + `POST /stop` run on a dedicated worker thread guarded by `RobotStateMachine.try_start()`, concurrently with the telemetry thread — both serialized through a shared `arm_lock` since SDK connection thread-safety is unverified. Backend-side consumption (`robot_client.py`, `episode_runner.py`) still open.

## Per-Episode Pipeline
1. `GET /camera/frame` (HTTP, one-shot) → YOLO inference on web app → object pose/class.
2. Trajectory generation (spline, using detected pose).
3. Call `robot.follow_trajectory()`; concurrently consume telemetry WS for RGB-D + joint state, buffered raw with each source's own embedded timestamp.
4. On execution end: **resample** the raw buffer onto a fixed-rate grid (see below).
5. Auto-flag success/fail if the robot API signals it; always human-overridable.
6. Write episode to HDF5; upsert episode row in SQLite; increment batch progress.

## Telemetry Transport & Timestamp Sync
Raw capture over a network/thread pipeline is jittery; the design goal is to make that jitter irrelevant to the stored data rather than eliminate it.

- **Timestamps are stamped at the source, on `robot-service`'s host, using `time.monotonic()`** — not `time.time()` (wall clock can jump on NTP correction) and not timestamped on arrival at the backend (that would bake network/asyncio jitter into the data). Every joint reading and every camera frame carries its own `ts`. Because the camera and joint poller run on the *same host*, their monotonic timestamps are directly comparable to each other with no clock-skew concern. `time.monotonic()`'s epoch is process-relative — never persisted or compared across a `robot-service` restart; HDF5 stores elapsed-time-since-episode-start instead.
- **Joint state and RGB-D frames are two independent producers**, each publishing on its own cadence — never merged into one message. RGB-D payloads are large (JPEG/PNG16-encoded, still large relative to a joint snapshot); bundling them would stall the tight joint-poll loop and reintroduce the exact lag we're avoiding.
- **Two logical telemetry channels** (ideally two WS connections, `/telemetry/ws/joints` and `/telemetry/ws/frames`), so a large in-flight frame can't head-of-line-block a time-critical joint update behind it on the same TCP connection.
- **Resampling (post-capture, backend-side)** onto one synthetic target grid — the two streams are *not* aligned to each other's native rate:
  - **Joint angles / actions**: linearly interpolated onto target grid timestamps.
  - **RGB-D frames**: nearest/Nth-frame selection using each frame's own hardware-adjacent (`ts`) timestamp, not WS arrival order — RGB and depth share the same RealSense frame index, so they're inherently aligned.
  - A tolerance check flags any episode/timestep with missing or delayed data (`flagged_gap`), surfaced as a QA queue rather than silently mislabeled.

## Transport Decisions (and why simpler options were rejected)
- **WebSocket, not WebRTC**: WebRTC solves browser-to-browser P2P media over untrusted networks — irrelevant for two backend processes on a LAN.
- **WebSocket, not Zenoh**: Zenoh solves multi-producer/multi-consumer pub-sub discovery. One robot, one consumer — plain WebSocket suffices. Revisit only at fleet scale.
- **Push, not polling**: `robot-service` is code we control, so it streams during execution rather than being polled.
- **HTTP, not WS, for single-frame capture**: `GET /camera/frame` is a discrete request/response (pre-trajectory detection), not a stream — doesn't belong on the telemetry WS.

## Data Model
- **Batch** = one collection run under a fixed config (typically one `object_class` + one randomization config, N episodes).
- **Episode** = one trajectory attempt: one instruction, one success/fail label, one synced data tuple (RGB, depth, joint pos, ee pose, gripper, actions, language instruction).
- **HDF5 schema per episode**:
```
/observations/rgb         (T, H, W, 3)
/observations/depth       (T, H, W)
/observations/joint_pos   (T, n_joints)
/observations/ee_pose     (T, 7)
/observations/gripper     (T,)
/actions                  (T, action_dim)   ← training target
attrs: language_instruction, object_class, success,
       camera_intrinsics, spline_params, timestamps
```
- **SQLite `batches` table**: batch_id, object_class, created_at, target/completed episode counts, status (running/paused/completed/crashed), randomization_params (JSON), target_hz.
- **SQLite `episodes` table**: episode_id, batch_id, object_class (denormalized), language_instruction, instruction_source (auto_template/human_edited), success, success_source (auto/human_override), hdf5_path, duration_s, n_frames, flagged_gap, yolo_confidence, export_split.

## Frontend Functionality
- Session/batch control: start/stop/pause, config, live episode counter, software e-stop always reachable.
- Live digital twin (Three.js + `urdf-loader`) driven by joint state over WebSocket during execution.
- Replay: synced video (frames muxed to MP4) + 3D trajectory scrub driven by stored `joint_pos`/`ee_pose`.
- Dataset browser: filter/sort by object class, success, flagged_gap, export_split; manual relabeling with instruction_source tracking.
- Bulk export of a filtered subset as a training-ready split.

## Open Items / Assumptions to Verify
- Whether to buffer-then-resample per episode (simpler, allows re-deriving training rates later) or resample inline as frames arrive (lower memory, no re-derivation) — currently unresolved, pick based on memory constraints.
- Confirm joint-poll "lag spikes" root cause before assuming architecture is at fault: instrument `telemetry.py`'s own call-to-call `time.monotonic()` deltas first (SDK-call blocking is the likely culprit), separately from WS receipt timing and frontend render cost.