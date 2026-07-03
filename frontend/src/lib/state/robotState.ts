import { writable } from 'svelte/store';
import type { Vec3 } from '$lib/components/splineVisualization/spline';

export type RobotJointName = 'joint_1' | 'joint_2' | 'joint_3' | 'joint_4' | 'joint_5' | 'joint_6';

export type RobotJointValues = Record<RobotJointName, number>;

export interface CurrentTrajectory {
	start: Vec3;
	end: Vec3;
	controlScaling: number;
	samplePoints: number;
	lineSamples: number;
}

export const initialRobotJointValues: RobotJointValues = {
	joint_1: 0,
	joint_2: 0,
	joint_3: 0,
	joint_4: 0,
	joint_5: 0,
	joint_6: 0
};

export const robotState = writable<RobotJointValues>({ ...initialRobotJointValues });

export const initialCurrentTrajectory: CurrentTrajectory = {
	start: [0, 0, 0],
	end: [-0.5, 0.5, 0.5],
	controlScaling: 1,
	samplePoints: 10,
	lineSamples: 100
};

export const currentTrajectory = writable<CurrentTrajectory>({ ...initialCurrentTrajectory });

export function setRobotJoint(name: RobotJointName, value: number) {
	robotState.update((state) => ({
		...state,
		[name]: value
	}));
}

export function setRobotJoints(values: Partial<RobotJointValues>) {
	robotState.update((state) => ({
		...state,
		...values
	}));
}

export function resetRobotJoints() {
	robotState.set({ ...initialRobotJointValues });
}

export function setCurrentTrajectory(values: Partial<CurrentTrajectory>) {
	currentTrajectory.update((state) => ({
		...state,
		...values
	}));
}

export function resetCurrentTrajectory() {
	currentTrajectory.set({ ...initialCurrentTrajectory });
}
