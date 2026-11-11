"""Background worker pool for audio decomposition.

This module manages a pool of workers that process audio decomposition jobs
in the background using a ProcessPoolExecutor for CPU-bound work.
"""

import asyncio
import logging
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from backend.waves.decompose_v3 import DecomposeResult, decompose_audio_to_waves


def _warm_up_worker(hold_s: float = 2.0) -> bool:
    """Run one tiny decomposition inside a worker process.

    A fresh worker pays ~25s on its first job (importing librosa and compiling
    its numba kernels). Doing that at startup keeps the first visitor from
    waiting for it. The short sleep keeps this worker busy so that each
    warm-up task lands on a different process.
    """
    import tempfile

    import numpy as np
    import soundfile as sf

    with tempfile.TemporaryDirectory() as tmp:
        sr = 24000
        t = np.arange(int(sr * 1.0)) / sr
        src = Path(tmp) / "warmup.wav"
        # A voiced-like tone with harmonics so pitch tracking has something to follow
        y = 0.3 * np.sin(2 * np.pi * 180 * t) + 0.1 * np.sin(2 * np.pi * 360 * t)
        sf.write(src, y.astype(np.float32), sr)
        decompose_audio_to_waves(str(src), tmp, 2, [1, 2])
    time.sleep(hold_s)
    return True

logger = logging.getLogger(__name__)


@dataclass
class DecomposeJob:
    """Job to be processed by the decomposition worker."""

    session_id: str
    turn_index: int
    slot_id: int
    agent_id: str
    voice_profile: str
    tts_basename: str
    input_path: Path
    output_dir: Path
    target_slot_id: int | None = None
    summary_text: str | None = None  # For turn_index=-1 (summary) only
    n_waves: int = 2  # Number of wave files to produce
    target_slots: list[int] | None = None  # Target slot for each wave (for frequency mapping)
    submitted_at: float = field(default_factory=time.time)


@dataclass
class WavesJobResult:
    """Result of a wave decomposition job, combining job info with result."""

    job: DecomposeJob
    result: DecomposeResult


