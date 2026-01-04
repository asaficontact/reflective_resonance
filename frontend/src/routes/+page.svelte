<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { appStore } from '$lib/stores/app.svelte';
	import { createMultiStream } from '$lib/utils/mock-responses';
	import { createRealStream } from '$lib/utils/streaming';
	import { KEYBOARD_SHORTCUTS, API_CONFIG } from '$lib/config/constants';
	import type { SlotId, ErrorType } from '$lib/types';

	import AgentPalette from '$lib/components/AgentPalette.svelte';
	import SpeakerSlots from '$lib/components/SpeakerSlots.svelte';
	import ResponsesPanel from '$lib/components/ResponsesPanel.svelte';
	import ChatDock from '$lib/components/ChatDock.svelte';
	import { Toaster, toast } from 'svelte-sonner';

	// Track active stream for cleanup
	let activeStream: { cancel: () => void } | null = null;

	// Message ID map for streaming updates
	let messageIds: Map<SlotId, string> = new Map();

	// Handle sending a message to all assigned agents
	function handleSendMessage(content: string) {
		if (!appStore.canSend) return;

		// Add user message
		appStore.addMessage({
			role: 'user',
			content
		});

		// Set sending state
		appStore.setIsSending(true);

		// Prepare slots for streaming
		const slotsToStream = appStore.assignedSlots.map((slot) => ({
			slotId: slot.id,
			agentId: slot.agentId!
		}));

		// Initialize empty messages for each slot
		messageIds.clear();
		slotsToStream.forEach(({ slotId, agentId }) => {
			const message = appStore.addMessage({
				role: 'agent',
				content: '',
				slotId: slotId as SlotId,
				agentId,
				isStreaming: true
			});
			messageIds.set(slotId as SlotId, message.id);
			appStore.setSlotStatus(slotId as SlotId, 'streaming');
		});

		// Streaming callbacks (shared by mock and real)
		const streamCallbacks = {
			onToken: (slotId: number, token: string) => {
				const messageId = messageIds.get(slotId as SlotId);
				if (messageId) {
					appStore.appendToMessage(messageId, token);
				}
			},
			onSlotComplete: (slotId: number) => {
				const messageId = messageIds.get(slotId as SlotId);
				if (messageId) {
					appStore.updateMessage(messageId, { isStreaming: false });
				}
				appStore.setSlotStatus(slotId as SlotId, 'done');
				appStore.resetRetryCount(slotId as SlotId);
			},
			onSlotError: (slotId: number, error: ErrorType) => {
				const messageId = messageIds.get(slotId as SlotId);
				if (messageId) {
					appStore.updateMessage(messageId, {
						isStreaming: false,
						content: `Error: ${getErrorMessage(error)}`
					});
				}
				appStore.setSlotStatus(slotId as SlotId, 'error', error);
				toast.error(`Slot ${slotId} error: ${getErrorMessage(error)}`);
			},
			onAllComplete: () => {
				appStore.setIsSending(false);
				activeStream = null;
			}
		};

		// Start streaming (mock or real based on config)
		if (API_CONFIG.useMock) {
			activeStream = createMultiStream({
				slots: slotsToStream,
				...streamCallbacks
			});
		} else {
			activeStream = createRealStream({
				message: content,
				slots: slotsToStream,
				...streamCallbacks
			});
		}
	}

	// Get human-readable error message
	function getErrorMessage(error: ErrorType): string {
		switch (error) {
			case 'network':
				return 'Network error. Check your connection.';
			case 'timeout':
				return 'Request timed out. Please try again.';
			case 'rate_limit':
				return 'Rate limit exceeded. Please wait.';
			case 'server_error':
				return 'Server error. Please try again later.';
			default:
				return 'An unexpected error occurred.';
		}
	}

	// Handle keyboard shortcuts
	function handleKeydown(e: KeyboardEvent) {
		// Don't capture when typing in input
		if (
			e.target instanceof HTMLInputElement ||
			e.target instanceof HTMLTextAreaElement
		) {
			return;
		}

		// Slot selection (1-6)
		if (KEYBOARD_SHORTCUTS.selectSlot.includes(e.key)) {
			const slotId = parseInt(e.key) as SlotId;
			appStore.selectSlot(appStore.selectedSlotId === slotId ? null : slotId);
			e.preventDefault();
		}

		// Clear selection (Escape)
		if (e.key === KEYBOARD_SHORTCUTS.clearSelection) {
			appStore.selectSlot(null);
			e.preventDefault();
		}
	}

	// Online/offline detection
	function handleOnline() {
		appStore.setIsOnline(true);
		toast.success('Connection restored');
	}

	function handleOffline() {
		appStore.setIsOnline(false);
		toast.error('You are offline');

		// Cancel active streams
		if (activeStream) {
			activeStream.cancel();
			activeStream = null;
			appStore.setIsSending(false);
		}
	}

	// Setup event listeners
	onMount(() => {
		if (!browser) return;

		window.addEventListener('keydown', handleKeydown);
		window.addEventListener('online', handleOnline);
		window.addEventListener('offline', handleOffline);

		return () => {
			window.removeEventListener('keydown', handleKeydown);
			window.removeEventListener('online', handleOnline);
			window.removeEventListener('offline', handleOffline);

			// Cleanup active stream
			if (activeStream) {
				activeStream.cancel();
			}
		};
	});
</script>

<svelte:head>
	<title>Reflective Resonance</title>
	<meta name="description" content="Interactive AI art installation control panel" />
</svelte:head>

<Toaster position="top-right" richColors closeButton />

<div class="app-layout">
	<AgentPalette />

	<main class="main-content">
		<SpeakerSlots />
		<ChatDock onsubmit={handleSendMessage} />
	</main>

	<ResponsesPanel />
</div>

<style>
	.app-layout {
		display: flex;
		height: 100vh;
		width: 100%;
		overflow: hidden;
		background: var(--rr-bg);
	}

	.main-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		position: relative;
		overflow: hidden;
	}
</style>
