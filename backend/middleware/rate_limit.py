"""FastAPI middleware for rate limiting.

Applies rate limits based on endpoint patterns and authentication state.
"""

import re
from typing import Callable, Optional
from uuid import UUID

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.config import settings
from backend.core.rate_limiter import (
    RateLimitType,
    check_rate_limit,
    RateLimitResult,
)
from backend.core.security import decode_token


# Route patterns mapped to rate limit types
ROUTE_PATTERNS: list[tuple[re.Pattern, RateLimitType, list[str]]] = [
    # Auth endpoints - strictest limits
    (re.compile(r"^/api/auth/(register|login|token)"), RateLimitType.AUTH, ["POST"]),

    # Poker actions - game-critical, need higher limits
    (re.compile(r"^/api/poker/tables/[^/]+/action"), RateLimitType.POKER_ACTION, ["POST"]),
    (re.compile(r"^/api/poker/tables/[^/]+/(join|leave|sit|stand)"), RateLimitType.POKER_ACTION, ["POST"]),

    # WebSocket - handled separately but included for completeness
    (re.compile(r"^/api/ws"), RateLimitType.WEBSOCKET, ["GET"]),

    # Admin endpoints - higher limits for admins
    (re.compile(r"^/api/admin/"), RateLimitType.ADMIN, ["GET", "POST", "PUT", "DELETE"]),

    # Read-heavy endpoints
    (re.compile(r"^/api/(poker|trivia|predictions|tournaments|spectator|stats)/"), RateLimitType.API_READ, ["GET"]),
    (re.compile(r"^/api/wallet/balance"), RateLimitType.API_READ, ["GET"]),

    # Write endpoints
    (re.compile(r"^/api/"), RateLimitType.API_WRITE, ["POST", "PUT", "DELETE"]),
]

# Endpoints exempt from rate limiting
EXEMPT_PATTERNS: list[re.Pattern] = [
    re.compile(r"^/health$"),
    re.compile(r"^/docs"),
    re.compile(r"^/openapi.json$"),
    re.compile(r"^/$"),
    re.compile(r"^/static/"),
]


def get_client_ip(request: Request) -> str:
    """Extract client IP from request, handling proxies."""
    # Check X-Forwarded-For header (set by reverse proxies)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Get the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header (nginx)
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


def get_rate_limit_type(path: str, method: str) -> Optional[RateLimitType]:
    """Determine rate limit type for a request."""
    # Check if exempt
    for pattern in EXEMPT_PATTERNS:
        if pattern.match(path):
            return None

    # Find matching route pattern
    for pattern, limit_type, methods in ROUTE_PATTERNS:
        if pattern.match(path) and method.upper() in methods:
            return limit_type

    # Default limit for unmatched API routes
    if path.startswith("/api/"):
        return RateLimitType.DEFAULT

    return None


def extract_agent_id_from_request(request: Request) -> Optional[UUID]:
    """Try to extract agent_id from JWT token in Authorization header."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]  # Remove "Bearer " prefix
    try:
        payload = decode_token(token)
        agent_id = payload.get("sub")
        if agent_id:
            return UUID(agent_id)
    except Exception:
        pass

    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces rate limits on API endpoints.

    Features:
    - Per-agent rate limiting for authenticated requests
    - Per-IP rate limiting for unauthenticated requests
    - Different limits for different endpoint types
    - Graceful degradation on Redis failure
    - Rate limit headers in response
    """

    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ) -> Response:
        # Skip if disabled
        if not self.enabled:
            return await call_next(request)

        # Determine rate limit type
        path = request.url.path
        method = request.method
        limit_type = get_rate_limit_type(path, method)

        # Skip if no rate limit applies
        if limit_type is None:
            return await call_next(request)

        # Extract identifiers
        agent_id = extract_agent_id_from_request(request)
        ip_address = get_client_ip(request)

        # Check rate limit
        result: RateLimitResult = await check_rate_limit(
            limit_type=limit_type,
            agent_id=agent_id,
            ip_address=ip_address,
        )

        if not result.allowed:
            # Return 429 Too Many Requests
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "error": "too_many_requests",
                    "retry_after": int(result.retry_after) if result.retry_after else 60,
                },
                headers=result.headers,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in result.headers.items():
            response.headers[key] = value

        return response


class WebSocketRateLimiter:
    """Rate limiter specifically for WebSocket connections and messages.

    Used within WebSocket handlers since middleware doesn't apply to WS.
    """

    async def check_connection(
        self,
        agent_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> RateLimitResult:
        """Check if a new WebSocket connection is allowed."""
        return await check_rate_limit(
            limit_type=RateLimitType.WEBSOCKET,
            agent_id=agent_id,
            ip_address=ip_address,
        )

    async def check_message(
        self,
        agent_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
    ) -> RateLimitResult:
        """Check if a WebSocket message can be processed."""
        return await check_rate_limit(
            limit_type=RateLimitType.POKER_ACTION,
            agent_id=agent_id,
            ip_address=ip_address,
        )


# Global WebSocket rate limiter instance
ws_rate_limiter = WebSocketRateLimiter()
