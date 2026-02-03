"""
Trivia Gladiator Engine.

Real-time knowledge competition where agents compete to answer
questions fastest. First correct answer wins the point.
"""

import asyncio
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Callable
from uuid import UUID, uuid4


class MatchStatus(Enum):
    """Status of a trivia match."""
    
    WAITING = auto()      # Waiting for players
    STARTING = auto()     # Countdown before first question
    QUESTION = auto()     # Question active, accepting answers
    REVEALING = auto()    # Showing answer before next question
    COMPLETE = auto()     # Match finished


class Category(Enum):
    """Trivia question categories."""
    
    SCIENCE = "science"
    HISTORY = "history"
    TECHNOLOGY = "technology"
    GEOGRAPHY = "geography"
    ENTERTAINMENT = "entertainment"
    SPORTS = "sports"
    MATH = "math"
    CODING = "coding"
    GENERAL = "general"


@dataclass
class TriviaQuestion:
    """A trivia question."""
    
    id: UUID
    category: Category
    question: str
    correct_answer: str
    incorrect_answers: list[str]
    difficulty: int  # 1-3
    time_limit_seconds: int = 15
    
    def get_shuffled_choices(self) -> list[str]:
        """Get all answers in random order."""
        choices = [self.correct_answer] + self.incorrect_answers
        random.shuffle(choices)
        return choices
    
    def is_correct(self, answer: str) -> bool:
        """Check if an answer is correct (case-insensitive)."""
        return answer.strip().lower() == self.correct_answer.strip().lower()
    
    def to_dict(self, hide_answer: bool = True) -> dict[str, Any]:
        data = {
            "id": str(self.id),
            "category": self.category.value,
            "question": self.question,
            "choices": self.get_shuffled_choices(),
            "difficulty": self.difficulty,
            "time_limit_seconds": self.time_limit_seconds,
        }
        if not hide_answer:
            data["correct_answer"] = self.correct_answer
        return data


@dataclass
class PlayerState:
    """State of a player in a trivia match."""
    
    agent_id: UUID
    display_name: str
    score: int = 0
    answers_correct: int = 0
    answers_wrong: int = 0
    fastest_answer_ms: int | None = None
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": str(self.agent_id),
            "display_name": self.display_name,
            "score": self.score,
            "answers_correct": self.answers_correct,
            "answers_wrong": self.answers_wrong,
            "fastest_answer_ms": self.fastest_answer_ms,
        }


@dataclass
class MatchResult:
    """Result of a completed trivia match."""
    
    match_id: UUID
    winner_id: UUID | None
    winner_name: str | None
    final_scores: dict[UUID, int]
    prize_pool: int
    payout: dict[UUID, int]  # agent_id -> chips won
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": str(self.match_id),
            "winner_id": str(self.winner_id) if self.winner_id else None,
            "winner_name": self.winner_name,
            "final_scores": {str(k): v for k, v in self.final_scores.items()},
            "prize_pool": self.prize_pool,
            "payout": {str(k): v for k, v in self.payout.items()},
        }


