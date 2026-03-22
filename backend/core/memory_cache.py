"""In-memory cache for OHLC data.

Project: Pseudo-Live Indian Index Market Data Platform
Version: 1.0
"""

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

from backend.core.models import OHLCData

logger = logging.getLogger(__name__)


class MemoryCache:
    """Thread-safe in-memory cache for OHLC data.

    Stores candle data by symbol and timeframe.
    This is a Phase 1 temporary solution before Redis integration.
    """

    def __init__(self) -> None:
        self._cache: dict[str, dict[str, list[OHLCData]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._lock = asyncio.Lock()

    async def set(self, symbol: str, timeframe: str, data: list[OHLCData]) -> None:
        """Store OHLC data for a symbol and timeframe.

        Args:
            symbol: The market symbol (e.g., 'NIFTY')
            timeframe: The time resolution (e.g., '1m')
            data: List of OHLC candles to store
        """
        async with self._lock:
            self._cache[symbol][timeframe] = data
            logger.debug(
                "Cache updated",
                extra={"symbol": symbol, "timeframe": timeframe, "count": len(data)},
            )

    async def get(self, symbol: str, timeframe: str) -> list[OHLCData]:
        """Retrieve OHLC data for a symbol and timeframe.

        Args:
            symbol: The market symbol
            timeframe: The time resolution

        Returns:
            List of OHLC candles, empty list if not found
        """
        async with self._lock:
            return self._cache[symbol].get(timeframe, []).copy()

    async def append(self, symbol: str, timeframe: str, candle: OHLCData) -> None:
        """Append a single candle to existing data.

        If the last candle has the same timestamp, update it instead of appending.

        Args:
            symbol: The market symbol
            timeframe: The time resolution
            candle: The OHLC candle to add
        """
        async with self._lock:
            existing = self._cache[symbol][timeframe]
            if existing and existing[-1].timestamp == candle.timestamp:
                existing[-1] = candle
                logger.debug(
                    "Updated existing candle",
                    extra={"symbol": symbol, "timeframe": timeframe},
                )
            else:
                existing.append(candle)
                logger.debug(
                    "Appended new candle",
                    extra={"symbol": symbol, "timeframe": timeframe},
                )

    async def get_latest(self, symbol: str, timeframe: str) -> Optional[OHLCData]:
        """Get the most recent candle for a symbol.

        Args:
            symbol: The market symbol
            timeframe: The time resolution

        Returns:
            The latest OHLC candle, or None if no data available
        """
        async with self._lock:
            candles = self._cache[symbol].get(timeframe, [])
            return candles[-1] if candles else None

    async def clear(self, symbol: Optional[str] = None) -> None:
        """Clear cache for a specific symbol or all symbols.

        Args:
            symbol: Symbol to clear, or None to clear all
        """
        async with self._lock:
            if symbol:
                if symbol in self._cache:
                    del self._cache[symbol]
                    logger.info("Cache cleared", extra={"symbol": symbol})
            else:
                self._cache.clear()
                logger.info("All cache cleared")

    async def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        async with self._lock:
            total_symbols = len(self._cache)
            total_candles = sum(
                len(candles)
                for candles in self._cache.values()
                for timeframe in candles
            )
            return {
                "total_symbols": total_symbols,
                "total_candles": total_candles,
                "symbols": {
                    symbol: {
                        timeframe: len(candles)
                        for timeframe, candles in timeframes.items()
                    }
                    for symbol, timeframes in self._cache.items()
                },
            }


memory_cache = MemoryCache()
