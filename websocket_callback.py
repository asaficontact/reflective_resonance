# WebSocket DAT Callbacks for Reflective Resonance TouchDesigner client
# - Handles backend events:
#   - turn1.waves.ready
#   - dialogue.waves.ready
#   - final_summary.ready
#
# Docs reference: https://docs.derivative.ca/WebSocket_DAT
#
# Slot Mapping:
#   Each physical slot (1-6) has TWO audio operators (A and B).
#   - Channel A: receives wave1 (fundamental frequency)
#   - Channel B: receives wave2 (1st harmonic)
#
#   This allows adjacent agents to share physical slots:
#   Agent 1: wave1→slot1A, wave2→slot2B
#   Agent 2: wave1→slot2A, wave2→slot3B
#   ...
#   Agent 6: wave1→slot6A, wave2→slot1B (wraps around)

import json
import time

# -----------------------------------------------------------------------------
# CONFIG (edit these)
# -----------------------------------------------------------------------------

# Map (slotId, channel) -> OP path
# Each physical slot 1-6 has an A channel (wave1) and B channel (wave2)
# Replace placeholders with your actual Audio File In CHOP operator paths
SLOT_AUDIO_OPS = {
    # Slot 1
    (1, 'A'): op('slot1A_audio'),  # wave1 for slot 1
    (1, 'B'): op('slot1B_audio'),  # wave2 for slot 1
    # Slot 2
    (2, 'A'): op('slot2A_audio'),
    (2, 'B'): op('slot2B_audio'),
    # Slot 3
    (3, 'A'): op('slot3A_audio'),
    (3, 'B'): op('slot3B_audio'),
    # Slot 4
    (4, 'A'): op('slot4A_audio'),
    (4, 'B'): op('slot4B_audio'),
    # Slot 5
    (5, 'A'): op('slot5A_audio'),
    (5, 'B'): op('slot5B_audio'),
    # Slot 6
    (6, 'A'): op('slot6A_audio'),
    (6, 'B'): op('slot6B_audio'),
}

# Duration is now provided by backend in event payloads (durationMs field).
# These fallback values are only used if durationMs is missing.
FALLBACK_TURN1_DURATION_MS = 8000.0
FALLBACK_COMMENT_DURATION_MS = 3500.0
FALLBACK_RESPONDENT_DURATION_MS = 5000.0
INTER_DIALOGUE_GAP_S = 0.5  # Small gap between dialogues (0.5s)

# If True, stop the slot audio before playing a new clip on that slot
STOP_BEFORE_PLAY = True

# Sentiment effect mappings - customize for your installation
# These define loading effect parameters based on user mood
SENTIMENT_EFFECTS = {
    'positive': {'color': (0.2, 0.8, 0.4), 'intensity': 1.2},
    'neutral':  {'color': (0.5, 0.5, 0.8), 'intensity': 1.0},
    'negative': {'color': (0.8, 0.3, 0.3), 'intensity': 0.8},
}

# Sentiment audio paths - played on slots 1A-6A until Turn 1 arrives
# Replace these placeholder paths with actual wave files
SENTIMENT_AUDIO_PATHS = {
    'positive': '/path/to/sentiment_positive.wav',
    'neutral':  '/path/to/sentiment_neutral.wav',
    'negative': '/path/to/sentiment_negative.wav',
}


# -----------------------------------------------------------------------------
# STATE (persists while the .toe is open)
# -----------------------------------------------------------------------------

_STATE = {
    "dialogue_queue": [],           # list of dialogue payload dicts
    "dialogue_running": False,      # whether we are currently sequencing playback
    "last_seq_by_session": {},      # sessionId -> last seq seen (basic dedupe)
    "pending_summary": None,        # final_summary payload waiting for dialogues to finish
    "turn1_playing": False,         # True while Turn 1 audio is playing
    "original_summary_volume": None,  # Saved volume before summary (to restore after)
}


# -----------------------------------------------------------------------------
# AUDIO CONTROL HELPERS
# -----------------------------------------------------------------------------

def _get_audio_op(slot_id, channel):
    """
    Get audio operator for a slot and channel.

    Args:
        slot_id: Physical slot ID (1-6)
        channel: 'A' for wave1 or 'B' for wave2

    Returns:
        The audio operator or None if not found
    """
    return SLOT_AUDIO_OPS.get((slot_id, channel))


