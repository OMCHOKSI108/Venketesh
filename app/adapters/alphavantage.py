import asyncio
from datetime import datetime, timezone
from typing import Optional
import httpx
from app.adapters.base import DataSourceAdapter
from app.core.logging_config import logger


class AlphaVantageAdapter(DataSourceAdapter):
    SYMBOL_MAP = {
        "NIFTY": "NIFTY",
        "BANKNIFTY": "BANKNIFTY",
        "SENSEX": "SENSEX",
        "NIFTYIT": "NIFTYIT",
        "DOWJONES": "DJI",
        "NASDAQ": "IXIC",
        "SP500": "SPX",
        "FTSE": "FTSE",
        "DAX": "DAX",
        "NIKKEI": "N225",
    }

    def __init__(self, api_key: str = "4MWG5D5P63I244XN"):
        super().__init__("alphavantage")
        self._client: Optional[httpx.AsyncClient] = None
        self.api_key = api_key

    @property
    def base_url(self) -> str:
        return "https://www.alphavantage.co"

    @property
    def priority(self) -> int:
        return 2

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
        av_symbol = self.SYMBOL_MAP.get(symbol, symbol)

        try:
            return await self._fetch_quote(av_symbol, symbol, timeframe)
        except Exception as e:
            logger.error("alphavantage_fetch_error", symbol=symbol, error=str(e))
            return None

    async def _fetch_quote(
        self, av_symbol: str, original_symbol: str, timeframe: str
    ) -> Optional[dict]:
        client = await self.get_client()

        params = {
            "function": "GLOBAL_QUOTE",
            "symbol": av_symbol,
            "apikey": self.api_key,
        }

        try:
            response = await client.get("/query", params=params, timeout=15.0)

            if response.status_code != 200:
                logger.warning("alphavantage_api_error", status=response.status_code)
                return None

            data = response.json()

            if "Global Quote" not in data or not data["Global Quote"]:
                return None

            quote = data["Global Quote"]
            price = float(quote.get("05. price", 0))
            open_price = float(quote.get("02. open", price))
            high = float(quote.get("03. high", price))
            low = float(quote.get("04. low", price))
            volume = int(quote.get("06. volume", 0))

            return {
                "symbol": original_symbol,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "timeframe": timeframe,
                "open": open_price,
                "high": high,
                "low": low,
                "close": price,
                "volume": volume,
                "is_closed": quote.get("09. market_closed", "false").lower() == "true",
                "source": "alphavantage",
            }

        except httpx.TimeoutException:
            logger.warning("alphavantage_timeout", symbol=av_symbol)
            return None
        except Exception as e:
            logger.error("alphavantage_fetch_exception", error=str(e))
            return None

    async def fetch_intraday(self, symbol: str, interval: str = "5min") -> Optional[list]:
        symbol = self._normalize_symbol(symbol)
        av_symbol = self.SYMBOL_MAP.get(symbol, symbol)

        client = await self.get_client()
        params = {
            "function": "TIME_SERIES_INTRADAY",
            "symbol": av_symbol,
            "interval": interval,
            "outputsize": "compact",
            "apikey": self.api_key,
        }

        try:
            response = await client.get("/query", params=params, timeout=30.0)
            if response.status_code != 200:
                return None

            data = response.json()
            time_series_key = f"Time Series ({interval})"

            if time_series_key not in data:
                return None

            records = []
            for ts, values in data[time_series_key].items():
                records.append(
                    {
                        "timestamp": ts,
                        "open": float(values.get("1. open", 0)),
                        "high": float(values.get("2. high", 0)),
                        "low": float(values.get("3. low", 0)),
                        "close": float(values.get("4. close", 0)),
                        "volume": int(values.get("5. volume", 0)),
                    }
                )

            return sorted(records, key=lambda x: x["timestamp"])
        except Exception as e:
            logger.error("alphavantage_intraday_error", symbol=symbol, error=str(e))
            return None

    async def health_check(self) -> bool:
        try:
            client = await self.get_client()
            response = await client.get(
                "/query",
                params={"function": "GLOBAL_QUOTE", "symbol": "IBM", "apikey": self.api_key},
                timeout=10.0,
            )
            return response.status_code == 200
        except Exception:
            return False
