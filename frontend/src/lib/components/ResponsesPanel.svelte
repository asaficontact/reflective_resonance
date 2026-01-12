<script lang="ts">
	import { appStore } from '$lib/stores/app.svelte';
	import ResponseCard from './ResponseCard.svelte';
	import { MessageSquare } from 'lucide-svelte';
	import type { TurnIndex } from '$lib/types';

	// Currently selected turn to display
	let selectedTurn = $state<TurnIndex>(1);

	// Get turn status for showing which turns are available
	const turnStatusMap = $derived(appStore.turnStatus);
	const currentTurn = $derived(appStore.currentTurnIndex);

	// Check if a turn has any data
	function turnHasData(turnIndex: TurnIndex): boolean {
		// Turn 4 (summary) is special - check dedicated summary state
		if (turnIndex === 4) {
			return appStore.summaryMessage !== null;
		}

		return appStore.assignedSlots.some((slot) => {
			const turns = appStore.getTurnsForSlot(slot.id);
			if (turnIndex === 1) return !!turns.turn1;
			if (turnIndex === 2) return !!turns.turn2;
			if (turnIndex === 3) return !!turns.turn3;
			return false;
		});
	}

	// Get responses for the selected turn
	const responsesForSelectedTurn = $derived.by(() => {
		return appStore.assignedSlots
			.map((slot) => {
				const turns = appStore.getTurnsForSlot(slot.id);
				const isStreaming = slot.status === 'streaming' && currentTurn === selectedTurn;

				let message = null;
				if (selectedTurn === 1) message = turns.turn1;
				else if (selectedTurn === 2) message = turns.turn2;
				else if (selectedTurn === 3) message = turns.turn3;

				// For T2, we also need the target info
				// For T3, we need the received comments count
				const receivedComments = turns.receivedComments || [];

				return {
					slot,
					message,
					isStreaming,
					receivedComments
				};
			})
			.filter((item) => item.message || item.isStreaming);
	});

	// For Turn 4 (summary), check summary message; for others, check slot responses
	const hasResponses = $derived(
		selectedTurn === 4
			? appStore.summaryMessage !== null
			: responsesForSelectedTurn.length > 0
	);

	// Auto-advance to latest turn with data
	$effect(() => {
		if (turnHasData(4)) selectedTurn = 4;
		else if (turnHasData(3)) selectedTurn = 3;
		else if (turnHasData(2)) selectedTurn = 2;
		else if (turnHasData(1)) selectedTurn = 1;
	});

	// Turn labels
	const turnLabels: Record<TurnIndex, string> = {
		1: 'Response',
		2: 'Comment',
		3: 'Reply',
		4: 'Summary'
	};
</script>

