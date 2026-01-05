import { INITIAL_SLOTS, CONFIG } from '$lib/config/constants';
import type {
	AgentId,
	Message,
	PersistedState,
	Slot,
	SlotId,
	SlotStatus,
	ErrorType,
	TurnIndex,
	TurnStatus,
	SlotTurnData
} from '$lib/types';
import { browser } from '$app/environment';

// Generate unique message IDs
function generateId(): string {
	return `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

// Create the app store with Svelte 5 Runes
function createAppStore() {
	// === State ===
	let slots = $state<Slot[]>(structuredClone(INITIAL_SLOTS));
	let messages = $state<Message[]>([]);
	let selectedSlotId = $state<SlotId | null>(null);
	let inputValue = $state('');
	let isSending = $state(false);
	let isOnline = $state(browser ? navigator.onLine : true);

	// 3-turn workflow state
	let currentSessionId = $state<string | null>(null);
	let currentTurnIndex = $state<TurnIndex | null>(null);
	let turnStatus = $state<Record<TurnIndex, TurnStatus>>({
		1: 'pending',
		2: 'pending',
		3: 'pending'
	});

	// === Derived State ===
	const assignedSlots = $derived(slots.filter((s) => s.agentId !== null));
	const canSend = $derived(
		inputValue.trim().length > 0 && assignedSlots.length > 0 && !isSending && isOnline
	);
	const agentUsageCounts = $derived(
		slots.reduce(
			(acc, slot) => {
				if (slot.agentId) {
					acc[slot.agentId] = (acc[slot.agentId] || 0) + 1;
				}
				return acc;
			},
			{} as Record<AgentId, number>
		)
	);
	const errorSlots = $derived(slots.filter((s) => s.status === 'error'));
	const streamingSlots = $derived(slots.filter((s) => s.status === 'streaming'));

	// === Actions ===
	function assignAgentToSlot(slotId: SlotId, agentId: AgentId): void {
		const slotIndex = slots.findIndex((s) => s.id === slotId);
		if (slotIndex !== -1) {
			slots[slotIndex] = {
				...slots[slotIndex],
				agentId,
				status: 'idle',
				retryCount: 0,
				errorType: undefined
			};
			persistState();
		}
	}

	function clearSlot(slotId: SlotId): void {
		const slotIndex = slots.findIndex((s) => s.id === slotId);
		if (slotIndex !== -1) {
			slots[slotIndex] = {
				...slots[slotIndex],
				agentId: null,
				status: 'idle',
				retryCount: 0,
				errorType: undefined
			};
			persistState();
		}
	}

	function selectSlot(slotId: SlotId | null): void {
		selectedSlotId = slotId;
	}

	function setSlotStatus(slotId: SlotId, status: SlotStatus, errorType?: ErrorType): void {
		const slotIndex = slots.findIndex((s) => s.id === slotId);
		if (slotIndex !== -1) {
			slots[slotIndex] = {
				...slots[slotIndex],
				status,
				errorType: errorType || slots[slotIndex].errorType
			};
		}
	}

	function incrementRetryCount(slotId: SlotId): void {
		const slotIndex = slots.findIndex((s) => s.id === slotId);
		if (slotIndex !== -1) {
			slots[slotIndex] = {
				...slots[slotIndex],
				retryCount: slots[slotIndex].retryCount + 1
			};
		}
	}

	function resetRetryCount(slotId: SlotId): void {
		const slotIndex = slots.findIndex((s) => s.id === slotId);
		if (slotIndex !== -1) {
			slots[slotIndex] = {
				...slots[slotIndex],
				retryCount: 0
			};
		}
	}

	function addMessage(message: Omit<Message, 'id' | 'timestamp'>): Message {
		const newMessage: Message = {
			...message,
			id: generateId(),
			timestamp: Date.now()
		};
		messages = [...messages, newMessage];
		return newMessage;
	}

	function updateMessage(messageId: string, updates: Partial<Message>): void {
		const messageIndex = messages.findIndex((m) => m.id === messageId);
		if (messageIndex !== -1) {
			messages[messageIndex] = {
				...messages[messageIndex],
				...updates
			};
			// Trigger reactivity
			messages = [...messages];
		}
	}

	function appendToMessage(messageId: string, content: string): void {
		const messageIndex = messages.findIndex((m) => m.id === messageId);
		if (messageIndex !== -1) {
			messages[messageIndex] = {
				...messages[messageIndex],
				content: messages[messageIndex].content + content
			};
			// Trigger reactivity
			messages = [...messages];
		}
	}

	function setInputValue(value: string): void {
		inputValue = value;
	}

	function setIsSending(value: boolean): void {
		isSending = value;
	}

	function setIsOnline(value: boolean): void {
		isOnline = value;
	}

	function getSlot(slotId: SlotId): Slot | undefined {
		return slots.find((s) => s.id === slotId);
	}

	function getSlotByAgent(agentId: AgentId): Slot | undefined {
		return slots.find((s) => s.agentId === agentId);
	}

	function getMessagesForSlot(slotId: SlotId): Message[] {
		return messages.filter((m) => m.slotId === slotId);
	}

	function getLatestMessageForSlot(slotId: SlotId): Message | undefined {
		const slotMessages = getMessagesForSlot(slotId);
		return slotMessages[slotMessages.length - 1];
	}

	// === 3-Turn Workflow Methods ===

	function setCurrentSession(sessionId: string | null): void {
		currentSessionId = sessionId;
	}

	function setTurnStatus(turnIndex: TurnIndex, status: TurnStatus): void {
		turnStatus[turnIndex] = status;
		if (status === 'in_progress') {
			currentTurnIndex = turnIndex;
		}
		// Trigger reactivity
		turnStatus = { ...turnStatus };
	}

	function resetTurnStatus(): void {
		turnStatus = {
			1: 'pending',
			2: 'pending',
			3: 'pending'
		};
		currentTurnIndex = null;
	}

	function getTurnsForSlot(slotId: SlotId): SlotTurnData {
		const sessionMessages = currentSessionId
			? messages.filter((m) => m.sessionId === currentSessionId && m.slotId === slotId)
			: messages.filter((m) => m.slotId === slotId);

		const turn1 = sessionMessages.find((m) => m.turnIndex === 1 && m.kind === 'response');
		const turn2 = sessionMessages.find((m) => m.turnIndex === 2 && m.kind === 'comment');
		const turn3 = sessionMessages.find((m) => m.turnIndex === 3 && m.kind === 'reply');

		// Find comments received by this slot (for context)
		const receivedComments = currentSessionId
			? messages.filter(
					(m) =>
						m.sessionId === currentSessionId &&
						m.turnIndex === 2 &&
						m.kind === 'comment' &&
						m.targetSlotId === slotId
				)
			: [];

		return {
			turn1,
			turn2,
			turn3,
			receivedComments
		};
	}

	function getReceivedComments(slotId: SlotId): Message[] {
		return currentSessionId
			? messages.filter(
					(m) =>
						m.sessionId === currentSessionId &&
						m.turnIndex === 2 &&
						m.kind === 'comment' &&
						m.targetSlotId === slotId
				)
			: [];
	}

	function updateMessageAudioStatus(messageId: string, audioPath: string): void {
		const messageIndex = messages.findIndex((m) => m.id === messageId);
		if (messageIndex !== -1) {
			messages[messageIndex] = {
				...messages[messageIndex],
				audioPath,
				audioReady: true
			};
			messages = [...messages];
		}
	}

	function findMessageByTurn(
		slotId: SlotId,
		turnIndex: TurnIndex,
		sessionId?: string
	): Message | undefined {
		const session = sessionId || currentSessionId;
		return messages.find(
			(m) => m.slotId === slotId && m.turnIndex === turnIndex && m.sessionId === session
		);
	}

	// === Persistence ===
	function persistState(): void {
		if (!browser) return;
		const state: PersistedState = {
			slots: slots.map(({ id, agentId }) => ({ id, agentId }))
		};
		localStorage.setItem(CONFIG.localStorageKey, JSON.stringify(state));
	}

	function loadPersistedState(): void {
		if (!browser) return;
		try {
			const stored = localStorage.getItem(CONFIG.localStorageKey);
			if (stored) {
				const state: PersistedState = JSON.parse(stored);
				state.slots.forEach((persisted) => {
					if (persisted.agentId) {
						assignAgentToSlot(persisted.id, persisted.agentId);
					}
				});
			}
		} catch {
			// Ignore parse errors, start fresh
		}
	}

	function clearPersistedState(): void {
		if (!browser) return;
		localStorage.removeItem(CONFIG.localStorageKey);
	}

	// Initialize from localStorage
	if (browser) {
		loadPersistedState();

		// Listen for online/offline events
		window.addEventListener('online', () => setIsOnline(true));
		window.addEventListener('offline', () => setIsOnline(false));
	}

	return {
		// State (getters)
		get slots() {
			return slots;
		},
		get messages() {
			return messages;
		},
		get selectedSlotId() {
			return selectedSlotId;
		},
		get inputValue() {
			return inputValue;
		},
		get isSending() {
			return isSending;
		},
		get isOnline() {
			return isOnline;
		},

		// 3-turn workflow state (getters)
		get currentSessionId() {
			return currentSessionId;
		},
		get currentTurnIndex() {
			return currentTurnIndex;
		},
		get turnStatus() {
			return turnStatus;
		},

		// Derived state (getters)
		get assignedSlots() {
			return assignedSlots;
		},
		get canSend() {
			return canSend;
		},
		get agentUsageCounts() {
			return agentUsageCounts;
		},
		get errorSlots() {
			return errorSlots;
		},
		get streamingSlots() {
			return streamingSlots;
		},

		// Actions
		assignAgentToSlot,
		clearSlot,
		selectSlot,
		setSlotStatus,
		incrementRetryCount,
		resetRetryCount,
		addMessage,
		updateMessage,
		appendToMessage,
		setInputValue,
		setIsSending,
		setIsOnline,
		getSlot,
		getSlotByAgent,
		getMessagesForSlot,
		getLatestMessageForSlot,
		loadPersistedState,
		clearPersistedState,

		// 3-turn workflow actions
		setCurrentSession,
		setTurnStatus,
		resetTurnStatus,
		getTurnsForSlot,
		getReceivedComments,
		updateMessageAudioStatus,
		findMessageByTurn
	};
}

// Export singleton store
export const appStore = createAppStore();
