// Agent type identifiers
export type AgentId =
	| 'claude-sonnet-4-5'
	| 'claude-opus-4-5'
	| 'gpt-5.2'
	| 'gpt-5.1'
	| 'gpt-4o'
	| 'gemini-3';

// Speaker slot identifiers (1-6)
export type SlotId = 1 | 2 | 3 | 4 | 5 | 6;

// Slot status during operation
export type SlotStatus = 'idle' | 'streaming' | 'done' | 'error';

// Error types for retry logic
export type ErrorType = 'network' | 'timeout' | 'rate_limit' | 'server_error' | 'tts_error' | 'unknown';

// Agent definition with visual properties
export interface Agent {
	id: AgentId;
	name: string;
	model: string;
	color: string;
	icon: string;
}

// Speaker slot state
export interface Slot {
	id: SlotId;
	agentId: AgentId | null;
	status: SlotStatus;
	errorType?: ErrorType;
	retryCount: number;
}

// Message in the conversation
export interface Message {
	id: string;
	role: 'user' | 'agent';
	content: string;
	slotId?: SlotId;
	agentId?: AgentId;
	timestamp: number;
	isStreaming?: boolean;
}

// Streaming response chunk
export interface StreamChunk {
	slotId: SlotId;
	content: string;
	done: boolean;
	error?: ErrorType;
}

// Drag and drop item for svelte-dnd-action
export interface DndItem {
	id: string;
	agentId: AgentId;
}

// App configuration
export interface AppConfig {
	maxRetries: number;
	streamingDelayMs: [number, number]; // min, max
	errorRate: number;
	responseMaxLength: number;
	localStorageKey: string;
}

// Persisted state for localStorage
export interface PersistedState {
	slots: Pick<Slot, 'id' | 'agentId'>[];
}
