import type { Agent, AgentId } from '$lib/types';

// All agents run on Claude; each has its own persona (see backend/agents.py)
export const AGENTS: Record<AgentId, Agent> = {
	'claude-sage': {
		id: 'claude-sage',
		name: 'Sage',
		model: 'claude-sonnet-5-5',
		color: '#7c3aed', // violet
		icon: 'sparkles'
	},
	'claude-poet': {
		id: 'claude-poet',
		name: 'Poet',
		model: 'claude-sonnet-5-5',
		color: '#a855f7', // purple
		icon: 'brain'
	},
	'claude-wonder': {
		id: 'claude-wonder',
		name: 'Wonder',
		model: 'claude-sonnet-5-5',
		color: '#10b981', // emerald
		icon: 'zap'
	},
	'claude-scientist': {
		id: 'claude-scientist',
		name: 'Scientist',
		model: 'claude-sonnet-5-5',
		color: '#06b6d4', // cyan
		icon: 'lightbulb'
	},
	'claude-questioner': {
		id: 'claude-questioner',
		name: 'Questioner',
		model: 'claude-sonnet-5-5',
		color: '#0ea5e9', // sky
		icon: 'message-circle'
	},
	'claude-trickster': {
		id: 'claude-trickster',
		name: 'Trickster',
		model: 'claude-sonnet-5-5',
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
