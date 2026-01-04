## MVP PRD: Multi-Voice TTS for 6 Agents (ElevenLabs)

### Context
Reflective Resonance currently runs **6 parallel LLM agents** (mapped to 6 “slots/speakers”) and streams their responses to the frontend via **SSE** (`/v1/chat`) as:
- `slot.start`
- `slot.token`
- `slot.done` (includes `fullContent`)
- `slot.error`
- `done`

Goal of this PRD: add **text-to-speech (TTS)** using **ElevenLabs** so each agent’s response is converted into audio using one of **6 curated voice profiles** defined in `eleven_labs_voice_profiles.md`.

This PRD is split into two implementation phases to allow incremental delivery and testing.

### References (docs + repo)
- **ElevenLabs API: Create speech**: `https://elevenlabs.io/docs/api-reference/text-to-speech/convert`
- **ElevenLabs TTS product guide (voice settings behavior)**: `https://elevenlabs.io/docs/creative-platform/playground/text-to-speech`
- **Current voice plan**: `eleven_labs_voice_profiles.md`
- **System architecture guide**: `rawagents_for_reflective_resonance.md`
- **Current backend SSE streaming**: `backend/streaming.py`, `backend/main.py`, `backend/models.py`
- **Current frontend SSE client**: `frontend/src/lib/utils/streaming.ts`, `frontend/src/routes/+page.svelte`

---

## Goals / Non-goals

### Goals
- Provide a backend module **`MultiVoiceAgentTTS`** that:
  - loads 6 voice profiles (voice id + model id + voice settings)
  - calls ElevenLabs TTS to generate audio
  - writes **`.wav` files** to disk in a predictable folder structure
  - supports a **fallback voice** if an invalid profile is selected
- Update the 6 agents so their final output is **structured JSON**:

```json
{ "text": "...", "voice_profile": "friendly_casual" }
```

- Connect structured agent outputs → `MultiVoiceAgentTTS` to generate audio per slot/agent response.

### Non-goals (for this MVP PRD)
- Voice input (STT) pipeline.
- TouchDesigner/OSC integration (beyond leaving clean hooks).
- Fine-grained SSML markup or phoneme dictionaries.
- Training / cloning new voices (we use existing voice IDs initially).

---

## ElevenLabs “correct usage” notes (verification)

### Output audio formats (important for WAV)
ElevenLabs “Create speech” supports `output_format` values including:
- MP3 variants (e.g. `mp3_44100_128`)
- PCM variants (e.g. `pcm_44100`, `pcm_48000`, etc.)
- `ulaw_8000`, `alaw_8000`
- Opus variants (e.g. `opus_48000_64`)

**MVP requirement is `.wav` output**:
- ElevenLabs returns **raw PCM** when using `output_format=pcm_44100` (or another PCM rate).
- A `.wav` file is typically **PCM + a WAV container header**.
- Implementation expectation: request **PCM** from ElevenLabs and wrap it with a WAV header before writing to `.wav`.

### `voice_settings` keys (what must be supported)
Per ElevenLabs API docs, `voice_settings` includes (at minimum):
- `stability`
- `similarity_boost`
- `style`
- `use_speaker_boost`

### About `speed`
The ElevenLabs product guide discusses a **Speed** setting in the UI, but the API reference does not consistently surface `speed` in the same `voice_settings` schema.

**Requirement for MVP**:
- Treat `speed` as **“verify-in-SDK”**:
  - If the installed ElevenLabs Python SDK supports `speed` for TTS requests, include it.
  - If not supported, exclude it from requests (and consider speed tuning as Phase 2.5 or a follow-up).

---

## Voice Profiles (source of truth)

### Source file
Voice profile definitions currently live in `eleven_labs_voice_profiles.md` and include:
- 6 profiles
- voice ids
- proposed settings per profile
- a `MultiVoiceAgentTTS` example implementation

### Required validation checks (before Phase 1 is considered “done”)
- Voice IDs are valid and usable for the account (some voices may require being in the account’s voice list).
- Requested `model_id` is supported for the account tier and region.
- `voice_settings` keys match the SDK/API expected names:
  - `stability`, `similarity_boost`, `style`, `use_speaker_boost` (and `speed` only if supported).
- Naming consistency:
  - Ensure the “voice_name” used in docs matches the voice id (avoid “Bella vs Sarah” mismatches).

---

## Phase 1 — Setup `MultiVoiceAgentTTS` (voice profiles + WAV generation)

### Objective
Implement a backend TTS module that can generate `.wav` files for each of the 6 voice profiles **from sample input text** (no agent integration yet).

### Deliverables

#### D1. Backend module structure (recommended)
Add a new backend package:
- `backend/tts/`
  - `profiles.py`: defines voice profiles and settings (loaded from constants)
  - `elevenlabs_tts.py`: thin wrapper around ElevenLabs client calls
  - `wav.py`: helper to wrap raw PCM bytes into WAV container bytes
  - `multi_voice_agent_tts.py`: `MultiVoiceAgentTTS` public API
  - `demo.py` (or `scripts/tts_demo.py`): generates 6 wav files from sample text

