#!/usr/bin/env python3
"""Demo script to generate WAV files for all 6 voice profiles."""

import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env from project root before importing backend modules
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from backend.tts import MultiVoiceAgentTTS, get_profile, list_profiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Sample texts that showcase each profile's character
DEMO_TEXTS = {
    "friendly_casual": "Hey! So nice to meet you! How's your day going?",
    "warm_professional": "That's a great question. Let me walk you through the key points.",
    "energetic_upbeat": "Oh my gosh, that's amazing! I'm so happy for you!",
    "calm_soothing": "I understand. Take your time, there's no rush at all.",
    "confident_charming": "Well, well, well. Isn't that rather delightful?",
    "playful_expressive": "Aww, you're so sweet! That really made my day!",
}


def main() -> int:
    output_dir = Path("artifacts/tts/phase1")
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("MultiVoiceAgentTTS Phase 1 Demo")
    logger.info("=" * 60)

    tts = MultiVoiceAgentTTS()
    profiles = list_profiles()

    logger.info(f"Available profiles: {profiles}")
    logger.info(f"Output directory: {output_dir.absolute()}")
    logger.info("")

    success_count = 0

    for profile_name in profiles:
        profile = get_profile(profile_name)
        text = DEMO_TEXTS.get(profile_name, "Hello, this is a test.")
        output_path = output_dir / f"{profile_name}.wav"

        logger.info(f"Generating: {profile_name}")
        logger.info(f"  Voice: {profile.voice_name}")
        logger.info(f"  Voice ID: {profile.voice_id}")
        logger.info(f"  Model: {profile.model_id}")
        logger.info(f"  Text: \"{text}\"")

        try:
            result_path = tts.generate_wav_to_file(text, profile_name, output_path)
            file_size = result_path.stat().st_size
            logger.info(f"  Output: {result_path} ({file_size:,} bytes)")
            logger.info("  SUCCESS")
            success_count += 1
        except Exception as e:
            logger.error(f"  FAILED: {e}")

        logger.info("")

    logger.info("=" * 60)
    logger.info(f"Results: {success_count}/{len(profiles)} profiles generated successfully")
    logger.info("=" * 60)

    if success_count == len(profiles):
        logger.info("Phase 1 Demo PASSED - All WAV files generated!")
        return 0
    else:
        logger.error("Phase 1 Demo FAILED - Some profiles could not be generated")
        return 1


if __name__ == "__main__":
    sys.exit(main())
