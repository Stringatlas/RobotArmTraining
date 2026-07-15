import { writable } from 'svelte/store';
import type { RobotJointName, RobotJointValues, EulerPose as ToolheadPose } from '$lib/types';

export const initialRobotJointValues: RobotJointValues = {
	joint_1: 0,
	joint_2: -1,
	joint_3: 2.4,
	joint_4: -1.4,
	joint_5: 1.57,
	joint_6: 0
};

export const robotJointValues = writable<RobotJointValues>({ ...initialRobotJointValues });
export const toolheadPose = writable<ToolheadPose>({x: 0, y: 0, z: 0, rx: 0, ry: 0,rz: 0});

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

export type RobotState = string;
export let robotState = writable<RobotState>('IDLE');
export let robotMovementState = writable<String>("idle");