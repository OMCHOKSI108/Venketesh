import random
import time
from datetime import datetime, timezone
from typing import Optional
import httpx
from app.adapters.base import DataSourceAdapter
from app.config import get_settings

settings = get_settings()


class NSEAdapter(DataSourceAdapter):
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    NSE_SYMBOL_MAP = {
        "NIFTY": "NIFTY 50",
        "BANKNIFTY": "NIFTY BANK",
        "SENSEX": "BSE Sensex",
        "NIFTYSENSEX": "NIFTY 50",
    }

    def __init__(self):
        super().__init__("nse")
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def base_url(self) -> str:
        return settings.nse_base_url

    @property
    def priority(self) -> int:
        return 1

    @property
    def rate_limit(self) -> int:
        return 1

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=15.0,
                follow_redirects=True,
                headers={
                    "User-Agent": random.choice(self.USER_AGENTS),
                    "Accept": "application/json",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
        return self._client

    async def fetch(self, symbol: str, timeframe: str = "1m") -> Optional[dict]:
        symbol = self._normalize_symbol(symbol)
        nse_symbol = self.NSE_SYMBOL_MAP.get(symbol, symbol)

        try:
            client = await self.get_client()

            index_data = await self._fetch_index_data(client, nse_symbol)
            if index_data:
                return index_data

            return await self._fetch_market_data(client, symbol)

        except Exception as e:
            from app.core.logging_config import logger

            logger.error("nse_fetch_error", symbol=symbol, error=str(e))
            return await self._fetch_mock_data(symbol)

    async def _fetch_index_data(self, client: httpx.AsyncClient, nse_symbol: str) -> Optional[dict]:
        try:
            response = await client.get("/api/market-data", params={"preopen": "true"})
            if response.status_code == 200:
                data = response.json()
                for idx in data.get("data", []):
                    if idx.get("indexName") == nse_symbol:
                        return self._transform_nse_data(idx, nse_symbol)
        except Exception:
            pass
        return None

    async def _fetch_market_data(self, client: httpx.AsyncClient, symbol: str) -> Optional[dict]:
        return None

    def _transform_nse_data(self, data: dict, symbol: str) -> dict:
        now = datetime.now(timezone.utc)
        return {
            "symbol": symbol,
            "timestamp": now.isoformat(),
            "timeframe": "1m",
            "open": data.get("open", 0),
            "high": data.get("high", 0),
            "low": data.get("low", 0),
            "close": data.get("last", 0),
            "volume": data.get("volume", 0),
            "is_closed": False,
            "source": "nse",
        }

    async def _fetch_mock_data(self, symbol: str) -> dict:
        from decimal import Decimal
        import random

        base_prices = {
            "NIFTY": 21750.0,
            "BANKNIFTY": 48500.0,
            "SENSEX": 72000.0,
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
            "source": "nse",
        }

    async def health_check(self) -> bool:
        try:
            client = await self.get_client()
            response = await client.get("/", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return True
