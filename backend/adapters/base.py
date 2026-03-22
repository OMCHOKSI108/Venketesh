# MODULE: backend/adapters/base.py
# TASK:   CHECKLIST.md §1.4
# SPEC:   BACKEND.md §2.2
# PHASE:  1
# STATUS: In Progress

from abc import ABC, abstractmethod

from backend.core.models import RawData


class DataSourceAdapter(ABC):
    """Abstract interface for all market data adapters.

    Edge Cases:
        - Implementations may return an empty list when a source has no data.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the adapter name.

        Edge Cases:
            - Name should stay stable for logging and source-health records.
        """

    @abstractmethod
    async def fetch(self, symbol: str) -> list[RawData]:
        """Fetch raw OHLC-like candles for a symbol.

        Args:
            symbol: Market symbol such as NIFTY.

        Returns:
            A list of raw candle records.

        Edge Cases:
            - Should raise `AdapterError` on network/parse issues.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Perform a lightweight adapter health probe.

        Returns:
            `True` when source is reachable and responsive.

        Edge Cases:
            - Should return `False` on transient source failures.
        """

    @abstractmethod
    def get_priority(self) -> int:
        """Return adapter priority (lower number means higher priority).

        Edge Cases:
            - Priority values must be unique among enabled adapters.
        """
