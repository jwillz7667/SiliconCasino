from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any
from uuid import UUID, uuid4

from backend.game_engine.poker.betting import (
    ActionType,
    BettingRound,
    BettingState,
    PlayerAction,
    PlayerBettingState,
)
from backend.game_engine.poker.deck import Card, Deck, cards_to_string
from backend.game_engine.poker.hand_evaluator import HandEvaluation, evaluator
from backend.game_engine.poker.table import TableConfig, TableState


class HandPhase(Enum):
    WAITING = auto()
    PREFLOP = auto()
    FLOP = auto()
    TURN = auto()
    RIVER = auto()
    SHOWDOWN = auto()
    COMPLETE = auto()


@dataclass
class HandResult:
    """Result of a completed hand."""

    hand_id: UUID
    winners: list[dict[str, Any]]
    pot_distribution: dict[int, int]
    showdown_hands: dict[int, dict[str, Any]] | None = None
    rake_collected: int = 0


@dataclass
class RakeConfig:
    """Configuration for rake collection."""

    percentage: float = 0.05  # 5% rake
    cap: int = 500  # Maximum rake per hand
    threshold: int = 100  # Minimum pot to collect rake


@dataclass
class HandState:
    """State of a single poker hand."""

    hand_id: UUID
    hand_number: int
    phase: HandPhase
    deck: Deck
    community_cards: list[Card] = field(default_factory=list)
    pot: int = 0
    betting: BettingState | None = None
    button_seat: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    events: list[dict[str, Any]] = field(default_factory=list)
    hole_cards: dict[int, list[Card]] = field(default_factory=dict)
    rake_collected: int = 0

    def to_public_dict(self, for_seat: int | None = None) -> dict[str, Any]:
        """Return public hand state, optionally including hole cards for a specific seat."""
        data = {
            "hand_id": str(self.hand_id),
            "hand_number": self.hand_number,
            "phase": self.phase.name,
            "community_cards": [str(c) for c in self.community_cards],
            "pot": self.pot,
            "button_seat": self.button_seat,
        }

        if self.betting:
            data["current_bet"] = self.betting.current_bet
            data["action_on"] = self.betting.action_on
            data["min_raise_to"] = self.betting.get_min_raise_to()
            data["players"] = {
                seat: {
                    "bet_this_round": p.bet_this_round,
                    "total_bet": p.total_bet_this_hand,
                    "is_folded": p.is_folded,
                    "is_all_in": p.is_all_in,
                    "stack": p.stack,
                }
                for seat, p in self.betting.players.items()
            }

        if for_seat is not None and for_seat in self.hole_cards:
            data["your_cards"] = [str(c) for c in self.hole_cards[for_seat]]

        return data


