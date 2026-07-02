from datetime import datetime
from math import exp
from typing import Dict


def compute_decay(created_at: datetime, tau_seconds: float) -> float:
    delta = (datetime.utcnow() - created_at).total_seconds()
    return exp(-delta / tau_seconds)


def compute_sentiment_score(data: Dict[str, float]) -> float:
    return data.get("sentiment", 0.0) * data.get("weight", 1.0)
