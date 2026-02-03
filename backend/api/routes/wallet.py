from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.core.security import get_current_agent
from backend.db.database import get_session
from backend.db.models.agent import Agent
from backend.services.wallet_service import WalletService

router = APIRouter()


class BalanceResponse(BaseModel):
    balance: int
    agent_id: UUID


class TransactionResponse(BaseModel):
    id: UUID
    type: str
    amount: int
    balance_after: int
    reference_id: UUID | None
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int


class CreditRequest(BaseModel):
    amount: int = Field(..., gt=0, le=1_000_000)


class CreditResponse(BaseModel):
    new_balance: int
    amount_credited: int
    transaction_id: UUID


@router.get("", response_model=BalanceResponse)
async def get_balance(
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> BalanceResponse:
    """Get current wallet balance."""
    service = WalletService(session)
    balance = await service.get_balance(agent.id)
    return BalanceResponse(balance=balance, agent_id=agent.id)


@router.get("/transactions", response_model=TransactionListResponse)
async def get_transactions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> TransactionListResponse:
    """Get transaction history."""
    service = WalletService(session)
    transactions = await service.get_transactions(agent.id, limit, offset)
    return TransactionListResponse(
        transactions=[TransactionResponse.model_validate(t) for t in transactions],
        total=len(transactions),
    )


@router.post("/credit", response_model=CreditResponse)
async def credit_chips(
    request: CreditRequest,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> CreditResponse:
    """Credit play chips to wallet (development only)."""
    if not settings.is_development:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Credit endpoint only available in development",
        )

    service = WalletService(session)
    transaction = await service.credit(agent.id, request.amount, "dev_credit")
    await session.commit()

    return CreditResponse(
        new_balance=transaction.balance_after,
        amount_credited=request.amount,
        transaction_id=transaction.id,
    )
