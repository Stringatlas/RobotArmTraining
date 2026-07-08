"""Shared pose / telemetry dataclasses.

Used by robot_client, ws_telemetry, trajectory generation, and
(later) episode_runner + resampler. Keeping these here — rather than
inline in robot_client — is what lets trajectory.py and episode.py
import Pose without importing the WS client itself.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TcpPose:
    """Cartesian tool-center-point pose, matching the robot's wire format."""

    x: float
    y: float
    z: float
    rx: float
    ry: float
    rz: float

    @classmethod
    def from_dict(cls, d: dict) -> "TcpPose":
        return cls(x=d["x"], y=d["y"], z=d["z"], rx=d["rx"], ry=d["ry"], rz=d["rz"])

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "rx": self.rx,
            "ry": self.ry,
            "rz": self.rz,
        }


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    """One raw sample off the robot's /telemetry/ws, hardware/robot timestamped.

    This is the raw, jittery-arrival form. Resampling onto a fixed-rate
    grid (later, in resampler.py) consumes a sequence of these — not
    built here, just keeping the shape ready for it.
    """

    joint_pos: list[float]
    tcp_pose: TcpPose
    state: str
    ts: float  # seconds, as emitted by the robot service

    @classmethod
    def from_wire(cls, msg: dict) -> "TelemetrySample":
        return cls(
            joint_pos=list(msg["joint_pos"]),
            tcp_pose=TcpPose.from_dict(msg["tcp_pose"]),
            state=msg["state"],
            ts=msg["ts"],
        )

    def to_dict(self) -> dict:
        return {
            "joint_pos": self.joint_pos,
            "tcp_pose": self.tcp_pose.to_dict(),
            "state": self.state,
            "ts": self.ts,
        }