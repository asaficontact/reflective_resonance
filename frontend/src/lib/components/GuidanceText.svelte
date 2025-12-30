<script lang="ts">
	import { Move, MousePointer, X } from 'lucide-svelte';

	interface Props {
		onclose?: () => void;
	}

	let { onclose }: Props = $props();
</script>

<div class="guidance" role="dialog" aria-labelledby="guidance-title">
	<button
		type="button"
		class="close-button"
		onclick={onclose}
		aria-label="Close guidance"
	>
		<X size={16} />
	</button>

	<h3 id="guidance-title" class="guidance-title">Get Started</h3>
	<div class="guidance-steps">
		<div class="step">
			<div class="step-icon">
				<Move size={20} />
			</div>
			<p class="step-text">Drag agents from the left panel to assign them to speaker slots</p>
		</div>
		<div class="step-divider">or</div>
		<div class="step">
			<div class="step-icon">
				<MousePointer size={20} />
			</div>
			<p class="step-text">Click a slot to select it, then click an agent to assign</p>
		</div>
	</div>
</div>

<style>
	.guidance {
		position: absolute;
		top: 1rem;
		right: 1rem;
		text-align: center;
		max-width: 340px;
		padding: 1.25rem;
		padding-top: 1rem;
		background: var(--rr-surface);
		border: 1px solid var(--rr-surface-elevated);
		border-radius: 1rem;
		box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
		z-index: var(--rr-z-overlay);
	}

	.close-button {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border: none;
		border-radius: 0.375rem;
		background: transparent;
		color: var(--rr-text-muted);
		cursor: pointer;
		transition: background var(--rr-transition-fast), color var(--rr-transition-fast);
	}

	.close-button:hover {
		background: var(--rr-surface-elevated);
		color: var(--rr-text-primary);
	}

	.guidance-title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--rr-text-primary);
		margin-bottom: 0.75rem;
	}

	.guidance-steps {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.step {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		text-align: left;
	}

	.step-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border-radius: 0.5rem;
		background: var(--rr-surface-elevated);
		color: var(--rr-accent-violet);
		flex-shrink: 0;
	}

	.step-text {
		font-size: 0.8125rem;
		color: var(--rr-text-secondary);
		line-height: 1.4;
	}

	.step-divider {
		font-size: 0.6875rem;
		color: var(--rr-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.1em;
	}
</style>
