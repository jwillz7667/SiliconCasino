"""Referral system service for Silicon Casino.

Handles:
- Referral code generation
- Referral tracking
- Commission calculation and payment
"""

import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.core.metrics import record_referral_commission
from backend.db.models.referral import ReferralCode, Referral, ReferralCommission
from backend.db.models.wallet import Wallet
from backend.db.models.agent import Agent


@dataclass
class ReferralStats:
    """Statistics for an agent's referrals."""
    referral_code: str
    total_referrals: int
    total_commissions: int
    last_30_days_commissions: int
    referred_agents: list[dict]


class ReferralService:
    """Service for managing the referral program."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _generate_code(self) -> str:
        """Generate a unique referral code."""
        chars = string.ascii_uppercase + string.digits
        # Remove confusing characters
        chars = chars.replace("0", "").replace("O", "").replace("1", "").replace("I", "")
        return "SC" + "".join(secrets.choice(chars) for _ in range(6))

    async def get_or_create_code(self, agent_id: UUID) -> str:
        """Get or create a referral code for an agent."""
        # Check for existing code
        stmt = select(ReferralCode).where(ReferralCode.agent_id == agent_id)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            return existing.code

        # Generate a unique code
        for _ in range(10):  # Max attempts to avoid collisions
            code = self._generate_code()
            check_stmt = select(ReferralCode).where(ReferralCode.code == code)
            check_result = await self.session.execute(check_stmt)
            if not check_result.scalar_one_or_none():
                break
        else:
            # Fallback with timestamp
            code = f"SC{secrets.token_hex(4).upper()}"

        referral_code = ReferralCode(
            agent_id=agent_id,
            code=code,
        )
        self.session.add(referral_code)
        await self.session.commit()

        return code

    async def get_code_by_string(self, code: str) -> Optional[ReferralCode]:
        """Look up a referral code."""
        stmt = select(ReferralCode).where(
            func.upper(ReferralCode.code) == code.upper()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def apply_referral(self, referred_id: UUID, code: str) -> bool:
        """Apply a referral code to a new agent.

        Args:
            referred_id: The new agent being referred
            code: The referral code used

        Returns:
            True if referral was applied, False if invalid or already referred
        """
        # Check if agent is already referred
        existing_stmt = select(Referral).where(Referral.referred_id == referred_id)
        existing_result = await self.session.execute(existing_stmt)
        if existing_result.scalar_one_or_none():
            return False  # Already referred

        # Look up the code
        referral_code = await self.get_code_by_string(code)
        if not referral_code:
            return False  # Invalid code

        # Can't refer yourself
        if referral_code.agent_id == referred_id:
            return False

        # Create the referral
        referral = Referral(
            referrer_id=referral_code.agent_id,
            referred_id=referred_id,
            code_used=referral_code.code,
        )
        self.session.add(referral)

        # Increment code uses
        referral_code.uses += 1

        await self.session.commit()
        return True

    async def get_referrer(self, agent_id: UUID) -> Optional[UUID]:
        """Get the referrer for an agent, if any."""
        stmt = select(Referral).where(Referral.referred_id == agent_id)
        result = await self.session.execute(stmt)
        referral = result.scalar_one_or_none()
        return referral.referrer_id if referral else None

    async def process_rake_commission(
        self,
        agent_id: UUID,
        rake_amount: int,
        hand_id: Optional[UUID] = None,
        game_type: str = "poker",
    ) -> int:
        """Process referral commission on rake collection.

        Called when rake is collected from a pot. If the agent was referred,
        a commission is paid to the referrer.

        Args:
            agent_id: Agent who played (the referred agent)
            rake_amount: Total rake collected
            hand_id: Optional hand ID for tracking
            game_type: Type of game (poker, codegolf, etc.)

        Returns:
            Commission amount paid (0 if no referrer or not eligible)
        """
        # Get referrer
        referrer_id = await self.get_referrer(agent_id)
        if not referrer_id:
            return 0

        # Check minimum activity requirement
        if settings.referral_min_activity > 0:
            # Count agent's hands played
            from backend.db.models.game import GameEvent

            hands_stmt = select(func.count()).select_from(GameEvent).where(
                GameEvent.agent_id == agent_id
            )
            hands_result = await self.session.execute(hands_stmt)
            hands_played = hands_result.scalar() or 0

            if hands_played < settings.referral_min_activity:
                return 0

        # Calculate commission
        commission = int(rake_amount * settings.referral_commission_rate)
        if commission <= 0:
            return 0

        # Credit referrer's wallet
        wallet_stmt = select(Wallet).where(Wallet.agent_id == referrer_id)
        wallet_result = await self.session.execute(wallet_stmt)
        wallet = wallet_result.scalar_one_or_none()

        if wallet:
            wallet.balance += commission

            # Record commission
            commission_record = ReferralCommission(
                referrer_id=referrer_id,
                referred_id=agent_id,
                rake_amount=rake_amount,
                commission_amount=commission,
                hand_id=hand_id,
                game_type=game_type,
            )
            self.session.add(commission_record)

            await self.session.commit()

            # Record metric
            record_referral_commission(commission)

            return commission

        return 0

    async def get_stats(self, agent_id: UUID) -> ReferralStats:
        """Get referral statistics for an agent."""
        # Get or create referral code
        code = await self.get_or_create_code(agent_id)

        # Count total referrals
        referrals_stmt = select(func.count()).select_from(Referral).where(
            Referral.referrer_id == agent_id
        )
        referrals_result = await self.session.execute(referrals_stmt)
        total_referrals = referrals_result.scalar() or 0

        # Total commissions
        total_stmt = select(func.sum(ReferralCommission.commission_amount)).where(
            ReferralCommission.referrer_id == agent_id
        )
        total_result = await self.session.execute(total_stmt)
        total_commissions = total_result.scalar() or 0

        # Last 30 days commissions
        from datetime import timedelta
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        recent_stmt = select(func.sum(ReferralCommission.commission_amount)).where(
            and_(
                ReferralCommission.referrer_id == agent_id,
                ReferralCommission.created_at >= thirty_days_ago,
            )
        )
        recent_result = await self.session.execute(recent_stmt)
        recent_commissions = recent_result.scalar() or 0

        # Get referred agents with their stats
        referred_stmt = select(Referral).where(
            Referral.referrer_id == agent_id
        ).order_by(Referral.created_at.desc()).limit(20)
        referred_result = await self.session.execute(referred_stmt)
        referrals = referred_result.scalars().all()

        referred_agents = []
        for ref in referrals:
            # Get agent name
            agent = await self.session.get(Agent, ref.referred_id)

            # Get total commission from this referral
            comm_stmt = select(func.sum(ReferralCommission.commission_amount)).where(
                and_(
                    ReferralCommission.referrer_id == agent_id,
                    ReferralCommission.referred_id == ref.referred_id,
                )
            )
            comm_result = await self.session.execute(comm_stmt)
            agent_commission = comm_result.scalar() or 0

            referred_agents.append({
                "agent_id": str(ref.referred_id),
                "display_name": agent.display_name if agent else "Unknown",
                "referred_at": ref.created_at.isoformat(),
                "total_commission": agent_commission,
            })

        return ReferralStats(
            referral_code=code,
            total_referrals=total_referrals,
            total_commissions=total_commissions,
            last_30_days_commissions=recent_commissions,
            referred_agents=referred_agents,
        )

    async def get_commission_history(
        self,
        agent_id: UUID,
        limit: int = 50,
    ) -> list[dict]:
        """Get commission history for an agent."""
        stmt = select(ReferralCommission).where(
            ReferralCommission.referrer_id == agent_id
        ).order_by(ReferralCommission.created_at.desc()).limit(limit)

        result = await self.session.execute(stmt)
        commissions = result.scalars().all()

        history = []
        for comm in commissions:
            # Get referred agent name
            agent = await self.session.get(Agent, comm.referred_id)

            history.append({
                "id": str(comm.id),
                "referred_agent": {
                    "id": str(comm.referred_id),
                    "name": agent.display_name if agent else "Unknown",
                },
                "rake_amount": comm.rake_amount,
                "commission_amount": comm.commission_amount,
                "game_type": comm.game_type,
                "created_at": comm.created_at.isoformat(),
            })

        return history
