# WebSocket DAT Callbacks for Reflective Resonance TouchDesigner client
# - Handles backend events:
#   - turn1.waves.ready
#   - dialogue.waves.ready
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

# How long to let each segment play (seconds).
# Tune these to your installation timing.
TURN1_PLAY_DURATION_S = 8.0
COMMENT_PLAY_DURATION_S = 3.5
RESPONDENT_PLAY_DURATION_S = 5.0
INTER_DIALOGUE_GAP_S = 1.0

# If True, stop the slot audio before playing a new clip on that slot
STOP_BEFORE_PLAY = True


# -----------------------------------------------------------------------------
# STATE (persists while the .toe is open)
# -----------------------------------------------------------------------------

_STATE = {
    "dialogue_queue": [],           # list of dialogue payload dicts
    "dialogue_running": False,      # whether we are currently sequencing playback
    "last_seq_by_session": {},      # sessionId -> last seq seen (basic dedupe)
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
    Turn 1: Load each agent's waves to their target physical slots, then play all.

    Event payload structure:
    {
        "slots": [
            {
                "slotId": 1,                    # Agent's logical slot
                "wave1PathAbs": "/path/...",    # Fundamental frequency
                "wave1TargetSlotId": 1,         # Physical slot for wave1
                "wave2PathAbs": "/path/...",    # 1st harmonic
                "wave2TargetSlotId": 2          # Physical slot for wave2
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

    # Load files for each agent's waves to their target physical slots
    for s in slots:
        wave1_path = s.get('wave1PathAbs')
        wave1_target = s.get('wave1TargetSlotId')
        wave2_path = s.get('wave2PathAbs')
        wave2_target = s.get('wave2TargetSlotId')

        # wave1 -> channel A of its target slot
        if wave1_path and wave1_target:
            _load_wave(int(wave1_target), 'A', wave1_path)

        # wave2 -> channel B of its target slot
        if wave2_path and wave2_target:
            _load_wave(int(wave2_target), 'B', wave2_path)

    # Start all at once
    _play_all_slots()

    # Optional: stop after duration (you can remove if you want loops)
    run("_stop_all_slots()", delaySeconds=TURN1_PLAY_DURATION_S, fromOP=me)


def _enqueue_dialogue(payload):
    _STATE["dialogue_queue"].append(payload)


def _ensure_dialogue_runner():
    if _STATE["dialogue_running"]:
        return
    _STATE["dialogue_running"] = True
    run("_run_next_dialogue()", delaySeconds=0.0, fromOP=me)


def _run_next_dialogue():
    """
    Pops one dialogue and schedules its playback. Called repeatedly until queue empty.

    Each dialogue step plays both wave1 (channel A) and wave2 (channel B)
    on their respective target slots.
    """
    if len(_STATE["dialogue_queue"]) == 0:
        _STATE["dialogue_running"] = False
        return

    dialogue = _STATE["dialogue_queue"].pop(0)

    commenters = dialogue.get('commenters', [])
    respondent = dialogue.get('respondent')

    # Safety check
    if not respondent or not respondent.get('wave1PathAbs'):
        debug('Dialogue missing respondent wave1PathAbs; skipping:', dialogue.get('dialogueId'))
        run("_run_next_dialogue()", delaySeconds=INTER_DIALOGUE_GAP_S, fromOP=me)
        return

    # Build playback steps: commenters then respondent
    # Each step: (role, wave1_target, wave1_path, wave2_target, wave2_path, duration)
    steps = []

    # Commenters: one by one
    for c in commenters:
        wave1_path = c.get('wave1PathAbs')
        wave1_target = c.get('wave1TargetSlotId')
        wave2_path = c.get('wave2PathAbs')
        wave2_target = c.get('wave2TargetSlotId')
        if not wave1_path:
            continue
        steps.append((
            "commenter",
            int(wave1_target) if wave1_target else None,
            wave1_path,
            int(wave2_target) if wave2_target else None,
            wave2_path,
            COMMENT_PLAY_DURATION_S
        ))

    # Respondent
    resp_wave1_path = respondent.get('wave1PathAbs')
    resp_wave1_target = respondent.get('wave1TargetSlotId')
    resp_wave2_path = respondent.get('wave2PathAbs')
    resp_wave2_target = respondent.get('wave2TargetSlotId')
    steps.append((
        "respondent",
        int(resp_wave1_target) if resp_wave1_target else None,
        resp_wave1_path,
        int(resp_wave2_target) if resp_wave2_target else None,
        resp_wave2_path,
        RESPONDENT_PLAY_DURATION_S
    ))

    # Schedule the sequence
    _play_steps_sequentially(steps, 0)


def _play_steps_sequentially(steps, idx):
    """
    Play steps[idx], then schedule next step.
    Each step has: (role, wave1_target, wave1_path, wave2_target, wave2_path, duration)

    Mapping:
        wave1 -> wave1_target's A channel
        wave2 -> wave2_target's B channel
    """
    if idx >= len(steps):
        # Dialogue done: small gap then next dialogue
        run("_run_next_dialogue()", delaySeconds=INTER_DIALOGUE_GAP_S, fromOP=me)
        return

    role, wave1_target, wave1_path, wave2_target, wave2_path, dur = steps[idx]

    # Play wave1 on target slot's A channel
    if wave1_path and wave1_target:
        _load_and_play_wave(wave1_target, 'A', wave1_path)

    # Play wave2 on target slot's B channel
    if wave2_path and wave2_target:
        _load_and_play_wave(wave2_target, 'B', wave2_path)

    # Schedule the next segment
    run(f"_play_steps_sequentially({repr(steps)}, {idx+1})", delaySeconds=float(dur), fromOP=me)


def _handle_dialogue(payload):
    """
    Dialogues are processed sequentially (queue).
    """
    _enqueue_dialogue(payload)
    _ensure_dialogue_runner()


def _handle_event_json(event_dict):
    if not _dedupe_event(event_dict):
        return

    evt_type = event_dict.get('type')
    payload = event_dict.get('payload', {}) or {}

    if evt_type == 'turn1.waves.ready':
        _handle_turn1(payload)
        return

    if evt_type == 'dialogue.waves.ready':
        _handle_dialogue(payload)
        return

    # Ignore unknown events
    # debug('Unknown event type:', evt_type)


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
    # Stop anything currently playing (optional)
    _stop_all_slots()
    _STATE["dialogue_queue"].clear()
    _STATE["dialogue_running"] = False
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
