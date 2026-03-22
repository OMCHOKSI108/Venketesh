# MODULE: backend/db/redis_client.py
# TASK:   CHECKLIST.md §2.3
# SPEC:   BACKEND.md §4.3
# PHASE:  2
# STATUS: In Progress

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

from backend.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client for cache and pub/sub operations.

    Edge Cases:
        - Returns safe defaults when connection is unavailable.
        - Serializes payloads as JSON strings for interoperability.
    """

    def __init__(self) -> None:
        """Initialize redis client placeholders.

        Edge Cases:
            - Actual connection is deferred to `connect`.
        """

        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Open Redis connection pool.

        Edge Cases:
            - Connection failures are logged and client remains `None`.
        """

        try:
            self._pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=settings.redis_pool_size,
            )
            self._client = redis.Redis(connection_pool=self._pool)
            await self._client.ping()
            logger.info(
                "redis_connected",
                extra={
                    "source": "redis",
                    "symbol": "",
                    "latency_ms": 0,
                    "status": "ok",
                },
            )
        except (
            redis.ConnectionError,
            redis.TimeoutError,
            redis.RedisError,
            OSError,
        ) as exc:
            logger.error(
                "redis_connect_failed",
                extra={
                    "source": "redis",
                    "symbol": "",
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                },
            )
            self._pool = None
            self._client = None

    async def disconnect(self) -> None:
        """Close Redis connection pool.

        Edge Cases:
            - Safe to call when no pool was created.
        """

        if self._pool is None:
            return
        await self._pool.disconnect()
        self._pool = None
        self._client = None

    async def set_ohlc(
        self, symbol: str, timeframe: str, data: list[dict[str, Any]]
    ) -> bool:
        """Set current OHLC array cache.

        Args:
            symbol: Symbol identifier.
            timeframe: Candle timeframe.
            data: OHLC candle dictionaries.

        Returns:
            True when write succeeds.

        Edge Cases:
            - Returns False when client is unavailable.
        """

        if self._client is None:
            return False
        try:
            key = self._ohlc_key(symbol, timeframe, "current")
            await self._client.setex(
                key,
                settings.redis_ohlc_ttl_seconds,
                json.dumps(data),
            )
            return True
        except (redis.RedisError, TypeError, ValueError) as exc:
            logger.error(
                "redis_set_ohlc_failed",
                extra={
                    "source": "redis",
                    "symbol": symbol.upper(),
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                },
            )
            return False

    async def get_ohlc(
        self, symbol: str, timeframe: str
    ) -> Optional[list[dict[str, Any]]]:
        """Get cached OHLC array from Redis.

        Args:
            symbol: Symbol identifier.
            timeframe: Candle timeframe.

        Returns:
            Cached list or `None`.

        Edge Cases:
            - Invalid JSON values are treated as cache misses.
        """

        if self._client is None:
            return None
        try:
            key = self._ohlc_key(symbol, timeframe, "current")
            raw_value = await self._client.get(key)
            if raw_value is None:
                return None
            return json.loads(raw_value)
        except (redis.RedisError, json.JSONDecodeError, TypeError) as exc:
            logger.error(
                "redis_get_ohlc_failed",
                extra={
                    "source": "redis",
                    "symbol": symbol.upper(),
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                },
            )
            return None

    async def set_latest_candle(
        self, symbol: str, timeframe: str, candle: dict[str, Any]
    ) -> bool:
        """Set latest OHLC candle cache entry.

        Args:
            symbol: Symbol identifier.
            timeframe: Candle timeframe.
            candle: Latest candle payload.

        Returns:
            True when write succeeds.

        Edge Cases:
            - Returns False when serialization fails.
        """

        if self._client is None:
            return False
        try:
            key = self._ohlc_key(symbol, timeframe, "latest")
            await self._client.setex(
                key,
                settings.redis_ohlc_ttl_seconds,
                json.dumps(candle),
            )
            return True
        except (redis.RedisError, TypeError, ValueError) as exc:
            logger.error(
                "redis_set_latest_failed",
                extra={
                    "source": "redis",
                    "symbol": symbol.upper(),
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                },
            )
            return False

    async def get_latest_candle(
        self, symbol: str, timeframe: str
    ) -> Optional[dict[str, Any]]:
        """Get latest candle from Redis cache.

        Args:
            symbol: Symbol identifier.
            timeframe: Candle timeframe.

        Returns:
            Latest candle payload or `None`.

        Edge Cases:
            - Invalid cache value returns `None`.
        """

        if self._client is None:
            return None
        try:
            key = self._ohlc_key(symbol, timeframe, "latest")
            raw_value = await self._client.get(key)
            if raw_value is None:
                return None
            return json.loads(raw_value)
        except (redis.RedisError, json.JSONDecodeError, TypeError) as exc:
            logger.error(
                "redis_get_latest_failed",
                extra={
                    "source": "redis",
                    "symbol": symbol.upper(),
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                },
            )
            return None

    async def publish(self, channel: str, message: dict[str, Any]) -> int:
        """Publish message to Redis pub/sub channel.

        Args:
            channel: Channel name.
            message: JSON serializable message.

        Returns:
            Subscriber count reported by Redis.

        Edge Cases:
            - Returns 0 when client is unavailable or publish fails.
        """

        if self._client is None:
            return 0
        try:
            return await self._client.publish(channel, json.dumps(message))
        except (redis.RedisError, TypeError, ValueError) as exc:
            logger.error(
                "redis_publish_failed",
                extra={
                    "source": "redis",
                    "symbol": "",
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                    "channel": channel,
                },
            )
            return 0

    async def subscribe(self, channel: str) -> Optional[redis.client.PubSub]:
        """Subscribe to Redis pub/sub channel.

        Args:
            channel: Channel name to subscribe.

        Returns:
            PubSub object when successful.

        Edge Cases:
            - Returns `None` when client is unavailable.
        """

        if self._client is None:
            return None
        try:
            pubsub = self._client.pubsub()
            await pubsub.subscribe(channel)
            return pubsub
        except redis.RedisError as exc:
            logger.error(
                "redis_subscribe_failed",
                extra={
                    "source": "redis",
                    "symbol": "",
                    "latency_ms": 0,
                    "status": "error",
                    "error": str(exc),
                    "channel": channel,
                },
            )
            return None

    def _ohlc_key(self, symbol: str, timeframe: str, suffix: str) -> str:
        """Build Redis cache key with project convention.

        Args:
            symbol: Symbol identifier.
            timeframe: Candle timeframe.
            suffix: Key suffix (`current` or `latest`).

        Returns:
            Redis key string.

        Edge Cases:
            - Symbol is normalized to uppercase for key consistency.
        """

        return f"ohlc:{symbol.upper()}:{timeframe}:{suffix}"


redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """Get singleton Redis client.

    Edge Cases:
        - Creates and connects client lazily.
    """

    global redis_client
    if redis_client is None:
        redis_client = RedisClient()
        await redis_client.connect()
    return redis_client
