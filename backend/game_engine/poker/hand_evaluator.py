from dataclasses import dataclass
from enum import IntEnum

from treys import Card as TreysCard
from treys import Evaluator

from backend.game_engine.poker.deck import Card


class HandRank(IntEnum):
    """Hand rankings from best (1) to worst (9)."""

    ROYAL_FLUSH = 1
    STRAIGHT_FLUSH = 2
    FOUR_OF_A_KIND = 3
    FULL_HOUSE = 4
    FLUSH = 5
    STRAIGHT = 6
    THREE_OF_A_KIND = 7
    TWO_PAIR = 8
    PAIR = 9
    HIGH_CARD = 10


HAND_RANK_NAMES = {
    HandRank.ROYAL_FLUSH: "Royal Flush",
    HandRank.STRAIGHT_FLUSH: "Straight Flush",
    HandRank.FOUR_OF_A_KIND: "Four of a Kind",
    HandRank.FULL_HOUSE: "Full House",
    HandRank.FLUSH: "Flush",
    HandRank.STRAIGHT: "Straight",
    HandRank.THREE_OF_A_KIND: "Three of a Kind",
    HandRank.TWO_PAIR: "Two Pair",
    HandRank.PAIR: "Pair",
    HandRank.HIGH_CARD: "High Card",
}


@dataclass
class HandEvaluation:
    """Result of evaluating a poker hand."""

    score: int
    rank: HandRank
    rank_name: str

    def __lt__(self, other: "HandEvaluation") -> bool:
        return self.score < other.score

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, HandEvaluation):
            return NotImplemented
        return self.score == other.score


class HandEvaluator:
    """Poker hand evaluator using the treys library."""

    def __init__(self):
        self._evaluator = Evaluator()

    def _card_to_treys(self, card: Card) -> int:
        """Convert our Card to treys integer format."""
        return TreysCard.new(str(card))

    def _cards_to_treys(self, cards: list[Card]) -> list[int]:
        """Convert a list of Cards to treys format."""
        return [self._card_to_treys(c) for c in cards]

    def _score_to_rank(self, score: int) -> HandRank:
        """Convert treys score to HandRank."""
        rank_class = self._evaluator.get_rank_class(score)
        # Treys rank classes are 0-indexed:
        # 0 = Royal Flush (special case of Straight Flush with score=1)
        # 1 = Straight Flush
        # 2 = Four of a Kind, etc.
        mapping = {
            0: HandRank.STRAIGHT_FLUSH,  # Will be upgraded to Royal Flush if score == 1
            1: HandRank.STRAIGHT_FLUSH,
            2: HandRank.FOUR_OF_A_KIND,
            3: HandRank.FULL_HOUSE,
            4: HandRank.FLUSH,
            5: HandRank.STRAIGHT,
            6: HandRank.THREE_OF_A_KIND,
            7: HandRank.TWO_PAIR,
            8: HandRank.PAIR,
            9: HandRank.HIGH_CARD,
        }
        rank = mapping.get(rank_class, HandRank.HIGH_CARD)
        # Royal Flush is a Straight Flush with the best possible score (1)
        if rank == HandRank.STRAIGHT_FLUSH and score == 1:
            return HandRank.ROYAL_FLUSH
        return rank

    def evaluate(self, hole_cards: list[Card], community_cards: list[Card]) -> HandEvaluation:
        """Evaluate a poker hand.

        Args:
            hole_cards: The player's 2 hole cards
            community_cards: The 3-5 community cards on the board

        Returns:
            HandEvaluation with score (lower is better), rank, and rank name
        """
        if len(hole_cards) != 2:
            raise ValueError(f"Expected 2 hole cards, got {len(hole_cards)}")
        if not (3 <= len(community_cards) <= 5):
            raise ValueError(f"Expected 3-5 community cards, got {len(community_cards)}")

        treys_hole = self._cards_to_treys(hole_cards)
        treys_board = self._cards_to_treys(community_cards)

        score = self._evaluator.evaluate(treys_board, treys_hole)
        rank = self._score_to_rank(score)

        return HandEvaluation(
            score=score,
            rank=rank,
            rank_name=HAND_RANK_NAMES[rank],
        )

    def evaluate_best(
        self, hole_cards: list[Card], community_cards: list[Card]
    ) -> tuple[HandEvaluation, list[Card]]:
        """Evaluate and return the best 5-card hand.

        Returns both the evaluation and the 5 cards that make up the best hand.
        """
        evaluation = self.evaluate(hole_cards, community_cards)
        all_cards = hole_cards + community_cards
        return evaluation, all_cards[:5]

    def compare_hands(
        self, hands: list[tuple[list[Card], list[Card]]], community_cards: list[Card]
    ) -> list[tuple[int, HandEvaluation]]:
        """Compare multiple hands and return rankings.

        Args:
            hands: List of (hole_cards, player_id_placeholder) tuples
            community_cards: The community cards

        Returns:
            List of (player_index, evaluation) sorted by hand strength (best first)
        """
        evaluations = []
        for idx, (hole_cards, _) in enumerate(hands):
            evaluation = self.evaluate(hole_cards, community_cards)
            evaluations.append((idx, evaluation))

        evaluations.sort(key=lambda x: x[1].score)
        return evaluations


evaluator = HandEvaluator()
