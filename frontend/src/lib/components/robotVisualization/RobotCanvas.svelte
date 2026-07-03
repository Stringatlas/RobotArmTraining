<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { RobotViewer } from './robotViewer';
	import {
		robotState,
		setRobotJoint,
		setRobotJoints,
		type RobotJointName
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

    
	$effect(() => {
		viewer_ = viewer;
	});

	onMount(() => {
		const unsubscribe = robotState.subscribe((values) => {
			latestJointValues = values;
			viewer?.setJointAngles(values);
		});

		viewer = new RobotViewer(canvas, { urdfUrl, workingPath, backgroundColor });
		viewer
			.load()
			.then(() => {
				loaded = true;
				viewer?.setJointAngles(latestJointValues);
			})
			.catch((err) => {
				loadError = err instanceof Error ? err.message : String(err);
				console.error('[RobotCanvas] failed to load URDF', err);
			});

		return () => {
			unsubscribe();
		};
	});

	onDestroy(() => {
		viewer?.dispose();
	});

	export function setJointAngle(jointName: string, value: number) {
		if (!viewer?.setJointAngle(jointName, value)) return;
		setRobotJoint(jointName as RobotJointName, value);
	}

	export function setJointAngles(values: Record<string, number>) {
		viewer?.setJointAngles(values);
		setRobotJoints(values as Partial<Record<RobotJointName, number>>);
	}

	export function setJoint1(value: number) {
		setJointAngle('joint_1', value);
	}

	export function setJoint2(value: number) {
		setJointAngle('joint_2', value);
	}

	export function setJoint3(value: number) {
		setJointAngle('joint_3', value);
	}

	export function setJoint4(value: number) {
		setJointAngle('joint_4', value);
	}

	export function setJoint5(value: number) {
		setJointAngle('joint_5', value);
	}

	export function setJoint6(value: number) {
		setJointAngle('joint_6', value);
	}

	export function getJointNames(): string[] {
		return viewer?.getJointNames() ?? [];
	}
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