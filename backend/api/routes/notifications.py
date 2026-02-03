"""API routes for push notifications."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.core.security import get_current_agent_id
from backend.db.database import get_session
from backend.services.notification_service import NotificationService


router = APIRouter()


class SubscribeRequest(BaseModel):
    """Request to subscribe to push notifications."""
    endpoint: str
    p256dh_key: str
    auth_key: str


class PreferencesRequest(BaseModel):
    """Request to update notification preferences."""
    big_hands: Optional[bool] = None
    tournament_start: Optional[bool] = None
    challenge_results: Optional[bool] = None
    referral_earnings: Optional[bool] = None


@router.get("/vapid-key")
async def get_vapid_key() -> dict:
    """Get the VAPID public key for push subscriptions."""
    if not settings.vapid_public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Push notifications not configured",
        )
    return {"publicKey": settings.vapid_public_key}


@router.post("/subscribe")
async def subscribe(
    request: SubscribeRequest,
    agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Subscribe to push notifications."""
    service = NotificationService(session)

    subscription = await service.add_subscription(
        agent_id=agent_id,
        endpoint=request.endpoint,
        p256dh_key=request.p256dh_key,
        auth_key=request.auth_key,
    )

    return {
        "id": str(subscription.id),
        "message": "Subscribed to push notifications",
    }


@router.post("/unsubscribe")
async def unsubscribe(
    request: SubscribeRequest,
    agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Unsubscribe from push notifications."""
    service = NotificationService(session)

    removed = await service.remove_subscription(
        agent_id=agent_id,
        endpoint=request.endpoint,
    )

    if removed:
        return {"message": "Unsubscribed from push notifications"}
    else:
        return {"message": "Subscription not found"}


@router.get("/preferences")
async def get_preferences(
    agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get notification preferences."""
    service = NotificationService(session)
    prefs = await service.get_preferences(agent_id)

    if prefs:
        return {
            "big_hands": prefs.big_hands,
            "tournament_start": prefs.tournament_start,
            "challenge_results": prefs.challenge_results,
            "referral_earnings": prefs.referral_earnings,
        }
    else:
        # Return defaults
        return {
            "big_hands": True,
            "tournament_start": True,
            "challenge_results": True,
            "referral_earnings": True,
        }


@router.put("/preferences")
async def update_preferences(
    request: PreferencesRequest,
    agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Update notification preferences."""
    service = NotificationService(session)

    prefs = await service.set_preferences(
        agent_id=agent_id,
        big_hands=request.big_hands,
        tournament_start=request.tournament_start,
        challenge_results=request.challenge_results,
        referral_earnings=request.referral_earnings,
    )

    return {
        "big_hands": prefs.big_hands,
        "tournament_start": prefs.tournament_start,
        "challenge_results": prefs.challenge_results,
        "referral_earnings": prefs.referral_earnings,
    }