@dataclass
class TriviaMatch:
    """A trivia match between agents."""
    
    id: UUID
    status: MatchStatus
    entry_fee: int
    max_players: int
    questions_count: int
    category: Category | None  # None = mixed categories
    
    players: dict[UUID, PlayerState] = field(default_factory=dict)
    questions: list[TriviaQuestion] = field(default_factory=list)
    current_question_index: int = 0
    question_start_time: datetime | None = None
    answers_this_round: dict[UUID, tuple[str, int]] = field(default_factory=dict)  # agent_id -> (answer, ms)
    
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    ended_at: datetime | None = None
    
    # Event callback for real-time updates
    _event_callback: Callable[[str, dict], None] | None = None
    
    @property
    def current_question(self) -> TriviaQuestion | None:
        if 0 <= self.current_question_index < len(self.questions):
            return self.questions[self.current_question_index]
        return None
    
    @property
    def prize_pool(self) -> int:
        return len(self.players) * self.entry_fee
    
    @property
    def is_full(self) -> bool:
        return len(self.players) >= self.max_players
    
    def add_player(self, agent_id: UUID, display_name: str) -> bool:
        """Add a player to the match."""
        if self.status != MatchStatus.WAITING:
            return False
        if self.is_full:
            return False
        if agent_id in self.players:
            return False
        
        self.players[agent_id] = PlayerState(
            agent_id=agent_id,
            display_name=display_name,
        )
        return True
    
    def remove_player(self, agent_id: UUID) -> bool:
        """Remove a player from the match (only before start)."""
        if self.status != MatchStatus.WAITING:
            return False
        if agent_id not in self.players:
            return False
        
        del self.players[agent_id]
        return True
    
    def submit_answer(self, agent_id: UUID, answer: str) -> tuple[bool, bool, int]:
        """
        Submit an answer for the current question.
        
        Returns: (accepted, is_correct, response_time_ms)
        """
        if self.status != MatchStatus.QUESTION:
            return False, False, 0
        
        if agent_id not in self.players:
            return False, False, 0
        
        if agent_id in self.answers_this_round:
            return False, False, 0  # Already answered
        
        if not self.current_question or not self.question_start_time:
            return False, False, 0
        
        # Calculate response time
        now = datetime.now(timezone.utc)
        response_time_ms = int((now - self.question_start_time).total_seconds() * 1000)
        
        # Check if within time limit
        if response_time_ms > self.current_question.time_limit_seconds * 1000:
            return False, False, response_time_ms
        
        # Record answer
        self.answers_this_round[agent_id] = (answer, response_time_ms)
        
        is_correct = self.current_question.is_correct(answer)
        player = self.players[agent_id]
        
        if is_correct:
            player.answers_correct += 1
            # Update fastest answer
            if player.fastest_answer_ms is None or response_time_ms < player.fastest_answer_ms:
                player.fastest_answer_ms = response_time_ms
        else:
            player.answers_wrong += 1
        
        return True, is_correct, response_time_ms
    
    def evaluate_round(self) -> tuple[UUID | None, int]:
        """
        Evaluate the current round and award points.
        
        Returns: (winner_agent_id, points_awarded)
        """
        if not self.current_question:
            return None, 0
        
        # Find fastest correct answer
        correct_answers = [
            (agent_id, answer, ms)
            for agent_id, (answer, ms) in self.answers_this_round.items()
            if self.current_question.is_correct(answer)
        ]
        
        if not correct_answers:
            return None, 0
        
        # Sort by response time
        correct_answers.sort(key=lambda x: x[2])
        winner_id, _, ms = correct_answers[0]
        
        # Points based on difficulty and speed
        base_points = self.current_question.difficulty * 100
        speed_bonus = max(0, (self.current_question.time_limit_seconds * 1000 - ms) // 100)
        total_points = base_points + speed_bonus
        
        self.players[winner_id].score += total_points
        
        return winner_id, total_points
    
    def get_leaderboard(self) -> list[PlayerState]:
        """Get players sorted by score."""
        return sorted(self.players.values(), key=lambda p: p.score, reverse=True)
    
    def get_result(self) -> MatchResult:
        """Get the final match result."""
        leaderboard = self.get_leaderboard()
        
        winner = leaderboard[0] if leaderboard else None
        
        # Winner takes 90%, platform takes 10%
        platform_fee = int(self.prize_pool * 0.10)
        winner_prize = self.prize_pool - platform_fee
        
        payout = {}
        if winner:
            payout[winner.agent_id] = winner_prize
        
        return MatchResult(
            match_id=self.id,
            winner_id=winner.agent_id if winner else None,
            winner_name=winner.display_name if winner else None,
            final_scores={p.agent_id: p.score for p in self.players.values()},
            prize_pool=self.prize_pool,
            payout=payout,
        )
    
    def to_dict(self, include_answer: bool = False) -> dict[str, Any]:
        data = {
            "id": str(self.id),
            "status": self.status.name,
            "entry_fee": self.entry_fee,
            "max_players": self.max_players,
            "current_players": len(self.players),
            "questions_count": self.questions_count,
            "current_question": self.current_question_index + 1,
            "category": self.category.value if self.category else "mixed",
            "prize_pool": self.prize_pool,
            "players": [p.to_dict() for p in self.get_leaderboard()],
            "created_at": self.created_at.isoformat(),
        }
        
        if self.current_question and self.status == MatchStatus.QUESTION:
            data["question"] = self.current_question.to_dict(hide_answer=not include_answer)
        
        if self.status == MatchStatus.REVEALING and self.current_question:
            data["question"] = self.current_question.to_dict(hide_answer=False)
            data["round_winner"] = None  # Set by engine
        
        return data


class TriviaEngine:
    """Engine for managing trivia matches."""
    
    # Sample questions (in production, load from database)
    SAMPLE_QUESTIONS = [
        TriviaQuestion(
            id=uuid4(),
            category=Category.TECHNOLOGY,
            question="What year was Python first released?",
            correct_answer="1991",
            incorrect_answers=["1989", "1995", "2000"],
            difficulty=2,
        ),
        TriviaQuestion(
            id=uuid4(),
            category=Category.TECHNOLOGY,
            question="Who created Linux?",
            correct_answer="Linus Torvalds",
            incorrect_answers=["Bill Gates", "Steve Jobs", "Richard Stallman"],
            difficulty=1,
        ),
        TriviaQuestion(
            id=uuid4(),
            category=Category.SCIENCE,
            question="What is the chemical symbol for gold?",
            correct_answer="Au",
            incorrect_answers=["Ag", "Fe", "Cu"],
            difficulty=1,
        ),
        TriviaQuestion(
            id=uuid4(),
            category=Category.MATH,
            question="What is the derivative of x²?",
            correct_answer="2x",
            incorrect_answers=["x", "x²", "2"],
            difficulty=1,
        ),
        TriviaQuestion(
            id=uuid4(),
            category=Category.HISTORY,
            question="In what year did World War II end?",
            correct_answer="1945",
            incorrect_answers=["1944", "1946", "1943"],
            difficulty=1,
        ),
        TriviaQuestion(
            id=uuid4(),
            category=Category.CODING,
            question="What does 'SQL' stand for?",
            correct_answer="Structured Query Language",
            incorrect_answers=["Simple Query Language", "Standard Query Language", "System Query Language"],
            difficulty=1,
        ),
        TriviaQuestion(
            id=uuid4(),
            category=Category.TECHNOLOGY,
            question="What company developed the Rust programming language?",
            correct_answer="Mozilla",
            incorrect_answers=["Google", "Microsoft", "Apple"],
            difficulty=2,
        ),
        TriviaQuestion(
            id=uuid4(),
            category=Category.SCIENCE,
            question="What is the speed of light in km/s (approximately)?",
            correct_answer="300,000",
            incorrect_answers=["150,000", "500,000", "1,000,000"],
            difficulty=2,
        ),
        TriviaQuestion(
            id=uuid4(),
            category=Category.CODING,
            question="What is the time complexity of binary search?",
            correct_answer="O(log n)",
            incorrect_answers=["O(n)", "O(n²)", "O(1)"],
            difficulty=2,
        ),
        TriviaQuestion(
            id=uuid4(),
            category=Category.TECHNOLOGY,
            question="What does 'API' stand for?",
            correct_answer="Application Programming Interface",
            incorrect_answers=["Advanced Programming Interface", "Application Process Integration", "Automated Programming Interface"],
            difficulty=1,
        ),
    ]
    
    def __init__(self):
        self._matches: dict[UUID, TriviaMatch] = {}
        self._question_bank: list[TriviaQuestion] = self.SAMPLE_QUESTIONS.copy()
    
    def create_match(
        self,
        entry_fee: int,
        max_players: int = 8,
        questions_count: int = 10,
        category: Category | None = None,
    ) -> TriviaMatch:
        """Create a new trivia match."""
        match = TriviaMatch(
            id=uuid4(),
            status=MatchStatus.WAITING,
            entry_fee=entry_fee,
            max_players=max_players,
            questions_count=questions_count,
            category=category,
        )
        
        # Select questions
        available = self._question_bank.copy()
        if category:
            available = [q for q in available if q.category == category]
        
        random.shuffle(available)
        match.questions = available[:questions_count]
        
        self._matches[match.id] = match
        return match
    
    def get_match(self, match_id: UUID) -> TriviaMatch | None:
        return self._matches.get(match_id)
    
    def list_matches(self, status: MatchStatus | None = None) -> list[TriviaMatch]:
        matches = list(self._matches.values())
        if status:
            matches = [m for m in matches if m.status == status]
        return sorted(matches, key=lambda m: m.created_at, reverse=True)
    
    def join_match(self, match_id: UUID, agent_id: UUID, display_name: str) -> bool:
        """Join a match. Returns True if successful."""
        match = self._matches.get(match_id)
        if not match:
            return False
        return match.add_player(agent_id, display_name)
    
    def leave_match(self, match_id: UUID, agent_id: UUID) -> bool:
        """Leave a match before it starts."""
        match = self._matches.get(match_id)
        if not match:
            return False
        return match.remove_player(agent_id)
    
    async def start_match(self, match_id: UUID) -> bool:
        """Start a match. Requires at least 2 players."""
        match = self._matches.get(match_id)
        if not match:
            return False
        
        if match.status != MatchStatus.WAITING:
            return False
        
        if len(match.players) < 2:
            return False
        
        match.status = MatchStatus.STARTING
        match.started_at = datetime.now(timezone.utc)
        
        # Brief countdown then start first question
        await asyncio.sleep(3)
        await self._next_question(match)
        
        return True
    
    async def _next_question(self, match: TriviaMatch) -> None:
        """Advance to the next question."""
        if match.current_question_index >= len(match.questions):
            # Match complete
            match.status = MatchStatus.COMPLETE
            match.ended_at = datetime.now(timezone.utc)
            return
        
        match.status = MatchStatus.QUESTION
        match.question_start_time = datetime.now(timezone.utc)
        match.answers_this_round = {}
        
        # Wait for time limit
        if match.current_question:
            await asyncio.sleep(match.current_question.time_limit_seconds)
        
        # Evaluate round
        winner_id, points = match.evaluate_round()
        
        # Reveal phase
        match.status = MatchStatus.REVEALING
        await asyncio.sleep(3)  # Show answer for 3 seconds
        
        # Next question
        match.current_question_index += 1
        await self._next_question(match)
    
    def submit_answer(
        self,
        match_id: UUID,
        agent_id: UUID,
        answer: str,
    ) -> tuple[bool, bool, int]:
        """Submit an answer. Returns (accepted, correct, response_time_ms)."""
        match = self._matches.get(match_id)
        if not match:
            return False, False, 0
        return match.submit_answer(agent_id, answer)
    
    def get_leaderboard(self, match_id: UUID) -> list[dict[str, Any]]:
        """Get current leaderboard for a match."""
        match = self._matches.get(match_id)
        if not match:
            return []
        return [p.to_dict() for p in match.get_leaderboard()]


# Global trivia engine
trivia_engine = TriviaEngine()
