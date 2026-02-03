"""Admin API routes for Silicon Casino.

Provides endpoints for human administrators to:
- Review and manage withdrawal requests
- Create and manage Code Golf challenges
- View platform analytics
- Manage agents and tables
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.core.admin_auth import (
    AdminRole,
    create_admin_token,
    get_current_admin,
    log_admin_action,
    require_permission,
    require_role,
    get_client_ip,
)
from backend.db.database import get_session
from backend.db.models.admin import AdminUser, AdminAuditLog
from backend.db.models.withdrawal import WithdrawalRequest
from backend.db.models.codegolf import CodeGolfChallenge, ChallengeStatus
from backend.db.models.agent import Agent
from backend.services.analytics_service import AnalyticsService


router = APIRouter()


# Request/Response Models
class AdminLoginRequest(BaseModel):
    """Admin login via email (for OAuth flow)."""
    email: str
    id_token: str  # Google OAuth ID token


class WithdrawalActionRequest(BaseModel):
    """Request to approve/reject a withdrawal."""
    rejection_reason: Optional[str] = None


class CreateChallengeRequest(BaseModel):
    """Admin request to create a Code Golf challenge."""
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    test_cases: list[dict] = Field(..., min_length=1)
    difficulty: str = Field("medium", pattern="^(easy|medium|hard|expert)$")
    allowed_languages: Optional[list[str]] = None
    entry_fee: int = Field(0, ge=0)
    duration_hours: int = Field(24, ge=1, le=168)
    starts_at: Optional[str] = None  # ISO format


class AdminCreateRequest(BaseModel):
    """Request to create a new admin user."""
    email: str
    name: str
    role: str = Field("viewer", pattern="^(viewer|moderator|admin)$")


# Dashboard & Analytics
@router.get("/dashboard")
async def get_dashboard(
    admin: dict = Depends(require_permission("view_dashboard")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get admin dashboard with platform overview."""
    analytics = AnalyticsService(session)
    stats = await analytics.get_platform_stats()

    return {
        "stats": {
            "total_agents": stats.total_agents,
            "active_agents_24h": stats.active_agents_24h,
            "active_agents_7d": stats.active_agents_7d,
            "total_hands_played": stats.total_hands_played,
            "total_volume": stats.total_volume,
            "total_rake_collected": stats.total_rake_collected,
            "total_referral_commissions": stats.total_referral_commissions,
            "active_tables": stats.active_tables,
            "active_tournaments": stats.active_tournaments,
            "active_challenges": stats.active_challenges,
            "pending_withdrawals": stats.pending_withdrawals,
        },
        "admin": admin,
    }


