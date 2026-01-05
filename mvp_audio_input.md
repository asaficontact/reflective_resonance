## MVP PRD: Audio Input (Push-to-Talk) + Speech-to-Text (ElevenLabs Scribe v1)

### Context (current system)
Reflective Resonance currently accepts **typed user input** from the frontend (`ChatDock`) and sends it to the backend `/v1/chat`, which runs a **3-turn multi-agent workflow** (Turn 1 response → Turn 2 comment → Turn 3 reply). The backend emits SSE events and generates WAV files via ElevenLabs TTS, storing artifacts under:
- `artifacts/tts/sessions/<session_id>/turn_1|turn_2|turn_3/*.wav`
- `artifacts/tts/sessions/<session_id>/session.json` (manifest)

### Goal (this PRD)
Replace the typed chatbox with a **press-and-hold push-to-talk** audio button that:
1) Records user speech locally in the browser while pressed
2) On release, uploads the recorded audio to backend STT
3) Backend transcribes the audio using **ElevenLabs Scribe v1** (single-shot, whole clip)
4) Backend stores audio + transcript to a **session directory**
5) Frontend receives transcript, then calls existing `/v1/chat` with that transcript (keeping current agent pipeline)

### References
- ElevenLabs Speech-to-Text API (Create transcript): `https://elevenlabs.io/docs/api-reference/speech-to-text/convert`
- ElevenLabs Speech-to-Text docs (Scribe models): `https://elevenlabs.io/docs/capabilities/speech-to-text`
- Current frontend chat input: `frontend/src/lib/components/ChatDock.svelte`
- Current backend workflow entrypoint: `backend/main.py` → `/v1/chat`
- Current backend workflow implementation: `backend/workflow.py`, `backend/sessions.py`, `backend/models.py`

---

## Product requirements

### Primary UX requirements (push-to-talk)
- **PTT interaction**: user **presses and holds** a large microphone button to speak.
  - On press: recording starts immediately.
  - On release: recording stops and upload/transcription starts.
- **Clear feedback** while recording:
  - Visual state change (glow / color shift) + timer (seconds recorded).
  - Optional: short “start” and “stop” sound cues (must be configurable, default off for gallery environments).
- **No always-on listening**.
- **No typed input field** in the default UI (audio button replaces `ChatDock`).

### Operational requirements (noisy environment, close mic)
- The environment is noisy but the user is close to the mic, and the UI is push-to-talk.
- Use browser capture constraints to improve intelligibility without heavy DSP:
  - `echoCancellation: true`
  - `noiseSuppression: true`
  - `autoGainControl: true`
- Add hard limits to reduce accidental long recordings:
  - **maxDurationSec** (default: 15s; configurable)
  - **minDurationMs** (default: 300ms; configurable)

### Data handling requirements
- Store the following per recording:
  - raw recorded audio file (as uploaded)
  - transcript text
  - timing + metadata (duration, mime type, upload timestamp)
- Store these in a deterministic **STT session directory** (separate from TTS sessions; see below).

---

## Functional specification

### Frontend: AudioInputDock component

#### Placement + design alignment
- Replace `<ChatDock onsubmit={handleSendMessage} />` in `frontend/src/routes/+page.svelte` with `<AudioInputDock ontranscript={handleSendMessage} />`.
- Style should follow existing dock conventions from `ChatDock.svelte`:
  - fixed at bottom, gradient background, centered max width
  - uses existing design tokens (`--rr-bg`, `--rr-accent-violet`, glow variables)
  - uses existing `Button` component (`$lib/components/ui/button`)

#### Interaction details (press-and-hold)
- Use **pointer events** (works across mouse + touch):
  - `pointerdown`: request mic permission if needed, start recording, call `setPointerCapture`.
  - `pointerup` / `pointercancel` / `lostpointercapture`: stop recording, finalize blob.
- Disable the button when:
  - no assigned slots
  - offline
  - already sending (`appStore.isSending`)
  - transcription in progress
- Show states:
  - idle: “Hold to talk”
  - recording: “Recording… (mm:ss)”
  - uploading: “Uploading…”
  - transcribing: “Transcribing…”
  - success: optional “Heard: <first 60 chars>”
  - error: toast + inline helper text

#### Recording method
- Use `MediaRecorder` over a `MediaStream` from `getUserMedia`.
- Preferred mime type order:
  - `audio/webm;codecs=opus`
  - `audio/ogg;codecs=opus`
  - fallback: `audio/webm` or browser default (as supported)
- Record with a small `timeslice` (e.g., 250ms) only if you need live UI meters; otherwise collect chunks until stop.

#### Client-side metadata
Capture and send:
- `mimeType`
- `durationMs` (measured by timestamps at start/stop)
- optional: `clientRecordedAt` timestamp

#### Frontend API call
After recording stops:
- POST audio blob to backend `/v1/stt` (multipart/form-data)
- Expect JSON response containing at minimum:
  - `sttSessionId`
  - `transcript` (string)
  - `audioPath` (relative path under artifacts for debug retrieval)
  - `transcriptPath` (relative path under artifacts for debug retrieval)
