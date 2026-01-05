import argparse
import librosa
import numpy as np
import soundfile as sf
import os

def decompose_audio(input_file, output_dir="output_waves_v3_matched", save_files=True):
    """
    V3: Dynamic Amplitude Matching
    Uses dynamic gain to force the mix envelope to perfectly match original envelope.
    Also calculates RMSE Loss.
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
    amp3 = extract_harmonic_amp(3)

    print("Synthesizing Base Waves (V1 Cosine)...")
    
    def synthesize_raw(freq_multiplier, amplitude_env):
        freq_curve = f0_mapped * freq_multiplier
        phase = np.cumsum(2 * np.pi * freq_curve / sr)
        wave = amplitude_env * np.cos(phase)
        return wave
    
    raw_wave1 = synthesize_raw(1, amp1)
    raw_wave2 = synthesize_raw(2, amp2)
    raw_wave3 = synthesize_raw(3, amp3)
    
    raw_mix = raw_wave1 + raw_wave2 + raw_wave3
    
    # --- V3 Dynamic Amplitude Matching ---
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
    wave3 = raw_wave3 * gain_curve
    mix = wave1 + wave2 + wave3
    
    # --- Calculate Loss Metrics ---
    # RMSE
    mse = np.mean((y - mix) ** 2)
    rmse = np.sqrt(mse)
    
    # Accuracy (1 - relative_error) roughly
    # Or just return RMSE
    print(f"Optimization Complete. RMSE Loss: {rmse:.6f}")
    
    # Save files
    if save_files:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        
        out1 = os.path.join(output_dir, f"{base_name}_v3_wave1.wav")
        out2 = os.path.join(output_dir, f"{base_name}_v3_wave2.wav")
        out3 = os.path.join(output_dir, f"{base_name}_v3_wave3.wav")
        
        sf.write(out1, wave1, sr)
        sf.write(out2, wave2, sr)
        sf.write(out3, wave3, sr)
        
        print(f"Done! Output saved to {output_dir}")

    # Return metric as extra return value
    return y, sr, wave1, wave2, wave3, mix, rmse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Decompose audio V3.')
    parser.add_argument('--input', type=str, required=True, help='Path to input')
    parser.add_argument('--output_dir', type=str, default='output_v3', help='Output dir')
    args = parser.parse_args()
    decompose_audio(args.input, args.output_dir)
