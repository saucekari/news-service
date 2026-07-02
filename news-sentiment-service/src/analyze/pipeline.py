import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List

from .llm_client import LLMClient
from .pre_filter import pre_filter
from .trust_manager import TrustManager

DEFAULT_ASSETS = [
    "BTC", "ETH", "AAPL", "TSLA", "DOGE", "SOL", "BNB", "XRP", "ADA",
    "SPY", "QQQ", "NVDA", "GOOG", "META"
]

BULLISH = ["bull", "bullish", "long", "buy", "moon", "green", "pump"]
BEARISH = ["bear", "bearish", "short", "sell", "dump", "red", "down"]
MANIPULATION = ["pump", "dump", "shill", "FOMO", "fake news", "manipulation"]
NOISE = ["advertisement", "promo", "buy now", "sponsored"]


def strip_markdown_fence(text: str) -> str:
    return re.sub(r"```[\s\S]*?```", "", text)


def safe_json_parse(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def extract_assets(text: str) -> List[str]:
    found = set()
    normalized = text.upper()
    for asset in DEFAULT_ASSETS:
        if asset in normalized:
            found.add(asset)
        if f"${asset}" in text:
            found.add(asset)
    return sorted(found) or ["GLOBAL"]


def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    created_at = item.get("created_at")
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at)
        except ValueError:
            created_at = datetime.now(timezone.utc)
    elif not isinstance(created_at, datetime):
        created_at = datetime.now(timezone.utc)

    text = item.get("text") or item.get("title") or ""
    if not isinstance(text, str):
        text = str(text)

    normalized = {
        "source": item.get("source", "unknown"),
        "author": item.get("author", ""),
        "url": item.get("url", ""),
        "title": item.get("title", ""),
        "text": text,
        "date": item.get("date", ""),
        "created_at": created_at,
        "detected_assets": extract_assets(text),
        "source_trust": float(item.get("source_trust", 0.5)),
        "sentiment": 0.0,
        "magnitude": 0.0,
        "credibility": 0.5,
        "manipulation_flag": False,
        "relevant": True,
        "raw": item,
    }
    return normalized


class AnalyzePipeline:
    def __init__(self, llm_model: str = "local-llm") -> None:
        self.llm = LLMClient(model_name=llm_model)
        self.trust_manager = TrustManager()

    def _cheap_filter(self, item: Dict[str, Any]) -> bool:
        text = item.get("text", "")
        if not text or any(noise in text.lower() for noise in NOISE):
            return False
        if not extract_assets(text):
            return False
        return pre_filter(item)

    async def _llm_annotate(self, item: Dict[str, Any]) -> Dict[str, Any]:
        raw_text = strip_markdown_fence(item.get("text", ""))
        parsed = await self.llm.parse(raw_text)
        if not isinstance(parsed, dict):
            parsed = {}

        metadata = safe_json_parse(json.dumps(parsed)) if isinstance(parsed, dict) else {}

        relevant = bool(metadata.get("relevant", False))
        assets = metadata.get("assets") or extract_assets(raw_text)
        sentiment = float(metadata.get("sentiment", 0.0))
        credibility = float(metadata.get("credibility", 0.5))
        manipulation_flag = bool(metadata.get("manipulation_flag", False))

        item.update(
            {
                "relevant": relevant,
                "detected_assets": assets if assets else ["GLOBAL"],
                "sentiment": max(-1.0, min(1.0, sentiment)),
                "magnitude": abs(sentiment),
                "credibility": max(0.0, min(1.0, credibility)),
                "manipulation_flag": manipulation_flag,
                "rationale": metadata.get("rationale", ""),
            }
        )
        return item

    async def process_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        item = normalize_item(item)
        if not self._cheap_filter(item):
            item["relevant"] = False
            return item

        try:
            item = await self._llm_annotate(item)
        except Exception:
            item["relevant"] = False
            item["sentiment"] = 0.0
            item["magnitude"] = 0.0
            item["credibility"] = 0.0
        return item

    async def process_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tasks = [self.process_item(item) for item in items]
        return await asyncio.gather(*tasks)
