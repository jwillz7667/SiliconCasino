"""Code Golf Arena game engine.

Manages challenge lifecycle, submissions, and prize distribution.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.core.metrics import record_rake
from backend.db.models.codegolf import (
    CodeGolfChallenge,
    CodeGolfSubmission,
    CodeGolfLeaderboard,
    ChallengeStatus,
)
from backend.db.models.wallet import Wallet
from backend.game_engine.codegolf.judge import judge_submission, JudgeResult
from backend.game_engine.codegolf.sandbox import Language


@dataclass
class SubmissionResult:
    """Result of submitting a solution."""
    submission_id: UUID
    passed: bool
    score: Optional[int]  # Code length if passed
    rank: Optional[int]
    passed_tests: int
    total_tests: int
    test_results: list[dict]
    code_length: int
    execution_time_ms: int
    error: Optional[str] = None


@dataclass
class ChallengeInfo:
    """Information about a challenge."""
    id: UUID
    title: str
    description: str
    difficulty: str
    allowed_languages: list[str]
    entry_fee: int
    prize_pool: int
    status: str
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]
    submission_count: int
    top_score: Optional[int]


class CodeGolfEngine:
    """Engine for managing Code Golf challenges and competitions.

    Features:
    - Challenge lifecycle management
    - Submission judging and scoring
    - Leaderboard tracking
    - Prize distribution
    - Entry fee and rake handling
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_challenge(self, challenge_id: UUID) -> Optional[CodeGolfChallenge]:
        """Get a challenge by ID."""
        return await self.session.get(CodeGolfChallenge, challenge_id)

    async def list_active_challenges(self) -> list[ChallengeInfo]:
        """List all active challenges."""
        now = datetime.now(timezone.utc)

        stmt = select(CodeGolfChallenge).where(
            and_(
                CodeGolfChallenge.status == ChallengeStatus.ACTIVE,
                CodeGolfChallenge.starts_at <= now,
                CodeGolfChallenge.ends_at > now,
            )
        ).order_by(CodeGolfChallenge.ends_at)

        result = await self.session.execute(stmt)
        challenges = result.scalars().all()

        infos = []
        for challenge in challenges:
            # Get submission count
            count_stmt = select(func.count()).select_from(CodeGolfSubmission).where(
                CodeGolfSubmission.challenge_id == challenge.id
            )
            count_result = await self.session.execute(count_stmt)
            submission_count = count_result.scalar() or 0

            # Get top score
            top_stmt = select(func.min(CodeGolfSubmission.score)).where(
                and_(
                    CodeGolfSubmission.challenge_id == challenge.id,
                    CodeGolfSubmission.score.isnot(None),
                )
            )
            top_result = await self.session.execute(top_stmt)
            top_score = top_result.scalar()

            infos.append(ChallengeInfo(
                id=challenge.id,
                title=challenge.title,
                description=challenge.description,
                difficulty=challenge.difficulty,
                allowed_languages=challenge.allowed_languages,
                entry_fee=challenge.entry_fee,
                prize_pool=challenge.prize_pool,
                status=challenge.status.value,
                starts_at=challenge.starts_at,
                ends_at=challenge.ends_at,
                submission_count=submission_count,
                top_score=top_score,
            ))

        return infos

    async def get_challenge_details(
        self,
        challenge_id: UUID,
        include_test_cases: bool = True,
    ) -> Optional[dict]:
        """Get full challenge details including test cases."""
        challenge = await self.get_challenge(challenge_id)
        if not challenge:
            return None

        # Get leaderboard
        leaderboard_stmt = select(CodeGolfLeaderboard).where(
            CodeGolfLeaderboard.challenge_id == challenge_id
        ).order_by(CodeGolfLeaderboard.rank).limit(10)

        result = await self.session.execute(leaderboard_stmt)
        leaderboard = result.scalars().all()

        # Filter test cases - only show non-hidden ones
        test_cases = []
        if include_test_cases:
            for tc in challenge.test_cases:
                if not tc.get("is_hidden", False):
                    test_cases.append({
                        "input": tc.get("input", ""),
                        "expected": tc.get("expected", ""),
                        "description": tc.get("description"),
                    })

        return {
            "id": str(challenge.id),
            "title": challenge.title,
            "description": challenge.description,
            "difficulty": challenge.difficulty,
            "allowed_languages": challenge.allowed_languages,
            "entry_fee": challenge.entry_fee,
            "prize_pool": challenge.prize_pool,
            "status": challenge.status.value,
            "starts_at": challenge.starts_at.isoformat() if challenge.starts_at else None,
            "ends_at": challenge.ends_at.isoformat() if challenge.ends_at else None,
            "test_cases": test_cases,
            "leaderboard": [
                {
                    "rank": entry.rank,
                    "agent_id": str(entry.agent_id),
                    "code_length": entry.code_length,
                }
                for entry in leaderboard
            ],
        }

    async def submit_solution(
        self,
        challenge_id: UUID,
        agent_id: UUID,
        code: str,
        language: str,
    ) -> SubmissionResult:
        """Submit a solution to a challenge.

        Args:
            challenge_id: Challenge to submit to
            agent_id: Submitting agent
            code: Solution source code
            language: Programming language

        Returns:
            SubmissionResult with judging outcome
        """
        # Get challenge
        challenge = await self.get_challenge(challenge_id)
        if not challenge:
            return SubmissionResult(
                submission_id=UUID(int=0),
                passed=False,
                score=None,
                rank=None,
                passed_tests=0,
                total_tests=0,
                test_results=[],
                code_length=len(code.encode("utf-8")),
                execution_time_ms=0,
                error="challenge_not_found",
            )

        # Verify challenge is active
        now = datetime.now(timezone.utc)
        if challenge.status != ChallengeStatus.ACTIVE:
            return SubmissionResult(
                submission_id=UUID(int=0),
                passed=False,
                score=None,
                rank=None,
                passed_tests=0,
                total_tests=0,
                test_results=[],
                code_length=len(code.encode("utf-8")),
                execution_time_ms=0,
                error="challenge_not_active",
            )

        if challenge.starts_at and now < challenge.starts_at:
            return SubmissionResult(
                submission_id=UUID(int=0),
                passed=False,
                score=None,
                rank=None,
                passed_tests=0,
                total_tests=0,
                test_results=[],
                code_length=len(code.encode("utf-8")),
                execution_time_ms=0,
                error="challenge_not_started",
            )

        if challenge.ends_at and now >= challenge.ends_at:
            return SubmissionResult(
                submission_id=UUID(int=0),
                passed=False,
                score=None,
                rank=None,
                passed_tests=0,
                total_tests=0,
                test_results=[],
                code_length=len(code.encode("utf-8")),
                execution_time_ms=0,
                error="challenge_ended",
            )

        # Verify language is allowed
        if language.lower() not in [l.lower() for l in challenge.allowed_languages]:
            return SubmissionResult(
                submission_id=UUID(int=0),
                passed=False,
                score=None,
                rank=None,
                passed_tests=0,
                total_tests=0,
                test_results=[],
                code_length=len(code.encode("utf-8")),
                execution_time_ms=0,
                error=f"language_not_allowed: {language}",
            )

        # Check for existing submission
        existing_stmt = select(CodeGolfSubmission).where(
            and_(
                CodeGolfSubmission.challenge_id == challenge_id,
                CodeGolfSubmission.agent_id == agent_id,
            )
        )
        result = await self.session.execute(existing_stmt)
        existing = result.scalar_one_or_none()

        # Handle entry fee for first submission
        if not existing and challenge.entry_fee > 0:
            wallet = await self._get_wallet(agent_id)
            if not wallet or wallet.balance < challenge.entry_fee:
                return SubmissionResult(
                    submission_id=UUID(int=0),
                    passed=False,
                    score=None,
                    rank=None,
                    passed_tests=0,
                    total_tests=0,
                    test_results=[],
                    code_length=len(code.encode("utf-8")),
                    execution_time_ms=0,
                    error="insufficient_balance",
                )

            # Deduct entry fee
            wallet.balance -= challenge.entry_fee

            # Add to prize pool (90%) and rake (10%)
            rake = int(challenge.entry_fee * 0.10)
            challenge.prize_pool += challenge.entry_fee - rake
            record_rake("codegolf", rake)

        # Judge the submission
        judge_result: JudgeResult = await judge_submission(
            code=code,
            language=language,
            test_cases=challenge.test_cases,
            challenge_id=challenge_id,
        )

        # Create or update submission
        if existing:
            submission = existing
            # Only update if new score is better (lower)
            if judge_result.passed:
                if submission.score is None or judge_result.score < submission.score:
                    submission.code = code
                    submission.language = language
                    submission.code_length = judge_result.code_length
                    submission.passed_tests = judge_result.passed_tests
                    submission.total_tests = judge_result.total_tests
                    submission.execution_time_ms = judge_result.total_execution_time_ms
                    submission.score = judge_result.score
                    submission.status = "passed"
                    submission.submitted_at = now
        else:
            submission = CodeGolfSubmission(
                challenge_id=challenge_id,
                agent_id=agent_id,
                language=language,
                code=code,
                code_length=judge_result.code_length,
                passed_tests=judge_result.passed_tests,
                total_tests=judge_result.total_tests,
                execution_time_ms=judge_result.total_execution_time_ms,
                score=judge_result.score,
                status="passed" if judge_result.passed else "failed",
                submitted_at=now,
            )
            self.session.add(submission)

        await self.session.flush()

        # Update leaderboard if passed
        rank = None
        if judge_result.passed:
            rank = await self._update_leaderboard(challenge_id, agent_id, judge_result.score)

        await self.session.commit()

        return SubmissionResult(
            submission_id=submission.id,
            passed=judge_result.passed,
            score=judge_result.score,
            rank=rank,
            passed_tests=judge_result.passed_tests,
            total_tests=judge_result.total_tests,
            test_results=[
                {
                    "passed": tr.passed,
                    "input": tr.input,
                    "expected": tr.expected,
                    "actual": tr.actual,
                    "execution_time_ms": tr.execution_time_ms,
                    "error": tr.error,
                }
                for tr in judge_result.test_results
            ],
            code_length=judge_result.code_length,
            execution_time_ms=judge_result.total_execution_time_ms,
            error=judge_result.error,
        )

    async def _get_wallet(self, agent_id: UUID) -> Optional[Wallet]:
        """Get agent's wallet."""
        stmt = select(Wallet).where(Wallet.agent_id == agent_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _update_leaderboard(
        self,
        challenge_id: UUID,
        agent_id: UUID,
        score: int,
    ) -> int:
        """Update leaderboard with new score.

        Returns the agent's new rank.
        """
        # Get or create leaderboard entry
        stmt = select(CodeGolfLeaderboard).where(
            and_(
                CodeGolfLeaderboard.challenge_id == challenge_id,
                CodeGolfLeaderboard.agent_id == agent_id,
            )
        )
        result = await self.session.execute(stmt)
        entry = result.scalar_one_or_none()

        if entry:
            # Only update if better score
            if score < entry.code_length:
                entry.code_length = score
        else:
            entry = CodeGolfLeaderboard(
                challenge_id=challenge_id,
                agent_id=agent_id,
                code_length=score,
                rank=0,  # Will be recalculated
            )
            self.session.add(entry)

        await self.session.flush()

        # Recalculate all ranks for this challenge
        all_entries_stmt = select(CodeGolfLeaderboard).where(
            CodeGolfLeaderboard.challenge_id == challenge_id
        ).order_by(CodeGolfLeaderboard.code_length)

        result = await self.session.execute(all_entries_stmt)
        all_entries = result.scalars().all()

        current_rank = 0
        agent_rank = 0
        for i, e in enumerate(all_entries, 1):
            e.rank = i
            if e.agent_id == agent_id:
                agent_rank = i

        return agent_rank

    async def finalize_challenge(self, challenge_id: UUID) -> dict:
        """Finalize a challenge and distribute prizes.

        Called when a challenge ends. Distributes prize pool to top finishers.

        Returns:
            Dict with finalization results
        """
        challenge = await self.get_challenge(challenge_id)
        if not challenge:
            return {"error": "challenge_not_found"}

        if challenge.status == ChallengeStatus.COMPLETED:
            return {"error": "already_finalized"}

        # Get final leaderboard
        stmt = select(CodeGolfLeaderboard).where(
            CodeGolfLeaderboard.challenge_id == challenge_id
        ).order_by(CodeGolfLeaderboard.rank).limit(10)

        result = await self.session.execute(stmt)
        leaderboard = result.scalars().all()

        if not leaderboard:
            challenge.status = ChallengeStatus.COMPLETED
            await self.session.commit()
            return {"message": "no_submissions", "prizes": []}

        # Prize distribution (50% / 30% / 20% for top 3)
        prize_pool = challenge.prize_pool
        prize_structure = [0.50, 0.30, 0.20]  # Top 3 percentages

        prizes = []
        for i, entry in enumerate(leaderboard[:3]):
            if i < len(prize_structure):
                prize_amount = int(prize_pool * prize_structure[i])
                entry.prize_amount = prize_amount

                # Credit winner's wallet
                wallet = await self._get_wallet(entry.agent_id)
                if wallet:
                    wallet.balance += prize_amount

                prizes.append({
                    "rank": entry.rank,
                    "agent_id": str(entry.agent_id),
                    "prize_amount": prize_amount,
                    "code_length": entry.code_length,
                })

        challenge.status = ChallengeStatus.COMPLETED
        await self.session.commit()

        return {
            "message": "finalized",
            "challenge_id": str(challenge_id),
            "prize_pool": prize_pool,
            "prizes": prizes,
        }

    async def create_challenge(
        self,
        title: str,
        description: str,
        test_cases: list[dict],
        difficulty: str = "medium",
        allowed_languages: Optional[list[str]] = None,
        entry_fee: int = 0,
        duration_hours: int = 24,
        starts_at: Optional[datetime] = None,
    ) -> CodeGolfChallenge:
        """Create a new challenge.

        Args:
            title: Challenge title
            description: Challenge description with examples
            test_cases: List of {"input": "", "expected": "", "is_hidden": bool}
            difficulty: easy/medium/hard/expert
            allowed_languages: Allowed languages (default: all)
            entry_fee: Entry fee in chips (0 for free)
            duration_hours: Challenge duration
            starts_at: Start time (default: now)

        Returns:
            Created challenge
        """
        if allowed_languages is None:
            allowed_languages = settings.codegolf_allowed_languages

        if starts_at is None:
            starts_at = datetime.now(timezone.utc)

        ends_at = starts_at + timedelta(hours=duration_hours)

        challenge = CodeGolfChallenge(
            title=title,
            description=description,
            test_cases=test_cases,
            difficulty=difficulty,
            allowed_languages=allowed_languages,
            entry_fee=entry_fee,
            prize_pool=0,
            status=ChallengeStatus.ACTIVE,
            starts_at=starts_at,
            ends_at=ends_at,
        )

        self.session.add(challenge)
        await self.session.commit()

        return challenge

    async def get_agent_submissions(
        self,
        agent_id: UUID,
        limit: int = 20,
    ) -> list[dict]:
        """Get an agent's submission history."""
        stmt = select(CodeGolfSubmission).where(
            CodeGolfSubmission.agent_id == agent_id
        ).order_by(CodeGolfSubmission.submitted_at.desc()).limit(limit)

        result = await self.session.execute(stmt)
        submissions = result.scalars().all()

        return [
            {
                "id": str(s.id),
                "challenge_id": str(s.challenge_id),
                "language": s.language,
                "code_length": s.code_length,
                "passed_tests": s.passed_tests,
                "total_tests": s.total_tests,
                "score": s.score,
                "status": s.status,
                "submitted_at": s.submitted_at.isoformat(),
            }
            for s in submissions
        ]
