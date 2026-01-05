"""ElevenLabs Speech-to-Text (Scribe) client wrapper.

Uses the ElevenLabs Scribe v1 model for transcription.
API Reference: https://elevenlabs.io/docs/api-reference/speech-to-text/convert
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import httpx

# Import config to trigger dotenv loading and env var resolution
from backend import config  # noqa: F401

logger = logging.getLogger(__name__)

ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
SCRIBE_MODEL_ID = "scribe_v1"


class ScribeError(Exception):
    """Error from ElevenLabs Scribe API."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Scribe API error {status_code}: {message}")


class ScribeClient:
    """Client for ElevenLabs Scribe v1 speech-to-text API."""

    def __init__(self):
        self.api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "ELEVENLABS_API_KEY not configured. "
                "Set RR_ELEVENLABS_API_KEY or ELEVENLABS_API_KEY environment variable."
            )

    async def transcribe(
        self,
        audio_path: Path,
        language_code: Optional[str] = None,
    ) -> dict[str, Any]:
        """Transcribe audio file using Scribe v1.

        Args:
            audio_path: Path to the audio file
            language_code: Optional language code (e.g., "en", "es").
                          If not provided, Scribe will auto-detect.

        Returns:
            Raw API response dict containing:
            - text: Transcribed text
            - words: List of word timings (if available)
            - language_code: Detected or specified language
            - transcription_id: Unique ID for this transcription

        Raises:
            ScribeError: If the API returns an error
        """
        logger.info(
            f"Transcribing audio: path={audio_path}, "
            f"size={audio_path.stat().st_size} bytes, "
            f"language={language_code or 'auto'}"
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(audio_path, "rb") as audio_file:
                # Build form data
                files = {"file": (audio_path.name, audio_file)}
                data: dict[str, str] = {"model_id": SCRIBE_MODEL_ID}

                if language_code:
                    data["language_code"] = language_code

                response = await client.post(
                    ELEVENLABS_STT_URL,
                    headers={"xi-api-key": self.api_key},
                    files=files,
                    data=data,
                )

        if response.status_code != 200:
            error_text = response.text
            logger.error(f"Scribe API error: {response.status_code} - {error_text}")
            raise ScribeError(response.status_code, error_text)

        result = response.json()
        transcript_text = result.get("text", "")

        logger.info(
            f"Transcription complete: {len(transcript_text)} chars, "
            f"language={result.get('language_code', 'unknown')}"
        )

        return result


# Lazy-initialized client singleton
_client: Optional[ScribeClient] = None


def get_scribe_client() -> ScribeClient:
    """Get or create ScribeClient (lazy singleton)."""
    global _client

    if _client is None:
        _client = ScribeClient()
        logger.info("ScribeClient initialized")

    return _client
