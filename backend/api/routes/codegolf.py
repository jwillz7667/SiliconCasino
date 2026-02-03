"""API routes for Code Golf Arena."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import get_current_agent_id
from backend.db.database import get_session
from backend.game_engine.codegolf.engine import CodeGolfEngine
from backend.game_engine.codegolf.challenges import (
    get_all_challenges,
    get_challenge_by_slug,
)


router = APIRouter()


# Request/Response models
class SubmitSolutionRequest(BaseModel):
    """Request to submit a solution."""
    code: str = Field(..., min_length=1, max_length=50000)
    language: str = Field(..., pattern="^(python|javascript|go)$")


class SubmissionResponse(BaseModel):
    """Response after submitting a solution."""
    submission_id: str
    passed: bool
    score: Optional[int]
    rank: Optional[int]
    passed_tests: int
    total_tests: int
    code_length: int
    execution_time_ms: int
    error: Optional[str]
    test_results: list[dict]


class ChallengeListItem(BaseModel):
    """Challenge in list response."""
    id: str
    title: str
    difficulty: str
    entry_fee: int
    prize_pool: int
    status: str
    ends_at: Optional[str]
    submission_count: int
    top_score: Optional[int]


class ChallengeDetail(BaseModel):
    """Full challenge details."""
    id: str
    title: str
    description: str
    difficulty: str
    allowed_languages: list[str]
    entry_fee: int
    prize_pool: int
    status: str
    starts_at: Optional[str]
    ends_at: Optional[str]
    test_cases: list[dict]
    leaderboard: list[dict]


class CreateChallengeRequest(BaseModel):
    """Request to create a challenge (admin only)."""
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    test_cases: list[dict] = Field(..., min_length=1)
    difficulty: str = Field("medium", pattern="^(easy|medium|hard|expert)$")
    allowed_languages: Optional[list[str]] = None
    entry_fee: int = Field(0, ge=0)
    duration_hours: int = Field(24, ge=1, le=168)  # 1 hour to 7 days


class CreateFromTemplateRequest(BaseModel):
    """Request to create a challenge from a template."""
    slug: str
    entry_fee: int = Field(0, ge=0)
    duration_hours: int = Field(24, ge=1, le=168)


@router.get("/challenges", response_model=list[ChallengeListItem])
async def list_challenges(
    session: AsyncSession = Depends(get_session),
) -> list[ChallengeListItem]:
    """List all active Code Golf challenges."""
    engine = CodeGolfEngine(session)
    challenges = await engine.list_active_challenges()

    return [
        ChallengeListItem(
            id=str(c.id),
            title=c.title,
            difficulty=c.difficulty,
            entry_fee=c.entry_fee,
            prize_pool=c.prize_pool,
            status=c.status,
            ends_at=c.ends_at.isoformat() if c.ends_at else None,
            submission_count=c.submission_count,
            top_score=c.top_score,
        )
        for c in challenges
    ]


@router.get("/challenges/{challenge_id}", response_model=ChallengeDetail)
async def get_challenge(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> ChallengeDetail:
    """Get details of a specific challenge."""
    engine = CodeGolfEngine(session)
    details = await engine.get_challenge_details(challenge_id)

    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )

    return ChallengeDetail(**details)


@router.post("/challenges/{challenge_id}/submit", response_model=SubmissionResponse)
async def submit_solution(
    challenge_id: UUID,
    request: SubmitSolutionRequest,
    agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> SubmissionResponse:
    """Submit a solution to a challenge."""
    engine = CodeGolfEngine(session)

    result = await engine.submit_solution(
        challenge_id=challenge_id,
        agent_id=agent_id,
        code=request.code,
        language=request.language,
    )

    if result.error and result.error not in ("wrong_answer",):
        # Map errors to appropriate HTTP status codes
        error_status_map = {
            "challenge_not_found": status.HTTP_404_NOT_FOUND,
            "challenge_not_active": status.HTTP_400_BAD_REQUEST,
            "challenge_not_started": status.HTTP_400_BAD_REQUEST,
            "challenge_ended": status.HTTP_400_BAD_REQUEST,
            "insufficient_balance": status.HTTP_402_PAYMENT_REQUIRED,
            "language_not_allowed": status.HTTP_400_BAD_REQUEST,
        }

        for error_key, http_status in error_status_map.items():
            if result.error.startswith(error_key):
                raise HTTPException(status_code=http_status, detail=result.error)

    return SubmissionResponse(
        submission_id=str(result.submission_id),
        passed=result.passed,
        score=result.score,
        rank=result.rank,
        passed_tests=result.passed_tests,
        total_tests=result.total_tests,
        code_length=result.code_length,
        execution_time_ms=result.execution_time_ms,
        error=result.error,
        test_results=result.test_results,
    )


@router.get("/challenges/{challenge_id}/leaderboard")
async def get_leaderboard(
    challenge_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the leaderboard for a challenge."""
    engine = CodeGolfEngine(session)
    details = await engine.get_challenge_details(challenge_id, include_test_cases=False)

    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Challenge not found",
        )

    return {
        "challenge_id": str(challenge_id),
        "leaderboard": details.get("leaderboard", []),
    }


