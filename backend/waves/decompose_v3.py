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


def decompose_audio_to_waves(
    input_path: str,
    output_dir: str,
    n_waves: int = 2,
) -> DecomposeResult:
    """
    Decompose a TTS WAV into N wave components (harmonics 1 through N).

    Uses dynamic gain to force the mix envelope to perfectly match original envelope.
    Calculates loss metrics: RMSE, NRMSE, SNR (dB), and envelope correlation.

    Args:
        input_path: Absolute path to input WAV file
        output_dir: Directory for output wave files
        n_waves: Number of wave files to produce (default: 2)

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

        # Frequency Mapping Logic (15Hz - 80Hz)
        valid_f0 = f0_clean[f0_clean > 0]
        if len(valid_f0) > 0:
            min_f0 = np.min(valid_f0)
            max_f0 = np.max(valid_f0)
            if max_f0 == min_f0:
                max_f0 += 1.0

            f0_mapped = np.zeros_like(f0_interp)
            mask = f0_interp > 0
            f0_mapped[mask] = 15.0 + (f0_interp[mask] - min_f0) / (max_f0 - min_f0) * (80.0 - 15.0)
        else:
            f0_mapped = f0_interp

        # Extract harmonic amplitudes (STFT)
        n_fft = 512
        S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
        freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

        # Extract amplitude envelopes for N harmonics
        amplitudes = []
        for harmonic_num in range(1, n_waves + 1):
            amp = _extract_harmonic_amp(
                S, f0_clean, harmonic_num, sr, n_fft, freqs, times_samples, times_frames
            )
            amplitudes.append(amp)

        # Synthesize N raw waves
        raw_waves = []
        for i, amp in enumerate(amplitudes):
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
