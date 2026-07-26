import { writable } from 'svelte/store';
import type { Detection3D, DetectionWorld } from '$lib/types';

/** Current detection results from the YOLO endpoint. */
export const detections = writable<Detection3D[]>([]);

/** Current world-frame detection results from the /detect/world endpoint. */
export const worldDetections = writable<DetectionWorld[]>([]);

/** True while a detect request is in-flight. */
export const isDetecting = writable<boolean>(false);

/** True while a world detect request is in-flight. */
export const isWorldDetecting = writable<boolean>(false);

/** Error message from the last detect attempt, if any. */
export const detectionError = writable<string | null>(null);

/** Error message from the last world detect attempt, if any. */
export const worldDetectionError = writable<string | null>(null);
