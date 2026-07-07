<script lang="ts">
    import { toolheadPose } from "$lib/state/robotState";

    let position = $derived(
        $toolheadPose.position.map(n => n.toFixed(2))
    );

    let orientation = $derived(
        $toolheadPose.orientation.map(n => n.toFixed(2))
    );
</script>

<div class="panel">
    <section class="section">
        <h2>Toolhead Position</h2>
        <div class="pose-grid">
            <span class="label">X</span><span class="value">{position[0]}</span>
            <span class="label">Y</span><span class="value">{position[1]}</span>
            <span class="label">Z</span><span class="value">{position[2]}</span>
        </div>
        <h2>Toolhead Orientation</h2>
        <div class="pose-grid">
            <span class="label">X</span><span class="value">{orientation[0]}</span>
            <span class="label">Y</span><span class="value">{orientation[1]}</span>
            <span class="label">Z</span><span class="value">{orientation[2]}</span>
        </div>
    </section>

    <section class="section spline-section">
        <h2>Test Spline Generation</h2>

        <div class="pose-columns">
            <div class="pose-card">
                <h3>Start Pose</h3>
                <button>Record Start Pose</button>

                <div class="compact-pose">
                    <h4>Current Pose</h4>

                    <label>
                        X
                        <input value="0.00" />
                    </label>
                    <label>
                        Y
                        <input value="0.00" />
                    </label>
                    <label>
                        Z
                        <input value="0.00" />
                    </label>
                    <label>
                        RX
                        <input value="0.00" />
                    </label>
                    <label>
                        RY
                        <input value="0.00" />
                    </label>
                    <label>
                        RZ
                        <input value="0.00" />
                    </label>
                </div>
            </div>

            <div class="pose-card">
                <h3>End Pose</h3>
                <button>Record End Pose</button>

                <div class="compact-pose">
                    <h4>Current Pose</h4>

                    <label>
                        X
                        <input value="0.00" />
                    </label>
                    <label>
                        Y
                        <input value="0.00" />
                    </label>
                    <label>
                        Z
                        <input value="0.00" />
                    </label>
                    <label>
                        RX
                        <input value="0.00" />
                    </label>
                    <label>
                        RY
                        <input value="0.00" />
                    </label>
                    <label>RZ<input value="0.00" /></label>
                </div>
            </div>
        </div>
    </section>

    <section class="section">
        <h2>Status</h2>
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

	input:focus {
		outline: 2px solid #60a5fa;
		outline-offset: 1px;
	}
    .pose-grid {
        display: grid;
        grid-template-columns: auto auto;
        gap: 0.5rem 1rem;
        align-items: center;
    }

    .label {
        color: #cbd5e1;
    }

    .value {
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-variant-numeric: tabular-nums;
        display: inline-block;
        width: 8ch;
        text-align: right;
    }

    .spline-section {
        gap: 0.5rem;
    }

    .pose-columns {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.75rem;
    }

    .pose-card {
        display: grid;
        gap: 0.5rem;
        padding: 0.5rem;
        border: 1px solid #334155;
        background: #0f172a;
    }

    .pose-card h3 {
        margin: 0;
        font-size: 0.9rem;
        font-weight: 600;
    }

    .pose-card button {
        width: fit-content;
        padding: 0.25rem 0.5rem;
        border: 1px solid #475569;
        background: #1e293b;
        color: #e2e8f0;
        cursor: pointer;
    }

    .pose-card button:hover {
        background: #334155;
    }

    .compact-pose {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 0.25rem 0.5rem;
        align-items: center;
    }

    .compact-pose h4 {
        grid-column: 1 / -1;
        margin: 0.25rem 0;
        font-size: 0.8rem;
        font-weight: 500;
    }

    .compact-pose label {
        display: contents;
        font-size: 0.75rem;
        color: #cbd5e1;
    }

    .compact-pose input {
        padding: 0.15rem 0.35rem;
        font-size: 0.8rem;
        height: 1.5rem;
    }
</style>