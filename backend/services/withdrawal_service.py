"""Service for managing withdrawal requests with human approval."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.core.exceptions import InsufficientFundsError, SiliconCasinoError
from backend.db.models.wallet import Wallet
from backend.db.models.withdrawal import WithdrawalRequest, WithdrawalStatus


class WithdrawalError(SiliconCasinoError):
    """Withdrawal-specific error."""

    pass


class WithdrawalService:
    """Service for handling withdrawal requests."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_request(
        self,
        agent_id: UUID,
        amount: int,
        destination_address: str,
        chain: str = "polygon",
        token: str = "USDC",
    ) -> WithdrawalRequest:
        """
        Create a new withdrawal request.

        This reserves the funds and puts the request in pending state
        for human approval.
        """
        if amount < settings.min_withdrawal:
            raise WithdrawalError(
                f"Minimum withdrawal is {settings.min_withdrawal} chips"
            )

        # Check for pending withdrawals
        pending = await self.get_pending_requests(agent_id)
        if pending:
            raise WithdrawalError(
                "You already have a pending withdrawal request. "
                "Please wait for it to be processed."
            )

        # Check balance
        result = await self.session.execute(
            select(Wallet).where(Wallet.agent_id == agent_id)
        )
        wallet = result.scalar_one_or_none()

        if not wallet:
            raise WithdrawalError("No wallet found")

        if wallet.balance < amount:
            raise InsufficientFundsError(
                f"Insufficient balance: have {wallet.balance}, need {amount}"
            )

        # Reserve the funds by deducting from balance
        wallet.balance -= amount

        # Create the request
        request = WithdrawalRequest(
            agent_id=agent_id,
            amount=amount,
            destination_address=destination_address,
            chain=chain,
            token=token,
            status=WithdrawalStatus.PENDING,
        )
        self.session.add(request)
        await self.session.flush()

        return request

    async def get_request(self, request_id: UUID) -> WithdrawalRequest | None:
        """Get a withdrawal request by ID."""
        result = await self.session.execute(
            select(WithdrawalRequest).where(WithdrawalRequest.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_requests(self, agent_id: UUID | None = None) -> list[WithdrawalRequest]:
        """Get all pending withdrawal requests, optionally filtered by agent."""
        query = select(WithdrawalRequest).where(
            WithdrawalRequest.status == WithdrawalStatus.PENDING
        )
        if agent_id:
            query = query.where(WithdrawalRequest.agent_id == agent_id)

        result = await self.session.execute(query.order_by(WithdrawalRequest.created_at))
        return list(result.scalars().all())

    async def get_agent_requests(
        self,
        agent_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[WithdrawalRequest]:
        """Get withdrawal history for an agent."""
        result = await self.session.execute(
            select(WithdrawalRequest)
            .where(WithdrawalRequest.agent_id == agent_id)
            .order_by(WithdrawalRequest.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def approve_request(
        self,
        request_id: UUID,
        reviewer: str,
    ) -> WithdrawalRequest:
        """
        Approve a withdrawal request (admin action).

        This marks the request as approved for processing.
        """
        request = await self.get_request(request_id)
        if not request:
            raise WithdrawalError("Withdrawal request not found")

        if request.status != WithdrawalStatus.PENDING:
            raise WithdrawalError(
                f"Cannot approve request with status {request.status}"
            )

        request.status = WithdrawalStatus.APPROVED
        request.reviewed_by = reviewer
        request.reviewed_at = datetime.now(timezone.utc)

        await self.session.flush()
        return request

    async def reject_request(
        self,
        request_id: UUID,
        reviewer: str,
        reason: str,
    ) -> WithdrawalRequest:
        """
        Reject a withdrawal request (admin action).

        This refunds the reserved chips back to the agent's wallet.
        """
        request = await self.get_request(request_id)
        if not request:
            raise WithdrawalError("Withdrawal request not found")

        if request.status != WithdrawalStatus.PENDING:
            raise WithdrawalError(
                f"Cannot reject request with status {request.status}"
            )

        # Refund the chips
        result = await self.session.execute(
            select(Wallet).where(Wallet.agent_id == request.agent_id)
        )
        wallet = result.scalar_one_or_none()
        if wallet:
            wallet.balance += request.amount

        request.status = WithdrawalStatus.REJECTED
        request.reviewed_by = reviewer
        request.reviewed_at = datetime.now(timezone.utc)
        request.rejection_reason = reason

        await self.session.flush()
        return request

    async def mark_processing(self, request_id: UUID) -> WithdrawalRequest:
        """Mark a request as currently being processed on-chain."""
        request = await self.get_request(request_id)
        if not request:
            raise WithdrawalError("Withdrawal request not found")

        if request.status != WithdrawalStatus.APPROVED:
            raise WithdrawalError(
                f"Cannot process request with status {request.status}"
            )

        request.status = WithdrawalStatus.PROCESSING
        await self.session.flush()
        return request

    async def complete_request(
        self,
        request_id: UUID,
        tx_hash: str,
    ) -> WithdrawalRequest:
        """Mark a withdrawal as completed with the transaction hash."""
        request = await self.get_request(request_id)
        if not request:
            raise WithdrawalError("Withdrawal request not found")

        if request.status != WithdrawalStatus.PROCESSING:
            raise WithdrawalError(
                f"Cannot complete request with status {request.status}"
            )

        request.status = WithdrawalStatus.COMPLETED
        request.tx_hash = tx_hash
        request.tx_confirmed_at = datetime.now(timezone.utc)

        await self.session.flush()
        return request

    async def fail_request(
        self,
        request_id: UUID,
        reason: str,
    ) -> WithdrawalRequest:
        """
        Mark a withdrawal as failed.

        This refunds the chips back to the agent's wallet.
        """
        request = await self.get_request(request_id)
        if not request:
            raise WithdrawalError("Withdrawal request not found")

        if request.status not in (WithdrawalStatus.APPROVED, WithdrawalStatus.PROCESSING):
            raise WithdrawalError(
                f"Cannot fail request with status {request.status}"
            )

        # Refund the chips
        result = await self.session.execute(
            select(Wallet).where(Wallet.agent_id == request.agent_id)
        )
        wallet = result.scalar_one_or_none()
        if wallet:
            wallet.balance += request.amount

        request.status = WithdrawalStatus.FAILED
        request.rejection_reason = reason

        await self.session.flush()
        return request

    async def get_stats(self) -> dict:
        """Get withdrawal statistics."""
        result = await self.session.execute(
            select(
                WithdrawalRequest.status,
                func.count(WithdrawalRequest.id).label("count"),
                func.sum(WithdrawalRequest.amount).label("total_amount"),
            ).group_by(WithdrawalRequest.status)
        )

        stats = {
            "pending": {"count": 0, "amount": 0},
            "approved": {"count": 0, "amount": 0},
            "processing": {"count": 0, "amount": 0},
            "completed": {"count": 0, "amount": 0},
            "rejected": {"count": 0, "amount": 0},
            "failed": {"count": 0, "amount": 0},
        }

        for status, count, total in result.all():
            stats[status.value] = {
                "count": count or 0,
                "amount": total or 0,
            }

        return stats


async def get_withdrawal_service(session: AsyncSession) -> WithdrawalService:
    """Dependency for getting withdrawal service."""
    return WithdrawalService(session)
