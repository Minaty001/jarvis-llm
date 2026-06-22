"""
Optional Redis Cache Client

Provides a simple async cache abstraction using Redis.
Only initialized if REDIS_URL is configured.

Usage:
    from utils.redis_cache import cache

    await cache.set("key", {"data": "value"}, ttl=300)
    value = await cache.get("key")
"""

import json
from typing import Any, Optional

from utils.config import settings


class RedisCache:
    """
    Async Redis cache wrapper.

    Gracefully degrades when Redis is not configured — get() returns
    None and set() is a no-op.
    """

    def __init__(self):
        self._client: Optional[Any] = None
        self._enabled: bool = False

    async def initialize(self):
        """
        Initialize the Redis connection pool.

        Called during application startup. Silently skips if
        REDIS_URL is not configured.
        """
        if not settings.redis_url:
            return

        try:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            # Verify connection
            await self._client.ping()
            self._enabled = True
        except Exception:
            self._enabled = False
            self._client = None

    async def close(self):
        """Close the Redis connection pool."""
        if self._client:
            await self._client.aclose()
            self._client = None
            self._enabled = False

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve a value from cache.

        Args:
            key: Cache key.

        Returns:
            Deserialized value, or None if not found or cache unavailable.
        """
        if not self._enabled or not self._client:
            return None
        try:
            value = await self._client.get(key)
            if value is not None:
                return json.loads(value)
        except Exception:
            return None
        return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> bool:
        """
        Store a value in cache with TTL.

        Args:
            key: Cache key.
            value: JSON-serializable value to cache.
            ttl: Time-to-live in seconds (default: 5 minutes).

        Returns:
            True if stored successfully.
        """
        if not self._enabled or not self._client:
            return False
        try:
            serialized = json.dumps(value, default=str)
            await self._client.setex(key, ttl, serialized)
            return True
        except Exception:
            return False

    async def delete(self, key: str) -> bool:
        """
        Remove a key from cache.

        Args:
            key: Cache key to delete.

        Returns:
            True if deleted or cache unavailable.
        """
        if not self._enabled or not self._client:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception:
            return False

    async def flush_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a glob pattern.

        Args:
            pattern: Redis glob pattern (e.g. "conversation:*").

        Returns:
            Number of deleted keys.
        """
        if not self._enabled or not self._client:
            return 0
        try:
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await self._client.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            return deleted
        except Exception:
            return 0


# ── Singleton ──
cache = RedisCache()
