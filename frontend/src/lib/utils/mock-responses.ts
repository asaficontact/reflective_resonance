import type { AgentId, ErrorType } from '$lib/types';
import { STREAMING_CONFIG } from '$lib/config/constants';

// Mock responses for each agent (3 variations each)
const MOCK_RESPONSES: Record<AgentId, string[]> = {
	'claude-sonnet-4-5': [
		"I appreciate the thoughtful question. Let me offer a nuanced perspective that considers multiple viewpoints while remaining grounded in practical considerations.",
		"That's an interesting topic to explore. From my analysis, there are several key factors to consider that might influence how we approach this.",
		"Thank you for sharing. I find this fascinating and would like to suggest a framework for thinking about it that balances different priorities."
	],
	'claude-opus-4-5': [
		"This is a profound inquiry that touches on fundamental aspects of human experience. Allow me to explore the deeper implications and philosophical underpinnings.",
		"What a rich topic for contemplation. I see layers of meaning here that connect to broader themes of consciousness, creativity, and connection.",
		"The depth of this question invites careful reflection. Let me share some thoughts that weave together multiple threads of understanding."
	],
	'gpt-5.2': [
		"Great question! Here's a comprehensive breakdown with actionable insights and specific recommendations you can implement right away.",
		"I can help with that! Let me provide a structured analysis with clear steps and practical examples to guide your approach.",
		"Excellent topic! Based on current best practices and emerging trends, here's what I'd recommend for optimal results."
	],
	'gpt-5.1': [
		"Let me think through this systematically. The key considerations include several important factors that we should weigh carefully.",
		"That's a good question to explore. I'll break down the main elements and provide some balanced perspectives on each.",
		"I'd be happy to help with that. Here's my analysis based on the available information and relevant context."
	],
	'gpt-4o': [
		"Here's a quick and direct answer: the main points to consider are clarity, efficiency, and practical application.",
		"To address your question directly: I'd focus on the core elements first, then expand from there based on your specific needs.",
		"Simply put, the best approach involves understanding the fundamentals and building systematically from there."
	],
	'gemini-3': [
		"I've analyzed this from multiple angles and found some interesting patterns. Let me share insights that synthesize different perspectives.",
		"This connects to several fascinating areas. Drawing from diverse knowledge domains, here's a multi-faceted view of the topic.",
		"Looking at this holistically, I see opportunities to integrate ideas from different fields for a more comprehensive understanding."
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
