import * as THREE from 'three';
import type { EulerPose } from '$lib/types';

export interface SplineTrajectoryViewerOptions {
	backgroundColor?: number;
}

function toVector3(pose: EulerPose) {
	return new THREE.Vector3(pose.position[0], pose.position[1], pose.position[2]);
}

export interface SplineTrajectoryObjectOptions {
	lineColor?: number;
	pointColor?: number;
	pointSize?: number;
}

export class SplineTrajectoryObjectBuilder {
	private options: SplineTrajectoryObjectOptions;

	constructor(options: SplineTrajectoryObjectOptions = {}) {
		this.options = options;
	}

	create(trajectory: EulerPose[]): THREE.Group {
		const group = new THREE.Group();
		group.name = 'trajectory-waypoints';

		if (trajectory.length === 0) {
			return group;
		}

		const points = trajectory.map(toVector3);

		const pointGeometry = new THREE.BufferGeometry().setFromPoints(points);
		const pointMaterial = new THREE.PointsMaterial({
			color: this.options.pointColor ?? 0x22c55e,
			size: this.options.pointSize ?? 0.01,
			sizeAttenuation: true
		});
		group.add(new THREE.Points(pointGeometry, pointMaterial));

		if (points.length > 1) {
			const lineGeometry = new THREE.BufferGeometry().setFromPoints(points);
			const lineMaterial = new THREE.LineBasicMaterial({
				color: this.options.lineColor ?? 0x7dd3fc,
				opacity: 0.95,
				transparent: true
			});
			group.add(new THREE.Line(lineGeometry, lineMaterial));
		}

		return group;
	}
}