<script lang="ts">
    import { toolheadPose } from "$lib/state/robotState";
    import { currentTrajectory } from "$lib/state/trajectoryState";
    import { requestTrajectory } from "$lib/adapter/trajectory"
    import type { EulerPose } from "$lib/types";

    let currentPosition = $derived(
        $toolheadPose.position.map(n => n.toFixed(2))
    );

    let currentOrientation = $derived(
        $toolheadPose.orientation.map(n => n.toFixed(2))
    );

    let startPose = $state({ x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0 });
    let endPose = $state({ x: 0, y: 0, z: 0, rx: 0, ry: 0, rz: 0 });

    function recordStart() {
        startPose = {
            x: parseFloat(currentPosition[0]),
            y: parseFloat(currentPosition[1]),
            z: parseFloat(currentPosition[2]),
            rx: parseFloat(currentOrientation[0]),
            ry: parseFloat(currentOrientation[1]),
            rz: parseFloat(currentOrientation[2])
        };
    }

    function recordEnd() {
        endPose = {
            x: parseFloat(currentPosition[0]),
            y: parseFloat(currentPosition[1]),
            z: parseFloat(currentPosition[2]),
            rx: parseFloat(currentOrientation[0]),
            ry: parseFloat(currentOrientation[1]),
            rz: parseFloat(currentOrientation[2])
        };
    }

    async function generateSpline() {
        let start: EulerPose = {position: [startPose.x, startPose.y, startPose.z], orientation: [startPose.rx, startPose.ry, startPose.rz]}
        let end: EulerPose = {position: [endPose.x, endPose.y, endPose.z], orientation: [endPose.rx, endPose.ry, endPose.rz]}
        let trajectory: EulerPose[] = await requestTrajectory(start, end);
        $currentTrajectory = trajectory;
    }

</script>

<div class="panel">
    <section class="section">
        <h2>Toolhead Position</h2>
        <div class="pose-grid">
            <span class="label">X</span><span class="value">{currentPosition[0]}</span>
            <span class="label">Y</span><span class="value">{currentPosition[1]}</span>
            <span class="label">Z</span><span class="value">{currentPosition[2]}</span>
        </div>
        <h2>Toolhead Orientation</h2>
        <div class="pose-grid">
            <span class="label">X</span><span class="value">{currentOrientation[0]}</span>
            <span class="label">Y</span><span class="value">{currentOrientation[1]}</span>
            <span class="label">Z</span><span class="value">{currentOrientation[2]}</span>
        </div>
    </section>

    <section class="section spline-section">
        <h2>Test Spline Generation</h2>
        <div class="pose-columns">
            <div class="pose-card">
                <h3>Start Pose</h3>
                <button onclick={recordStart}>Record Start Pose</button>
                <div class="compact-pose">
                    <h4>Current Pose</h4>
                    <label>X <input type="number" bind:value={startPose.x} step="0.01" /></label>
                    <label>Y <input type="number" bind:value={startPose.y} step="0.01" /></label>
                    <label>Z <input type="number" bind:value={startPose.z} step="0.01" /></label>
                    <label>RX <input type="number" bind:value={startPose.rx} step="0.01" /></label>
                    <label>RY <input type="number" bind:value={startPose.ry} step="0.01" /></label>
                    <label>RZ <input type="number" bind:value={startPose.rz} step="0.01" /></label>
                </div>
            </div>

            <div class="pose-card">
                <h3>End Pose</h3>
                <button onclick={recordEnd}>Record End Pose</button>
                <div class="compact-pose">
                    <h4>Current Pose</h4>
                    <label>X <input type="number" bind:value={endPose.x} step="0.01" /></label>
                    <label>Y <input type="number" bind:value={endPose.y} step="0.01" /></label>
                    <label>Z <input type="number" bind:value={endPose.z} step="0.01" /></label>
                    <label>RX <input type="number" bind:value={endPose.rx} step="0.01" /></label>
                    <label>RY <input type="number" bind:value={endPose.ry} step="0.01" /></label>
                    <label>RZ <input type="number" bind:value={endPose.rz} step="0.01" /></label>
                </div>
            </div>
        </div>
        <button onclick={generateSpline}>Generate Spline</button>
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

    button {
        width: fit-content;
        padding: 0.25rem 0.5rem;
        border: 1px solid #475569;
        background: #1e293b;
        color: #e2e8f0;
        cursor: pointer;
    }

    button:hover {
        background: #334155;
    }

    .compact-pose {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.25rem 0.5rem;
    }

    .compact-pose h4 {
        grid-column: 1 / -1;
        margin: 0.25rem 0;
        font-size: 0.8rem;
        font-weight: 500;
    }

    .compact-pose label {
        display: flex;
        align-items: center;
        gap: 0.25rem;
        font-size: 0.75rem;
        color: #cbd5e1;
    }

    .compact-pose input {
        flex: 1;
        padding: 0.15rem 0.35rem;
        font-size: 0.8rem;
        height: 1.5rem;
        border: 1px solid #475569;
        border-radius: 0;
        background: #0f172a;
        color: #e2e8f0;
        width: 100%;
        box-sizing: border-box;
    }

    .compact-pose input:focus {
        outline: 2px solid #60a5fa;
        outline-offset: 1px;
    }
</style>