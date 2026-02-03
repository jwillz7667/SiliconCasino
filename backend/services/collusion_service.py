"""
Anti-collusion detection service.

Detects potential collusion patterns between players:
- Same-human detection (multiple accounts)
- Coordinated betting patterns
- Chip dumping
- Win rate anomalies
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models.agent import Agent
from backend.db.models.game import GameEvent, PokerHand

logger = logging.getLogger(__name__)


class FlagSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FlagType(str, Enum):
    SAME_HUMAN = "same_human"
    WIN_RATE_ANOMALY = "win_rate_anomaly"
    CHIP_DUMPING = "chip_dumping"
    COORDINATED_BETTING = "coordinated_betting"
    TIMING_PATTERN = "timing_pattern"


@dataclass
class CollusionFlag:
    """A detected potential collusion indicator."""

    flag_type: FlagType
    severity: FlagSeverity
    agents_involved: list[UUID]
    description: str
    evidence: dict[str, Any]
    detected_at: datetime


@dataclass
class AgentStats:
    """Statistics for a single agent."""

    agent_id: UUID
    total_hands: int
    hands_won: int
    win_rate: float
    total_profit: int
    vpip: float  # Voluntarily put in pot percentage
    pfr: float  # Pre-flop raise percentage
    aggression_factor: float
    opponents_played: dict[UUID, int]  # agent_id -> hands played together


class CollusionService:
    """Service for detecting potential collusion between players."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def analyze_agent(self, agent_id: UUID) -> list[CollusionFlag]:
        """
        Run full collusion analysis for an agent.

        Returns a list of detected flags.
        """
        if not settings.collusion_detection_enabled:
            return []

        flags: list[CollusionFlag] = []

        # Get agent stats
        stats = await self.get_agent_stats(agent_id)

        if stats.total_hands < settings.min_hands_for_analysis:
            logger.info(
                f"Agent {agent_id} has {stats.total_hands} hands, "
                f"need {settings.min_hands_for_analysis} for analysis"
            )
            return flags

        # Check win rate anomaly
        if win_flag := await self._check_win_rate_anomaly(agent_id, stats):
            flags.append(win_flag)

        # Check chip dumping patterns
        if dump_flags := await self._check_chip_dumping(agent_id):
            flags.extend(dump_flags)

        # Check coordinated betting
        if coord_flags := await self._check_coordinated_betting(agent_id):
            flags.extend(coord_flags)

        return flags

    async def get_agent_stats(self, agent_id: UUID) -> AgentStats:
        """Calculate statistics for an agent."""
        # Get hand participation data
        result = await self.session.execute(
            text("""
                SELECT
                    COUNT(DISTINCT ge.hand_id) as total_hands,
                    COUNT(DISTINCT CASE
                        WHEN ge.event_type = 'hand_complete'
                        AND ge.payload->>'winner_seat' IS NOT NULL
                        THEN ge.hand_id
                    END) as hands_won,
                    SUM(CASE
                        WHEN ge.event_type = 'player_action'
                        AND ge.payload->>'action_type' IN ('bet', 'raise', 'call')
                        THEN 1 ELSE 0
                    END) as voluntary_actions,
                    SUM(CASE
                        WHEN ge.event_type = 'player_action'
                        AND ge.payload->>'action_type' IN ('bet', 'raise')
                        THEN 1 ELSE 0
                    END) as aggressive_actions,
                    SUM(CASE
                        WHEN ge.event_type = 'player_action'
                        AND ge.payload->>'action_type' IN ('call', 'check')
                        THEN 1 ELSE 0
                    END) as passive_actions
                FROM game_events ge
                WHERE ge.agent_id = :agent_id
            """),
            {"agent_id": str(agent_id)},
        )
        row = result.fetchone()

        total_hands = row.total_hands if row else 0
        hands_won = row.hands_won if row else 0
        voluntary_actions = row.voluntary_actions if row else 0
        aggressive_actions = row.aggressive_actions if row else 0
        passive_actions = row.passive_actions if row else 0

        win_rate = hands_won / total_hands if total_hands > 0 else 0
        vpip = voluntary_actions / total_hands if total_hands > 0 else 0
        pfr = aggressive_actions / total_hands if total_hands > 0 else 0

        # Aggression factor: (bets + raises) / (calls + checks)
        passive = passive_actions or 1
        aggression = aggressive_actions / passive

        # Get opponents played
        opponents: dict[UUID, int] = defaultdict(int)
        # (This would query shared hands - simplified for now)

        return AgentStats(
            agent_id=agent_id,
            total_hands=total_hands,
            hands_won=hands_won,
            win_rate=win_rate,
            total_profit=0,  # Would calculate from transactions
            vpip=vpip,
            pfr=pfr,
            aggression_factor=aggression,
            opponents_played=opponents,
        )

    async def _check_win_rate_anomaly(
        self,
        agent_id: UUID,
        stats: AgentStats,
    ) -> CollusionFlag | None:
        """Check for suspiciously high win rates."""
        if stats.win_rate < settings.suspicious_win_rate_threshold:
            return None

        # Calculate expected win rate based on table size
        # For a 6-max table, expected is ~16.7%
        expected_win_rate = 1 / 6

        if stats.win_rate > expected_win_rate * 3:  # 3x expected is very suspicious
            severity = FlagSeverity.HIGH
        elif stats.win_rate > expected_win_rate * 2:
            severity = FlagSeverity.MEDIUM
        else:
            severity = FlagSeverity.LOW

        return CollusionFlag(
            flag_type=FlagType.WIN_RATE_ANOMALY,
            severity=severity,
            agents_involved=[agent_id],
            description=f"Agent has {stats.win_rate:.1%} win rate over {stats.total_hands} hands",
            evidence={
                "win_rate": stats.win_rate,
                "expected_rate": expected_win_rate,
                "hands_played": stats.total_hands,
                "hands_won": stats.hands_won,
            },
            detected_at=datetime.now(timezone.utc),
        )

    async def _check_chip_dumping(self, agent_id: UUID) -> list[CollusionFlag]:
        """
        Detect chip dumping patterns.

        Chip dumping: consistently losing big pots to specific opponents
        in suspicious ways (e.g., calling big bets with weak hands).
        """
        flags: list[CollusionFlag] = []

        # Query for large losses to specific opponents
        result = await self.session.execute(
            text("""
                WITH agent_losses AS (
                    SELECT
                        ge.hand_id,
                        ph.total_pot,
                        ge.payload->>'amount' as bet_amount
                    FROM game_events ge
                    JOIN poker_hands ph ON ge.hand_id = ph.id
                    WHERE ge.agent_id = :agent_id
                    AND ge.event_type = 'player_action'
                    AND ge.payload->>'action_type' IN ('call', 'raise')
                    AND ph.total_pot > 1000
                )
                SELECT
                    hand_id,
                    total_pot,
                    bet_amount
                FROM agent_losses
                ORDER BY total_pot DESC
                LIMIT 10
            """),
            {"agent_id": str(agent_id)},
        )

        large_losses = result.fetchall()

        # Analyze patterns (simplified)
        if len(large_losses) >= 5:
            total_lost = sum(row.total_pot for row in large_losses)
            if total_lost > 10000:  # Threshold for suspicion
                flags.append(
                    CollusionFlag(
                        flag_type=FlagType.CHIP_DUMPING,
                        severity=FlagSeverity.MEDIUM,
                        agents_involved=[agent_id],
                        description=f"Agent has lost {total_lost} chips in {len(large_losses)} large pots",
                        evidence={
                            "total_lost": total_lost,
                            "large_pots_count": len(large_losses),
                        },
                        detected_at=datetime.now(timezone.utc),
                    )
                )

        return flags

    async def _check_coordinated_betting(self, agent_id: UUID) -> list[CollusionFlag]:
        """
        Detect coordinated betting patterns between players.

        Signs include:
        - Never raising each other
        - Always folding to each other's bets
        - Suspicious timing patterns
        """
        flags: list[CollusionFlag] = []

        # This would analyze betting patterns between pairs of players
        # Simplified implementation for now

        return flags

    async def check_same_human(
        self,
        agent_id_1: UUID,
        agent_id_2: UUID,
    ) -> CollusionFlag | None:
        """
        Check if two agents might be controlled by the same human.

        Factors to consider:
        - Moltbook ID overlap
        - IP address patterns
        - Timing patterns (never online simultaneously)
        - Playing style similarities
        """
        # Get agents
        result = await self.session.execute(
            select(Agent).where(Agent.id.in_([agent_id_1, agent_id_2]))
        )
        agents = {a.id: a for a in result.scalars().all()}

        if len(agents) != 2:
            return None

        agent1 = agents[agent_id_1]
        agent2 = agents[agent_id_2]

        # Check Moltbook ID (if both have one and they're different, likely different humans)
        if agent1.moltbook_id and agent2.moltbook_id:
            if agent1.moltbook_id == agent2.moltbook_id:
                return CollusionFlag(
                    flag_type=FlagType.SAME_HUMAN,
                    severity=FlagSeverity.CRITICAL,
                    agents_involved=[agent_id_1, agent_id_2],
                    description="Both agents linked to same Moltbook account",
                    evidence={
                        "moltbook_id": agent1.moltbook_id,
                    },
                    detected_at=datetime.now(timezone.utc),
                )

        # Additional checks would go here:
        # - API key creation timestamps
        # - Request IP addresses
        # - Playing time overlap analysis

        return None

    async def get_flagged_agents(
        self,
        min_severity: FlagSeverity = FlagSeverity.MEDIUM,
    ) -> list[dict[str, Any]]:
        """Get all agents with collusion flags above a severity threshold."""
        # In production, this would query from a collusion_flags table
        # For now, return empty list
        return []

    async def adjust_trust_level(
        self,
        agent_id: UUID,
        adjustment: float,
        reason: str,
    ) -> None:
        """Adjust an agent's trust level based on collusion analysis."""
        result = await self.session.execute(
            select(Agent).where(Agent.id == agent_id)
        )
        agent = result.scalar_one_or_none()

        if agent:
            new_level = max(0.0, min(1.0, agent.trust_level + adjustment))
            agent.trust_level = new_level
            logger.info(
                f"Adjusted trust level for agent {agent_id}: "
                f"{agent.trust_level - adjustment:.2f} -> {new_level:.2f} ({reason})"
            )


async def get_collusion_service(session: AsyncSession) -> CollusionService:
    """Dependency for getting collusion service."""
    return CollusionService(session)
