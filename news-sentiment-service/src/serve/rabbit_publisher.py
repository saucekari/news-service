import json
from typing import Any, Dict

try:
    import aio_pika
    from aio_pika import DeliveryMode
    AIO_PIKA_AVAILABLE = True
except ImportError:
    aio_pika = None
    DeliveryMode = None
    AIO_PIKA_AVAILABLE = False


class RabbitPublisher:
    def __init__(self, amqp_url: str) -> None:
        self.amqp_url = amqp_url

    async def publish(self, snapshot: Dict[str, Any]) -> None:
        """Publish a snapshot to data.news.sentiment."""
        if not AIO_PIKA_AVAILABLE:
            print("[news] RabbitPublisher: aio-pika not installed, skipping publish.")
            return

        connection = await aio_pika.connect_robust(self.amqp_url)
        async with connection:
            channel = await connection.channel()
            await channel.declare_queue("data.news.sentiment", durable=True)
            message = aio_pika.Message(
                body=json.dumps(snapshot, ensure_ascii=False).encode("utf-8"),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
            )
            await channel.default_exchange.publish(
                message,
                routing_key="data.news.sentiment",
            )
