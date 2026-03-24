import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc
from app.models.news import NewsArticle, SymbolSentiment, NewsSource
from app.services.sentiment_engine import sentiment_engine
from app.services.entity_mapper import entity_mapper
from app.services.cache import cache_service
from app.core.logging_config import logger
from app.config import get_settings

settings = get_settings()

NEWS_CACHE_TTL = 300


class NewsService:
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self.finnhub_key = settings.finnhub_api_key
        self.alphavantage_key = settings.alphavantage_api_key

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_finnhub_news(self, category: str = "general") -> list[dict]:
        client = await self.get_client()
        try:
            response = await client.get(
                "https://finnhub.io/api/v1/news",
                params={"category": category, "token": self.finnhub_key},
                timeout=15.0,
            )
            if response.status_code == 200:
                return response.json()
            return []
        except Exception as e:
            logger.error("finnhub_news_error", error=str(e))
            return []

    async def fetch_market_news(self) -> list[dict]:
        news_items = []

        categories = ["market", "forex", "crypto"]
        for category in categories:
            items = await self.fetch_finnhub_news(category)
            news_items.extend(items)
            await asyncio.sleep(0.5)

        return news_items

    async def process_news_item(self, item: dict) -> Optional[NewsArticle]:
        try:
            title = item.get("headline", "")
            summary = item.get("summary", "")
            source = item.get("source", "unknown")
            url = item.get("url", "")
            published_at = (
                datetime.fromtimestamp(item.get("datetime", 0), tz=timezone.utc)
                if item.get("datetime")
                else datetime.now(timezone.utc)
            )

            sentiment = sentiment_engine.analyze_article(title, summary)
            related_symbols = entity_mapper.extract_symbols(f"{title} {summary}")

            return NewsArticle(
                title=title[:500],
                summary=summary[:1000] if summary else None,
                source=source,
                url=url if url else None,
                published_at=published_at,
                sentiment_score=sentiment["score"],
                sentiment_label=sentiment["label"],
                related_symbols=related_symbols,
                is_processed=True,
                fetched_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error("process_news_error", error=str(e), item=str(item)[:100])
            return None

    async def fetch_and_store_news(self, db: Session) -> int:
        logger.info("fetching_news_start")

        news_items = await self.fetch_market_news()
        stored_count = 0

        for item in news_items[:50]:
            try:
                existing = db.execute(
                    select(NewsArticle).where(
                        and_(
                            NewsArticle.title == item.get("headline", "")[:500],
                            NewsArticle.source == item.get("source", "unknown"),
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    continue

                article = await self.process_news_item(item)
                if article:
                    db.add(article)
                    stored_count += 1

            except Exception as e:
                logger.error("store_news_error", error=str(e))

        try:
            db.commit()
        except Exception as e:
            logger.error("db_commit_error", error=str(e))
            db.rollback()

        logger.info("fetching_news_complete", stored=stored_count)
        return stored_count

    async def get_recent_news(
        self, db: Session, limit: int = 20, symbol: Optional[str] = None
    ) -> list[dict]:
        from sqlalchemy import cast, String, text

        query = select(NewsArticle).order_by(desc(NewsArticle.published_at))

        if symbol:
            query = query.where(cast(NewsArticle.related_symbols, String).like(f'%"{symbol}"%'))

        query = query.limit(limit)
        result = db.execute(query)
        articles = result.scalars().all()

        return [
            {
                "id": a.id,
                "title": a.title,
                "summary": a.summary,
                "source": a.source,
                "url": a.url,
                "published_at": a.published_at.isoformat(),
                "sentiment_score": a.sentiment_score,
                "sentiment_label": a.sentiment_label,
                "related_symbols": a.related_symbols or [],
            }
            for a in articles
        ]

    async def compute_symbol_sentiment(self, db: Session, hours: int = 24) -> list[dict]:
        from sqlalchemy import cast, String
        from app.core.constants import SUPPORTED_SYMBOLS

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        results = []

        for symbol in SUPPORTED_SYMBOLS:
            articles = (
                db.execute(
                    select(NewsArticle).where(
                        and_(
                            cast(NewsArticle.related_symbols, String).like(f'%"{symbol}"%'),
                            NewsArticle.published_at >= cutoff,
                        )
                    )
                )
                .scalars()
                .all()
            )

            if not articles:
                results.append(
                    {
                        "symbol": symbol,
                        "sentiment_score": 0.0,
                        "sentiment_label": "NEUTRAL",
                        "article_count": 0,
                        "bullish_count": 0,
                        "bearish_count": 0,
                        "neutral_count": 0,
                    }
                )
                continue

            scores = [a.sentiment_score for a in articles]
            avg_score = sum(scores) / len(scores)
            label = sentiment_engine.get_sentiment_label(avg_score)

            bullish = sum(1 for a in articles if a.sentiment_label == "BULLISH")
            bearish = sum(1 for a in articles if a.sentiment_label == "BEARISH")
            neutral = sum(1 for a in articles if a.sentiment_label == "NEUTRAL")

            results.append(
                {
                    "symbol": symbol,
                    "sentiment_score": round(avg_score, 3),
                    "sentiment_label": label,
                    "article_count": len(articles),
                    "bullish_count": bullish,
                    "bearish_count": bearish,
                    "neutral_count": neutral,
                }
            )

        return results

    async def get_cached_news(self, db: Session, limit: int = 20) -> list[dict]:
        cached = await cache_service.get_json(f"news:recent:{limit}")
        if cached:
            return cached

        news = await self.get_recent_news(db, limit)
        if news:
            await cache_service.set(f"news:recent:{limit}", news, ttl=NEWS_CACHE_TTL)

        return news

    async def get_cached_sentiment(self, db: Session) -> list[dict]:
        cached = await cache_service.get_json("news:sentiment")
        if cached:
            return cached

        sentiment = await self.compute_symbol_sentiment(db)
        if sentiment:
            await cache_service.set("news:sentiment", sentiment, ttl=NEWS_CACHE_TTL)

        return sentiment


news_service = NewsService()
