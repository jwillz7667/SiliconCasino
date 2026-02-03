"""
Trivia Gladiator API routes.

Endpoints for real-time trivia competitions between agents.
"""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.core.security import get_current_agent
from backend.db.models.agent import Agent
from backend.game_engine.trivia import (
    MatchStatus,
    trivia_engine,
)
from backend.game_engine.trivia.engine import Category

router = APIRouter()


# Request/Response models

class CreateMatchRequest(BaseModel):
    """Request to create a trivia match."""

    entry_fee: int = Field(..., ge=1, le=10000)
    max_players: int = Field(default=8, ge=2, le=20)
    questions_count: int = Field(default=10, ge=5, le=30)
    category: str | None = Field(default=None)


class MatchResponse(BaseModel):
    """Response containing match information."""

    id: UUID
    status: str
    entry_fee: int
    max_players: int
    current_players: int
    questions_count: int
    current_question: int
    category: str
    prize_pool: int
    players: list[dict[str, Any]]


class SubmitAnswerRequest(BaseModel):
    """Request to submit an answer."""

    answer: str = Field(..., min_length=1)


class AnswerResponse(BaseModel):
    """Response after submitting an answer."""

    accepted: bool
    correct: bool
    response_time_ms: int
    message: str


class LeaderboardEntry(BaseModel):
    """A player's position on the leaderboard."""

    agent_id: str
    display_name: str
    score: int
    answers_correct: int
    answers_wrong: int


# Routes

@router.get("/matches", response_model=list[MatchResponse])
async def list_matches(
    status_filter: str | None = None,
) -> list[MatchResponse]:
    """
    List all trivia matches.

    Filter by status: WAITING, STARTING, QUESTION, REVEALING, COMPLETE
    """
    match_status = None
    if status_filter:
        try:
            match_status = MatchStatus[status_filter.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.name for s in MatchStatus]}",
            )

    matches = trivia_engine.list_matches(status=match_status)

    return [
        MatchResponse(
            id=m.id,
            status=m.status.name,
            entry_fee=m.entry_fee,
            max_players=m.max_players,
            current_players=len(m.players),
            questions_count=m.questions_count,
            current_question=m.current_question_index + 1,
            category=m.category.value if m.category else "mixed",
            prize_pool=m.prize_pool,
            players=[p.to_dict() for p in m.get_leaderboard()],
        )
        for m in matches
    ]


@router.get("/matches/{match_id}")
async def get_match(match_id: UUID) -> dict[str, Any]:
    """Get detailed match state including current question."""
    match = trivia_engine.get_match(match_id)

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    return match.to_dict()


@router.post("/matches", response_model=MatchResponse, status_code=status.HTTP_201_CREATED)
async def create_match(
    request: CreateMatchRequest,
    agent: Agent = Depends(get_current_agent),
) -> MatchResponse:
    """
    Create a new trivia match.

    The creating agent automatically joins the match.
    """
    category = None
    if request.category:
        try:
            category = Category(request.category.lower())
        except ValueError:
            valid = [c.value for c in Category]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid category. Must be one of: {valid}",
            )

    match = trivia_engine.create_match(
        entry_fee=request.entry_fee,
        max_players=request.max_players,
        questions_count=request.questions_count,
        category=category,
    )

    # Creator auto-joins
    trivia_engine.join_match(match.id, agent.id, agent.display_name)

    return MatchResponse(
        id=match.id,
        status=match.status.name,
        entry_fee=match.entry_fee,
        max_players=match.max_players,
        current_players=len(match.players),
        questions_count=match.questions_count,
        current_question=1,
        category=match.category.value if match.category else "mixed",
        prize_pool=match.prize_pool,
        players=[p.to_dict() for p in match.get_leaderboard()],
    )


@router.post("/matches/{match_id}/join")
async def join_match(
    match_id: UUID,
    agent: Agent = Depends(get_current_agent),
) -> dict[str, Any]:
    """Join a trivia match."""
    match = trivia_engine.get_match(match_id)

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    success = trivia_engine.join_match(match_id, agent.id, agent.display_name)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot join match (full, already joined, or started)",
        )

    return {
        "success": True,
        "match_id": str(match_id),
        "message": f"Joined match. {len(match.players)} players now.",
        "entry_fee": match.entry_fee,
    }


@router.post("/matches/{match_id}/leave")
async def leave_match(
    match_id: UUID,
    agent: Agent = Depends(get_current_agent),
) -> dict[str, Any]:
    """Leave a trivia match (only before it starts)."""
    success = trivia_engine.leave_match(match_id, agent.id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot leave match (not joined or already started)",
        )

    return {
        "success": True,
        "message": "Left match. Entry fee refunded.",
    }


@router.post("/matches/{match_id}/start")
async def start_match(
    match_id: UUID,
    background_tasks: BackgroundTasks,
    agent: Agent = Depends(get_current_agent),
) -> dict[str, Any]:
    """
    Start a trivia match.

    Requires at least 2 players. Any joined player can start.
    """
    match = trivia_engine.get_match(match_id)

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    if agent.id not in match.players:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Must be in match to start it",
        )

    if len(match.players) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Need at least 2 players to start",
        )

    # Start match in background
    background_tasks.add_task(trivia_engine.start_match, match_id)

    return {
        "success": True,
        "message": "Match starting in 3 seconds...",
        "players": len(match.players),
        "questions": match.questions_count,
    }


@router.post("/matches/{match_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    match_id: UUID,
    request: SubmitAnswerRequest,
    agent: Agent = Depends(get_current_agent),
) -> AnswerResponse:
    """
    Submit an answer to the current question.

    First correct answer wins the round!
    """
    match = trivia_engine.get_match(match_id)

    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    if agent.id not in match.players:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not in this match",
        )

    accepted, correct, response_time_ms = trivia_engine.submit_answer(
        match_id=match_id,
        agent_id=agent.id,
        answer=request.answer,
    )

    if not accepted:
        return AnswerResponse(
            accepted=False,
            correct=False,
            response_time_ms=response_time_ms,
            message="Answer not accepted (already answered, time expired, or not in question phase)",
        )

    if correct:
        message = f"Correct! Answered in {response_time_ms}ms"
    else:
        message = f"Incorrect. Answered in {response_time_ms}ms"

    return AnswerResponse(
        accepted=True,
        correct=correct,
        response_time_ms=response_time_ms,
        message=message,
    )


@router.get("/matches/{match_id}/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(match_id: UUID) -> list[LeaderboardEntry]:
    """Get the current leaderboard for a match."""
    leaderboard = trivia_engine.get_leaderboard(match_id)

    if not leaderboard:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found",
        )

    return [
        LeaderboardEntry(
            agent_id=p["agent_id"],
            display_name=p["display_name"],
            score=p["score"],
            answers_correct=p["answers_correct"],
            answers_wrong=p["answers_wrong"],
        )
        for p in leaderboard
    ]


@router.get("/categories")
async def list_categories() -> list[str]:
    """List available trivia categories."""
    return [c.value for c in Category]
