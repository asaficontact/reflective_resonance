"""Sentiment analysis using fast LLM with structured output."""

import asyncio
import logging

from rawagents import AsyncLLM, LLMConfig

from backend.config import settings
from backend.prompts import render_sentiment_prompt
from backend.sentiment.models import SentimentResult

logger = logging.getLogger(__name__)

_sentiment_llm: AsyncLLM | None = None


def get_sentiment_llm() -> AsyncLLM:
    """Get or create sentiment LLM client (lazy init)."""
    global _sentiment_llm
    if _sentiment_llm is None:
        _sentiment_llm = AsyncLLM(
            config=LLMConfig(
                model=settings.sentiment_model,
                retries=1,
                timeout=settings.sentiment_timeout_s,
            )
        )
        logger.info(f"Sentiment LLM initialized: {settings.sentiment_model}")
    return _sentiment_llm


async def analyze_sentiment(user_message: str) -> SentimentResult | None:
    """Analyze sentiment of user message.

    Args:
        user_message: The user's message to analyze.

    Returns:
        SentimentResult or None on error/timeout.
    """
    if not settings.sentiment_enabled:
        return None

    try:
        llm = get_sentiment_llm()
        prompt = render_sentiment_prompt(user_message)

        result: SentimentResult = await asyncio.wait_for(
            llm.complete_structured(
                messages=[{"role": "user", "content": prompt}],
                model=settings.sentiment_model,
                response_model=SentimentResult,
                temperature=settings.sentiment_temperature,
            ),
            timeout=settings.sentiment_timeout_s,
        )

        logger.info(f"Sentiment: {result.sentiment} - {result.justification[:50]}...")
        return result

    except asyncio.TimeoutError:
        logger.warning("Sentiment analysis timed out")
        return None
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        return None
