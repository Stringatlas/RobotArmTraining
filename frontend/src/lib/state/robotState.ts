import { writable } from 'svelte/store';
import type { Vec3 } from '$lib/components/splineVisualization/spline';
import type { RobotJointName, RobotJointValues, EulerPose as ToolheadPose } from '$lib/types';

export interface Trajectory {
	start: Vec3;
	end: Vec3;
	controlScaling: number;
	samplePoints: number;
	lineSamples: number;
}

export const initialRobotJointValues: RobotJointValues = {
	joint_1: 0,
	joint_2: -1,
	joint_3: 2.4,
	joint_4: -1.4,
	joint_5: 1.57,
	joint_6: 0
};

export const robotJointValues = writable<RobotJointValues>({ ...initialRobotJointValues });
export const toolheadPose = writable<ToolheadPose>({position: [0, 0, 0], orientation: [0,0,0]});

export const initialCurrentTrajectory: Trajectory = {
	start: [0, 0, 0],
	end: [-0.5, 0.5, 0.5],
	controlScaling: 1,
	samplePoints: 10,
	lineSamples: 100
};

export const currentTrajectory = writable<Trajectory>({ ...initialCurrentTrajectory });

export function setRobotJoint(name: RobotJointName, value: number) {
	robotJointValues.update((state) => ({
		...state,
		[name]: value
	}));
}

export function setRobotJoints(values: Partial<RobotJointValues>) {
	robotJointValues.update((state) => ({
		...state,
		...values
	}));
}

export function resetRobotJoints() {
	robotJointValues.set({ ...initialRobotJointValues });
}

export function setCurrentTrajectory(values: Partial<Trajectory>) {
	currentTrajectory.update((state) => ({
		...state,
		...values
	}));
}

export function resetCurrentTrajectory() {
	currentTrajectory.set({ ...initialCurrentTrajectory });
}
