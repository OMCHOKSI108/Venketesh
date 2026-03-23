import json
from datetime import datetime, timedelta
from typing import Optional, Any
import redis.asyncio as redis
from app.config import get_settings

settings = get_settings()


class CacheService:
    def __init__(self):
        self._client: Optional[redis.Redis] = None

    async def get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None

    async def get(self, key: str) -> Optional[str]:
        client = await self.get_client()
        return await client.get(key)

    async def set(
        self, key: str, value: Any, ttl: Optional[int] = None, ex: Optional[int] = None
    ) -> bool:
        client = await self.get_client()
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        if ttl:
            ex = ttl
        return await client.set(key, value, ex=ex)

    async def delete(self, key: str) -> int:
        client = await self.get_client()
        return await client.delete(key)

    async def exists(self, key: str) -> bool:
        client = await self.get_client()
        return await client.exists(key) > 0

    async def get_json(self, key: str) -> Optional[dict]:
        value = await self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    async def set_json(self, key: str, value: dict, ttl: Optional[int] = None) -> bool:
        return await self.set(key, json.dumps(value), ttl=ttl)

    async def publish(self, channel: str, message: Any) -> int:
        client = await self.get_client()
        if isinstance(message, (dict, list)):
            message = json.dumps(message)
        return await client.publish(channel, message)

    async def subscribe(self, channel: str):
        client = await self.get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(channel)
        return pubsub

    def ohlc_key(self, symbol: str, timeframe: str) -> str:
        return f"ohlc:{symbol}:{timeframe}:current"

    def ohlc_latest_ts_key(self, symbol: str, timeframe: str) -> str:
        return f"ohlc:{symbol}:{timeframe}:latest_ts"

    def health_key(self, source: str) -> str:
        return f"health:{source}"

    def ws_subscriptions_key(self, symbol: str) -> str:
        return f"ws:subscriptions:{symbol}"

    async def cache_ohlc(self, symbol: str, timeframe: str, data: dict, ttl: int = 60) -> bool:
        key = self.ohlc_key(symbol, timeframe)
        return await self.set_json(key, data, ttl=ttl)

    async def get_cached_ohlc(self, symbol: str, timeframe: str) -> Optional[dict]:
        key = self.ohlc_key(symbol, timeframe)
        return await self.get_json(key)

    async def cache_source_health(self, source: str, status: dict, ttl: int = 30) -> bool:
        key = self.health_key(source)
        return await self.set_json(key, status, ttl=ttl)

    async def get_source_health(self, source: str) -> Optional[dict]:
        key = self.health_key(source)
        return await self.get_json(key)


cache_service = CacheService()
