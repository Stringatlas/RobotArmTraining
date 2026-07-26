<script lang="ts">
	import ControlPanel from '$lib/components/ControlPanel.svelte';
	import Scene from '$lib/components/Scene.svelte';
	import WebStream from '$lib/components/CamStream.svelte';
</script>

<div class="main-grid">
	<div class="left-panel">
		<ControlPanel />
	</div>

	<div class="right-panel">
		<div class="scene-panel">
			<Scene urdfUrl="/robot/urdf/lm3_with_gripper.urdf" workingPath="robot/meshes/" />
		</div>

		<div class="stream-panel">
			<WebStream />
		</div>
	</div>
</div>

<style>
	.main-grid {
		display: grid;
		grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
		height: 100%;
		min-height: 0;
	}

	.left-panel,
	.right-panel,
	.scene-panel,
	.stream-panel {
		min-width: 0;
		min-height: 0;
	}

	.left-panel {
		border-right: 1px solid #334155;
		background: #0b1220;
		overflow-y: auto;
	}

	.right-panel {
		display: grid;
		grid-template-rows: 1fr 1fr;
		min-height: 0;
	}

	.scene-panel {
		min-height: 0;
		border-bottom: 1px solid #334155;
	}

	.stream-panel {
		min-height: 0;
		background: #111827;
	}
</style>
