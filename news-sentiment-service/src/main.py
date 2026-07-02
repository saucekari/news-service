import asyncio

from src.ingest.base_ingester import BaseIngester
from src.analyze.pre_filter import pre_filter
from src.score.calculator import compute_sentiment_score


async def main() -> None:
    """Entry point for news-sentiment-service."""
    print("Starting news-sentiment-service...")
    print("This repository contains ingest, analyze, score and serve layers.")
    await asyncio.sleep(0.1)


if __name__ == "__main__":
    asyncio.run(main())
