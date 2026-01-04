"""Voice profile definitions for the 6 Reflective Resonance agents."""

from typing import Literal

from pydantic import BaseModel

VoiceProfileName = Literal[
    "friendly_casual",
    "warm_professional",
    "energetic_upbeat",
    "calm_soothing",
    "confident_charming",
    "playful_expressive",
]


class VoiceSettings(BaseModel):
    """Voice settings for ElevenLabs TTS generation."""

    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True
    speed: float = 1.0


class VoiceProfile(BaseModel):
    """Complete voice profile definition."""

    name: VoiceProfileName
    voice_id: str
    voice_name: str
    description: str
    model_id: str = "eleven_flash_v2_5"
    settings: VoiceSettings


VOICE_PROFILES: dict[VoiceProfileName, VoiceProfile] = {
    "friendly_casual": VoiceProfile(
        name="friendly_casual",
        voice_id="cgSgspJ2msm6clMCkdW9",  # Jessica
        voice_name="Jessica",
        description="Young female, American, expressive, conversational",
        settings=VoiceSettings(
            stability=0.45,
            similarity_boost=0.75,
            style=0.15,
            speed=1.0,
        ),
    ),
    "warm_professional": VoiceProfile(
        name="warm_professional",
        voice_id="cjVigY5qzO86Huf0OWal",  # Eric
        voice_name="Eric",
        description="Middle-aged male, American, friendly, professional",
        settings=VoiceSettings(
            stability=0.55,
            similarity_boost=0.75,
            style=0.1,
            speed=0.95,
        ),
    ),
    "energetic_upbeat": VoiceProfile(
        name="energetic_upbeat",
        voice_id="FGY2WhTYpPnrIDTdsKH5",  # Laura
        voice_name="Laura",
        description="Young female, American, upbeat, energetic",
        settings=VoiceSettings(
            stability=0.35,
            similarity_boost=0.75,
            style=0.25,
            speed=1.05,
        ),
    ),
    "calm_soothing": VoiceProfile(
        name="calm_soothing",
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Rachel
        voice_name="Rachel",
        description="Young female, American, calm, pleasant",
        settings=VoiceSettings(
            stability=0.65,
            similarity_boost=0.75,
            style=0.05,
            speed=0.92,
        ),
    ),
    "confident_charming": VoiceProfile(
        name="confident_charming",
        voice_id="JBFqnCBsd6RMkjVDRZzb",  # George
        voice_name="George",
        description="Middle-aged male, British, warm, articulate",
        settings=VoiceSettings(
            stability=0.50,
            similarity_boost=0.75,
            style=0.15,
            speed=0.98,
        ),
    ),
    "playful_expressive": VoiceProfile(
        name="playful_expressive",
        voice_id="EXAVITQu4vr4xnSDxMaL",  # Bella/Sarah
        voice_name="Sarah",
        description="Young female, expressive, dynamic range",
        settings=VoiceSettings(
            stability=0.30,
            similarity_boost=0.75,
            style=0.30,
            speed=1.0,
        ),
    ),
}


def get_profile(name: str) -> VoiceProfile:
    """Get profile by name, raise ValueError if not found."""
    if name not in VOICE_PROFILES:
        raise ValueError(f"Unknown profile: {name}. Available: {list(VOICE_PROFILES.keys())}")
    return VOICE_PROFILES[name]


def list_profiles() -> list[str]:
    """List all available profile names."""
    return list(VOICE_PROFILES.keys())
