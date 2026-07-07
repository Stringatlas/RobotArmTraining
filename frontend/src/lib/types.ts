export type EulerPose = {position: [number, number, number], orientation: [number, number, number]};
export type QuaternionPose = {position: [number, number, number], orientation: [number, number, number, number]};
export type RobotJointName = 'joint_1' | 'joint_2' | 'joint_3' | 'joint_4' | 'joint_5' | 'joint_6';
export type RobotJointValues = Record<RobotJointName, number>;