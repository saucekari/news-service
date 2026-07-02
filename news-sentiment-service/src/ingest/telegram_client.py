from .base_ingester import BaseIngester


class TelegramClient(BaseIngester):
    async def fetch(self) -> dict:
        """Placeholder for Telethon channel ingestion."""
        return {"source": self.source_name, "items": []}
