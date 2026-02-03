from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.game import GameEvent, PokerHand


class EventStore:
    """Service for storing and retrieving game events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def store_event(
        self,
        hand_id: UUID,
        sequence_num: int,
        event_type: str,
        agent_id: UUID | None,
        payload: dict[str, Any],
    ) -> GameEvent:
        """Store a game event."""
        event = GameEvent(
            hand_id=hand_id,
            sequence_num=sequence_num,
            event_type=event_type,
            agent_id=agent_id,
            payload=payload,
        )
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_hand_events(
        self,
        hand_id: UUID,
        from_sequence: int = 0,
    ) -> list[GameEvent]:
        """Get events for a hand, optionally from a specific sequence."""
        result = await self.session.execute(
            select(GameEvent)
            .where(GameEvent.hand_id == hand_id)
            .where(GameEvent.sequence_num >= from_sequence)
            .order_by(GameEvent.sequence_num)
        )
        return list(result.scalars().all())

    async def get_table_hands(
        self,
        table_id: UUID,
        limit: int = 10,
    ) -> list[PokerHand]:
        """Get recent hands for a table."""
        result = await self.session.execute(
            select(PokerHand)
            .where(PokerHand.table_id == table_id)
            .order_by(PokerHand.hand_number.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
