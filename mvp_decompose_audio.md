## MVP PRD: Decompose TTS WAV into 3 “Wave” Tracks (V3) — Background, Per-Session

### Context
Reflective Resonance generates **TTS WAV** artifacts for a **3-turn** multi-agent workflow:
- Turn 1: `response`
- Turn 2: `comment`
- Turn 3: `reply`

Today, each slot/turn produces a WAV file under:
- `artifacts/tts/sessions/<session_id>/turn_<N>/*.wav`

We want to add an **audio decomposition** step that runs **in parallel** (non-blocking) whenever a TTS WAV is written, producing **three derived WAV files** per input audio using the existing algorithm in `decompose_audio_v3.py`.

The decomposition outputs must be stored **per-session** and **per-turn** under a new artifacts subtree:
- `artifacts/waves/sessions/<session_id>/turn_<N>/...`

No new SSE event is required for this MVP: the system should continue emitting existing events (`slot.audio` etc.) as-is.

---

## Goals / Non-goals

### Goals
- Automatically run decomposition for **every successfully written TTS WAV** in Turn 1/2/3.
- Run decomposition **non-blocking** so:
  - `slot.audio` is emitted as soon as the TTS WAV is written.
  - decomposition work continues concurrently and does not delay the chat workflow.
- Store decomposition outputs in a **deterministic, per-session layout** mirroring the TTS session layout.
- Add guardrails for stability:
  - bounded concurrency (avoid CPU saturation)
  - best-effort error handling (decomposition failures must not fail the turn)
  - clear logs and per-file traceability

### Non-goals (MVP)
- No new frontend features or UI changes.
- No new SSE event (no `slot.waves` / progress updates).
- No real-time visualization of wave tracks.
- No persistent job queue (Celery/RQ) and no cross-process durability guarantees.
- No algorithm changes to `decompose_audio_v3.py` beyond minimal “productionization” needed to integrate it.

---

## Current System (Relevant Implementation)

### Backend workflow
Each slot in `backend/workflow.py` writes TTS WAVs in Turn 1/2/3 using:
- `await asyncio.to_thread(tts.generate_wav_to_file, text, voice_profile, audio_path)`

Then it emits:
- `slot.audio` with a relative path under `tts/sessions/<session_id>/turn_<N>/...`

### Artifact serving
The backend serves `artifacts/` via:
- `GET /v1/audio/<path under artifacts>`

So wave outputs under `artifacts/waves/...` will be retrievable without adding new endpoints.

---

## Decomposition Algorithm (V3) — What it Produces

The existing function `decompose_audio(input_file, output_dir, save_files=True)`:
- Loads audio at **processing_sr = 8000** (resamples input)
- Extracts pitch \(f0\) using `librosa.pyin` (C2 → C7)
- Extracts harmonic amplitude envelopes via STFT bins at \(f0, 2f0, 3f0\)
- Maps pitch to a **15–80Hz** output frequency range
- Synthesizes **3 cosine-based tracks** (`wave1`, `wave2`, `wave3`)
- Applies a dynamic gain curve to match the original envelope
- Writes 3 files:
  - `<base>_v3_wave1.wav`
  - `<base>_v3_wave2.wav`
  - `<base>_v3_wave3.wav`
- Returns `(y, sr, wave1, wave2, wave3, mix, rmse)`

For this MVP, we only require **the 3 output WAVs** to be written; returning values can be used for metrics/logging.

---

## Proposed Design

### 1) Storage layout (per-session, per-turn)

#### Input (existing)
- `artifacts/tts/sessions/<session_id>/turn_<N>/<tts_filename>.wav`

#### Output (new)
- `artifacts/waves/sessions/<session_id>/turn_<N>/<tts_filename_base>_v3_wave1.wav`
- `artifacts/waves/sessions/<session_id>/turn_<N>/<tts_filename_base>_v3_wave2.wav`
- `artifacts/waves/sessions/<session_id>/turn_<N>/<tts_filename_base>_v3_wave3.wav`

Notes:
- Use the **same `<tts_filename_base>`** as the TTS WAV (minus `.wav`).
- Turn folder naming must match existing `turn_1`, `turn_2`, `turn_3`.
- The decomposition job must `mkdir -p` the output directory before writing.

### 2) Execution model (non-blocking + bounded parallelism)

Decomposition is CPU-heavy (pitch tracking + STFT + synthesis). For “smooth” operation:

- **Do not await decomposition** in the slot coroutine.
- Schedule decomposition after the TTS WAV write succeeds, using:
  - an `asyncio` background task (`asyncio.create_task(...)`) that enqueues or executes work
  - a **bounded concurrency mechanism** (required)

