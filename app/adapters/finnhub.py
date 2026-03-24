import asyncio
from datetime import datetime, timezone
from typing import Optional
import httpx
from app.adapters.base import DataSourceAdapter
from app.core.logging_config import logger


class FinnhubAdapter(DataSourceAdapter):
    SYMBOL_MAP = {
        "NIFTY": "^NSEI",
        "BANKNIFTY": "^NSEBANK",
        "SENSEX": "^BSESN",
        "NIFTYIT": "^NSEMDCP",
        "DOWJONES": "AAPL",
        "NASDAQ": "AMZN",
        "SP500": "SPY",
        "FTSE": "FLOT",
        "DAX": "DAX",
        "NIKKEI": "NIKKEI",
    }

    def __init__(self, api_key: str = "d2m1fi9r01qgtft6o72gd2m1fi9r01qgtft6o730"):
        super().__init__("finnhub")
        self._client: Optional[httpx.AsyncClient] = None
        self.api_key = api_key

    @property
    def base_url(self) -> str:
        return "https://finnhub.io/api/v1"

    @property
    def priority(self) -> int:
        return 3

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                },
            )
        return self._client

    async def fetch(self, symbol: str, timeframe: str = "1d") -> Optional[dict]:
        symbol = self._normalize_symbol(symbol)
        finnhub_symbol = self.SYMBOL_MAP.get(symbol, symbol)

        try:
            return await self._fetch_quote(finnhub_symbol, symbol, timeframe)
        except Exception as e:
            logger.error("finnhub_fetch_error", symbol=symbol, error=str(e))
            return None

    async def _fetch_quote(
        self, fh_symbol: str, original_symbol: str, timeframe: str
    ) -> Optional[dict]:
        client = await self.get_client()

        params = {
            "symbol": fh_symbol,
            "token": self.api_key,
        }

        try:
            response = await client.get("/quote", params=params, timeout=10.0)

            if response.status_code != 200:
                logger.warning("finnhub_api_error", status=response.status_code)
                return None

            data = response.json()

            if "c" not in data or data["c"] == 0:
                return None

            return {
                "symbol": original_symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "timeframe": timeframe,
                "open": data.get("o", data["c"]),
                "high": data.get("h", data["c"]),
                "low": data.get("l", data["c"]),
                "close": data["c"],
                "volume": data.get("v", 0),
                "is_closed": False,
                "source": "finnhub",
            }

        except httpx.TimeoutException:
            logger.warning("finnhub_timeout", symbol=fh_symbol)
            return None
        except Exception as e:
            logger.error("finnhub_fetch_exception", error=str(e))
            return None

    async def fetch_candles(
        self,
        symbol: str,
        resolution: str = "D",
        from_ts: Optional[int] = None,
        to_ts: Optional[int] = None,
    ) -> Optional[list]:
        symbol = self._normalize_symbol(symbol)
        fh_symbol = self.SYMBOL_MAP.get(symbol, symbol)

        if from_ts is None:
            from_ts = int((datetime.now(timezone.utc).timestamp() - 30 * 24 * 3600))
        if to_ts is None:
            to_ts = int(datetime.now(timezone.utc).timestamp())

        client = await self.get_client()
        params = {
            "symbol": fh_symbol,
            "resolution": resolution,
            "from": from_ts,
            "to": to_ts,
            "token": self.api_key,
        }

        try:
            response = await client.get("/stock/candle", params=params, timeout=30.0)
            if response.status_code != 200:
                return None

            data = response.json()
            if data.get("s") != "ok":
                return None

            records = []
            for i in range(len(data.get("t", []))):
                records.append(
                    {
                        "timestamp": datetime.fromtimestamp(
                            data["t"][i], tz=timezone.utc
                        ).isoformat(),
                        "open": data["o"][i],
                        "high": data["h"][i],
                        "low": data["l"][i],
                        "close": data["c"][i],
                        "volume": data["v"][i],
                    }
                )

            return records
        except Exception as e:
            logger.error("finnhub_candles_error", symbol=symbol, error=str(e))
            return None

    async def health_check(self) -> bool:
        try:
            client = await self.get_client()
            response = await client.get(
                "/quote", params={"symbol": "AAPL", "token": self.api_key}, timeout=10.0
            )
            return response.status_code == 200
        except Exception:
            return False