class WavesWorkerPool:
    """Manages background audio decomposition workers.

    Uses an asyncio.Queue for job management and a ProcessPoolExecutor
    for CPU-bound decomposition work.
    """

    def __init__(
        self,
        max_workers: int = 2,
        queue_max_size: int = 100,
        job_timeout_s: float = 60.0,
    ):
        """Initialize the worker pool.

        Args:
            max_workers: Number of ProcessPoolExecutor workers
            queue_max_size: Maximum queue size (jobs dropped when full)
            job_timeout_s: Timeout for each decomposition job
        """
        self._max_workers = max_workers
        self._queue_max_size = queue_max_size
        self._job_timeout_s = job_timeout_s

        self._executor: ProcessPoolExecutor | None = None
        self._queue: asyncio.Queue[DecomposeJob | None] | None = None
        self._worker_tasks: list[asyncio.Task] = []
        self._running = False

        # Result notification callback (for events orchestrator)
        self._result_callback: Callable[[WavesJobResult], None] | None = None

    def set_result_callback(
        self, callback: Callable[[WavesJobResult], None] | None
    ) -> None:
        """Set a callback to be invoked when jobs complete.

        The callback receives a WavesJobResult with both the job and result.
        This is used by the events orchestrator to track wave-mix readiness.

        Args:
            callback: Function to call on job completion, or None to clear
        """
        self._result_callback = callback
        logger.debug(f"Result callback {'set' if callback else 'cleared'}")

    async def start(self) -> None:
        """Start the worker pool. Call on app startup."""
        if self._running:
            logger.warning("WavesWorkerPool already running")
            return

        logger.info(
            f"Starting WavesWorkerPool: workers={self._max_workers}, "
            f"queue_size={self._queue_max_size}, timeout={self._job_timeout_s}s"
        )

        self._executor = ProcessPoolExecutor(max_workers=self._max_workers)
        self._queue = asyncio.Queue(maxsize=self._queue_max_size)
        self._running = True

        # Start worker tasks
        for i in range(self._max_workers):
            task = asyncio.create_task(self._worker_loop(i))
            self._worker_tasks.append(task)

        logger.info(f"WavesWorkerPool started with {self._max_workers} workers")

        # Warm the worker processes in the background (does not block startup)
        self._warmup_task = asyncio.create_task(self._warm_up())

    async def _warm_up(self) -> None:
        """Pre-load librosa in every worker process so the first job is fast."""
        if self._executor is None:
            return
        loop = asyncio.get_running_loop()
        start = time.perf_counter()
        try:
            await asyncio.gather(
                *[
                    loop.run_in_executor(self._executor, _warm_up_worker)
                    for _ in range(self._max_workers)
                ]
            )
            logger.info(
                f"WavesWorkerPool warm-up done in {time.perf_counter() - start:.1f}s"
            )
        except Exception as e:  # warm-up is best-effort
            logger.warning(f"WavesWorkerPool warm-up failed: {e}")

    async def stop(self) -> None:
        """Gracefully stop the worker pool. Call on app shutdown."""
        if not self._running:
            logger.warning("WavesWorkerPool not running")
            return

        logger.info("Stopping WavesWorkerPool...")
        self._running = False

        # Send sentinel values to stop workers
        if self._queue:
            for _ in range(len(self._worker_tasks)):
                try:
                    self._queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass

        # Wait for worker tasks to complete
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
            self._worker_tasks.clear()

        # Shutdown executor
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None

        self._queue = None
        logger.info("WavesWorkerPool stopped")

    def submit_job(self, job: DecomposeJob) -> bool:
        """Submit a decomposition job (non-blocking, fire-and-forget).

        Args:
            job: The decomposition job to submit

        Returns:
            True if job was queued, False if queue is full (job dropped)
        """
        if not self._running or self._queue is None:
            logger.warning("WavesWorkerPool not running, job dropped")
            return False

        try:
            self._queue.put_nowait(job)
            logger.info(
                f"Decomposition job queued: session={job.session_id}, "
                f"turn={job.turn_index}, file={job.input_path.name}"
            )
            return True
        except asyncio.QueueFull:
            logger.warning(
                f"Waves queue full, job dropped: session={job.session_id}, "
                f"turn={job.turn_index}, file={job.input_path.name}"
            )
            return False

    async def _worker_loop(self, worker_id: int) -> None:
        """Process jobs from queue.

        Args:
            worker_id: Identifier for this worker (for logging)
        """
        logger.debug(f"Worker {worker_id} started")
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                # Wait for a job with timeout to check _running flag periodically
                try:
                    job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Sentinel value signals shutdown
                if job is None:
                    logger.debug(f"Worker {worker_id} received shutdown signal")
                    break

                # Process the job
                await self._process_job(loop, worker_id, job)

            except Exception as e:
                logger.error(f"Worker {worker_id} unexpected error: {e}")

        logger.debug(f"Worker {worker_id} stopped")

    async def _process_job(
        self,
        loop: asyncio.AbstractEventLoop,
        worker_id: int,
        job: DecomposeJob,
    ) -> None:
        """Process a single decomposition job.

        Args:
            loop: The event loop
            worker_id: Identifier for this worker
            job: The job to process
        """
        try:
            logger.debug(
                f"Worker {worker_id} processing: session={job.session_id}, "
                f"turn={job.turn_index}, file={job.input_path.name}"
            )

            # Imported here to avoid a circular import at module load
            from backend.config import settings

            # Run CPU-bound decomposition in process pool with timeout
            result: DecomposeResult = await asyncio.wait_for(
                loop.run_in_executor(
                    self._executor,
                    decompose_audio_to_waves,
                    str(job.input_path),
                    str(job.output_dir),
                    job.n_waves,
                    job.target_slots,  # Pass target slots for frequency mapping
                    # Summary (turn_index=-1) plays on all six slots at once: turn it down
                    settings.summary_wave_gain if job.turn_index == -1 else 1.0,
                ),
                timeout=self._job_timeout_s,
            )

            if result.success:
                logger.info(
                    f"Decomposition complete: session={job.session_id}, "
                    f"turn={job.turn_index}, file={job.input_path.name}, "
                    f"rmse={result.rmse:.4f}, duration={result.duration_ms:.0f}ms"
                )
            else:
                logger.warning(
                    f"Decomposition failed: session={job.session_id}, "
                    f"turn={job.turn_index}, file={job.input_path.name}, "
                    f"error={result.error}"
                )

            # Notify the events orchestrator
            if self._result_callback:
                try:
                    job_result = WavesJobResult(job=job, result=result)
                    self._result_callback(job_result)
                except Exception as e:
                    logger.error(f"Error in result callback: {e}")

        except asyncio.TimeoutError:
            logger.warning(
                f"Decomposition timeout: session={job.session_id}, "
                f"turn={job.turn_index}, file={job.input_path.name}, "
                f"timeout={self._job_timeout_s}s"
            )
        except Exception as e:
            logger.error(
                f"Decomposition error: session={job.session_id}, "
                f"turn={job.turn_index}, file={job.input_path.name}, "
                f"error={e}"
            )


# Module-level singleton
_worker_pool: WavesWorkerPool | None = None


def get_worker_pool() -> WavesWorkerPool:
    """Get or create the worker pool singleton.

    Returns:
        The WavesWorkerPool instance
    """
    global _worker_pool
    if _worker_pool is None:
        # Import here to avoid circular imports
        from backend.config import settings

        _worker_pool = WavesWorkerPool(
            max_workers=settings.waves_max_workers,
            queue_max_size=settings.waves_queue_max_size,
            job_timeout_s=settings.waves_job_timeout_s,
        )
    return _worker_pool


async def startup_waves_worker() -> None:
    """Initialize and start the waves worker pool."""
    from backend.config import settings

    if not settings.waves_enabled:
        logger.info("Waves decomposition disabled (waves_enabled=False)")
        return

    pool = get_worker_pool()
    await pool.start()


async def shutdown_waves_worker() -> None:
    """Gracefully shutdown the waves worker pool."""
    global _worker_pool
    if _worker_pool is not None:
        await _worker_pool.stop()
        _worker_pool = None
