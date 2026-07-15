export type EulerPose = {x: number, y: number, z: number, rx: number, ry: number, rz: number};
export type QuaternionPose = {x: number, y: number, z: number, rx: number, ry: number, rz: number, rw: number};
export type RobotJointName = 'joint_1' | 'joint_2' | 'joint_3' | 'joint_4' | 'joint_5' | 'joint_6';
export type RobotJointValues = Record<RobotJointName, number>;