def _set_audio_file(audio_op, abs_path):
    """
    Set the file path on your audio operator.
    Adjust this function to match your operator type.
    Common patterns:
      - Audio File In CHOP: audio_op.par.file = abs_path
      - Audio Movie In CHOP: audio_op.par.file = abs_path
    """
    if audio_op is None:
        return

    # Try common parameter names
    if hasattr(audio_op, 'par') and hasattr(audio_op.par, 'file'):
        audio_op.par.file = abs_path
        return

    # Fallback: some ops use "filepath" or similar
    if hasattr(audio_op, 'par') and hasattr(audio_op.par, 'filepath'):
        audio_op.par.filepath = abs_path
        return

    debug('No recognized file parameter on op:', audio_op.path if audio_op else 'None')


def _stop_audio(audio_op):
    """
    Stop playback on your audio operator.
    Adjust as needed.
    """
    if audio_op is None:
        return

    if hasattr(audio_op, 'par') and hasattr(audio_op.par, 'play'):
        try:
            audio_op.par.play = 0
        except:
            pass

    # Some ops support a pulse parameter to cue/stop
    if hasattr(audio_op, 'par') and hasattr(audio_op.par, 'stop'):
        try:
            audio_op.par.stop.pulse()
        except:
            pass


def _play_audio(audio_op):
    """
    Start playback on your audio operator.
    Adjust as needed.
    Common patterns:
      - audio_op.par.play = 1
      - audio_op.par.cuepulse.pulse()
    """
    if audio_op is None:
        return

    if hasattr(audio_op, 'par') and hasattr(audio_op.par, 'cuepulse'):
        try:
            audio_op.par.cuepulse.pulse()
        except:
            pass

    if hasattr(audio_op, 'par') and hasattr(audio_op.par, 'play'):
        try:
            audio_op.par.play = 1
        except:
            pass


def _load_wave(slot_id, channel, abs_path):
    """
    Load a wave file to a specific slot and channel (without playing).

    Args:
        slot_id: Physical slot ID (1-6)
        channel: 'A' for wave1 or 'B' for wave2
        abs_path: Absolute path to the wave file
    """
    audio_op = _get_audio_op(slot_id, channel)
    if audio_op is None:
        debug(f'Missing audio op for slot {slot_id}{channel}')
        return

    if STOP_BEFORE_PLAY:
        _stop_audio(audio_op)

    _set_audio_file(audio_op, abs_path)


def _load_and_play_wave(slot_id, channel, abs_path):
    """
    Load a wave file and start playback.

    Args:
        slot_id: Physical slot ID (1-6)
        channel: 'A' for wave1 or 'B' for wave2
        abs_path: Absolute path to the wave file
    """
    audio_op = _get_audio_op(slot_id, channel)
    if audio_op is None:
        debug(f'Missing audio op for slot {slot_id}{channel}')
        return

    if STOP_BEFORE_PLAY:
        _stop_audio(audio_op)

    _set_audio_file(audio_op, abs_path)
    _play_audio(audio_op)


def _play_all_slots():
    """Start playback on all audio operators."""
    for (slot_id, channel), audio_op in SLOT_AUDIO_OPS.items():
        if audio_op is None:
            continue
        _play_audio(audio_op)


def _stop_all_slots():
    """Stop playback on all audio operators."""
    for (slot_id, channel), audio_op in SLOT_AUDIO_OPS.items():
        if audio_op is None:
            continue
        _stop_audio(audio_op)


# -----------------------------------------------------------------------------
# EVENT HANDLING
# -----------------------------------------------------------------------------

