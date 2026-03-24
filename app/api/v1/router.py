from fastapi import APIRouter
from app.api.v1.endpoints import (
    ohlc,
    symbols,
    health,
    etl,
    insights,
    scheduler,
    indices,
    news,
    prediction,
)

api_router = APIRouter()

api_router.include_router(ohlc.router)
api_router.include_router(symbols.router)
api_router.include_router(health.router)
api_router.include_router(etl.router)
api_router.include_router(insights.router)
api_router.include_router(scheduler.router)
api_router.include_router(indices.router)
api_router.include_router(news.router)
api_router.include_router(prediction.router)
