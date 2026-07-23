export type EulerPose = {x: number, y: number, z: number, rx: number, ry: number, rz: number};
export type QuaternionPose = {x: number, y: number, z: number, rx: number, ry: number, rz: number, rw: number};
export type RobotJointName = 'joint_1' | 'joint_2' | 'joint_3' | 'joint_4' | 'joint_5' | 'joint_6';
export type RobotJointValues = Record<RobotJointName, number>;

export interface BBox {
	x1: number;
	y1: number;
	x2: number;
	y2: number;
}

export interface Detection3D {
	name: string;
	confidence: number;
	bbox: BBox;
	center_px: { cx: number; cy: number };
	depth_m: number | null;
	camera_xyz_m: [number, number, number] | null;
}
