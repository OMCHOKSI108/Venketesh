from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.services.database import get_db
from app.services.aggregator import aggregator_service
from app.core.constants import SUPPORTED_SYMBOLS
from app.core.logging_config import logger

router = APIRouter(prefix="/indices", tags=["Indices"])


@router.get("")
async def get_all_indices(
    limit: int = Query(10, ge=1, le=100, description="Number of indices to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    symbols = SUPPORTED_SYMBOLS[offset : offset + limit]
    total = len(SUPPORTED_SYMBOLS)

    results = []
    for symbol in symbols:
        ohlc = await aggregator_service.get_latest(db, symbol, "1d")

        if ohlc:
            results.append(
                {
                    "symbol": ohlc.symbol,
                    "exchange": _get_exchange(symbol),
                    "name": _get_name(symbol),
                    "price": float(ohlc.close),
                    "open": float(ohlc.open),
                    "high": float(ohlc.high),
                    "low": float(ohlc.low),
                    "change": float(ohlc.close - ohlc.open),
                    "change_percent": round(
                        float((ohlc.close - ohlc.open) / ohlc.open * 100) if ohlc.open > 0 else 0,
                        2,
                    ),
                    "volume": ohlc.volume,
                    "source": ohlc.source,
                    "timestamp": ohlc.timestamp.isoformat(),
                }
            )
        else:
            results.append(
                {
                    "symbol": symbol,
                    "exchange": _get_exchange(symbol),
                    "name": _get_name(symbol),
                    "price": 0,
                    "open": 0,
                    "high": 0,
                    "low": 0,
                    "change": 0,
                    "change_percent": 0,
                    "volume": 0,
                    "source": "none",
                    "timestamp": None,
                }
            )

    return {
        "data": results,
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "count": len(results),
        },
    }


def _get_exchange(symbol: str) -> str:
    exchange_map = {
        "NIFTY": "NSE",
        "BANKNIFTY": "NSE",
        "SENSEX": "BSE",
        "NIFTYIT": "NSE",
        "DOWJONES": "NYSE",
        "NASDAQ": "NASDAQ",
        "SP500": "NYSE",
        "FTSE": "LSE",
        "DAX": "XETRA",
        "NIKKEI": "TSE",
        "N225": "TSE",
    }
    return exchange_map.get(symbol, "UNKNOWN")


def _get_name(symbol: str) -> str:
    name_map = {
        "NIFTY": "NIFTY 50",
        "BANKNIFTY": "NIFTY Bank",
        "SENSEX": "BSE Sensex",
        "NIFTYIT": "NIFTY IT",
        "DOWJONES": "Dow Jones",
        "NASDAQ": "NASDAQ 100",
        "SP500": "S&P 500",
        "FTSE": "FTSE 100",
        "DAX": "DAX",
        "NIKKEI": "Nikkei 225",
        "N225": "Nikkei 225",
    }
    return name_map.get(symbol, symbol)
