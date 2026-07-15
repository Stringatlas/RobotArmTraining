import type { EulerPose, QuaternionPose } from '$lib/types';
import { Euler, Quaternion } from 'three';
import { currentTrajectory } from '$lib/state/trajectoryState';

export type BackendQuaternionPose = {position: [number, number, number], orientation: [number, number, number, number]};

export function convertEulerToQuaternion(pose: EulerPose): QuaternionPose {
    const q = new Quaternion().setFromEuler(
        new Euler(pose.rx, pose.ry, pose.rz, 'ZYX')
    );

    return {
        x: pose.x,
        y: pose.y,
        z: pose.z,
        rx: q.x,
        ry: q.y, 
        rz: q.z,
        rw: q.w
    };
}

export function convertQuaternionToEuler(pose: QuaternionPose): EulerPose {
    const e = new Euler().setFromQuaternion(
        new Quaternion(pose.rx, pose.ry, pose.rz, pose.rw),"ZYX"
    );

    return {
        x: pose.x,
        y: pose.y,
        z: pose.z,
        rx: e.x,
        ry: e.y, 
        rz: e.z,
    };
}

export function adaptQuaternionForBackend(pose: QuaternionPose): BackendQuaternionPose {
    return {
        position: [pose.x, pose.y, pose.z],
        orientation: [pose.rx, pose.ry, pose.rz, pose.rw]
    }
}


export function adaptBackendQuaternion(pose: BackendQuaternionPose): QuaternionPose{
    return {
        x: pose.position[0],
        y: pose.position[1],
        z: pose.position[2],
        rx: pose.orientation[0],
        ry: pose.orientation[1],
        rz: pose.orientation[2],
        rw: pose.orientation[3],
    }
}

export async function requestTrajectory(currentPose: EulerPose, targetPose: EulerPose): Promise<EulerPose[]> {
    let convertedCurrentPose = adaptQuaternionForBackend(convertEulerToQuaternion(currentPose));
    let convertedTargetPose = adaptQuaternionForBackend(convertEulerToQuaternion(targetPose));
    const res = await fetch("api/trajectory/generate", {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
        current_pose: convertedCurrentPose,   // { position: [x,y,z], orientation: [x,y,z,w] }
        target_pose: convertedTargetPose
        })
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(`Trajectory request failed: ${JSON.stringify(err.detail)}`);
    }

    const data = await res.json();
    let trajectory = data.waypoints.map((pose: BackendQuaternionPose) => convertQuaternionToEuler(adaptBackendQuaternion(pose)));
    currentTrajectory.set(trajectory);
    return trajectory;
}