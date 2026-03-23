from abc import ABC, abstractmethod
from typing import Optional
import httpx
from app.core.logging_config import logger


class DataSourceAdapter(ABC):
    def __init__(self, name: str):
        self.name = name
        self._client: Optional[httpx.AsyncClient] = None

    @property
    @abstractmethod
    def base_url(self) -> str:
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        pass

    @property
    def rate_limit(self) -> int:
        return 10

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    @abstractmethod
    async def fetch(self, symbol: str, timeframe: str = "1m") -> Optional[dict]:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass

    async def rate_limit_remaining(self) -> int:
        return self.rate_limit

    def _normalize_symbol(self, symbol: str) -> str:
        return symbol.upper().strip()

    def _normalize_timeframe(self, timeframe: str) -> str:
        return timeframe.lower().strip()
