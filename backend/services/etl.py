# MODULE: backend/services/etl.py
# TASK:   CHECKLIST.md §3.3, §4.3
# SPEC:   BACKEND.md §2.2.2
# PHASE:  3
# STATUS: In Progress

from __future__ import annotations

import logging
import time
from datetime import UTC
from datetime import datetime
from typing import Optional

from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.adapters.nse import NSEAdapter
from backend.adapters.yahoo import YahooAdapter
from backend.core.exceptions import AllSourcesFailedError
from backend.core.models import OHLCData
from backend.core.models import RawData
from backend.core.validator import DataValidator
from backend.db.database import get_database
from backend.db.models import ETLJobDb
from backend.db.models import OHLCDb
from backend.db.models import SourceHealthDb
from backend.db.redis_client import get_redis_client
from backend.services.aggregator import AggregatorService

logger = logging.getLogger(__name__)


class ETLPipeline:
    """Extract-transform-validate-load pipeline.

    Edge Cases:
        - Continues with Redis updates even if DB writes fail.
        - Logs and skips invalid candles without aborting full run.
    """

    def __init__(self) -> None:
        """Initialize ETL dependencies.

        Edge Cases:
            - Adapters are sorted by priority inside `AggregatorService`.
        """

        self._aggregator = AggregatorService([NSEAdapter(), YahooAdapter()])
        self._validator = DataValidator()

    async def run(self, symbol: str, timeframe: str = "1m") -> dict:
        """Run complete ETL cycle for a symbol.

        Args:
            symbol: Symbol to process.
            timeframe: Timeframe to process.

        Returns:
            ETL cycle result summary.

        Edge Cases:
            - On all-sources-failed, returns result with zero writes and error set.
        """

        started_at = time.perf_counter()
        symbol_upper = symbol.upper()
        job_id = await self._create_etl_job(symbol_upper, "running")
        result = {
            "job_id": job_id,
            "symbol": symbol_upper,
            "timeframe": timeframe,
            "source": "",
            "extracted": 0,
            "validated": 0,
            "invalid": 0,
            "loaded": 0,
            "latest_candle": None,
            "errors": [],
        }

        try:
            raw_rows = await self._aggregator.fetch(symbol_upper, timeframe)
            result["extracted"] = len(raw_rows)
            result["source"] = self._aggregator.active_source or "unknown"

            transformed = self._transform(raw_rows, symbol_upper)
            valid_rows, invalid_count = self._validate(transformed)
            result["validated"] = len(valid_rows)
            result["invalid"] = invalid_count

            if valid_rows:
                loaded = await self._load_to_db(valid_rows, timeframe)
                result["loaded"] = loaded
                await self._write_to_redis(symbol_upper, timeframe, valid_rows)
                result["latest_candle"] = valid_rows[-1].model_dump(mode="json")

            latency_ms = int((time.perf_counter() - started_at) * 1000)
            await self._update_source_health(
                source_name=result["source"],
                status="healthy",
                latency_ms=latency_ms,
                success=True,
            )
            await self._update_etl_job(job_id, "completed", result["loaded"], None)
            return result
        except AllSourcesFailedError as exc:
            result["errors"].append(str(exc))
            await self._update_source_health(
                source_name=self._aggregator.active_source or "unknown",
                status="down",
                latency_ms=int((time.perf_counter() - started_at) * 1000),
                success=False,
            )
            await self._update_etl_job(job_id, "failed", 0, str(exc))
            return result
        except Exception as exc:
            result["errors"].append(str(exc))
            await self._update_etl_job(job_id, "failed", result["loaded"], str(exc))
            return result

    def _transform(self, raw_rows: list[RawData], symbol: str) -> list[OHLCData]:
        """Transform raw adapter rows into normalized OHLC models.

        Edge Cases:
            - Naive timestamps are converted to UTC.
            - `is_closed` is computed from current minute floor.
        """

        current_minute = datetime.now(tz=UTC).replace(second=0, microsecond=0)
        transformed: list[OHLCData] = []
        for row in raw_rows:
            try:
                timestamp = row["timestamp"]
                if not isinstance(timestamp, datetime):
                    raise ValueError("timestamp must be datetime")
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
                floored = timestamp.astimezone(UTC).replace(second=0, microsecond=0)
                transformed.append(
                    OHLCData(
                        symbol=symbol,
                        timestamp=floored,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=int(row["volume"]) if row.get("volume") is not None else None,
                        source=str(row.get("source", self._aggregator.active_source)),
                        is_closed=floored < current_minute,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning(
                    "etl_transform_skip_row",
                    extra={
                        "source": "etl",
                        "symbol": symbol,
                        "latency_ms": 0,
                        "status": "error",
                        "error": str(exc),
                    },
                )
        transformed.sort(key=lambda item: item.timestamp)
        return transformed

    def _validate(self, candles: list[OHLCData]) -> tuple[list[OHLCData], int]:
        """Validate transformed candles.

        Edge Cases:
            - Invalid candles are rejected but not raised.
        """

        valid: list[OHLCData] = []
        invalid = 0
        for candle in candles:
            result = self._validator.validate(candle)
            if result.valid:
                valid.append(candle)
            else:
                invalid += 1
        return valid, invalid

    async def _load_to_db(self, candles: list[OHLCData], timeframe: str) -> int:
        """Upsert candles into PostgreSQL.

        Edge Cases:
            - DB errors return zero writes but keep pipeline alive.
        """

        if not candles:
            return 0
        try:
            database = await get_database()
            async with database.get_session() as session:
                for candle in candles:
                    stmt = pg_insert(OHLCDb).values(
                        symbol=candle.symbol,
                        timestamp=candle.timestamp,
                        timeframe=timeframe,
                        open=candle.open,
                        high=candle.high,
                        low=candle.low,
                        close=candle.close,
                        volume=candle.volume,
                        source=candle.source,
                        is_closed=candle.is_closed,
                    )
                    stmt = stmt.on_conflict_do_update(
                        index_elements=["symbol", "timestamp", "timeframe"],
                        set_={
                            "open": candle.open,
                            "high": candle.high,
                            "low": candle.low,
                            "close": candle.close,
                            "volume": candle.volume,
                            "source": candle.source,
                            "is_closed": candle.is_closed,
                        },
                    )
                    await session.execute(stmt)
                await session.commit()
            return len(candles)
        except Exception as exc:
            logger.error(
                "etl_db_load_failed",
                extra={
                    "source": "postgres",
                    "symbol": candles[-1].symbol,
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                },
            )
            return 0

    async def _write_to_redis(
        self, symbol: str, timeframe: str, candles: list[OHLCData]
    ) -> None:
        """Write latest ETL result to Redis cache.

        Edge Cases:
            - Cache writes are best-effort and errors are swallowed.
        """

        if not candles:
            return
        redis = await get_redis_client()
        payload = [candle.model_dump(mode="json") for candle in candles]
        await redis.set_ohlc(symbol, timeframe, payload)
        await redis.set_latest_candle(symbol, timeframe, payload[-1])

    async def _create_etl_job(self, symbol: str, status: str) -> int:
        """Create ETL job record.

        Edge Cases:
            - Returns 0 when DB write fails.
        """

        try:
            database = await get_database()
            async with database.get_session() as session:
                row = ETLJobDb(
                    job_type="ohlc_etl",
                    symbol=symbol,
                    status=status,
                )
                session.add(row)
                await session.commit()
                await session.refresh(row)
                return row.id
        except Exception:
            return 0

    async def _update_etl_job(
        self,
        job_id: int,
        status: str,
        records_processed: int,
        error_message: Optional[str],
    ) -> None:
        """Update ETL job record.

        Edge Cases:
            - No-op when `job_id` is zero.
        """

        if job_id == 0:
            return
        try:
            database = await get_database()
            async with database.get_session() as session:
                row = await session.get(ETLJobDb, job_id)
                if row is None:
                    return
                row.status = status
                row.records_processed = records_processed
                row.error_message = error_message
                row.completed_at = datetime.now(tz=UTC)
                await session.commit()
        except Exception:
            return

    async def _update_source_health(
        self,
        source_name: str,
        status: str,
        latency_ms: int,
        success: bool,
    ) -> None:
        """Upsert source health status into DB and Redis.

        Edge Cases:
            - On DB failure, Redis health cache may still be updated.
        """

        now = datetime.now(tz=UTC)
        normalized_source = source_name or "unknown"
        try:
            database = await get_database()
            async with database.get_session() as session:
                stmt = pg_insert(SourceHealthDb).values(
                    source_name=normalized_source,
                    status=status,
                    latency_ms=latency_ms,
                    last_success_at=now if success else None,
                    last_failure_at=None if success else now,
                    failure_count=0 if success else 1,
                    checked_at=now,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=["source_name"],
                    set_={
                        "status": status,
                        "latency_ms": latency_ms,
                        "last_success_at": now if success else SourceHealthDb.last_success_at,
                        "last_failure_at": now if not success else SourceHealthDb.last_failure_at,
                        "failure_count": (
                            0 if success else SourceHealthDb.failure_count + 1
                        ),
                        "checked_at": now,
                    },
                )
                await session.execute(stmt)
                await session.commit()
        except Exception:
            pass

        redis = await get_redis_client()
        await redis.set_json(
            key=f"health:{normalized_source}",
            value={
                "source_name": normalized_source,
                "status": status,
                "latency_ms": latency_ms,
                "checked_at": now.isoformat(),
            },
            ttl_seconds=30,
        )
