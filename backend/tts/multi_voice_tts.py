"""MultiVoiceAgentTTS - TTS system with 6 voice profiles for Reflective Resonance."""

import logging
from pathlib import Path

from backend.config import settings
from backend.tts.elevenlabs_client import generate_pcm
from backend.tts.profiles import (
    VoiceProfile,
    get_profile,
    list_profiles,
)
from backend.tts.wav import pcm_to_wav, write_wav_file

logger = logging.getLogger(__name__)


class MultiVoiceAgentTTS:
    """TTS system with 6 voice profiles for the Reflective Resonance installation."""

    def __init__(self) -> None:
        self._fallback_profile = settings.tts_fallback_profile
        self._output_format = settings.tts_output_format
        self._sample_rate = self._parse_sample_rate(self._output_format)

    def _parse_sample_rate(self, output_format: str) -> int:
        """Extract sample rate from format string (e.g., 'pcm_24000' -> 24000)."""
        parts = output_format.split("_")
        if len(parts) >= 2:
            try:
                return int(parts[1])
            except ValueError:
                pass
        return 24000  # default

    def list_profiles(self) -> list[str]:
        """List all available voice profile names."""
        return list_profiles()

    def get_profile(self, profile_name: str) -> VoiceProfile:
        """Get a voice profile by name."""
        return get_profile(profile_name)

    def _resolve_profile(self, profile_name: str) -> VoiceProfile:
        """Resolve profile name with fallback for invalid names."""
        try:
            return get_profile(profile_name)
        except ValueError:
            logger.warning(
                f"Invalid profile '{profile_name}', falling back to '{self._fallback_profile}'"
            )
            return get_profile(self._fallback_profile)

    def generate_wav(self, text: str, profile_name: str) -> bytes:
        """Generate WAV audio bytes for text using specified voice profile.

        Args:
            text: Text to convert to speech
            profile_name: One of the 6 voice profile names

        Returns:
            WAV file bytes (with header)
        """
        profile = self._resolve_profile(profile_name)

        logger.info(
            f"Generating WAV: profile={profile_name}, "
            f"voice={profile.voice_name}, text_len={len(text)}"
        )

        pcm_data = generate_pcm(text, profile, self._output_format)
        wav_data = pcm_to_wav(pcm_data, sample_rate=self._sample_rate)

        logger.info(f"Generated WAV: {len(wav_data)} bytes")
        return wav_data

    def generate_wav_to_file(
        self,
        text: str,
        profile_name: str,
        path: Path | str,
    ) -> Path:
        """Generate WAV audio and save to file.

        Args:
            text: Text to convert to speech
            profile_name: One of the 6 voice profile names
            path: Output file path

        Returns:
            Path to the written WAV file
        """
        profile = self._resolve_profile(profile_name)
        path = Path(path)

        logger.info(f"Generating WAV to file: profile={profile_name}, path={path}")

        pcm_data = generate_pcm(text, profile, self._output_format)
        result_path = write_wav_file(pcm_data, path, sample_rate=self._sample_rate)

        logger.info(f"Wrote WAV file: {result_path} ({result_path.stat().st_size} bytes)")
        return result_path