<aside class="responses-panel">
	<div class="panel-header">
		<h2 class="panel-title">Responses</h2>
	</div>

	<!-- Turn Tabs -->
	<div class="turn-tabs">
		{#each [1, 2, 3, 4] as turn (turn)}
			{@const hasData = turnHasData(turn as TurnIndex)}
			{@const isActive = turnStatusMap[turn as TurnIndex] === 'in_progress'}
			{@const isDone = turnStatusMap[turn as TurnIndex] === 'done'}
			{@const isSelected = selectedTurn === turn}
			<button
				class="turn-tab"
				class:selected={isSelected}
				class:has-data={hasData}
				class:active={isActive}
				class:done={isDone}
				onclick={() => (selectedTurn = turn as TurnIndex)}
				disabled={!hasData && !isActive}
			>
				<span class="turn-number">T{turn}</span>
				<span class="turn-name">{turnLabels[turn as TurnIndex]}</span>
				{#if isActive}
					<span class="status-dot"></span>
				{/if}
			</button>
		{/each}
	</div>

	{#if hasResponses}
		{#if selectedTurn === 4}
			<!-- Turn 4: Summary (single message, not per-slot) -->
			{@const summary = appStore.summaryMessage}
			{#if summary}
				<div class="summary-display">
					<div class="summary-card">
						<div class="summary-header">
							<span class="summary-label">Session Summary</span>
							{#if summary.voiceProfile}
								<span class="summary-voice">{summary.voiceProfile}</span>
							{/if}
						</div>
						<p class="summary-text">{summary.content}</p>
						{#if summary.audioReady}
							<div class="summary-audio-badge">Audio Ready</div>
						{/if}
					</div>
				</div>
			{/if}
		{:else}
			<div class="responses-list">
				{#each responsesForSelectedTurn as { slot, message, isStreaming, receivedComments } (slot.id)}
					<ResponseCard
						{slot}
						{message}
						{isStreaming}
						turnIndex={selectedTurn}
						{receivedComments}
					/>
				{/each}
			</div>
		{/if}
	{:else}
		<div class="empty-state">
			<MessageSquare size={32} strokeWidth={1.5} />
			{#if currentTurn && turnStatusMap[currentTurn] === 'in_progress'}
				<p>Processing Turn {currentTurn}...</p>
			{:else}
				<p>Agent responses will appear here</p>
			{/if}
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

	.panel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: 0.75rem;
		flex-shrink: 0;
	}

	.panel-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--rr-text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	/* Turn Tabs */
	.turn-tabs {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1rem;
		flex-shrink: 0;
	}

	.turn-tab {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.125rem;
		padding: 0.5rem 0.25rem;
		background: var(--rr-surface-elevated);
		border: 1px solid transparent;
		border-radius: 0.5rem;
		cursor: pointer;
		transition: all 0.15s ease;
		position: relative;
		font-family: inherit;
	}

	.turn-tab:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}

	.turn-tab:not(:disabled):hover {
		background: rgba(255, 255, 255, 0.05);
	}

	.turn-tab.selected {
		background: rgba(59, 130, 246, 0.15);
		border-color: rgba(59, 130, 246, 0.5);
	}

	.turn-tab.has-data:not(.selected) {
		background: rgba(255, 255, 255, 0.03);
	}

	.turn-number {
		font-size: 0.6875rem;
		font-weight: 700;
		color: var(--rr-text-muted);
		text-transform: uppercase;
	}

	.turn-tab.selected .turn-number {
		color: rgb(147, 197, 253);
	}

	.turn-tab.has-data .turn-number {
		color: var(--rr-text-secondary);
	}

	.turn-name {
		font-size: 0.625rem;
		color: var(--rr-text-muted);
	}

	.turn-tab.selected .turn-name {
		color: rgb(147, 197, 253);
	}

	.status-dot {
		position: absolute;
		top: 0.25rem;
		right: 0.25rem;
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: rgb(34, 197, 94);
		animation: pulse 1.5s ease-in-out infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.5;
		}
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

	/* Summary Display (Turn 4) */
	.summary-display {
		flex: 1;
		padding: 0.5rem 0;
		overflow-y: auto;
	}

	.summary-card {
		background: linear-gradient(135deg, rgba(147, 51, 234, 0.15) 0%, rgba(79, 70, 229, 0.15) 100%);
		border: 1px solid rgba(147, 51, 234, 0.3);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	.summary-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.75rem;
	}

	.summary-label {
		font-size: 0.75rem;
		font-weight: 600;
		color: rgb(192, 132, 252);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.summary-voice {
		font-size: 0.625rem;
		color: var(--rr-text-muted);
		background: rgba(255, 255, 255, 0.05);
		padding: 0.125rem 0.5rem;
		border-radius: 0.25rem;
	}

	.summary-text {
		font-size: 0.875rem;
		line-height: 1.6;
		color: var(--rr-text);
		margin: 0;
	}

	.summary-audio-badge {
		margin-top: 0.75rem;
		font-size: 0.625rem;
		color: rgb(134, 239, 172);
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.summary-audio-badge::before {
		content: '●';
		font-size: 0.5rem;
	}

	/* Responsive */
	@media (max-width: 1200px) {
		.responses-panel {
			width: 280px;
			min-width: 280px;
		}
	}
</style>
