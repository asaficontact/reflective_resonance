"""Pydantic models for sentiment analysis."""

from typing import Literal

from pydantic import BaseModel, Field

SentimentValue = Literal["positive", "neutral", "negative"]


class SentimentResult(BaseModel):
    """Structured output from sentiment analysis LLM."""

    sentiment: SentimentValue = Field(description="The overall emotional tone")
    justification: str = Field(
        min_length=1,
        max_length=200,
        description="Brief explanation of sentiment determination",
    )
