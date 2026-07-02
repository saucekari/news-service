from datetime import datetime, timezone
from math import exp, tanh
from typing import Dict, Iterable, List


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def compute_recency_weight(created_at: datetime, tau_seconds: float) -> float:
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    delta = (now - created_at).total_seconds()
    return exp(-delta / tau_seconds) if tau_seconds > 0 else 1.0


def aggregate_asset_scores(items: Iterable[Dict[str, float]], tau_seconds: float = 300.0) -> Dict[str, float]:
    sentiment_weight_sum = 0.0
    weight_sum = 0.0

    for item in items:
        if not item.get("relevant", False):
            continue
        sentiment = float(item.get("sentiment", 0.0))
        credibility = float(item.get("credibility", 0.5))
        source_trust = float(item.get("source_trust", 0.5))
        magnitude = abs(sentiment)
        created_at = item.get("created_at")
        if not hasattr(created_at, "isoformat"):
            created_at = datetime.now(timezone.utc)

        recency = compute_recency_weight(created_at, tau_seconds)
        weight = recency * source_trust * magnitude * credibility
        sentiment_weight_sum += sentiment * weight
        weight_sum += weight

    sentiment_a = sentiment_weight_sum / weight_sum if weight_sum else 0.0
    return {
        "sentiment": max(-1.0, min(1.0, sentiment_a)),
        "news_volume": weight_sum,
        "top_sources": 0,
    }


def compute_market_mood(items: Iterable[Dict[str, float]], tau_seconds: float = 900.0) -> float:
    positive = 0.0
    negative = 0.0

    for item in items:
        if not item.get("relevant", False):
            continue
        sentiment = float(item.get("sentiment", 0.0))
        created_at = item.get("created_at")
        if not hasattr(created_at, "isoformat"):
            created_at = datetime.now(timezone.utc)
        recency = compute_recency_weight(created_at, tau_seconds)
        if sentiment >= 0:
            positive += sentiment * recency
        else:
            negative += abs(sentiment) * recency

    if positive + negative == 0:
        return 0.0
    return clamp((positive - negative) / (positive + negative), -1.0, 1.0)


def compute_directional_score(sentiment_a: float, direction: float, news_volume: float, max_score: float = 1.0) -> float:
    alignment = direction * sentiment_a
    volume_factor = tanh(news_volume / 10.0)
    return clamp(alignment * volume_factor, -max_score, max_score)


def aggregate_by_asset(items: List[Dict[str, float]], tau_seconds: float = 300.0) -> Dict[str, Dict[str, float]]:
    buckets: Dict[str, List[Dict[str, float]]] = {}
    for item in items:
        if not item.get("relevant", False):
            continue
        assets = item.get("detected_assets", ["GLOBAL"])
        if not isinstance(assets, list):
            assets = [assets]
        for asset in assets:
            buckets.setdefault(asset, []).append(item)

    return {
        asset: aggregate_asset_scores(bucket, tau_seconds)
        for asset, bucket in buckets.items()
    }
