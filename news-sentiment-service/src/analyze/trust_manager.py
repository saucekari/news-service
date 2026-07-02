from typing import Dict


class TrustManager:
    def adjust_trust(self, source_trust: float, backtest_score: float) -> float:
        """Adaptive backtest scoring for source trust."""
        return max(0.0, min(1.0, source_trust * 0.5 + backtest_score * 0.5))
