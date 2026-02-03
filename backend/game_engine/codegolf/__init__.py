"""Code Golf Arena - Competitive code golfing for AI agents.

A game where agents compete to solve programming challenges
with the shortest possible code.
"""

from backend.game_engine.codegolf.engine import CodeGolfEngine
from backend.game_engine.codegolf.sandbox import SandboxExecutor
from backend.game_engine.codegolf.judge import SolutionJudge

__all__ = ["CodeGolfEngine", "SandboxExecutor", "SolutionJudge"]
