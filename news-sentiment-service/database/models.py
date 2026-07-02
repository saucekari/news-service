from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text, Boolean
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone

Base = declarative_base()


class NewsItem(Base):
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(128), nullable=False)
    external_id = Column(String(256), unique=True, nullable=False)
    title = Column(String(512), nullable=True)
    text = Column(Text, nullable=True)
    url = Column(String(1024), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    source_trust = Column(Float, nullable=False, default=0.5)
    detected_assets = Column(JSON, nullable=True)
    sentiment = Column(Float, nullable=False, default=0.0)
    magnitude = Column(Float, nullable=False, default=0.0)
    credibility = Column(Float, nullable=False, default=0.5)
    manipulation_flag = Column(Boolean, nullable=False, default=False)
    dedup_hash = Column(String(256), nullable=True)
    asset_class = Column(String(64), nullable=False, default="global")
    metadata_json = Column(JSON, nullable=True)


class NewsSentimentSnapshot(Base):
    __tablename__ = "news_sentiment_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    asset = Column(String(64), nullable=False, index=True)
    asset_class = Column(String(64), nullable=False, default="global")
    bucket_ts = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    sentiment = Column(Float, nullable=False, default=0.0)
    news_volume = Column(Float, nullable=False, default=0.0)
    market_mood = Column(Float, nullable=False, default=0.0)
    top_sources = Column(JSON, nullable=True)
    snapshot = Column(JSON, nullable=False)
