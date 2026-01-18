"""Shared types and utilities for benchmark modules.

This module provides utilities (mixins, base classes) for benchmark code.
Result types have been consolidated into kagami.benchmarks.core.result.
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LLMServiceMixin:
    """Benchmark helper for lazy, cached LLM service access."""

    _llm_service: Any | None

    async def _get_llm_service(self) -> Any:
        """Get (and lazily initialize) the global LLM service."""
        if getattr(self, "_llm_service", None) is None:
            try:
                from kagami.core.services.llm import get_llm_service

                self._llm_service = get_llm_service()
                await self._llm_service.initialize()
            except Exception as e:
                logger.error(f"Failed to initialize LLM service: {e}")
                raise
        return self._llm_service


class JSONProblemsMixin:
    """Shared loader for JSON/JSONL 'problems' datasets.

    Expects subclasses to define:
    - self.data_path: Path | None
    - self._problems: list[dict[str, Any]]
    - self._get_sample_problems() -> list[dict[str, Any]]
    """

    data_path: Path | None
    _problems: list[dict[str, Any]]

    def _get_sample_problems(self) -> list[dict[str, Any]]:  # pragma: no cover
        """Get sample problems for testing when no data file is available.

        This is an abstract method that must be implemented by subclasses
        to provide fallback sample data for benchmarking when the main
        dataset file is not available.

        Returns:
            List of sample problem dictionaries

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}._get_sample_problems() must be implemented "
            "to provide fallback sample data when no dataset file is available"
        )

    def load_problems(self, num_samples: int | None = None) -> list[dict[str, Any]]:
        """Load problems from JSON/JSONL dataset (or fall back to samples)."""
        problems: list[dict[str, Any]] = []

        # Try loading from file if path provided
        if self.data_path and self.data_path.exists():
            import json

            with open(self.data_path, encoding="utf-8") as f:
                if self.data_path.suffix == ".jsonl":
                    for line in f:
                        line = line.strip()
                        if line:
                            problems.append(json.loads(line))
                else:
                    problems = json.load(f)

        # If no file, use sample problems for testing
        if not problems:
            problems = self._get_sample_problems()

        if num_samples:
            problems = problems[:num_samples]

        self._problems = problems
        return problems


class CodeProblemsRunnerBase(LLMServiceMixin, JSONProblemsMixin):
    """Shared base for code-generation benchmarks using JSON problems + timeouts."""

    timeout_seconds: int

    def __init__(self, data_path: str | Path | None = None, timeout_seconds: int = 10) -> None:
        self.data_path = Path(data_path) if data_path else None
        self.timeout_seconds = timeout_seconds
        self._llm_service = None
        self._problems = []