This is a recommendation for implementation clarity; backend team may adjust file naming, but should preserve the responsibilities.

#### D2. Configuration
Add configuration support for ElevenLabs:
- **Env var**: `ELEVENLABS_API_KEY` (or `RR_ELEVENLABS_API_KEY`, but choose one and standardize)
- **Config surface**: `backend/config.py` should expose a setting for the key (and optionally default model id)

#### D3. Voice profiles (MVP requirements)
Voice profile object must include:
- `profile_name`: one of:
  - `friendly_casual`
  - `warm_professional`
  - `energetic_upbeat`
  - `calm_soothing`
  - `confident_charming`
  - `playful_expressive`
- `voice_id`: ElevenLabs voice id string
- `model_id`: default model for that profile
- `voice_settings`:
  - required: `stability`, `similarity_boost`, `style`, `use_speaker_boost`
  - optional: `speed` (only if SDK supports)
- `output_format` for Phase 1 test: **default to `pcm_44100`** (for WAV writing)

#### D4. WAV output folder layout
Write files to a deterministic folder.

Recommended:
- `artifacts/tts/phase1/`
  - `friendly_casual.wav`
  - `warm_professional.wav`
  - `energetic_upbeat.wav`
  - `calm_soothing.wav`
  - `confident_charming.wav`
  - `playful_expressive.wav`

#### D5. Phase 1 demo/test command
Provide a simple command to generate all 6 wav files.

Acceptance test requirements:
- The script runs with only `ELEVENLABS_API_KEY` configured.
- It produces exactly 6 `.wav` files in the output directory.
- Files are playable by a standard audio player (valid WAV container).
- Logs clearly show:
  - which profile is being generated
  - selected `voice_id`, `model_id`, `output_format`
  - output path

### Functional requirements
- **FR1**: `MultiVoiceAgentTTS.generate_wav(text: str, profile_name: str) -> bytes`
- **FR2**: `MultiVoiceAgentTTS.generate_wav_to_file(text: str, profile_name: str, path: Path) -> Path`
- **FR3**: `MultiVoiceAgentTTS.list_profiles() -> list[str]`
- **FR4**: Fallback voice behavior:
  - If `profile_name` invalid → use fallback profile (configurable; default `friendly_casual`)

### Non-functional requirements
- **NFR1**: Fail fast if API key is missing
- **NFR2**: Clear error messaging on:
  - invalid voice id
  - invalid model id
  - 401/403 auth errors
  - rate limits
- **NFR3**: Logging must never print the API key

### Dependencies
- Add ElevenLabs SDK dependency to Python project (backend team will pick version).
- No additional audio libs required if WAV header is manually written; otherwise backend team may use a lightweight WAV utility library.

### Phase 1 Acceptance Criteria
- AC1: Running the demo produces 6 valid `.wav` files.
- AC2: Each output is audibly distinct (different voice identity).
- AC3: Invalid profile name triggers fallback voice without crashing.

---

## Phase 2 — Agents output structured JSON and drive `MultiVoiceAgentTTS`

### Objective
Update the existing 6-agent system so each slot’s final output includes:
- `text`: the spoken response
- `voice_profile`: one of the 6 profiles

Then, generate audio via `MultiVoiceAgentTTS` and expose the results.

### Current system constraints (important)
The backend currently uses streaming token generation:
- `backend/streaming.py` calls `llm.stream(...)` and emits `slot.token` events for each chunk.
- Final result is a single string in `slot.done.fullContent`.

Structured JSON output + streaming can be implemented in two ways; this PRD requires choosing one explicitly.

### Phase 2 design decision (required)

#### Option A (recommended): Structured generation first, then “simulate streaming”
1) Call LLM using **structured output** (`complete_structured`) to obtain a Pydantic model:
   - `SpokenResponse(text: str, voice_profile: VoiceProfileName)`
2) Emit `slot.token` events by chunking `SpokenResponse.text` (e.g., by sentence or word groups).
3) Emit `slot.done` with the full structured payload (see SSE schema changes below).
4) Run TTS and emit a new SSE event `slot.audio` when the WAV is ready.

Pros:
- Guarantees valid JSON at the application boundary.
- Keeps existing frontend streaming UX (still sees tokens).

Cons:
- Tokens are not “true” LLM streaming; they are simulated from the final result.

#### Option B: Stream raw JSON and parse at the end
1) Ask the model to stream JSON directly.
2) Frontend receives JSON fragments as tokens (hard to interpret).
3) Parse on `slot.done` and then run TTS.

Pros:
- True streaming.
Cons:
- Fragile UX; noisy tokens; parsing failures likely if the stream includes any non-JSON.

**MVP requirement**: implement **Option A** unless the backend team strongly prefers Option B for latency reasons.

