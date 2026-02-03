from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base

if TYPE_CHECKING:
    from backend.db.models.agent import Agent


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), unique=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    agent: Mapped["Agent"] = relationship("Agent", back_populates="wallet")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="wallet", order_by="Transaction.created_at.desc()"
    )

    def __repr__(self) -> str:
        return f"<Wallet {self.id} balance={self.balance}>"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    wallet_id: Mapped[UUID] = mapped_column(ForeignKey("wallets.id"), index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference_id: Mapped[UUID | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()", index=True
    )

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction {self.type} {self.amount}>"
