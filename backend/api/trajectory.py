"""
POST /trajectory/generate

Exposes trajectory_service.generate_trajectory() over HTTP. This endpoint
does no physical execution — it just returns the waypoint list. Something
else (episode_runner.py) is responsible for calling robot_client with the
result.

Novice notes (feel free to delete this docstring once it makes sense):
- `router = APIRouter(...)` groups these routes under a shared prefix/tag,
  then main.py does `app.include_router(router)` once at startup.
- FastAPI validates the incoming JSON against TrajectoryRequest automatically
  before this function even runs — if a field is missing or the wrong type,
  the caller gets a 422 with details, and generate() never executes. That's
  the main benefit of defining the pydantic schemas: validation is free.
- HTTPException is how you return a non-500, non-200 error with a clear
  message instead of letting a raw Python exception leak to the client.
"""
import numpy as np
from fastapi import APIRouter, HTTPException

from models.trajectory_schemas import (
    TrajectoryRequest,
    TrajectoryResponse,
    PoseModel,
)

from models.robot import Pose
from services.trajectory.trajectory import TrajectoryParams, generate_trajectory

router = APIRouter(prefix="/trajectory", tags=["trajectory"])


def _to_internal_pose(pose: PoseModel) -> Pose:
    """Convert wire-format PoseModel (lists) to internal Pose (numpy arrays)."""
    return Pose(
        position=np.array(pose.position, dtype=float),
        orientation=np.array(pose.orientation, dtype=float),
    )


def _to_internal_params(params) -> TrajectoryParams:
    """Convert wire-format TrajectoryParamsModel to internal TrajectoryParams."""
    if params is None:
        return TrajectoryParams()

    kwargs = params.model_dump()
    # retreat_direction / approach_direction need to become numpy arrays (or
    # stay None so TrajectoryParams.__post_init__ applies its own default).
    for key in ("retreat_direction", "approach_direction"):
        if kwargs[key] is not None:
            kwargs[key] = np.array(kwargs[key], dtype=float)

    return TrajectoryParams(**kwargs)


@router.post("/generate", response_model=TrajectoryResponse)
def generate_trajectory_endpoint(request: TrajectoryRequest) -> TrajectoryResponse:
    """
    Generate a waypoint trajectory from current_pose to target_pose.

    Returns 422 automatically (via pydantic) for malformed input, and 400
    for otherwise-valid input that the geometry can't handle (e.g. current
    and target poses being identical, which degenerates the Bezier curve).
    """
    current = _to_internal_pose(request.current_pose)
    target = _to_internal_pose(request.target_pose)
    params = _to_internal_params(request.params)

    if np.allclose(current.position, target.position):
        raise HTTPException(
            status_code=400,
            detail="current_pose and target_pose positions are identical; nothing to plan.",
        )

    try:
        waypoints = generate_trajectory(current, target, params)
    except Exception as exc:
        # Anything unexpected from the geometry layer becomes a 500 with a
        # readable message instead of an opaque stack trace to the client.
        raise HTTPException(status_code=500, detail=f"Trajectory generation failed: {exc}")

    return TrajectoryResponse(
        waypoints=[
            PoseModel(position=wp.position.tolist(), orientation=wp.orientation.tolist())
            for wp in waypoints
        ],
        n_waypoints=len(waypoints),
    )