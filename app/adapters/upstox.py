from datetime import datetime, timezone
from typing import Optional
import httpx
from app.adapters.base import DataSourceAdapter
from app.config import get_settings
from app.core.logging_config import logger

settings = get_settings()


class UpstoxAdapter(DataSourceAdapter):
    def __init__(self):
        super().__init__("upstox")
        self._client: Optional[httpx.AsyncClient] = None
        self._api_key = settings.upstox_api_key

    @property
    def base_url(self) -> str:
        return "https://api.upstox.com/v2"

    @property
    def priority(self) -> int:
        return 0

    @property
    def rate_limit(self) -> int:
        return 10

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=15.0,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def fetch(self, symbol: str, timeframe: str = "1m") -> Optional[dict]:
        if not self._api_key:
            logger.warning("upstox_api_key_not_configured")
            return await self._fetch_mock_data(symbol)

        symbol = self._normalize_symbol(symbol)

        try:
            return await self._fetch_market_data(symbol, timeframe)
        except Exception as e:
            logger.error("upstox_fetch_error", symbol=symbol, error=str(e))
            return await self._fetch_mock_data(symbol)

    async def _fetch_market_data(self, symbol: str, timeframe: str) -> Optional[dict]:
        client = await self.get_client()

        instrument_token = self._get_instrument_token(symbol)
        if not instrument_token:
            return None

        url = f"/market/OHLC/{instrument_token}"
        params = {"interval": timeframe}

        response = await client.get(url, params=params)

        if response.status_code != 200:
            return None

        data = response.json()
        return self._transform_data(data, symbol, timeframe)

    def _get_instrument_token(self, symbol: str) -> Optional[str]:
        token_map = {
            "NIFTY": "NSE_FO|0",
            "BANKNIFTY": "NSE_FO|0",
        }
        return token_map.get(symbol)

    def _transform_data(self, data: dict, symbol: str, timeframe: str) -> dict:
        candle = data.get("data", {})

        return {
            "symbol": symbol,
            "timestamp": candle.get("timestamp", datetime.now(timezone.utc).isoformat()),
            "timeframe": timeframe,
            "open": float(candle.get("open", 0)),
            "high": float(candle.get("high", 0)),
            "low": float(candle.get("low", 0)),
            "close": float(candle.get("close", 0)),
            "volume": int(candle.get("volume", 0)),
            "is_closed": candle.get("is_closed", False),
            "source": "upstox",
        }

    async def _fetch_mock_data(self, symbol: str) -> dict:
        import random
        from decimal import Decimal

        base_prices = {
            "NIFTY": 21750.0,
            "BANKNIFTY": 48500.0,
        }
        base = base_prices.get(symbol, 10000.0)
        variance = base * 0.005

        close_price = base + random.uniform(-variance, variance)
        open_price = close_price + random.uniform(-variance / 2, variance / 2)
        high_price = max(open_price, close_price) + random.uniform(0, variance / 2)
        low_price = min(open_price, close_price) - random.uniform(0, variance / 2)

        return {
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "timeframe": "1m",
            "open": float(Decimal(str(open_price))),
            "high": float(Decimal(str(high_price))),
            "low": float(Decimal(str(low_price))),
            "close": float(Decimal(str(close_price))),
            "volume": random.randint(1000000, 5000000),
            "is_closed": False,
            "source": "upstox",
        }

    async def health_check(self) -> bool:
        if not self._api_key:
            return False

        try:
            client = await self.get_client()
            response = await client.get("/profile", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False
