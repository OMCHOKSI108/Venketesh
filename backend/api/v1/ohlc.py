# MODULE: backend/api/v1/ohlc.py
# TASK:   CHECKLIST.md §1.7
# SPEC:   BACKEND.md §5.1.1
# PHASE:  1
# STATUS: In Progress

from __future__ import annotations

import logging
import time
from datetime import UTC
from datetime import datetime

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from pydantic import BaseModel

from backend.adapters.yahoo import YahooAdapter
from backend.core.config import settings
from backend.core.memory_cache import MemoryCache
from backend.core.models import OHLCData
from backend.core.models import RawData
from backend.services.aggregator import AggregatorService, AllSourcesFailedError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ohlc", tags=["ohlc"])

_cache = MemoryCache()
_aggregator = AggregatorService([YahooAdapter()])


class OhlcMeta(BaseModel):
    """Metadata for OHLC API response.

    Edge Cases:
        - `source` can be `cache` when data origin is unavailable.
    """

    count: int
    source: str
    cached: bool
    query_time_ms: int


class OhlcResponse(BaseModel):
    """OHLC list response payload.

    Edge Cases:
        - Empty list is possible when adapter has no usable data.
    """

    symbol: str
    timeframe: str
    data: list[OHLCData]
    meta: OhlcMeta


@router.get("/{symbol}", response_model=OhlcResponse)
async def get_ohlc(
    symbol: str,
    timeframe: str = Query(default=settings.default_timeframe),
    limit: int = Query(
        default=settings.default_limit,
        ge=1,
        le=settings.max_limit,
    ),
    from_time: Optional[str] = Query(default=None, description="ISO 8601 start time"),
    to_time: Optional[str] = Query(default=None, description="ISO 8601 end time"),
) -> OhlcResponse:
    """Return OHLC candles for a symbol and timeframe.

    Args:
        symbol: Market symbol.
        timeframe: Candle timeframe.
        limit: Maximum number of candles to return.
        from_time: Start time (ISO 8601) for filtering.
        to_time: End time (ISO 8601) for filtering.

    Returns:
        OHLC response object matching API v1 schema.

    Edge Cases:
        - Cache miss triggers adapter fetch and cache population.
        - Adapter errors return HTTP 502.
        - from/to filters applied after fetching.
    """

    started_at = time.perf_counter()
    normalized_symbol = symbol.upper()
    try:
        cached_data = await _cache.get(normalized_symbol, timeframe)
        if cached_data:
            candles = cached_data[-limit:]

            if from_time:
                from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
                candles = [c for c in candles if c.timestamp >= from_dt]
            if to_time:
                to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
                candles = [c for c in candles if c.timestamp <= to_dt]

            candles = candles[-limit:]
            query_time_ms = int((time.perf_counter() - started_at) * 1000)
            return OhlcResponse(
                symbol=normalized_symbol,
                timeframe=timeframe,
                data=candles,
                meta=OhlcMeta(
                    count=len(candles),
                    source=candles[-1].source if candles else "cache",
                    cached=True,
                    query_time_ms=query_time_ms,
                ),
            )

        raw_rows = await _aggregator.fetch(normalized_symbol, timeframe)
        candles = _normalize_raw_rows(raw_rows, normalized_symbol)

        if from_time:
            from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
            candles = [c for c in candles if c.timestamp >= from_dt]
        if to_time:
            to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
            candles = [c for c in candles if c.timestamp <= to_dt]

        candles = candles[-limit:]
        if not candles:
            raise HTTPException(status_code=404, detail="No OHLC data available.")
        await _cache.set(normalized_symbol, timeframe, candles)
        query_time_ms = int((time.perf_counter() - started_at) * 1000)
        return OhlcResponse(
            symbol=normalized_symbol,
            timeframe=timeframe,
            data=candles,
            meta=OhlcMeta(
                count=len(candles),
                source=candles[-1].source,
                cached=False,
                query_time_ms=query_time_ms,
            ),
        )
    except AllSourcesFailedError as exc:
        query_time_ms = int((time.perf_counter() - started_at) * 1000)
        logger.error(
            "ohlc_fetch_failed",
            extra={
                "source": "aggregator",
                "symbol": normalized_symbol,
                "latency_ms": query_time_ms,
                "status": "error",
                "error": str(exc),
            },
        )
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch OHLC data from all sources.",
        ) from exc


@router.get("/{symbol}/latest", response_model=OhlcResponse)
async def get_latest_ohlc(
    symbol: str,
    timeframe: str = Query(default=settings.default_timeframe),
) -> OhlcResponse:
    """Return only the latest candle for a symbol.

    Args:
        symbol: Market symbol.
        timeframe: Candle timeframe.

    Returns:
        OHLC response with exactly one candle in `data`.

    Edge Cases:
        - Cache miss falls back to adapter fetch then narrows to one candle.
    """

    response = await get_ohlc(
        symbol=symbol,
        timeframe=timeframe,
        limit=1,
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="Latest OHLC candle not found.")
    return response


def _normalize_raw_rows(raw_rows: list[RawData], symbol: str) -> list[OHLCData]:
    """Normalize adapter rows into validated OHLCData models.

    Args:
        raw_rows: Adapter-level raw rows.
        symbol: Requested symbol.

    Returns:
        List of validated OHLCData sorted by timestamp.

    Edge Cases:
        - Rows with invalid shape are skipped and logged.
        - Naive timestamps are interpreted as UTC.
    """

    normalized: list[OHLCData] = []
    current_minute = datetime.now(tz=UTC).replace(second=0, microsecond=0)
    for row in raw_rows:
        try:
            timestamp = row["timestamp"]
            if not isinstance(timestamp, datetime):
                raise ValueError("timestamp is not datetime")
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            minute_floor = timestamp.astimezone(UTC).replace(second=0, microsecond=0)
            candle = OHLCData(
                symbol=symbol,
                timestamp=minute_floor,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]) if row.get("volume") is not None else None,
                source="nse",
                is_closed=minute_floor < current_minute,
            )
            normalized.append(candle)
        except (KeyError, TypeError, ValueError) as exc:
            logger.error(
                "ohlc_normalize_row_failed",
                extra={
                    "source": "nse",
                    "symbol": symbol,
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                },
            )
            continue
    normalized.sort(key=lambda item: item.timestamp)
    return normalized
