"""Yahoo Finance data adapter."""

# MODULE: backend/adapters/yahoo.py
# TASK:   CHECKLIST.md §2.1
# SPEC:   BACKEND.md §2.2
# PHASE:  2
# STATUS: In Progress

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import yfinance as yf
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.adapters.base import DataSourceAdapter
from backend.core.config import settings
from backend.core.exceptions import AdapterError
from backend.core.models import RawData

logger = logging.getLogger(__name__)


class YahooAdapter(DataSourceAdapter):
    """Yahoo Finance data source adapter.

    Fetches 1-minute candles for Indian indices using yfinance.
    """

    SYMBOL_MAP = {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "SENSEX": "^BSESN",
    }

    @property
    def name(self) -> str:
        """Get adapter source name.

        Edge Cases:
            - Always lowercase for uniform source tracking.
        """

        return "yahoo"

    def get_priority(self) -> int:
        """Return adapter priority in the chain.

        Edge Cases:
            - Higher numerical value means lower priority.
        """

        return 3

    def _map_symbol(self, symbol: str) -> str:
        """Map common symbols to Yahoo format."""
        return self.SYMBOL_MAP.get(symbol.upper(), symbol.upper())

    async def health_check(self) -> bool:
        """Check if Yahoo Finance is reachable.

        Edge Cases:
            - Returns False if Yahoo API payload is unexpectedly empty.
        """

        try:
            info = await asyncio.to_thread(self._read_ticker_info, "^NSEI")
            return info is not None
        except (ConnectionError, RuntimeError, TimeoutError, ValueError) as e:
            logger.warning("Yahoo health check failed", extra={"error": str(e)})
            return False

    @retry(
        stop=stop_after_attempt(settings.yahoo_max_retries),
        wait=wait_exponential(multiplier=1, max=10),
        retry=retry_if_exception_type(AdapterError),
    )
    async def fetch(self, symbol: str) -> list[RawData]:
        """Fetch OHLC data for a symbol from Yahoo Finance.

        Args:
            symbol: Symbol to fetch (e.g., 'NIFTY', 'BANKNIFTY')

        Returns:
            List of raw OHLC data dictionaries

        Raises:
            AdapterError: On fetch failure
        """
        try:
            return await asyncio.to_thread(self._fetch_yahoo_data_sync, symbol)
        except (ConnectionError, RuntimeError, TimeoutError, ValueError) as e:
            raise AdapterError(
                "Yahoo fetch error",
                source=self.name,
                symbol=symbol.upper(),
                error=str(e),
            ) from e

    def _fetch_yahoo_data_sync(self, symbol: str) -> list[RawData]:
        """Fetch Yahoo OHLC data in a worker thread.

        Edge Cases:
            - Returns empty list when Yahoo has no intraday rows.
        """

        yahoo_symbol = self._map_symbol(symbol)

        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(
            period=settings.yahoo_period,
            interval=settings.yahoo_interval,
            auto_adjust=True,
            back_adjust=True,
        )

        if df.empty:
            logger.warning("Yahoo returned empty data", extra={"symbol": symbol})
            return []

        candles: list[RawData] = []
        for timestamp, row in df.iterrows():
            candle = self._transform_candle(symbol, timestamp, row)
            candles.append(candle)

        logger.info(
            "Yahoo fetch success",
            extra={"symbol": symbol, "count": len(candles)},
        )
        return candles

    def _read_ticker_info(self, symbol: str) -> dict[str, Any] | None:
        """Read Yahoo ticker info in sync context.

        Edge Cases:
            - Returns None if info payload is unavailable.
        """

        ticker = yf.Ticker(symbol)
        info = ticker.info
        if not isinstance(info, dict):
            return None
        return info

    def _transform_candle(self, symbol: str, timestamp: datetime, row: Any) -> RawData:
        """Transform Yahoo data row to RawData format."""
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        else:
            timestamp = timestamp.astimezone(UTC)

        timestamp = self._floor_to_minute(timestamp)

        return {
            "symbol": symbol.upper(),
            "timestamp": timestamp,
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": int(row["Volume"]) if "Volume" in row else None,
            "source": "yahoo",
        }

    def _floor_to_minute(self, dt: datetime) -> datetime:
        """Floor timestamp to minute boundary."""
        return dt.replace(second=0, microsecond=0)
