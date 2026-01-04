"""ElevenLabs API client wrapper with lazy initialization."""

import logging
import os

from elevenlabs.client import ElevenLabs

# Import config to trigger dotenv loading and env var resolution
from backend import config  # noqa: F401
from backend.tts.profiles import VoiceProfile

logger = logging.getLogger(__name__)

# Lazy-initialized client (follows agents.py pattern)
_client: ElevenLabs | None = None


def get_client() -> ElevenLabs:
    """Get or create ElevenLabs client (lazy singleton)."""
    global _client

    if _client is None:
        # Read from os.environ since config.py sets it there after resolving
        # both RR_ELEVENLABS_API_KEY and ELEVENLABS_API_KEY
        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY not configured. "
                "Set RR_ELEVENLABS_API_KEY or ELEVENLABS_API_KEY environment variable."
            )

        _client = ElevenLabs(api_key=api_key)
        logger.info("ElevenLabs client initialized")

    return _client


def generate_pcm(
    text: str,
    profile: VoiceProfile,
    output_format: str = "pcm_24000",
) -> bytes:
    """Generate PCM audio using ElevenLabs API.

    Args:
        text: Text to convert to speech
        profile: Voice profile with voice_id, model_id, and settings
        output_format: ElevenLabs output format (default pcm_24000)

    Returns:
        Raw PCM audio bytes (signed 16-bit LE mono)
    """
    client = get_client()

    logger.info(
        f"Generating TTS: voice={profile.voice_name}, "
        f"model={profile.model_id}, format={output_format}"
    )

    # ElevenLabs convert returns an iterator of bytes
    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=profile.voice_id,
        model_id=profile.model_id,
        output_format=output_format,
        voice_settings={
            "stability": profile.settings.stability,
            "similarity_boost": profile.settings.similarity_boost,
            "style": profile.settings.style,
            "use_speaker_boost": profile.settings.use_speaker_boost,
            "speed": profile.settings.speed,
        },
    )

    # Collect all chunks
    audio_chunks = []
    for chunk in audio_generator:
        audio_chunks.append(chunk)

    return b"".join(audio_chunks)
