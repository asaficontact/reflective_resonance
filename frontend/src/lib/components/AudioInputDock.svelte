<script lang="ts">
	import { onDestroy } from 'svelte';
	import { appStore } from '$lib/stores/app.svelte';
	import { API_CONFIG } from '$lib/config/constants';
	import { Mic, MicOff, Loader2, WifiOff } from 'lucide-svelte';
	import { toast } from 'svelte-sonner';

	interface Props {
		ontranscript: (transcript: string) => void;
	}

	let { ontranscript }: Props = $props();

	// ------------------------------------------------------------------
	// Always-on microphone with voice activity detection (no push-to-talk)
	//
	// The mic stream stays open. A visitor simply speaks: speech start and
	// end are detected automatically, the utterance is uploaded for STT and
	// the transcript is sent on. While a round is being generated and played
	// back on the speakers, listening is paused so the installation does not
	// hear itself.
	// ------------------------------------------------------------------

	type MicState = 'off' | 'starting' | 'listening' | 'recording' | 'transcribing' | 'blocked';
	let state = $state<MicState>('off');
	let paused = $state(false); // manual mute (click the mic button)
	let level = $state(0); // 0..1 input level for the meter
	let recordingDuration = $state(0);
	let holdRemainingMs = $state(0); // playback hold after a round

	// --- Tunables -------------------------------------------------------
	const MAX_DURATION_SEC = 15; // longest single utterance
	const MIN_SPEECH_MS = 600; // shorter bursts are ignored (coughs, clicks)
	const START_HOLD_MS = 160; // level must stay above threshold this long to start
	const END_SILENCE_MS = 1300; // silence that ends an utterance
	const PRE_ROLL_MS = 500; // audio kept from just before speech was detected
	// Volume gate (RMS): sound quieter than this is ignored as background noise.
	// Adjustable on the page with the "Noise gate" slider and remembered in the
	// browser. Measured with the reSpeaker: a quiet room is ~0.001, someone
	// speaking at the microphone is ~0.02-0.045.
	const GATE_DEFAULT = 0.012;
	const GATE_MIN = 0.002; // the gate never goes below this
	const GATE_STORAGE_KEY = 'reflective-resonance-mic-gate';
	const METER_MAX = 0.06; // RMS shown as a full meter
	const THRESHOLD_RATIO = 3.2; // threshold = noise floor x this
	const UPLOAD_SAMPLE_RATE = 16000;
	// Playback hold after a round: speech runs at about 17 characters per second
	const PLAYBACK_CHARS_PER_SEC = 15;
	const PLAYBACK_EXTRA_SEC = 8;
	const PLAYBACK_FALLBACK_SEC = 75;

	// --- Noise gate state (after the tunables it reads) -------------------
	let gate = $state(loadGate()); // volume gate (RMS), see GATE_DEFAULT
	let rmsNow = $state(0); // current speech-band level (RMS) for the meter

	function loadGate(): number {
		try {
			const stored = parseFloat(localStorage.getItem(GATE_STORAGE_KEY) ?? '');
			if (stored >= 0 && stored <= METER_MAX) return stored;
		} catch {
			// storage unavailable: use the default
		}
		return GATE_DEFAULT;
	}

	function saveGate() {
		try {
			localStorage.setItem(GATE_STORAGE_KEY, String(gate));
		} catch {
			// storage unavailable: the value just is not remembered
		}
	}

	const meterPercent = $derived(Math.min(100, (rmsNow / METER_MAX) * 100));
	const gatePercent = $derived(Math.min(100, (gate / METER_MAX) * 100));

	// --- Audio graph ----------------------------------------------------
	let stream: MediaStream | null = null;
	let audioCtx: AudioContext | null = null;
	let processor: ScriptProcessorNode | null = null;
	let sourceNode: MediaStreamAudioSourceNode | null = null;
	let sinkNode: GainNode | null = null;

	// --- Detection state (plain variables: updated ~12x per second) ------
	let noiseFloor = 0.004;
	let hpPrevIn = 0;
	let hpPrevOut = 0;
	let aboveMs = 0;
	let silenceMs = 0;
	let speechMs = 0;
	let capturing = false;
	let captured: Float32Array[] = [];
	let capturedMs = 0;
	let preRoll: Float32Array[] = [];
	let preRollMs = 0;
	let holdTimer: ReturnType<typeof setInterval> | null = null;
	let holdUntil = 0;
	let wasSending = false;

	const ready = $derived(appStore.assignedSlots.length > 0 && appStore.isOnline);

	// The mic may act on speech only when nothing else is going on
	const armed = $derived(
		ready && !appStore.isSending && !paused && holdRemainingMs === 0 && state === 'listening'
	);

	const buttonLabel = $derived.by(() => {
		if (state === 'blocked') return 'Click to enable the microphone';
		if (state === 'starting') return 'Starting microphone...';
		if (paused) return 'Microphone paused';
		if (state === 'recording') return `Listening to you... ${formatDuration(recordingDuration)}`;
		if (state === 'transcribing') return 'Transcribing...';
		if (appStore.isSending) return 'The voices are answering...';
		if (holdRemainingMs > 0) return `The water is speaking... ${Math.ceil(holdRemainingMs / 1000)}s`;
		if (state === 'listening') return 'Listening - just speak';
		return 'Microphone off';
	});

	const statusText = $derived.by(() => {
		if (!appStore.isOnline) return '';
		if (appStore.assignedSlots.length === 0) return 'Assign agents to speaker slots first';
		if (appStore.isSending) {
			return `Streaming from ${appStore.streamingSlots.length} agent${appStore.streamingSlots.length !== 1 ? 's' : ''}...`;
		}
		if (holdRemainingMs > 0) return 'Click the mic to listen again now';
		if (paused) return 'Click the mic to resume';
		return `${appStore.assignedSlots.length} agent${appStore.assignedSlots.length !== 1 ? 's' : ''} ready - click the mic to pause`;
	});

	function formatDuration(ms: number): string {
		const seconds = Math.floor(ms / 1000);
		const mins = Math.floor(seconds / 60);
		const secs = seconds % 60;
		return `${mins}:${secs.toString().padStart(2, '0')}`;
	}

	// ------------------------------------------------------------------
	// Microphone lifecycle
	// ------------------------------------------------------------------

	async function startMic() {
		if (state !== 'off' && state !== 'blocked') return;
		state = 'starting';
		try {
			stream = await navigator.mediaDevices.getUserMedia({
				audio: {
					channelCount: 1,
					echoCancellation: true,
					noiseSuppression: true,
					// Auto gain would slowly amplify room noise between visitors
					autoGainControl: false
				}
			});

			audioCtx = new AudioContext();
			sourceNode = audioCtx.createMediaStreamSource(stream);
			processor = audioCtx.createScriptProcessor(4096, 1, 1);
			processor.onaudioprocess = handleAudioFrame;
			// The processor must be connected to run; a muted gain keeps it silent
			sinkNode = audioCtx.createGain();
			sinkNode.gain.value = 0;
			sourceNode.connect(processor);
			processor.connect(sinkNode);
			sinkNode.connect(audioCtx.destination);

			if (audioCtx.state === 'suspended') {
				await audioCtx.resume().catch(() => {});
			}
			// Browsers may keep audio suspended until the page is clicked once
			state = audioCtx.state === 'running' ? 'listening' : 'blocked';
		} catch (err) {
			console.error('Mic error:', err);
			if (err instanceof DOMException && err.name === 'NotAllowedError') {
				toast.error('Microphone permission denied. Please allow access.');
			} else {
				toast.error('Failed to open the microphone');
			}
			stopMic();
			state = 'blocked';
		}
	}

	function stopMic() {
		processor?.disconnect();
		sourceNode?.disconnect();
		sinkNode?.disconnect();
		stream?.getTracks().forEach((track) => track.stop());
		audioCtx?.close().catch(() => {});
		processor = null;
		sourceNode = null;
		sinkNode = null;
		stream = null;
		audioCtx = null;
		resetCapture();
		level = 0;
		state = 'off';
	}

	function resetCapture() {
		capturing = false;
		captured = [];
		capturedMs = 0;
		aboveMs = 0;
		silenceMs = 0;
		speechMs = 0;
		recordingDuration = 0;
	}

	// ------------------------------------------------------------------
	// Voice activity detection (runs for every audio frame, ~85 ms)
	// ------------------------------------------------------------------

	function handleAudioFrame(e: AudioProcessingEvent) {
		const input = e.inputBuffer.getChannelData(0);
		const sampleRate = e.inputBuffer.sampleRate;
		const frameMs = (input.length / sampleRate) * 1000;

		// Level of the speech band only: a one-pole high-pass (~200 Hz) removes
		// the low rumble of the water speakers (20-100 Hz) before measuring.
		const alpha = 1 / (1 + (2 * Math.PI * 200) / sampleRate);
		let sum = 0;
		for (let i = 0; i < input.length; i++) {
			const out = alpha * (hpPrevOut + input[i] - hpPrevIn);
			hpPrevIn = input[i];
			hpPrevOut = out;
			sum += out * out;
		}
		const rms = Math.sqrt(sum / input.length);
		level = Math.min(1, rms * 12);
		rmsNow = rms;

		if (!armed && !capturing) {
			// Not allowed to listen right now: forget any partial detection
			aboveMs = 0;
			preRoll = [];
			preRollMs = 0;
			return;
		}

		// Speech must be louder than the gate, and clearly above the room noise
		const threshold = Math.max(gate, GATE_MIN, noiseFloor * THRESHOLD_RATIO);
		const isLoud = rms > threshold;
		const frame = new Float32Array(input);

		if (!capturing) {
			// Learn the room's noise floor while nobody is speaking
			if (!isLoud) noiseFloor = noiseFloor * 0.95 + rms * 0.05;

			preRoll.push(frame);
			preRollMs += frameMs;
			while (preRollMs > PRE_ROLL_MS + frameMs && preRoll.length > 1) {
				preRollMs -= (preRoll[0].length / sampleRate) * 1000;
				preRoll.shift();
			}

			aboveMs = isLoud ? aboveMs + frameMs : 0;
			if (aboveMs >= START_HOLD_MS) {
				// Speech started: keep the pre-roll so the first word is not clipped
				capturing = true;
				captured = preRoll;
				capturedMs = preRollMs;
				preRoll = [];
				preRollMs = 0;
				speechMs = aboveMs;
				silenceMs = 0;
				state = 'recording';
			}
			return;
		}

		// Capturing an utterance
		captured.push(frame);
		capturedMs += frameMs;
		recordingDuration = capturedMs;
		if (isLoud) {
			speechMs += frameMs;
			silenceMs = 0;
		} else {
			silenceMs += frameMs;
		}

		if (silenceMs >= END_SILENCE_MS || capturedMs >= MAX_DURATION_SEC * 1000) {
			const frames = captured;
			const hadSpeech = speechMs >= MIN_SPEECH_MS;
			resetCapture();
			if (hadSpeech) {
				void uploadAndTranscribe(encodeWav(frames, sampleRate));
			} else {
				state = 'listening'; // too short to be speech: ignore it
			}
		}
	}

	// ------------------------------------------------------------------
	// Encoding and upload
	// ------------------------------------------------------------------

	function encodeWav(frames: Float32Array[], sampleRate: number): Blob {
		const total = frames.reduce((n, f) => n + f.length, 0);
		const pcm = new Float32Array(total);
		let offset = 0;
		for (const f of frames) {
			pcm.set(f, offset);
			offset += f.length;
		}

		// Downsample to 16 kHz by averaging (enough for speech, small upload)
		const ratio = sampleRate / UPLOAD_SAMPLE_RATE;
		const outLength = ratio > 1 ? Math.floor(total / ratio) : total;
		const outRate = ratio > 1 ? UPLOAD_SAMPLE_RATE : sampleRate;
		const buffer = new ArrayBuffer(44 + outLength * 2);
		const view = new DataView(buffer);
		const writeString = (pos: number, s: string) => {
			for (let i = 0; i < s.length; i++) view.setUint8(pos + i, s.charCodeAt(i));
		};
		writeString(0, 'RIFF');
		view.setUint32(4, 36 + outLength * 2, true);
		writeString(8, 'WAVE');
		writeString(12, 'fmt ');
		view.setUint32(16, 16, true);
		view.setUint16(20, 1, true); // PCM
		view.setUint16(22, 1, true); // mono
		view.setUint32(24, outRate, true);
		view.setUint32(28, outRate * 2, true);
		view.setUint16(32, 2, true);
		view.setUint16(34, 16, true);
		writeString(36, 'data');
		view.setUint32(40, outLength * 2, true);

		for (let i = 0; i < outLength; i++) {
			let sample: number;
			if (ratio > 1) {
				const start = Math.floor(i * ratio);
				const end = Math.min(total, Math.floor((i + 1) * ratio));
				let acc = 0;
				for (let j = start; j < end; j++) acc += pcm[j];
				sample = acc / Math.max(1, end - start);
			} else {
				sample = pcm[i];
			}
			const clamped = Math.max(-1, Math.min(1, sample));
			view.setInt16(44 + i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
		}
		return new Blob([buffer], { type: 'audio/wav' });
	}

	async function uploadAndTranscribe(blob: Blob) {
		state = 'transcribing';
		try {
			const formData = new FormData();
			formData.append('file', blob, 'utterance.wav');

			const response = await fetch(`${API_CONFIG.baseUrl}/v1/stt`, {
				method: 'POST',
				body: formData
			});

			// 422 = no speech in the clip (room noise): quietly keep listening
			if (response.status === 422) return;
			if (!response.ok) {
				const error = await response.json().catch(() => ({}));
				throw new Error(error.detail || `HTTP ${response.status}`);
			}

			const result = await response.json();
			// The STT service labels non-speech as tags like "[background noise]"
			// or "(music)": remove them, and send only if real words remain.
			const transcript = (result.transcript ?? '')
				.replace(/\[[^\]]*\]|\([^)]*\)/g, ' ')
				.replace(/\s+/g, ' ')
				.trim();
			if (/[\p{L}\p{N}]/u.test(transcript)) ontranscript(transcript);
		} catch (err) {
			console.error('STT error:', err);
			toast.error(err instanceof Error ? err.message : 'Failed to transcribe');
		} finally {
			if (state === 'transcribing') state = 'listening';
		}
	}

	// ------------------------------------------------------------------
	// Playback hold: after a round, stay quiet while the speakers play it
	// ------------------------------------------------------------------

	function estimatePlaybackMs(): number {
		const messages = appStore.messages;
		let lastUser = -1;
		for (let i = messages.length - 1; i >= 0; i--) {
			if (messages[i].role === 'user') {
				lastUser = i;
				break;
			}
		}
		let chars = 0;
		for (let i = lastUser + 1; i < messages.length; i++) chars += messages[i].content.length;
		const seconds =
			chars > 0 ? chars / PLAYBACK_CHARS_PER_SEC + PLAYBACK_EXTRA_SEC : PLAYBACK_FALLBACK_SEC;
		return seconds * 1000;
	}

	function startHold(ms: number) {
		clearHold();
		holdUntil = Date.now() + ms;
		holdRemainingMs = ms;
		holdTimer = setInterval(() => {
			holdRemainingMs = Math.max(0, holdUntil - Date.now());
			if (holdRemainingMs === 0) clearHold();
		}, 250);
	}

	function clearHold() {
		if (holdTimer) clearInterval(holdTimer);
		holdTimer = null;
		holdRemainingMs = 0;
	}

	// When a round finishes generating, hold for its estimated playback time
	$effect(() => {
		const sending = appStore.isSending;
		if (wasSending && !sending) startHold(estimatePlaybackMs());
		wasSending = sending;
	});

	// Open the mic as soon as agents are assigned; close it when they are not
	$effect(() => {
		if (ready && state === 'off') {
			void startMic();
		} else if (!ready && state !== 'off' && state !== 'starting') {
			stopMic();
		}
	});

	// One click: enable audio if the browser blocked it, skip the playback
	// hold, or pause / resume listening.
	async function handleMicClick() {
		if (!ready) return;
		if (state === 'blocked' || state === 'off') {
			if (audioCtx && audioCtx.state === 'suspended') {
				await audioCtx.resume().catch(() => {});
				state = (audioCtx.state as AudioContextState) === 'running' ? 'listening' : 'blocked';
			} else {
				stopMic();
				await startMic();
			}
			return;
		}
		if (holdRemainingMs > 0) {
			clearHold();
			return;
		}
		paused = !paused;
		if (paused && capturing) {
			resetCapture();
			state = 'listening';
		}
	}

	onDestroy(() => {
		clearHold();
		stopMic();
	});
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
			class:processing={state === 'transcribing'}
			class:listening={armed}
			class:muted={paused || state === 'blocked'}
			disabled={!ready}
			onclick={handleMicClick}
			aria-label={buttonLabel}
			style="--mic-level: {armed || state === 'recording' ? level : 0}"
		>
			{#if state === 'transcribing' || state === 'starting'}
				<Loader2 size={32} class="spinner" />
			{:else if paused || state === 'blocked'}
				<MicOff size={32} />
			{:else}
				<Mic size={32} />
			{/if}
		</button>

		<span class="button-label">{buttonLabel}</span>

		{#if statusText}
			<span class="status-text">{statusText}</span>
		{/if}

		{#if ready}
			<div class="gate-control" title="Sound below the marker is ignored as background noise">
				<span class="gate-label">Noise gate</span>
				<div class="gate-meter">
					<div class="gate-meter-fill" class:over={rmsNow > gate} style="width: {meterPercent}%"></div>
					<div class="gate-marker" style="left: {gatePercent}%"></div>
					<input
						class="gate-slider"
						type="range"
						min="0"
						max={METER_MAX}
						step="0.001"
						bind:value={gate}
						onchange={saveGate}
						aria-label="Noise gate: sound quieter than this is ignored"
					/>
				</div>
			</div>
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

	/* Always-on listening: a soft ring that follows the input level */
	.mic-button.listening {
		box-shadow: 0 0 0 calc(2px + var(--mic-level, 0) * 18px) var(--rr-glow-violet);
	}

	.mic-button.recording {
		box-shadow: 0 0 0 calc(4px + var(--mic-level, 0) * 22px) rgba(239, 68, 68, 0.45);
		animation: none;
	}

	.mic-button.muted {
		opacity: 0.6;
	}

	/* Noise gate: live level meter with a draggable threshold marker */
	.gate-control {
		display: flex;
		align-items: center;
		gap: 0.6rem;
		width: 260px;
		opacity: 0.55;
		transition: opacity 0.2s ease;
	}

	.gate-control:hover,
	.gate-control:focus-within {
		opacity: 1;
	}

	.gate-label {
		font-size: 0.6875rem;
		color: var(--rr-text-muted);
		white-space: nowrap;
	}

	.gate-meter {
		position: relative;
		flex: 1;
		height: 8px;
		border-radius: 4px;
		background: var(--rr-surface-elevated);
	}

	.gate-meter-fill {
		height: 100%;
		border-radius: 4px;
		background: var(--rr-text-muted);
		transition: width 0.08s linear;
	}

	.gate-meter-fill.over {
		background: var(--rr-accent-violet);
	}

	.gate-marker {
		position: absolute;
		top: -4px;
		width: 2px;
		height: 16px;
		background: var(--rr-text-primary);
		pointer-events: none;
	}

	.gate-slider {
		position: absolute;
		inset: -8px 0;
		width: 100%;
		margin: 0;
		opacity: 0;
		cursor: ew-resize;
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