Recommended MVP implementation strategy:
- A small **background worker pool** inside the backend process:
  - `asyncio.Queue` of decomposition jobs
  - N workers (configurable) pulling from queue
  - Each worker runs the CPU work via a **ProcessPool** (`concurrent.futures.ProcessPoolExecutor`)
  - A per-worker timeout (configurable) to prevent pathological hangs

Why a ProcessPool:
- Decomposition is CPU-bound; process pool reduces contention with the asyncio loop and isolates CPU spikes.

### 3) Integration points (where to trigger jobs)

Trigger decomposition **only after** the TTS WAV file is fully written:
- Turn 1: after `tts.generate_wav_to_file(...)` succeeds
- Turn 2: same
- Turn 3: same

The trigger should be placed such that:
- `slot.audio` emission remains immediate after TTS write
- manifest writes remain immediate
- decomposition begins “as soon as possible” but does not block the workflow

### 4) Configuration knobs

Add settings in `backend/config.py` (defaults are MVP-safe):
- **`waves_enabled: bool = True`**
- **`waves_max_workers: int = 2`** (ProcessPool worker count)
- **`waves_queue_max_size: int = 128`** (drop/backpressure behavior defined below)
- **`waves_job_timeout_s: int = 60`** (per file)
- **`waves_processing_sr: int = 8000`** (must match algorithm; optional to surface)

Behavior:
- If `waves_enabled` is false → no jobs scheduled.
- If queue is full:
  - MVP: drop the job and log a warning (prefer not to block TTS pipeline).

### 5) Logging and observability requirements

Each decomposition job must log:
- sessionId, turnIndex
- input wav path
- output dir
- start/end timestamps and duration
- success/failure + exception details
- optional: `rmse` from return values

Log levels:
- `INFO`: job start/end
- `WARNING`: queue full / job dropped
- `ERROR`: decomposition failure

### 6) Error handling requirements

- Decomposition failures must not emit `slot.error` and must not fail the workflow.
- Failures are “best-effort”:
  - log error with context
  - continue processing other jobs

### 7) Frontend requirements

None for MVP.

Wave files will be accessible (for debugging or TouchDesigner) via the existing static mount:
- `GET /v1/audio/waves/sessions/<session_id>/turn_<N>/<filename>`

---

## Deliverables

### Backend deliverables
- A small backend module/package for wave decomposition, e.g.:
  - `backend/waves/`
    - `decompose_v3.py` (callable function; adapted from `decompose_audio_v3.py`)
    - `worker.py` (queue + worker pool + scheduling API)
    - `paths.py` (path mapping helpers: input wav → output dir)
- Integration changes in `backend/workflow.py` to schedule jobs after each successful TTS write.
- Optional: extend `TTSSession` or add a new `WaveSession` helper to compute wave output directories.

### Dependencies
Python packages (exact versions TBD by implementer):
- `librosa`
- `soundfile`
- `numpy`

System dependency:
- `libsndfile` (required by `soundfile` on many platforms)

---

## Acceptance Criteria

- **AC1: Correct storage layout**
  - For any session `<session_id>`, decomposition outputs appear under:
    - `artifacts/waves/sessions/<session_id>/turn_1/`
    - `artifacts/waves/sessions/<session_id>/turn_2/`
    - `artifacts/waves/sessions/<session_id>/turn_3/`

- **AC2: Output completeness**
  - For each TTS WAV written successfully, exactly **3 wave files** are produced with suffixes:
    - `_v3_wave1.wav`, `_v3_wave2.wav`, `_v3_wave3.wav`

- **AC3: Non-blocking**
  - `slot.audio` emission timing is not delayed by decomposition (decomposition runs after `slot.audio` without awaiting).

- **AC4: Bounded parallelism**
  - System does not spawn unbounded background tasks; maximum parallel decomposition is capped by configuration.

- **AC5: Failure isolation**
  - If decomposition fails for one file, the chat workflow and TTS generation still complete normally.

---

## Testing Plan (MVP)

### Local manual tests
- Generate a session with all 3 turns.
- Verify that:
  - TTS WAVs exist under `artifacts/tts/sessions/<session_id>/turn_<N>/`
  - wave outputs appear under the corresponding `artifacts/waves/sessions/<session_id>/turn_<N>/`
  - filenames match expected suffixes

### Load sanity test
- Run a few back-to-back sessions and confirm:
  - CPU usage remains stable (bounded by worker count)
  - queue behavior is sane (no memory blowups)
  - logs show completion for jobs

---

## Rollout Notes / Future Extensions (non-MVP)
- Add a `slot.waves` SSE event to notify frontend/TouchDesigner when decomposition completes.
- Persist decomposition metadata into `session.json` (rmse, processing_sr, durations, wave paths).
- Add a cleanup policy (TTL) for `artifacts/waves`.
- Optimize the algorithm for speed or incorporate caching for repeated inputs.


