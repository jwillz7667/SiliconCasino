import pytest

from backend.game_engine.poker.deck import Card, cards_from_string
from backend.game_engine.poker.hand_evaluator import HandEvaluator, HandRank


@pytest.fixture
def evaluator():
    return HandEvaluator()


class TestHandEvaluator:
    def test_royal_flush(self, evaluator):
        hole = cards_from_string("AhKh")
        board = cards_from_string("QhJhTh")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.ROYAL_FLUSH

    def test_straight_flush(self, evaluator):
        hole = cards_from_string("9h8h")
        board = cards_from_string("7h6h5h")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.STRAIGHT_FLUSH

    def test_four_of_a_kind(self, evaluator):
        hole = cards_from_string("AhAs")
        board = cards_from_string("AcAd2h")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.FOUR_OF_A_KIND

    def test_full_house(self, evaluator):
        hole = cards_from_string("AhAs")
        board = cards_from_string("AcKdKh")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.FULL_HOUSE

    def test_flush(self, evaluator):
        hole = cards_from_string("Ah9h")
        board = cards_from_string("Kh7h2h")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.FLUSH

    def test_straight(self, evaluator):
        hole = cards_from_string("AhKd")
        board = cards_from_string("QcJhTs")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.STRAIGHT

    def test_three_of_a_kind(self, evaluator):
        hole = cards_from_string("AhAs")
        board = cards_from_string("AcKd2h")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.THREE_OF_A_KIND

    def test_two_pair(self, evaluator):
        hole = cards_from_string("AhAs")
        board = cards_from_string("KcKd2h")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.TWO_PAIR

    def test_pair(self, evaluator):
        hole = cards_from_string("AhAs")
        board = cards_from_string("Kc7d2h")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.PAIR

    def test_high_card(self, evaluator):
        hole = cards_from_string("Ah9d")
        board = cards_from_string("Kc7h2s")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.HIGH_CARD

    def test_wheel_straight(self, evaluator):
        hole = cards_from_string("Ah2d")
        board = cards_from_string("3c4h5s")
        result = evaluator.evaluate(hole, board)
        assert result.rank == HandRank.STRAIGHT

    def test_compare_hands(self, evaluator):
        hands = [
            (cards_from_string("AhKh"), None),
            (cards_from_string("2c7d"), None),
        ]
        board = cards_from_string("QhJhTh")

        rankings = evaluator.compare_hands(hands, board)

        assert rankings[0][0] == 0
        assert rankings[0][1].rank == HandRank.ROYAL_FLUSH

    def test_invalid_hole_cards(self, evaluator):
        with pytest.raises(ValueError):
            evaluator.evaluate(cards_from_string("Ah"), cards_from_string("KcQhJh"))

    def test_invalid_community_cards(self, evaluator):
        with pytest.raises(ValueError):
            evaluator.evaluate(cards_from_string("AhKh"), cards_from_string("Qh"))


class TestHandEvaluation:
    def test_comparison(self, evaluator):
        royal = evaluator.evaluate(cards_from_string("AhKh"), cards_from_string("QhJhTh"))
        flush = evaluator.evaluate(cards_from_string("Ah9h"), cards_from_string("Kh7h2h"))

        assert royal < flush
        assert not flush < royal

    def test_equality(self, evaluator):
        eval1 = evaluator.evaluate(cards_from_string("AhKh"), cards_from_string("QhJhTh"))
        eval2 = evaluator.evaluate(cards_from_string("AsKs"), cards_from_string("QsJsTs"))

        assert eval1 == eval2
