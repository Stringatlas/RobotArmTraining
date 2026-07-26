<script lang="ts">
	import NavBar from '$lib/components/NavBar.svelte';
	let { children } = $props();
</script>

<svelte:head>

</svelte:head>

<div class="layout">
	<div class="top-bar">
		<NavBar />
	</div>
	<div class="page-content">
		{@render children()}
	</div>
</div>

<style>
	:global(body) {
		margin: 0;
		height: 100vh;
		overflow: hidden;
		background: #0f172a;
	}

	:global(html) {
		height: 100vh;
		overflow: hidden;
		background: #0f172a;
	}

	.layout {
		display: grid;
		grid-template-rows: auto 1fr;
		height: 100vh;
		background: #0f172a;
	}

	.top-bar {
		border-bottom: 1px solid #334155;
		background: #111827;
	}

	.page-content {
		min-height: 0;
		overflow: hidden;
	}
</style>
