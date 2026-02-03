"""Token bucket rate limiter with Redis backend.

Implements a distributed rate limiter using Redis for state storage,
allowing horizontal scaling across multiple backend instances.
"""

import asyncio
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from uuid import UUID

import redis.asyncio as redis

from backend.config import settings


class RateLimitType(str, Enum):
    """Categories of rate limits for different endpoint types."""
    AUTH = "auth"
    POKER_ACTION = "poker_action"
    WEBSOCKET = "websocket"
    API_READ = "api_read"
    API_WRITE = "api_write"
    ADMIN = "admin"
    DEFAULT = "default"


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for a rate limit bucket."""
    requests: int  # Maximum requests allowed
    window: int  # Time window in seconds
    burst: Optional[int] = None  # Optional burst capacity (defaults to requests)

    @property
    def burst_capacity(self) -> int:
        return self.burst if self.burst is not None else self.requests


# Rate limits per endpoint type
RATE_LIMITS: dict[RateLimitType, RateLimitConfig] = {
    RateLimitType.AUTH: RateLimitConfig(requests=5, window=60),  # 5/min - strict for auth
    RateLimitType.POKER_ACTION: RateLimitConfig(requests=60, window=60, burst=10),  # 60/min with burst
    RateLimitType.WEBSOCKET: RateLimitConfig(requests=100, window=60, burst=20),  # 100/min
    RateLimitType.API_READ: RateLimitConfig(requests=120, window=60),  # 120/min for reads
    RateLimitType.API_WRITE: RateLimitConfig(requests=30, window=60),  # 30/min for writes
    RateLimitType.ADMIN: RateLimitConfig(requests=300, window=60),  # Higher limit for admins
    RateLimitType.DEFAULT: RateLimitConfig(requests=30, window=60),  # 30/min default
}


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    reset_at: float
    retry_after: Optional[float] = None

    @property
    def headers(self) -> dict[str, str]:
        """Generate rate limit headers for HTTP response."""
        headers = {
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(int(self.reset_at)),
        }
        if self.retry_after is not None:
            headers["Retry-After"] = str(int(self.retry_after))
        return headers


class TokenBucketRateLimiter:
    """Token bucket rate limiter with Redis backend.

    Uses atomic Lua script for thread-safe token bucket operations.
    Supports per-agent and per-IP rate limiting with configurable limits.
    """

    # Lua script for atomic token bucket operation
    BUCKET_SCRIPT = """
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local window = tonumber(ARGV[3])
    local now = tonumber(ARGV[4])
    local requested = tonumber(ARGV[5])

    -- Get current bucket state
    local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
    local tokens = tonumber(bucket[1])
    local last_update = tonumber(bucket[2])

    -- Initialize bucket if it doesn't exist
    if tokens == nil then
        tokens = capacity
        last_update = now
    end

    -- Calculate token refill
    local elapsed = now - last_update
    local refill = elapsed * (capacity / window)
    tokens = math.min(capacity, tokens + refill)

    -- Check if request can be fulfilled
    local allowed = 0
    if tokens >= requested then
        tokens = tokens - requested
        allowed = 1
    end

    -- Update bucket state
    redis.call('HMSET', key, 'tokens', tokens, 'last_update', now)
    redis.call('EXPIRE', key, window * 2)

    -- Calculate reset time (when bucket will be full)
    local reset_time = now + ((capacity - tokens) / (capacity / window))

    return {allowed, math.floor(tokens), math.floor(reset_time)}
    """

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url or settings.redis_url
        self._redis: Optional[redis.Redis] = None
        self._script_sha: Optional[str] = None
        self._lock = asyncio.Lock()

    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            async with self._lock:
                if self._redis is None:
                    self._redis = redis.from_url(
                        self._redis_url,
                        encoding="utf-8",
                        decode_responses=True,
                    )
                    # Load the Lua script
                    self._script_sha = await self._redis.script_load(self.BUCKET_SCRIPT)
        return self._redis

    def _make_key(
        self,
        limit_type: RateLimitType,
        identifier: str,
    ) -> str:
        """Generate Redis key for rate limit bucket."""
        return f"ratelimit:{limit_type.value}:{identifier}"

    async def check(
        self,
        limit_type: RateLimitType,
        agent_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        requested: int = 1,
    ) -> RateLimitResult:
        """Check rate limit and consume tokens if allowed.

        Args:
            limit_type: Type of rate limit to apply
            agent_id: Agent UUID for per-agent limiting
            ip_address: Client IP for per-IP limiting (fallback)
            requested: Number of tokens to consume (default 1)

        Returns:
            RateLimitResult with allowed status and limit info
        """
        config = RATE_LIMITS.get(limit_type, RATE_LIMITS[RateLimitType.DEFAULT])

        # Determine identifier (prefer agent_id over IP)
        if agent_id:
            identifier = str(agent_id)
        elif ip_address:
            identifier = f"ip:{ip_address}"
        else:
            identifier = "anonymous"

        key = self._make_key(limit_type, identifier)
        now = time.time()

        try:
            redis_client = await self._get_redis()
            result = await redis_client.evalsha(
                self._script_sha,
                1,  # Number of keys
                key,
                config.burst_capacity,
                config.requests / config.window,  # Refill rate
                config.window,
                now,
                requested,
            )

            allowed, remaining, reset_at = result
            return RateLimitResult(
                allowed=bool(allowed),
                remaining=remaining,
                reset_at=reset_at,
                retry_after=reset_at - now if not allowed else None,
            )

        except redis.RedisError:
            # On Redis failure, allow request but log warning
            # This prevents Redis outage from blocking all traffic
            return RateLimitResult(
                allowed=True,
                remaining=config.requests,
                reset_at=now + config.window,
            )

    async def reset(
        self,
        limit_type: RateLimitType,
        agent_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Reset rate limit bucket for an identifier.

        Useful for admin operations or after successful auth.
        """
        if agent_id:
            identifier = str(agent_id)
        elif ip_address:
            identifier = f"ip:{ip_address}"
        else:
            return False

        key = self._make_key(limit_type, identifier)

        try:
            redis_client = await self._get_redis()
            await redis_client.delete(key)
            return True
        except redis.RedisError:
            return False

    async def get_status(
        self,
        limit_type: RateLimitType,
        agent_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[dict]:
        """Get current rate limit status without consuming tokens."""
        if agent_id:
            identifier = str(agent_id)
        elif ip_address:
            identifier = f"ip:{ip_address}"
        else:
            return None

        key = self._make_key(limit_type, identifier)
        config = RATE_LIMITS.get(limit_type, RATE_LIMITS[RateLimitType.DEFAULT])

        try:
            redis_client = await self._get_redis()
            bucket = await redis_client.hgetall(key)

            if not bucket:
                return {
                    "tokens": config.burst_capacity,
                    "capacity": config.burst_capacity,
                    "window": config.window,
                }

            tokens = float(bucket.get("tokens", config.burst_capacity))
            last_update = float(bucket.get("last_update", time.time()))

            # Calculate current tokens with refill
            now = time.time()
            elapsed = now - last_update
            refill = elapsed * (config.burst_capacity / config.window)
            current_tokens = min(config.burst_capacity, tokens + refill)

            return {
                "tokens": int(current_tokens),
                "capacity": config.burst_capacity,
                "window": config.window,
                "reset_in": int((config.burst_capacity - current_tokens) / (config.burst_capacity / config.window)),
            }

        except redis.RedisError:
            return None

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


# Global rate limiter instance
rate_limiter = TokenBucketRateLimiter()


# Convenience functions
async def check_rate_limit(
    limit_type: RateLimitType,
    agent_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
) -> RateLimitResult:
    """Check rate limit using global limiter."""
    return await rate_limiter.check(limit_type, agent_id, ip_address)


async def reset_rate_limit(
    limit_type: RateLimitType,
    agent_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
) -> bool:
    """Reset rate limit using global limiter."""
    return await rate_limiter.reset(limit_type, agent_id, ip_address)
