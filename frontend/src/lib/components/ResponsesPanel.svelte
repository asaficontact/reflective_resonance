<script lang="ts">
	import { appStore } from '$lib/stores/app.svelte';
	import ResponseCard from './ResponseCard.svelte';
	import { MessageSquare } from 'lucide-svelte';

	// Get the latest responses for each assigned slot
	const latestResponses = $derived.by(() => {
		return appStore.assignedSlots
			.map((slot) => {
				const latestMessage = appStore.getLatestMessageForSlot(slot.id);
				if (latestMessage && latestMessage.role === 'agent') {
					return { slot, message: latestMessage };
				}
				return null;
			})
			.filter((item): item is NonNullable<typeof item> => item !== null);
	});

	const hasResponses = $derived(latestResponses.length > 0);
</script>

<aside class="responses-panel">
	<h2 class="panel-title">Responses</h2>

	{#if hasResponses}
		<div class="responses-list">
			{#each latestResponses as { slot, message } (message.id)}
				<ResponseCard {message} {slot} />
			{/each}
		</div>
	{:else}
		<div class="empty-state">
			<MessageSquare size={32} strokeWidth={1.5} />
			<p>Agent responses will appear here</p>
		</div>
	{/if}
</aside>

<style>
	.responses-panel {
		display: flex;
		flex-direction: column;
		width: 320px;
		min-width: 320px;
		height: 100%;
		padding: 1.5rem 1rem;
		background: var(--rr-surface);
		border-left: 1px solid var(--rr-surface-elevated);
		overflow: hidden;
	}

	.panel-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--rr-text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-bottom: 1rem;
		flex-shrink: 0;
	}

	.responses-list {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		flex: 1;
		overflow-y: auto;
		padding-bottom: 100px; /* Space for chat dock */
	}

	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		flex: 1;
		gap: 1rem;
		color: var(--rr-text-muted);
		text-align: center;
		padding: 2rem;
	}

	.empty-state p {
		font-size: 0.875rem;
		max-width: 200px;
	}

	/* Responsive */
	@media (max-width: 1200px) {
		.responses-panel {
			width: 280px;
			min-width: 280px;
		}
	}
</style>
