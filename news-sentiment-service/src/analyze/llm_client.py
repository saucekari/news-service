from typing import Dict


class LLMClient:
    def __init__(self, model_name: str = "local-llm") -> None:
        self.model_name = model_name

    async def parse(self, text: str) -> Dict[str, str]:
        """Basic local heuristic parser for sentiment/asset structure."""
        cleaned = text.strip()
        lowered = cleaned.lower()
        sentiment = 0.0
        if any(word in lowered for word in ["bull", "bullish", "long", "buy", "moon", "green"]):
            sentiment += 0.6
        if any(word in lowered for word in ["bear", "bearish", "short", "sell", "dump", "red", "down"]):
            sentiment -= 0.6
        if any(word in lowered for word in ["risk-off", "risk off", "macro pressure", "uncertainty", "volatility"]):
            sentiment -= 0.2
        if any(word in lowered for word in ["breakout", "recovery", "rally", "bounce"]):
            sentiment += 0.2

        manipulation_flag = bool(any(word in lowered for word in ["pump", "dump", "shill", "fake news", "FOMO", "manipulation"]))
        credibility = 0.45 if manipulation_flag else 0.75
        if "breaking" in lowered or "official" in lowered:
            credibility = min(1.0, credibility + 0.15)

        assets = []
        for token in ["BTC", "ETH", "AAPL", "TSLA", "DOGE", "SOL", "BNB", "XRP", "ADA", "SPY", "QQQ", "NVDA", "GOOG", "META"]:
            if token.lower() in lowered or f"${token.lower()}" in lowered:
                assets.append(token)
        if not assets:
            assets = ["GLOBAL"]

        relevant = sentiment != 0.0 or any(asset != "GLOBAL" for asset in assets)
        rationale = "heuristic sentiment parser"

        return {
            "relevant": relevant,
            "assets": assets,
            "sentiment": max(-1.0, min(1.0, sentiment)),
            "manipulation_flag": manipulation_flag,
            "credibility": credibility,
            "rationale": rationale,
        }
