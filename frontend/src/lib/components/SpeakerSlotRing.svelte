<script lang="ts">
	import type { Slot, AgentId } from '$lib/types';
	import { appStore } from '$lib/stores/app.svelte';
	import { getAgent } from '$lib/config/agents';
	import AgentCard from './AgentCard.svelte';
	import { X, RotateCcw, Loader2 } from 'lucide-svelte';
	import { dndzone, type DndEvent } from 'svelte-dnd-action';

	interface Props {
		slot: Slot;
		ondrop?: (agentId: AgentId) => void;
	}

	let { slot, ondrop }: Props = $props();

	const isSelected = $derived(appStore.selectedSlotId === slot.id);
	const agent = $derived(slot.agentId ? getAgent(slot.agentId) : null);
	let isHovering = $state(false);

	// DnD state - must use $state to allow svelte-dnd-action to update items
	let dndItems = $state<{ id: string; agentId: AgentId }[]>([]);
	let isDragging = $state(false);

	// Sync dndItems with slot state when not actively dragging
	$effect(() => {
		if (!isDragging) {
			dndItems = slot.agentId
				? [{ id: `slot-${slot.id}`, agentId: slot.agentId }]
				: [];
		}
	});

	function handleClick() {
		if (slot.agentId) {
			// If slot has agent, select it
			appStore.selectSlot(slot.id);
		} else {
			// If empty, toggle selection
			appStore.selectSlot(isSelected ? null : slot.id);
		}
	}

	function handleClear(e: MouseEvent) {
		e.stopPropagation();
		appStore.clearSlot(slot.id);
	}

	function handleRetry(e: MouseEvent) {
		e.stopPropagation();
		// Will be handled by parent for retry logic
		appStore.setSlotStatus(slot.id, 'streaming');
		appStore.incrementRetryCount(slot.id);
	}

	function handleDndConsider(e: CustomEvent<DndEvent<{ id: string; agentId: AgentId }>>) {
		// Mark as dragging and accept the items from the library
		isDragging = true;
		dndItems = e.detail.items;
		isHovering = e.detail.items.length > 0 && !slot.agentId;
	}

	function handleDndFinalize(e: CustomEvent<DndEvent<{ id: string; agentId: AgentId }>>) {
		const items = e.detail.items;

		// Process the drop - if we have a new item, call ondrop
		if (items.length > 0 && items[0].agentId) {
			ondrop?.(items[0].agentId);
		}

		// Reset drag state - effect will sync dndItems after ondrop updates slot
		isDragging = false;
		isHovering = false;
	}

	// Compute ring classes
	const ringClasses = $derived.by(() => {
		const classes = ['slot-ring'];
		if (!slot.agentId) classes.push('slot-ring--empty');
		if (isHovering) classes.push('slot-ring--hover');
		if (isSelected) classes.push('slot-ring--selected');
		if (slot.agentId && slot.status === 'idle') classes.push('slot-ring--assigned');
		if (slot.status === 'streaming') classes.push('slot-ring--streaming');
		if (slot.status === 'error') classes.push('slot-ring--error');
		return classes.join(' ');
	});

	const ringStyle = $derived(
		agent ? `--agent-color: ${agent.color}; border-color: ${agent.color};` : ''
	);
</script>

<div
	class="speaker-slot"
	role="button"
	tabindex="0"
	aria-label="Speaker slot {slot.id}{agent ? `: ${agent.name}` : ' (empty)'}"
	onclick={handleClick}
	onkeydown={(e) => e.key === 'Enter' && handleClick()}
>
	<span class="slot-number">{slot.id}</span>

	<div
		class={ringClasses}
		style={ringStyle}
		use:dndzone={{
			items: dndItems,
			flipDurationMs: 200,
			dropTargetStyle: {},
			dropTargetClasses: ['slot-ring--hover'],
			type: 'agent'
		}}
		onconsider={handleDndConsider}
		onfinalize={handleDndFinalize}
	>
		{#if agent}
			<div class="slot-content">
				<AgentCard {agent} variant="slot" />

				{#if slot.status === 'streaming'}
					<div class="slot-status">
						<Loader2 size={16} class="animate-spin" />
					</div>
				{:else if slot.status === 'error'}
					<button
						type="button"
						class="slot-action slot-action--retry"
						onclick={handleRetry}
						aria-label="Retry"
					>
						<RotateCcw size={14} />
					</button>
				{:else}
					<button
						type="button"
						class="slot-action slot-action--clear"
						onclick={handleClear}
						aria-label="Clear slot"
					>
						<X size={14} />
					</button>
				{/if}
			</div>
		{:else}
			<div class="slot-empty">
				<span>Drop agent</span>
			</div>
		{/if}
	</div>
</div>

<style>
	.speaker-slot {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
	}

	.slot-number {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--rr-text-muted);
		font-family: monospace;
	}

	.slot-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		width: 100%;
		height: 100%;
		position: relative;
	}

	.slot-empty {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 100%;
		height: 100%;
		color: var(--rr-text-muted);
		font-size: 0.75rem;
	}

	.slot-status {
		position: absolute;
		bottom: 0.5rem;
		color: var(--rr-accent-blue);
	}

	.slot-action {
		position: absolute;
		top: 0.25rem;
		right: 0.25rem;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.5rem;
		height: 1.5rem;
		border-radius: 50%;
		border: none;
		cursor: pointer;
		opacity: 0;
		transition: opacity var(--rr-transition-fast);
	}

	.speaker-slot:hover .slot-action {
		opacity: 1;
	}

	.slot-action--clear {
		background: rgba(239, 68, 68, 0.2);
		color: #ef4444;
	}

	.slot-action--clear:hover {
		background: rgba(239, 68, 68, 0.4);
	}

	.slot-action--retry {
		background: rgba(14, 165, 233, 0.2);
		color: var(--rr-accent-blue);
		opacity: 1;
	}

	.slot-action--retry:hover {
		background: rgba(14, 165, 233, 0.4);
	}

	/* Animation for spinning loader */
	:global(.animate-spin) {
		animation: spin 1s linear infinite;
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
