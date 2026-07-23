import type { Detection3D } from '$lib/types';
import { detections, isDetecting, detectionError } from '$lib/state/detectionState';

const DETECT_URL = '/api/detect';

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