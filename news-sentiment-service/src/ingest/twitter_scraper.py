from .base_ingester import BaseIngester


class TwitterScraper(BaseIngester):
    async def fetch(self) -> dict:
        """Placeholder for Twitter/X scraping implementation."""
        return {"source": self.source_name, "items": []}
