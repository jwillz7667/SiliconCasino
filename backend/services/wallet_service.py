from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import InsufficientFundsError
from backend.db.models.wallet import Transaction, Wallet


class WalletService:
    """Service for managing agent wallets and transactions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_wallet(self, agent_id: UUID) -> Wallet | None:
        """Get wallet for an agent."""
        result = await self.session.execute(
            select(Wallet).where(Wallet.agent_id == agent_id)
        )
        return result.scalar_one_or_none()

    async def get_balance(self, agent_id: UUID) -> int:
        """Get current balance for an agent."""
        wallet = await self.get_wallet(agent_id)
        return wallet.balance if wallet else 0

    async def credit(
        self,
        agent_id: UUID,
        amount: int,
        transaction_type: str = "credit",
        reference_id: UUID | None = None,
    ) -> Transaction:
        """Add chips to an agent's wallet."""
        if amount <= 0:
            raise ValueError("Amount must be positive")

        wallet = await self.get_wallet(agent_id)
        if not wallet:
            raise ValueError(f"No wallet found for agent {agent_id}")

        new_balance = wallet.balance + amount
        wallet.balance = new_balance

        transaction = Transaction(
            wallet_id=wallet.id,
            type=transaction_type,
            amount=amount,
            balance_after=new_balance,
            reference_id=reference_id,
        )
        self.session.add(transaction)
        await self.session.flush()

        return transaction

    async def debit(
        self,
        agent_id: UUID,
        amount: int,
        transaction_type: str = "debit",
        reference_id: UUID | None = None,
    ) -> Transaction:
        """Remove chips from an agent's wallet."""
        if amount <= 0:
            raise ValueError("Amount must be positive")

        wallet = await self.get_wallet(agent_id)
        if not wallet:
            raise ValueError(f"No wallet found for agent {agent_id}")

        if wallet.balance < amount:
            raise InsufficientFundsError(
                f"Insufficient funds: need {amount}, have {wallet.balance}"
            )

        new_balance = wallet.balance - amount
        wallet.balance = new_balance

        transaction = Transaction(
            wallet_id=wallet.id,
            type=transaction_type,
            amount=-amount,
            balance_after=new_balance,
            reference_id=reference_id,
        )
        self.session.add(transaction)
        await self.session.flush()

        return transaction

    async def transfer(
        self,
        from_agent_id: UUID,
        to_agent_id: UUID,
        amount: int,
        reference_id: UUID | None = None,
    ) -> tuple[Transaction, Transaction]:
        """Transfer chips between agents."""
        debit_tx = await self.debit(
            from_agent_id, amount, "transfer_out", reference_id
        )
        credit_tx = await self.credit(
            to_agent_id, amount, "transfer_in", reference_id
        )
        return debit_tx, credit_tx

    async def get_transactions(
        self,
        agent_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        """Get transaction history for an agent."""
        wallet = await self.get_wallet(agent_id)
        if not wallet:
            return []

        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.wallet_id == wallet.id)
            .order_by(Transaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())


async def get_wallet_service(session: AsyncSession) -> WalletService:
    """Dependency for getting wallet service."""
    return WalletService(session)
