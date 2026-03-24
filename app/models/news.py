from datetime import datetime
from sqlalchemy import BigInteger, String, DateTime, Text, Float, Boolean, Index, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class NewsArticle(Base, TimestampMixin):
    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sentiment_label: Mapped[str] = mapped_column(String(20), nullable=False, default="NEUTRAL")
    related_symbols: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("idx_news_published", "published_at"),
        Index("idx_news_source", "source"),
        Index("idx_news_sentiment", "sentiment_label"),
    )

    def __repr__(self):
        return f"<NewsArticle(id={self.id}, title={self.title[:50]}, sentiment={self.sentiment_label})>"


class SymbolSentiment(Base, TimestampMixin):
    __tablename__ = "symbol_sentiment"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    avg_sentiment_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sentiment_label: Mapped[str] = mapped_column(String(20), nullable=False, default="NEUTRAL")
    article_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bullish_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    bearish_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    neutral_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    weighted_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (Index("idx_sentiment_symbol_date", "symbol", "date"),)

    def __repr__(self):
        return f"<SymbolSentiment(symbol={self.symbol}, date={self.date}, label={self.sentiment_label})>"


class NewsSource(Base, TimestampMixin):
    __tablename__ = "news_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    url: Mapped[str] = mapped_column(String(500), nullable=True)
    credibility_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<NewsSource(name={self.name}, credibility={self.credibility_score})>"
