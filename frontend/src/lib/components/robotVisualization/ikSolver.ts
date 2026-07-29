import * as THREE from 'three';
import type { URDFRobot } from 'urdf-loader';

/**
 * Position-only CCD (Cyclic Coordinate Descent) IK solver.
 *
 * Works directly on the URDFRobot scene graph — no DH parameters needed.
 *
 * THE KEY CCD INVARIANT: each joint angle update is applied to the robot
 * immediately so the next joint in the same sweep sees the corrected arm
 * configuration, not the stale pose from the start of the pass.
 *
 * @param robot       The loaded URDFRobot.
 * @param jointNames  Revolute joint names ordered base → tip.
 * @param tcpFrame    Object3D whose world position is the end-effector.
 * @param target      Desired TCP world position (world space, metres).
 * @param iterations  CCD passes (default 20 — typically converges in < 10).
 * @returns           Record<jointName, angleRad> of the solved configuration.
 */
export function solveCCDIK(
	robot: URDFRobot,
	jointNames: string[],
	tcpFrame: THREE.Object3D,
	target: THREE.Vector3,
	iterations = 20
): Record<string, number> {
	// --- Snapshot current joint angles as the starting configuration ---
	const angles: Record<string, number> = {};
	for (const name of jointNames) {
		const joint = robot.joints[name];
		if (!joint) continue;
		const v = joint.jointValue;
		angles[name] = Array.isArray(v) ? (v[0] ?? 0) : ((v as unknown as number) ?? 0);
	}

	// Bring the scene up to date with the starting angles.
	robot.setJointValues(angles);
	robot.updateMatrixWorld(true);

	// --- CCD outer loop ---
	for (let iter = 0; iter < iterations; iter++) {
		// Read current TCP position (already up to date from previous iteration).
		const tcpPos = new THREE.Vector3();
		tcpFrame.getWorldPosition(tcpPos);

		// Early exit — 1 mm convergence threshold.
		if (tcpPos.distanceTo(target) < 0.001) break;

		// --- Inner sweep: tip joint → base joint ---
		for (let i = jointNames.length - 1; i >= 0; i--) {
			const name = jointNames[i];
			const joint = robot.joints[name];
			if (!joint || joint.jointType !== 'revolute') continue;

			// Refresh TCP and pivot from the live scene graph.
			// This is correct because we apply each joint update immediately (see below),
			// so by the time we reach joint i the scene reflects all corrections from
			// joints i+1 … tip already applied in this same sweep.
			tcpFrame.getWorldPosition(tcpPos);
			const pivot = new THREE.Vector3();
			joint.getWorldPosition(pivot);

			const toTcp = new THREE.Vector3().subVectors(tcpPos, pivot);
			const toTarget = new THREE.Vector3().subVectors(target, pivot);

			// Degenerate: TCP or target is at the pivot — skip.
			if (toTcp.lengthSq() < 1e-10 || toTarget.lengthSq() < 1e-10) continue;

			// --- World-space rotation axis ---
			// joint.axis is defined in the joint's local frame (after origin RPY).
			// Applying the joint's world quaternion to it gives the world-space axis.
			// The axis vector is invariant under rotation around itself, so the current
			// joint angle does NOT affect this result — it's mathematically exact.
			const axisLocal = (joint as unknown as { axis?: THREE.Vector3 }).axis;
			const axisWorld = new THREE.Vector3(
				axisLocal?.x ?? 0,
				axisLocal?.y ?? 0,
				axisLocal?.z ?? 1
			);
			const worldQuat = new THREE.Quaternion();
			joint.getWorldQuaternion(worldQuat);
			axisWorld.applyQuaternion(worldQuat).normalize();

			// --- Project both vectors onto the plane perpendicular to the axis ---
			const toTcpProj = toTcp.clone().addScaledVector(axisWorld, -toTcp.dot(axisWorld));
			const toTargetProj = toTarget.clone().addScaledVector(axisWorld, -toTarget.dot(axisWorld));

			// Skip if either projection is degenerate (vector nearly collinear with axis).
			if (toTcpProj.lengthSq() < 1e-8 || toTargetProj.lengthSq() < 1e-8) continue;

			toTcpProj.normalize();
			toTargetProj.normalize();

			// --- Signed angle in the rotation plane ---
			const cosA = Math.min(1, Math.max(-1, toTcpProj.dot(toTargetProj)));
			const cross = new THREE.Vector3().crossVectors(toTcpProj, toTargetProj);
			const sign = cross.dot(axisWorld) >= 0 ? 1 : -1;
			const delta = sign * Math.acos(cosA);

			// Clamp to URDF limits.
			const limit = joint.limit as { lower: number; upper: number };
			const newAngle = Math.min(
				limit.upper,
				Math.max(limit.lower, (angles[name] ?? 0) + delta)
			);
			angles[name] = newAngle;

			// KEY: apply immediately so the next joint's getWorldPosition / getWorldQuaternion
			// reflect the corrected arm configuration, not the stale pre-sweep pose.
			joint.setJointValue(newAngle);
			robot.updateMatrixWorld(true);
		}
	}

	return angles;
}
