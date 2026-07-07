<script lang="ts">
    import TestPanel from '$lib/components/TestPanel.svelte';
	import Scene from '$lib/components/Scene.svelte';
	import WebStream from '$lib/components/CamStream.svelte';
    import { toolheadPose } from '$lib/state/robotState';

</script>

<div class="page-shell">
	<div class="main-grid">
		<div class="left-panel">
			<TestPanel />
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
</div>

<style>
	.page-shell {
		min-height: 100vh;
		display: grid;
		grid-template-rows: auto 1fr;
		background: #0f172a;
	}


	.main-grid {
		display: grid;
		grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
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
	}

	.right-panel {
		display: grid;
		grid-template-rows: minmax(0, 1fr) minmax(0, 1fr);
		min-height: 0;
	}

	.scene-panel {
		min-height: 0;
		border-bottom: 1px solid #334155;
	}

	.stream-panel {
		background: #111827;
	}

	:global(body) {
		margin: 0;
		min-height: 100vh;
		background: #0f172a;
	}

	:global(html) {
		min-height: 100vh;
		background: #0f172a;
	}
</style>