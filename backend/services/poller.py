# MODULE: backend/services/poller.py
# TASK:   CHECKLIST.md §2.4, §4.4
# SPEC:   BACKEND.md §2.2.2
# PHASE:  4
# STATUS: In Progress

from __future__ import annotations

import asyncio
import logging
from datetime import UTC
from datetime import datetime
from typing import Optional

from backend.core.config import settings
from backend.db.redis_client import RedisClient
from backend.db.redis_client import get_redis_client
from backend.services.etl import ETLPipeline

logger = logging.getLogger(__name__)


class PollingLoop:
    """Background polling scheduler for ETL cycles.

    Edge Cases:
        - Keeps running after cycle exceptions.
        - Watchdog restarts loop if task unexpectedly ends.
    """

    def __init__(self) -> None:
        """Initialize polling loop state.

        Edge Cases:
            - Uses settings defaults for symbol/timeframe.
        """

        self._task: Optional[asyncio.Task[None]] = None
        self._watchdog_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._redis: Optional[RedisClient] = None
        self._poll_interval = settings.poll_interval
        self._default_symbol = settings.default_symbol
        self._default_timeframe = settings.default_timeframe
        self._etl = ETLPipeline()
        self.last_poll_at: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        """Return whether poller task is active."""

        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start poller and watchdog tasks.

        Edge Cases:
            - Repeated start calls are ignored when already running.
        """

        if self.is_running:
            return
        self._stop_event.clear()
        self._redis = await get_redis_client()
        self._task = asyncio.create_task(self._run_loop())
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog_loop())

    async def stop(self) -> None:
        """Stop poller and watchdog tasks.

        Edge Cases:
            - Safe to call even if tasks are already stopped.
        """

        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._watchdog_task is not None:
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                pass
            self._watchdog_task = None

    async def _run_loop(self) -> None:
        """Main polling loop."""

        while not self._stop_event.is_set():
            try:
                await self._poll_once(self._default_symbol, self._default_timeframe)
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
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

    async def _watchdog_loop(self) -> None:
        """Restart poller task if it unexpectedly stops.

        Edge Cases:
            - Stops when global stop event is set.
        """

        while not self._stop_event.is_set():
            await asyncio.sleep(5)
            if self._stop_event.is_set():
                break
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._run_loop())
                logger.warning(
                    "poller_restarted_by_watchdog",
                    extra={
                        "source": "poller",
                        "symbol": self._default_symbol,
                        "latency_ms": 0,
                        "status": "restarted",
                    },
                )

    async def _poll_once(self, symbol: str, timeframe: str) -> None:
        """Execute one ETL cycle and publish WS update.

        Edge Cases:
            - Publish is skipped if ETL returns no latest candle.
        """

        result = await self._etl.run(symbol, timeframe)
        self.last_poll_at = datetime.now(tz=UTC)
        latest_candle = result.get("latest_candle")
        if latest_candle and self._redis is not None:
            await self._redis.publish(
                f"ohlc:updates:{symbol.upper()}",
                {
                    "type": "ohlc",
                    "data": latest_candle,
                    "timestamp": self.last_poll_at.isoformat(),
                },
            )


polling_loop: Optional[PollingLoop] = None


async def get_polling_loop() -> PollingLoop:
    """Get singleton polling loop."""

    global polling_loop
    if polling_loop is None:
        polling_loop = PollingLoop()
    return polling_loop
