import type { AppConfig, Slot, SlotId } from '$lib/types';

// App configuration
export const CONFIG: AppConfig = {
	maxRetries: 3,
	streamingDelayMs: [30, 80], // Token delay range in ms
	errorRate: 0.05, // 5% mock error rate
	responseMaxLength: 500, // Max characters per response
	localStorageKey: 'reflective-resonance-state'
};

// All slot IDs
export const SLOT_IDS: SlotId[] = [1, 2, 3, 4, 5, 6];

// Initial slots state
export const INITIAL_SLOTS: Slot[] = SLOT_IDS.map((id) => ({
	id,
	agentId: null,
	status: 'idle',
	retryCount: 0
}));

// Keyboard shortcuts
export const KEYBOARD_SHORTCUTS = {
	selectSlot: ['1', '2', '3', '4', '5', '6'],
	clearSelection: 'Escape',
	sendMessage: 'Enter'
} as const;

// Streaming simulation config (for mock mode)
export const STREAMING_CONFIG = {
	initialDelayMs: [200, 1500], // Random delay before streaming starts
	tokenDelayMs: [30, 80], // Delay between tokens
	errorChance: 0.05 // 5% chance of error in dev mode
} as const;

// Backend API configuration
export const API_CONFIG = {
	baseUrl: 'http://localhost:8000',
	useMock: false // Set to true to use mock streaming instead of real backend
} as const;
