from typing import Dict


def apply_alignment(sentiment_a: float, direction: float, market_mood: float) -> float:
    """Apply directed adjustment to sentiment score."""
    return sentiment_a * direction + market_mood * 0.1
