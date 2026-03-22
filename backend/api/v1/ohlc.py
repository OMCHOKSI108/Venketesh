# MODULE: backend/api/v1/ohlc.py
# TASK:   CHECKLIST.md §1.7, §2.3
# SPEC:   BACKEND.md §5.1.1
# PHASE:  2
# STATUS: In Progress

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import desc, select

from backend.adapters.nse import NSEAdapter
from backend.adapters.yahoo import YahooAdapter
from backend.core.config import settings
from backend.core.exceptions import AllSourcesFailedError
from backend.core.models import OHLCData, RawData
from backend.db.database import get_database
from backend.db.models import OHLCData as DB_OHLCData
from backend.db.models import Symbol
from backend.db.redis_client import get_redis_client
from backend.services.aggregator import AggregatorService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ohlc", tags=["ohlc"])

_aggregator = AggregatorService([NSEAdapter(), YahooAdapter()])


class OhlcMeta(BaseModel):
    """Metadata object for OHLC responses.

    Edge Cases:
        - `source` falls back to `unknown` when origin cannot be inferred.
    """

    count: int
    source: str
    cached: bool
    query_time_ms: int


class OhlcResponse(BaseModel):
    """OHLC endpoint response schema.

    Edge Cases:
        - Empty list is possible before 404 mapping at handler level.
    """

    symbol: str
    timeframe: str
    data: list[OHLCData]
    meta: OhlcMeta


@router.get("/{symbol}", response_model=OhlcResponse)
async def get_ohlc(
    symbol: str,
    timeframe: str = Query(default="1m"),
    limit: int = Query(default=300, ge=1, le=1000),
    from_time: Optional[datetime] = Query(None),
    to_time: Optional[datetime] = Query(None),
) -> OhlcResponse:
    """Get OHLC candles for a symbol.

    Args:
        symbol: Symbol name.
        timeframe: Requested timeframe.
        limit: Max closed candles to include in the response.
        from_time: Start timestamp filter.
        to_time: End timestamp filter.

    Returns:
        OHLC response with data and metadata.

    Raises:
        HTTPException: 404 for empty data.

    Edge Cases:
        - Queries DB for historical closed candles, adds current open from Redis.
        - Caches result for 60s.
    """

    normalized_symbol = symbol.upper()
    started_at = time.perf_counter()
    redis = await get_redis_client()

    # Check cache
    cache_key = f"ohlc:query:{normalized_symbol}:{timeframe}:{limit}:{from_time.isoformat() if from_time else 'none'}:{to_time.isoformat() if to_time else 'none'}"
    cached = await redis.get(cache_key)
    if cached:
        data = [OHLCData.model_validate(candle) for candle in json.loads(cached)]
        return OhlcResponse(
            symbol=normalized_symbol,
            timeframe=timeframe,
            data=data,
            meta=OhlcMeta(
                count=len(data),
                source=data[-1].source if data else "unknown",
                cached=True,
                query_time_ms=int((time.perf_counter() - started_at) * 1000),
            ),
        )

    # Query DB for historical closed candles
    database = await get_database()
    async with database.get_session() as session:
        query = select(DB_OHLCData).where(
            DB_OHLCData.symbol == normalized_symbol,
            DB_OHLCData.timeframe == timeframe,
            DB_OHLCData.is_closed == True,
        )
        if from_time:
            query = query.where(DB_OHLCData.timestamp >= from_time)
        if to_time:
            query = query.where(DB_OHLCData.timestamp <= to_time)
        query = query.order_by(desc(DB_OHLCData.timestamp)).limit(limit)
        result = await session.execute(query)
        historical_rows = result.scalars().all()
        historical = [
            OHLCData(**row.__dict__) for row in reversed(historical_rows)
        ]  # ascending

    # Get current open candle from Redis
    current_key = f"ohlc:{normalized_symbol}:{timeframe}:current"
    current_data = await redis.get(current_key)
    if current_data:
        current = OHLCData.model_validate(json.loads(current_data))
        data = historical + [current]
    else:
        data = historical

    if not data:
        raise HTTPException(status_code=404, detail="No OHLC data available.")

    # Cache result
    payload = [candle.model_dump(mode="json") for candle in data]
    await redis.set(cache_key, json.dumps(payload), ex=60)

    return OhlcResponse(
        symbol=normalized_symbol,
        timeframe=timeframe,
        data=data,
        meta=OhlcMeta(
            count=len(data),
            source=data[-1].source if data else "unknown",
            cached=False,
            query_time_ms=int((time.perf_counter() - started_at) * 1000),
        ),
    )


