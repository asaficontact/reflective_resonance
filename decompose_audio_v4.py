import argparse
import librosa
import numpy as np
import soundfile as sf
import os

def decompose_audio(input_file, output_dir="output_waves_v4_2waves", save_files=True):
    """
    V4: Dynamic Amplitude Matching (2 Waves)
    Uses dynamic gain to force the mix envelope to perfectly match original envelope.
    Decomposes into only 2 harmonic waves (Fundamental + 1st Harmonic).
    """
    
    print(f"Loading audio: {input_file}")
    processing_sr = 8000
    y, sr = librosa.load(input_file, sr=processing_sr)
    
    print(f"Extracting pitch (f0) at {sr}Hz...")
    hop_length = 128
    f0, voiced_flag, voiced_probs = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr, hop_length=hop_length)
    f0_clean = np.nan_to_num(f0)
    
    # Interpolate f0
    times_samples = np.arange(len(y)) / sr
    times_frames = librosa.frames_to_time(np.arange(len(f0)), sr=sr, hop_length=hop_length)
    f0_interp = np.interp(times_samples, times_frames, f0_clean)
    
    # --- Frequency Mapping Logic (15Hz - 80Hz) ---
    print("Mapping frequencies to 15-80Hz range...")
    valid_f0 = f0_clean[f0_clean > 0]
    if len(valid_f0) > 0:
        min_f0 = np.min(valid_f0)
        max_f0 = np.max(valid_f0)
        if max_f0 == min_f0: max_f0 += 1.0
        
        f0_mapped = np.zeros_like(f0_interp)
        mask = f0_interp > 0
        f0_mapped[mask] = 15.0 + (f0_interp[mask] - min_f0) / (max_f0 - min_f0) * (80.0 - 15.0)
    else:
        f0_mapped = f0_interp
        
    print(f"Extracting harmonic amplitudes (STFT)...")
    n_fft = 512
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)
    
    def extract_harmonic_amp(harmonic_num):
        target_f = f0_clean * harmonic_num
        bin_idx = np.round(target_f / (sr / n_fft)).astype(int)
        bin_idx = np.clip(bin_idx, 0, len(freqs)-1)
        frame_indices = np.arange(len(bin_idx))
        amps = S[bin_idx, frame_indices]
        amps = amps * (f0_clean > 0).astype(float)
        amp_interp = np.interp(times_samples, times_frames, amps)
        
        # Base normalization (start with x3.0 gain as a baseline)
        normalization = (2 / 512) * 3.0
        return amp_interp * normalization

    amp1 = extract_harmonic_amp(1)
    amp2 = extract_harmonic_amp(2)

    print("Synthesizing Base Waves (V4 2-EAVES)...")
    
    def synthesize_raw(freq_multiplier, amplitude_env):
        freq_curve = f0_mapped * freq_multiplier
        phase = np.cumsum(2 * np.pi * freq_curve / sr)
        wave = amplitude_env * np.cos(phase)
        return wave
    
    raw_wave1 = synthesize_raw(1, amp1)
    raw_wave2 = synthesize_raw(2, amp2)
    
    raw_mix = raw_wave1 + raw_wave2
    
    # --- V3/V4 Dynamic Amplitude Matching ---
    print("Calculating Dynamic Gain Optimization...")
    
    # 1. Calculate Envelopes
    # We use a simple windowed RMS for envelope comparison
    def calculate_envelope(signal):
        return librosa.feature.rms(y=signal, frame_length=512, hop_length=128, center=True)[0]
    
    # Get envelopes at frame rate
    env_original_frames = calculate_envelope(y)
    env_mix_frames = calculate_envelope(raw_mix)
    
    # Avoid division by zero
    epsilon = 1e-8
    gain_curve_frames = env_original_frames / (env_mix_frames + epsilon)
    
    # Interpolate gain curve to sample level
    # Reuse times_frames from earlier which matches hop_length=128
    gain_curve = np.interp(times_samples, times_frames, gain_curve_frames)
    
    # Apply Gain Curve
    # We cap the gain to avoid exploding on silence/noise (e.g. max x10 gain)
    gain_curve = np.clip(gain_curve, 0, 10.0)
    
    wave1 = raw_wave1 * gain_curve
    wave2 = raw_wave2 * gain_curve
    mix = wave1 + wave2
    
    # --- Calculate Loss Metrics ---
    # 1. RMSE
    mse = np.mean((y - mix) ** 2)
    rmse = np.sqrt(mse)
    
    # 2. Normalized RMSE (relative to signal std)
    nrmse = rmse / (np.std(y) + 1e-10)
    
    # 3. Signal-to-Noise Ratio (dB)
    signal_power = np.mean(y ** 2)
    noise_power = mse  # same as np.mean((y - mix) ** 2)
    snr_db = 10 * np.log10(signal_power / (noise_power + 1e-10))
    
    # 4. Envelope Correlation
    env_mix_final = calculate_envelope(mix)
    # Align lengths if needed
    min_len = min(len(env_original_frames), len(env_mix_final))
    env_corr = np.corrcoef(env_original_frames[:min_len], env_mix_final[:min_len])[0, 1]
    
    print(f"Optimization Complete:")
    print(f"  RMSE: {rmse:.6f}")
    print(f"  NRMSE: {nrmse:.4f} ({nrmse*100:.1f}% error)")
    print(f"  SNR: {snr_db:.2f} dB")
    print(f"  Envelope Correlation: {env_corr:.4f}")
    
    # Save files
    if save_files:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        
        out1 = os.path.join(output_dir, f"{base_name}_v4_wave1.wav")
        out2 = os.path.join(output_dir, f"{base_name}_v4_wave2.wav")
        
        sf.write(out1, wave1, sr)
        sf.write(out2, wave2, sr)
        
        print(f"Done! Output saved to {output_dir}")

    # Return metric as extra return value
    # Return all metrics as a dict
    metrics = {'rmse': rmse, 'nrmse': nrmse, 'snr_db': snr_db, 'env_corr': env_corr}
    return y, sr, wave1, wave2, mix, metrics

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Decompose audio V4 (2 Waves).')
    parser.add_argument('--input', type=str, required=True, help='Path to input')
    parser.add_argument('--output_dir', type=str, default='output_waves_v4_2waves', help='Output dir')
    args = parser.parse_args()
    decompose_audio(args.input, args.output_dir)
