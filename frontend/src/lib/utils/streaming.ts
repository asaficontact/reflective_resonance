/**
 * Real SSE streaming client for backend API.
 * Replaces mock streaming with actual LLM responses.
 */

import type { AgentId, ErrorType } from '$lib/types';
import { API_CONFIG } from '$lib/config/constants';

// SSE event data types (matching backend models)
interface SlotStartEvent {
	slotId: number;
	agentId: string;
}

interface SlotTokenEvent {
	slotId: number;
	content: string;
}

interface SlotDoneEvent {
	slotId: number;
	agentId: string;
	fullContent: string;
}

interface SlotErrorEvent {
	slotId: number;
	agentId: string;
	error: {
		type: ErrorType;
		message: string;
	};
}

interface DoneEvent {
	completedSlots: number;
}

// Multi-stream options (same interface as mock-responses.ts)
export interface MultiStreamOptions {
	message: string;
	slots: Array<{ slotId: number; agentId: AgentId }>;
	onToken: (slotId: number, token: string) => void;
	onSlotComplete: (slotId: number) => void;
	onSlotError: (slotId: number, error: ErrorType) => void;
	onAllComplete: () => void;
}

/**
 * Create a real SSE stream to the backend API.
 * Broadcasts a message to all slots and streams responses.
 */
export function createRealStream(options: MultiStreamOptions): { cancel: () => void } {
	const { message, slots, onToken, onSlotComplete, onSlotError, onAllComplete } = options;

	const abortController = new AbortController();
	let cancelled = false;

	// Start the streaming request
	(async () => {
		try {
			const response = await fetch(`${API_CONFIG.baseUrl}/v1/chat`, {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Accept: 'text/event-stream'
				},
				body: JSON.stringify({
					message,
					slots: slots.map((s) => ({
						slotId: s.slotId,
						agentId: s.agentId
					}))
				}),
				signal: abortController.signal
			});

			if (!response.ok) {
				throw new Error(`HTTP ${response.status}: ${response.statusText}`);
			}

			if (!response.body) {
				throw new Error('Response body is null');
			}

			const reader = response.body.getReader();
			const decoder = new TextDecoder();
			let buffer = '';

			while (!cancelled) {
				const { done, value } = await reader.read();

				if (done) {
					break;
				}

				buffer += decoder.decode(value, { stream: true });

				// Process complete SSE messages
				const lines = buffer.split('\n');
				buffer = lines.pop() || ''; // Keep incomplete line in buffer

				let currentEvent = '';

				for (const line of lines) {
					if (line.startsWith('event: ')) {
						currentEvent = line.slice(7).trim();
					} else if (line.startsWith('data: ')) {
						const dataStr = line.slice(6);

						try {
							const data = JSON.parse(dataStr);
							handleSSEEvent(currentEvent, data, {
								onToken,
								onSlotComplete,
								onSlotError,
								onAllComplete
							});
						} catch (e) {
							console.error('Failed to parse SSE data:', dataStr, e);
						}

						currentEvent = '';
					}
				}
			}

			// If we finished normally without cancellation, ensure onAllComplete is called
			if (!cancelled) {
				onAllComplete();
			}
		} catch (error) {
			if (cancelled || (error instanceof Error && error.name === 'AbortError')) {
				// Cancelled by user, ignore
				return;
			}

			console.error('SSE stream error:', error);

			// Emit error for all slots
			for (const slot of slots) {
				onSlotError(slot.slotId, 'network');
			}
			onAllComplete();
		}
	})();

	return {
		cancel: () => {
			cancelled = true;
			abortController.abort();
		}
	};
}

/**
 * Handle individual SSE events from the backend.
 */
function handleSSEEvent(
	eventType: string,
	data: unknown,
	callbacks: {
		onToken: (slotId: number, token: string) => void;
		onSlotComplete: (slotId: number) => void;
		onSlotError: (slotId: number, error: ErrorType) => void;
		onAllComplete: () => void;
	}
) {
	switch (eventType) {
		case 'slot.start': {
			// Slot started streaming - no action needed, UI already shows streaming state
			const event = data as SlotStartEvent;
			console.debug(`Slot ${event.slotId} (${event.agentId}) started streaming`);
			break;
		}

		case 'slot.token': {
			const event = data as SlotTokenEvent;
			callbacks.onToken(event.slotId, event.content);
			break;
		}

		case 'slot.done': {
			const event = data as SlotDoneEvent;
			callbacks.onSlotComplete(event.slotId);
			console.debug(`Slot ${event.slotId} completed: ${event.fullContent.length} chars`);
			break;
		}

		case 'slot.error': {
			const event = data as SlotErrorEvent;
			callbacks.onSlotError(event.slotId, event.error.type);
			console.error(`Slot ${event.slotId} error:`, event.error);
			break;
		}

		case 'done': {
			const event = data as DoneEvent;
			console.debug(`All slots complete: ${event.completedSlots} slots`);
			callbacks.onAllComplete();
			break;
		}

		default:
			console.warn('Unknown SSE event type:', eventType, data);
	}
}