def _handle_user_sentiment(payload):
    """
    Handle user_sentiment event - play sentiment audio and show loading effect.
    Called BEFORE turn1.waves.ready, enabling anticipatory audio/visuals.

    Plays sentiment audio on slots 1A-6A until Turn 1 arrives and takes over.

    Event payload structure:
    {
        "sentiment": "positive" | "neutral" | "negative",
        "justification": "Brief explanation..."
    }
    """
    sentiment = payload.get('sentiment', 'neutral')
    justification = payload.get('justification', '')

    debug(f'>>> USER SENTIMENT: {sentiment} - {justification}')

    # Get audio path for this sentiment
    audio_path = SENTIMENT_AUDIO_PATHS.get(sentiment, SENTIMENT_AUDIO_PATHS['neutral'])

    debug(f'  Playing sentiment audio on slots 1A-6A: {audio_path}')

    # Load and play the same audio on all 6 slots (A channel only)
    for slot_id in range(1, 7):
        _load_and_play_wave(slot_id, 'A', audio_path)

    debug(f'  Sentiment audio playing (will stop when Turn 1 arrives)')

    # Optional: Update visual effects based on sentiment
    effect = SENTIMENT_EFFECTS.get(sentiment, SENTIMENT_EFFECTS['neutral'])
    color = effect['color']
    intensity = effect['intensity']

    # Example: Update TouchDesigner parameters
    # Uncomment and modify these lines to match your network:
    #
    # # Set loading effect color
    # if op('sentiment_color'):
    #     op('sentiment_color').par.value0r = color[0]
    #     op('sentiment_color').par.value0g = color[1]
    #     op('sentiment_color').par.value0b = color[2]
    #
    # # Set intensity
    # if op('loading_intensity'):
    #     op('loading_intensity').par.value0 = intensity
    #
    # # Trigger loading animation
    # if op('loading_trigger'):
    #     op('loading_trigger').par.start.pulse()


def _dedupe_event(event_dict):
    """
    Deduplicate per session based on seq. Returns True if this event is new.
    """
    session_id = event_dict.get('sessionId')
    seq = event_dict.get('seq')

    if not session_id or seq is None:
        return True

    last = _STATE["last_seq_by_session"].get(session_id, 0)
    if seq <= last:
        return False

    _STATE["last_seq_by_session"][session_id] = seq
    return True


def _handle_turn1(payload):
    """
    Turn 1: Play each agent's waves SEQUENTIALLY from slot 1 to slot 6.

    Event payload structure:
    {
        "slots": [
            {
                "slotId": 1,                    # Agent's logical slot
                "wave1PathAbs": "/path/...",    # Fundamental frequency
                "wave1TargetSlotId": 1,         # Physical slot for wave1
                "wave2PathAbs": "/path/...",    # 1st harmonic
                "wave2TargetSlotId": 2,         # Physical slot for wave2
                "durationMs": 8500.0            # Actual audio duration in ms
            },
            ...
        ]
    }

    Mapping:
        wave1 -> target slot's A channel
        wave2 -> target slot's B channel
    """
    slots = payload.get('slots', [])
    if not slots:
        debug('turn1.waves.ready payload has no slots')
        return

    slot_count = len(slots)
    debug(f'>>> TURN 1 START: {slot_count} slots (sequential playback)')

    # Sort slots by slotId to ensure order 1, 2, 3, 4, 5, 6
    sorted_slots = sorted(slots, key=lambda s: s.get('slotId', 0))

    # Build steps list: (slot_id, wave1_target, wave1_path, wave2_target, wave2_path, duration_ms)
    steps = []
    for s in sorted_slots:
        slot_id = s.get('slotId')
        wave1_path = s.get('wave1PathAbs')
        wave1_target = s.get('wave1TargetSlotId')
        wave2_path = s.get('wave2PathAbs')
        wave2_target = s.get('wave2TargetSlotId')
        duration_ms = s.get('durationMs', FALLBACK_TURN1_DURATION_MS)

        debug(f'  Turn1 slot {slot_id}: duration={duration_ms:.0f}ms, wave1->{wave1_target}A, wave2->{wave2_target}B')

        steps.append((
            slot_id,
            int(wave1_target) if wave1_target else None,
            wave1_path,
            int(wave2_target) if wave2_target else None,
            wave2_path,
            duration_ms
        ))

    # Mark Turn 1 as playing
    _STATE["turn1_playing"] = True

    # Start sequential playback
    _play_turn1_sequentially(steps, 0)


