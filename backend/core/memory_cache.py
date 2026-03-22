# MODULE: backend/core/memory_cache.py
# TASK:   CHECKLIST.md §1.6
# SPEC:   BACKEND.md §4.3
# PHASE:  1
# STATUS: In Progress

import asyncio
from collections.abc import Sequence

from backend.core.models import OHLCData


class MemoryCache:
    """Simple async-safe in-memory OHLC cache.

    Edge Cases:
        - Returns empty list for unknown symbol/timeframe combinations.
        - Stores copies to avoid external mutation side-effects.
    """

    def __init__(self) -> None:
        """Initialize internal store and lock.

        Edge Cases:
            - Lock protects concurrent reads/writes in async context.
        """

        self._store: dict[str, dict[str, list[OHLCData]]] = {}
        self._lock = asyncio.Lock()

    async def set(self, symbol: str, timeframe: str, data: Sequence[OHLCData]) -> None:
        """Set OHLC data for a symbol/timeframe combination.

        Args:
            symbol: Market symbol.
            timeframe: Candle timeframe such as 1m.
            data: Sequence of OHLC candles.

        Edge Cases:
            - Existing values are replaced atomically under lock.
        """

        async with self._lock:
            symbol_map = self._store.setdefault(symbol, {})
            symbol_map[timeframe] = list(data)

    async def get(self, symbol: str, timeframe: str) -> list[OHLCData]:
        """Get OHLC data for a symbol/timeframe combination.

        Args:
            symbol: Market symbol.
            timeframe: Candle timeframe.

        Returns:
            Cached candles or an empty list.

        Edge Cases:
            - Returns a copy to preserve cache immutability from caller side.
        """

        async with self._lock:
            symbol_map = self._store.get(symbol, {})
            candles = symbol_map.get(timeframe, [])
            return list(candles)
