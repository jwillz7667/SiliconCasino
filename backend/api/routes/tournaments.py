"""API routes for tournament management."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import InsufficientFundsError
from backend.core.security import get_current_agent
from backend.db.database import get_session
from backend.db.models.agent import Agent
from backend.db.models.tournament import TournamentFormat, TournamentStatus
from backend.services.tournament_service import (
    TournamentError,
    TournamentService,
    get_tournament_service,
)

router = APIRouter()


class CreateTournamentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    format: str = Field(default="freezeout")
    buy_in: int = Field(..., gt=0)
    rake: int = Field(default=0, ge=0)
    starting_chips: int = Field(default=10000, gt=0)
    min_players: int = Field(default=2, ge=2)
    max_players: int = Field(default=100, ge=2)
    level_duration_minutes: int = Field(default=15, ge=1)
    scheduled_start_at: datetime | None = None


class TournamentResponse(BaseModel):
    id: str
    name: str
    description: str | None
    format: str
    buy_in: int
    rake: int
    starting_chips: int
    min_players: int
    max_players: int
    status: str
    scheduled_start_at: str | None
    started_at: str | None
    completed_at: str | None
    total_prize_pool: int
    entries_count: int
    created_at: str


class EntryResponse(BaseModel):
    id: str
    tournament_id: str
    agent_id: str
    is_active: bool
    is_eliminated: bool
    finish_position: int | None
    current_chips: int
    rebuys: int
    registered_at: str


class LeaderboardEntry(BaseModel):
    rank: int
    agent_id: str
    chips: int
    is_eliminated: bool
    finish_position: int | None


@router.get("", response_model=list[TournamentResponse])
async def list_tournaments(
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """List all tournaments."""
    service = await get_tournament_service(session)

    status = None
    if status_filter:
        try:
            status = TournamentStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}",
            )

    tournaments = await service.list_tournaments(status, limit, offset)
    return [t.to_dict() for t in tournaments]


@router.post("", response_model=TournamentResponse)
async def create_tournament(
    request: CreateTournamentRequest,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """
    Create a new tournament.

    In production, this should require admin authentication.
    """
    try:
        format_enum = TournamentFormat(request.format)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format: {request.format}",
        )

    service = await get_tournament_service(session)

    try:
        tournament = await service.create_tournament(
            name=request.name,
            description=request.description,
            format=format_enum,
            buy_in=request.buy_in,
            rake=request.rake,
            starting_chips=request.starting_chips,
            min_players=request.min_players,
            max_players=request.max_players,
            level_duration_minutes=request.level_duration_minutes,
            scheduled_start_at=request.scheduled_start_at,
        )
        await session.commit()
        return tournament.to_dict()
    except TournamentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/{tournament_id}", response_model=TournamentResponse)
async def get_tournament(
    tournament_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Get tournament details."""
    service = await get_tournament_service(session)
    tournament = await service.get_tournament(tournament_id)

    if not tournament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tournament not found",
        )

    return tournament.to_dict()


@router.post("/{tournament_id}/register", response_model=EntryResponse)
async def register_for_tournament(
    tournament_id: UUID,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Register for a tournament."""
    service = await get_tournament_service(session)

    try:
        entry = await service.register(tournament_id, agent.id)
        await session.commit()
        return entry.to_dict()
    except InsufficientFundsError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except TournamentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{tournament_id}/unregister")
async def unregister_from_tournament(
    tournament_id: UUID,
    agent: Agent = Depends(get_current_agent),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Unregister from a tournament (only before it starts)."""
    service = await get_tournament_service(session)

    try:
        await service.unregister(tournament_id, agent.id)
        await session.commit()
        return {"message": "Successfully unregistered"}
    except TournamentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/{tournament_id}/leaderboard", response_model=list[LeaderboardEntry])
async def get_leaderboard(
    tournament_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    """Get tournament leaderboard."""
    service = await get_tournament_service(session)

    try:
        return await service.get_leaderboard(tournament_id)
    except TournamentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/{tournament_id}/blinds")
async def get_current_blinds(
    tournament_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    """Get current blind levels for a tournament."""
    service = await get_tournament_service(session)

    try:
        return await service.get_current_blinds(tournament_id)
    except TournamentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# ==================== Admin Endpoints ====================


@router.post("/{tournament_id}/start", response_model=TournamentResponse)
async def start_tournament(
    tournament_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """
    Start a tournament (admin only).

    In production, this should require admin authentication.
    """
    service = await get_tournament_service(session)

    try:
        tournament = await service.start_tournament(tournament_id)
        await session.commit()
        return tournament.to_dict()
    except TournamentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{tournament_id}/advance-level", response_model=TournamentResponse)
async def advance_blind_level(
    tournament_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """
    Advance tournament to next blind level (admin only).

    In production, this should require admin authentication.
    """
    service = await get_tournament_service(session)

    try:
        tournament = await service.advance_blind_level(tournament_id)
        await session.commit()
        return tournament.to_dict()
    except TournamentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/{tournament_id}/cancel", response_model=TournamentResponse)
async def cancel_tournament(
    tournament_id: UUID,
    reason: str = "Cancelled by admin",
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """
    Cancel a tournament and refund entries (admin only).

    In production, this should require admin authentication.
    """
    service = await get_tournament_service(session)

    try:
        tournament = await service.cancel_tournament(tournament_id, reason)
        await session.commit()
        return tournament.to_dict()
    except TournamentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
