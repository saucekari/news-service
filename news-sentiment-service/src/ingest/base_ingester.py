import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Optional


class BaseIngester(ABC):
    def __init__(self, source_name: str, rate_limit: int = 60) -> None:
        self.source_name = source_name
        self.rate_limit = rate_limit
        self.last_run: Optional[datetime] = None

    @abstractmethod
    async def fetch(self) -> Any:
        raise NotImplementedError

    async def deduplicate(self, item: Dict[str, Any]) -> bool:
        return False

    async def run(self) -> Any:
        self.last_run = datetime.utcnow()
        await asyncio.sleep(0)
        return await self.fetch()
