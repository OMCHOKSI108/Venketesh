import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
import httpx
from dateutil import parser as date_parser
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc, func
from app.models.news import NewsArticle, SymbolSentiment, NewsSource
from app.services.sentiment_engine import sentiment_engine
from app.services.entity_mapper import entity_mapper
from app.services.cache import cache_service
from app.services.news_scraper import news_scraper
from app.core.logging_config import logger
from app.config import get_settings

settings = get_settings()

NEWS_CACHE_TTL = 180


class NewsService:
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self.finnhub_key = settings.finnhub_api_key

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _parse_date(self, date_str: str) -> datetime:
        if not date_str:
            return datetime.now(timezone.utc)
        try:
            if isinstance(date_str, datetime):
                return (
                    date_str.replace(tzinfo=timezone.utc)
                    if date_str.tzinfo is None
                    else date_str.astimezone(timezone.utc)
                )
            return date_parser.parse(date_str).astimezone(timezone.utc)
        except:
            return datetime.now(timezone.utc)

    async def fetch_all_news_sources(self) -> list[dict]:
        all_news = []

        try:
            scraped_news = await news_scraper.fetch_all()
            all_news.extend(scraped_news)
            logger.info("scraped_news_count", count=len(scraped_news))
        except Exception as e:
            logger.error("scraper_error", error=str(e))

        try:
            finnhub_news = await self._fetch_finnhub()
            all_news.extend(finnhub_news)
            logger.info("finnhub_news_count", count=len(finnhub_news))
        except Exception as e:
            logger.error("finnhub_error", error=str(e))

        all_news.sort(key=lambda x: self._parse_date(x.get("published_at", "")), reverse=True)

        return self._deduplicate(all_news)

    async def _fetch_finnhub(self) -> list[dict]:
        client = await self.get_client()
        news_items = []

        categories = ["general", "market", "forex"]
        for category in categories:
            try:
                response = await client.get(
                    "https://finnhub.io/api/v1/news",
                    params={"category": category, "token": self.finnhub_key},
                    timeout=15.0,
                )
                if response.status_code == 200:
                    items = response.json()
                    for item in items[:10]:
                        news_items.append(
                            {
                                "title": item.get("headline", ""),
                                "summary": item.get("summary", ""),
                                "source": item.get("source", "Finnhub"),
                                "url": item.get("url", ""),
                                "published_at": datetime.fromtimestamp(
                                    item.get("datetime", 0), tz=timezone.utc
                                ).isoformat()
                                if item.get("datetime")
                                else "",
                            }
                        )
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error("finnhub_category_error", category=category, error=str(e))

        return news_items

    def _deduplicate(self, articles: list[dict]) -> list[dict]:
        seen = set()
        unique = []
        for article in articles:
            title_lower = article.get("title", "").lower()[:100]
            if title_lower and title_lower not in seen:
                seen.add(title_lower)
                unique.append(article)
        return unique

    async def process_news_item(self, item: dict) -> Optional[NewsArticle]:
        try:
            title = item.get("title", "")
            summary = item.get("summary", "")
            source = item.get("source", "unknown")
            url = item.get("url", "")
            published_at = self._parse_date(item.get("published_at", ""))

            if not title:
                return None

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
            logger.error("process_news_error", error=str(e))
            return None

    async def fetch_and_store_news(self, db: Session) -> int:
        logger.info("fetching_news_start")

        news_items = await self.fetch_all_news_sources()
        stored_count = 0

        for item in news_items[:60]:
            try:
                title = item.get("title", "")[:500]
                if not title:
                    continue

                existing = db.execute(
                    select(func.count(NewsArticle.id)).where(
                        and_(
                            NewsArticle.title.like(f"{title[:100]}%"),
                            NewsArticle.source == item.get("source", "unknown"),
                        )
                    )
                ).scalar()

                if existing and existing > 0:
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
        self, db: Session, limit: int = 30, symbol: Optional[str] = None
    ) -> list[dict]:
        from sqlalchemy import cast, String

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

    async def get_cached_news(self, db: Session, limit: int = 30) -> list[dict]:
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
