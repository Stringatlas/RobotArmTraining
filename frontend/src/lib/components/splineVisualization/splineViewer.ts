import * as THREE from 'three';
import { Spline3D, type Vec3 } from './spline';
import type { CurrentTrajectory } from '$lib/state/robotState';

export interface SplineTrajectoryViewerOptions {
	backgroundColor?: number;
}

function toVector3(value: Vec3) {
	return new THREE.Vector3(value[0], value[1], value[2]);
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

	create(trajectory: CurrentTrajectory): THREE.Group {
		const spline = new Spline3D(trajectory.start, trajectory.end, trajectory.controlScaling);
		const samplePointCount = Math.max(2, Math.floor(trajectory.samplePoints));
		const linePointCount = Math.max(2, Math.floor(trajectory.lineSamples));

		const group = new THREE.Group();
		group.name = 'spline-trajectory';

		const linePoints = spline.sampleUniform(linePointCount);
		const lineGeometry = new THREE.BufferGeometry().setFromPoints(linePoints.map(toVector3));
		const lineMaterial = new THREE.LineBasicMaterial({
			color: this.options.lineColor ?? 0x7dd3fc,
			opacity: 0.95,
			transparent: true
		});
		group.add(new THREE.Line(lineGeometry, lineMaterial));

		const samplePoints = spline.sampleArcLength(samplePointCount);
		const pointGeometry = new THREE.BufferGeometry().setFromPoints(samplePoints.map(toVector3));
		const pointMaterial = new THREE.PointsMaterial({
			color: this.options.pointColor ?? 0x22c55e,
			size: this.options.pointSize ?? 0.06,
			sizeAttenuation: true
		});
		group.add(new THREE.Points(pointGeometry, pointMaterial));

		return group;
	}
}