- On success, call existing flow:
  - `handleSendMessage(transcript)`

---

## Backend: Speech-to-Text (Scribe v1) API

### New endpoint: `POST /v1/stt`
**Purpose**: accept a single recorded audio clip, run Scribe v1 transcription, store artifacts, and return transcript.

#### Request (multipart/form-data)
- `file`: audio blob upload (required)
- optional form fields:
  - `language_code` (optional; default: auto or `eng` depending on ElevenLabs behavior)
  - `timestamp_granularity` (optional; default: none)
  - `sessionLabel` (optional; for debugging; e.g., “kiosk-1”)

#### Response (application/json)
Required fields:
- `sttSessionId: string` (UUID)
- `transcript: string`
- `audioPath: string` (relative path for retrieval via `/v1/audio/<audioPath>`)
- `transcriptPath: string` (relative path for retrieval via `/v1/audio/<transcriptPath>`)
- `durationMs: int`
- `mimeType: string`

Optional fields (nice-to-have):
- `words: [...]` if word timestamps are enabled
- `languageCode: string` if returned by provider
- `confidence: float` if returned by provider

#### Behavior requirements
- Validate audio size/duration:
  - Reject with `413` if file exceeds max size
  - Reject with `422` if duration < minDurationMs (if duration is provided)
- On ElevenLabs STT errors:
  - Return `502` with a safe error message
  - Log provider status code and request id (if available)

### ElevenLabs integration requirements
- Use Scribe v1 “create transcript” endpoint from docs: `https://elevenlabs.io/docs/api-reference/speech-to-text/convert`
- Required model selection:
  - `model_id = "scribe_v1"`
- Upload audio as provided by client; if the provider rejects the mime/container, backend may need to:
  - either transcode to a supported format (future enhancement)
  - or return a clear 415/422 with guidance (MVP acceptable)

---

## Storage: STT session directory

### Directory layout
Store each recording under:
- `artifacts/stt/sessions/<stt_session_id>/`
  - `input.<ext>` (original upload, extension based on mime type)
  - `transcript.json` (full provider response, redacted if needed)
  - `transcript.txt` (plain transcript string)
  - `metadata.json` (mime type, durationMs, createdAt, userAgent optional)

### Retention policy (MVP)
- Default keep for development: retain indefinitely.
- Production setting: configurable retention days; optionally delete raw audio but keep transcript + metadata.

---

## Integration with existing `/v1/chat` flow

### Required behavior
- Frontend calls `/v1/chat` with:
  - `message = transcript` (from `/v1/stt`)
  - `slots = currently assigned slots`
- No changes required to the `/v1/chat` contract for MVP.

### Optional future improvement (not required for MVP)
Allow `/v1/chat` to accept an `inputSessionId` to link STT session ↔ TTS session for a single “super session”.

---

## Error handling + edge cases

### Microphone permission denied
- Show a toast: “Microphone permission is required.”
- Provide a “Retry permission” action (re-click button).

### User releases too quickly / silent input
- If duration < min threshold or STT returns empty transcript:
  - show “Didn’t catch that—try again.”
  - do not call `/v1/chat`

### Offline / network failures
- Reuse existing offline handling in app (`appStore.isOnline`).
- If upload fails: show toast “Network error uploading audio.”

### Concurrency
- Only one recording/transcription in progress at a time.
- If an SSE workflow is currently running (`appStore.isSending`), disable PTT.

---

## Security + privacy
- Microphone is only accessed during press-and-hold.
- Audio uploads are sent over HTTPS in production.
- STT artifacts are stored on server disk; ensure `artifacts/stt/` is:
  - excluded by `.gitignore`
  - served only if you explicitly want debug retrieval (see note below)

**Important**: current backend serves `artifacts/` via `/v1/audio` StaticFiles. If you keep that behavior, STT transcripts/audio under `artifacts/stt/` will also be retrievable. For MVP debugging this is helpful; for production you may want to restrict what is served.

---

## Observability
Log per STT request:
- sttSessionId
- mimeType + sizeBytes + durationMs
- provider model_id (scribe_v1)
- transcription latency (ms)
- transcript length (chars)

---

## Testing plan / acceptance criteria

### Frontend acceptance criteria
- AC-F1: Holding the mic button records; releasing stops.
- AC-F2: UI shows recording state + timer; shows uploading/transcribing states.
- AC-F3: On successful transcription, the transcript is sent to `/v1/chat` and the existing SSE workflow runs normally.

### Backend acceptance criteria
- AC-B1: `/v1/stt` returns a transcript for a valid audio upload.
- AC-B2: A new `artifacts/stt/sessions/<uuid>/` directory is created containing input + transcript files.
- AC-B3: Error cases return appropriate HTTP codes and do not crash the server.

### End-to-end acceptance criteria
- AC-E2E1: A user can complete: press-to-talk → transcript → 3-turn workflow → TTS WAV outputs.


