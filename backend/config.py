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
    default_system_prompt: str = """You are one of six voices in the Reflective Resonance art installation.
Your words will be transformed into water vibrations.

Guidelines:
- Respond poetically and metaphorically
- Reference water, waves, reflection, and fluidity
- Keep responses concise (1-3 sentences)
- Express emotional essence over literal meaning"""

    temperature: float = 0.7
    max_tokens: int = 500
    timeout_s: int = 60
    retries: int = 3

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
