# MODULE: backend/api/v1/ohlc.py
# TASK:   CHECKLIST.md §1.7, §2.3, §3.4
# SPEC:   BACKEND.md §5.1.1
# PHASE:  3
# STATUS: In Progress

from __future__ import annotations

import logging
import time
from datetime import UTC
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select
from sqlalchemy import desc
from sqlalchemy import select

from backend.adapters.nse import NSEAdapter
from backend.adapters.yahoo import YahooAdapter
from backend.core.config import settings
from backend.core.exceptions import AllSourcesFailedError
from backend.core.models import OHLCData
from backend.core.models import RawData
from backend.db.database import get_database
from backend.db.models import OHLCDb
from backend.db.redis_client import get_redis_client
from backend.services.aggregator import AggregatorService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ohlc", tags=["ohlc"])

_aggregator = AggregatorService([NSEAdapter(), YahooAdapter()])


class OhlcMeta(BaseModel):
    """Metadata object for OHLC responses.

    Edge Cases:
        - Source falls back to `unknown` when no row has source details.
    """

    count: int
    source: str
    cached: bool
    query_time_ms: int


class OhlcResponse(BaseModel):
    """OHLC endpoint response schema.

    Edge Cases:
        - Data is sorted ascending by timestamp for chart consumption.
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
    from_time: Optional[datetime] = Query(default=None, alias="from"),
    to_time: Optional[datetime] = Query(default=None, alias="to"),
) -> OhlcResponse:
    """Get OHLC candles for a symbol.

    Args:
        symbol: Symbol name.
        timeframe: Candle timeframe.
        limit: Max number of closed candles from DB.
        from_time: Optional inclusive start time.
        to_time: Optional inclusive end time.

    Returns:
        OHLC response payload.

    Edge Cases:
        - Uses query-level Redis cache before hitting DB.
        - Falls back to adapters when DB has no candles.
    """

    normalized_symbol = symbol.upper()
    started_at = time.perf_counter()
    redis = await get_redis_client()
    cache_key = _query_cache_key(normalized_symbol, timeframe, limit, from_time, to_time)

    cached = await redis.get_json(cache_key)
    if isinstance(cached, list):
        candles = _normalize_cached_rows(cached, normalized_symbol)
        return _build_response(
            symbol=normalized_symbol,
            timeframe=timeframe,
            candles=candles,
            cached=True,
            query_time_ms=int((time.perf_counter() - started_at) * 1000),
        )

    candles = await _query_db_candles(
        symbol=normalized_symbol,
        timeframe=timeframe,
        limit=limit,
        from_time=from_time,
        to_time=to_time,
    )
    candles = candles + await _get_current_open_from_redis(normalized_symbol, timeframe)

    if not candles:
        candles = await _fetch_from_sources(normalized_symbol, timeframe, redis)

    if not candles:
        raise HTTPException(status_code=404, detail="No OHLC data available.")

    payload = [row.model_dump(mode="json") for row in candles]
    await redis.set_json(cache_key, payload, ttl_seconds=settings.redis_ohlc_ttl_seconds)
    return _build_response(
        symbol=normalized_symbol,
        timeframe=timeframe,
        candles=candles,
        cached=False,
        query_time_ms=int((time.perf_counter() - started_at) * 1000),
    )


@router.get("/{symbol}/latest", response_model=OhlcResponse)
async def get_latest_ohlc(
    symbol: str,
    timeframe: str = Query(default=settings.default_timeframe),
) -> OhlcResponse:
    """Get the latest OHLC candle.

    Args:
        symbol: Symbol name.
        timeframe: Candle timeframe.

    Returns:
        Response containing exactly one candle.

    Edge Cases:
        - Falls back to full endpoint path when latest key is missing.
    """

    normalized_symbol = symbol.upper()
    started_at = time.perf_counter()
    redis = await get_redis_client()
    latest = await redis.get_latest_candle(normalized_symbol, timeframe)
    if isinstance(latest, dict):
        candles = _normalize_cached_rows([latest], normalized_symbol)
        if candles:
            return _build_response(
                symbol=normalized_symbol,
                timeframe=timeframe,
                candles=candles,
                cached=True,
                query_time_ms=int((time.perf_counter() - started_at) * 1000),
            )

    response = await get_ohlc(symbol=normalized_symbol, timeframe=timeframe, limit=1)
    if not response.data:
        raise HTTPException(status_code=404, detail="Latest OHLC candle not found.")
    return response


async def _query_db_candles(
    symbol: str,
    timeframe: str,
    limit: int,
    from_time: Optional[datetime],
    to_time: Optional[datetime],
) -> list[OHLCData]:
    """Query historical closed candles from DB.

    Edge Cases:
        - Returns empty list if DB is unreachable or query fails.
    """

    try:
        database = await get_database()
        async with database.get_session() as session:
            stmt: Select[tuple[OHLCDb]] = select(OHLCDb).where(
                OHLCDb.symbol == symbol,
                OHLCDb.timeframe == timeframe,
                OHLCDb.is_closed.is_(True),
            )
            if from_time is not None:
                stmt = stmt.where(OHLCDb.timestamp >= _ensure_utc(from_time))
            if to_time is not None:
                stmt = stmt.where(OHLCDb.timestamp <= _ensure_utc(to_time))
            stmt = stmt.order_by(desc(OHLCDb.timestamp)).limit(limit)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return sorted((_db_row_to_ohlc(row) for row in rows), key=lambda item: item.timestamp)
    except Exception as exc:
        logger.warning(
            "ohlc_db_query_failed",
            extra={
                "source": "postgres",
                "symbol": symbol,
                "latency_ms": 0,
                "status": "error",
                "error": str(exc),
            },
        )
        return []


async def _get_current_open_from_redis(symbol: str, timeframe: str) -> list[OHLCData]:
    """Read current candle from Redis.

    Edge Cases:
        - Returns empty list on cache miss or invalid payload.
    """

    redis = await get_redis_client()
    current_rows = await redis.get_ohlc(symbol, timeframe)
    if not current_rows:
        return []
    candles = _normalize_cached_rows(current_rows, symbol)
    return [candles[-1]] if candles else []


async def _fetch_from_sources(
    symbol: str,
    timeframe: str,
    redis: object,
) -> list[OHLCData]:
    """Fetch candles from source adapters as fallback.

    Edge Cases:
        - Returns empty list when all adapters fail.
    """

    try:
        raw_rows = await _aggregator.fetch(symbol, timeframe)
    except AllSourcesFailedError:
        return []
    candles = _normalize_raw_rows(raw_rows, symbol)
    if candles:
        payload = [row.model_dump(mode="json") for row in candles]
        await redis.set_ohlc(symbol, timeframe, payload)
        await redis.set_latest_candle(symbol, timeframe, payload[-1])
    return candles


def _build_response(
    symbol: str,
    timeframe: str,
    candles: list[OHLCData],
    cached: bool,
    query_time_ms: int,
) -> OhlcResponse:
    """Create response payload model.

    Edge Cases:
        - Defaults source to unknown for empty data arrays.
    """

    return OhlcResponse(
        symbol=symbol,
        timeframe=timeframe,
        data=candles,
        meta=OhlcMeta(
            count=len(candles),
            source=candles[-1].source if candles else "unknown",
            cached=cached,
            query_time_ms=query_time_ms,
        ),
    )


def _query_cache_key(
    symbol: str,
    timeframe: str,
    limit: int,
    from_time: Optional[datetime],
    to_time: Optional[datetime],
) -> str:
    """Build redis key for OHLC query cache."""

    from_part = from_time.isoformat() if from_time else "none"
    to_part = to_time.isoformat() if to_time else "none"
    return f"ohlc:query:{symbol}:{timeframe}:{limit}:{from_part}:{to_part}"


def _normalize_raw_rows(raw_rows: list[RawData], symbol: str) -> list[OHLCData]:
    """Convert raw adapter rows to validated OHLC models.

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
            minute_floor = _ensure_utc(timestamp).replace(second=0, microsecond=0)
            normalized.append(
                OHLCData(
                    symbol=symbol,
                    timestamp=minute_floor,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]) if row.get("volume") is not None else None,
                    source=str(row.get("source", _aggregator.active_source or "unknown")),
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
    """Convert cached rows to OHLCData models.

    Edge Cases:
        - Handles both ISO timestamps and datetime values.
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
            minute_floor = _ensure_utc(timestamp).replace(second=0, microsecond=0)
            normalized.append(
                OHLCData(
                    symbol=symbol,
                    timestamp=minute_floor,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]) if row.get("volume") is not None else None,
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


def _db_row_to_ohlc(row: OHLCDb) -> OHLCData:
    """Convert DB row to OHLCData."""

    return OHLCData(
        symbol=row.symbol,
        timestamp=_ensure_utc(row.timestamp).replace(second=0, microsecond=0),
        open=_to_float(row.open),
        high=_to_float(row.high),
        low=_to_float(row.low),
        close=_to_float(row.close),
        volume=row.volume,
        source=row.source,
        is_closed=row.is_closed,
    )


def _to_float(value: Decimal | float | int) -> float:
    """Convert numeric values to float."""

    return float(value)


def _ensure_utc(value: datetime) -> datetime:
    """Return timezone-aware UTC datetime."""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
