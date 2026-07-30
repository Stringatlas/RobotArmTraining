import { writable } from 'svelte/store';

export type RecordingStatus = 'idle' | 'recording' | 'saving';

export const recordingStatus = writable<RecordingStatus>('idle');
export const recordingElapsed = writable<number>(0);
export const currentEpisodeId = writable<string>('');

let elapsedInterval: ReturnType<typeof setInterval> | null = null;

function clearElapsedTimer(): void {
	if (elapsedInterval !== null) {
		clearInterval(elapsedInterval);
		elapsedInterval = null;
	}
}

function startElapsedTimer(): void {
	clearElapsedTimer();
	recordingElapsed.set(0);
	elapsedInterval = setInterval(() => {
		recordingElapsed.update(v => v + 0.1);
	}, 100);
}

export async function startRecording(
	batchId: string = '',
	objectClass: string = '',
	languageInstruction: string = ''
): Promise<void> {
	recordingStatus.set('recording');
	startElapsedTimer();

	try {
		const res = await fetch('/api/recording/start', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				batch_id: batchId,
				object_class: objectClass,
				language_instruction: languageInstruction
			})
		});

		if (!res.ok) {
			const err = await res.json();
			throw new Error(`Failed to start recording: ${JSON.stringify(err.detail)}`);
		}

		const data = await res.json();
		currentEpisodeId.set(data.episode_id);
	} catch (err) {
		recordingStatus.set('idle');
		clearElapsedTimer();
		recordingElapsed.set(0);
		throw err;
	}
}

export async function stopRecording(): Promise<{
	episode_id: string;
	batch_id: string;
	hdf5_path: string;
	duration_s: number;
	n_frames: number;
	n_telemetry_samples: number;
}> {
	recordingStatus.set('saving');
	clearElapsedTimer();

	const res = await fetch('/api/recording/stop', {
		method: 'POST'
	});

	if (!res.ok) {
		const err = await res.json();
		recordingStatus.set('idle');
		recordingElapsed.set(0);
		throw new Error(`Failed to stop recording: ${JSON.stringify(err.detail)}`);
	}

	const data = await res.json();
	recordingStatus.set('idle');
	recordingElapsed.set(0);
	currentEpisodeId.set(data.episode_id);
	return data;
}

export async function getRecordingStatus(): Promise<{
	recording: boolean;
	batch_id: string;
	episode_id: string;
	elapsed_s: number;
}> {
	const res = await fetch('/api/recording/status');
	if (!res.ok) {
		throw new Error('Failed to get recording status');
	}
	return res.json();
}