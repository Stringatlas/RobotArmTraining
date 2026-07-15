import { writable } from 'svelte/store';
import { robotJointValues, toolheadPose, robotMovementState } from '$lib/state/robotState';
import type { RobotJointValues, EulerPose as ToolheadPose } from '$lib/types'; 

const WS_PATH = '/api/telemetry/ws';
const RECONNECT_DELAY_MS = 2000;
const STALE_TIMEOUT_MS = 3000;

export type TelemetryStatus = 'disconnected' | 'connecting' | 'connected' | 'stale';
export const telemetryStatus = writable<TelemetryStatus>('disconnected');

// --- Conversion functions -------------------------------------------------

/**
 * Backend sends joint_pos as a flat 6-element array in joint order
 * [joint_1..joint_6]. Convert to the named-key shape the store expects.
 */
function toRobotJointValues(jointPos: number[]): RobotJointValues {
	if (jointPos.length !== 6) {
		throw new Error(`Expected 6 joint values, got ${jointPos.length}`);
	}
	return {
		joint_1: jointPos[0],
		joint_2: jointPos[1],
		joint_3: jointPos[2],
		joint_4: jointPos[3],
		joint_5: jointPos[4],
		joint_6: jointPos[5]
	};
}


// --- Wire message shape -----------------------------------------------

interface TelemetryMessage {
	joint_pos: number[];
	tcp_pose: { x: number; y: number; z: number; rx: number; ry: number; rz: number };
	state: string;
	ts: number;
}

function isTelemetryMessage(msg: unknown): msg is TelemetryMessage {
	if (typeof msg !== 'object' || msg === null) return false;
	const m = msg as Record<string, unknown>;
	return (
		Array.isArray(m.joint_pos) &&
		typeof m.tcp_pose === 'object' &&
		m.tcp_pose !== null &&
		typeof m.state === 'string' &&
		typeof m.ts === 'number'
	);
}

// --- Connection lifecycle -----------------------------------------------

let socket: WebSocket | null = null;
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let staleTimer: ReturnType<typeof setTimeout> | null = null;
let manuallyClosed = false;

/** Latest raw robot state string (e.g. "TEACHING"), exposed for UI badges etc. */
export let latestRobotState: string | null = null;

function clearStaleTimer(): void {
	if (staleTimer !== null) {
		clearTimeout(staleTimer);
		staleTimer = null;
	}
}

/** Called on every successfully-applied message: marks connected, resets staleness clock. */
function markMessageReceived(): void {
	telemetryStatus.set('connected');
	clearStaleTimer();
	staleTimer = setTimeout(() => {
		telemetryStatus.set('stale');
	}, STALE_TIMEOUT_MS);
}

function connect(): void {
	if (manuallyClosed) return;

	telemetryStatus.set('connecting');

	const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
	const url = `${protocol}//${window.location.host}${WS_PATH}`;

	socket = new WebSocket(url);

	socket.onopen = () => {
		console.info('[telemetry] connected');
		// Socket is open, but no data has arrived yet — don't claim 'connected'
		// (i.e. "updating") until the first message actually lands.
	};

	socket.onmessage = (event: MessageEvent) => {
		let parsed: unknown;
		try {
			parsed = JSON.parse(event.data);
		} catch (err) {
			console.warn('[telemetry] malformed JSON, skipping', err);
			return;
		}

		if (!isTelemetryMessage(parsed)) {
			console.warn('[telemetry] unexpected message shape, skipping', parsed);
			return;
		}

		try {
			robotJointValues.set(toRobotJointValues(parsed.joint_pos));
			toolheadPose.set(parsed.tcp_pose);
            robotMovementState.set(parsed.state);
			latestRobotState = parsed.state;
			markMessageReceived();
		} catch (err) {
			console.warn('[telemetry] failed to apply message', err);
		}
	};

	socket.onerror = (event: Event) => {
		console.warn('[telemetry] socket error', event);
	};

	socket.onclose = () => {
		socket = null;
		clearStaleTimer();
		if (!manuallyClosed) {
			telemetryStatus.set('disconnected');
			reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
		}
	};
}

export function startTelemetry(): void {
	manuallyClosed = false;
	if (socket === null) connect();
}

export function stopTelemetry(): void {
	manuallyClosed = true;
	if (reconnectTimer !== null) {
		clearTimeout(reconnectTimer);
		reconnectTimer = null;
	}
	clearStaleTimer();
	socket?.close();
	socket = null;
	telemetryStatus.set('disconnected');
}