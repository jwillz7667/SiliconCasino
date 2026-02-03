"""
Service for cryptocurrency operations on Polygon network.

This service handles:
- Deposit address generation
- Deposit monitoring
- Withdrawal processing to blockchain
- USDC token interactions
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models.wallet import Wallet
from backend.db.models.withdrawal import CryptoDeposit, DepositAddress, WithdrawalRequest, WithdrawalStatus

logger = logging.getLogger(__name__)

# USDC has 6 decimals
USDC_DECIMALS = 6
CHIPS_PER_USDC = 100  # 1 USDC = 100 chips


class CryptoService:
    """
    Service for handling cryptocurrency operations.

    In production, this would integrate with Web3.py or similar
    for actual blockchain interactions.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self._deposit_index_counter = 0

    async def get_or_create_deposit_address(self, agent_id: UUID) -> DepositAddress:
        """
        Get or generate a unique deposit address for an agent.

        In production, this would derive addresses from an HD wallet
        for secure deposit tracking.
        """
        result = await self.session.execute(
            select(DepositAddress).where(DepositAddress.agent_id == agent_id)
        )
        existing = result.scalar_one_or_none()

        if existing:
            return existing

        # In production, this would use HD wallet derivation
        # For development, generate a placeholder address
        self._deposit_index_counter += 1
        derivation_index = self._deposit_index_counter

        # Placeholder address format (in production, use real derivation)
        address = f"0x{agent_id.hex[:40]}"

        deposit_addr = DepositAddress(
            agent_id=agent_id,
            address=address,
            chain="polygon",
            derivation_index=derivation_index,
        )
        self.session.add(deposit_addr)
        await self.session.flush()

        return deposit_addr

    async def process_deposit(
        self,
        tx_hash: str,
        from_address: str,
        to_address: str,
        amount_wei: int,
        block_number: int,
    ) -> CryptoDeposit | None:
        """
        Process an incoming deposit transaction.

        Returns the CryptoDeposit record if successful, None if already processed.
        """
        # Check if already processed
        result = await self.session.execute(
            select(CryptoDeposit).where(CryptoDeposit.tx_hash == tx_hash)
        )
        if result.scalar_one_or_none():
            logger.info(f"Deposit {tx_hash} already processed")
            return None

        # Find the agent by deposit address
        result = await self.session.execute(
            select(DepositAddress).where(DepositAddress.address == to_address)
        )
        deposit_addr = result.scalar_one_or_none()

        if not deposit_addr:
            logger.warning(f"Unknown deposit address: {to_address}")
            return None

        # Create deposit record
        deposit = CryptoDeposit(
            agent_id=deposit_addr.agent_id,
            tx_hash=tx_hash,
            from_address=from_address,
            to_address=to_address,
            amount=amount_wei,
            token="USDC",
            chain="polygon",
            block_number=block_number,
            confirmations=0,
            is_credited=False,
        )
        self.session.add(deposit)
        await self.session.flush()

        logger.info(f"Deposit recorded: {tx_hash} for agent {deposit_addr.agent_id}")
        return deposit

    async def update_deposit_confirmations(
        self,
        tx_hash: str,
        confirmations: int,
    ) -> CryptoDeposit | None:
        """
        Update confirmation count for a deposit.

        If confirmations reach threshold, credit the agent's wallet.
        """
        result = await self.session.execute(
            select(CryptoDeposit).where(CryptoDeposit.tx_hash == tx_hash)
        )
        deposit = result.scalar_one_or_none()

        if not deposit:
            return None

        deposit.confirmations = confirmations

        # Credit wallet if confirmed and not already credited
        if confirmations >= settings.deposit_confirmations and not deposit.is_credited:
            await self._credit_deposit(deposit)

        await self.session.flush()
        return deposit

    async def _credit_deposit(self, deposit: CryptoDeposit) -> None:
        """Credit a confirmed deposit to the agent's wallet."""
        # Convert USDC amount to chips
        # USDC has 6 decimals, so 1 USDC = 1_000_000 wei
        usdc_amount = deposit.amount / (10 ** USDC_DECIMALS)
        chips_amount = int(usdc_amount * CHIPS_PER_USDC)

        if chips_amount <= 0:
            logger.warning(f"Deposit {deposit.tx_hash} amount too small to credit")
            return

        # Get or create wallet
        result = await self.session.execute(
            select(Wallet).where(Wallet.agent_id == deposit.agent_id)
        )
        wallet = result.scalar_one_or_none()

        if not wallet:
            logger.error(f"No wallet found for agent {deposit.agent_id}")
            return

        wallet.balance += chips_amount
        deposit.is_credited = True
        deposit.credited_at = datetime.now(timezone.utc)

        logger.info(
            f"Credited {chips_amount} chips to agent {deposit.agent_id} "
            f"from deposit {deposit.tx_hash}"
        )

    async def process_withdrawal(
        self,
        request: WithdrawalRequest,
    ) -> str | None:
        """
        Process an approved withdrawal by sending crypto on-chain.

        Returns the transaction hash if successful, None otherwise.

        In production, this would:
        1. Build the USDC transfer transaction
        2. Sign with hot wallet
        3. Submit to Polygon network
        4. Return the tx hash
        """
        if request.status != WithdrawalStatus.APPROVED:
            logger.error(f"Cannot process withdrawal {request.id}: status is {request.status}")
            return None

        # Convert chips to USDC amount
        usdc_amount = request.amount / CHIPS_PER_USDC
        usdc_wei = int(usdc_amount * (10 ** USDC_DECIMALS))

        # In production, this would be actual blockchain transaction
        # For development, simulate a successful transaction
        if settings.is_development:
            # Simulate transaction hash
            tx_hash = f"0x{'0' * 64}"
            logger.info(
                f"[DEV] Simulated withdrawal: {request.amount} chips "
                f"({usdc_amount} USDC) to {request.destination_address}"
            )
            return tx_hash

        # Production implementation would go here:
        # from web3 import Web3
        # w3 = Web3(Web3.HTTPProvider(settings.polygon_rpc_url))
        # usdc_contract = w3.eth.contract(
        #     address=settings.usdc_contract_address,
        #     abi=USDC_ABI
        # )
        # tx = usdc_contract.functions.transfer(
        #     request.destination_address,
        #     usdc_wei
        # ).build_transaction({...})
        # signed = w3.eth.account.sign_transaction(tx, settings.hot_wallet_private_key)
        # tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
        # return tx_hash.hex()

        logger.warning("Production crypto transfers not yet implemented")
        return None

    async def get_pending_deposits(self) -> list[CryptoDeposit]:
        """Get all deposits awaiting confirmation."""
        result = await self.session.execute(
            select(CryptoDeposit).where(CryptoDeposit.is_credited == False)  # noqa: E712
        )
        return list(result.scalars().all())

    async def get_agent_deposits(
        self,
        agent_id: UUID,
        limit: int = 50,
    ) -> list[CryptoDeposit]:
        """Get deposit history for an agent."""
        result = await self.session.execute(
            select(CryptoDeposit)
            .where(CryptoDeposit.agent_id == agent_id)
            .order_by(CryptoDeposit.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class DepositMonitor:
    """
    Background service to monitor for incoming deposits.

    In production, this would:
    - Connect to Polygon node via WebSocket
    - Subscribe to USDC Transfer events
    - Filter for transfers to known deposit addresses
    - Call CryptoService to process deposits
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the deposit monitoring loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Deposit monitor started")

    async def stop(self) -> None:
        """Stop the deposit monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Deposit monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_deposits()
            except Exception as e:
                logger.exception(f"Error in deposit monitor: {e}")

            # Poll interval (in production, use WebSocket events instead)
            await asyncio.sleep(30)

    async def _check_deposits(self) -> None:
        """
        Check for new deposits and confirmations.

        In production, this would query the blockchain for:
        1. New Transfer events to deposit addresses
        2. Updated confirmation counts for pending deposits
        """
        async with self.session_factory() as session:
            service = CryptoService(session)

            # Update confirmations for pending deposits
            pending = await service.get_pending_deposits()
            for deposit in pending:
                # In production, get actual confirmation count from blockchain
                # For now, simulate confirmations
                if settings.is_development:
                    new_confirmations = min(
                        deposit.confirmations + 3,
                        settings.deposit_confirmations + 1,
                    )
                    await service.update_deposit_confirmations(
                        deposit.tx_hash,
                        new_confirmations,
                    )

            await session.commit()


async def get_crypto_service(session: AsyncSession) -> CryptoService:
    """Dependency for getting crypto service."""
    return CryptoService(session)
