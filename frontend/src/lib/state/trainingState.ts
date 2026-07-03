import {writable} from 'svelte/store';

// Batch parameters
export let currentBatchID = writable<string>('BatchID');
export let batchSize = writable<number>(0);
export let objectClass = writable<string>('Coke Can');
export let batchSeed = writable<number>(0);
export let pollingInterval = writable<number>(100);

export let currentEpisodeIndex = writable<number>(0);

export type RobotState = 'Idle' | 'Running' | 'Paused';
export let robotState = writable<RobotState>('Idle');

export type TrainingState = 'Idle' | 'YOLO Detection' | 'Trajectory Generation' | 'Executing Trajectory';
export let trainingState = writable<TrainingState>('Idle');

export let currentTCPPose = writable<[number, number, number, number, number, number]>([0, 0, 0, 0, 0, 0]);
export let detectedObjectPosition = writable<[number, number, number] | null>(null);