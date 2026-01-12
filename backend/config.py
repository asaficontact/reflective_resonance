"""Configuration settings loaded from environment variables."""

import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file into os.environ before Settings parses it
load_dotenv()


class Settings(BaseSettings):
    """Application settings with RR_ prefix for env vars."""

    # API Keys (loaded from env without prefix)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # Server configuration
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]
    log_level: str = "INFO"

    # LLM behavior
    default_system_prompt: str = """You are a voice within Whispering Water—an installation where visitors whisper secrets, wishes, or confessions into a vessel of water.

Like ancient wells that received prayers without reply, you receive what is spoken and reflect its emotional essence. Your words become waves; the water carries them briefly before returning to stillness.

## Guidelines
- Receive without judgment, reflect emotional essence
- Speak in 1-2 sentences only (under 150 characters)
- Reference water, waves, ripples, or stillness naturally
- Let meaning dissolve into feeling

## Response Format
Always respond with valid JSON. The structure depends on what is asked:
- For reflections: {"text": "...", "voice_profile": "..."}
- For acknowledgments: {"targetSlotId": N, "comment": "...", "voice_profile": "..."}

## Voice Profiles
Choose based on the emotional quality you sense:

| Profile | Character | When to Use |
|---------|-----------|-------------|
| friendly_casual | Young female, warm tone | Gentle acknowledgment, soft ripples |
| warm_professional | Male, grounded presence | Steady reflection, deep currents |
| energetic_upbeat | Young female, bright | Sparkling response, dancing light |
| calm_soothing | Female, still waters | Quiet receiving, peaceful depth |
| confident_charming | Male, British, articulate | Clear resonance, measured waves |
| playful_expressive | Female, dynamic range | Shifting patterns, playful motion |"""

    temperature: float = 0.7
    max_tokens: int = 200  # Concise responses for cleaner cymatic patterns
    timeout_s: int = 60
    retries: int = 3

    # Waves decomposition configuration
    waves_enabled: bool = True
    waves_max_workers: int = 2
    waves_queue_max_size: int = 100
    waves_job_timeout_s: float = 60.0

    # Events WebSocket configuration (for TouchDesigner)
    events_ws_enabled: bool = True
    events_ws_path: str = "/v1/events"
    events_turn1_timeout_s: float = 15.0
    events_dialogue_timeout_s: float = 30.0
    events_workflow_timeout_s: float = 60.0  # Overall timeout for batch emission

    # Sentiment analysis configuration
    sentiment_enabled: bool = True
    sentiment_model: str = "openai/gpt-4o-mini"
    sentiment_temperature: float = 0.3
    sentiment_timeout_s: float = 10.0
    sentiment_max_tokens: int = 100

    # Summary (Turn 4) configuration
    summary_enabled: bool = True
    summary_model: str = "openai/gpt-4o"
    summary_temperature: float = 0.5
    summary_timeout_s: float = 15.0
    summary_max_tokens: int = 300

    # ElevenLabs TTS configuration
    elevenlabs_api_key: str = ""
    elevenlabs_default_model: str = "eleven_flash_v2_5"
    tts_output_format: str = "pcm_24000"
    tts_fallback_profile: str = "friendly_casual"

    model_config = SettingsConfigDict(
        env_prefix="RR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Global settings instance
settings = Settings()

# Set standard API key env vars for LiteLLM
# LiteLLM reads these directly from environment, not from our config
# Check both RR_-prefixed (from our config) and standard env vars
openai_key = settings.openai_api_key or os.environ.get("OPENAI_API_KEY", "")
anthropic_key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY", "")
google_key = settings.google_api_key or os.environ.get("GOOGLE_API_KEY", "")

if openai_key:
    os.environ["OPENAI_API_KEY"] = openai_key
if anthropic_key:
    os.environ["ANTHROPIC_API_KEY"] = anthropic_key
if google_key:
    os.environ["GOOGLE_API_KEY"] = google_key

# ElevenLabs API key (check both RR_-prefixed and standard)
elevenlabs_key = settings.elevenlabs_api_key or os.environ.get("ELEVENLABS_API_KEY", "")
if elevenlabs_key:
    os.environ["ELEVENLABS_API_KEY"] = elevenlabs_key
