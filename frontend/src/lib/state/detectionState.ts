import { writable } from 'svelte/store';
import type { Detection3D } from '$lib/types';

/** Current detection results from the YOLO endpoint. */
export const detections = writable<Detection3D[]>([]);

/** True while a detect request is in-flight. */
export const isDetecting = writable<boolean>(false);

/** Error message from the last detect attempt, if any. */
export const detectionError = writable<string | null>(null);