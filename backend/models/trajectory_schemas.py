"""
Pydantic schemas for the trajectory generation API.

These are the "wire format" — plain lists of floats over JSON — that get
converted to/from the numpy-based Pose/TrajectoryParams dataclasses used
internally by trajectory_service.py. Keeping this conversion at the API
boundary means the service layer never has to know about HTTP/JSON at all.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import numpy as np


class PoseModel(BaseModel):
    """A single pose: 3D position + quaternion orientation."""

    position: list[float] = Field(
        ..., min_length=3, max_length=3,
        description="End-effector position [x, y, z] in meters, robot base frame.",
    )
    orientation: list[float] = Field(
        ..., min_length=4, max_length=4,
        description="Unit quaternion [x, y, z, w] (note: xyzw order, not wxyz).",
    )

    @field_validator("orientation")
    @classmethod
    def orientation_must_be_unit_length(cls, v: list[float]) -> list[float]:
        norm = float(np.linalg.norm(v))
        # Reject anything that isn't approximately a unit quaternion, rather
        # than silently normalizing it — a badly-off norm usually means the
        # caller sent garbage (e.g. wxyz order, or radians by mistake) and
        # normalizing would hide that bug instead of surfacing it.
        if not (0.9 <= norm <= 1.1):
            raise ValueError(
                f"orientation must be a unit quaternion (norm ~1.0), got norm={norm:.4f}"
            )
        return v


class TrajectoryParamsModel(BaseModel):
    """
    Optional tuning knobs for trajectory shape. All have defaults matching
    TrajectoryParams in trajectory_service.py — most callers won't need to
    set any of these.
    """

    lift_height: float = Field(
        0.08, gt=0, le=0.5,
        description="Meters to lift straight up before curving toward target.",
    )
    approach_height: float = Field(
        0.05, gt=0, le=0.5,
        description="Meters of straight-line final approach into the target.",
    )
    retreat_direction: Optional[list[float]] = Field(
        None, min_length=3, max_length=3,
        description="Departure direction vector, e.g. [0,0,1] for straight up. Defaults to +Z.",
    )
    approach_direction: Optional[list[float]] = Field(
        None, min_length=3, max_length=3,
        description="Approach direction vector, e.g. [0,0,-1] for straight down. Defaults to -Z.",
    )
    n_waypoints: int = Field(
        50, ge=2, le=500,
        description="Number of waypoints to sample along the trajectory.",
    )
    arc_length_samples: int = Field(
        200, ge=10, le=2000,
        description="Internal resolution for arc-length reparameterization. Leave as default.",
    )


class TrajectoryRequest(BaseModel):
    current_pose: PoseModel = Field(..., description="Robot's current end-effector pose.")
    target_pose: PoseModel = Field(..., description="Detected target pose to move toward.")
    params: Optional[TrajectoryParamsModel] = Field(
        None, description="Optional trajectory shaping params; defaults used if omitted."
    )


class TrajectoryResponse(BaseModel):
    waypoints: list[PoseModel] = Field(..., description="Ordered list of poses to follow, start to end.")
    n_waypoints: int