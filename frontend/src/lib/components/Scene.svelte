<script lang="ts">
	import * as THREE from 'three';
	import { onDestroy, onMount } from 'svelte';
	import RobotCanvas from './robotVisualization/RobotCanvas.svelte';
	import { RobotViewer } from './robotVisualization/robotViewer';
	import { SplineTrajectoryObjectBuilder } from './splineVisualization/splineViewer';
	import { currentTrajectory } from '$lib/state/trajectoryState';
	import {
		initialRobotJointValues,
		robotJointValues,
		setRobotJoint,
	} from '$lib/state/robotState';
	import type { EulerPose, RobotJointName } from '$lib/types';

	interface Props {
		urdfUrl: string;
		workingPath: string;
		backgroundColor?: number;
	}

	type JointRange = { lower: number; upper: number };

	const JOINTS = [
		{ name: 'joint_1', label: 'Joint 1' },
		{ name: 'joint_2', label: 'Joint 2' },
		{ name: 'joint_3', label: 'Joint 3' },
		{ name: 'joint_4', label: 'Joint 4' },
		{ name: 'joint_5', label: 'Joint 5' },
		{ name: 'joint_6', label: 'Joint 6' }
	] as const satisfies Array<{ name: RobotJointName; label: string }>;

	const DEFAULT_LIMIT: JointRange = { lower: -6.28, upper: 6.28 };

	const splineBuilder = new SplineTrajectoryObjectBuilder({ pointSize: 0.03 });

	let {
		urdfUrl,
		workingPath,
		backgroundColor = undefined
	}: Props = $props();

	let viewer = $state<RobotViewer | undefined>(undefined);
	let jointValues = $state({ ...initialRobotJointValues });
	let jointLimits = $state<Partial<Record<RobotJointName, JointRange>>>({});
	let showTrajectory = $state(true);
	let showJoints = $state(true);
	let currentTrajectoryValue = $state<EulerPose[]>([]);

	let trajectoryObject: THREE.Group | undefined;

	function formatAngle(value: number) {
		return `${value.toFixed(2)}`;
	}

	function getLimits(name: RobotJointName): JointRange {
		return jointLimits[name] ?? DEFAULT_LIMIT;
	}

	function setJointFromInput(name: RobotJointName, event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		const value = Number(input.value);
		setRobotJoint(name, value);
	}

	function disposeObject(object: THREE.Object3D) {
		object.traverse((child) => {
			const mesh = child as THREE.Mesh;
			if (mesh.geometry) {
				mesh.geometry.dispose();
			}

			const material = mesh.material;
			if (Array.isArray(material)) {
				material.forEach((item) => item.dispose());
			} else if (material) {
				(material as THREE.Material).dispose();
			}
		});
	}

	function syncSplineObject() {
		if (trajectoryObject && viewer) {
			viewer.removeObject(trajectoryObject);
			disposeObject(trajectoryObject);
			trajectoryObject = undefined;
		}

		if (!viewer || !showTrajectory) return;

		const nextObject = splineBuilder.create(currentTrajectoryValue);
		viewer.addObject(nextObject);
		trajectoryObject = nextObject;
	}

	function syncJointLimits() {
		if (!viewer) return false;

		let updated = false;
		let ready = true;
		const nextLimits: Partial<Record<RobotJointName, JointRange>> = { ...jointLimits };

		for (const joint of JOINTS) {
			const limits = viewer.getJointLimits(joint.name);
			if (!limits) {
				ready = false;
				continue;
			}

			const current = nextLimits[joint.name];
			if (!current || current.lower !== limits.lower || current.upper !== limits.upper) {
				nextLimits[joint.name] = { lower: limits.lower, upper: limits.upper };
				updated = true;
			}
		}

		if (updated) {
			jointLimits = nextLimits;
		}

		return ready;
	}

	$effect(() => {
		const unsubscribe = robotJointValues.subscribe((values) => {
			jointValues = values;
		});

		return unsubscribe;
	});

	$effect(() => {
		const unsubscribe = currentTrajectory.subscribe((trajectory) => {
			currentTrajectoryValue = trajectory;
		});

		return unsubscribe;
	});

	$effect(() => {
		viewer;
		showTrajectory;
		currentTrajectoryValue;
		syncSplineObject();
	});

	onMount(() => {
		let frameId = 0;

		const pollLimits = () => {
			if (syncJointLimits()) return;
			frameId = requestAnimationFrame(pollLimits);
		};

		pollLimits();

		return () => cancelAnimationFrame(frameId);
	});

	onDestroy(() => {
		if (trajectoryObject && viewer) {
			viewer.removeObject(trajectoryObject);
			disposeObject(trajectoryObject);
		}
		trajectoryObject = undefined;
	});
