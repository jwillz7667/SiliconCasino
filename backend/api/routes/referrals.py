"""API routes for the referral system."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import get_current_agent_id
from backend.db.database import get_session
from backend.services.referral_service import ReferralService


router = APIRouter()


class ApplyReferralRequest(BaseModel):
    """Request to apply a referral code."""
    code: str


@router.get("/code")
async def get_referral_code(
    agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get or generate the agent's referral code."""
    service = ReferralService(session)
    code = await service.get_or_create_code(agent_id)

    return {
        "code": code,
        "share_url": f"https://siliconcasino.ai/register?ref={code}",
    }


@router.get("/stats")
async def get_referral_stats(
    agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get referral statistics for the current agent."""
    service = ReferralService(session)
    stats = await service.get_stats(agent_id)

    return {
        "referral_code": stats.referral_code,
        "share_url": f"https://siliconcasino.ai/register?ref={stats.referral_code}",
        "total_referrals": stats.total_referrals,
        "total_commissions": stats.total_commissions,
        "last_30_days_commissions": stats.last_30_days_commissions,
        "referred_agents": stats.referred_agents,
    }


@router.get("/commissions")
async def get_commission_history(
    limit: int = 50,
    agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get commission history for the current agent."""
    service = ReferralService(session)
    history = await service.get_commission_history(agent_id, limit=limit)

    return {
        "commissions": history,
        "count": len(history),
    }


@router.post("/apply")
async def apply_referral(
    request: ApplyReferralRequest,
    agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Apply a referral code to the current agent.

    Note: This is typically done during registration, but can be applied
    within a grace period after registration.
    """
    service = ReferralService(session)
    success = await service.apply_referral(agent_id, request.code)

    if success:
        return {"message": "Referral applied successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid code or agent already has a referrer",
        )


@router.get("/validate/{code}")
async def validate_code(
    code: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Validate a referral code (public endpoint for registration)."""
    service = ReferralService(session)
    referral_code = await service.get_code_by_string(code)

    if referral_code:
        return {
            "valid": True,
            "code": referral_code.code,
        }
    else:
        return {
            "valid": False,
        }
