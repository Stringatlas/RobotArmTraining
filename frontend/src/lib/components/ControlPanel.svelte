<script lang="ts">
	import {
		languageInstruction,
		currentBatchID,
		currentEpisodeIndex,
		objectClass,
		trainingState
	} from '$lib/state/trainingState';

    import { robotState } from '$lib/state/robotState';
    import {
        recordingStatus,
        recordingElapsed,
        currentEpisodeId,
        startRecording,
        stopRecording
    } from '$lib/adapter/recording';

    let errorMsg = $state("");

    async function handleStart() {
        errorMsg = '';
        try {
            await startRecording($currentBatchID, $objectClass, $languageInstruction);
        } catch (e) {
            errorMsg = String(e);
        }
    }

    async function handleStop() {
        errorMsg = '';
        try {
            const result = await stopRecording();
            console.log('Recording saved:', result);
        } catch (e) {
            errorMsg = String(e);
        }
    }
</script>

<div class="panel">
	<section class="section">
		<h2>Batch</h2>

		<label>
			<span>Batch ID</span>
			<input type="text" bind:value={$currentBatchID} />
		</label>

		<label>
			<span>Language instruction</span>
			<input type="text" min="0" bind:value={$languageInstruction} />
		</label>

		<label>
			<span>Object</span>
			<input type="text" bind:value={$objectClass} />
		</label>
	</section>

	<section class="section">
		<h2>Recording</h2>

		{#if $recordingStatus === 'idle'}
			<button class="rec-btn start" onclick={handleStart}>
				Start Recording
			</button>
		{:else if $recordingStatus === 'recording'}
			<div class="recording-indicator">● Recording</div>
			<div class="elapsed">{$recordingElapsed.toFixed(1)}s</div>
			<button class="rec-btn stop" onclick={handleStop}>
				Stop & Save
			</button>
		{:else if $recordingStatus === 'saving'}
			<div class="recording-indicator saving">Saving episode…</div>
		{/if}

		{#if errorMsg}
			<div class="error">{errorMsg}</div>
		{/if}

		<label>
			<span>Episode ID</span>
			<input type="text" readonly value={$currentEpisodeId} />
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

	.rec-btn {
		padding: 0.5rem 1rem;
		border: none;
		border-radius: 0;
		font-size: 0.875rem;
		font-weight: 600;
		cursor: pointer;
	}

	.rec-btn.start {
		background: #22c55e;
		color: #052e16;
	}

	.rec-btn.stop {
		background: #ef4444;
		color: #450a0a;
	}

	.recording-indicator {
		font-size: 0.875rem;
		font-weight: 600;
		color: #22c55e;
	}

	.recording-indicator.saving {
		color: #fbbf24;
	}

	.elapsed {
		font-size: 1.25rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.error {
		font-size: 0.75rem;
		color: #f87171;
		word-break: break-word;
	}
</style>
