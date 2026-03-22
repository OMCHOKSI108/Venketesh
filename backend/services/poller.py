# MODULE: backend/services/poller.py
# TASK:   CHECKLIST.md §2.4 Background Polling Loop
# SPEC:   BACKEND.md §2.2.2 (ETL Flow)
# PHASE:  2
# STATUS: In Progress

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from backend.adapters.nse import NSEAdapter
from backend.adapters.yahoo import YahooAdapter
from backend.core.config import settings
from backend.core.models import OHLCData
from backend.db.redis_client import RedisClient, get_redis_client
from backend.services.aggregator import AllSourcesFailedError, AggregatorService

logger = logging.getLogger(__name__)


class PollingLoop:
    """Background polling loop for fetching OHLC data.

    Edge Cases:
        - Loop never stops on exceptions; logs and continues.
        - On startup failure, retries after brief delay.
    """

    def __init__(self) -> None:
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._stop_event = asyncio.Event()

        self._aggregator = AggregatorService([NSEAdapter(), YahooAdapter()])
        self._redis: Optional[RedisClient] = None
        self._poll_interval = settings.poll_interval

    @property
    def is_running(self) -> bool:
        """Check if polling loop is active."""
        return self._running and self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start the polling loop as a background task."""
        if self.is_running:
            logger.info("Polling loop already running")
            return

        self._running = True
        self._stop_event.clear()

        self._redis = await get_redis_client()

        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "Polling loop started",
            extra={"interval": self._poll_interval},
        )

    async def stop(self) -> None:
        """Stop the polling loop gracefully."""
        if not self.is_running:
            logger.info("Polling loop not running")
            return

        self._running = False
        self._stop_event.set()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Polling loop stopped")

    async def _run_loop(self) -> None:
        """Main polling loop - runs until stopped."""
        symbol = "NIFTY"
        timeframe = "1m"

        while not self._stop_event.is_set():
            try:
                await self._fetch_and_cache(symbol, timeframe)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Polling loop error",
                    extra={
                        "symbol": symbol,
                        "error": str(e),
                    },
                )
                await asyncio.sleep(5)
                continue

            await asyncio.sleep(self._poll_interval)

    async def _fetch_and_cache(self, symbol: str, timeframe: str) -> None:
        """Fetch data, validate, and cache in Redis."""
        try:
            raw_data = await self._aggregator.fetch(symbol, timeframe)

            candles = []
            for raw in raw_data:
                try:
                    ts = raw.get("timestamp")
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)

                    candle = OHLCData(
                        symbol=symbol.upper(),
                        timestamp=ts,
                        open=float(raw["open"]),
                        high=float(raw["high"]),
                        low=float(raw["low"]),
                        close=float(raw["close"]),
                        volume=int(raw["volume"]) if raw.get("volume") else None,
                        source=raw.get(
                            "source", self._aggregator.active_source or "unknown"
                        ),
                        is_closed=False,
                    )
                    candles.append(candle)
                except Exception as e:
                    logger.warning(
                        "Skipping invalid candle",
                        extra={"symbol": symbol, "error": str(e)},
                    )

            if candles:
                candles.sort(key=lambda c: c.timestamp)

                data_dicts = [c.model_dump(mode="json") for c in candles]

                if self._redis:
                    await self._redis.set_ohlc(symbol, timeframe, data_dicts)

                    latest = candles[-1]
                    await self._redis.set_latest_candle(
                        symbol,
                        timeframe,
                        latest.model_dump(mode="json"),
                    )

                    await self._redis.publish(
                        f"ohlc:updates:{symbol}",
                        {
                            "type": "ohlc",
                            "data": latest.model_dump(mode="json"),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

                logger.info(
                    "Polled and cached",
                    extra={
                        "symbol": symbol,
                        "source": self._aggregator.active_source,
                        "candles": len(candles),
                    },
                )

        except AllSourcesFailedError as e:
            logger.error(
                "All sources failed",
                extra={"symbol": symbol, "error": str(e)},
            )


polling_loop: Optional[PollingLoop] = None


async def get_polling_loop() -> PollingLoop:
    """Get or create the polling loop singleton."""
    global polling_loop
    if polling_loop is None:
        polling_loop = PollingLoop()
    return polling_loop
