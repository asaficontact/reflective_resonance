"""Audio decomposition algorithm for wave component extraction.

This module contains the decomposition algorithm that splits TTS audio
into 2 wave components (fundamental + 1st harmonic) for the water-based
art installation.

IMPORTANT: This function runs in a subprocess (ProcessPoolExecutor),
so it must be picklable (module-level function, no closures).
"""

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)


# Slot-specific frequency ranges (symmetric "dome" pattern: high-mid-low-low-mid-high)
SLOT_FREQ_RANGES: dict[int, tuple[float, float]] = {
    1: (80.0, 100.0),   # Outer high
    2: (50.0, 70.0),    # Middle medium
    3: (20.0, 40.0),    # Center low
    4: (20.0, 40.0),    # Center low
    5: (50.0, 70.0),    # Middle medium
    6: (80.0, 100.0),   # Outer high
}


@dataclass
class DecomposeResult:
    """Result from audio decomposition job."""

    success: bool
    input_path: str
    output_dir: str
    wave_paths: list[str] = field(default_factory=list)  # List of N wave paths
    n_waves: int = 2  # Number of waves produced
    rmse: float | None = None
    nrmse: float | None = None
    snr_db: float | None = None
    env_corr: float | None = None
    error: str | None = None
    duration_ms: float = 0.0


def _extract_harmonic_amp(
    S: np.ndarray,
    f0_clean: np.ndarray,
    harmonic_num: int,
    sr: int,
    n_fft: int,
    freqs: np.ndarray,
    times_samples: np.ndarray,
    times_frames: np.ndarray,
) -> np.ndarray:
    """Extract amplitude envelope for a specific harmonic."""
    target_f = f0_clean * harmonic_num
    bin_idx = np.round(target_f / (sr / n_fft)).astype(int)
    bin_idx = np.clip(bin_idx, 0, len(freqs) - 1)
    frame_indices = np.arange(len(bin_idx))
    amps = S[bin_idx, frame_indices]
    amps = amps * (f0_clean > 0).astype(float)
    amp_interp = np.interp(times_samples, times_frames, amps)

    # Base normalization (start with x3.0 gain as a baseline)
    normalization = (2 / 512) * 3.0
    return amp_interp * normalization


def _synthesize_raw(
    f0_mapped: np.ndarray,
    freq_multiplier: int,
    amplitude_env: np.ndarray,
    sr: int,
) -> np.ndarray:
    """Synthesize a raw wave from frequency and amplitude data."""
    freq_curve = f0_mapped * freq_multiplier
    phase = np.cumsum(2 * np.pi * freq_curve / sr)
    wave = amplitude_env * np.cos(phase)
    return wave


def _calculate_envelope(signal: np.ndarray) -> np.ndarray:
    """Calculate RMS envelope of a signal."""
    return librosa.feature.rms(y=signal, frame_length=512, hop_length=128, center=True)[0]


def _synthesize_with_freq_range(
    f0_interp: np.ndarray,
    min_f0: float,
    max_f0: float,
    target_freq_range: tuple[float, float],
    amplitude_env: np.ndarray,
    sr: int,
) -> np.ndarray:
    """
    Synthesize a wave with frequency mapped to a target range.

    Preserves pitch contour: higher original pitch → higher output within range.

    Args:
        f0_interp: Interpolated f0 at sample rate
        min_f0: Minimum f0 from original audio
        max_f0: Maximum f0 from original audio
        target_freq_range: (min_freq, max_freq) for this wave's target slot
        amplitude_env: Amplitude envelope (extracted from harmonic)
        sr: Sample rate

    Returns:
        Synthesized wave with frequency in target range
    """
    min_freq, max_freq = target_freq_range

    # Map f0 to target frequency range (preserving pitch contour)
    f0_mapped = np.zeros_like(f0_interp)
    mask = f0_interp > 0
    if max_f0 > min_f0:
        # Linear mapping: original pitch range → target frequency range
        f0_mapped[mask] = min_freq + (f0_interp[mask] - min_f0) / (max_f0 - min_f0) * (max_freq - min_freq)
    else:
        # Fallback: use midpoint of range
        f0_mapped[mask] = (min_freq + max_freq) / 2

    # Synthesize wave (no harmonic multiplication - frequency determined by slot)
    phase = np.cumsum(2 * np.pi * f0_mapped / sr)
    wave = amplitude_env * np.cos(phase)
    return wave


