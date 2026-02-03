"""Unit tests for the trivia engine."""

from uuid import uuid4

import pytest

from backend.game_engine.trivia.engine import (
    TriviaEngine,
    TriviaMatch,
    TriviaQuestion,
    MatchStatus,
    Category,
)


class TestTriviaQuestion:
    """Tests for TriviaQuestion class."""

    def test_is_correct_case_insensitive(self):
        """Answer checking should be case-insensitive."""
        q = TriviaQuestion(
            id=uuid4(),
            category=Category.SCIENCE,
            question="What is H2O?",
            correct_answer="Water",
            incorrect_answers=["Fire", "Air", "Earth"],
            difficulty=1,
        )

        assert q.is_correct("Water")
        assert q.is_correct("water")
        assert q.is_correct("WATER")
        assert q.is_correct("  water  ")
        assert not q.is_correct("Fire")

    def test_shuffled_choices(self):
        """Should return all choices including correct answer."""
        q = TriviaQuestion(
            id=uuid4(),
            category=Category.SCIENCE,
            question="Test?",
            correct_answer="Correct",
            incorrect_answers=["Wrong1", "Wrong2", "Wrong3"],
            difficulty=1,
        )

        choices = q.get_shuffled_choices()

        assert len(choices) == 4
        assert "Correct" in choices
        assert "Wrong1" in choices


class TestTriviaMatch:
    """Tests for TriviaMatch class."""

    def test_add_player(self):
        """Should add players to waiting match."""
        match = TriviaMatch(
            id=uuid4(),
            status=MatchStatus.WAITING,
            entry_fee=10,
            max_players=4,
            questions_count=5,
            category=None,
        )

        agent1 = uuid4()
        agent2 = uuid4()

        assert match.add_player(agent1, "Player1")
        assert match.add_player(agent2, "Player2")
        assert len(match.players) == 2
        assert agent1 in match.players

    def test_cannot_add_duplicate_player(self):
        """Should not add same player twice."""
        match = TriviaMatch(
            id=uuid4(),
            status=MatchStatus.WAITING,
            entry_fee=10,
            max_players=4,
            questions_count=5,
            category=None,
        )

        agent = uuid4()

        assert match.add_player(agent, "Player")
        assert not match.add_player(agent, "Player")
        assert len(match.players) == 1

    def test_cannot_add_to_full_match(self):
        """Should not add players beyond max."""
        match = TriviaMatch(
            id=uuid4(),
            status=MatchStatus.WAITING,
            entry_fee=10,
            max_players=2,
            questions_count=5,
            category=None,
        )

        match.add_player(uuid4(), "P1")
        match.add_player(uuid4(), "P2")
        assert not match.add_player(uuid4(), "P3")

    def test_prize_pool_calculation(self):
        """Prize pool should equal entry_fee * players."""
        match = TriviaMatch(
            id=uuid4(),
            status=MatchStatus.WAITING,
            entry_fee=100,
            max_players=8,
            questions_count=5,
            category=None,
        )

        match.add_player(uuid4(), "P1")
        match.add_player(uuid4(), "P2")
        match.add_player(uuid4(), "P3")

        assert match.prize_pool == 300

    def test_leaderboard_sorted_by_score(self):
        """Leaderboard should be sorted by score descending."""
        match = TriviaMatch(
            id=uuid4(),
            status=MatchStatus.WAITING,
            entry_fee=10,
            max_players=4,
            questions_count=5,
            category=None,
        )

        a1 = uuid4()
        a2 = uuid4()
        a3 = uuid4()

        match.add_player(a1, "Low")
        match.add_player(a2, "High")
        match.add_player(a3, "Mid")

        match.players[a1].score = 100
        match.players[a2].score = 500
        match.players[a3].score = 300

        leaderboard = match.get_leaderboard()

        assert leaderboard[0].display_name == "High"
        assert leaderboard[1].display_name == "Mid"
        assert leaderboard[2].display_name == "Low"


class TestTriviaEngine:
    """Tests for TriviaEngine class."""

    def test_create_match(self):
        """Should create a match with correct settings."""
        engine = TriviaEngine()

        match = engine.create_match(
            entry_fee=50,
            max_players=6,
            questions_count=10,
            category=Category.TECHNOLOGY,
        )

        assert match.id is not None
        assert match.status == MatchStatus.WAITING
        assert match.entry_fee == 50
        assert match.max_players == 6
        assert match.category == Category.TECHNOLOGY
        assert len(match.questions) <= 10  # May have fewer if not enough in bank

    def test_join_match(self):
        """Should join match successfully."""
        engine = TriviaEngine()
        match = engine.create_match(entry_fee=10, max_players=4, questions_count=5)

        agent_id = uuid4()
        success = engine.join_match(match.id, agent_id, "TestAgent")

        assert success
        assert agent_id in match.players

    def test_list_matches_filter(self):
        """Should filter matches by status."""
        engine = TriviaEngine()

        m1 = engine.create_match(entry_fee=10, max_players=4, questions_count=5)
        m2 = engine.create_match(entry_fee=10, max_players=4, questions_count=5)
        m2.status = MatchStatus.COMPLETE

        waiting = engine.list_matches(status=MatchStatus.WAITING)
        complete = engine.list_matches(status=MatchStatus.COMPLETE)

        assert len(waiting) == 1
        assert waiting[0].id == m1.id
        assert len(complete) == 1
        assert complete[0].id == m2.id

    def test_submit_answer_not_in_match(self):
        """Should reject answers from non-participants."""
        engine = TriviaEngine()
        match = engine.create_match(entry_fee=10, max_players=4, questions_count=5)

        # Try to answer without joining
        accepted, correct, ms = engine.submit_answer(
            match.id, uuid4(), "some answer"
        )

        assert not accepted

    def test_result_calculation(self):
        """Should calculate winner and payout correctly."""
        engine = TriviaEngine()
        match = engine.create_match(entry_fee=100, max_players=4, questions_count=5)

        a1 = uuid4()
        a2 = uuid4()

        match.add_player(a1, "Winner")
        match.add_player(a2, "Loser")

        match.players[a1].score = 1000
        match.players[a2].score = 500

        result = match.get_result()

        assert result.winner_id == a1
        assert result.winner_name == "Winner"
        # Winner gets 90% of 200 (2 players * 100 fee)
        assert result.payout[a1] == 180
