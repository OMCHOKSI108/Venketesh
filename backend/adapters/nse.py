# MODULE: backend/adapters/nse.py
# TASK:   CHECKLIST.md §1.5
# SPEC:   BACKEND.md §2.2
# PHASE:  1
# STATUS: In Progress

import logging
import random
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.adapters.base import DataSourceAdapter
from backend.core.config import settings
from backend.core.exceptions import AdapterError
from backend.core.models import RawData

logger = logging.getLogger(__name__)

NSE_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


class NSEAdapter(DataSourceAdapter):
    """NSE India data source adapter.

    Fetches 1-minute candles for Indian indices from NSE unofficial endpoints.
    """

    @property
    def name(self) -> str:
        return "nse"

    def get_priority(self) -> int:
        return 2

    def _get_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(NSE_USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }

    async def health_check(self) -> bool:
        """Check if NSE is reachable."""
        try:
            async with httpx.AsyncClient(
                timeout=settings.nse_timeout_seconds
            ) as client:
                response = await client.get(
                    settings.nse_base_url,
                    headers=self._get_headers(),
                )
                return response.status_code == 200
        except Exception as e:
            logger.warning("NSE health check failed", extra={"error": str(e)})
            return False

    async def fetch(self, symbol: str) -> list[RawData]:
        """Fetch OHLC data for a symbol from NSE.

        Args:
            symbol: Symbol to fetch (e.g., 'NIFTY', 'BANKNIFTY')

        Returns:
            List of raw OHLC data dictionaries

        Raises:
            AdapterError: On fetch failure
        """
        try:
            return await self._fetch_nse_data(symbol)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (403, 429):
                raise AdapterError(
                    f"NSE blocked: {e.response.status_code}", ban_detected=True
                ) from e
            raise AdapterError(f"NSE HTTP error: {e}") from e
        except httpx.ConnectError as e:
            raise AdapterError(f"NSE connection error: {e}") from e
        except httpx.TimeoutException as e:
            raise AdapterError(f"NSE timeout: {e}") from e

    async def _fetch_nse_data(self, symbol: str) -> list[RawData]:
        """Internal method to fetch data from NSE.

        NSE doesn't provide a direct API for historical candle data.
        This adapter attempts to use the equity historical data endpoint.
        """
        nse_symbol = self._map_symbol(symbol)

        url = f"{settings.nse_base_url}/api/historical/cm/equity?symbol={nse_symbol}"

        async with httpx.AsyncClient(timeout=settings.nse_timeout_seconds) as client:
            response = await client.get(
                url,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            data = response.json()

            return self._parse_response(symbol, data)

    def _map_symbol(self, symbol: str) -> str:
        """Map common symbols to NSE format."""
        mapping = {
            "NIFTY": "NIFTY",
            "BANKNIFTY": "BANKNIFTY",
            "SENSEX": "SENSEX",
        }
        return mapping.get(symbol.upper(), symbol.upper())

    def _parse_response(self, symbol: str, data: dict[str, Any]) -> list[RawData]:
        """Parse NSE response into RawData format."""
        candles = []

        try:
            grp = data.get("data", [])
            for item in grp:
                if isinstance(item, dict):
                    candle = self._transform_candle(symbol, item)
                    if candle:
                        candles.append(candle)
        except (KeyError, TypeError, ValueError) as e:
            logger.error("Failed to parse NSE response", extra={"error": str(e)})

        return candles

    def _transform_candle(self, symbol: str, item: dict[str, Any]) -> RawData | None:
        """Transform a single NSE data item to RawData format."""
        try:
            timestamp_str = item.get("CH_TIMESTAMP")
            if timestamp_str:
                if isinstance(timestamp_str, int):
                    timestamp = datetime.fromtimestamp(timestamp_str, tz=timezone.utc)
                else:
                    timestamp = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )
            else:
                timestamp = datetime.now(timezone.utc)

            open_price = float(item.get("CH_OPENING_PRICE", 0))
            high_price = float(item.get("CH_TRADE_HIGH_PRICE", 0))
            low_price = float(item.get("CH_TRADE_LOW_PRICE", 0))
            close_price = float(item.get("CH_CLOSING_PRICE", 0))
            volume = int(item.get("CH_TOT_TRADED_QTY", 0))

            timestamp = self._floor_to_minute(timestamp)

            return {
                "symbol": symbol,
                "timestamp": timestamp,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
            }
        except (KeyError, TypeError, ValueError) as e:
            logger.debug("Failed to transform candle", extra={"error": str(e)})
            return None

    def _floor_to_minute(self, dt: datetime) -> datetime:
        """Floor timestamp to minute boundary."""
        return dt.replace(second=0, microsecond=0)
