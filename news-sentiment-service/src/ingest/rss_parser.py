from .base_ingester import BaseIngester


class RSSParser(BaseIngester):
    async def fetch(self) -> dict:
        """Placeholder for RSS feed parsing of CoinDesk / Cointelegraph."""
        return {"source": self.source_name, "items": []}