def _play_turn1_sequentially(steps, idx):
    """
    Play Turn 1 slots one at a time.
    Each step: (slot_id, wave1_target, wave1_path, wave2_target, wave2_path, duration_ms)
    """
    if idx >= len(steps):
        # All Turn 1 slots done
        _on_turn1_complete()
        return

    slot_id, wave1_target, wave1_path, wave2_target, wave2_path, duration_ms = steps[idx]

    debug(f'>>> TURN 1 SLOT {slot_id} PLAYING ({idx+1}/{len(steps)}): duration={duration_ms:.0f}ms')

    # Load and play wave1 on target slot's A channel
    if wave1_path and wave1_target:
        _load_and_play_wave(wave1_target, 'A', wave1_path)

    # Load and play wave2 on target slot's B channel
    if wave2_path and wave2_target:
        _load_and_play_wave(wave2_target, 'B', wave2_path)

    # Schedule next slot after this one finishes (+ small buffer)
    next_delay_ms = int(duration_ms + 200)
    run(f"_play_turn1_sequentially({repr(steps)}, {idx+1})", delayMilliSeconds=next_delay_ms, fromOP=me)


def _on_turn1_complete():
    """Called when Turn 1 playback finishes."""
    _STATE["turn1_playing"] = False
    debug('>>> TURN 1 COMPLETE')

    # If dialogues are queued, start them now
    if len(_STATE["dialogue_queue"]) > 0 and not _STATE["dialogue_running"]:
        debug('>>> Starting queued dialogues')
        _ensure_dialogue_runner()


def _enqueue_dialogue(payload):
    _STATE["dialogue_queue"].append(payload)


def _ensure_dialogue_runner():
    # Don't start if dialogues already running
    if _STATE["dialogue_running"]:
        return
    # Don't start if Turn 1 is still playing - will be started by _on_turn1_complete()
    if _STATE["turn1_playing"]:
        debug('  (dialogues queued, waiting for Turn 1 to complete)')
        return
    _STATE["dialogue_running"] = True
    run("_run_next_dialogue()", delayMilliSeconds=0, fromOP=me)


def _run_next_dialogue():
    """
    Pops one dialogue and schedules its playback. Called repeatedly until queue empty.

    Each dialogue step plays both wave1 (channel A) and wave2 (channel B)
    on their respective target slots.
    """
    if len(_STATE["dialogue_queue"]) == 0:
        _STATE["dialogue_running"] = False
        debug('>>> ALL DIALOGUES COMPLETE')

        # Check if there's a pending summary to play
        if _STATE["pending_summary"] is not None:
            debug('>>> Playing queued final summary')
            # Small delay before summary starts (payload read by _play_final_summary_now)
            run("_play_final_summary_now()", delayMilliSeconds=500, fromOP=me)
        return

    dialogue = _STATE["dialogue_queue"].pop(0)
    dialogue_id = dialogue.get('dialogueId', 'unknown')
    remaining = len(_STATE["dialogue_queue"])

    commenters = dialogue.get('commenters', [])
    respondent = dialogue.get('respondent')

    debug(f'>>> DIALOGUE START: {dialogue_id} ({remaining} remaining in queue)')

    # Safety check
    if not respondent or not respondent.get('wave1PathAbs'):
        debug(f'  Dialogue {dialogue_id} missing respondent wave1PathAbs; skipping')
        run("_run_next_dialogue()", delayMilliSeconds=int(INTER_DIALOGUE_GAP_S * 1000), fromOP=me)
        return

    # Build playback steps: commenters then respondent
    # Each step: (role, slot_id, wave1_target, wave1_path, wave2_target, wave2_path, duration_s)
    steps = []

    # Commenters: one by one (use durationMs from payload, convert to seconds)
    for c in commenters:
        slot_id = c.get('slotId')
        wave1_path = c.get('wave1PathAbs')
        wave1_target = c.get('wave1TargetSlotId')
        wave2_path = c.get('wave2PathAbs')
        wave2_target = c.get('wave2TargetSlotId')
        duration_ms = c.get('durationMs', FALLBACK_COMMENT_DURATION_MS)
        if not wave1_path:
            continue
        steps.append((
            "commenter",
            slot_id,
            int(wave1_target) if wave1_target else None,
            wave1_path,
            int(wave2_target) if wave2_target else None,
            wave2_path,
            (duration_ms + 200) / 1000.0  # Convert to seconds with small buffer
        ))

    # Respondent (use durationMs from payload, convert to seconds)
    resp_slot_id = respondent.get('slotId')
    resp_wave1_path = respondent.get('wave1PathAbs')
    resp_wave1_target = respondent.get('wave1TargetSlotId')
    resp_wave2_path = respondent.get('wave2PathAbs')
    resp_wave2_target = respondent.get('wave2TargetSlotId')
    resp_duration_ms = respondent.get('durationMs', FALLBACK_RESPONDENT_DURATION_MS)
    steps.append((
        "respondent",
        resp_slot_id,
        int(resp_wave1_target) if resp_wave1_target else None,
        resp_wave1_path,
        int(resp_wave2_target) if resp_wave2_target else None,
        resp_wave2_path,
        (resp_duration_ms + 200) / 1000.0  # Convert to seconds with small buffer
    ))

    debug(f'  Dialogue {dialogue_id}: {len(commenters)} commenters + 1 respondent = {len(steps)} steps')

    # Schedule the sequence (pass dialogue_id for logging)
    _play_steps_sequentially(steps, 0, dialogue_id)