</script>

<div class="scene-shell">
	<RobotCanvas
		bind:viewer_={viewer}
		urdfUrl={urdfUrl}
		workingPath={workingPath}
		backgroundColor={backgroundColor}
	/>

	<div class="slider-overlay" aria-label="Scene controls">
		<div class="toggle-row">
			<label class="toggle-row">
				<input bind:checked={showTrajectory} type="checkbox" aria-label="Show trajectory" />
				<span>Trajectory</span>
			</label>

			<label class="toggle-row">
				<input bind:checked={showJoints} type="checkbox" aria-label="Show joints" />
				<span>Joints</span>
			</label>
		</div>

		{#each JOINTS as joint}
			{@const limits = getLimits(joint.name)}
			{@const value = jointValues[joint.name]}
			<div class="slider-row">
				<span class="slider-label">{joint.label}</span>
				<span class="slider-value">{formatAngle(value)}</span>
				{#if showJoints}
					<input
						class="slider-input"
						type="range"
						min={limits.lower}
						max={limits.upper}
						step="0.01"
						value={value}
						aria-label={`${joint.label} angle`}
						aria-valuemin={limits.lower}
						aria-valuemax={limits.upper}
						aria-valuenow={value}
						oninput={(event) => setJointFromInput(joint.name, event)}
					/>
				{/if}
			</div>
		{/each}
	</div>
</div>

<style>
	.scene-shell {
		position: relative;
		width: 100%;
		height: 100%;
		min-height: 0;
		overflow: hidden;
		background: #0b1220;
	}

	.scene-shell :global(.robot-canvas-wrapper) {
		width: 100%;
		height: 100%;
		min-height: 0;
	}

	.slider-overlay {
		position: absolute;
		z-index: 2;
		top: 1rem;
		left: 1rem;
		bottom: 1rem;
		width: fit-content;
        height: fit-content;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding: 0.5rem;
		background: transparent;
		border: 0;
		box-shadow: none;
		backdrop-filter: none;
		color: #eef4ff;
	}

	.toggle-row {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		font-size: 0.95rem;
		color: #eef4ff;
	}

	.toggle-row input {
		accent-color: #22c55e;
	}

	.slider-row {
		display: grid;
		grid-template-columns: 4rem 3rem minmax(0, 1fr);
		align-items: center;
		gap: 0.75rem;
		min-width: 0;
	}

	.slider-label,
	.slider-value {
		font-size: 0.92rem;
		line-height: 1.2;
		color: #eef4ff;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.slider-input {
		width: min(100%, 5rem);
		min-width: 0;
		margin: 0;
		background: transparent;
		appearance: auto;
		cursor: pointer;
		outline: none;
	}

	.slider-input:focus-visible {
		outline: 2px solid rgba(122, 205, 255, 0.65);
		outline-offset: 3px;
	}

	@media (max-width: 1080px) {
		.slider-overlay {
			width: min(26rem, 40vw);
		}
	}

	@media (max-width: 820px) {
		.slider-overlay {
			top: auto;
			left: 0.75rem;
			right: 0.75rem;
			bottom: 0.75rem;
			width: auto;
			max-height: 52vh;
		}

		.slider-row {
			grid-template-columns: 6rem 5rem minmax(0, 1fr);
		}
	}

	@media (max-width: 560px) {
		.slider-overlay {
			padding: 0.25rem;
			gap: 0.6rem;
		}

		.slider-row {
			grid-template-columns: 1fr;
			gap: 0.35rem;
		}
	}
</style>