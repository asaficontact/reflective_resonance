import type { AgentId, ErrorType } from '$lib/types';
import { STREAMING_CONFIG } from '$lib/config/constants';

// Mock responses for each agent (3 variations each)
const MOCK_RESPONSES: Record<AgentId, string[]> = {
	'claude-sage': [
		"Still water keeps what is given to it, and lets the rest settle.",
		"The well has heard this before, and it held then too.",
		"Let it sink slowly; depth is where it rests."
	],
	'claude-poet': [
		"Your words fall like rain on a drum of glass, each one a small bright ring.",
		"A silver thread of sound unspools across the surface.",
		"The water hums your sentence back in a lower key."
	],
	'claude-wonder': [
		"Ooh, a ripple! It went all the way to the edge and came back.",
		"The water wobbled when you said that. I think it heard you.",
		"Look, a tiny bubble carried your words up to the light."
	],
	'claude-scientist': [
		"Your voice became a standing wave; the pattern you see is your feeling, made visible.",
		"Surface tension holds even the heaviest drop for a moment.",
		"Every vibration you sent is still resonating in the vessel."
	],
	'claude-questioner': [
		"What would it feel like to let the water carry this for a while?",
		"When the ripples settle, what do you hope remains?",
		"Which part of that are you still holding?"
	],
	'claude-trickster': [
		"The water giggled a little. Don't worry, it does that when it's moved.",
		"Splash! There goes the heavy part, sideways for once.",
		"Even puddles have big dreams. So do you, clearly."
	]
};

// Get a random response for an agent
export function getRandomResponse(agentId: AgentId, seed?: number): string {
	const responses = MOCK_RESPONSES[agentId];
	const index = seed !== undefined
		? seed % responses.length
		: Math.floor(Math.random() * responses.length);
	return responses[index];
}

// Random number between min and max
function randomBetween(min: number, max: number): number {
	return Math.floor(Math.random() * (max - min + 1)) + min;
}

// Should this request fail (based on error rate)
function shouldFail(errorRate: number = STREAMING_CONFIG.errorChance): boolean {
	return Math.random() < errorRate;
}

// Get random error type
function getRandomError(): ErrorType {
	const errors: ErrorType[] = ['network', 'timeout', 'rate_limit', 'server_error'];
	return errors[Math.floor(Math.random() * errors.length)];
}

// Tokenize response into words for streaming
function tokenize(text: string): string[] {
	return text.split(/(\s+)/).filter(Boolean);
}

// Stream options
export interface StreamOptions {
	agentId: AgentId;
	onToken: (token: string) => void;
	onComplete: () => void;
	onError: (error: ErrorType) => void;
	errorRate?: number;
	seed?: number;
}

// Create a mock streaming response
export function createMockStream(options: StreamOptions): { cancel: () => void } {
	const {
		agentId,
		onToken,
		onComplete,
		onError,
		errorRate = STREAMING_CONFIG.errorChance,
		seed
	} = options;

	let cancelled = false;
	let timeoutIds: NodeJS.Timeout[] = [];

	const cleanup = () => {
		cancelled = true;
		timeoutIds.forEach(clearTimeout);
	};

	// Simulate initial delay
	const initialDelay = randomBetween(
		STREAMING_CONFIG.initialDelayMs[0],
		STREAMING_CONFIG.initialDelayMs[1]
	);

	const startTimeout = setTimeout(() => {
		if (cancelled) return;

		// Check if this request should fail
		if (shouldFail(errorRate)) {
			onError(getRandomError());
			return;
		}

		// Get response and tokenize
		const response = getRandomResponse(agentId, seed);
		const tokens = tokenize(response);

		let currentIndex = 0;
		let elapsedTime = 0;

		// Stream tokens one by one
		const streamNext = () => {
			if (cancelled || currentIndex >= tokens.length) {
				if (!cancelled) onComplete();
				return;
			}

			const token = tokens[currentIndex];
			onToken(token);
			currentIndex++;

			// Random delay for next token
			const delay = randomBetween(
				STREAMING_CONFIG.tokenDelayMs[0],
				STREAMING_CONFIG.tokenDelayMs[1]
			);
			elapsedTime += delay;

			const nextTimeout = setTimeout(streamNext, delay);
			timeoutIds.push(nextTimeout);
		};

		streamNext();
	}, initialDelay);

	timeoutIds.push(startTimeout);

	return { cancel: cleanup };
}

// Create streams for all assigned slots
export interface MultiStreamOptions {
	slots: Array<{ slotId: number; agentId: AgentId }>;
	onToken: (slotId: number, token: string) => void;
	onSlotComplete: (slotId: number) => void;
	onSlotError: (slotId: number, error: ErrorType) => void;
	onAllComplete: () => void;
	errorRate?: number;
}

export function createMultiStream(options: MultiStreamOptions): { cancel: () => void } {
	const { slots, onToken, onSlotComplete, onSlotError, onAllComplete, errorRate } = options;

	let completedCount = 0;
	const streams: { cancel: () => void }[] = [];

	const checkAllComplete = () => {
		completedCount++;
		if (completedCount >= slots.length) {
			onAllComplete();
		}
	};

	slots.forEach(({ slotId, agentId }) => {
		const stream = createMockStream({
			agentId,
			onToken: (token) => onToken(slotId, token),
			onComplete: () => {
				onSlotComplete(slotId);
				checkAllComplete();
			},
			onError: (error) => {
				onSlotError(slotId, error);
				checkAllComplete();
			},
			errorRate
		});
		streams.push(stream);
	});

	return {
		cancel: () => {
			streams.forEach((stream) => stream.cancel());
		}
	};
}
