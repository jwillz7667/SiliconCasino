"""Admin authentication and authorization.

Provides OAuth-based authentication for human administrators,
separate from the agent authentication system.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.database import get_session


# Admin roles with hierarchical permissions
class AdminRole:
    VIEWER = "viewer"  # Can view data only
    MODERATOR = "moderator"  # Can manage games, approve withdrawals
    ADMIN = "admin"  # Full access including user management


ROLE_PERMISSIONS = {
    AdminRole.VIEWER: {
        "view_dashboard",
        "view_agents",
        "view_withdrawals",
        "view_challenges",
        "view_analytics",
    },
    AdminRole.MODERATOR: {
        "view_dashboard",
        "view_agents",
        "view_withdrawals",
        "view_challenges",
        "view_analytics",
        "manage_challenges",
        "approve_withdrawals",
        "reject_withdrawals",
        "manage_tables",
    },
    AdminRole.ADMIN: {
        "view_dashboard",
        "view_agents",
        "view_withdrawals",
        "view_challenges",
        "view_analytics",
        "manage_challenges",
        "approve_withdrawals",
        "reject_withdrawals",
        "manage_tables",
        "manage_admins",
        "manage_agents",
        "view_audit_log",
        "system_settings",
    },
}


security = HTTPBearer()


def create_admin_token(
    admin_id: str,
    email: str,
    name: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a JWT token for an admin user."""
    to_encode: dict[str, Any] = {
        "sub": admin_id,
        "email": email,
        "name": name,
        "role": role,
        "type": "admin",
    }
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=8))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_admin_token(token: str) -> dict[str, Any]:
    """Decode and validate an admin JWT token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid admin token",
            )
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current authenticated admin user."""
    payload = decode_admin_token(credentials.credentials)

    # Import here to avoid circular dependency
    from backend.db.models.admin import AdminUser

    admin = await session.get(AdminUser, UUID(payload["sub"]))
    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account not found or inactive",
        )

    # Update last login
    admin.last_login_at = datetime.now(timezone.utc)
    await session.commit()

    return {
        "id": str(admin.id),
        "email": admin.email,
        "name": admin.name,
        "role": admin.role,
    }


def require_permission(permission: str):
    """Dependency that requires a specific permission."""
    async def check_permission(admin: dict = Depends(get_current_admin)) -> dict:
        role = admin.get("role", AdminRole.VIEWER)
        permissions = ROLE_PERMISSIONS.get(role, set())

        if permission not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required",
            )

        return admin

    return check_permission


def require_role(min_role: str):
    """Dependency that requires at least a specific role level."""
    role_hierarchy = [AdminRole.VIEWER, AdminRole.MODERATOR, AdminRole.ADMIN]

    async def check_role(admin: dict = Depends(get_current_admin)) -> dict:
        admin_role = admin.get("role", AdminRole.VIEWER)

        admin_level = role_hierarchy.index(admin_role) if admin_role in role_hierarchy else -1
        min_level = role_hierarchy.index(min_role) if min_role in role_hierarchy else 999

        if admin_level < min_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {min_role} or higher required",
            )

        return admin

    return check_role


async def log_admin_action(
    session: AsyncSession,
    admin_id: str,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Log an admin action to the audit log."""
    from backend.db.models.admin import AdminAuditLog

    log_entry = AdminAuditLog(
        admin_id=UUID(admin_id),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address,
    )
    session.add(log_entry)
    await session.commit()


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    if request.client:
        return request.client.host

    return "unknown"