@router.get("/analytics")
async def get_analytics(
    days: int = 30,
    admin: dict = Depends(require_permission("view_analytics")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get detailed analytics data."""
    analytics = AnalyticsService(session)

    game_stats = await analytics.get_game_type_stats()
    daily_hands = await analytics.get_daily_hands(days)
    daily_volume = await analytics.get_daily_volume(days)
    top_agents = await analytics.get_top_agents(10)
    big_hands = await analytics.get_recent_big_hands(1000, 10)

    return {
        "game_stats": {
            "poker_hands": game_stats.poker_hands,
            "poker_volume": game_stats.poker_volume,
            "poker_rake": game_stats.poker_rake,
            "tournament_entries": game_stats.tournament_entries,
            "tournament_prize_pools": game_stats.tournament_prize_pools,
            "codegolf_submissions": game_stats.codegolf_submissions,
            "codegolf_prize_pools": game_stats.codegolf_prize_pools,
        },
        "daily_hands": [
            {"date": p.timestamp.isoformat(), "count": p.value}
            for p in daily_hands
        ],
        "daily_volume": [
            {"date": p.timestamp.isoformat(), "volume": p.value}
            for p in daily_volume
        ],
        "top_agents": top_agents,
        "recent_big_hands": big_hands,
    }


# Withdrawal Management
@router.get("/withdrawals")
async def list_withdrawals(
    status_filter: Optional[str] = None,
    limit: int = 50,
    admin: dict = Depends(require_permission("view_withdrawals")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List withdrawal requests."""
    stmt = select(WithdrawalRequest).order_by(WithdrawalRequest.created_at.desc())

    if status_filter:
        stmt = stmt.where(WithdrawalRequest.status == status_filter)

    stmt = stmt.limit(limit)
    result = await session.execute(stmt)
    withdrawals = result.scalars().all()

    return {
        "withdrawals": [
            {
                "id": str(w.id),
                "agent_id": str(w.agent_id),
                "amount": w.amount,
                "destination_address": w.destination_address,
                "chain": w.chain,
                "token": w.token,
                "status": w.status,
                "reviewed_by": w.reviewed_by,
                "reviewed_at": w.reviewed_at.isoformat() if w.reviewed_at else None,
                "rejection_reason": w.rejection_reason,
                "tx_hash": w.tx_hash,
                "created_at": w.created_at.isoformat(),
            }
            for w in withdrawals
        ],
        "count": len(withdrawals),
    }


@router.post("/withdrawals/{withdrawal_id}/approve")
async def approve_withdrawal(
    withdrawal_id: UUID,
    request: Request,
    admin: dict = Depends(require_permission("approve_withdrawals")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Approve a pending withdrawal."""
    withdrawal = await session.get(WithdrawalRequest, withdrawal_id)
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")

    if withdrawal.status != "pending":
        raise HTTPException(status_code=400, detail="Withdrawal is not pending")

    withdrawal.status = "approved"
    withdrawal.reviewed_by = admin["email"]
    withdrawal.reviewed_at = datetime.now(timezone.utc)

    await log_admin_action(
        session=session,
        admin_id=admin["id"],
        action="approve_withdrawal",
        resource_type="withdrawal",
        resource_id=str(withdrawal_id),
        details={"amount": withdrawal.amount},
        ip_address=get_client_ip(request),
    )

    await session.commit()

    return {"message": "Withdrawal approved", "withdrawal_id": str(withdrawal_id)}


@router.post("/withdrawals/{withdrawal_id}/reject")
async def reject_withdrawal(
    withdrawal_id: UUID,
    body: WithdrawalActionRequest,
    request: Request,
    admin: dict = Depends(require_permission("reject_withdrawals")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Reject a pending withdrawal."""
    withdrawal = await session.get(WithdrawalRequest, withdrawal_id)
    if not withdrawal:
        raise HTTPException(status_code=404, detail="Withdrawal not found")

    if withdrawal.status != "pending":
        raise HTTPException(status_code=400, detail="Withdrawal is not pending")

    withdrawal.status = "rejected"
    withdrawal.reviewed_by = admin["email"]
    withdrawal.reviewed_at = datetime.now(timezone.utc)
    withdrawal.rejection_reason = body.rejection_reason

    # TODO: Refund the agent's balance

    await log_admin_action(
        session=session,
        admin_id=admin["id"],
        action="reject_withdrawal",
        resource_type="withdrawal",
        resource_id=str(withdrawal_id),
        details={"reason": body.rejection_reason},
        ip_address=get_client_ip(request),
    )

    await session.commit()

    return {"message": "Withdrawal rejected", "withdrawal_id": str(withdrawal_id)}


# Challenge Management
@router.get("/challenges")
async def list_challenges(
    status_filter: Optional[str] = None,
    admin: dict = Depends(require_permission("view_challenges")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List all Code Golf challenges."""
    stmt = select(CodeGolfChallenge).order_by(CodeGolfChallenge.created_at.desc())

    if status_filter:
        stmt = stmt.where(CodeGolfChallenge.status == status_filter)

    result = await session.execute(stmt)
    challenges = result.scalars().all()

    return {
        "challenges": [
            {
                "id": str(c.id),
                "title": c.title,
                "difficulty": c.difficulty,
                "entry_fee": c.entry_fee,
                "prize_pool": c.prize_pool,
                "status": c.status if isinstance(c.status, str) else c.status.value,
                "starts_at": c.starts_at.isoformat() if c.starts_at else None,
                "ends_at": c.ends_at.isoformat() if c.ends_at else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in challenges
        ],
    }


@router.post("/challenges")
async def create_challenge(
    body: CreateChallengeRequest,
    request: Request,
    admin: dict = Depends(require_permission("manage_challenges")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create a new Code Golf challenge."""
    from backend.game_engine.codegolf.engine import CodeGolfEngine

    starts_at = None
    if body.starts_at:
        starts_at = datetime.fromisoformat(body.starts_at.replace("Z", "+00:00"))

    engine = CodeGolfEngine(session)
    challenge = await engine.create_challenge(
        title=body.title,
        description=body.description,
        test_cases=body.test_cases,
        difficulty=body.difficulty,
        allowed_languages=body.allowed_languages,
        entry_fee=body.entry_fee,
        duration_hours=body.duration_hours,
        starts_at=starts_at,
    )

    await log_admin_action(
        session=session,
        admin_id=admin["id"],
        action="create_challenge",
        resource_type="challenge",
        resource_id=str(challenge.id),
        details={"title": body.title},
        ip_address=get_client_ip(request),
    )

    return {
        "id": str(challenge.id),
        "title": challenge.title,
        "status": challenge.status.value if hasattr(challenge.status, 'value') else challenge.status,
    }


@router.post("/challenges/{challenge_id}/finalize")
async def finalize_challenge(
    challenge_id: UUID,
    request: Request,
    admin: dict = Depends(require_permission("manage_challenges")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Finalize a challenge and distribute prizes."""
    from backend.game_engine.codegolf.engine import CodeGolfEngine

    engine = CodeGolfEngine(session)
    result = await engine.finalize_challenge(challenge_id)

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    await log_admin_action(
        session=session,
        admin_id=admin["id"],
        action="finalize_challenge",
        resource_type="challenge",
        resource_id=str(challenge_id),
        details=result,
        ip_address=get_client_ip(request),
    )

    return result


# Agent Management
@router.get("/agents")
async def list_agents(
    limit: int = 100,
    admin: dict = Depends(require_permission("view_agents")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List all agents."""
    from backend.db.models.wallet import Wallet

    stmt = select(Agent, Wallet.balance).outerjoin(
        Wallet, Wallet.agent_id == Agent.id
    ).order_by(Agent.created_at.desc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    return {
        "agents": [
            {
                "id": str(agent.id),
                "display_name": agent.display_name,
                "is_active": agent.is_active,
                "trust_level": agent.trust_level,
                "balance": balance or 0,
                "created_at": agent.created_at.isoformat(),
            }
            for agent, balance in rows
        ],
    }


@router.post("/agents/{agent_id}/toggle-active")
async def toggle_agent_active(
    agent_id: UUID,
    request: Request,
    admin: dict = Depends(require_permission("manage_agents")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Toggle an agent's active status."""
    agent = await session.get(Agent, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.is_active = not agent.is_active

    await log_admin_action(
        session=session,
        admin_id=admin["id"],
        action="toggle_agent_active",
        resource_type="agent",
        resource_id=str(agent_id),
        details={"is_active": agent.is_active},
        ip_address=get_client_ip(request),
    )

    await session.commit()

    return {
        "agent_id": str(agent_id),
        "is_active": agent.is_active,
    }


# Admin User Management
@router.get("/admins")
async def list_admins(
    admin: dict = Depends(require_permission("manage_admins")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """List all admin users."""
    stmt = select(AdminUser).order_by(AdminUser.created_at.desc())
    result = await session.execute(stmt)
    admins = result.scalars().all()

    return {
        "admins": [
            {
                "id": str(a.id),
                "email": a.email,
                "name": a.name,
                "role": a.role,
                "is_active": a.is_active,
                "last_login_at": a.last_login_at.isoformat() if a.last_login_at else None,
                "created_at": a.created_at.isoformat(),
            }
            for a in admins
        ],
    }


@router.post("/admins")
async def create_admin(
    body: AdminCreateRequest,
    request: Request,
    admin: dict = Depends(require_role(AdminRole.ADMIN)),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create a new admin user."""
    # Check for existing
    stmt = select(AdminUser).where(AdminUser.email == body.email)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Admin with this email already exists")

    new_admin = AdminUser(
        email=body.email,
        name=body.name,
        role=body.role,
    )
    session.add(new_admin)

    await log_admin_action(
        session=session,
        admin_id=admin["id"],
        action="create_admin",
        resource_type="admin",
        resource_id=None,
        details={"email": body.email, "role": body.role},
        ip_address=get_client_ip(request),
    )

    await session.commit()

    return {
        "id": str(new_admin.id),
        "email": new_admin.email,
        "name": new_admin.name,
        "role": new_admin.role,
    }


# Audit Log
@router.get("/audit-log")
async def get_audit_log(
    limit: int = 100,
    admin: dict = Depends(require_permission("view_audit_log")),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get admin audit log."""
    stmt = select(AdminAuditLog).order_by(
        AdminAuditLog.created_at.desc()
    ).limit(limit)

    result = await session.execute(stmt)
    logs = result.scalars().all()

    return {
        "logs": [
            {
                "id": str(log.id),
                "admin_id": str(log.admin_id) if log.admin_id else None,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ],
    }


# Temporary admin login for development (should be replaced with OAuth in production)
@router.post("/dev-login")
async def dev_admin_login(
    email: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Development-only admin login. Replace with OAuth in production."""
    if settings.environment != "development":
        raise HTTPException(status_code=403, detail="Dev login only available in development")

    # Check if admin exists
    stmt = select(AdminUser).where(AdminUser.email == email)
    result = await session.execute(stmt)
    admin = result.scalar_one_or_none()

    if not admin:
        # Create admin in development
        admin = AdminUser(
            email=email,
            name=email.split("@")[0],
            role=AdminRole.ADMIN,
        )
        session.add(admin)
        await session.commit()

    token = create_admin_token(
        admin_id=str(admin.id),
        email=admin.email,
        name=admin.name,
        role=admin.role,
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "admin": {
            "id": str(admin.id),
            "email": admin.email,
            "name": admin.name,
            "role": admin.role,
        },
    }
