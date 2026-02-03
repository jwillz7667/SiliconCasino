"""Database models for push notifications."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.db.database import Base


class PushSubscription(Base):
    """Push notification subscription for an agent."""

    __tablename__ = "push_subscriptions"
    __table_args__ = (
        UniqueConstraint("agent_id", "endpoint", name="uq_push_sub_agent_endpoint"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh_key: Mapped[str] = mapped_column(Text, nullable=False)
    auth_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class NotificationPreferences(Base):
    """Notification preferences for an agent."""

    __tablename__ = "notification_preferences"

    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    big_hands: Mapped[bool] = mapped_column(Boolean, default=True)
    tournament_start: Mapped[bool] = mapped_column(Boolean, default=True)
    challenge_results: Mapped[bool] = mapped_column(Boolean, default=True)
    referral_earnings: Mapped[bool] = mapped_column(Boolean, default=True)
