<script lang="ts">
	import {
		batchSize,
		batchSeed,
		currentBatchID,
		currentEpisodeIndex,
		objectClass,
		pollingInterval,
		robotState,
		trainingState
	} from '$lib/state/trainingState';
</script>

<div class="panel">
	<section class="section">
		<h2>Batch</h2>

		<label>
			<span>Batch ID</span>
			<input type="text" bind:value={$currentBatchID} />
		</label>

		<label>
			<span>Batch Size</span>
			<input type="number" min="0" bind:value={$batchSize} />
		</label>

		<label>
			<span>Object</span>
			<input type="text" bind:value={$objectClass} />
		</label>

		<label>
			<span>Batch Seed</span>
			<input type="number" bind:value={$batchSeed} />
		</label>

		<label>
			<span>Polling Interval (ms)</span>
			<input type="number" min="0" bind:value={$pollingInterval} />
		</label>
	</section>

	<section class="section">
		<h2>Status</h2>

		<label>
			<span>Current Episode</span>
			<input type="number" readonly value={$currentEpisodeIndex} />
		</label>

		<label>
			<span>Robot State</span>
			<input type="text" readonly value={$robotState} />
		</label>

		<label>
			<span>Training State</span>
			<input type="text" readonly value={$trainingState} />
		</label>
	</section>
</div>

<style>
	.panel {
		box-sizing: border-box;
		width: 100%;
		height: 100%;
		padding: 1rem;
		display: grid;
		gap: 1rem;
		align-content: start;
		background: #0b1220;
		color: #e2e8f0;
	}

	.section {
		display: grid;
		gap: 0.75rem;
		padding: 1rem;
		border: 1px solid #334155;
		background: #111827;
	}

	h2 {
		margin: 0;
		font-size: 1rem;
		font-weight: 600;
	}

	label {
		display: grid;
		gap: 0.35rem;
	}

	span {
		font-size: 0.875rem;
		color: #cbd5e1;
	}

	input {
		width: 100%;
		box-sizing: border-box;
		padding: 0.5rem 0.625rem;
		border: 1px solid #475569;
		border-radius: 0;
		background: #0f172a;
		color: #e2e8f0;
	}

	input[readonly] {
		background: #1e293b;
		color: #cbd5e1;
	}

	input:focus {
		outline: 2px solid #60a5fa;
		outline-offset: 1px;
	}
</style>