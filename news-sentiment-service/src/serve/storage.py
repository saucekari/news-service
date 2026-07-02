import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    Float,
    JSON,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


class Storage:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)

    def save_news_item(self, payload: Dict[str, Any]) -> None:
        with self.SessionLocal() as session:
            item = NewsItem(
                source=payload.get("source", "unknown"),
                external_id=payload.get("external_id", payload.get("url", "")),
                title=payload.get("title"),
                text=payload.get("text"),
                url=payload.get("url", ""),
                created_at=payload.get("created_at", datetime.now(timezone.utc)),
                source_trust=float(payload.get("source_trust", 0.5)),
                detected_assets=payload.get("detected_assets", []),
                sentiment=float(payload.get("sentiment", 0.0)),
                magnitude=float(payload.get("magnitude", 0.0)),
                credibility=float(payload.get("credibility", 0.5)),
                manipulation_flag=bool(payload.get("manipulation_flag", False)),
                dedup_hash=payload.get("dedup_hash", ""),
                asset_class=payload.get("asset_class", "global"),
                metadata_json=payload.get("metadata", {}),
            )
            session.add(item)
            session.commit()

    def save_snapshot(self, payload: Dict[str, Any]) -> None:
        with self.SessionLocal() as session:
            session.add(
                NewsSentimentSnapshot(
                    asset=payload.get("asset", "GLOBAL"),
                    asset_class=payload.get("asset_class", "global"),
                    bucket_ts=payload.get("bucket_ts", datetime.now(timezone.utc)),
                    created_at=datetime.now(timezone.utc),
                    sentiment=payload.get("sentiment", 0.0),
                    news_volume=payload.get("news_volume", 0.0),
                    market_mood=payload.get("market_mood", 0.0),
                    top_sources=payload.get("top_sources", []),
                    snapshot=self._make_json_serializable(payload),
                )
            )
            session.commit()

    def _make_json_serializable(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._make_json_serializable(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._make_json_serializable(v) for v in value]
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def get_latest_snapshot(self, asset: str) -> Optional[Dict[str, Any]]:
        with self.SessionLocal() as session:
            record = (
                session.query(NewsSentimentSnapshot)
                .filter(NewsSentimentSnapshot.asset == asset)
                .order_by(NewsSentimentSnapshot.bucket_ts.desc())
                .first()
            )
            if record:
                return {
                    "asset": record.asset,
                    "asset_class": record.asset_class,
                    "bucket_ts": record.bucket_ts.isoformat(),
                    "sentiment": record.sentiment,
                    "news_volume": record.news_volume,
                    "market_mood": record.market_mood,
                    "top_sources": record.top_sources,
                    "snapshot": record.snapshot,
                }
            return None


class NewsItem(Base):
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(128), nullable=False)
    external_id = Column(String(256), unique=True, nullable=False)
    title = Column(String(512), nullable=True)
    text = Column(Text, nullable=True)
    url = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False)
    source_trust = Column(Float, nullable=False)
    detected_assets = Column(JSON, nullable=True)
    sentiment = Column(Float, nullable=False)
    magnitude = Column(Float, nullable=False)
    credibility = Column(Float, nullable=False)
    manipulation_flag = Column(Boolean, nullable=False, default=False)
    dedup_hash = Column(String(256), nullable=True)
    asset_class = Column(String(64), nullable=False, default="global")
    metadata_json = Column(JSON, nullable=True)


class NewsSentimentSnapshot(Base):
    __tablename__ = "news_sentiment_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    asset = Column(String(64), nullable=False, index=True)
    asset_class = Column(String(64), nullable=False, default="global")
    bucket_ts = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False)
    sentiment = Column(Float, nullable=False)
    news_volume = Column(Float, nullable=False)
    market_mood = Column(Float, nullable=False)
    top_sources = Column(JSON, nullable=True)
    snapshot = Column(JSON, nullable=False)
