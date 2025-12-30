<script lang="ts">
	import type { Message, Slot } from '$lib/types';
	import { getAgent } from '$lib/config/agents';
	import { Loader2 } from 'lucide-svelte';

	interface Props {
		message: Message;
		slot: Slot;
	}

	let { message, slot }: Props = $props();

	const agent = $derived(slot.agentId ? getAgent(slot.agentId) : null);
</script>

{#if agent}
	<div class="response-card" style="--agent-color: {agent.color}">
		<div class="response-header">
			<div class="agent-badge">
				<span class="slot-number">{slot.id}</span>
				<span class="agent-name">{agent.name}</span>
			</div>
			{#if message.isStreaming}
				<Loader2 size={14} class="animate-spin" />
			{/if}
		</div>
		<div class="response-content">
			{message.content || '...'}
			{#if message.isStreaming}
				<span class="cursor">|</span>
			{/if}
		</div>
	</div>
{/if}

<style>
	.response-card {
		background: var(--rr-surface);
		border: 1px solid var(--rr-surface-elevated);
		border-left: 3px solid var(--agent-color);
		border-radius: 0.75rem;
		padding: 0.75rem 1rem;
		transition: border-color var(--rr-transition-fast);
	}

	.response-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.5rem;
	}

	.agent-badge {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.slot-number {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 1.25rem;
		height: 1.25rem;
		background: var(--agent-color);
		color: white;
		font-size: 0.625rem;
		font-weight: 700;
		border-radius: 50%;
	}

	.agent-name {
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--rr-text-secondary);
	}

	.response-content {
		font-size: 0.875rem;
		color: var(--rr-text-primary);
		line-height: 1.5;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.cursor {
		display: inline-block;
		animation: blink 1s step-end infinite;
		color: var(--agent-color);
	}

	@keyframes blink {
		50% {
			opacity: 0;
		}
	}

	:global(.animate-spin) {
		animation: spin 1s linear infinite;
		color: var(--agent-color);
	}

	@keyframes spin {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}
</style>
