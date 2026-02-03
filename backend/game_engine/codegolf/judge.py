"""Solution judge for Code Golf submissions.

Validates submissions against test cases and calculates scores.
"""

import asyncio
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from backend.game_engine.codegolf.sandbox import (
    ExecutionResult,
    Language,
    sandbox,
)
from backend.core.metrics import record_codegolf_submission


@dataclass
class TestCase:
    """A single test case for a challenge."""
    input: str
    expected_output: str
    is_hidden: bool = False  # Hidden tests shown only after submission
    description: Optional[str] = None


@dataclass
class TestResult:
    """Result of running a single test case."""
    passed: bool
    input: str
    expected: str
    actual: str
    execution_time_ms: int
    error: Optional[str] = None


@dataclass
class JudgeResult:
    """Complete result of judging a submission."""
    passed: bool  # All tests passed
    passed_tests: int
    total_tests: int
    code_length: int
    total_execution_time_ms: int
    test_results: list[TestResult]
    score: Optional[int]  # Code length if passed, None otherwise
    error: Optional[str] = None


class SolutionJudge:
    """Judges Code Golf submissions against test cases.

    Scoring:
    - Score = code length (in bytes) if all tests pass
    - Lower score is better
    - Failed submissions have no score
    """

    def __init__(self, max_test_time_ms: int = 30000):
        """Initialize judge.

        Args:
            max_test_time_ms: Maximum total time for all tests
        """
        self.max_test_time_ms = max_test_time_ms

    def calculate_code_length(self, code: str) -> int:
        """Calculate code length in bytes.

        For Code Golf, we count bytes, not characters.
        Leading/trailing whitespace on each line is preserved.
        """
        return len(code.encode("utf-8"))

    def normalize_output(self, output: str) -> str:
        """Normalize output for comparison.

        - Strip trailing whitespace from each line
        - Strip trailing newlines
        - Normalize line endings to \\n
        """
        lines = output.replace("\r\n", "\n").split("\n")
        # Strip trailing whitespace from each line
        lines = [line.rstrip() for line in lines]
        # Remove trailing empty lines
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines)

    def compare_output(self, expected: str, actual: str) -> bool:
        """Compare expected and actual output.

        Uses normalized comparison to be lenient about:
        - Trailing whitespace
        - Trailing newlines
        """
        return self.normalize_output(expected) == self.normalize_output(actual)

    async def judge_submission(
        self,
        code: str,
        language: Language,
        test_cases: list[TestCase],
        challenge_id: Optional[UUID] = None,
    ) -> JudgeResult:
        """Judge a submission against all test cases.

        Args:
            code: Source code to judge
            language: Programming language
            test_cases: List of test cases to run
            challenge_id: Optional challenge ID for metrics

        Returns:
            JudgeResult with pass/fail status and details
        """
        code_length = self.calculate_code_length(code)
        test_results: list[TestResult] = []
        total_time = 0
        passed_count = 0

        # Validate code first
        is_valid, validation_error = await sandbox.validate_code(code, language)
        if not is_valid:
            return JudgeResult(
                passed=False,
                passed_tests=0,
                total_tests=len(test_cases),
                code_length=code_length,
                total_execution_time_ms=0,
                test_results=[],
                score=None,
                error=validation_error,
            )

        # Run each test case
        for test_case in test_cases:
            # Check time budget
            if total_time >= self.max_test_time_ms:
                test_results.append(TestResult(
                    passed=False,
                    input=test_case.input if not test_case.is_hidden else "[hidden]",
                    expected=test_case.expected_output if not test_case.is_hidden else "[hidden]",
                    actual="",
                    execution_time_ms=0,
                    error="time_budget_exceeded",
                ))
                continue

            # Execute code with test input
            result: ExecutionResult = await sandbox.execute(
                code=code,
                language=language,
                stdin=test_case.input,
            )

            total_time += result.execution_time_ms

            # Check if output matches expected
            if result.timed_out:
                test_passed = False
                error = "timeout"
            elif result.error:
                test_passed = False
                error = result.error
            elif result.exit_code != 0:
                test_passed = False
                error = f"exit_code_{result.exit_code}"
            else:
                test_passed = self.compare_output(
                    test_case.expected_output,
                    result.stdout,
                )
                error = None if test_passed else "wrong_answer"

            if test_passed:
                passed_count += 1

            test_results.append(TestResult(
                passed=test_passed,
                input=test_case.input if not test_case.is_hidden else "[hidden]",
                expected=test_case.expected_output if not test_case.is_hidden else "[hidden]",
                actual=result.stdout if not test_case.is_hidden else ("[correct]" if test_passed else "[incorrect]"),
                execution_time_ms=result.execution_time_ms,
                error=error,
            ))

        # Calculate final result
        all_passed = passed_count == len(test_cases)
        score = code_length if all_passed else None

        # Record metrics
        if challenge_id:
            result_type = "passed" if all_passed else "failed"
            if any(r.error == "timeout" for r in test_results):
                result_type = "timeout"
            elif any(r.error and r.error not in ("wrong_answer", "timeout") for r in test_results):
                result_type = "error"

            record_codegolf_submission(
                language=language.value,
                result=result_type,
                execution_time=total_time / 1000,
                code_length=code_length,
            )

        return JudgeResult(
            passed=all_passed,
            passed_tests=passed_count,
            total_tests=len(test_cases),
            code_length=code_length,
            total_execution_time_ms=total_time,
            test_results=test_results,
            score=score,
        )

    async def run_single_test(
        self,
        code: str,
        language: Language,
        test_input: str,
    ) -> ExecutionResult:
        """Run code with a single test input (for testing/debugging)."""
        return await sandbox.execute(code, language, test_input)


# Global judge instance
judge = SolutionJudge()


async def judge_submission(
    code: str,
    language: str,
    test_cases: list[dict],
    challenge_id: Optional[UUID] = None,
) -> JudgeResult:
    """Judge a submission using the global judge.

    Args:
        code: Source code
        language: Language name string
        test_cases: List of dicts with 'input' and 'expected' keys
        challenge_id: Optional challenge ID

    Returns:
        JudgeResult
    """
    try:
        lang = Language(language.lower())
    except ValueError:
        return JudgeResult(
            passed=False,
            passed_tests=0,
            total_tests=len(test_cases),
            code_length=len(code.encode("utf-8")),
            total_execution_time_ms=0,
            test_results=[],
            score=None,
            error=f"Unsupported language: {language}",
        )

    cases = [
        TestCase(
            input=tc.get("input", ""),
            expected_output=tc.get("expected", tc.get("expected_output", "")),
            is_hidden=tc.get("is_hidden", False),
            description=tc.get("description"),
        )
        for tc in test_cases
    ]

    return await judge.judge_submission(code, lang, cases, challenge_id)
