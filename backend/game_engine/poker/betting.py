from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
from uuid import UUID


class ActionType(Enum):
    FOLD = auto()
    CHECK = auto()
    CALL = auto()
    BET = auto()
    RAISE = auto()
    ALL_IN = auto()


class BettingRound(Enum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"


@dataclass
class PlayerAction:
    """Represents a player's action."""

    player_seat: int
    agent_id: UUID
    action_type: ActionType
    amount: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_seat": self.player_seat,
            "agent_id": str(self.agent_id),
            "action_type": self.action_type.name,
            "amount": self.amount,
        }


@dataclass
class PlayerBettingState:
    """Tracks a player's betting state within a hand."""

    seat: int
    agent_id: UUID
    stack: int
    bet_this_round: int = 0
    total_bet_this_hand: int = 0
    has_acted: bool = False
    is_folded: bool = False
    is_all_in: bool = False

    @property
    def is_active(self) -> bool:
        """Player can still act in the hand."""
        return not self.is_folded and not self.is_all_in

    def reset_for_round(self) -> None:
        """Reset state for a new betting round."""
        self.bet_this_round = 0
        self.has_acted = False


@dataclass
class BettingState:
    """Tracks the state of betting within a hand."""

    round: BettingRound
    players: dict[int, PlayerBettingState] = field(default_factory=dict)
    current_bet: int = 0
    min_raise: int = 0
    pot: int = 0
    action_on: int = -1
    last_aggressor: int = -1
    big_blind: int = 0

    def get_valid_actions(self, seat: int) -> list[ActionType]:
        """Get valid actions for a player."""
        player = self.players.get(seat)
        if not player or not player.is_active:
            return []

        actions = [ActionType.FOLD]

        to_call = self.current_bet - player.bet_this_round

        if to_call == 0:
            actions.append(ActionType.CHECK)
        else:
            if player.stack >= to_call:
                actions.append(ActionType.CALL)

        min_raise_to = self.current_bet + self.min_raise
        if player.stack > to_call:
            if self.current_bet == 0:
                if player.stack >= self.big_blind:
                    actions.append(ActionType.BET)
            else:
                if player.stack + player.bet_this_round >= min_raise_to:
                    actions.append(ActionType.RAISE)

        if player.stack > 0:
            actions.append(ActionType.ALL_IN)

        return actions

    def get_call_amount(self, seat: int) -> int:
        """Get the amount needed to call."""
        player = self.players.get(seat)
        if not player:
            return 0
        return min(self.current_bet - player.bet_this_round, player.stack)

    def get_min_raise_to(self) -> int:
        """Get the minimum total bet for a raise."""
        return self.current_bet + self.min_raise

    def process_action(self, action: PlayerAction) -> bool:
        """Process a player action and update state.

        Returns True if betting round is complete.
        """
        player = self.players.get(action.player_seat)
        if not player:
            raise ValueError(f"No player at seat {action.player_seat}")

        if action.action_type == ActionType.FOLD:
            player.is_folded = True
            player.has_acted = True

        elif action.action_type == ActionType.CHECK:
            if self.current_bet > player.bet_this_round:
                raise ValueError("Cannot check when facing a bet")
            player.has_acted = True

        elif action.action_type == ActionType.CALL:
            call_amount = min(self.current_bet - player.bet_this_round, player.stack)
            player.stack -= call_amount
            player.bet_this_round += call_amount
            player.total_bet_this_hand += call_amount
            self.pot += call_amount
            player.has_acted = True
            if player.stack == 0:
                player.is_all_in = True

        elif action.action_type in (ActionType.BET, ActionType.RAISE):
            if action.amount < self.get_min_raise_to() and action.amount < player.stack + player.bet_this_round:
                raise ValueError(f"Raise must be at least {self.get_min_raise_to()}")

            raise_amount = action.amount - player.bet_this_round
            if raise_amount > player.stack:
                raise ValueError(f"Cannot bet {raise_amount}, only have {player.stack}")

            actual_raise = action.amount - self.current_bet
            if actual_raise > self.min_raise:
                self.min_raise = actual_raise

            player.stack -= raise_amount
            player.bet_this_round = action.amount
            player.total_bet_this_hand += raise_amount
            self.pot += raise_amount
            self.current_bet = action.amount
            self.last_aggressor = action.player_seat
            player.has_acted = True

            for p in self.players.values():
                if p.seat != action.player_seat and p.is_active:
                    p.has_acted = False

            if player.stack == 0:
                player.is_all_in = True

        elif action.action_type == ActionType.ALL_IN:
            all_in_amount = player.stack
            total_bet = player.bet_this_round + all_in_amount

            if total_bet > self.current_bet:
                actual_raise = total_bet - self.current_bet
                if actual_raise >= self.min_raise:
                    self.min_raise = actual_raise
                    for p in self.players.values():
                        if p.seat != action.player_seat and p.is_active:
                            p.has_acted = False
                self.current_bet = total_bet
                self.last_aggressor = action.player_seat

            player.bet_this_round = total_bet
            player.total_bet_this_hand += all_in_amount
            self.pot += all_in_amount
            player.stack = 0
            player.is_all_in = True
            player.has_acted = True

        return self._is_round_complete()

    def _is_round_complete(self) -> bool:
        """Check if the betting round is complete."""
        active_players = [p for p in self.players.values() if p.is_active]

        if len(active_players) <= 1:
            return True

        for player in active_players:
            if not player.has_acted:
                return False
            if player.bet_this_round < self.current_bet:
                return False

        return True

    def get_next_to_act(self, button_seat: int, num_seats: int) -> int | None:
        """Get the next player to act."""
        active_seats = sorted([
            s for s, p in self.players.items() if p.is_active and not p.has_acted
        ])

        if not active_seats:
            active_seats = sorted([
                s for s, p in self.players.items()
                if p.is_active and p.bet_this_round < self.current_bet
            ])

        if not active_seats:
            return None

        for seat in range(self.action_on + 1, num_seats):
            if seat in active_seats:
                return seat
        for seat in range(0, self.action_on + 1):
            if seat in active_seats:
                return seat

        return active_seats[0] if active_seats else None

    def start_new_round(self, new_round: BettingRound, first_to_act: int) -> None:
        """Start a new betting round."""
        self.round = new_round
        self.current_bet = 0
        self.min_raise = self.big_blind
        self.action_on = first_to_act
        self.last_aggressor = -1

        for player in self.players.values():
            player.reset_for_round()

    def count_active_players(self) -> int:
        """Count players still active in the hand."""
        return sum(1 for p in self.players.values() if not p.is_folded)

    def count_players_with_action(self) -> int:
        """Count players who can still take action."""
        return sum(1 for p in self.players.values() if p.is_active)
