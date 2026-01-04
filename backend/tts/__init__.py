"""TTS module for Reflective Resonance with 6 voice profiles."""

from backend.tts.multi_voice_tts import MultiVoiceAgentTTS
from backend.tts.profiles import (
    VOICE_PROFILES,
    VoiceProfile,
    VoiceProfileName,
    VoiceSettings,
    get_profile,
    list_profiles,
)

__all__ = [
    "MultiVoiceAgentTTS",
    "VoiceProfile",
    "VoiceProfileName",
    "VoiceSettings",
    "VOICE_PROFILES",
    "get_profile",
    "list_profiles",
]