class PokerEngine:
    """Main poker game engine that manages hands."""

    def __init__(
        self,
        table_config: TableConfig,
        seed: int | None = None,
        rake_config: RakeConfig | None = None,
    ):
        self.table = TableState(config=table_config)
        self._seed = seed
        self._rake_config = rake_config or RakeConfig()
        self._current_hand: HandState | None = None
        self._event_sequence = 0
        self._total_rake_collected: int = 0  # Track total rake for the session

    def _calculate_rake(self, pot: int) -> int:
        """Calculate rake to collect from the pot."""
        if pot < self._rake_config.threshold:
            return 0

        rake = int(pot * self._rake_config.percentage)
        return min(rake, self._rake_config.cap)

    @property
    def current_hand(self) -> HandState | None:
        return self._current_hand

    @property
    def total_rake_collected(self) -> int:
        """Get total rake collected during this session."""
        return self._total_rake_collected

    def seat_player(self, agent_id: UUID, seat_number: int, buy_in: int) -> bool:
        """Seat a player at the table."""
        if seat_number < 0 or seat_number >= self.table.config.max_players:
            raise ValueError(f"Invalid seat number: {seat_number}")

        seat = self.table.seats[seat_number]
        if seat.is_occupied:
            raise ValueError(f"Seat {seat_number} is already occupied")

        if buy_in < self.table.config.min_buy_in:
            raise ValueError(f"Buy-in {buy_in} below minimum {self.table.config.min_buy_in}")
        if buy_in > self.table.config.max_buy_in:
            raise ValueError(f"Buy-in {buy_in} above maximum {self.table.config.max_buy_in}")

        seat.agent_id = agent_id
        seat.stack = buy_in
        seat.status = "seated"
        seat.hole_cards = []

        return True

    def remove_player(self, agent_id: UUID) -> int:
        """Remove a player from the table. Returns their remaining stack."""
        seat = self.table.get_seat_by_agent(agent_id)
        if not seat:
            raise ValueError(f"Agent {agent_id} not found at table")

        remaining_stack = seat.stack
        seat.agent_id = None
        seat.stack = 0
        seat.status = "empty"
        seat.hole_cards = []

        return remaining_stack

    def add_chips(self, agent_id: UUID, amount: int) -> int:
        """Add chips to a player's stack. Returns new stack."""
        seat = self.table.get_seat_by_agent(agent_id)
        if not seat:
            raise ValueError(f"Agent {agent_id} not found at table")

        new_stack = seat.stack + amount
        if new_stack > self.table.config.max_buy_in:
            raise ValueError("Stack would exceed maximum buy-in")

        seat.stack = new_stack
        return new_stack

    def can_start_hand(self) -> bool:
        """Check if we can start a new hand."""
        return self._current_hand is None and self.table.can_start_hand()

    def start_hand(self) -> HandState:
        """Start a new hand."""
        if self._current_hand is not None:
            raise ValueError("Hand already in progress")

        ready_players = self.table.get_ready_players()
        if len(ready_players) < 2:
            raise ValueError("Need at least 2 players to start")

        self.table.advance_button()
        self.table.hand_number += 1
        self._event_sequence = 0

        hand = HandState(
            hand_id=uuid4(),
            hand_number=self.table.hand_number,
            phase=HandPhase.PREFLOP,
            deck=Deck(seed=self._seed),
            button_seat=self.table.button_position,
        )

        for seat in ready_players:
            hole_cards = hand.deck.deal(2)
            seat.hole_cards = hole_cards
            hand.hole_cards[seat.seat_number] = hole_cards

        sb_seat, bb_seat = self.table.get_blinds_positions()
        sb_amount = min(self.table.config.small_blind, self.table.seats[sb_seat].stack)
        bb_amount = min(self.table.config.big_blind, self.table.seats[bb_seat].stack)

        betting = BettingState(
            round=BettingRound.PREFLOP,
            big_blind=self.table.config.big_blind,
            min_raise=self.table.config.big_blind,
        )

        for seat in ready_players:
            betting.players[seat.seat_number] = PlayerBettingState(
                seat=seat.seat_number,
                agent_id=seat.agent_id,
                stack=seat.stack,
            )

        sb_player = betting.players[sb_seat]
        sb_player.stack -= sb_amount
        sb_player.bet_this_round = sb_amount
        sb_player.total_bet_this_hand = sb_amount
        hand.pot += sb_amount
        betting.pot += sb_amount  # Sync betting pot with blinds
        self.table.seats[sb_seat].stack -= sb_amount

        bb_player = betting.players[bb_seat]
        bb_player.stack -= bb_amount
        bb_player.bet_this_round = bb_amount
        bb_player.total_bet_this_hand = bb_amount
        hand.pot += bb_amount
        betting.pot += bb_amount  # Sync betting pot with blinds
        self.table.seats[bb_seat].stack -= bb_amount

        betting.current_bet = bb_amount
        betting.action_on = self.table.get_first_to_act_preflop()

        hand.betting = betting
        self._current_hand = hand
        self.table.status = "playing"

        self._add_event("hand_start", None, {
            "hand_number": hand.hand_number,
            "button_seat": hand.button_seat,
            "small_blind": sb_amount,
            "big_blind": bb_amount,
        })

        return hand

    def get_valid_actions(self, agent_id: UUID) -> list[ActionType]:
        """Get valid actions for a player."""
        if not self._current_hand or not self._current_hand.betting:
            return []

        seat = self.table.get_seat_by_agent(agent_id)
        if not seat:
            return []

        if self._current_hand.betting.action_on != seat.seat_number:
            return []

        return self._current_hand.betting.get_valid_actions(seat.seat_number)

    def process_action(self, agent_id: UUID, action_type: ActionType, amount: int = 0) -> bool:
        """Process a player action. Returns True if hand continues."""
        if not self._current_hand or not self._current_hand.betting:
            raise ValueError("No hand in progress")

        seat = self.table.get_seat_by_agent(agent_id)
        if not seat:
            raise ValueError(f"Agent {agent_id} not found at table")

        betting = self._current_hand.betting
        if betting.action_on != seat.seat_number:
            raise ValueError(f"Not {agent_id}'s turn to act")

        valid_actions = betting.get_valid_actions(seat.seat_number)
        if action_type not in valid_actions:
            raise ValueError(f"Invalid action {action_type.name}. Valid: {[a.name for a in valid_actions]}")

        action = PlayerAction(
            player_seat=seat.seat_number,
            agent_id=agent_id,
            action_type=action_type,
            amount=amount,
        )

        round_complete = betting.process_action(action)

        self.table.seats[seat.seat_number].stack = betting.players[seat.seat_number].stack

        self._add_event("player_action", agent_id, action.to_dict())

        if betting.count_active_players() == 1:
            return self._handle_everyone_folded()

        if round_complete:
            return self._advance_to_next_phase()

        # Get next player to act - use explicit None check since seat 0 is valid
        next_to_act = betting.get_next_to_act(
            self.table.button_position,
            self.table.config.max_players,
        )
        if next_to_act is not None:
            betting.action_on = next_to_act

        return True

    def _advance_to_next_phase(self) -> bool:
        """Advance to the next phase of the hand."""
        hand = self._current_hand
        if not hand or not hand.betting:
            return False

        if hand.betting.count_players_with_action() <= 1:
            if hand.phase == HandPhase.RIVER:
                return self._handle_showdown()
            self._deal_remaining_and_showdown()
            return False

        phase_transitions = {
            HandPhase.PREFLOP: (HandPhase.FLOP, 3),
            HandPhase.FLOP: (HandPhase.TURN, 1),
            HandPhase.TURN: (HandPhase.RIVER, 1),
            HandPhase.RIVER: (HandPhase.SHOWDOWN, 0),
        }

        transition = phase_transitions.get(hand.phase)
        if not transition:
            return False

        next_phase, cards_to_deal = transition

        if next_phase == HandPhase.SHOWDOWN:
            return self._handle_showdown()

        hand.deck.burn()
        new_cards = hand.deck.deal(cards_to_deal)
        hand.community_cards.extend(new_cards)

        hand.phase = next_phase

        self._add_event("community_cards", None, {
            "phase": next_phase.name,
            "cards": [str(c) for c in new_cards],
            "board": [str(c) for c in hand.community_cards],
        })

        ready_seats = sorted([s.seat_number for s in self.table.get_ready_players()])
        active_seats = [s for s in ready_seats if not hand.betting.players[s].is_folded]

        first_to_act = None
        button_idx = -1
        for i, s in enumerate(active_seats):
            if s == self.table.button_position:
                button_idx = i
                break

        if button_idx >= 0:
            first_idx = (button_idx + 1) % len(active_seats)
            first_to_act = active_seats[first_idx]
        else:
            first_to_act = active_seats[0] if active_seats else ready_seats[0]

        hand.betting.start_new_round(
            BettingRound(next_phase.name.lower()),
            first_to_act,
        )

        return True

    def _deal_remaining_and_showdown(self) -> bool:
        """Deal remaining community cards and go to showdown when all-in."""
        hand = self._current_hand
        if not hand:
            return False

        while len(hand.community_cards) < 5:
            if hand.phase == HandPhase.PREFLOP:
                hand.deck.burn()
                hand.community_cards.extend(hand.deck.deal(3))
                hand.phase = HandPhase.FLOP
            elif hand.phase == HandPhase.FLOP:
                hand.deck.burn()
                hand.community_cards.extend(hand.deck.deal(1))
                hand.phase = HandPhase.TURN
            elif hand.phase == HandPhase.TURN:
                hand.deck.burn()
                hand.community_cards.extend(hand.deck.deal(1))
                hand.phase = HandPhase.RIVER

        self._add_event("community_cards", None, {
            "phase": "RUNOUT",
            "board": [str(c) for c in hand.community_cards],
        })

        return self._handle_showdown()

    def _handle_everyone_folded(self) -> bool:
        """Handle case where everyone but one player folded."""
        hand = self._current_hand
        if not hand or not hand.betting:
            return False

        active_players = [
            (seat, p) for seat, p in hand.betting.players.items() if not p.is_folded
        ]

        if len(active_players) != 1:
            return True

        winner_seat, winner_state = active_players[0]
        total_pot = hand.betting.pot

        # Calculate and collect rake
        rake = self._calculate_rake(total_pot)
        pot_won = total_pot - rake
        hand.rake_collected = rake
        self._total_rake_collected += rake

        self.table.seats[winner_seat].stack += pot_won

        result = HandResult(
            hand_id=hand.hand_id,
            winners=[{
                "seat": winner_seat,
                "agent_id": str(winner_state.agent_id),
                "amount": pot_won,
                "reason": "everyone_folded",
            }],
            pot_distribution={winner_seat: pot_won},
            rake_collected=rake,
        )

        self._add_event("hand_complete", None, {
            "result": "fold_win",
            "winner_seat": winner_seat,
            "pot": pot_won,
            "rake": rake,
        })

        self._complete_hand(result)
        return False

    def _handle_showdown(self) -> bool:
        """Handle showdown and determine winner(s)."""
        hand = self._current_hand
        if not hand or not hand.betting:
            return False

        hand.phase = HandPhase.SHOWDOWN

        active_players = [
            (seat, p) for seat, p in hand.betting.players.items() if not p.is_folded
        ]

        if len(active_players) == 1:
            return self._handle_everyone_folded()

        evaluations: list[tuple[int, UUID, HandEvaluation]] = []
        showdown_hands = {}

        for seat, player_state in active_players:
            hole_cards = hand.hole_cards.get(seat, [])
            if len(hole_cards) == 2 and len(hand.community_cards) >= 3:
                eval_result = evaluator.evaluate(hole_cards, hand.community_cards)
                evaluations.append((seat, player_state.agent_id, eval_result))
                showdown_hands[seat] = {
                    "hole_cards": [str(c) for c in hole_cards],
                    "hand_rank": eval_result.rank_name,
                    "score": eval_result.score,
                }

        evaluations.sort(key=lambda x: x[2].score)

        best_score = evaluations[0][2].score
        winners = [(seat, agent_id, eval_) for seat, agent_id, eval_ in evaluations if eval_.score == best_score]

        total_pot = hand.betting.pot

        # Calculate and collect rake
        rake = self._calculate_rake(total_pot)
        pot = total_pot - rake
        hand.rake_collected = rake
        self._total_rake_collected += rake

        share = pot // len(winners)
        remainder = pot % len(winners)

        pot_distribution = {}
        result_winners = []

        for i, (seat, agent_id, eval_) in enumerate(winners):
            amount = share + (1 if i < remainder else 0)
            pot_distribution[seat] = amount
            self.table.seats[seat].stack += amount
            result_winners.append({
                "seat": seat,
                "agent_id": str(agent_id),
                "amount": amount,
                "hand_rank": eval_.rank_name,
            })

        result = HandResult(
            hand_id=hand.hand_id,
            winners=result_winners,
            pot_distribution=pot_distribution,
            showdown_hands=showdown_hands,
            rake_collected=rake,
        )

        self._add_event("showdown", None, {
            "hands": showdown_hands,
            "winners": result_winners,
            "rake": rake,
        })

        self._complete_hand(result)
        return False

    def _complete_hand(self, result: HandResult) -> None:
        """Complete the current hand."""
        if self._current_hand:
            self._current_hand.phase = HandPhase.COMPLETE

        for seat in self.table.seats.values():
            seat.hole_cards = []

        self._current_hand = None
        self.table.status = "waiting"

        self._add_event("hand_end", None, {
            "hand_id": str(result.hand_id),
            "pot_distribution": {str(k): v for k, v in result.pot_distribution.items()},
        })

    def _add_event(self, event_type: str, agent_id: UUID | None, payload: dict[str, Any]) -> None:
        """Add an event to the hand history."""
        if not self._current_hand:
            return

        self._event_sequence += 1
        self._current_hand.events.append({
            "sequence": self._event_sequence,
            "type": event_type,
            "agent_id": str(agent_id) if agent_id else None,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def get_state(self, for_agent: UUID | None = None) -> dict[str, Any]:
        """Get current game state, optionally personalized for an agent."""
        state = {
            "table": self.table.to_public_dict(),
            "hand": None,
        }

        if self._current_hand:
            seat = self.table.get_seat_by_agent(for_agent) if for_agent else None
            seat_num = seat.seat_number if seat else None
            state["hand"] = self._current_hand.to_public_dict(for_seat=seat_num)

            if for_agent and self._current_hand.betting:
                state["valid_actions"] = [a.name for a in self.get_valid_actions(for_agent)]
                state["is_your_turn"] = self._current_hand.betting.action_on == seat_num
            else:
                state["valid_actions"] = []
                state["is_your_turn"] = False

        return state

    def get_community_cards_string(self) -> str:
        """Get community cards as a string for database storage."""
        if not self._current_hand:
            return ""
        return cards_to_string(self._current_hand.community_cards)
