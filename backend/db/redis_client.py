# MODULE: backend/db/redis_client.py
# TASK:   CHECKLIST.md §2.3 Redis Integration
# SPEC:   BACKEND.md §4.3 (Redis Schema)
# PHASE:  2
# STATUS: In Progress

import json
import logging
from typing import Any, Optional

import redis.asyncio as redis

from backend.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client for OHLC data caching and pub/sub.

    Edge Cases:
        - If Redis is unavailable, operations fail gracefully without crashing.
        - All methods are async for non-blocking I/O.
    """

    def __init__(self) -> None:
        self._pool: Optional[redis.ConnectionPool] = None
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Initialize Redis connection pool."""
        try:
            self._pool = redis.ConnectionPool.from_url(
                settings.redis_url,
                decode_responses=True,
                max_connections=50,
            )
            self._client = redis.Redis(connection_pool=self._pool)
            await self._client.ping()
            logger.info("Redis connected", extra={"url": settings.redis_url})
        except Exception as e:
            logger.error("Redis connection failed", extra={"error": str(e)})
            self._pool = None
            self._client = None

    async def disconnect(self) -> None:
        """Close Redis connection pool."""
        if self._pool:
            await self._pool.disconnect()
            logger.info("Redis disconnected")

    async def is_connected(self) -> bool:
        """Check if Redis is connected."""
        if not self._client:
            return False
        try:
            await self._client.ping()
            return True
        except Exception:
            return False

    def _get_key(self, symbol: str, timeframe: str, suffix: str = "current") -> str:
        """Generate Redis key for OHLC data."""
        return f"ohlc:{symbol}:{timeframe}:{suffix}"

    async def set_ohlc(
        self, symbol: str, timeframe: str, data: list[dict[str, Any]]
    ) -> bool:
        """Store OHLC data in Redis with TTL.

        Args:
            symbol: Market symbol
            timeframe: Time resolution
            data: List of OHLC candles (as dicts)

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            logger.warning("Redis not connected, skipping set_ohlc")
            return False

        try:
            key = self._get_key(symbol, timeframe, "current")
            json_data = json.dumps(data)
            await self._client.setex(key, 60, json_data)
            logger.debug(
                "OHLC data cached",
                extra={"symbol": symbol, "timeframe": timeframe, "count": len(data)},
            )
            return True
        except Exception as e:
            logger.error(
                "Failed to cache OHLC data",
                extra={"symbol": symbol, "error": str(e)},
            )
            return False

    async def get_ohlc(self, symbol: str, timeframe: str) -> Optional[list[dict]]:
        """Retrieve OHLC data from Redis.

        Args:
            symbol: Market symbol
            timeframe: Time resolution

        Returns:
            List of OHLC candles or None if not found
        """
        if not self._client:
            return None

        try:
            key = self._get_key(symbol, timeframe, "current")
            data = await self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(
                "Failed to retrieve OHLC data",
                extra={"symbol": symbol, "error": str(e)},
            )
            return None

    async def set_latest_candle(
        self, symbol: str, timeframe: str, candle: dict[str, Any]
    ) -> bool:
        """Store the latest single candle.

        Args:
            symbol: Market symbol
            timeframe: Time resolution
            candle: OHLC candle dict

        Returns:
            True if successful
        """
        if not self._client:
            return False

        try:
            key = self._get_key(symbol, timeframe, "latest")
            await self._client.setex(key, 60, json.dumps(candle))
            return True
        except Exception as e:
            logger.error(
                "Failed to cache latest candle",
                extra={"symbol": symbol, "error": str(e)},
            )
            return False

    async def get_latest_candle(
        self, symbol: str, timeframe: str
    ) -> Optional[dict[str, Any]]:
        """Get the latest candle from Redis."""
        if not self._client:
            return None

        try:
            key = self._get_key(symbol, timeframe, "latest")
            data = await self._client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception:
            return None

    async def publish(self, channel: str, message: dict[str, Any]) -> int:
        """Publish message to Redis channel.

        Args:
            channel: Channel name
            message: Message to publish (will be JSON serialized)

        Returns:
            Number of subscribers or 0 if failed
        """
        if not self._client:
            return 0

        try:
            result = await self._client.publish(channel, json.dumps(message))
            return result
        except Exception as e:
            logger.error(
                "Failed to publish message",
                extra={"channel": channel, "error": str(e)},
            )
            return 0

    async def subscribe(self, channel: str) -> Optional[redis.client.PubSub]:
        """Create a subscription to a channel."""
        if not self._client:
            return None

        try:
            pubsub = self._client.pubsub()
            await pubsub.subscribe(channel)
            return pubsub
        except Exception as e:
            logger.error(
                "Failed to subscribe",
                extra={"channel": channel, "error": str(e)},
            )
            return None


redis_client: Optional[RedisClient] = None


async def get_redis_client() -> RedisClient:
    """Get or create Redis client singleton."""
    global redis_client
    if redis_client is None:
        redis_client = RedisClient()
        await redis_client.connect()
    return redis_client
