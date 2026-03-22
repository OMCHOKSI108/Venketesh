# MODULE: backend/api/v1/ohlc.py
# TASK:   CHECKLIST.md §1.7
# SPEC:   BACKEND.md §5.1.1
# PHASE:  1
# STATUS: In Progress

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.adapters.nse import NSEAdapter
from backend.adapters.yahoo import YahooAdapter
from backend.core.config import settings
from backend.core.exceptions import AllSourcesFailedError
from backend.core.memory_cache import MemoryCache
from backend.core.models import OHLCData, RawData
from backend.services.aggregator import AggregatorService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ohlc", tags=["ohlc"])

_cache = MemoryCache()
_aggregator = AggregatorService([NSEAdapter(), YahooAdapter()])


class OhlcMeta(BaseModel):
    """Metadata object for OHLC responses.

    Edge Cases:
        - `source` falls back to `"unknown"` when data list is unexpectedly empty.
    """

    count: int
    source: str
    cached: bool
    query_time_ms: int


class OhlcResponse(BaseModel):
    """OHLC endpoint response schema.

    Edge Cases:
        - Empty list is allowed for 404-free internal flows before HTTP mapping.
    """

    symbol: str
    timeframe: str
    data: list[OHLCData]
    meta: OhlcMeta


@router.get("/{symbol}", response_model=OhlcResponse)
async def get_ohlc(
    symbol: str,
    timeframe: str = Query(default=settings.default_timeframe),
    limit: int = Query(default=settings.default_limit, ge=1, le=settings.max_limit),
) -> OhlcResponse:
    """Get OHLC candles for a symbol.

    Args:
        symbol: Symbol name.
        timeframe: Requested timeframe.
        limit: Max candles to include in the response.

    Returns:
        OHLC response with data and metadata.

    Raises:
        HTTPException: 404 for empty data, 502 for source failures.

    Edge Cases:
        - Uses in-memory cache first and fetches sources only on cache miss.
    """

    normalized_symbol = symbol.upper()
    started_at = time.perf_counter()

    cached = await _cache.get(normalized_symbol, timeframe)
    if cached:
        sliced = cached[-limit:]
        return OhlcResponse(
            symbol=normalized_symbol,
            timeframe=timeframe,
            data=sliced,
            meta=OhlcMeta(
                count=len(sliced),
                source=sliced[-1].source if sliced else "unknown",
                cached=True,
                query_time_ms=int((time.perf_counter() - started_at) * 1000),
            ),
        )

    try:
        raw_rows = await _aggregator.fetch(normalized_symbol, timeframe)
    except AllSourcesFailedError as exc:
        logger.error(
            "ohlc_fetch_failed",
            extra={
                "source": "aggregator",
                "symbol": normalized_symbol,
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
                "status": "error",
                "error": exc.message,
            },
        )
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch OHLC data from all sources.",
        ) from exc

    candles = _normalize_raw_rows(raw_rows, normalized_symbol)
    if not candles:
        raise HTTPException(status_code=404, detail="No OHLC data available.")

    await _cache.set(normalized_symbol, timeframe, candles)
    sliced = candles[-limit:]
    return OhlcResponse(
        symbol=normalized_symbol,
        timeframe=timeframe,
        data=sliced,
        meta=OhlcMeta(
            count=len(sliced),
            source=sliced[-1].source if sliced else "unknown",
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
        OHLC response containing exactly one candle.

    Edge Cases:
        - Relies on `get_ohlc` for fallback and error mapping.
    """

    result = await get_ohlc(symbol=symbol, timeframe=timeframe, limit=1)
    if not result.data:
        raise HTTPException(status_code=404, detail="Latest OHLC candle not found.")
    return result


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
