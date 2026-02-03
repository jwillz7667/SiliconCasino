"""Withdrawal request models for human approval workflow."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum as SQLEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base


class WithdrawalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class WithdrawalRequest(Base):
    """Withdrawal request requiring human approval."""

    __tablename__ = "withdrawal_requests"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    destination_address: Mapped[str] = mapped_column(String(255), nullable=False)
    chain: Mapped[str] = mapped_column(String(50), default="polygon")
    token: Mapped[str] = mapped_column(String(20), default="USDC")

    status: Mapped[WithdrawalStatus] = mapped_column(
        SQLEnum(WithdrawalStatus), default=WithdrawalStatus.PENDING, nullable=False
    )

    # Review information
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Transaction tracking
    tx_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tx_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    agent = relationship("Agent", back_populates="withdrawal_requests")

    def __repr__(self) -> str:
        return f"<WithdrawalRequest {self.id} agent={self.agent_id} amount={self.amount} status={self.status}>"

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "agent_id": str(self.agent_id),
            "amount": self.amount,
            "destination_address": self.destination_address,
            "chain": self.chain,
            "token": self.token,
            "status": self.status.value,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "rejection_reason": self.rejection_reason,
            "tx_hash": self.tx_hash,
            "tx_confirmed_at": self.tx_confirmed_at.isoformat() if self.tx_confirmed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DepositAddress(Base):
    """Generated deposit addresses for agents."""

    __tablename__ = "deposit_addresses"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, unique=True
    )
    address: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    chain: Mapped[str] = mapped_column(String(50), default="polygon")
    derivation_index: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    agent = relationship("Agent", back_populates="deposit_address")

    def __repr__(self) -> str:
        return f"<DepositAddress {self.address} agent={self.agent_id}>"


class CryptoDeposit(Base):
    """Tracked crypto deposits."""

    __tablename__ = "crypto_deposits"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("agents.id"), nullable=False, index=True
    )
    tx_hash: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    from_address: Mapped[str] = mapped_column(String(255), nullable=False)
    to_address: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # In smallest unit (wei/satoshi)
    token: Mapped[str] = mapped_column(String(20), default="USDC")
    chain: Mapped[str] = mapped_column(String(50), default="polygon")

    block_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    confirmations: Mapped[int] = mapped_column(BigInteger, default=0)
    is_credited: Mapped[bool] = mapped_column(default=False)
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    agent = relationship("Agent", back_populates="crypto_deposits")

    def __repr__(self) -> str:
        return f"<CryptoDeposit {self.tx_hash[:16]}... amount={self.amount}>"
