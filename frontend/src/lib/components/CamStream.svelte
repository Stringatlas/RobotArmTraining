<script lang="ts">
	import { onMount } from 'svelte';
	import { cameraFrameUrl, cameraStatus, startCameraStream, stopCameraStream } from '$lib/state/videoStream';
	import { detections, isDetecting, detectionError } from '$lib/state/detectionState';
	import { runDetection } from '$lib/adapter/detection';

	let canvas = $state<HTMLCanvasElement>();
	let ctx = $state<CanvasRenderingContext2D | null>(null);

	onMount(() => {
		if (canvas) ctx = canvas.getContext('2d');
	});

	function toggleStream() {
		if ($cameraStatus === 'disconnected') {
			startCameraStream();
		} else {
			stopCameraStream();
		}
	}

	// Redraw overlay whenever detections or frame changes
	$effect(() => {
		if (ctx && $cameraFrameUrl && $detections.length > 0) {
			drawOverlay();
		} else if (ctx) {
			ctx.clearRect(0, 0, 640, 480);
		}
	});

	function drawOverlay() {
		if (!ctx) return;
		ctx.clearRect(0, 0, 640, 480);

		for (const d of $detections) {
			const { x1, y1, x2, y2 } = d.bbox;

			// Bounding box
			ctx.strokeStyle = '#00ff88';
			ctx.lineWidth = 2;
			ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);

			// Center dot
			ctx.fillStyle = '#ff3333';
			ctx.beginPath();
			ctx.arc(d.center_px.cx, d.center_px.cy, 4, 0, 2 * Math.PI);
			ctx.fill();

			// Label
			ctx.fillStyle = '#00ff88';
			ctx.font = 'bold 13px monospace';
			ctx.fillText(`${d.name} ${(d.confidence * 100).toFixed(0)}%`, x1 + 2, y1 - 6);
		}
	}

	async function handleDetect() {
		await runDetection();
	}
</script>

<div class="camera-panel">
	{#if $cameraFrameUrl}
		<div class="frame-wrapper">
			<img
				src={$cameraFrameUrl}
				alt="Camera feed"
				class="camera-feed"
				width={640}
				height={480}
			/>
			<canvas
				bind:this={canvas}
				width={640}
				height={480}
				class="overlay-canvas"
			></canvas>
			<div class="controls">
				<button class="ctrl-btn" onclick={handleDetect} disabled={$isDetecting}>
					{$isDetecting ? 'Detecting…' : 'Detect'}
				</button>
				<button class="ctrl-btn" onclick={toggleStream}>Stop Stream</button>
			</div>
		</div>
		{#if $detectionError}
			<div class="error-msg">{$detectionError}</div>
		{/if}
	{:else}
		<div class="placeholder">
			<p>Camera feed</p>
			<p class="status">{$cameraStatus}</p>
			{#if $cameraStatus === 'disconnected'}
				<button onclick={toggleStream}>Start Stream</button>
			{/if}
		</div>
	{/if}
</div>

<style>
	.camera-panel {
		position: relative;
		width: 100%;
		height: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		overflow: hidden;
		background: #111;
	}

	.frame-wrapper {
		position: relative;
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.camera-feed {
		width: 100%;
		height: 100%;
		object-fit: contain;
		display: block;
	}

	.overlay-canvas {
		position: absolute;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		pointer-events: none;
	}

	.controls {
		position: absolute;
		bottom: 0.5rem;
		right: 0.5rem;
		display: flex;
		gap: 0.4rem;
	}

	.ctrl-btn {
		padding: 0.25rem 0.5rem;
		border: 1px solid #475569;
		background: #1e293b;
		color: #e2e8f0;
		cursor: pointer;
		font-size: 0.8rem;
	}

	.ctrl-btn:hover:not(:disabled) {
		background: #334155;
	}

	.ctrl-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.error-msg {
		position: absolute;
		bottom: 2.5rem;
		left: 0.5rem;
		color: #ff6666;
		font-family: monospace;
		font-size: 0.75rem;
		background: rgba(0, 0, 0, 0.7);
		padding: 0.2rem 0.4rem;
		border-radius: 3px;
	}

	.placeholder {
		color: #666;
		text-align: center;
		font-family: monospace;
		display: grid;
		gap: 0.5rem;
		place-items: center;
	}

	.status {
		font-size: 0.8em;
		text-transform: uppercase;
	}

	button {
		width: fit-content;
		padding: 0.25rem 0.5rem;
		border: 1px solid #475569;
		background: #1e293b;
		color: #e2e8f0;
		cursor: pointer;
	}

	button:hover {
		background: #334155;
	}
</style>