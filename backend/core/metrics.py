"""Prometheus metrics for Silicon Casino.

Provides observability into system performance, game statistics,
and business metrics for monitoring and alerting.
"""

import time
from contextlib import asynccontextmanager
from functools import wraps
from typing import AsyncGenerator, Callable, Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    Info,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    multiprocess,
    REGISTRY,
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings


# Custom registry for multiprocess mode
def get_registry() -> CollectorRegistry:
    """Get the appropriate registry for the current mode."""
    if settings.environment == "production":
        # In production with multiple workers, use multiprocess mode
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return registry
    return REGISTRY


# Application info
APP_INFO = Info("silicon_casino", "Silicon Casino application information")
APP_INFO.info({
    "version": "0.3.0",
    "environment": settings.environment,
})


# HTTP Request Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being processed",
    ["method", "endpoint"],
)


# WebSocket Metrics
WEBSOCKET_CONNECTIONS = Gauge(
    "websocket_connections_active",
    "Active WebSocket connections",
    ["connection_type"],  # "agent", "spectator"
)

WEBSOCKET_MESSAGES_TOTAL = Counter(
    "websocket_messages_total",
    "Total WebSocket messages",
    ["direction", "message_type"],  # direction: "in", "out"
)


# Poker Game Metrics
POKER_TABLES_ACTIVE = Gauge(
    "poker_tables_active",
    "Currently active poker tables",
    ["table_type"],  # "cash", "tournament"
)

POKER_HANDS_TOTAL = Counter(
    "poker_hands_total",
    "Total poker hands played",
    ["table_type"],
)

POKER_HAND_DURATION = Histogram(
    "poker_hand_duration_seconds",
    "Duration of poker hands",
    [],
    buckets=(5, 10, 30, 60, 120, 300, 600),
)

POKER_ACTIONS_TOTAL = Counter(
    "poker_actions_total",
    "Total poker actions taken",
    ["action_type"],  # "fold", "check", "call", "bet", "raise", "all_in"
)

POKER_POT_SIZE = Histogram(
    "poker_pot_size_chips",
    "Poker pot sizes in chips",
    [],
    buckets=(100, 500, 1000, 2500, 5000, 10000, 25000, 50000, 100000),
)


# Tournament Metrics
TOURNAMENTS_ACTIVE = Gauge(
    "tournaments_active",
    "Currently active tournaments",
    ["format"],  # "freezeout", "rebuy", "turbo"
)

TOURNAMENT_ENTRIES_TOTAL = Counter(
    "tournament_entries_total",
    "Total tournament entries",
    ["format"],
)

TOURNAMENT_PRIZE_POOL = Histogram(
    "tournament_prize_pool_chips",
    "Tournament prize pools in chips",
    [],
    buckets=(1000, 5000, 10000, 50000, 100000, 500000, 1000000),
)


# Code Golf Metrics
CODEGOLF_SUBMISSIONS_TOTAL = Counter(
    "codegolf_submissions_total",
    "Total Code Golf submissions",
    ["language", "result"],  # result: "passed", "failed", "error", "timeout"
)

CODEGOLF_EXECUTION_DURATION = Histogram(
    "codegolf_execution_duration_seconds",
    "Code Golf solution execution time",
    ["language"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
)

CODEGOLF_CODE_LENGTH = Histogram(
    "codegolf_code_length_bytes",
    "Code Golf solution length in bytes",
    ["language"],
    buckets=(10, 50, 100, 200, 500, 1000, 2000, 5000),
)


# Financial Metrics
RAKE_COLLECTED_TOTAL = Counter(
    "rake_collected_chips_total",
    "Total rake collected in chips",
    ["game_type"],  # "poker", "codegolf", "trivia"
)

DEPOSITS_TOTAL = Counter(
    "deposits_total",
    "Total deposits",
    ["token", "chain"],
)

DEPOSITS_AMOUNT = Counter(
    "deposits_amount_total",
    "Total deposit amount",
    ["token", "chain"],
)

WITHDRAWALS_TOTAL = Counter(
    "withdrawals_total",
    "Total withdrawals",
    ["status"],  # "pending", "approved", "rejected", "completed"
)

WITHDRAWALS_AMOUNT = Counter(
    "withdrawals_amount_total",
    "Total withdrawal amount in chips",
    ["status"],
)

REFERRAL_COMMISSIONS_TOTAL = Counter(
    "referral_commissions_chips_total",
    "Total referral commissions paid in chips",
)


# Agent Metrics
AGENTS_REGISTERED_TOTAL = Counter(
    "agents_registered_total",
    "Total agents registered",
)

AGENTS_ACTIVE = Gauge(
    "agents_active",
    "Agents active in last 24 hours",
)


# System Metrics
DATABASE_POOL_SIZE = Gauge(
    "database_pool_size",
    "Database connection pool size",
    ["state"],  # "active", "idle", "overflow"
)

REDIS_CONNECTIONS = Gauge(
    "redis_connections_active",
    "Active Redis connections",
)

RATE_LIMIT_HITS = Counter(
    "rate_limit_hits_total",
    "Rate limit hits",
    ["limit_type", "result"],  # result: "allowed", "blocked"
)


# Helper functions for recording metrics
def record_http_request(method: str, endpoint: str, status: int, duration: float) -> None:
    """Record HTTP request metrics."""
    # Normalize endpoint to reduce cardinality
    normalized = normalize_endpoint(endpoint)
    HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=normalized, status=status).inc()
    HTTP_REQUEST_DURATION.labels(method=method, endpoint=normalized).observe(duration)


