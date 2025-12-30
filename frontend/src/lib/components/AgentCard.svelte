<script lang="ts">
	import type { Agent } from '$lib/types';
	import { appStore } from '$lib/stores/app.svelte';
	import {
		Sparkles,
		Brain,
		Zap,
		Lightbulb,
		MessageCircle,
		Star
	} from 'lucide-svelte';

	interface Props {
		agent: Agent;
		variant?: 'palette' | 'slot' | 'compact';
		onclick?: () => void;
		draggable?: boolean;
	}

	let { agent, variant = 'palette', onclick, draggable = true }: Props = $props();

	const usageCount = $derived(appStore.agentUsageCounts[agent.id] || 0);

	// Map icon names to components
	const iconMap = {
		sparkles: Sparkles,
		brain: Brain,
		zap: Zap,
		lightbulb: Lightbulb,
		'message-circle': MessageCircle,
		star: Star
	};

	const IconComponent = $derived(iconMap[agent.icon as keyof typeof iconMap] || Sparkles);
</script>

<button
	type="button"
	class="agent-card agent-card--{variant}"
	style="--agent-color: {agent.color}"
	onclick={onclick}
	{draggable}
	aria-label="Agent: {agent.name}"
>
	<div class="agent-card__icon">
		<IconComponent size={variant === 'compact' ? 16 : 20} />
	</div>
	<div class="agent-card__info">
		<span class="agent-card__name">{agent.name}</span>
		{#if variant === 'palette' && usageCount > 0}
			<span class="agent-card__usage">x{usageCount}</span>
		{/if}
	</div>
</button>

<style>
	.agent-card {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.75rem 1rem;
		background: var(--rr-surface);
		border: 1px solid transparent;
		border-radius: 0.75rem;
		cursor: grab;
		transition:
			background var(--rr-transition-fast),
			border-color var(--rr-transition-fast),
			box-shadow var(--rr-transition-fast);
		width: 100%;
		text-align: left;
	}

	.agent-card:hover {
		background: var(--rr-surface-elevated);
		border-color: var(--agent-color);
		box-shadow: 0 0 15px color-mix(in srgb, var(--agent-color) 30%, transparent);
	}

	.agent-card:active {
		cursor: grabbing;
	}

	.agent-card__icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		border-radius: 0.5rem;
		background: color-mix(in srgb, var(--agent-color) 15%, transparent);
		color: var(--agent-color);
	}

	.agent-card__info {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
		flex: 1;
		min-width: 0;
	}

	.agent-card__name {
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--rr-text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.agent-card__usage {
		font-size: 0.75rem;
		color: var(--rr-text-secondary);
	}

	/* Variant: slot (inside speaker ring) */
	.agent-card--slot {
		padding: 0.5rem;
		background: transparent;
		border: none;
		cursor: default;
		flex-direction: column;
		gap: 0.25rem;
		text-align: center;
	}

	.agent-card--slot:hover {
		background: transparent;
		border-color: transparent;
		box-shadow: none;
	}

	.agent-card--slot .agent-card__icon {
		width: 2.5rem;
		height: 2.5rem;
	}

	.agent-card--slot .agent-card__info {
		align-items: center;
	}

	.agent-card--slot .agent-card__name {
		font-size: 0.75rem;
	}

	/* Variant: compact */
	.agent-card--compact {
		padding: 0.5rem 0.75rem;
		gap: 0.5rem;
	}

	.agent-card--compact .agent-card__icon {
		width: 1.5rem;
		height: 1.5rem;
	}

	.agent-card--compact .agent-card__name {
		font-size: 0.75rem;
	}
</style>
