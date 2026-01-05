<script lang="ts">
	import type { Slot, Message, TurnIndex } from '$lib/types';
	import { getAgent } from '$lib/config/agents';
	import { Loader2, ArrowRight, Volume2 } from 'lucide-svelte';

	interface Props {
		slot: Slot;
		message: Message | null;
		isStreaming?: boolean;
		turnIndex: TurnIndex;
		receivedComments?: Message[];
	}

	let { slot, message, isStreaming = false, turnIndex, receivedComments = [] }: Props = $props();

	const agent = $derived(slot.agentId ? getAgent(slot.agentId) : null);

	// Get target agent name for Turn 2 display
	function getTargetAgent(targetSlotId: number | undefined) {
		if (!targetSlotId) return null;
		return `Speaker ${targetSlotId}`;
	}

	// Count received comments for Turn 3
	const receivedCount = $derived(receivedComments?.length || 0);
</script>

{#if agent}
	<div class="response-card" style="--agent-color: {agent.color}">
		<div class="response-header">
			<div class="agent-badge">
				<span class="slot-number">{slot.id}</span>
				<span class="agent-name">{agent.name}</span>
			</div>
			<div class="header-indicators">
				{#if message?.audioReady}
					<Volume2 size={14} class="audio-icon" />
				{/if}
				{#if isStreaming}
					<Loader2 size={14} class="animate-spin" />
				{/if}
			</div>
		</div>

		{#if message}
			<div class="response-content">
				<!-- Turn 2: Show target indicator -->
				{#if turnIndex === 2 && message.targetSlotId}
					<div class="target-indicator">
						<ArrowRight size={12} />
						<span>{getTargetAgent(message.targetSlotId)}</span>
					</div>
				{/if}

				<!-- Turn 3: Show received comments count -->
				{#if turnIndex === 3 && receivedCount > 0}
					<div class="received-indicator">
						Replying to {receivedCount} comment{receivedCount > 1 ? 's' : ''}
					</div>
				{/if}

				<p class="content-text">{message.content}</p>

				{#if message.voiceProfile}
					<div class="voice-badge">
						{message.voiceProfile.replace(/_/g, ' ')}
					</div>
				{/if}
			</div>
		{:else if isStreaming}
			<div class="response-content">
				<p class="content-text loading">Generating response...</p>
			</div>
		{:else}
			<div class="response-content">
				<p class="content-text empty">No response for this turn</p>
			</div>
		{/if}
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

	.header-indicators {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.audio-icon {
		color: rgb(34, 197, 94);
	}

	.response-content {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.target-indicator {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		font-size: 0.6875rem;
		color: rgb(168, 85, 247);
		font-weight: 500;
	}

	.received-indicator {
		font-size: 0.6875rem;
		color: rgb(34, 197, 94);
		font-weight: 500;
	}

	.content-text {
		font-size: 0.875rem;
		color: var(--rr-text-primary);
		line-height: 1.5;
		white-space: pre-wrap;
		word-break: break-word;
		margin: 0;
	}

	.content-text.loading {
		color: var(--rr-text-muted);
		font-style: italic;
	}

	.content-text.empty {
		color: var(--rr-text-muted);
		font-style: italic;
		font-size: 0.75rem;
	}

	.voice-badge {
		display: inline-flex;
		align-self: flex-start;
		font-size: 0.625rem;
		padding: 0.125rem 0.5rem;
		background: rgba(255, 255, 255, 0.05);
		border-radius: 0.25rem;
		color: var(--rr-text-muted);
		text-transform: capitalize;
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
