# MODULE: backend/services/aggregator.py
# TASK:   CHECKLIST.md §2.2
# SPEC:   BACKEND.md §2.2.1
# PHASE:  2
# STATUS: In Progress

import logging
import time
from typing import Optional

from backend.adapters.base import DataSourceAdapter
from backend.core.exceptions import AdapterError
from backend.core.exceptions import AllSourcesFailedError
from backend.core.models import RawData

logger = logging.getLogger(__name__)


class AggregatorService:
    """Aggregate market data through priority-ordered adapters.

    Edge Cases:
        - Returns first successful non-empty response.
        - Raises `AllSourcesFailedError` when all adapters fail or return empty.
    """

    def __init__(self, adapters: list[DataSourceAdapter]) -> None:
        """Initialize aggregator with sorted adapters.

        Args:
            adapters: Data source adapters to evaluate by priority.

        Edge Cases:
            - Empty adapter list is allowed but always raises on fetch.
        """

        self._adapters = sorted(adapters, key=lambda adapter: adapter.get_priority())
        self._active_source: Optional[str] = None

    @property
    def active_source(self) -> Optional[str]:
        """Get last successful adapter name.

        Edge Cases:
            - Returns `None` before the first successful fetch.
        """

        return self._active_source

    async def fetch(self, symbol: str, timeframe: str = "1m") -> list[RawData]:
        """Fetch data using failover across configured adapters.

        Args:
            symbol: Requested market symbol.
            timeframe: Requested timeframe.

        Returns:
            Raw OHLC rows from the first successful adapter.

        Raises:
            AllSourcesFailedError: When no adapter returns valid data.

        Edge Cases:
            - Empty responses are treated as adapter failures.
        """

        errors: list[str] = []
        for adapter in self._adapters:
            started_at = time.perf_counter()
            try:
                logger.info(
                    "aggregator_try_source",
                    extra={
                        "source": adapter.name,
                        "symbol": symbol,
                        "latency_ms": 0,
                        "status": "trying",
                        "timeframe": timeframe,
                        "priority": adapter.get_priority(),
                    },
                )
                rows = await adapter.fetch(symbol)
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                if not rows:
                    errors.append(f"{adapter.name}: empty response")
                    logger.warning(
                        "aggregator_empty_response",
                        extra={
                            "source": adapter.name,
                            "symbol": symbol,
                            "latency_ms": latency_ms,
                            "status": "empty",
                        },
                    )
                    continue

                self._active_source = adapter.name
                logger.info(
                    "aggregator_source_success",
                    extra={
                        "source": adapter.name,
                        "symbol": symbol,
                        "latency_ms": latency_ms,
                        "status": "ok",
                        "count": len(rows),
                    },
                )
                return rows
            except AdapterError as exc:
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                errors.append(f"{adapter.name}: {exc}")
                logger.warning(
                    "aggregator_source_failed",
                    extra={
                        "source": adapter.name,
                        "symbol": symbol,
                        "latency_ms": latency_ms,
                        "status": "error",
                        "error": str(exc),
                    },
                )

        logger.error(
            "aggregator_all_sources_failed",
            extra={
                "source": "aggregator",
                "symbol": symbol,
                "latency_ms": 0,
                "status": "error",
                "errors": errors,
            },
        )
        raise AllSourcesFailedError(
            "All sources failed",
            symbol=symbol,
            timeframe=timeframe,
            errors=errors,
        )

    def get_adapters(self) -> list[DataSourceAdapter]:
        """Return configured adapters.

        Edge Cases:
            - Returns a shallow copy to protect internal ordering.
        """

        return list(self._adapters)
