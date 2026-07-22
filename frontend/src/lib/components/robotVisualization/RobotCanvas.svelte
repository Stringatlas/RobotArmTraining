<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { RobotViewer } from './robotViewer';
	import {
		robotJointValues,
		toolheadPose,
		gripperValue,
	} from '$lib/state/robotState';

    interface Props {
        urdfUrl: string;
        workingPath: string;
        backgroundColor?: number;
		viewer_?: RobotViewer | undefined;
    }

    let {
        urdfUrl,
        workingPath,
        backgroundColor = undefined,
		viewer_ = $bindable(undefined)
    }: Props = $props();

	let canvas: HTMLCanvasElement;
	let viewer = $state<RobotViewer | undefined>(undefined);
	let loadError = $state<string | null>(null);
	let loaded = $state(false);
	let latestJointValues = $state({
		joint_1: 0,
		joint_2: 0,
		joint_3: 0,
		joint_4: 0,
		joint_5: 0,
		joint_6: 0
	});
	let latestGripperValue = $state(1);

	function syncToolheadPose() {
		const pose = viewer?.getToolheadCenterPose();
		if (!pose) return;
        const position = pose?.position;
        const rotation = pose.rotation;
		toolheadPose.set({x: position.x, y: position.y, z: position.z, rx: rotation.x, ry: rotation.y, rz: rotation.z});
	}
  
	$effect(() => {
		viewer_ = viewer;
	});

	onMount(() => {
		const unsubscribeJoints = robotJointValues.subscribe((values) => {
			latestJointValues = values;
			viewer?.setJointAngles(values);
			syncToolheadPose();
		});

		const unsubscribeGripper = gripperValue.subscribe((value) => {
			latestGripperValue = value;
			viewer?.setGripperValue(value);
			syncToolheadPose();
		});

		viewer = new RobotViewer(canvas, { urdfUrl, workingPath, backgroundColor });
		viewer
			.load()
			.then(() => {
				loaded = true;
				viewer?.setJointAngles(latestJointValues);
				viewer?.setGripperValue(latestGripperValue);
				syncToolheadPose();
			})
			.catch((err) => {
				loadError = err instanceof Error ? err.message : String(err);
				console.error('[RobotCanvas] failed to load URDF', err);
			});

		return () => {
			unsubscribeJoints();
			unsubscribeGripper();
		};
	});

	onDestroy(() => {
		viewer?.dispose();
	});
</script>

<div class="robot-canvas-wrapper">
	<canvas bind:this={canvas}></canvas>
	{#if loadError}
		<div class="overlay error">Failed to load robot: {loadError}</div>
	{:else if !loaded}
		<div class="overlay">Loading robot…</div>
	{/if}
</div>

<style>
	.robot-canvas-wrapper {
		position: relative;
		width: 100%;
		height: 100%;
	}

	canvas {
		display: block;
		width: 100%;
		height: 100%;
	}

	.overlay {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		color: #eee;
		font-family: sans-serif;
		pointer-events: none;
		background: rgba(0, 0, 0, 0.15);
	}

	.overlay.error {
		color: #ff8080;
	}
</style>