def _play_steps_sequentially(steps, idx, dialogue_id=''):
    """
    Play steps[idx], then schedule next step.
    Each step has: (role, slot_id, wave1_target, wave1_path, wave2_target, wave2_path, duration)

    Mapping:
        wave1 -> wave1_target's A channel
        wave2 -> wave2_target's B channel
    """
    if idx >= len(steps):
        # Dialogue done: small gap then next dialogue
        debug(f'  Dialogue {dialogue_id} COMPLETE, next in {INTER_DIALOGUE_GAP_S}s')
        run("_run_next_dialogue()", delayMilliSeconds=int(INTER_DIALOGUE_GAP_S * 1000), fromOP=me)
        return

    role, slot_id, wave1_target, wave1_path, wave2_target, wave2_path, dur = steps[idx]

    debug(f'  [{dialogue_id}] Step {idx+1}/{len(steps)}: {role} slot{slot_id} -> {wave1_target}A/{wave2_target}B, dur={dur:.1f}s')

    # Play wave1 on target slot's A channel
    if wave1_path and wave1_target:
        _load_and_play_wave(wave1_target, 'A', wave1_path)

    # Play wave2 on target slot's B channel
    if wave2_path and wave2_target:
        _load_and_play_wave(wave2_target, 'B', wave2_path)

    # Schedule the next segment
    run(f"_play_steps_sequentially({repr(steps)}, {idx+1}, {repr(dialogue_id)})", delayMilliSeconds=int(dur * 1000), fromOP=me)


def _handle_dialogue(payload):
    """
    Dialogues are processed sequentially (queue).
    """
    dialogue_id = payload.get('dialogueId', 'unknown')
    queue_len = len(_STATE["dialogue_queue"])
    debug(f'>>> DIALOGUE RECEIVED: {dialogue_id} (queue size before: {queue_len})')
    _enqueue_dialogue(payload)
    _ensure_dialogue_runner()


def _handle_final_summary(payload):
    """
    Final Summary (Turn 4): Load 6 waves to slots 1A-6A and play all.
    If dialogues are still running, queue the summary to play after they finish.

    Event payload structure:
    {
        "status": "complete" | "failed",
        "text": "Summary text...",
        "waveInfo": {
            "voiceProfile": "voice_name",
            "waves": [
                {"slotId": 1, "wavePathAbs": "/path/...", "wavePathRel": "...", "durationMs": 2500.0},
                {"slotId": 2, "wavePathAbs": "/path/...", "wavePathRel": "...", "durationMs": 2500.0},
                ...
            ]
        }
    }

    Summary waves play on the A channel only (no B channel usage).
    """
    # Store the payload
    _STATE["pending_summary"] = payload

    # If dialogues are running or queued, wait for them to finish
    if _STATE["dialogue_running"] or len(_STATE["dialogue_queue"]) > 0:
        debug(f'>>> FINAL SUMMARY QUEUED (dialogues still running)')
        return

    # No dialogues running, play immediately
    _play_final_summary_now()


