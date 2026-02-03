"""API routes for withdrawal management."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import InsufficientFundsError
from backend.core.security import get_current_agent
from backend.db.database import get_session
from backend.db.models.agent import Agent
from backend.services.withdrawal_service import (
    WithdrawalError,
    WithdrawalService,
    get_withdrawal_service,
)

router = APIRouter()


class CreateWithdrawalRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount of chips to withdraw")
    destination_address: str = Field(..., min_length=42, max_length=42, description="Polygon wallet address")
    chain: str = Field(default="polygon", description="Blockchain network")
    token: str = Field(default="USDC", description="Token to receive")


class WithdrawalResponse(BaseModel):
    id: str
    agent_id: str
    amount: int
    destination_address: str
    chain: str
    token: str
    status: str
    reviewed_by: str | None
    reviewed_at: str | None
    rejection_reason: str | None
    tx_hash: str | None
    created_at: str


class ApproveRequest(BaseModel):
    reviewer: str = Field(..., description="Admin username/ID approving this request")


class RejectRequest(BaseModel):
    reviewer: str = Field(..., description="Admin username/ID rejecting this request")
    reason: str = Field(..., min_length=1, description="Reason for rejection")


@router.post("", response_model=WithdrawalResponse)
async def create_withdrawal(
    request: CreateWithdrawalRequest,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """
    Create a new withdrawal request.

    The chips will be reserved (deducted from balance) until the
    withdrawal is processed or rejected.
    """
    service = await get_withdrawal_service(session)

    try:
        withdrawal = await service.create_request(
            agent_id=agent.id,
            amount=request.amount,
            destination_address=request.destination_address,
            chain=request.chain,
            token=request.token,
        )
        await session.commit()
        return withdrawal.to_dict()

    except InsufficientFundsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except WithdrawalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("", response_model=list[WithdrawalResponse])
async def list_withdrawals(
    limit: int = 50,
    offset: int = 0,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Get withdrawal history for the authenticated agent."""
    service = await get_withdrawal_service(session)
    requests = await service.get_agent_requests(agent.id, limit, offset)
    return [r.to_dict() for r in requests]


@router.get("/{request_id}", response_model=WithdrawalResponse)
async def get_withdrawal(
    request_id: UUID,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get a specific withdrawal request."""
    service = await get_withdrawal_service(session)
    withdrawal = await service.get_request(request_id)

    if not withdrawal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Withdrawal request not found",
        )

    if withdrawal.agent_id != agent.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this withdrawal",
        )

    return withdrawal.to_dict()


# ==================== Admin Endpoints ====================
# These require separate admin authentication in production

@router.get("/admin/pending", response_model=list[WithdrawalResponse])
async def list_pending_withdrawals(
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """
    List all pending withdrawal requests (admin only).

    In production, this should require admin authentication.
    """
    service = await get_withdrawal_service(session)
    requests = await service.get_pending_requests()
    return [r.to_dict() for r in requests]


@router.post("/admin/{request_id}/approve", response_model=WithdrawalResponse)
async def approve_withdrawal(
    request_id: UUID,
    request: ApproveRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """
    Approve a pending withdrawal request (admin only).

    In production, this should require admin authentication.
    """
    service = await get_withdrawal_service(session)

    try:
        withdrawal = await service.approve_request(request_id, request.reviewer)
        await session.commit()
        return withdrawal.to_dict()
    except WithdrawalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/admin/{request_id}/reject", response_model=WithdrawalResponse)
async def reject_withdrawal(
    request_id: UUID,
    request: RejectRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """
    Reject a pending withdrawal request (admin only).

    The reserved chips will be refunded to the agent's wallet.
    In production, this should require admin authentication.
    """
    service = await get_withdrawal_service(session)

    try:
        withdrawal = await service.reject_request(
            request_id,
            request.reviewer,
            request.reason,
        )
        await session.commit()
        return withdrawal.to_dict()
    except WithdrawalError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/admin/stats")
async def get_withdrawal_stats(
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """
    Get withdrawal statistics (admin only).

    In production, this should require admin authentication.
    """
    service = await get_withdrawal_service(session)
    return await service.get_stats()
