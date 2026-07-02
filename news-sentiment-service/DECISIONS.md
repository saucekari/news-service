# DECISIONS

- `Analyze` pipeline uses a local heuristic parser as a stand-in for the LLM layer until a proper local model is integrated.
- `RSSParser` and `RedditParser` were implemented as isolated source modules with headless browser support and fallback HTML parsing.
- `Storage` and `database/models.py` now include richer `NewsItem` and `NewsSentimentSnapshot` schemas aligned with news sentiment feature requirements.
- `RabbitPublisher` uses `aio-pika` to publish durable JSON messages to `data.news.sentiment` when `RABBITMQ_URL` is configured.
- `main.py` currently demonstrates the end-to-end flow locally, persisting snapshots to SQLite and optionally publishing snapshots.
- Non-standard service integration choices are explicitly documented here rather than hidden in code comments.
