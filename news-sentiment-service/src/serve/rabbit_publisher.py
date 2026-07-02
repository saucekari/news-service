from typing import Any, Dict


class RabbitPublisher:
    def __init__(self, amqp_url: str) -> None:
        self.amqp_url = amqp_url

    async def publish(self, snapshot: Dict[str, Any]) -> None:
        """Publish a snapshot to data.news.sentiment."""
        print(f"Publish snapshot to RabbitMQ: {snapshot}")
