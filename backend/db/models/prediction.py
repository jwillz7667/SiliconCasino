"""Database models for prediction markets."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base

if TYPE_CHECKING:
    from backend.db.models.agent import Agent


class PredictionMarket(Base):
    """A binary prediction market."""

    __tablename__ = "prediction_markets"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    question: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    status: Mapped[str] = mapped_column(
        Enum("OPEN", "CLOSED", "RESOLVED", "CANCELLED", name="market_status"),
        default="OPEN",
        index=True,
    )

    resolution_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    oracle_source: Mapped[str] = mapped_column(String(50), default="manual")
    oracle_data: Mapped[dict] = mapped_column(JSONB, default={})

    # AMM pools
    yes_pool: Mapped[int] = mapped_column(Integer, default=1000)
    no_pool: Mapped[int] = mapped_column(Integer, default=1000)

    total_volume: Mapped[int] = mapped_column(Integer, default=0)

    # Resolution
    resolved_outcome: Mapped[str | None] = mapped_column(String(10), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    positions: Mapped[list["PredictionPosition"]] = relationship(
        "PredictionPosition", back_populates="market"
    )
    trades: Mapped[list["PredictionTrade"]] = relationship(
        "PredictionTrade", back_populates="market"
    )

    def __repr__(self) -> str:
        return f"<Market {self.id}: {self.question[:30]}...>"


class PredictionPosition(Base):
    """An agent's position in a prediction market."""

    __tablename__ = "prediction_positions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    market_id: Mapped[UUID] = mapped_column(ForeignKey("prediction_markets.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)

    outcome: Mapped[str] = mapped_column(String(10), nullable=False)  # "yes" or "no"
    shares: Mapped[int] = mapped_column(Integer, default=0)
    avg_price: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    cost_basis: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()", onupdate="NOW()"
    )

    # Relationships
    market: Mapped["PredictionMarket"] = relationship(
        "PredictionMarket", back_populates="positions"
    )
    agent: Mapped["Agent"] = relationship("Agent")

    def __repr__(self) -> str:
        return f"<Position {self.agent_id} in {self.market_id}: {self.shares} {self.outcome}>"


class PredictionTrade(Base):
    """Record of a trade in a prediction market."""

    __tablename__ = "prediction_trades"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    market_id: Mapped[UUID] = mapped_column(ForeignKey("prediction_markets.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)

    trade_type: Mapped[str] = mapped_column(String(10), nullable=False)  # "buy" or "sell"
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)  # "yes" or "no"
    shares: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)  # Chips paid/received

    # Snapshot of prices at time of trade
    yes_price_before: Mapped[float] = mapped_column(Numeric(10, 4))
    yes_price_after: Mapped[float] = mapped_column(Numeric(10, 4))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()", index=True
    )

    # Relationships
    market: Mapped["PredictionMarket"] = relationship(
        "PredictionMarket", back_populates="trades"
    )
    agent: Mapped["Agent"] = relationship("Agent")

    def __repr__(self) -> str:
        return f"<Trade {self.trade_type} {self.shares} {self.outcome} @ {self.price}>"
