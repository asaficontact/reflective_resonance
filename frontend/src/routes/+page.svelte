<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { appStore } from '$lib/stores/app.svelte';
	import { createMultiStream } from '$lib/utils/mock-responses';
	import { createRealStream, type SlotStartData, type SlotDoneData, type SlotAudioData } from '$lib/utils/streaming';
	import { KEYBOARD_SHORTCUTS, API_CONFIG } from '$lib/config/constants';
	import type { SlotId, ErrorType, TurnIndex, MessageKind } from '$lib/types';

	import AgentPalette from '$lib/components/AgentPalette.svelte';
	import SpeakerSlots from '$lib/components/SpeakerSlots.svelte';
	import ResponsesPanel from '$lib/components/ResponsesPanel.svelte';
	import AudioInputDock from '$lib/components/AudioInputDock.svelte';
	import { Toaster, toast } from 'svelte-sonner';

	// Track active stream for cleanup
	let activeStream: { cancel: () => void } | null = null;

	// Message ID map for streaming updates (keyed by slotId-turnIndex-kind)
	let messageIds: Map<string, string> = new Map();

	// Generate message key for lookup
	function getMessageKey(slotId: SlotId, turnIndex: TurnIndex, kind: MessageKind): string {
		return `${slotId}-${turnIndex}-${kind}`;
	}

	// Handle sending a message to all assigned agents
	function handleSendMessage(content: string) {
		// Check if we can send (either via input field or direct content like audio transcript)
		const canSendDirect = content.trim().length > 0 &&
			appStore.assignedSlots.length > 0 &&
			!appStore.isSending &&
			appStore.isOnline;

		if (!canSendDirect) return;

		// Reset turn status for new workflow
		appStore.resetTurnStatus();

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

		// Clear message IDs from previous run
		messageIds.clear();

		// Set all slots to streaming
		slotsToStream.forEach(({ slotId }) => {
			appStore.setSlotStatus(slotId as SlotId, 'streaming');
		});

		// Legacy callbacks (for backwards compatibility with mock)
		const legacyCallbacks = {
			onToken: (slotId: number, token: string) => {
				// Only handle for Turn 1 (legacy mode)
				const key = getMessageKey(slotId as SlotId, 1, 'response');
				let messageId = messageIds.get(key);

				if (!messageId) {
					// Create message if not exists
					const slot = appStore.getSlot(slotId as SlotId);
					const message = appStore.addMessage({
						role: 'agent',
						content: '',
						slotId: slotId as SlotId,
						agentId: slot?.agentId,
						isStreaming: true,
						turnIndex: 1,
						kind: 'response'
					});
					messageId = message.id;
					messageIds.set(key, messageId);
				}

				appStore.appendToMessage(messageId, token);
			},
			onSlotComplete: (slotId: number) => {
				const key = getMessageKey(slotId as SlotId, 1, 'response');
				const messageId = messageIds.get(key);
				if (messageId) {
					appStore.updateMessage(messageId, { isStreaming: false });
				}
				appStore.setSlotStatus(slotId as SlotId, 'done');
				appStore.resetRetryCount(slotId as SlotId);
			},
			onSlotError: (slotId: number, error: ErrorType) => {
				appStore.setSlotStatus(slotId as SlotId, 'error', error);
				toast.error(`Slot ${slotId} error: ${getErrorMessage(error)}`);
			},
			onAllComplete: () => {
				appStore.setIsSending(false);
				appStore.clearAllSpeakingSlots();
				activeStream = null;
			}
		};

		// 3-Turn workflow callbacks
		const workflowCallbacks = {
			onSessionStart: (sessionId: string) => {
				appStore.setCurrentSession(sessionId);
			},
			onTurnStart: (turnIndex: TurnIndex, _sessionId: string) => {
				appStore.setTurnStatus(turnIndex, 'in_progress');
			},
			onTurnDone: (turnIndex: TurnIndex, _slotCount: number, _sessionId: string) => {
				appStore.setTurnStatus(turnIndex, 'done');
			},
			onSlotStart: (data: SlotStartData) => {
				// Mark slot as speaking (for ripple effect)
				console.log(`[Ripple] Slot ${data.slotId} started speaking - Turn ${data.turnIndex}`);
				appStore.setSlotSpeaking(data.slotId, true);
			},
			onSlotDone: (data: SlotDoneData) => {
				// Clear speaking state for this slot
				appStore.setSlotSpeaking(data.slotId, false);
				const key = getMessageKey(data.slotId, data.turnIndex, data.kind);

				// Create or update message for this turn
				let messageId = messageIds.get(key);
				if (messageId) {
					// Update existing message (include sessionId for Turn 1 messages created by onToken)
					appStore.updateMessage(messageId, {
						content: data.text,
						voiceProfile: data.voiceProfile,
						isStreaming: false,
						targetSlotId: data.targetSlotId,
						sessionId: data.sessionId,
						turnIndex: data.turnIndex,
						kind: data.kind
					});
				} else {
					// Create new message
					const message = appStore.addMessage({
						role: 'agent',
						content: data.text,
						slotId: data.slotId,
						agentId: data.agentId,
						isStreaming: false,
						sessionId: data.sessionId,
						turnIndex: data.turnIndex,
						kind: data.kind,
						voiceProfile: data.voiceProfile,
						targetSlotId: data.targetSlotId
					});
					messageIds.set(key, message.id);
				}

				// Mark slot as done after Turn 1
				if (data.turnIndex === 1) {
					appStore.setSlotStatus(data.slotId, 'done');
					appStore.resetRetryCount(data.slotId);
				}
			},
			onSlotAudio: (data: SlotAudioData) => {
				const key = getMessageKey(data.slotId, data.turnIndex, data.kind);
				const messageId = messageIds.get(key);
				if (messageId) {
					appStore.updateMessageAudioStatus(messageId, data.audioPath);
				}
			}
		};

		// Start streaming (mock or real based on config)
		if (API_CONFIG.useMock) {
			activeStream = createMultiStream({
				slots: slotsToStream,
				...legacyCallbacks
			});
		} else {
			activeStream = createRealStream({
				message: content,
				slots: slotsToStream,
				...legacyCallbacks,
				...workflowCallbacks
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
			case 'tts_error':
				return 'Text-to-speech error.';
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
		<AudioInputDock ontranscript={handleSendMessage} />
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