def decompose_audio_to_waves(
    input_path: str,
    output_dir: str,
    n_waves: int = 2,
    target_slots: list[int] | None = None,
) -> DecomposeResult:
    """
    Decompose a TTS WAV into N wave components with slot-aware frequency mapping.

    Each wave's frequency is mapped to its target slot's frequency range:
    - Slot 1, 6: 80-100Hz (outer high)
    - Slot 2, 5: 50-70Hz (middle medium)
    - Slot 3, 4: 20-40Hz (center low)

    Amplitude envelopes are extracted from harmonics for natural sound variation.
    Uses dynamic gain to force the mix envelope to match original envelope.

    Args:
        input_path: Absolute path to input WAV file
        output_dir: Directory for output wave files
        n_waves: Number of wave files to produce (default: 2)
        target_slots: Target slot ID for each wave (e.g., [1, 2] for agent in slot 1).
                      If None, falls back to legacy behavior (15-80Hz base frequency).

    Returns:
        DecomposeResult with success status and output paths

    Note:
        This function runs in a subprocess (ProcessPoolExecutor)
        so it must be picklable (module-level, no closures).
    """
    start_time = time.time()

    try:
        input_path_obj = Path(input_path)
        output_dir_obj = Path(output_dir)

        # Validate input file exists
        if not input_path_obj.exists():
            return DecomposeResult(
                success=False,
                input_path=input_path,
                output_dir=output_dir,
                error=f"Input file not found: {input_path}",
                duration_ms=(time.time() - start_time) * 1000,
            )

        # Create output directory
        output_dir_obj.mkdir(parents=True, exist_ok=True)

        # Load audio at processing sample rate
        processing_sr = 8000
        y, sr = librosa.load(input_path, sr=processing_sr)

        # Extract pitch (f0)
        hop_length = 128
        f0, voiced_flag, voiced_probs = librosa.pyin(
            y,
            fmin=librosa.note_to_hz("C2"),
            fmax=librosa.note_to_hz("C7"),
            sr=sr,
            hop_length=hop_length,
        )
        f0_clean = np.nan_to_num(f0)

        # Interpolate f0
        times_samples = np.arange(len(y)) / sr
        times_frames = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop_length)
        f0_interp = np.interp(times_samples, times_frames, f0_clean)

        # Extract f0 range for frequency mapping
        valid_f0 = f0_clean[f0_clean > 0]
        if len(valid_f0) > 0:
            min_f0 = float(np.min(valid_f0))
            max_f0 = float(np.max(valid_f0))
            if max_f0 == min_f0:
                max_f0 += 1.0
        else:
            # Fallback for silent/unvoiced audio
            min_f0, max_f0 = 100.0, 300.0

        # Determine if using slot-aware frequency mapping
        use_slot_mapping = (
            target_slots is not None
            and len(target_slots) == n_waves
            and all(slot in SLOT_FREQ_RANGES for slot in target_slots)
        )

        # Legacy frequency mapping (only used if target_slots not provided)
        if not use_slot_mapping:
            f0_mapped = np.zeros_like(f0_interp)
            mask = f0_interp > 0
            f0_mapped[mask] = 15.0 + (f0_interp[mask] - min_f0) / (max_f0 - min_f0) * (80.0 - 15.0)

        # Extract harmonic amplitudes (STFT)
        n_fft = 512
        S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        # Extract amplitude envelopes for N harmonics (used for natural sound variation)
        amplitudes = []
        for harmonic_num in range(1, n_waves + 1):
            amp = _extract_harmonic_amp(
                S, f0_clean, harmonic_num, sr, n_fft, freqs, times_samples, times_frames
            )
            amplitudes.append(amp)

        # Synthesize N raw waves
        raw_waves = []
        for i, amp in enumerate(amplitudes):
            if use_slot_mapping:
                # NEW: Use slot-specific frequency range
                target_slot = target_slots[i]
                freq_range = SLOT_FREQ_RANGES[target_slot]
                raw_wave = _synthesize_with_freq_range(
                    f0_interp, min_f0, max_f0, freq_range, amp, sr
                )
            else:
                # Legacy: Use harmonic multiplication with base frequency
                harmonic_num = i + 1
                raw_wave = _synthesize_raw(f0_mapped, harmonic_num, amp, sr)
            raw_waves.append(raw_wave)

        # Compute raw mix (sum of all waves)
        raw_mix = np.sum(raw_waves, axis=0)

        # V3 Dynamic Amplitude Matching
        env_original_frames = _calculate_envelope(y)
        env_mix_frames = _calculate_envelope(raw_mix)

        # Avoid division by zero
        epsilon = 1e-8
        gain_curve_frames = env_original_frames / (env_mix_frames + epsilon)

        # Interpolate gain curve to sample level
        gain_curve = np.interp(times_samples, times_frames, gain_curve_frames)

        # Apply Gain Curve (cap to avoid exploding on silence/noise)
        gain_curve = np.clip(gain_curve, 0, 10.0)

        # Apply gain to all waves
        final_waves = [raw_wave * gain_curve for raw_wave in raw_waves]
        mix = np.sum(final_waves, axis=0)

        # Calculate Loss Metrics
        mse = np.mean((y - mix) ** 2)
        rmse = float(np.sqrt(mse))

        # Extended metrics
        nrmse = rmse / (np.std(y) + 1e-10)
        signal_power = np.mean(y ** 2)
        noise_power = mse
        snr_db = float(10 * np.log10(signal_power / (noise_power + 1e-10)))
        env_mix_final = _calculate_envelope(mix)
        min_len = min(len(env_original_frames), len(env_mix_final))
        env_corr = float(np.corrcoef(env_original_frames[:min_len], env_mix_final[:min_len])[0, 1])

        # Save N wave files
        base_name = input_path_obj.stem
        wave_paths = []
        for i, wave in enumerate(final_waves):
            wave_num = i + 1
            out_path = output_dir_obj / f"{base_name}_v3_wave{wave_num}.wav"
            sf.write(str(out_path), wave, sr)
            wave_paths.append(str(out_path))

        duration_ms = (time.time() - start_time) * 1000

        return DecomposeResult(
            success=True,
            input_path=input_path,
            output_dir=output_dir,
            wave_paths=wave_paths,
            n_waves=n_waves,
            rmse=rmse,
            nrmse=nrmse,
            snr_db=snr_db,
            env_corr=env_corr,
            duration_ms=duration_ms,
        )

    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return DecomposeResult(
            success=False,
            input_path=input_path,
            output_dir=output_dir,
            error=str(e),
            duration_ms=duration_ms,
        )
