# Progress

## Done (robot-service)
- `arm_lock.py`, `robot_state.py`, `worker.py` — trajectory execution via queue + daemon thread, `wait=False` + poll so `stop_event` is noticed promptly.
- `api/routes.py`, `api/schemas.py` — `POST /follow_trajectory` (202/409), `POST /stop`. `Waypoint`/`CartesianPose` kept as separate types (API vs. internal), converted via plain dict.
- `api/main.py` — lifespan spins up worker + telemetry threads, wires `app.state`.
- `telemetry.py` — runs continuously, takes `arm_lock` on every read (not relaxed yet — SDK thread-safety on the shared connection is unverified, not just read/write ordering).
- Manually tested via curl/Postman with mock arm; telemetry confirmed live during `executing`.

## Stubbed, untested
- `GET /joint_angles`, `GET /camera/frame`, `GET /camera/info`, `api/schemas.py`'s `FrameResponse`/`CameraInfo`.

## Open decisions
- `episode_runner.py`: block on `follow_trajectory` + poll, or fire-and-forget relying on telemetry/state? (affects `robot_client.py` shape)
- Buffer-then-resample vs. inline resampling for telemetry.
- `arm_lock`: relax to writes-only once Lebai confirms concurrent-read safety.
- `/stop` currently returns state at call time, not post-stop — decide if frontend needs to await actual completion.