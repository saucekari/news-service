from sqlalchemy import Column, DateTime, Integer, JSON, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()


class Storage:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def init_db(self) -> None:
        Base.metadata.create_all(self.engine)

    def save_snapshot(self, payload: dict) -> None:
        with self.SessionLocal() as session:
            session.add(
                NewsSentimentSnapshot(
                    created_at=datetime.utcnow(),
                    snapshot=payload,
                )
            )
            session.commit()


class NewsSentimentSnapshot(Base):
    __tablename__ = "news_sentiment_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, nullable=False)
    snapshot = Column(JSON, nullable=False)