def normalize_endpoint(path: str) -> str:
    """Normalize endpoint path to reduce metric cardinality.

    Replaces UUIDs and numeric IDs with placeholders.
    """
    import re
    # Replace UUIDs
    path = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "{id}",
        path,
        flags=re.IGNORECASE,
    )
    # Replace numeric IDs
    path = re.sub(r"/\d+(/|$)", "/{id}\\1", path)
    return path


def record_poker_action(action_type: str) -> None:
    """Record a poker action."""
    POKER_ACTIONS_TOTAL.labels(action_type=action_type).inc()


def record_poker_hand(table_type: str, pot_size: int, duration: float) -> None:
    """Record completion of a poker hand."""
    POKER_HANDS_TOTAL.labels(table_type=table_type).inc()
    POKER_POT_SIZE.observe(pot_size)
    POKER_HAND_DURATION.observe(duration)


def record_rake(game_type: str, amount: int) -> None:
    """Record rake collection."""
    RAKE_COLLECTED_TOTAL.labels(game_type=game_type).inc(amount)


def record_codegolf_submission(
    language: str,
    result: str,
    execution_time: float,
    code_length: int,
) -> None:
    """Record a Code Golf submission."""
    CODEGOLF_SUBMISSIONS_TOTAL.labels(language=language, result=result).inc()
    CODEGOLF_EXECUTION_DURATION.labels(language=language).observe(execution_time)
    CODEGOLF_CODE_LENGTH.labels(language=language).observe(code_length)


def record_deposit(token: str, chain: str, amount: int) -> None:
    """Record a deposit."""
    DEPOSITS_TOTAL.labels(token=token, chain=chain).inc()
    DEPOSITS_AMOUNT.labels(token=token, chain=chain).inc(amount)


def record_withdrawal(status: str, amount: int) -> None:
    """Record a withdrawal."""
    WITHDRAWALS_TOTAL.labels(status=status).inc()
    WITHDRAWALS_AMOUNT.labels(status=status).inc(amount)


def record_referral_commission(amount: int) -> None:
    """Record a referral commission payment."""
    REFERRAL_COMMISSIONS_TOTAL.inc(amount)


def record_rate_limit(limit_type: str, allowed: bool) -> None:
    """Record a rate limit check."""
    result = "allowed" if allowed else "blocked"
    RATE_LIMIT_HITS.labels(limit_type=limit_type, result=result).inc()


@asynccontextmanager
async def track_request_duration(method: str, endpoint: str) -> AsyncGenerator[None, None]:
    """Context manager to track HTTP request duration."""
    normalized = normalize_endpoint(endpoint)
    HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=normalized).inc()
    start_time = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start_time
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=normalized).dec()
        HTTP_REQUEST_DURATION.labels(method=method, endpoint=normalized).observe(duration)


def track_websocket_connection(connection_type: str) -> Callable:
    """Decorator to track WebSocket connection lifecycle."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            WEBSOCKET_CONNECTIONS.labels(connection_type=connection_type).inc()
            try:
                return await func(*args, **kwargs)
            finally:
                WEBSOCKET_CONNECTIONS.labels(connection_type=connection_type).dec()
        return wrapper
    return decorator


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically track HTTP metrics."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        method = request.method
        endpoint = request.url.path
        normalized = normalize_endpoint(endpoint)

        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=normalized).inc()
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            status = response.status_code
        except Exception as e:
            status = 500
            raise
        finally:
            duration = time.perf_counter() - start_time
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method, endpoint=normalized).dec()
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=normalized,
                status=status,
            ).inc()
            HTTP_REQUEST_DURATION.labels(
                method=method,
                endpoint=normalized,
            ).observe(duration)

        return response


async def get_metrics() -> tuple[bytes, str]:
    """Generate Prometheus metrics output."""
    registry = get_registry()
    return generate_latest(registry), CONTENT_TYPE_LATEST
