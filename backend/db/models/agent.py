from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base

if TYPE_CHECKING:
    from backend.db.models.wallet import Wallet


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    moltbook_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    wallet: Mapped["Wallet"] = relationship("Wallet", back_populates="agent", uselist=False)

    def __repr__(self) -> str:
        return f"<Agent {self.display_name} ({self.id})>"
