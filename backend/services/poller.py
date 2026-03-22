# MODULE: backend/services/poller.py
# TASK:   CHECKLIST.md §2.4
# SPEC:   BACKEND.md §2.2.2
# PHASE:  2
# STATUS: In Progress

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Optional

from backend.core.config import settings
from backend.db.redis_client import get_redis_client
from backend.services.etl import ETLPipeline

logger = logging.getLogger(__name__)


class PollingLoop:
    """Background polling loop for pseudo-live OHLC refresh.

    Edge Cases:
        - Loop keeps running even when sources fail temporarily.
        - Redis unavailability does not crash the loop.
    """

    def __init__(self) -> None:
        """Initialize polling state and dependencies.

        Edge Cases:
            - Interval and default symbol come from settings only.
        """

        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._redis: Optional[RedisClient] = None
        self._poll_interval = settings.poll_interval
        self._default_symbol = settings.default_symbol
        self._default_timeframe = settings.default_timeframe
        self._etl = ETLPipeline()

    @property
    def is_running(self) -> bool:
        """Check whether polling task is active.

        Edge Cases:
            - Returns False if task is done or never started.
        """

        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start the background polling loop.

        Edge Cases:
            - Calling start repeatedly does nothing when already running.
        """

        if self.is_running:
            return
        self._stop_event.clear()
        self._redis = await get_redis_client()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "poller_started",
            extra={
                "source": "poller",
                "symbol": self._default_symbol,
                "latency_ms": 0,
                "status": "ok",
                "interval_seconds": self._poll_interval,
            },
        )

    async def stop(self) -> None:
        """Stop the background polling loop.

        Edge Cases:
            - Cancelled task is swallowed to avoid shutdown crash.
        """

        if self._task is None:
            return
        self._stop_event.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info(
            "poller_stopped",
            extra={
                "source": "poller",
                "symbol": self._default_symbol,
                "latency_ms": 0,
                "status": "ok",
            },
        )

    async def _run_loop(self) -> None:
        """Run poll cycles until stopped.

        Edge Cases:
            - Unexpected per-cycle errors are logged and delayed.
        """

        while not self._stop_event.is_set():
            try:
                await self._poll_once(self._default_symbol, self._default_timeframe)
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except (RuntimeError, ValueError, TypeError) as exc:
                logger.error(
                    "poller_cycle_failed",
                    extra={
                        "source": "poller",
                        "symbol": self._default_symbol,
                        "latency_ms": 0,
                        "status": "error",
                        "error": str(exc),
                    },
                )
                await asyncio.sleep(5)

    async def _poll_once(self, symbol: str, timeframe: str) -> None:
        """Execute one polling cycle.

        Args:
            symbol: Symbol to fetch.
            timeframe: Timeframe to fetch.

        Edge Cases:
            - Empty valid candle list short-circuits without write operations.
        """

        try:
            result = await self._etl.run(symbol, timeframe)
            if result["validated"] > 0 and self._redis:
                # Publish the latest candle
                latest_data = await self._redis.get_ohlc(symbol, timeframe)
                if latest_data:
                    await self._redis.publish(
                        f"ohlc:updates:{symbol.upper()}",
                        {
                            "type": "ohlc",
                            "data": latest_data[-1],
                            "timestamp": datetime.now(tz=UTC).isoformat(),
                        },
                    )
        except Exception as exc:
            logger.error(
                "poller_cycle_failed",
                extra={
                    "source": "poller",
                    "symbol": symbol,
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                },
            )

    def _normalize_rows(self, rows: list[RawData], symbol: str) -> list[OHLCData]:
        """Normalize raw rows to validated OHLC models.

        Args:
            rows: Raw adapter rows.
            symbol: Requested symbol.

        Returns:
            Sorted validated candles.

        Edge Cases:
            - Invalid rows are skipped with warning logs.
        """

        current_minute = datetime.now(tz=UTC).replace(second=0, microsecond=0)
        normalized: list[OHLCData] = []
        for row in rows:
            try:
                timestamp = row["timestamp"]
                if not isinstance(timestamp, datetime):
                    raise ValueError("timestamp is not datetime")
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=UTC)
                minute_floor = timestamp.astimezone(UTC).replace(
                    second=0, microsecond=0
                )
                normalized.append(
                    OHLCData(
                        symbol=symbol.upper(),
                        timestamp=minute_floor,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=(
                            int(row["volume"])
                            if row.get("volume") is not None
                            else None
                        ),
                        source=str(row.get("source", self._aggregator.active_source)),
                        is_closed=minute_floor < current_minute,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning(
                    "poller_invalid_row",
                    extra={
                        "source": self._aggregator.active_source or "poller",
                        "symbol": symbol.upper(),
                        "latency_ms": 0,
                        "status": "error",
                        "error": str(exc),
                    },
                )
polling_loop: Optional[PollingLoop] = None


async def get_polling_loop() -> PollingLoop:
    """Get singleton polling loop.

    Edge Cases:
        - Creates instance lazily on first access.
    """

    global polling_loop
    if polling_loop is None:
        polling_loop = PollingLoop()
    return polling_loop
