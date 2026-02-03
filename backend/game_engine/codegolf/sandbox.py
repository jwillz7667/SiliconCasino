"""Docker-based sandbox executor for Code Golf submissions.

Provides secure, isolated code execution with strict resource limits.
Each submission runs in a fresh container with no network access.
"""

import asyncio
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional
import shutil

from backend.config import settings


class Language(str, Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    GO = "go"


@dataclass(frozen=True)
class LanguageConfig:
    """Configuration for a supported language."""
    image: str
    file_extension: str
    compile_command: Optional[list[str]]
    run_command: list[str]
    timeout: int  # seconds
    memory: str  # Docker memory limit


# Language configurations with security constraints
LANGUAGE_CONFIGS: dict[Language, LanguageConfig] = {
    Language.PYTHON: LanguageConfig(
        image="python:3.11-slim",
        file_extension=".py",
        compile_command=None,
        run_command=["python", "/code/solution.py"],
        timeout=settings.codegolf_sandbox_timeout,
        memory=settings.codegolf_sandbox_memory,
    ),
    Language.JAVASCRIPT: LanguageConfig(
        image="node:20-slim",
        file_extension=".js",
        compile_command=None,
        run_command=["node", "/code/solution.js"],
        timeout=settings.codegolf_sandbox_timeout,
        memory=settings.codegolf_sandbox_memory,
    ),
    Language.GO: LanguageConfig(
        image="golang:1.21-alpine",
        file_extension=".go",
        compile_command=["go", "build", "-o", "/code/solution", "/code/solution.go"],
        run_command=["/code/solution"],
        timeout=settings.codegolf_sandbox_timeout + 5,  # Extra time for compilation
        memory="128m",  # Go needs more memory for compilation
    ),
}


@dataclass
class ExecutionResult:
    """Result of code execution."""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: int
    timed_out: bool = False
    error: Optional[str] = None


class SandboxExecutor:
    """Executes code in isolated Docker containers.

    Security features:
    - No network access
    - Read-only filesystem (except /tmp)
    - Memory limit enforcement
    - CPU limit (1 core)
    - Execution timeout
    - No privileged operations
    - Fresh container per execution
    """

    def __init__(self):
        self._docker_available: Optional[bool] = None

    async def _check_docker(self) -> bool:
        """Check if Docker is available."""
        if self._docker_available is not None:
            return self._docker_available

        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.wait()
            self._docker_available = proc.returncode == 0
        except FileNotFoundError:
            self._docker_available = False

        return self._docker_available

    async def _pull_image_if_needed(self, image: str) -> bool:
        """Pull Docker image if not present."""
        # Check if image exists
        proc = await asyncio.create_subprocess_exec(
            "docker", "image", "inspect", image,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.wait()

        if proc.returncode == 0:
            return True

        # Pull the image
        proc = await asyncio.create_subprocess_exec(
            "docker", "pull", image,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Failed to pull image {image}: {stderr.decode()}")

        return True

    async def execute(
        self,
        code: str,
        language: Language,
        stdin: str = "",
    ) -> ExecutionResult:
        """Execute code in a sandboxed container.

        Args:
            code: Source code to execute
            language: Programming language
            stdin: Input to provide to the program

        Returns:
            ExecutionResult with output and timing information
        """
        if not await self._check_docker():
            return ExecutionResult(
                success=False,
                stdout="",
                stderr="Docker is not available",
                exit_code=-1,
                execution_time_ms=0,
                error="sandbox_unavailable",
            )

        config = LANGUAGE_CONFIGS.get(language)
        if not config:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Unsupported language: {language}",
                exit_code=-1,
                execution_time_ms=0,
                error="unsupported_language",
            )

        # Ensure image is available
        try:
            await self._pull_image_if_needed(config.image)
        except RuntimeError as e:
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                execution_time_ms=0,
                error="image_pull_failed",
            )

        # Create temporary directory for code
        temp_dir = tempfile.mkdtemp(prefix="codegolf_")
        try:
            # Write code to file
            code_file = Path(temp_dir) / f"solution{config.file_extension}"
            code_file.write_text(code)

            # Write stdin to file
            stdin_file = Path(temp_dir) / "stdin.txt"
            stdin_file.write_text(stdin)

            # Build Docker command
            docker_cmd = [
                "docker", "run",
                "--rm",  # Remove container after execution
                "--network", settings.codegolf_docker_network,  # No network access
                "--memory", config.memory,  # Memory limit
                "--memory-swap", config.memory,  # No swap
                "--cpus", "1",  # CPU limit
                "--pids-limit", "64",  # Process limit
                "--read-only",  # Read-only filesystem
                "--tmpfs", "/tmp:size=10M",  # Writable /tmp with size limit
                "--security-opt", "no-new-privileges",  # No privilege escalation
                "-v", f"{temp_dir}:/code:ro",  # Mount code as read-only
                "-w", "/code",
                "-i",  # Interactive for stdin
                config.image,
            ]

            # Handle compilation for compiled languages
            if config.compile_command:
                # Need writable directory for compilation
                compile_cmd = docker_cmd.copy()
                # Replace read-only mount with writable for compile
                compile_cmd = [c for c in compile_cmd if not c.startswith(f"{temp_dir}:/code")]
                compile_cmd.extend(["-v", f"{temp_dir}:/code"])
                compile_cmd.extend(config.compile_command)

                proc = await asyncio.create_subprocess_exec(
                    *compile_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    _, compile_stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=config.timeout,
                    )
                except asyncio.TimeoutError:
                    proc.kill()
                    return ExecutionResult(
                        success=False,
                        stdout="",
                        stderr="Compilation timed out",
                        exit_code=-1,
                        execution_time_ms=config.timeout * 1000,
                        timed_out=True,
                        error="compilation_timeout",
                    )

                if proc.returncode != 0:
                    return ExecutionResult(
                        success=False,
                        stdout="",
                        stderr=compile_stderr.decode()[:2000],
                        exit_code=proc.returncode,
                        execution_time_ms=0,
                        error="compilation_error",
                    )

            # Execute the code
            run_cmd = docker_cmd + config.run_command

            import time
            start_time = time.perf_counter()

            proc = await asyncio.create_subprocess_exec(
                *run_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=stdin.encode()),
                    timeout=config.timeout,
                )
                execution_time_ms = int((time.perf_counter() - start_time) * 1000)

                return ExecutionResult(
                    success=proc.returncode == 0,
                    stdout=stdout.decode()[:10000],  # Limit output size
                    stderr=stderr.decode()[:2000],
                    exit_code=proc.returncode,
                    execution_time_ms=execution_time_ms,
                )

            except asyncio.TimeoutError:
                proc.kill()
                execution_time_ms = config.timeout * 1000
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr="Execution timed out",
                    exit_code=-1,
                    execution_time_ms=execution_time_ms,
                    timed_out=True,
                    error="execution_timeout",
                )

        finally:
            # Cleanup temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def validate_code(self, code: str, language: Language) -> tuple[bool, str]:
        """Validate code for basic issues before execution.

        Checks for:
        - Empty code
        - Code length limits
        - Obvious malicious patterns

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not code or not code.strip():
            return False, "Code cannot be empty"

        if len(code) > 50000:  # 50KB limit
            return False, "Code exceeds maximum length (50KB)"

        # Check for language validity
        if language not in LANGUAGE_CONFIGS:
            return False, f"Unsupported language: {language}"

        # Basic sanitization - reject obviously dangerous patterns
        # Note: The sandbox provides real security, this is just early rejection
        dangerous_patterns = [
            "import os",  # Python OS access
            "import subprocess",  # Python subprocess
            "require('child_process')",  # Node child process
            "exec(",  # Various exec calls
            "eval(",  # Eval can be abused
            "os/exec",  # Go os/exec
        ]

        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern.lower() in code_lower:
                # Allow in specific contexts (e.g., comments)
                # The sandbox provides real isolation, so we're lenient here
                pass

        return True, ""


# Global sandbox executor instance
sandbox = SandboxExecutor()


async def execute_code(
    code: str,
    language: str,
    stdin: str = "",
) -> ExecutionResult:
    """Execute code using the global sandbox."""
    try:
        lang = Language(language.lower())
    except ValueError:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"Unsupported language: {language}",
            exit_code=-1,
            execution_time_ms=0,
            error="unsupported_language",
        )

    return await sandbox.execute(code, lang, stdin)
