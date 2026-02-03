"""Tournament models for multi-player poker tournaments."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class TournamentStatus(str, Enum):
    REGISTERING = "registering"
    STARTING = "starting"
    RUNNING = "running"
    FINAL_TABLE = "final_table"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TournamentFormat(str, Enum):
    FREEZEOUT = "freezeout"  # No rebuys
    REBUY = "rebuy"  # Rebuys allowed
    TURBO = "turbo"  # Fast blinds
    HYPER_TURBO = "hyper_turbo"  # Very fast blinds


class Tournament(Base):
    """A poker tournament."""

    __tablename__ = "tournaments"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Configuration
    format: Mapped[TournamentFormat] = mapped_column(
        SQLEnum(TournamentFormat), default=TournamentFormat.FREEZEOUT
    )
    buy_in: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rake: Mapped[int] = mapped_column(BigInteger, default=0)  # Tournament fee
    starting_chips: Mapped[int] = mapped_column(BigInteger, default=10000)
    min_players: Mapped[int] = mapped_column(Integer, default=2)
    max_players: Mapped[int] = mapped_column(Integer, default=100)

    # Blind structure (JSON array of levels)
    blind_structure: Mapped[dict] = mapped_column(JSONB, default=list)
    level_duration_minutes: Mapped[int] = mapped_column(Integer, default=15)
    current_level: Mapped[int] = mapped_column(Integer, default=0)

    # Prize structure (JSON: position -> percentage)
    prize_structure: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Status
    status: Mapped[TournamentStatus] = mapped_column(
        SQLEnum(TournamentStatus), default=TournamentStatus.REGISTERING
    )

    # Scheduling
    registration_opens_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    scheduled_start_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Stats
    total_prize_pool: Mapped[int] = mapped_column(BigInteger, default=0)
    entries_count: Mapped[int] = mapped_column(Integer, default=0)
    rebuys_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    entries: Mapped[list["TournamentEntry"]] = relationship(
        "TournamentEntry", back_populates="tournament"
    )
    payouts: Mapped[list["TournamentPayout"]] = relationship(
        "TournamentPayout", back_populates="tournament"
    )

    def __repr__(self) -> str:
        return f"<Tournament {self.name} ({self.status.value})>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "format": self.format.value,
            "buy_in": self.buy_in,
            "rake": self.rake,
            "starting_chips": self.starting_chips,
            "min_players": self.min_players,
            "max_players": self.max_players,
            "blind_structure": self.blind_structure,
            "level_duration_minutes": self.level_duration_minutes,
            "current_level": self.current_level,
            "prize_structure": self.prize_structure,
            "status": self.status.value,
            "scheduled_start_at": self.scheduled_start_at.isoformat() if self.scheduled_start_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_prize_pool": self.total_prize_pool,
            "entries_count": self.entries_count,
            "rebuys_count": self.rebuys_count,
            "created_at": self.created_at.isoformat(),
        }


class TournamentEntry(Base):
    """A player's entry in a tournament."""

    __tablename__ = "tournament_entries"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tournament_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tournaments.id"), nullable=False, index=True
    )
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_eliminated: Mapped[bool] = mapped_column(Boolean, default=False)
    finish_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Chip count
    current_chips: Mapped[int] = mapped_column(BigInteger, default=0)
    rebuys: Mapped[int] = mapped_column(Integer, default=0)
    total_invested: Mapped[int] = mapped_column(BigInteger, default=0)

    # Timestamps
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    eliminated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Current table assignment
    table_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("poker_tables.id"), nullable=True
    )
    seat_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    tournament: Mapped["Tournament"] = relationship("Tournament", back_populates="entries")
    agent = relationship("Agent")

    def __repr__(self) -> str:
        return f"<TournamentEntry {self.agent_id} in {self.tournament_id}>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "tournament_id": str(self.tournament_id),
            "agent_id": str(self.agent_id),
            "is_active": self.is_active,
            "is_eliminated": self.is_eliminated,
            "finish_position": self.finish_position,
            "current_chips": self.current_chips,
            "rebuys": self.rebuys,
            "total_invested": self.total_invested,
            "registered_at": self.registered_at.isoformat(),
            "eliminated_at": self.eliminated_at.isoformat() if self.eliminated_at else None,
            "table_id": str(self.table_id) if self.table_id else None,
            "seat_number": self.seat_number,
        }


class TournamentPayout(Base):
    """Prize payout record for a tournament finish."""

    __tablename__ = "tournament_payouts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tournament_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tournaments.id"), nullable=False, index=True
    )
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )

    finish_position: Mapped[int] = mapped_column(Integer, nullable=False)
    prize_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    tournament: Mapped["Tournament"] = relationship("Tournament", back_populates="payouts")
    agent = relationship("Agent")

    def __repr__(self) -> str:
        return f"<TournamentPayout #{self.finish_position} {self.prize_amount}>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "tournament_id": str(self.tournament_id),
            "agent_id": str(self.agent_id),
            "finish_position": self.finish_position,
            "prize_amount": self.prize_amount,
            "is_paid": self.is_paid,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
        }
