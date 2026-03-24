from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.services.database import get_db
from app.services.news_service import news_service

router = APIRouter(prefix="/news", tags=["News"])


@router.get("")
async def get_news(
    limit: int = Query(20, ge=1, le=100, description="Number of articles to return"),
    symbol: Optional[str] = Query(None, description="Filter by related symbol"),
    db: Session = Depends(get_db),
):
    news = await news_service.get_cached_news(db, limit)

    if symbol:
        symbol = symbol.upper()
        news = [n for n in news if symbol in (n.get("related_symbols") or [])]

    return {
        "data": news,
        "meta": {
            "count": len(news),
            "limit": limit,
            "symbol_filter": symbol,
        },
    }


@router.get("/sentiment")
async def get_sentiment(db: Session = Depends(get_db)):
    sentiment = await news_service.get_cached_sentiment(db)

    return {
        "data": sentiment,
        "meta": {
            "count": len(sentiment),
            "hours": 24,
        },
    }


@router.get("/sentiment/{symbol}")
async def get_symbol_sentiment(symbol: str, db: Session = Depends(get_db)):
    symbol = symbol.upper()
    sentiment = await news_service.get_cached_sentiment(db)

    for s in sentiment:
        if s["symbol"] == symbol:
            return s

    return {
        "symbol": symbol,
        "sentiment_score": 0.0,
        "sentiment_label": "NEUTRAL",
        "article_count": 0,
    }


@router.post("/fetch")
async def fetch_news(db: Session = Depends(get_db)):
    count = await news_service.fetch_and_store_news(db)
    return {
        "status": "completed",
        "articles_added": count,
    }
