<script lang="ts">
	import { appStore } from '$lib/stores/app.svelte';
	import { Textarea } from '$lib/components/ui/textarea';
	import { Button } from '$lib/components/ui/button';
	import { Send, WifiOff } from 'lucide-svelte';

	interface Props {
		onsubmit: (message: string) => void;
	}

	let { onsubmit }: Props = $props();

	function handleSubmit() {
		if (!appStore.canSend) return;
		const message = appStore.inputValue.trim();
		if (message) {
			onsubmit(message);
			appStore.setInputValue('');
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	}

	const placeholderText = $derived.by(() => {
		if (!appStore.isOnline) return 'You are offline...';
		if (appStore.assignedSlots.length === 0) return 'Assign agents to speaker slots first...';
		if (appStore.isSending) return 'Waiting for responses...';
		return 'Type your message... (Enter to send, Shift+Enter for new line)';
	});

	const isDisabled = $derived(!appStore.canSend);
</script>

<div class="chat-dock" class:offline={!appStore.isOnline}>
	<div class="chat-container">
		{#if !appStore.isOnline}
			<div class="offline-indicator">
				<WifiOff size={16} />
				<span>You are offline</span>
			</div>
		{/if}

		<div class="input-wrapper">
			<Textarea
				value={appStore.inputValue}
				oninput={(e: Event) => appStore.setInputValue((e.target as HTMLTextAreaElement).value)}
				onkeydown={handleKeydown}
				placeholder={placeholderText}
				disabled={appStore.assignedSlots.length === 0 || !appStore.isOnline}
				class="chat-input"
				rows={1}
			/>
			<Button
				onclick={handleSubmit}
				disabled={isDisabled}
				variant="default"
				size="icon"
				class="send-button"
				aria-label="Send message"
			>
				<Send size={18} />
			</Button>
		</div>

		<div class="chat-status">
			{#if appStore.isSending}
				<span class="status-text">
					Streaming from {appStore.streamingSlots.length} agent{appStore.streamingSlots.length !== 1 ? 's' : ''}...
				</span>
			{:else if appStore.assignedSlots.length > 0}
				<span class="status-text">
					{appStore.assignedSlots.length} agent{appStore.assignedSlots.length !== 1 ? 's' : ''} ready
				</span>
			{/if}
		</div>
	</div>
</div>

<style>
	.chat-dock {
		position: fixed;
		bottom: 0;
		left: 240px; /* Same as palette width */
		right: 320px; /* Same as responses panel width */
		padding: 1rem 2rem 1.5rem;
		background: linear-gradient(to top, var(--rr-bg), transparent);
		z-index: var(--rr-z-overlay);
	}

	.chat-dock.offline {
		background: linear-gradient(to top, rgba(239, 68, 68, 0.1), transparent);
	}

	.chat-container {
		max-width: 800px;
		margin: 0 auto;
	}

	.offline-indicator {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.5rem;
		margin-bottom: 0.5rem;
		background: rgba(239, 68, 68, 0.15);
		border-radius: 0.5rem;
		color: #ef4444;
		font-size: 0.875rem;
	}

	.input-wrapper {
		display: flex;
		gap: 0.75rem;
		align-items: flex-end;
	}

	.input-wrapper :global(.chat-input) {
		flex: 1;
		min-height: 48px;
		max-height: 120px;
		resize: none;
		background: var(--rr-surface);
		border: 1px solid var(--rr-surface-elevated);
		border-radius: 0.75rem;
		padding: 0.75rem 1rem;
		font-size: 0.9375rem;
		color: var(--rr-text-primary);
	}

	.input-wrapper :global(.chat-input:focus) {
		border-color: var(--rr-accent-violet);
		box-shadow: 0 0 0 2px var(--rr-glow-violet);
	}

	.input-wrapper :global(.chat-input:disabled) {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.input-wrapper :global(.send-button) {
		width: 48px;
		height: 48px;
		background: var(--rr-accent-violet);
		border-radius: 0.75rem;
	}

	.input-wrapper :global(.send-button:hover:not(:disabled)) {
		background: color-mix(in srgb, var(--rr-accent-violet) 85%, white);
	}

	.input-wrapper :global(.send-button:disabled) {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.chat-status {
		margin-top: 0.5rem;
		text-align: center;
	}

	.status-text {
		font-size: 0.75rem;
		color: var(--rr-text-muted);
	}

	/* Responsive */
	@media (max-width: 1200px) {
		.chat-dock {
			right: 280px;
		}
	}
</style>
