import type { EulerPose, QuaternionPose } from '$lib/types';
import { Euler, Quaternion } from 'three';

function convertEulerToQuaternion(pose: EulerPose): QuaternionPose {
    const q = new Quaternion().setFromEuler(
        new Euler(...pose.orientation, 'ZYX')
    );
    
    return {
        position: pose.position,
        orientation: [q.w, q.x, q.y, q.z]
    };
}

function convertQuaternionToEuler(pose: QuaternionPose): EulerPose {
    const e = new Euler().setFromQuaternion(
        new Quaternion(...pose.orientation),"ZYX"
    );

    return {
        position: pose.position,
        orientation: [e.x, e.y, e.z]
    };
}


async function requestTrajectory(currentPose: EulerPose, targetPose: EulerPose): Promise<QuaternionPose[]> {
    let convertedCurrentPose = convertEulerToQuaternion(currentPose);
    let convertedTargetPose = convertEulerToQuaternion(targetPose);
    const res = await fetch('http://localhost:8000/trajectory/generate', {
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
  return data.waypoints;
}