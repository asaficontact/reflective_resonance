"""Audio decomposition module for wave component extraction.

This module provides background processing of TTS audio files to extract
wave components for the water-based art installation.
"""

from backend.waves.decompose_v3 import DecomposeResult, decompose_audio_to_waves
from backend.waves.paths import (
    WAVES_SESSIONS_BASE,
    get_wave_output_paths,
    tts_path_to_waves_dir,
)
from backend.waves.worker import (
    DecomposeJob,
    WavesJobResult,
    WavesWorkerPool,
    get_worker_pool,
    shutdown_waves_worker,
    startup_waves_worker,
)

__all__ = [
    # Worker pool
    "DecomposeJob",
    "WavesJobResult",
    "WavesWorkerPool",
    "get_worker_pool",
    "startup_waves_worker",
    "shutdown_waves_worker",
    # Paths
    "WAVES_SESSIONS_BASE",
    "tts_path_to_waves_dir",
    "get_wave_output_paths",
    # Decomposition
    "DecomposeResult",
    "decompose_audio_to_waves",
]
