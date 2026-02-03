"""Unit tests for rate limiter."""

import pytest
from backend.core.rate_limiter import (
    RateLimitType,
    RateLimitConfig,
    RateLimitResult,
    RATE_LIMITS,
)


class TestRateLimitConfig:
    """Tests for rate limit configuration."""

    def test_config_creation(self):
        """Test creating a rate limit config."""
        config = RateLimitConfig(requests=10, window=60, burst=15)
        assert config.requests == 10
        assert config.window == 60
        assert config.burst_capacity == 15

    def test_config_burst_defaults_to_requests(self):
        """Test burst defaults to requests when not specified."""
        config = RateLimitConfig(requests=10, window=60)
        assert config.burst_capacity == 10

    def test_all_rate_limit_types_configured(self):
        """Test all rate limit types have configurations."""
        for rate_type in RateLimitType:
            assert rate_type in RATE_LIMITS or rate_type == RateLimitType.DEFAULT


class TestRateLimitResult:
    """Tests for rate limit results."""

    def test_result_allowed(self):
        """Test allowed result."""
        result = RateLimitResult(
            allowed=True,
            remaining=5,
            reset_at=1000.0,
        )
        assert result.allowed
        assert result.remaining == 5
        assert result.retry_after is None

    def test_result_blocked(self):
        """Test blocked result with retry_after."""
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            reset_at=1060.0,
            retry_after=60.0,
        )
        assert not result.allowed
        assert result.remaining == 0
        assert result.retry_after == 60.0

    def test_result_headers(self):
        """Test rate limit headers generation."""
        result = RateLimitResult(
            allowed=True,
            remaining=5,
            reset_at=1000.0,
        )
        headers = result.headers
        assert "X-RateLimit-Remaining" in headers
        assert headers["X-RateLimit-Remaining"] == "5"
        assert "X-RateLimit-Reset" in headers

    def test_result_headers_with_retry(self):
        """Test rate limit headers include Retry-After when blocked."""
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            reset_at=1060.0,
            retry_after=60.0,
        )
        headers = result.headers
        assert "Retry-After" in headers
        assert headers["Retry-After"] == "60"


class TestRateLimitTypes:
    """Tests for rate limit type configurations."""

    def test_auth_limit_is_strict(self):
        """Test auth endpoint has strict limits."""
        auth_config = RATE_LIMITS[RateLimitType.AUTH]
        default_config = RATE_LIMITS[RateLimitType.DEFAULT]
        assert auth_config.requests <= default_config.requests

    def test_poker_action_allows_burst(self):
        """Test poker actions allow for burst traffic."""
        poker_config = RATE_LIMITS[RateLimitType.POKER_ACTION]
        assert poker_config.burst is not None
        assert poker_config.burst_capacity > 0

    def test_admin_has_higher_limits(self):
        """Test admin endpoints have higher limits."""
        admin_config = RATE_LIMITS[RateLimitType.ADMIN]
        default_config = RATE_LIMITS[RateLimitType.DEFAULT]
        assert admin_config.requests > default_config.requests
