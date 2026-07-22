import { writable } from 'svelte/store';

const CAMERA_WS_PATH = '/api/telemetry/ws/camera';
const RECONNECT_DELAY_MS = 2000;

export type CameraStatus = 'disconnected' | 'connecting' | 'connected';
export const cameraStatus = writable<CameraStatus>('disconnected');

/** Latest frame as an object URL (blob:…). Subscribe to this to display the feed. */
export const cameraFrameUrl = writable<string | null>(null);

// --- Connection lifecycle ---------------------------------------------------

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let manuallyClosed = false;

/** Revoke the previous blob URL to avoid memory leaks. */
let previousBlobUrl: string | null = null;

function setFrameBlob(blob: Blob): void {
	if (previousBlobUrl !== null) {
		URL.revokeObjectURL(previousBlobUrl);
	}
	const url = URL.createObjectURL(blob);
	previousBlobUrl = url;
	cameraFrameUrl.set(url);
}

function connect(): void {
	if (manuallyClosed) return;

	cameraStatus.set('connecting');

	const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
	const url = `${protocol}//${window.location.host}${CAMERA_WS_PATH}`;

	socket = new WebSocket(url);

	socket.onopen = () => {
		console.info('[camera] connected');
	};

	socket.onmessage = (event: MessageEvent) => {
		// The backend sends: JSON text (frame metadata), then binary (JPEG bytes).
		// We only care about the binary JPEG — the JSON is informational.
		if (event.data instanceof Blob) {
			setFrameBlob(event.data);
			cameraStatus.set('connected');
		}
		// Text messages (frame metadata) are ignored for now.
	};

	socket.onerror = (event: Event) => {
		console.warn('[camera] socket error', event);
	};

	socket.onclose = () => {
		socket = null;
		if (!manuallyClosed) {
			cameraStatus.set('disconnected');
			reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
		}
	};
}

export function startCameraStream(): void {
	manuallyClosed = false;
	if (socket === null) connect();
}

export function stopCameraStream(): void {
	manuallyClosed = true;
	if (reconnectTimer !== null) {
		clearTimeout(reconnectTimer);
		reconnectTimer = null;
	}
	if (previousBlobUrl !== null) {
		URL.revokeObjectURL(previousBlobUrl);
		previousBlobUrl = null;
	}
	cameraFrameUrl.set(null);
	socket?.close();
	socket = null;
	cameraStatus.set('disconnected');
}