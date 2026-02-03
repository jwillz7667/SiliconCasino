"""Database models for trivia matches."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.database import Base

if TYPE_CHECKING:
    from backend.db.models.agent import Agent


class TriviaQuestion(Base):
    """A trivia question in the question bank."""

    __tablename__ = "trivia_questions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str] = mapped_column(String(500), nullable=False)
    incorrect_answers: Mapped[list[str]] = mapped_column(ARRAY(String(500)), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)  # 1-3
    time_limit_seconds: Mapped[int] = mapped_column(Integer, default=15)

    times_used: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    def __repr__(self) -> str:
        return f"<Question {self.id}: {self.question[:30]}...>"


class TriviaMatch(Base):
    """A trivia match between agents."""

    __tablename__ = "trivia_matches"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")

    status: Mapped[str] = mapped_column(
        Enum("WAITING", "STARTING", "QUESTION", "REVEALING", "COMPLETE", name="trivia_status"),
        default="WAITING",
        index=True,
    )

    entry_fee: Mapped[int] = mapped_column(Integer, nullable=False)
    max_players: Mapped[int] = mapped_column(Integer, default=8)
    questions_count: Mapped[int] = mapped_column(Integer, default=10)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)  # None = mixed

    prize_pool: Mapped[int] = mapped_column(Integer, default=0)
    winner_id: Mapped[UUID | None] = mapped_column(ForeignKey("agents.id"), nullable=True)

    current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    question_ids: Mapped[list[str]] = mapped_column(ARRAY(String(36)), default=[])

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    participants: Mapped[list["TriviaParticipant"]] = relationship(
        "TriviaParticipant", back_populates="match"
    )
    winner: Mapped["Agent | None"] = relationship("Agent", foreign_keys=[winner_id])

    def __repr__(self) -> str:
        return f"<TriviaMatch {self.id} ({self.status})>"


class TriviaParticipant(Base):
    """An agent participating in a trivia match."""

    __tablename__ = "trivia_participants"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    match_id: Mapped[UUID] = mapped_column(ForeignKey("trivia_matches.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)

    score: Mapped[int] = mapped_column(Integer, default=0)
    answers_correct: Mapped[int] = mapped_column(Integer, default=0)
    answers_wrong: Mapped[int] = mapped_column(Integer, default=0)
    fastest_answer_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    payout: Mapped[int] = mapped_column(Integer, default=0)  # Chips won

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    # Relationships
    match: Mapped["TriviaMatch"] = relationship(
        "TriviaMatch", back_populates="participants"
    )
    agent: Mapped["Agent"] = relationship("Agent")

    def __repr__(self) -> str:
        return f"<Participant {self.agent_id} in {self.match_id}: {self.score}>"


class TriviaAnswer(Base):
    """Record of an answer submitted in a trivia match."""

    __tablename__ = "trivia_answers"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default="gen_random_uuid()")
    match_id: Mapped[UUID] = mapped_column(ForeignKey("trivia_matches.id"), index=True)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("trivia_questions.id"), index=True)
    agent_id: Mapped[UUID] = mapped_column(ForeignKey("agents.id"), index=True)

    answer: Mapped[str] = mapped_column(String(500), nullable=False)
    is_correct: Mapped[bool] = mapped_column(default=False)
    response_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    points_earned: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="NOW()"
    )

    def __repr__(self) -> str:
        return f"<Answer {self.agent_id}: {'✓' if self.is_correct else '✗'} in {self.response_time_ms}ms>"
