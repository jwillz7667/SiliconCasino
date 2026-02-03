from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class PokerTable(Base):
    __tablename__ = "poker_tables"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    small_blind: Mapped[int] = mapped_column(BigInteger, nullable=False)
    big_blind: Mapped[int] = mapped_column(BigInteger, nullable=False)
    min_buy_in: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_buy_in: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_players: Mapped[int] = mapped_column(SmallInteger, default=6)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    seats: Mapped[list["TableSeat"]] = relationship(
        "TableSeat", back_populates="table", order_by="TableSeat.seat_number"
    )
    hands: Mapped[list["PokerHand"]] = relationship(
        "PokerHand", back_populates="table", order_by="PokerHand.hand_number.desc()"
    )

    def __repr__(self) -> str:
        return f"<PokerTable {self.name} ({self.id})>"


class TableSeat(Base):
    __tablename__ = "table_seats"
    __table_args__ = (UniqueConstraint("table_id", "seat_number", name="uq_table_seat"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    table_id: Mapped[UUID] = mapped_column(ForeignKey("poker_tables.id"), index=True)
    seat_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    agent_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)
    stack: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), default="empty")

    table: Mapped["PokerTable"] = relationship("PokerTable", back_populates="seats")

    def __repr__(self) -> str:
        return f"<TableSeat {self.seat_number} stack={self.stack}>"


class PokerHand(Base):
    __tablename__ = "poker_hands"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    table_id: Mapped[UUID] = mapped_column(ForeignKey("poker_tables.id"), index=True)
    hand_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    button_seat: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    community_cards: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total_pot: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), default="in_progress")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    table: Mapped["PokerTable"] = relationship("PokerTable", back_populates="hands")
    events: Mapped[list["GameEvent"]] = relationship(
        "GameEvent", back_populates="hand", order_by="GameEvent.sequence_num"
    )

    def __repr__(self) -> str:
        return f"<PokerHand #{self.hand_number} pot={self.total_pot}>"


class GameEvent(Base):
    __tablename__ = "game_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    hand_id: Mapped[UUID] = mapped_column(ForeignKey("poker_hands.id"), index=True)
    sequence_num: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_id: Mapped[UUID | None] = mapped_column(nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    hand: Mapped["PokerHand"] = relationship("PokerHand", back_populates="events")

    def __repr__(self) -> str:
        return f"<GameEvent {self.event_type} #{self.sequence_num}>"
