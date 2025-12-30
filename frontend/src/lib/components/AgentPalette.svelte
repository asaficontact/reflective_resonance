<script lang="ts">
	import { AGENT_LIST } from '$lib/config/agents';
	import { appStore } from '$lib/stores/app.svelte';
	import AgentCard from './AgentCard.svelte';
	import { dndzone, SOURCES, TRIGGERS, type DndEvent } from 'svelte-dnd-action';
	import type { AgentId } from '$lib/types';

	// Create draggable items from agents
	let items = $state(
		AGENT_LIST.map((agent) => ({
			id: agent.id,
			agentId: agent.id as AgentId
		}))
	);

	function handleAgentClick(agentId: AgentId) {
		// If a slot is selected, assign this agent to it
		if (appStore.selectedSlotId !== null) {
			appStore.assignAgentToSlot(appStore.selectedSlotId, agentId);
			appStore.selectSlot(null);
		}
	}

	function handleDndConsider(e: CustomEvent<DndEvent<{ id: string; agentId: AgentId }>>) {
		// Keep items unchanged - we're only providing copies
		items = e.detail.items;
	}

	function handleDndFinalize(e: CustomEvent<DndEvent<{ id: string; agentId: AgentId }>>) {
		// Reset items after drag ends
		items = AGENT_LIST.map((agent) => ({
			id: agent.id,
			agentId: agent.id as AgentId
		}));
	}
</script>

<aside class="agent-palette">
	<h2 class="palette-title">Agents</h2>
	<p class="palette-hint">
		{#if appStore.selectedSlotId !== null}
			Click an agent to assign to slot {appStore.selectedSlotId}
		{:else}
			Drag to slots or click a slot first
		{/if}
	</p>

	<div
		class="agent-list"
		use:dndzone={{
			items,
			flipDurationMs: 200,
			dropTargetStyle: {},
			type: 'agent',
			dragDisabled: false,
			centreDraggedOnCursor: true
		}}
		onconsider={handleDndConsider}
		onfinalize={handleDndFinalize}
	>
		{#each items as item (item.id)}
			{@const agent = AGENT_LIST.find((a) => a.id === item.agentId)!}
			<div class="agent-item">
				<AgentCard {agent} onclick={() => handleAgentClick(agent.id)} />
			</div>
		{/each}
	</div>
</aside>

<style>
	.agent-palette {
		display: flex;
		flex-direction: column;
		width: 240px;
		min-width: 240px;
		height: 100%;
		padding: 1.5rem 1rem;
		background: var(--rr-surface);
		border-right: 1px solid var(--rr-surface-elevated);
	}

	.palette-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--rr-text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-bottom: 0.5rem;
	}

	.palette-hint {
		font-size: 0.75rem;
		color: var(--rr-text-muted);
		margin-bottom: 1rem;
		min-height: 2rem;
	}

	.agent-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		flex: 1;
		overflow-y: auto;
	}

	.agent-item {
		/* Ensure consistent sizing during drag */
	}

	/* Style for dragged item */
	:global(.agent-item[aria-grabbed='true']) {
		opacity: 0.5;
	}
</style>
