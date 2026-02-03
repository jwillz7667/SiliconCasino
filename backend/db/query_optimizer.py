"""Query caching layer for optimized database access.

Provides Redis-based caching for frequently accessed, read-heavy queries
with automatic invalidation and TTL-based expiration.
"""

import hashlib
import json
import pickle
from datetime import timedelta
from typing import Any, Callable, Optional, TypeVar, Union
from uuid import UUID

import redis.asyncio as redis

from backend.config import settings


T = TypeVar("T")


class UUIDEncoder(json.JSONEncoder):
    """JSON encoder that handles UUIDs."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, UUID):
            return str(obj)
        return super().default(obj)


def make_cache_key(*args, prefix: str = "cache", **kwargs) -> str:
    """Generate a cache key from arguments.

    Creates a deterministic hash of the arguments to use as Redis key.
    """
    # Serialize arguments to a string
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = ":".join(key_parts)

    # Hash for consistent key length
    key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

    return f"{prefix}:{key_hash}"


class QueryCache:
    """Redis-based query cache for database results.

    Features:
    - Automatic serialization/deserialization
    - TTL-based expiration
    - Namespace-based invalidation
    - Graceful degradation on Redis failure
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=False,  # We use pickle, need bytes
            )
        return self._redis

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        try:
            client = await self._get_redis()
            data = await client.get(key)
            if data is None:
                return None
            return pickle.loads(data)
        except (redis.RedisError, pickle.UnpicklingError):
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Union[int, timedelta] = 300,
    ) -> bool:
        """Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be picklable)
            ttl: Time to live in seconds or timedelta

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            client = await self._get_redis()
            data = pickle.dumps(value)
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            await client.setex(key, ttl, data)
            return True
        except (redis.RedisError, pickle.PicklingError):
            return False

    async def delete(self, key: str) -> bool:
        """Delete a specific key from cache."""
        try:
            client = await self._get_redis()
            await client.delete(key)
            return True
        except redis.RedisError:
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern: Redis glob pattern (e.g., "cache:poker:*")

        Returns:
            Number of keys deleted
        """
        try:
            client = await self._get_redis()
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)
                if keys:
                    await client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            return deleted
        except redis.RedisError:
            return 0

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Union[int, timedelta] = 300,
    ) -> Any:
        """Get from cache or compute and cache value.

        Args:
            key: Cache key
            factory: Async callable that produces the value if not cached
            ttl: Time to live

        Returns:
            Cached or computed value
        """
        value = await self.get(key)
        if value is not None:
            return value

        # Compute value
        if callable(factory):
            value = await factory() if hasattr(factory, "__await__") else factory()
        else:
            value = factory

        # Cache it
        await self.set(key, value, ttl)
        return value

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global cache instance
query_cache = QueryCache()


# Cache namespaces for organized invalidation
class CacheNamespace:
    """Cache key prefixes for different data types."""
    AGENT = "cache:agent"
    TABLE = "cache:table"
    TOURNAMENT = "cache:tournament"
    CHALLENGE = "cache:challenge"
    STATS = "cache:stats"
    LEADERBOARD = "cache:leaderboard"
    WALLET = "cache:wallet"


# Convenience functions for common cache operations
async def cache_agent_stats(agent_id: UUID, stats: dict, ttl: int = 300) -> bool:
    """Cache agent statistics."""
    key = f"{CacheNamespace.AGENT}:{agent_id}:stats"
    return await query_cache.set(key, stats, ttl)


async def get_agent_stats(agent_id: UUID) -> Optional[dict]:
    """Get cached agent statistics."""
    key = f"{CacheNamespace.AGENT}:{agent_id}:stats"
    return await query_cache.get(key)


async def invalidate_agent_stats(agent_id: UUID) -> bool:
    """Invalidate agent statistics cache."""
    key = f"{CacheNamespace.AGENT}:{agent_id}:stats"
    return await query_cache.delete(key)


async def cache_table_state(table_id: UUID, state: dict, ttl: int = 10) -> bool:
    """Cache table state (short TTL for real-time data)."""
    key = f"{CacheNamespace.TABLE}:{table_id}:state"
    return await query_cache.set(key, state, ttl)


async def get_table_state(table_id: UUID) -> Optional[dict]:
    """Get cached table state."""
    key = f"{CacheNamespace.TABLE}:{table_id}:state"
    return await query_cache.get(key)


async def cache_leaderboard(
    leaderboard_type: str,
    data: list,
    ttl: int = 60,
) -> bool:
    """Cache leaderboard data."""
    key = f"{CacheNamespace.LEADERBOARD}:{leaderboard_type}"
    return await query_cache.set(key, data, ttl)


async def get_leaderboard(leaderboard_type: str) -> Optional[list]:
    """Get cached leaderboard."""
    key = f"{CacheNamespace.LEADERBOARD}:{leaderboard_type}"
    return await query_cache.get(key)


async def invalidate_leaderboard(leaderboard_type: str) -> bool:
    """Invalidate leaderboard cache."""
    key = f"{CacheNamespace.LEADERBOARD}:{leaderboard_type}"
    return await query_cache.delete(key)


async def invalidate_all_leaderboards() -> int:
    """Invalidate all leaderboard caches."""
    return await query_cache.delete_pattern(f"{CacheNamespace.LEADERBOARD}:*")


async def cache_challenge_details(challenge_id: UUID, details: dict, ttl: int = 300) -> bool:
    """Cache Code Golf challenge details."""
    key = f"{CacheNamespace.CHALLENGE}:{challenge_id}"
    return await query_cache.set(key, details, ttl)


async def get_challenge_details(challenge_id: UUID) -> Optional[dict]:
    """Get cached challenge details."""
    key = f"{CacheNamespace.CHALLENGE}:{challenge_id}"
    return await query_cache.get(key)


async def invalidate_challenge(challenge_id: UUID) -> bool:
    """Invalidate challenge cache."""
    key = f"{CacheNamespace.CHALLENGE}:{challenge_id}"
    return await query_cache.delete(key)


def cached(
    namespace: str,
    ttl: Union[int, timedelta] = 300,
    key_builder: Optional[Callable[..., str]] = None,
):
    """Decorator for caching async function results.

    Args:
        namespace: Cache namespace prefix
        ttl: Time to live
        key_builder: Optional function to build cache key from args

    Example:
        @cached("stats:agent", ttl=300)
        async def get_agent_stats(agent_id: UUID) -> dict:
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            # Build cache key
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                key = make_cache_key(*args, prefix=namespace, **kwargs)

            # Try cache first
            cached_value = await query_cache.get(key)
            if cached_value is not None:
                return cached_value

            # Compute value
            result = await func(*args, **kwargs)

            # Cache result
            await query_cache.set(key, result, ttl)

            return result

        return wrapper
    return decorator
