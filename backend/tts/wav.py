"""PCM to WAV conversion helper."""

import io
import wave
from pathlib import Path


def pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Convert raw PCM bytes to WAV format.

    Args:
        pcm_data: Raw PCM audio (signed 16-bit little-endian)
        sample_rate: Sample rate in Hz (default 24000 for ElevenLabs pcm_24000)
        channels: Number of audio channels (default 1 = mono)
        sample_width: Bytes per sample (default 2 = 16-bit)

    Returns:
        WAV file bytes with proper header
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return buffer.getvalue()


def write_wav_file(
    pcm_data: bytes,
    path: Path | str,
    sample_rate: int = 24000,
) -> Path:
    """Write PCM data to WAV file.

    Args:
        pcm_data: Raw PCM audio bytes
        path: Output file path
        sample_rate: Sample rate in Hz

    Returns:
        Path to written file
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    wav_data = pcm_to_wav(pcm_data, sample_rate)
    path.write_bytes(wav_data)
    return path
