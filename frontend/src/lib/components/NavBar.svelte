<script lang="ts">
	type Status = 'checking' | 'ok' | 'down';
	let backendStatus = $state<Status>('checking');
    let robotStatus = $state<Status>('checking');

	async function checkBackendStatus() {
		try {
			const response = await fetch('/api/health');
			await response.json();
			backendStatus = response.ok ? 'ok' : 'down';
		} catch (err) {
			console.error('Backend unreachable:', err);
			backendStatus = 'down';
		}
	}

    async function checkRobotStatus() {
		try {
			const response = await fetch('/robot_api/health');
			await response.json();
			robotStatus = response.ok ? 'ok' : 'down';
		} catch (err) {
			console.error('Robot unreachable:', err);
			robotStatus = 'down';
		}
	}

	$effect(() => {
		checkBackendStatus();
        checkRobotStatus();

		const interval = setInterval(() => {checkBackendStatus(); checkRobotStatus();}, 5000);
		return () => clearInterval(interval);
	});
</script>

<nav class="nav-bar" aria-label="Primary">
	<a href="/">Collect</a>
	<a href="/label">Label</a>
	<a href="/test">Test API</a>

	<div class="status" title={`Backend Status`}>
        <span>Backend: </span>
		<span class="status-dot {backendStatus}"></span>
		<span class="status-label">{backendStatus}</span>
        <span>   </span>
        <span>Robot: </span>
		<span class="status-dot {robotStatus}"></span>
		<span class="status-label">{robotStatus}</span>
	</div>
</nav>

<style>
	.nav-bar {
		display: flex;
		align-items: center;
		gap: 1rem;
		min-height: 2.5rem;
		padding: 0 1rem;
		color: #e2e8f0;
	}

	.nav-bar a {
		color: inherit;
		text-decoration: none;
	}

	.nav-bar a:hover {
		text-decoration: underline;
	}

	.status {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-left: auto;
		font-size: 0.8rem;
		color: #94a3b8;
	}

	.status-dot {
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 50%;
		background: #64748b; /* default/checking = gray */
		flex-shrink: 0;
	}

	.status-dot.ok {
		background: #22c55e;
	}

	.status-dot.down {
		background: #ef4444;
	}

	.status-dot.checking {
		background: #94a3b8;
	}
</style>