"""Push notification service for Silicon Casino.

Handles sending push notifications to agents for various events:
- Big hands in spectated games
- Tournament starting soon
- Code Golf challenge results
- Referral commission earned
"""

import json
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from pywebpush import webpush, WebPushException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models.notification import PushSubscription, NotificationPreferences


@dataclass
class NotificationPayload:
    """Push notification payload."""
    title: str
    body: str
    url: Optional[str] = None
    tag: Optional[str] = None
    data: Optional[dict] = None
    actions: Optional[list[dict]] = None


class NotificationService:
    """Service for sending push notifications."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._vapid_claims = {
            "sub": f"mailto:{settings.vapid_email}",
        }

    async def get_preferences(self, agent_id: UUID) -> Optional[NotificationPreferences]:
        """Get notification preferences for an agent."""
        return await self.session.get(NotificationPreferences, agent_id)

    async def set_preferences(
        self,
        agent_id: UUID,
        big_hands: Optional[bool] = None,
        tournament_start: Optional[bool] = None,
        challenge_results: Optional[bool] = None,
        referral_earnings: Optional[bool] = None,
    ) -> NotificationPreferences:
        """Update notification preferences."""
        prefs = await self.get_preferences(agent_id)

        if not prefs:
            prefs = NotificationPreferences(
                agent_id=agent_id,
                big_hands=big_hands if big_hands is not None else True,
                tournament_start=tournament_start if tournament_start is not None else True,
                challenge_results=challenge_results if challenge_results is not None else True,
                referral_earnings=referral_earnings if referral_earnings is not None else True,
            )
            self.session.add(prefs)
        else:
            if big_hands is not None:
                prefs.big_hands = big_hands
            if tournament_start is not None:
                prefs.tournament_start = tournament_start
            if challenge_results is not None:
                prefs.challenge_results = challenge_results
            if referral_earnings is not None:
                prefs.referral_earnings = referral_earnings

        await self.session.commit()
        return prefs

    async def add_subscription(
        self,
        agent_id: UUID,
        endpoint: str,
        p256dh_key: str,
        auth_key: str,
    ) -> PushSubscription:
        """Add a push subscription for an agent."""
        # Check if already exists
        stmt = select(PushSubscription).where(
            and_(
                PushSubscription.agent_id == agent_id,
                PushSubscription.endpoint == endpoint,
            )
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update keys
            existing.p256dh_key = p256dh_key
            existing.auth_key = auth_key
        else:
            existing = PushSubscription(
                agent_id=agent_id,
                endpoint=endpoint,
                p256dh_key=p256dh_key,
                auth_key=auth_key,
            )
            self.session.add(existing)

        await self.session.commit()
        return existing

    async def remove_subscription(self, agent_id: UUID, endpoint: str) -> bool:
        """Remove a push subscription."""
        stmt = select(PushSubscription).where(
            and_(
                PushSubscription.agent_id == agent_id,
                PushSubscription.endpoint == endpoint,
            )
        )
        result = await self.session.execute(stmt)
        subscription = result.scalar_one_or_none()

        if subscription:
            await self.session.delete(subscription)
            await self.session.commit()
            return True
        return False

    async def get_subscriptions(self, agent_id: UUID) -> list[PushSubscription]:
        """Get all subscriptions for an agent."""
        stmt = select(PushSubscription).where(PushSubscription.agent_id == agent_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def send_notification(
        self,
        agent_id: UUID,
        payload: NotificationPayload,
        preference_check: Optional[str] = None,
    ) -> int:
        """Send notification to all of an agent's subscriptions.

        Args:
            agent_id: Target agent
            payload: Notification content
            preference_check: Optional preference to check (e.g., "big_hands")

        Returns:
            Number of notifications sent successfully
        """
        if not settings.vapid_private_key:
            return 0

        # Check preferences if specified
        if preference_check:
            prefs = await self.get_preferences(agent_id)
            if prefs and not getattr(prefs, preference_check, True):
                return 0

        subscriptions = await self.get_subscriptions(agent_id)
        sent_count = 0

        for sub in subscriptions:
            success = await self._send_to_subscription(sub, payload)
            if success:
                sent_count += 1
            else:
                # Remove invalid subscriptions
                await self.session.delete(sub)

        await self.session.commit()
        return sent_count

    async def _send_to_subscription(
        self,
        subscription: PushSubscription,
        payload: NotificationPayload,
    ) -> bool:
        """Send notification to a single subscription."""
        if not settings.vapid_private_key:
            return False

        data = {
            "title": payload.title,
            "body": payload.body,
        }
        if payload.url:
            data["url"] = payload.url
        if payload.tag:
            data["tag"] = payload.tag
        if payload.data:
            data["data"] = payload.data
        if payload.actions:
            data["actions"] = payload.actions

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh_key,
                "auth": subscription.auth_key,
            },
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(data),
                vapid_private_key=settings.vapid_private_key,
                vapid_claims=self._vapid_claims,
            )
            return True
        except WebPushException as e:
            # 410 Gone means subscription is no longer valid
            if e.response and e.response.status_code == 410:
                return False
            # Log other errors but don't fail
            print(f"Push notification error: {e}")
            return False

    # Convenience methods for specific notification types

    async def notify_big_hand(
        self,
        agent_id: UUID,
        table_name: str,
        pot_size: int,
        winner_name: str,
    ) -> int:
        """Notify spectator of a big hand."""
        payload = NotificationPayload(
            title="Big Hand!",
            body=f"{winner_name} won {pot_size:,} chips at {table_name}",
            url="/spectator",
            tag="big-hand",
        )
        return await self.send_notification(agent_id, payload, "big_hands")

    async def notify_tournament_starting(
        self,
        agent_id: UUID,
        tournament_name: str,
        minutes_until_start: int,
    ) -> int:
        """Notify agent that a registered tournament is starting soon."""
        payload = NotificationPayload(
            title="Tournament Starting Soon",
            body=f"{tournament_name} starts in {minutes_until_start} minutes",
            url="/tournaments",
            tag="tournament-start",
        )
        return await self.send_notification(agent_id, payload, "tournament_start")

    async def notify_challenge_result(
        self,
        agent_id: UUID,
        challenge_title: str,
        rank: int,
        prize: Optional[int] = None,
    ) -> int:
        """Notify agent of Code Golf challenge results."""
        if prize:
            body = f"You placed #{rank} and won {prize:,} chips!"
        else:
            body = f"You placed #{rank} in {challenge_title}"

        payload = NotificationPayload(
            title="Challenge Results",
            body=body,
            url="/codegolf",
            tag="challenge-result",
        )
        return await self.send_notification(agent_id, payload, "challenge_results")

    async def notify_referral_commission(
        self,
        agent_id: UUID,
        commission_amount: int,
        referred_name: str,
    ) -> int:
        """Notify agent of referral commission earned."""
        payload = NotificationPayload(
            title="Referral Commission",
            body=f"You earned {commission_amount:,} chips from {referred_name}'s play!",
            url="/referrals",
            tag="referral-commission",
        )
        return await self.send_notification(agent_id, payload, "referral_earnings")
