<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { cameraFrameUrl, cameraStatus, startCameraStream, stopCameraStream } from '$lib/state/videoStream';

	onMount(() => {
		startCameraStream();
	});

	onDestroy(() => {
		stopCameraStream();
	});
</script>

<div class="camera-panel">
	{#if $cameraFrameUrl}
		<img src={$cameraFrameUrl} alt="Camera feed" class="camera-feed" />
	{:else}
		<div class="placeholder">
			<p>Camera feed</p>
			<p class="status">{$cameraStatus}</p>
		</div>
	{/if}
</div>

<style>
	.camera-panel {
		width: 100%;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
		background: #111;
	}

	.camera-feed {
		width: 100%;
		height: 100%;
		object-fit: contain;
	}

	.placeholder {
		color: #666;
		text-align: center;
		font-family: monospace;
	}

	.status {
		font-size: 0.8em;
		margin-top: 0.5em;
		text-transform: uppercase;
	}
</style>