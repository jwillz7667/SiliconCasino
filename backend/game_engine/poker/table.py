from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from backend.game_engine.poker.deck import Card


@dataclass
class SeatState:
    """State of a single seat at the table."""

    seat_number: int
    agent_id: UUID | None = None
    stack: int = 0
    status: str = "empty"
    hole_cards: list[Card] = field(default_factory=list)
    is_sitting_out: bool = False

    @property
    def is_occupied(self) -> bool:
        return self.agent_id is not None and self.status != "empty"

    @property
    def is_ready(self) -> bool:
        return self.is_occupied and not self.is_sitting_out and self.stack > 0

    def to_public_dict(self) -> dict[str, Any]:
        """Return public information about the seat."""
        return {
            "seat_number": self.seat_number,
            "agent_id": str(self.agent_id) if self.agent_id else None,
            "stack": self.stack,
            "status": self.status,
            "is_sitting_out": self.is_sitting_out,
        }

    def to_private_dict(self) -> dict[str, Any]:
        """Return full information including hole cards."""
        data = self.to_public_dict()
        data["hole_cards"] = [str(c) for c in self.hole_cards]
        return data


@dataclass
class TableConfig:
    """Configuration for a poker table."""

    table_id: UUID
    name: str
    small_blind: int
    big_blind: int
    min_buy_in: int
    max_buy_in: int
    max_players: int = 6


@dataclass
class TableState:
    """Complete state of a poker table."""

    config: TableConfig
    seats: dict[int, SeatState] = field(default_factory=dict)
    button_position: int = 0
    hand_number: int = 0
    status: str = "waiting"

    def __post_init__(self) -> None:
        if not self.seats:
            self.seats = {
                i: SeatState(seat_number=i) for i in range(self.config.max_players)
            }

    def get_empty_seats(self) -> list[int]:
        """Get list of empty seat numbers."""
        return [s.seat_number for s in self.seats.values() if not s.is_occupied]

    def get_occupied_seats(self) -> list[SeatState]:
        """Get list of occupied seats."""
        return [s for s in self.seats.values() if s.is_occupied]

    def get_ready_players(self) -> list[SeatState]:
        """Get seats with players ready to play."""
        return [s for s in self.seats.values() if s.is_ready]

    def get_seat_by_agent(self, agent_id: UUID) -> SeatState | None:
        """Find seat occupied by an agent."""
        for seat in self.seats.values():
            if seat.agent_id == agent_id:
                return seat
        return None

    def can_start_hand(self) -> bool:
        """Check if we have enough players to start a hand."""
        return len(self.get_ready_players()) >= 2

    def advance_button(self) -> int:
        """Move button to next occupied seat."""
        occupied = sorted([s.seat_number for s in self.get_ready_players()])
        if not occupied:
            return self.button_position

        current_idx = -1
        for i, seat_num in enumerate(occupied):
            if seat_num == self.button_position:
                current_idx = i
                break

        next_idx = (current_idx + 1) % len(occupied)
        self.button_position = occupied[next_idx]
        return self.button_position

    def get_blinds_positions(self) -> tuple[int, int]:
        """Get small blind and big blind positions.

        Returns (small_blind_seat, big_blind_seat)
        """
        ready = sorted([s.seat_number for s in self.get_ready_players()])
        if len(ready) < 2:
            raise ValueError("Need at least 2 players for blinds")

        button_idx = -1
        for i, seat in enumerate(ready):
            if seat == self.button_position:
                button_idx = i
                break

        if button_idx == -1:
            button_idx = 0
            self.button_position = ready[0]

        if len(ready) == 2:
            sb_seat = self.button_position
            bb_idx = (button_idx + 1) % len(ready)
            bb_seat = ready[bb_idx]
        else:
            sb_idx = (button_idx + 1) % len(ready)
            bb_idx = (button_idx + 2) % len(ready)
            sb_seat = ready[sb_idx]
            bb_seat = ready[bb_idx]

        return sb_seat, bb_seat

    def get_first_to_act_preflop(self) -> int:
        """Get the first player to act preflop (UTG)."""
        ready = sorted([s.seat_number for s in self.get_ready_players()])
        if len(ready) < 2:
            raise ValueError("Need at least 2 players")

        _, bb_seat = self.get_blinds_positions()
        bb_idx = ready.index(bb_seat)
        utg_idx = (bb_idx + 1) % len(ready)
        return ready[utg_idx]

    def get_first_to_act_postflop(self) -> int:
        """Get first player to act postflop (first active after button)."""
        ready = sorted([s.seat_number for s in self.get_ready_players()])
        if not ready:
            raise ValueError("No ready players")

        button_idx = 0
        for i, seat in enumerate(ready):
            if seat == self.button_position:
                button_idx = i
                break

        first_idx = (button_idx + 1) % len(ready)
        return ready[first_idx]

    def to_public_dict(self) -> dict[str, Any]:
        """Return public table state."""
        return {
            "table_id": str(self.config.table_id),
            "name": self.config.name,
            "small_blind": self.config.small_blind,
            "big_blind": self.config.big_blind,
            "min_buy_in": self.config.min_buy_in,
            "max_buy_in": self.config.max_buy_in,
            "max_players": self.config.max_players,
            "button_position": self.button_position,
            "hand_number": self.hand_number,
            "status": self.status,
            "seats": [self.seats[i].to_public_dict() for i in range(self.config.max_players)],
        }
