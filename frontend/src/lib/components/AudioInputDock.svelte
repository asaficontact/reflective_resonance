<script lang="ts">
	import { appStore } from '$lib/stores/app.svelte';
	import { API_CONFIG } from '$lib/config/constants';
	import { Mic, Loader2, WifiOff } from 'lucide-svelte';
	import { toast } from 'svelte-sonner';

	interface Props {
		ontranscript: (transcript: string) => void;
	}

	let { ontranscript }: Props = $props();

	// Recording state
	type RecordingState = 'idle' | 'recording' | 'uploading' | 'transcribing';
	let state = $state<RecordingState>('idle');
	let recordingDuration = $state(0);
	let mediaRecorder: MediaRecorder | null = null;
	let audioChunks: Blob[] = [];
	let recordingStartTime = 0;
	let durationInterval: ReturnType<typeof setInterval> | null = null;
	let currentMimeType = '';

	// Limits
	const MAX_DURATION_SEC = 15;

	// Derived states
	const isDisabled = $derived(
		appStore.assignedSlots.length === 0 || !appStore.isOnline || appStore.isSending || state !== 'idle'
	);

	const buttonLabel = $derived.by(() => {
		switch (state) {
			case 'recording':
				return `Recording... ${formatDuration(recordingDuration)}`;
			case 'uploading':
				return 'Uploading...';
			case 'transcribing':
				return 'Transcribing...';
			default:
				return 'Hold to talk';
		}
	});

	const statusText = $derived.by(() => {
		if (!appStore.isOnline) return '';
		if (appStore.assignedSlots.length === 0) return 'Assign agents to speaker slots first';
		if (appStore.isSending) {
			return `Streaming from ${appStore.streamingSlots.length} agent${appStore.streamingSlots.length !== 1 ? 's' : ''}...`;
		}
		return `${appStore.assignedSlots.length} agent${appStore.assignedSlots.length !== 1 ? 's' : ''} ready`;
	});

	function formatDuration(ms: number): string {
		const seconds = Math.floor(ms / 1000);
		const mins = Math.floor(seconds / 60);
		const secs = seconds % 60;
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	// Get preferred MIME type
	function getPreferredMimeType(): string {
		const types = ['audio/webm;codecs=opus', 'audio/ogg;codecs=opus', 'audio/webm'];
		for (const type of types) {
			if (MediaRecorder.isTypeSupported(type)) return type;
		}
		return '';
	}

	async function startRecording() {
		try {
			const stream = await navigator.mediaDevices.getUserMedia({
				audio: {
					echoCancellation: true,
					noiseSuppression: true,
					autoGainControl: true
				}
			});

			currentMimeType = getPreferredMimeType();
			mediaRecorder = new MediaRecorder(stream, {
				mimeType: currentMimeType || undefined
			});
			audioChunks = [];

			mediaRecorder.ondataavailable = (e) => {
				if (e.data.size > 0) audioChunks.push(e.data);
			};

			mediaRecorder.onstop = async () => {
				// Stop all tracks
				stream.getTracks().forEach((track) => track.stop());

				// Create blob and upload
				const mimeType = currentMimeType || 'audio/webm';
				const blob = new Blob(audioChunks, { type: mimeType });
				await uploadAndTranscribe(blob, mimeType);
			};

			// Start recording
			state = 'recording';
			recordingStartTime = Date.now();
			recordingDuration = 0;

			// Update duration display
			durationInterval = setInterval(() => {
				recordingDuration = Date.now() - recordingStartTime;

				// Auto-stop at max duration
				if (recordingDuration >= MAX_DURATION_SEC * 1000) {
					stopRecording();
				}
			}, 100);

			mediaRecorder.start();
		} catch (err) {
			console.error('Mic error:', err);
			if (err instanceof DOMException && err.name === 'NotAllowedError') {
				toast.error('Microphone permission denied. Please allow access.');
			} else {
				toast.error('Failed to start recording');
			}
			state = 'idle';
		}
	}

	function stopRecording() {
		if (durationInterval) {
			clearInterval(durationInterval);
			durationInterval = null;
		}

		if (mediaRecorder && mediaRecorder.state === 'recording') {
			mediaRecorder.stop();
		}
	}

	async function uploadAndTranscribe(blob: Blob, mimeType: string) {
		state = 'uploading';

		try {
			const formData = new FormData();
			const ext = mimeType.includes('webm') ? 'webm' : mimeType.includes('ogg') ? 'ogg' : 'webm';
			formData.append('file', blob, `recording.${ext}`);

			state = 'transcribing';

			const response = await fetch(`${API_CONFIG.baseUrl}/v1/stt`, {
				method: 'POST',
				body: formData
			});

			if (!response.ok) {
				const error = await response.json().catch(() => ({}));
				throw new Error(error.detail || `HTTP ${response.status}`);
			}

			const result = await response.json();
			const transcript = result.transcript?.trim();

			if (!transcript) {
				toast.error("Didn't catch that - try again.");
				state = 'idle';
				return;
			}

			// Success! Pass transcript to parent
			ontranscript(transcript);
			state = 'idle';
		} catch (err) {
			console.error('STT error:', err);
			toast.error(err instanceof Error ? err.message : 'Failed to transcribe');
			state = 'idle';
		}
	}

	// Pointer event handlers for press-and-hold
	function handlePointerDown(e: PointerEvent) {
		if (isDisabled) return;
		(e.target as HTMLElement).setPointerCapture(e.pointerId);
		startRecording();
	}

	function handlePointerUp() {
		if (state === 'recording') {
			stopRecording();
		}
	}

	function handlePointerCancel() {
		if (state === 'recording') {
			stopRecording();
		}
	}
</script>

<div class="audio-dock" class:offline={!appStore.isOnline}>
	<div class="dock-container">
		{#if !appStore.isOnline}
			<div class="offline-indicator">
				<WifiOff size={16} />
				<span>You are offline</span>
			</div>
		{/if}

		<button
			class="mic-button"
			class:recording={state === 'recording'}
			class:processing={state === 'uploading' || state === 'transcribing'}
			disabled={isDisabled}
			onpointerdown={handlePointerDown}
			onpointerup={handlePointerUp}
			onpointercancel={handlePointerCancel}
			onlostpointercapture={handlePointerUp}
		>
			{#if state === 'uploading' || state === 'transcribing'}
				<Loader2 size={32} class="spinner" />
			{:else}
				<Mic size={32} />
			{/if}
		</button>

		<span class="button-label">{buttonLabel}</span>

		{#if statusText}
			<span class="status-text">{statusText}</span>
		{/if}
	</div>
</div>

<style>
	.audio-dock {
		position: fixed;
		bottom: 0;
		left: 240px; /* Same as palette width */
		right: 320px; /* Same as responses panel width */
		padding: 1rem 2rem 1.5rem;
		background: linear-gradient(to top, var(--rr-bg), transparent);
		z-index: var(--rr-z-overlay);
	}

	.audio-dock.offline {
		background: linear-gradient(to top, rgba(239, 68, 68, 0.1), transparent);
	}

	.dock-container {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		max-width: 400px;
		margin: 0 auto;
	}

	.offline-indicator {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.5rem 1rem;
		background: rgba(239, 68, 68, 0.15);
		border-radius: 0.5rem;
		color: #ef4444;
		font-size: 0.875rem;
	}

	.mic-button {
		width: 80px;
		height: 80px;
		border-radius: 50%;
		border: none;
		background: var(--rr-surface-elevated);
		color: var(--rr-text-primary);
		cursor: pointer;
		transition: all 0.2s ease;
		display: flex;
		align-items: center;
		justify-content: center;
		touch-action: none;
		user-select: none;
		font-family: inherit;
	}

	.mic-button:hover:not(:disabled) {
		background: var(--rr-accent-violet);
		box-shadow: 0 0 20px var(--rr-glow-violet);
	}

	.mic-button:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.mic-button.recording {
		background: rgb(239, 68, 68);
		box-shadow: 0 0 30px rgba(239, 68, 68, 0.5);
		animation: pulse-recording 1s ease-in-out infinite;
	}

	.mic-button.processing {
		background: var(--rr-accent-violet);
		box-shadow: 0 0 20px var(--rr-glow-violet);
	}

	.button-label {
		font-size: 0.9375rem;
		color: var(--rr-text-secondary);
		text-align: center;
		font-weight: 500;
	}

	.status-text {
		font-size: 0.75rem;
		color: var(--rr-text-muted);
		text-align: center;
	}

	@keyframes pulse-recording {
		0%,
		100% {
			transform: scale(1);
		}
		50% {
			transform: scale(1.05);
		}
	}

	.mic-button :global(.spinner) {
		animation: spin 1s linear infinite;
	}

	@keyframes spin {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}

	/* Responsive */
	@media (max-width: 1200px) {
		.audio-dock {
			right: 280px;
		}
	}
</style>
