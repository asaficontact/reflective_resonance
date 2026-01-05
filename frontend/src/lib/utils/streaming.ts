/**
 * Real SSE streaming client for backend API.
 * Phase 3: 3-Turn Inter-Agent Workflow support.
 */

import type { AgentId, ErrorType, TurnIndex, MessageKind, SlotId } from '$lib/types';
import { API_CONFIG } from '$lib/config/constants';

// SSE event data types (matching backend models)
interface TurnStartEvent {
	sessionId: string;
	turnIndex: TurnIndex;
}

interface TurnDoneEvent {
	sessionId: string;
	turnIndex: TurnIndex;
	slotCount: number;
}

interface SlotStartEvent {
	sessionId: string;
	turnIndex: TurnIndex;
	kind: MessageKind;
	slotId: number;
	agentId: string;
}

interface SlotTokenEvent {
	slotId: number;
	content: string;
}

interface SlotDoneEvent {
	sessionId: string;
	turnIndex: TurnIndex;
	kind: MessageKind;
	slotId: number;
	agentId: string;
	text: string;
	voiceProfile: string;
	targetSlotId?: number; // Only for Turn 2 (comment)
}

interface SlotAudioEvent {
	sessionId: string;
	turnIndex: TurnIndex;
	kind: MessageKind;
	slotId: number;
	agentId: string;
	voiceProfile: string;
	audioFormat: string;
	audioPath: string;
}

interface SlotErrorEvent {
	sessionId: string;
	turnIndex: TurnIndex;
	kind: MessageKind;
	slotId: number;
	agentId: string;
	error: {
		type: ErrorType;
		message: string;
	};
}

interface DoneEvent {
	sessionId: string;
	completedSlots: number;
	turns: number;
}

// Extended slot done data for 3-turn workflow
export interface SlotDoneData {
	slotId: SlotId;
	agentId: AgentId;
	text: string;
	voiceProfile: string;
	sessionId: string;
	turnIndex: TurnIndex;
	kind: MessageKind;
	targetSlotId?: SlotId;
}

// Extended audio ready data
export interface SlotAudioData {
	slotId: SlotId;
	agentId: AgentId;
	voiceProfile: string;
	audioPath: string;
	sessionId: string;
	turnIndex: TurnIndex;
	kind: MessageKind;
}

// Multi-stream options with 3-turn workflow callbacks
export interface MultiStreamOptions {
	message: string;
	slots: Array<{ slotId: number; agentId: AgentId }>;

	// Legacy callbacks (for backwards compatibility)
	onToken: (slotId: number, token: string) => void;
	onSlotComplete: (slotId: number) => void;
	onSlotError: (slotId: number, error: ErrorType) => void;
	onAllComplete: () => void;

	// 3-turn workflow callbacks (optional)
	onTurnStart?: (turnIndex: TurnIndex, sessionId: string) => void;
	onTurnDone?: (turnIndex: TurnIndex, slotCount: number, sessionId: string) => void;
	onSlotDone?: (data: SlotDoneData) => void;
	onSlotAudio?: (data: SlotAudioData) => void;
	onSessionStart?: (sessionId: string) => void;
}

/**
 * Create a real SSE stream to the backend API.
 * Broadcasts a message to all slots and streams 3-turn workflow responses.
 */
export function createRealStream(options: MultiStreamOptions): { cancel: () => void } {
	const {
		message,
		slots,
		onToken,
		onSlotComplete,
		onSlotError,
		onAllComplete,
		onTurnStart,
		onTurnDone,
		onSlotDone,
		onSlotAudio,
		onSessionStart
	} = options;

	const abortController = new AbortController();
	let cancelled = false;
	let sessionId: string | null = null;

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

							// Capture session ID from first event
							if (!sessionId && data.sessionId) {
								sessionId = data.sessionId;
								onSessionStart?.(sessionId);
							}

							handleSSEEvent(currentEvent, data, {
								onToken,
								onSlotComplete,
								onSlotError,
								onAllComplete,
								onTurnStart,
								onTurnDone,
								onSlotDone,
								onSlotAudio
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
		onTurnStart?: (turnIndex: TurnIndex, sessionId: string) => void;
		onTurnDone?: (turnIndex: TurnIndex, slotCount: number, sessionId: string) => void;
		onSlotDone?: (data: SlotDoneData) => void;
		onSlotAudio?: (data: SlotAudioData) => void;
	}
) {
	switch (eventType) {
		case 'turn.start': {
			const event = data as TurnStartEvent;
			console.debug(`Turn ${event.turnIndex} started (session: ${event.sessionId})`);
			callbacks.onTurnStart?.(event.turnIndex, event.sessionId);
			break;
		}

		case 'turn.done': {
			const event = data as TurnDoneEvent;
			console.debug(
				`Turn ${event.turnIndex} done: ${event.slotCount} slots (session: ${event.sessionId})`
			);
			callbacks.onTurnDone?.(event.turnIndex, event.slotCount, event.sessionId);
			break;
		}

		case 'slot.start': {
			const event = data as SlotStartEvent;
			console.debug(
				`Slot ${event.slotId} (${event.agentId}) started - Turn ${event.turnIndex} ${event.kind}`
			);
			break;
		}

		case 'slot.token': {
			// Legacy event - kept for backwards compatibility
			const event = data as SlotTokenEvent;
			callbacks.onToken(event.slotId, event.content);
			break;
		}

		case 'slot.done': {
			const event = data as SlotDoneEvent;

			// For Turn 1, use legacy callback for backwards compatibility
			if (event.turnIndex === 1) {
				callbacks.onToken(event.slotId, event.text);
				callbacks.onSlotComplete(event.slotId);
			}

			// Call new callback with full data
			callbacks.onSlotDone?.({
				slotId: event.slotId as SlotId,
				agentId: event.agentId as AgentId,
				text: event.text,
				voiceProfile: event.voiceProfile,
				sessionId: event.sessionId,
				turnIndex: event.turnIndex,
				kind: event.kind,
				targetSlotId: event.targetSlotId as SlotId | undefined
			});

			console.debug(
				`Slot ${event.slotId} done - Turn ${event.turnIndex} ${event.kind}: ` +
					`voice=${event.voiceProfile}, ${event.text.length} chars` +
					(event.targetSlotId ? ` -> slot ${event.targetSlotId}` : '')
			);
			break;
		}

		case 'slot.audio': {
			const event = data as SlotAudioEvent;
			console.debug(
				`Slot ${event.slotId} audio ready - Turn ${event.turnIndex}: ${event.audioPath}`
			);
			callbacks.onSlotAudio?.({
				slotId: event.slotId as SlotId,
				agentId: event.agentId as AgentId,
				voiceProfile: event.voiceProfile,
				audioPath: event.audioPath,
				sessionId: event.sessionId,
				turnIndex: event.turnIndex,
				kind: event.kind
			});
			break;
		}

		case 'slot.error': {
			const event = data as SlotErrorEvent;
			callbacks.onSlotError(event.slotId, event.error.type);
			console.error(
				`Slot ${event.slotId} error - Turn ${event.turnIndex} ${event.kind}:`,
				event.error
			);
			break;
		}

		case 'done': {
			const event = data as DoneEvent;
			console.debug(
				`Workflow complete: ${event.completedSlots} slots, ${event.turns} turns ` +
					`(session: ${event.sessionId})`
			);
			callbacks.onAllComplete();
			break;
		}

		default:
			console.warn('Unknown SSE event type:', eventType, data);
	}
}
