import type { Agent, AgentId } from '$lib/types';

// Agent definitions with unique colors for visual distinction
export const AGENTS: Record<AgentId, Agent> = {
	'claude-sonnet-4-5': {
		id: 'claude-sonnet-4-5',
		name: 'Claude Sonnet 4.5',
		model: 'claude-sonnet-4-5',
		color: '#7c3aed', // violet
		icon: 'sparkles'
	},
	'claude-opus-4-5': {
		id: 'claude-opus-4-5',
		name: 'Claude Opus 4.5',
		model: 'claude-opus-4-5',
		color: '#a855f7', // purple
		icon: 'brain'
	},
	'gpt-5.2': {
		id: 'gpt-5.2',
		name: 'GPT 5.2',
		model: 'gpt-5.2',
		color: '#10b981', // emerald
		icon: 'zap'
	},
	'gpt-5.1': {
		id: 'gpt-5.1',
		name: 'GPT 5.1',
		model: 'gpt-5.1',
		color: '#06b6d4', // cyan
		icon: 'lightbulb'
	},
	'gpt-4o': {
		id: 'gpt-4o',
		name: 'GPT 4o',
		model: 'gpt-4o',
		color: '#0ea5e9', // sky
		icon: 'message-circle'
	},
	'gemini-3': {
		id: 'gemini-3',
		name: 'Gemini 3',
		model: 'gemini-3',
		color: '#f59e0b', // amber
		icon: 'star'
	}
};

// Array of all agents for iteration
export const AGENT_LIST: Agent[] = Object.values(AGENTS);

// Get agent by ID with type safety
export function getAgent(id: AgentId): Agent {
	return AGENTS[id];
}
