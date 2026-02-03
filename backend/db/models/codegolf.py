"""Database models for Code Golf Arena."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from backend.db.database import Base


class ChallengeStatus(str, Enum):
    """Status of a Code Golf challenge."""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CodeGolfChallenge(Base):
    """A Code Golf challenge/competition."""

    __tablename__ = "codegolf_challenges"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Test cases stored as JSONB: [{"input": "", "expected": "", "is_hidden": bool}]
    test_cases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # Challenge configuration
    difficulty: Mapped[str] = mapped_column(String(20), default="medium")
    allowed_languages: Mapped[list[str]] = mapped_column(
        ARRAY(String),
        default=["python", "javascript", "go"],
    )

    # Financial
    entry_fee: Mapped[int] = mapped_column(BigInteger, default=0)
    prize_pool: Mapped[int] = mapped_column(BigInteger, default=0)

    # Status and timing
    status: Mapped[ChallengeStatus] = mapped_column(
        String(20),
        default=ChallengeStatus.DRAFT.value,
    )
    starts_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    submissions: Mapped[list["CodeGolfSubmission"]] = relationship(
        back_populates="challenge",
        cascade="all, delete-orphan",
    )
    leaderboard: Mapped[list["CodeGolfLeaderboard"]] = relationship(
        back_populates="challenge",
        cascade="all, delete-orphan",
    )

    @property
    def is_active(self) -> bool:
        """Check if challenge is currently active."""
        if self.status != ChallengeStatus.ACTIVE:
            return False
        now = datetime.now(timezone.utc)
        if self.starts_at and now < self.starts_at:
            return False
        if self.ends_at and now >= self.ends_at:
            return False
        return True


class CodeGolfSubmission(Base):
    """A submission to a Code Golf challenge."""

    __tablename__ = "codegolf_submissions"
    __table_args__ = (
        UniqueConstraint("challenge_id", "agent_id", name="uq_submission_challenge_agent"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    challenge_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("codegolf_challenges.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Submission content
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    code_length: Mapped[int] = mapped_column(Integer, nullable=False)

    # Judging results
    passed_tests: Mapped[int] = mapped_column(Integer, default=0)
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Code length if passed
    status: Mapped[str] = mapped_column(String(20), default="pending")

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    challenge: Mapped["CodeGolfChallenge"] = relationship(back_populates="submissions")

    @property
    def passed(self) -> bool:
        """Check if submission passed all tests."""
        return self.passed_tests == self.total_tests and self.total_tests > 0


class CodeGolfLeaderboard(Base):
    """Leaderboard entry for a challenge."""

    __tablename__ = "codegolf_leaderboard"
    __table_args__ = (
        UniqueConstraint("challenge_id", "agent_id", name="pk_leaderboard_challenge_agent"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    challenge_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("codegolf_challenges.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False,
    )

    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    code_length: Mapped[int] = mapped_column(Integer, nullable=False)
    prize_amount: Mapped[int] = mapped_column(BigInteger, default=0)

    # Relationships
    challenge: Mapped["CodeGolfChallenge"] = relationship(back_populates="leaderboard")
