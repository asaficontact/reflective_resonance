<script lang="ts">
	import { appStore } from '$lib/stores/app.svelte';
	import SpeakerSlotRing from './SpeakerSlotRing.svelte';
	import GuidanceText from './GuidanceText.svelte';
	import type { AgentId, SlotId } from '$lib/types';

	function handleDrop(slotId: SlotId, agentId: AgentId) {
		appStore.assignAgentToSlot(slotId, agentId);
	}

	const hasAssignedAgents = $derived(appStore.assignedSlots.length > 0);

	// Track if user has dismissed the guidance for this session
	let isDismissed = $state(false);

	function handleGuidanceClose() {
		isDismissed = true;
	}

	// Show guidance when no agents assigned AND not manually dismissed
	const showGuidance = $derived(!hasAssignedAgents && !isDismissed);
</script>

<section class="speaker-slots">
	<div class="slots-grid">
		{#each appStore.slots as slot (slot.id)}
			<SpeakerSlotRing {slot} ondrop={(agentId) => handleDrop(slot.id, agentId)} />
		{/each}
	</div>

	{#if showGuidance}
		<GuidanceText onclose={handleGuidanceClose} />
	{/if}
</section>

<style>
	.speaker-slots {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		flex: 1;
		padding: 2rem;
		position: relative;
	}

	.slots-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		grid-template-rows: repeat(2, 1fr);
		gap: 2rem;
		max-width: 600px;
	}

	/* Responsive adjustments */
	@media (max-width: 1200px) {
		.slots-grid {
			gap: 1.5rem;
		}
	}
</style>
