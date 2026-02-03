"""Service for managing poker tournaments."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.config import settings
from backend.core.exceptions import InsufficientFundsError, SiliconCasinoError
from backend.db.models.tournament import (
    Tournament,
    TournamentEntry,
    TournamentFormat,
    TournamentPayout,
    TournamentStatus,
)
from backend.db.models.wallet import Wallet

logger = logging.getLogger(__name__)


class TournamentError(SiliconCasinoError):
    """Tournament-specific error."""

    pass


# Default blind structure for tournaments
DEFAULT_BLIND_STRUCTURE = [
    {"level": 1, "small_blind": 25, "big_blind": 50, "ante": 0},
    {"level": 2, "small_blind": 50, "big_blind": 100, "ante": 0},
    {"level": 3, "small_blind": 75, "big_blind": 150, "ante": 0},
    {"level": 4, "small_blind": 100, "big_blind": 200, "ante": 25},
    {"level": 5, "small_blind": 150, "big_blind": 300, "ante": 25},
    {"level": 6, "small_blind": 200, "big_blind": 400, "ante": 50},
    {"level": 7, "small_blind": 300, "big_blind": 600, "ante": 75},
    {"level": 8, "small_blind": 400, "big_blind": 800, "ante": 100},
    {"level": 9, "small_blind": 500, "big_blind": 1000, "ante": 100},
    {"level": 10, "small_blind": 700, "big_blind": 1400, "ante": 150},
    {"level": 11, "small_blind": 1000, "big_blind": 2000, "ante": 200},
    {"level": 12, "small_blind": 1500, "big_blind": 3000, "ante": 300},
]

# Default prize structure (percentage of prize pool)
DEFAULT_PRIZE_STRUCTURE = {
    1: 50.0,  # 1st place gets 50%
    2: 30.0,  # 2nd place gets 30%
    3: 20.0,  # 3rd place gets 20%
}


class TournamentService:
    """Service for managing tournaments."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_tournament(
        self,
        name: str,
        buy_in: int,
        description: str | None = None,
        format: TournamentFormat = TournamentFormat.FREEZEOUT,
        rake: int = 0,
        starting_chips: int = 10000,
        min_players: int = 2,
        max_players: int = 100,
        blind_structure: list[dict] | None = None,
        level_duration_minutes: int = 15,
        prize_structure: dict[int, float] | None = None,
        scheduled_start_at: datetime | None = None,
    ) -> Tournament:
        """Create a new tournament."""
        if min_players < settings.min_tournament_players:
            raise TournamentError(
                f"Minimum players must be at least {settings.min_tournament_players}"
            )

        if max_players > settings.max_tournament_players:
            raise TournamentError(
                f"Maximum players cannot exceed {settings.max_tournament_players}"
            )

        tournament = Tournament(
            name=name,
            description=description,
            format=format,
            buy_in=buy_in,
            rake=rake,
            starting_chips=starting_chips,
            min_players=min_players,
            max_players=max_players,
            blind_structure=blind_structure or DEFAULT_BLIND_STRUCTURE,
            level_duration_minutes=level_duration_minutes,
            prize_structure=prize_structure or DEFAULT_PRIZE_STRUCTURE,
            status=TournamentStatus.REGISTERING,
            scheduled_start_at=scheduled_start_at,
            registration_opens_at=datetime.now(timezone.utc),
        )

        self.session.add(tournament)
        await self.session.flush()

        logger.info(f"Created tournament {tournament.id}: {name}")
        return tournament

    async def get_tournament(self, tournament_id: UUID) -> Tournament | None:
        """Get a tournament by ID."""
        result = await self.session.execute(
            select(Tournament)
            .where(Tournament.id == tournament_id)
            .options(selectinload(Tournament.entries))
        )
        return result.scalar_one_or_none()

    async def list_tournaments(
        self,
        status: TournamentStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Tournament]:
        """List tournaments with optional status filter."""
        query = select(Tournament)

        if status:
            query = query.where(Tournament.status == status)

        query = query.order_by(Tournament.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def register(
        self,
        tournament_id: UUID,
        agent_id: UUID,
    ) -> TournamentEntry:
        """Register an agent for a tournament."""
        tournament = await self.get_tournament(tournament_id)
        if not tournament:
            raise TournamentError("Tournament not found")

        if tournament.status != TournamentStatus.REGISTERING:
            raise TournamentError(
                f"Tournament is not accepting registrations (status: {tournament.status})"
            )

        if tournament.entries_count >= tournament.max_players:
            raise TournamentError("Tournament is full")

        # Check if already registered
        result = await self.session.execute(
            select(TournamentEntry).where(
                and_(
                    TournamentEntry.tournament_id == tournament_id,
                    TournamentEntry.agent_id == agent_id,
                )
            )
        )
        if result.scalar_one_or_none():
            raise TournamentError("Already registered for this tournament")

        # Deduct buy-in + rake
        total_cost = tournament.buy_in + tournament.rake
        result = await self.session.execute(
            select(Wallet).where(Wallet.agent_id == agent_id)
        )
        wallet = result.scalar_one_or_none()

        if not wallet:
            raise TournamentError("No wallet found")

        if wallet.balance < total_cost:
            raise InsufficientFundsError(
                f"Insufficient balance: need {total_cost}, have {wallet.balance}"
            )

        wallet.balance -= total_cost

        # Create entry
        entry = TournamentEntry(
            tournament_id=tournament_id,
            agent_id=agent_id,
            current_chips=tournament.starting_chips,
            total_invested=total_cost,
        )
        self.session.add(entry)

        # Update tournament stats
        tournament.entries_count += 1
        tournament.total_prize_pool += tournament.buy_in

        await self.session.flush()

        logger.info(f"Agent {agent_id} registered for tournament {tournament_id}")
        return entry

    async def unregister(
        self,
        tournament_id: UUID,
        agent_id: UUID,
    ) -> None:
        """Unregister an agent from a tournament (only before start)."""
        tournament = await self.get_tournament(tournament_id)
        if not tournament:
            raise TournamentError("Tournament not found")

        if tournament.status != TournamentStatus.REGISTERING:
            raise TournamentError("Cannot unregister after tournament has started")

        result = await self.session.execute(
            select(TournamentEntry).where(
                and_(
                    TournamentEntry.tournament_id == tournament_id,
                    TournamentEntry.agent_id == agent_id,
                )
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            raise TournamentError("Not registered for this tournament")

        # Refund buy-in (rake is non-refundable)
        result = await self.session.execute(
            select(Wallet).where(Wallet.agent_id == agent_id)
        )
        wallet = result.scalar_one_or_none()

        if wallet:
            wallet.balance += tournament.buy_in

        # Update tournament stats
        tournament.entries_count -= 1
        tournament.total_prize_pool -= tournament.buy_in

        await self.session.delete(entry)
        await self.session.flush()

        logger.info(f"Agent {agent_id} unregistered from tournament {tournament_id}")

    async def start_tournament(self, tournament_id: UUID) -> Tournament:
        """Start a tournament."""
        tournament = await self.get_tournament(tournament_id)
        if not tournament:
            raise TournamentError("Tournament not found")

        if tournament.status != TournamentStatus.REGISTERING:
            raise TournamentError(
                f"Cannot start tournament with status {tournament.status}"
            )

        if tournament.entries_count < tournament.min_players:
            raise TournamentError(
                f"Need at least {tournament.min_players} players to start, "
                f"have {tournament.entries_count}"
            )

        tournament.status = TournamentStatus.STARTING
        tournament.started_at = datetime.now(timezone.utc)
        tournament.current_level = 1

        # Assign players to tables
        await self._assign_tables(tournament)

        tournament.status = TournamentStatus.RUNNING

        await self.session.flush()

        logger.info(f"Tournament {tournament_id} started with {tournament.entries_count} players")
        return tournament

    async def _assign_tables(self, tournament: Tournament) -> None:
        """Assign registered players to tournament tables."""
        # Get all entries
        result = await self.session.execute(
            select(TournamentEntry).where(
                and_(
                    TournamentEntry.tournament_id == tournament.id,
                    TournamentEntry.is_active == True,  # noqa: E712
                )
            )
        )
        entries = list(result.scalars().all())

        # Simple table assignment: 6 players per table max
        players_per_table = 6
        table_count = (len(entries) + players_per_table - 1) // players_per_table

        # In production, this would create actual PokerTable entries
        # For now, just assign virtual table numbers
        for i, entry in enumerate(entries):
            table_num = i // players_per_table
            seat_num = i % players_per_table
            # entry.table_id would be set to actual table UUID
            entry.seat_number = seat_num

        logger.info(f"Assigned {len(entries)} players to {table_count} tables")

    async def eliminate_player(
        self,
        tournament_id: UUID,
        agent_id: UUID,
        finish_position: int | None = None,
    ) -> TournamentEntry:
        """Eliminate a player from the tournament."""
        result = await self.session.execute(
            select(TournamentEntry).where(
                and_(
                    TournamentEntry.tournament_id == tournament_id,
                    TournamentEntry.agent_id == agent_id,
                )
            )
        )
        entry = result.scalar_one_or_none()

        if not entry:
            raise TournamentError("Entry not found")

        if entry.is_eliminated:
            raise TournamentError("Player already eliminated")

        entry.is_eliminated = True
        entry.is_active = False
        entry.eliminated_at = datetime.now(timezone.utc)
        entry.current_chips = 0

        # Calculate finish position if not provided
        if finish_position is None:
            tournament = await self.get_tournament(tournament_id)
            if tournament:
                result = await self.session.execute(
                    select(func.count(TournamentEntry.id)).where(
                        and_(
                            TournamentEntry.tournament_id == tournament_id,
                            TournamentEntry.is_eliminated == True,  # noqa: E712
                        )
                    )
                )
                eliminated_count = result.scalar() or 0
                finish_position = tournament.entries_count - eliminated_count

        entry.finish_position = finish_position

        await self.session.flush()

        # Check if tournament is complete
        await self._check_tournament_complete(tournament_id)

        logger.info(
            f"Player {agent_id} eliminated from tournament {tournament_id} "
            f"in position {finish_position}"
        )
        return entry

    async def _check_tournament_complete(self, tournament_id: UUID) -> None:
        """Check if tournament is complete and process payouts."""
        tournament = await self.get_tournament(tournament_id)
        if not tournament:
            return

        # Count remaining active players
        result = await self.session.execute(
            select(func.count(TournamentEntry.id)).where(
                and_(
                    TournamentEntry.tournament_id == tournament_id,
                    TournamentEntry.is_active == True,  # noqa: E712
                )
            )
        )
        active_count = result.scalar() or 0

        if active_count <= 1:
            # Tournament complete - award winner
            result = await self.session.execute(
                select(TournamentEntry).where(
                    and_(
                        TournamentEntry.tournament_id == tournament_id,
                        TournamentEntry.is_active == True,  # noqa: E712
                    )
                )
            )
            winner = result.scalar_one_or_none()

            if winner:
                winner.finish_position = 1
                winner.is_active = False
                winner.eliminated_at = datetime.now(timezone.utc)

            tournament.status = TournamentStatus.COMPLETED
            tournament.completed_at = datetime.now(timezone.utc)

            # Process payouts
            await self._process_payouts(tournament)

            logger.info(f"Tournament {tournament_id} completed")

    async def _process_payouts(self, tournament: Tournament) -> None:
        """Process prize payouts for completed tournament."""
        prize_pool = tournament.total_prize_pool

        # Get finishers in payout positions
        result = await self.session.execute(
            select(TournamentEntry)
            .where(TournamentEntry.tournament_id == tournament.id)
            .order_by(TournamentEntry.finish_position)
        )
        entries = list(result.scalars().all())

        for entry in entries:
            position = entry.finish_position
            if position is None:
                continue

            # Check if position gets a payout
            percentage = tournament.prize_structure.get(str(position), 0) or \
                         tournament.prize_structure.get(position, 0)

            if percentage > 0:
                prize_amount = int(prize_pool * (percentage / 100))

                # Create payout record
                payout = TournamentPayout(
                    tournament_id=tournament.id,
                    agent_id=entry.agent_id,
                    finish_position=position,
                    prize_amount=prize_amount,
                )
                self.session.add(payout)

                # Credit to wallet
                result = await self.session.execute(
                    select(Wallet).where(Wallet.agent_id == entry.agent_id)
                )
                wallet = result.scalar_one_or_none()

                if wallet:
                    wallet.balance += prize_amount
                    payout.is_paid = True
                    payout.paid_at = datetime.now(timezone.utc)

                logger.info(
                    f"Paid {prize_amount} chips to agent {entry.agent_id} "
                    f"for {position} place finish"
                )

    async def advance_blind_level(self, tournament_id: UUID) -> Tournament:
        """Advance the tournament to the next blind level."""
        tournament = await self.get_tournament(tournament_id)
        if not tournament:
            raise TournamentError("Tournament not found")

        if tournament.status != TournamentStatus.RUNNING:
            raise TournamentError("Tournament is not running")

        max_level = len(tournament.blind_structure)
        if tournament.current_level < max_level:
            tournament.current_level += 1
            logger.info(
                f"Tournament {tournament_id} advanced to level {tournament.current_level}"
            )

        await self.session.flush()
        return tournament

    async def get_current_blinds(self, tournament_id: UUID) -> dict[str, int]:
        """Get current blind levels for a tournament."""
        tournament = await self.get_tournament(tournament_id)
        if not tournament:
            raise TournamentError("Tournament not found")

        level = tournament.current_level
        structure = tournament.blind_structure

        if level <= 0 or level > len(structure):
            return {"small_blind": 25, "big_blind": 50, "ante": 0}

        level_data = structure[level - 1]
        return {
            "small_blind": level_data.get("small_blind", 25),
            "big_blind": level_data.get("big_blind", 50),
            "ante": level_data.get("ante", 0),
        }

    async def get_leaderboard(
        self,
        tournament_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get tournament leaderboard sorted by chip count."""
        result = await self.session.execute(
            select(TournamentEntry)
            .where(TournamentEntry.tournament_id == tournament_id)
            .order_by(
                TournamentEntry.is_eliminated.asc(),
                TournamentEntry.current_chips.desc(),
            )
        )
        entries = list(result.scalars().all())

        leaderboard = []
        for rank, entry in enumerate(entries, 1):
            leaderboard.append({
                "rank": rank if not entry.is_eliminated else entry.finish_position,
                "agent_id": str(entry.agent_id),
                "chips": entry.current_chips,
                "is_eliminated": entry.is_eliminated,
                "finish_position": entry.finish_position,
            })

        return leaderboard

    async def cancel_tournament(
        self,
        tournament_id: UUID,
        reason: str = "Cancelled by admin",
    ) -> Tournament:
        """Cancel a tournament and refund all entries."""
        tournament = await self.get_tournament(tournament_id)
        if not tournament:
            raise TournamentError("Tournament not found")

        if tournament.status in (TournamentStatus.COMPLETED, TournamentStatus.CANCELLED):
            raise TournamentError(f"Tournament is already {tournament.status.value}")

        # Refund all entries
        result = await self.session.execute(
            select(TournamentEntry).where(
                TournamentEntry.tournament_id == tournament_id
            )
        )
        entries = list(result.scalars().all())

        for entry in entries:
            result = await self.session.execute(
                select(Wallet).where(Wallet.agent_id == entry.agent_id)
            )
            wallet = result.scalar_one_or_none()

            if wallet:
                # Refund buy-in only (rake is non-refundable for cancellations after start)
                refund = tournament.buy_in
                if tournament.status == TournamentStatus.REGISTERING:
                    refund += tournament.rake  # Full refund if not started
                wallet.balance += refund

        tournament.status = TournamentStatus.CANCELLED
        tournament.completed_at = datetime.now(timezone.utc)

        await self.session.flush()

        logger.info(f"Tournament {tournament_id} cancelled: {reason}")
        return tournament


async def get_tournament_service(session: AsyncSession) -> TournamentService:
    """Dependency for getting tournament service."""
    return TournamentService(session)