def _play_final_summary_now():
    """Actually play the final summary (called when ready)."""
    payload = _STATE["pending_summary"]
    if payload is None:
        debug('>>> FINAL SUMMARY: No pending payload')
        return

    _STATE["pending_summary"] = None

    debug('>>> FINAL SUMMARY START')

    status = payload.get('status')
    if status != 'complete':
        debug(f'  final_summary.ready status is not complete: {status}')
        return

    wave_info = payload.get('waveInfo')
    if not wave_info:
        debug('  final_summary.ready missing waveInfo')
        return

    waves = wave_info.get('waves', [])
    if not waves:
        debug('  final_summary.ready has no waves')
        return

    # Double the volume for summary playback
    if op('audiodevout7'):
        current_vol = op('audiodevout7').par.volume.eval()
        _STATE["original_summary_volume"] = current_vol
        op('audiodevout7').par.volume = current_vol * 2
        debug(f'  audiodevout7 volume: {current_vol} -> {current_vol * 2}')

    max_duration_ms = 0.0

    debug(f'  Loading {len(waves)} waves to slots 1A-6A')

    # Load each wave to its target slot's A channel
    for w in waves:
        slot_id = w.get('slotId')
        wave_path = w.get('wavePathAbs')
        duration_ms = w.get('durationMs', 3000.0)

        max_duration_ms = max(max_duration_ms, duration_ms)

        debug(f'    Slot {slot_id}A: duration={duration_ms:.0f}ms')

        if slot_id and wave_path:
            _load_wave(int(slot_id), 'A', wave_path)

    # Start all at once
    _play_all_slots()

    debug(f'>>> FINAL SUMMARY PLAYING: max_duration={max_duration_ms:.0f}ms')

    # Stop and restore volume after longest audio + buffer
    stop_delay_ms = int(max_duration_ms + 500)
    run("_on_summary_complete()", delayMilliSeconds=stop_delay_ms, fromOP=me)


def _on_summary_complete():
    """Called when summary playback finishes. Stops audio and restores volume."""
    _stop_all_slots()

    # Restore original volume
    if op('audiodevout7') and _STATE["original_summary_volume"] is not None:
        original_vol = _STATE["original_summary_volume"]
        op('audiodevout7').par.volume = original_vol
        debug(f'>>> FINAL SUMMARY COMPLETE: audiodevout7 volume restored to {original_vol}')
        _STATE["original_summary_volume"] = None
    else:
        debug('>>> FINAL SUMMARY COMPLETE')


def _handle_event_json(event_dict):
    if not _dedupe_event(event_dict):
        return

    evt_type = event_dict.get('type')
    session_id = event_dict.get('sessionId', '')[:8]  # First 8 chars of session
    seq = event_dict.get('seq', 0)
    payload = event_dict.get('payload', {}) or {}

    debug(f'EVENT [{session_id}] seq={seq}: {evt_type}')

    if evt_type == 'user_sentiment':
        _handle_user_sentiment(payload)
        return

    if evt_type == 'turn1.waves.ready':
        _handle_turn1(payload)
        return

    if evt_type == 'dialogue.waves.ready':
        _handle_dialogue(payload)
        return

    if evt_type == 'final_summary.ready':
        _handle_final_summary(payload)
        return

    # Ignore unknown events (but log them now for debugging)
    debug(f'  (unknown event type, ignoring)')


# -----------------------------------------------------------------------------
# WEBSOCKET DAT CALLBACKS
# -----------------------------------------------------------------------------
# Different TouchDesigner builds expose different callback names/signatures.
# We implement the common ones and route to the same handler.
# Docs: https://docs.derivative.ca/WebSocket_DAT

def onConnect(dat, client=None):
    debug('WebSocket connected', client)
    # Optional: say hello to server (if your backend supports it)
    try:
        dat.sendText(json.dumps({"type":"hello","client":"touchdesigner"}))
    except:
        pass
    return


def onDisconnect(dat, client=None):
    debug('WebSocket disconnected', client)
    # NOTE: Don't clear playback state on disconnect!
    # Events are already received and playback should continue.
    # The backend often disconnects after sending all events.
    # Only clear deduplication state for the next connection.
    # _STATE["last_seq_by_session"] could be cleared here if needed
    return


# Variant A: some builds call this
def onReceiveText(dat, rowIndex, message, bytes=None, peer=None):
    try:
        event_dict = json.loads(message)
    except Exception as e:
        debug('Invalid JSON:', e, message[:200])
        return

    _handle_event_json(event_dict)
    return


# Variant B: some builds call this name
def onWebSocketReceiveText(dat, rowIndex, message, client=None):
    try:
        event_dict = json.loads(message)
    except Exception as e:
        debug('Invalid JSON:', e, message[:200])
        return

    _handle_event_json(event_dict)
    return


def onReceiveBinary(dat, rowIndex, message, bytes=None, peer=None):
    # Not used (server sends JSON text)
    return


def onError(dat, error, client=None):
    debug('WebSocket error:', error, client)
    return