---

## Phase 2 API + SSE specification

### Backend changes (minimum)

#### Change 1: Add a structured response model
Define a backend Pydantic model (new file is OK) for agent outputs:
- `text: str`
- `voice_profile: Literal[...]` for the 6 profile names

#### Change 2: Update system prompt
Update the base system prompt currently configured in `backend/config.py` (`settings.default_system_prompt`) to:
- maintain the poetic constraints
- include the voice profile guide from `eleven_labs_voice_profiles.md`
- require output to be a structured `{text, voice_profile}`

#### Change 3: Update per-slot generation path
Modify `backend/streaming.py` `stream_slot(...)` logic to:
- produce `SpokenResponse` (structured)
- push `slot.token` events using `SpokenResponse.text` chunks
- push a richer `slot.done`

### SSE event schema updates (Phase 2)

#### `slot.done` (new payload)
Current payload:
- `slotId`, `agentId`, `fullContent`

New payload must include (names may vary but must be consistent across backend/frontend):
- `slotId: int`
- `agentId: str`
- `text: str` (the spoken response)
- `voiceProfile: str` (one of the 6 profile names)

#### New event: `slot.audio`
Emit after TTS completes for a slot:
- `slotId: int`
- `agentId: str`
- `voiceProfile: str`
- `audioFormat: "wav"`
- `audioPath: str` OR `audioUrl: str`
- optional: `durationMs: int`, `sampleRateHz: int`

**Design requirement**: do not inline base64 audio in SSE for MVP; send a path/url so the client (or TouchDesigner bridge) can fetch it.

### Audio storage and retrieval

#### Storage layout (Phase 2)
Recommended:
- `artifacts/tts/phase2/<session_id>/<turn_id>/`
  - `slot-1-friendly_casual.wav`
  - `slot-2-warm_professional.wav`
  - ...

`session_id` may be derived from a request header or server-generated UUID. `turn_id` increments per broadcast.

#### Retrieval endpoint (recommended)
Add:
- `GET /v1/audio/{session_id}/{turn_id}/{filename}`
  - returns `audio/wav`

This endpoint should serve files only from the allowed artifacts directory.

---

## Phase 2 frontend integration (minimal)

### Current frontend behavior
Frontend uses `createRealStream()` to handle:
- token streaming into message content
- “complete” state per slot on `slot.done`

### Required frontend changes for Phase 2 (if the UI remains in use for monitoring)
- Parse the new `slot.done` payload and display only `text` (not JSON).
- Optionally handle `slot.audio` to:
  - show a “play” control per slot, or
  - automatically play the audio for each slot in a chosen order, or
  - forward the audio URL to the next stage of the installation pipeline.

If the frontend UI will be removed later, this monitoring UI still serves as a valuable debug tool during MVP build-out.

---

## Error handling + fallback behavior (Phase 2)

### Voice profile fallback
If agent selects an invalid profile (should be prevented by Pydantic enum, but still):
- Use fallback voice profile and log a warning.

### TTS failures
If ElevenLabs TTS fails for a slot:
- Still emit `slot.done` (LLM text is valid)
- Emit `slot.audio` with an error variant OR emit `slot.error` with a TTS-specific error type.

Recommendation:
- Add a new `ErrorType` value `tts_error` (backend + frontend) for observability.

---

## Security and operational requirements
- API keys must remain server-side only.
- Ensure `.wav` artifacts are either:
  - excluded from git by `.gitignore`, or
  - written to a temp/artifacts directory that is already ignored.
- Rate limiting:
  - Protect ElevenLabs calls with retries + exponential backoff.
  - Add per-turn concurrency caps if needed (6 parallel TTS calls can spike usage).

---

## Observability
Add structured logs for:
- LLM request start/end per slot
- parsed `voice_profile` per slot
- TTS request start/end per slot
- output file path per slot
- latency breakdown (LLM vs TTS)

---

## Acceptance Criteria (Phase 2)
- AC1: Each slot produces a structured response with a valid `voice_profile`.
- AC2: For every slot that completes (`slot.done`), a WAV is produced and retrievable (or a clear TTS error is emitted).
- AC3: The existing `/v1/chat` SSE flow continues to work end-to-end (start → tokens → done → overall done), with either:
  - simulated streaming tokens (Option A), or
  - documented alternative.

---

## Implementation Checklist (for backend team)

### Phase 1
- Add ElevenLabs API key config
- Add `backend/tts/*` modules and `MultiVoiceAgentTTS`
- Implement PCM→WAV wrapping
- Add demo script and ensure 6 WAV files generated
- Confirm voice IDs + models work with the account

### Phase 2
- Add Pydantic model for `{text, voice_profile}`
- Update system prompt to instruct voice selection
- Update `stream_slot` to use structured output (Option A)
- Add `slot.audio` event + artifacts storage
- Add audio retrieval endpoint
- Update frontend monitoring UI to handle new payloads/events (if needed)


