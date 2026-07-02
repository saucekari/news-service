import asyncio
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyze.pipeline import AnalyzePipeline
from score.pipeline import aggregate_by_asset, compute_market_mood
from serve.rabbit_publisher import RabbitPublisher
from serve.storage import Storage


async def main() -> None:
    """Entry point for news-sentiment-service."""
    print("Starting news-sentiment-service...")
    print("This repository contains ingest, analyze, score and serve layers.")

    sample_items = [
        {
            "source": "reddit:r/bitcoin",
            "author": "crypto_whale",
            "title": "BTC is ready to moon",
            "text": "BTC looks bullish and ready to break out, long setup for $BTC.",
            "url": "https://old.reddit.com/r/bitcoin/post/1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_trust": 0.7,
        },
        {
            "source": "coindesk",
            "author": "newsdesk",
            "title": "Bitcoin price down on macro concerns",
            "text": "Macro pressure shows risk-off sentiment across crypto markets.",
            "url": "https://www.coindesk.com/article/1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_trust": 0.5,
        },
    ]

    analyzer = AnalyzePipeline()
    annotated = await analyzer.process_items(sample_items)
    asset_scores = aggregate_by_asset(annotated)
    market_mood = compute_market_mood(annotated)

    print("Annotated items:")
    for item in annotated:
        print(item)

    print("Asset score buckets:")
    print(asset_scores)
    print("Market mood:", market_mood)

    storage = Storage(database_url="sqlite:///./news_sentiment_service.db")
    storage.init_db()

    for asset, values in asset_scores.items():
        snapshot_payload = {
            "asset": asset,
            "asset_class": "crypto" if asset != "GLOBAL" else "global",
                "bucket_ts": datetime.now(timezone.utc),
            "sentiment": values["sentiment"],
            "news_volume": values["news_volume"],
            "market_mood": market_mood,
            "top_sources": [],
            "snapshot": {
                "asset": asset,
                "sentiment": values["sentiment"],
                "news_volume": values["news_volume"],
                "market_mood": market_mood,
            },
        }
        storage.save_snapshot(snapshot_payload)

    rabbit_url = os.getenv("RABBITMQ_URL")
    if rabbit_url:
        publisher = RabbitPublisher(amqp_url=rabbit_url)
        print("Publishing snapshots to RabbitMQ...")
        for asset, values in asset_scores.items():
            snapshot_payload = {
                "asset": asset,
                "asset_class": "crypto" if asset != "GLOBAL" else "global",
                "bucket_ts": datetime.now(timezone.utc).isoformat(),
                "sentiment": values["sentiment"],
                "news_volume": values["news_volume"],
                "market_mood": market_mood,
            }
            await publisher.publish(snapshot_payload)
    else:
        print("RABBITMQ_URL not set, skipping RabbitMQ publish.")


if __name__ == "__main__":
    asyncio.run(main())
