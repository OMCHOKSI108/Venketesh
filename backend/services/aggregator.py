# MODULE: backend/services/aggregator.py
# TASK:   CHECKLIST.md §2.2 Aggregator Service
# SPEC:   BACKEND.md §2.2.1 (Adapter interface)
# PHASE:  2
# STATUS: In Progress

import logging
from typing import Optional

from backend.adapters.base import AdapterError, DataSourceAdapter
from backend.core.models import RawData

logger = logging.getLogger(__name__)


class AllSourcesFailedError(Exception):
    """Raised when all data sources fail to fetch data."""

    pass


class AggregatorService:
    """Aggregates data from multiple adapters with priority-based failover.

    Edge Cases:
        - If all sources fail, raises AllSourcesFailedError instead of crashing.
        - Logs which source was tried and which succeeded.
    """

    def __init__(self, adapters: list[DataSourceAdapter]) -> None:
        self._adapters = sorted(adapters, key=lambda a: a.get_priority())
        self._active_source: Optional[str] = None

    @property
    def active_source(self) -> Optional[str]:
        """Return the name of the last successful adapter."""
        return self._active_source

    async def fetch(self, symbol: str, timeframe: str = "1m") -> list[RawData]:
        """Fetch OHLC data from available sources in priority order.

        Args:
            symbol: Market symbol (e.g., 'NIFTY')
            timeframe: Time resolution (e.g., '1m')

        Returns:
            List of raw OHLC data from the first successful source

        Raises:
            AllSourcesFailedError: When all adapters fail
        """
        errors = []

        for adapter in self._adapters:
            try:
                logger.info(
                    "Attempting fetch from adapter",
                    extra={
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "adapter": adapter.name,
                        "priority": adapter.get_priority(),
                    },
                )
                result = await adapter.fetch(symbol)

                if result:
                    self._active_source = adapter.name
                    logger.info(
                        "Successfully fetched from adapter",
                        extra={
                            "symbol": symbol,
                            "source": adapter.name,
                            "candles": len(result),
                        },
                    )
                    return result
                else:
                    logger.warning(
                        "Adapter returned empty data",
                        extra={"symbol": symbol, "adapter": adapter.name},
                    )
                    errors.append(f"{adapter.name}: empty response")

            except AdapterError as e:
                logger.warning(
                    "Adapter failed",
                    extra={
                        "symbol": symbol,
                        "adapter": adapter.name,
                        "error": str(e),
                    },
                )
                errors.append(f"{adapter.name}: {e}")
            except Exception as e:
                logger.error(
                    "Unexpected adapter error",
                    extra={
                        "symbol": symbol,
                        "adapter": adapter.name,
                        "error": str(e),
                    },
                )
                errors.append(f"{adapter.name}: {e}")

        logger.error(
            "All sources failed",
            extra={"symbol": symbol, "errors": errors},
        )
        raise AllSourcesFailedError(f"All sources failed: {'; '.join(errors)}")

    def get_adapters(self) -> list[DataSourceAdapter]:
        """Return the list of configured adapters."""
        return self._adapters.copy()
