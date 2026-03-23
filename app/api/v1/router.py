from fastapi import APIRouter
from app.api.v1.endpoints import ohlc, symbols, health

api_router = APIRouter()

api_router.include_router(ohlc.router)
api_router.include_router(symbols.router)
api_router.include_router(health.router)
