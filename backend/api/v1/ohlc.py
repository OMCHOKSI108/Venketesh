"""OHLC API endpoints.

Project: Pseudo-Live Indian Index Market Data Platform
Version: 1.0
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from backend.core.models import OHLCData
from backend.core.memory_cache import memory_cache

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ohlc"])

DEFAULT_TIMEFRAME = "1m"
DEFAULT_LIMIT = 100
MAX_LIMIT = 1000


class OHLCResponse(BaseModel):
    """OHLC API response."""

    symbol: str
    timeframe: str
    data: list[dict]
    meta: dict


class LatestCandleResponse(BaseModel):
    """Latest candle response."""

    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[int] = None
    is_closed: bool
    source: str


@router.get("/ohlc/{symbol}", response_model=OHLCResponse)
async def get_ohlc(
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME, pattern="^[0-9]+[mhd]$"),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
) -> OHLCResponse:
    """Get OHLC data for a symbol.

    Fetches from in-memory cache, or calls the data source directly if cache is empty.
    Tries NSE first, falls back to Yahoo if NSE fails.

    Args:
        symbol: Market symbol (e.g., 'NIFTY', 'BANKNIFTY')
        timeframe: Time resolution (e.g., '1m', '5m', '1h')
        limit: Maximum number of candles to return

    Returns:
        OHLC data response
    """
    try:
        candles = await memory_cache.get(symbol.upper(), timeframe)

        if not candles:
            logger.info(
                "Cache miss, fetching from source",
                extra={"symbol": symbol, "timeframe": timeframe},
            )

            from backend.adapters.yahoo import YahooAdapter

            try:
                adapter = YahooAdapter()
                raw_data = await adapter.fetch(symbol.upper())
                logger.info(
                    "Fetched from Yahoo",
                    extra={"symbol": symbol, "count": len(raw_data)},
                )
            except Exception as e:
                logger.error(
                    "All adapters failed",
                    extra={"symbol": symbol, "error": str(e)},
                )
                raise HTTPException(status_code=503, detail="All data sources failed")

            for raw in raw_data:
                try:
                    candle = OHLCData(**raw)
                    await memory_cache.append(symbol.upper(), timeframe, candle)
                except Exception as e:
                    logger.warning(
                        "Skipping invalid candle",
                        extra={"symbol": symbol, "error": str(e)},
                    )
            candles = await memory_cache.get(symbol.upper(), timeframe)

        if not candles:
            raise HTTPException(status_code=404, detail="No data available")

        candles = candles[-limit:]
        data = [candle.to_lwc_format() for candle in candles]

        return OHLCResponse(
            symbol=symbol.upper(),
            timeframe=timeframe,
            data=data,
            meta={
                "count": len(data),
                "source": candles[0].source if candles else "unknown",
                "cached": True,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error fetching OHLC data",
            extra={"symbol": symbol, "timeframe": timeframe, "error": str(e)},
        )
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ohlc/{symbol}/latest", response_model=LatestCandleResponse)
async def get_latest_candle(
    symbol: str,
    timeframe: str = Query(default=DEFAULT_TIMEFRAME, pattern="^[0-9]+[mhd]$"),
) -> LatestCandleResponse:
    """Get the latest candle for a symbol.

    Args:
        symbol: Market symbol
        timeframe: Time resolution

    Returns:
        Latest candle data
    """
    candle = await memory_cache.get_latest(symbol.upper(), timeframe)

    if not candle:
        raise HTTPException(status_code=404, detail="No data available for symbol")

    return LatestCandleResponse(
        symbol=candle.symbol,
        timestamp=candle.timestamp.isoformat(),
        open=candle.open,
        high=candle.high,
        low=candle.low,
        close=candle.close,
        volume=candle.volume,
        is_closed=candle.is_closed,
        source=candle.source,
    )