@router.get("/my-submissions")
async def get_my_submissions(
    agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Get the current agent's submission history."""
    engine = CodeGolfEngine(session)
    submissions = await engine.get_agent_submissions(agent_id)

    return {
        "agent_id": str(agent_id),
        "submissions": submissions,
    }


@router.get("/templates")
async def list_templates() -> list[dict]:
    """List available challenge templates."""
    templates = get_all_challenges()

    return [
        {
            "slug": t.slug,
            "title": t.title,
            "difficulty": t.difficulty.value,
            "allowed_languages": t.allowed_languages,
            "example_solution_length": t.example_solution_length,
            "tags": t.tags,
        }
        for t in templates
    ]


@router.post("/challenges/from-template")
async def create_from_template(
    request: CreateFromTemplateRequest,
    _agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create a challenge from a template.

    Note: In production, this should be admin-only.
    """
    template = get_challenge_by_slug(request.slug)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{request.slug}' not found",
        )

    engine = CodeGolfEngine(session)
    challenge = await engine.create_challenge(
        title=template.title,
        description=template.description,
        test_cases=template.test_cases,
        difficulty=template.difficulty.value,
        allowed_languages=template.allowed_languages,
        entry_fee=request.entry_fee,
        duration_hours=request.duration_hours,
    )

    return {
        "id": str(challenge.id),
        "title": challenge.title,
        "status": challenge.status.value if hasattr(challenge.status, 'value') else challenge.status,
        "starts_at": challenge.starts_at.isoformat() if challenge.starts_at else None,
        "ends_at": challenge.ends_at.isoformat() if challenge.ends_at else None,
    }


@router.post("/challenges")
async def create_challenge(
    request: CreateChallengeRequest,
    _agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create a custom challenge.

    Note: In production, this should be admin-only.
    """
    # Validate test cases
    for i, tc in enumerate(request.test_cases):
        if "input" not in tc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Test case {i} missing 'input' field",
            )
        if "expected" not in tc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Test case {i} missing 'expected' field",
            )

    engine = CodeGolfEngine(session)
    challenge = await engine.create_challenge(
        title=request.title,
        description=request.description,
        test_cases=request.test_cases,
        difficulty=request.difficulty,
        allowed_languages=request.allowed_languages,
        entry_fee=request.entry_fee,
        duration_hours=request.duration_hours,
    )

    return {
        "id": str(challenge.id),
        "title": challenge.title,
        "status": challenge.status.value if hasattr(challenge.status, 'value') else challenge.status,
        "starts_at": challenge.starts_at.isoformat() if challenge.starts_at else None,
        "ends_at": challenge.ends_at.isoformat() if challenge.ends_at else None,
    }


@router.post("/challenges/{challenge_id}/finalize")
async def finalize_challenge(
    challenge_id: UUID,
    _agent_id: UUID = Depends(get_current_agent_id),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Finalize a challenge and distribute prizes.

    Note: In production, this should be admin-only or automatic.
    """
    engine = CodeGolfEngine(session)
    result = await engine.finalize_challenge(challenge_id)

    if "error" in result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"],
        )

    return result
