from sqlalchemy import Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class NewsItem(Base):
    __tablename__ = "news_items"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(128), nullable=False)
    external_id = Column(String(256), unique=True, nullable=False)
    title = Column(String(512), nullable=True)
    text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    metadata = Column(JSON, nullable=True)


class NewsSentimentSnapshot(Base):
    __tablename__ = "news_sentiment_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    snapshot = Column(JSON, nullable=False)