@router.get("/{symbol}/latest", response_model=OhlcResponse)
async def get_latest_ohlc(
    symbol: str,
    timeframe: str = Query(default=settings.default_timeframe),
) -> OhlcResponse:
    """Get only the latest OHLC candle.

    Args:
        symbol: Symbol name.
        timeframe: Requested timeframe.

    Returns:
        OHLC response containing one candle.

    Edge Cases:
        - Falls back to full fetch path when Redis latest key is missing.
    """

    normalized_symbol = symbol.upper()
    started_at = time.perf_counter()
    redis = await get_redis_client()
    latest = await redis.get_latest_candle(normalized_symbol, timeframe)

    if latest:
        candles = _normalize_cached_rows([latest], normalized_symbol)
        if candles:
            return OhlcResponse(
                symbol=normalized_symbol,
                timeframe=timeframe,
                data=candles,
                meta=OhlcMeta(
                    count=1,
                    source=candles[0].source,
                    cached=True,
                    query_time_ms=int((time.perf_counter() - started_at) * 1000),
                ),
            )

    response = await get_ohlc(symbol=normalized_symbol, timeframe=timeframe, limit=1)
    if not response.data:
        raise HTTPException(status_code=404, detail="Latest OHLC candle not found.")
    return response


@router.get("/symbols")
async def get_symbols() -> list[dict]:
    """Get list of available symbols.

    Returns:
        List of symbol metadata.
    """
    database = await get_database()
    async with database.get_session() as session:
        query = select(Symbol).where(Symbol.is_active == True)
        result = await session.execute(query)
        symbols = result.scalars().all()
        return [
            {
                "symbol": s.symbol,
                "name": s.name,
                "exchange": s.exchange,
                "instrument_type": s.instrument_type,
                "currency": s.currency,
            }
            for s in symbols
        ]


def _normalize_raw_rows(raw_rows: list[RawData], symbol: str) -> list[OHLCData]:
    """Convert raw adapter rows to validated OHLC models.

    Args:
        raw_rows: Adapter response rows.
        symbol: Symbol name.

    Returns:
        Sorted list of validated OHLC rows.

    Edge Cases:
        - Invalid rows are skipped and logged.
    """

    normalized: list[OHLCData] = []
    current_minute = datetime.now(tz=UTC).replace(second=0, microsecond=0)

    for row in raw_rows:
        try:
            timestamp = row["timestamp"]
            if not isinstance(timestamp, datetime):
                raise ValueError("timestamp must be datetime")
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            minute_floor = timestamp.astimezone(UTC).replace(second=0, microsecond=0)
            normalized.append(
                OHLCData(
                    symbol=symbol,
                    timestamp=minute_floor,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=(
                        int(row["volume"]) if row.get("volume") is not None else None
                    ),
                    source=str(
                        row.get("source", _aggregator.active_source or "unknown")
                    ),
                    is_closed=minute_floor < current_minute,
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "ohlc_row_invalid",
                extra={
                    "source": "normalize",
                    "symbol": symbol,
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                },
            )

    normalized.sort(key=lambda item: item.timestamp)
    return normalized


def _normalize_cached_rows(rows: list[dict], symbol: str) -> list[OHLCData]:
    """Convert cached dict rows to OHLC models.

    Args:
        rows: Cached rows from Redis.
        symbol: Requested symbol.

    Returns:
        Valid OHLCData list sorted by timestamp.

    Edge Cases:
        - Handles ISO timestamps stored by `model_dump(mode=\"json\")`.
    """

    normalized: list[OHLCData] = []
    for row in rows:
        try:
            raw_ts = row.get("timestamp")
            if isinstance(raw_ts, str):
                timestamp = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            elif isinstance(raw_ts, datetime):
                timestamp = raw_ts
            else:
                raise ValueError("invalid cached timestamp")

            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            minute_floor = timestamp.astimezone(UTC).replace(second=0, microsecond=0)

            normalized.append(
                OHLCData(
                    symbol=symbol,
                    timestamp=minute_floor,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=(
                        int(row["volume"]) if row.get("volume") is not None else None
                    ),
                    source=str(row.get("source", "unknown")),
                    is_closed=bool(row.get("is_closed", False)),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "ohlc_cached_row_invalid",
                extra={
                    "source": "redis",
                    "symbol": symbol,
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                },
            )
    normalized.sort(key=lambda item: item.timestamp)
    return normalized
