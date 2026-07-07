<script lang="ts">
	import NavBar from '$lib/components/NavBar.svelte';
	let { children } = $props();
</script>

<svelte:head>

</svelte:head>

<div class="top-bar">
    <NavBar />
</div>

{@render children()}

<style>
    .top-bar {
		border-bottom: 1px solid #334155;
		background: #111827;
	}
</style>