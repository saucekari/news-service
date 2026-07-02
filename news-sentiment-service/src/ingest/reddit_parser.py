from .base_ingester import BaseIngester


class RedditParser(BaseIngester):
    async def fetch(self) -> dict:
        """Placeholder for Reddit JSON endpoint ingestion."""
        return {"source": self.source_name, "items": []}
