"""Yahoo Finance data adapter.

Project: Pseudo-Live Indian Index Market Data Platform
Version: 1.0
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

import yfinance as yf

from backend.adapters.base import AdapterError, DataSourceAdapter
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

    def __init__(self) -> None:
        self.timeout = 30

    @property
    def name(self) -> str:
        return "yahoo"

    def get_priority(self) -> int:
        return 3

    def _map_symbol(self, symbol: str) -> str:
        """Map common symbols to Yahoo format."""
        return self.SYMBOL_MAP.get(symbol.upper(), symbol.upper())

    async def health_check(self) -> bool:
        """Check if Yahoo Finance is reachable."""
        try:
            ticker = yf.Ticker("^NSEI")
            info = ticker.info
            return info is not None
        except Exception as e:
            logger.warning("Yahoo health check failed", extra={"error": str(e)})
            return False

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
            return await self._fetch_yahoo_data(symbol)
        except Exception as e:
            raise AdapterError(f"Yahoo fetch error: {e}") from e

    async def _fetch_yahoo_data(self, symbol: str) -> list[RawData]:
        """Internal method to fetch data from Yahoo Finance."""
        yahoo_symbol = self._map_symbol(symbol)

        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(
            period="1d",
            interval="1m",
            auto_adjust=True,
            back_adjust=True,
        )

        if df.empty:
            logger.warning("Yahoo returned empty data", extra={"symbol": symbol})
            return []

        candles = []
        for timestamp, row in df.iterrows():
            candle = self._transform_candle(symbol, timestamp, row)
            candles.append(candle)

        logger.info(
            "Yahoo fetch success",
            extra={"symbol": symbol, "count": len(candles)},
        )
        return candles

    def _transform_candle(self, symbol: str, timestamp: datetime, row: Any) -> RawData:
        """Transform Yahoo data row to RawData format."""
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        else:
            timestamp = timestamp.astimezone(timezone.utc)

        timestamp = self._floor_to_minute(timestamp)

        return RawData(
            {
                "symbol": symbol.upper(),
                "timestamp": timestamp,
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]) if "Volume" in row else None,
                "source": "yahoo",
            }
        )

    def _floor_to_minute(self, dt: datetime) -> datetime:
        """Floor timestamp to minute boundary."""
        return dt.replace(second=0, microsecond=0)
