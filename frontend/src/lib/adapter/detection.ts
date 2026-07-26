import type { Detection3D, DetectionWorld } from '$lib/types';
import { detections, isDetecting, detectionError, worldDetections, isWorldDetecting, worldDetectionError } from '$lib/state/detectionState';

const DETECT_URL = '/api/detect';
const DETECT_WORLD_URL = '/api/detect/world';

export async function runDetection(): Promise<Detection3D[]> {
	isDetecting.set(true);
	detectionError.set(null);

	try {
		const res = await fetch(DETECT_URL, { method: 'POST' });

		if (!res.ok) {
			const err = await res.json().catch(() => ({ detail: res.statusText }));
			throw new Error(err.detail ?? `Detection request failed (${res.status})`);
		}

		const data = await res.json();
        console.log(data)
		const result: Detection3D[] = data.detections ?? [];
		detections.set(result);
		return result;
	} catch (e: unknown) {
		const msg = e instanceof Error ? e.message : String(e);
		detectionError.set(msg);
		detections.set([]);
		return [];
	} finally {
		isDetecting.set(false);
	}
}

export async function runWorldDetection(): Promise<DetectionWorld[]> {
	isWorldDetecting.set(true);
	worldDetectionError.set(null);

	try {
		const res = await fetch(DETECT_WORLD_URL, { method: 'POST' });

		if (!res.ok) {
			const err = await res.json().catch(() => ({ detail: res.statusText }));
			throw new Error(err.detail ?? `World detection request failed (${res.status})`);
		}

		const data = await res.json();
		const result: DetectionWorld[] = data.detections ?? [];
		worldDetections.set(result);
		return result;
	} catch (e: unknown) {
		const msg = e instanceof Error ? e.message : String(e);
		worldDetectionError.set(msg);
		worldDetections.set([]);
		return [];
	} finally {
		isWorldDetecting.set(false);
	}
}
