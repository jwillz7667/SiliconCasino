"""Analytics and metrics aggregation service.

Provides aggregated statistics for dashboards and reporting.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.agent import Agent
from backend.db.models.game import PokerHand, GameEvent, PokerTable
from backend.db.models.wallet import Transaction, Wallet
from backend.db.models.tournament import Tournament, TournamentEntry
from backend.db.models.codegolf import CodeGolfChallenge, CodeGolfSubmission
from backend.db.models.referral import ReferralCommission
from backend.db.models.withdrawal import WithdrawalRequest


@dataclass
class PlatformStats:
    """Platform-wide statistics."""
    total_agents: int
    active_agents_24h: int
    active_agents_7d: int
    total_hands_played: int
    total_volume: int
    total_rake_collected: int
    total_referral_commissions: int
    active_tables: int
    active_tournaments: int
    active_challenges: int
    pending_withdrawals: int


@dataclass
class TimeSeriesPoint:
    """Single point in a time series."""
    timestamp: datetime
    value: int


@dataclass
class GameTypeStats:
    """Statistics broken down by game type."""
    poker_hands: int
    poker_volume: int
    poker_rake: int
    tournament_entries: int
    tournament_prize_pools: int
    codegolf_submissions: int
    codegolf_prize_pools: int


class AnalyticsService:
    """Service for aggregating analytics and metrics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_platform_stats(self) -> PlatformStats:
        """Get overall platform statistics."""
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        # Total agents
        total_agents_stmt = select(func.count()).select_from(Agent)
        total_agents = (await self.session.execute(total_agents_stmt)).scalar() or 0

        # Active agents (24h) - agents with game events in last 24h
        active_24h_stmt = select(func.count(distinct(GameEvent.agent_id))).where(
            GameEvent.created_at >= day_ago
        )
        active_24h = (await self.session.execute(active_24h_stmt)).scalar() or 0

        # Active agents (7d)
        active_7d_stmt = select(func.count(distinct(GameEvent.agent_id))).where(
            GameEvent.created_at >= week_ago
        )
        active_7d = (await self.session.execute(active_7d_stmt)).scalar() or 0

        # Total hands played
        hands_stmt = select(func.count()).select_from(PokerHand).where(
            PokerHand.status == "completed"
        )
        total_hands = (await self.session.execute(hands_stmt)).scalar() or 0

        # Total volume (sum of pot sizes)
        volume_stmt = select(func.sum(PokerHand.pot_size)).where(
            PokerHand.status == "completed"
        )
        total_volume = (await self.session.execute(volume_stmt)).scalar() or 0

        # Total rake collected
        rake_stmt = select(func.sum(PokerHand.rake_collected)).where(
            PokerHand.status == "completed"
        )
        total_rake = (await self.session.execute(rake_stmt)).scalar() or 0

        # Total referral commissions
        ref_stmt = select(func.sum(ReferralCommission.commission_amount))
        total_referral = (await self.session.execute(ref_stmt)).scalar() or 0

        # Active tables
        tables_stmt = select(func.count()).select_from(PokerTable).where(
            PokerTable.status == "active"
        )
        active_tables = (await self.session.execute(tables_stmt)).scalar() or 0

        # Active tournaments
        tourney_stmt = select(func.count()).select_from(Tournament).where(
            Tournament.status.in_(["registering", "running"])
        )
        active_tournaments = (await self.session.execute(tourney_stmt)).scalar() or 0

        # Active challenges
        challenge_stmt = select(func.count()).select_from(CodeGolfChallenge).where(
            and_(
                CodeGolfChallenge.status == "active",
                CodeGolfChallenge.ends_at > now,
            )
        )
        active_challenges = (await self.session.execute(challenge_stmt)).scalar() or 0

        # Pending withdrawals
        withdrawal_stmt = select(func.count()).select_from(WithdrawalRequest).where(
            WithdrawalRequest.status == "pending"
        )
        pending_withdrawals = (await self.session.execute(withdrawal_stmt)).scalar() or 0

        return PlatformStats(
            total_agents=total_agents,
            active_agents_24h=active_24h,
            active_agents_7d=active_7d,
            total_hands_played=total_hands,
            total_volume=total_volume,
            total_rake_collected=total_rake,
            total_referral_commissions=total_referral,
            active_tables=active_tables,
            active_tournaments=active_tournaments,
            active_challenges=active_challenges,
            pending_withdrawals=pending_withdrawals,
        )

    async def get_game_type_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> GameTypeStats:
        """Get statistics broken down by game type."""
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Poker stats
        poker_hands_stmt = select(func.count()).select_from(PokerHand).where(
            and_(
                PokerHand.status == "completed",
                PokerHand.completed_at >= start_date,
                PokerHand.completed_at <= end_date,
            )
        )
        poker_hands = (await self.session.execute(poker_hands_stmt)).scalar() or 0

        poker_volume_stmt = select(func.sum(PokerHand.pot_size)).where(
            and_(
                PokerHand.status == "completed",
                PokerHand.completed_at >= start_date,
                PokerHand.completed_at <= end_date,
            )
        )
        poker_volume = (await self.session.execute(poker_volume_stmt)).scalar() or 0

        poker_rake_stmt = select(func.sum(PokerHand.rake_collected)).where(
            and_(
                PokerHand.status == "completed",
                PokerHand.completed_at >= start_date,
                PokerHand.completed_at <= end_date,
            )
        )
        poker_rake = (await self.session.execute(poker_rake_stmt)).scalar() or 0

        # Tournament stats
        tourney_entries_stmt = select(func.count()).select_from(TournamentEntry).where(
            TournamentEntry.registered_at >= start_date
        )
        tourney_entries = (await self.session.execute(tourney_entries_stmt)).scalar() or 0

        tourney_pools_stmt = select(func.sum(Tournament.total_prize_pool)).where(
            and_(
                Tournament.status == "completed",
                Tournament.completed_at >= start_date,
                Tournament.completed_at <= end_date,
            )
        )
        tourney_pools = (await self.session.execute(tourney_pools_stmt)).scalar() or 0

        # Code Golf stats
        codegolf_subs_stmt = select(func.count()).select_from(CodeGolfSubmission).where(
            CodeGolfSubmission.submitted_at >= start_date
        )
        codegolf_subs = (await self.session.execute(codegolf_subs_stmt)).scalar() or 0

        codegolf_pools_stmt = select(func.sum(CodeGolfChallenge.prize_pool)).where(
            and_(
                CodeGolfChallenge.status == "completed",
                CodeGolfChallenge.ends_at >= start_date,
                CodeGolfChallenge.ends_at <= end_date,
            )
        )
        codegolf_pools = (await self.session.execute(codegolf_pools_stmt)).scalar() or 0

        return GameTypeStats(
            poker_hands=poker_hands,
            poker_volume=poker_volume,
            poker_rake=poker_rake,
            tournament_entries=tourney_entries,
            tournament_prize_pools=tourney_pools or 0,
            codegolf_submissions=codegolf_subs,
            codegolf_prize_pools=codegolf_pools or 0,
        )

    async def get_daily_hands(self, days: int = 30) -> list[TimeSeriesPoint]:
        """Get daily hand count for the past N days."""
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=days)

        # This would be more efficient with a proper time-series query
        # but for simplicity we'll do day-by-day counts
        points = []

        for i in range(days):
            day_start = start_date + timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            stmt = select(func.count()).select_from(PokerHand).where(
                and_(
                    PokerHand.status == "completed",
                    PokerHand.completed_at >= day_start,
                    PokerHand.completed_at < day_end,
                )
            )
            count = (await self.session.execute(stmt)).scalar() or 0

            points.append(TimeSeriesPoint(
                timestamp=day_start,
                value=count,
            ))

        return points

    async def get_daily_volume(self, days: int = 30) -> list[TimeSeriesPoint]:
        """Get daily volume (pot sizes) for the past N days."""
        now = datetime.now(timezone.utc)
        start_date = now - timedelta(days=days)

        points = []

        for i in range(days):
            day_start = start_date + timedelta(days=i)
            day_end = day_start + timedelta(days=1)

            stmt = select(func.sum(PokerHand.pot_size)).where(
                and_(
                    PokerHand.status == "completed",
                    PokerHand.completed_at >= day_start,
                    PokerHand.completed_at < day_end,
                )
            )
            volume = (await self.session.execute(stmt)).scalar() or 0

            points.append(TimeSeriesPoint(
                timestamp=day_start,
                value=volume,
            ))

        return points

    async def get_top_agents(self, limit: int = 10) -> list[dict]:
        """Get top agents by total winnings."""
        stmt = select(
            Wallet.agent_id,
            Wallet.balance,
            Agent.display_name,
        ).join(Agent, Agent.id == Wallet.agent_id).order_by(
            Wallet.balance.desc()
        ).limit(limit)

        result = await self.session.execute(stmt)
        rows = result.all()

        return [
            {
                "agent_id": str(row.agent_id),
                "display_name": row.display_name,
                "balance": row.balance,
            }
            for row in rows
        ]

    async def get_recent_big_hands(self, min_pot: int = 1000, limit: int = 10) -> list[dict]:
        """Get recent hands with large pots."""
        stmt = select(PokerHand).where(
            and_(
                PokerHand.status == "completed",
                PokerHand.pot_size >= min_pot,
            )
        ).order_by(PokerHand.completed_at.desc()).limit(limit)

        result = await self.session.execute(stmt)
        hands = result.scalars().all()

        return [
            {
                "id": str(hand.id),
                "table_id": str(hand.table_id),
                "pot_size": hand.pot_size,
                "rake_collected": hand.rake_collected,
                "completed_at": hand.completed_at.isoformat() if hand.completed_at else None,
            }
            for hand in hands
        ]
