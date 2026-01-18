# SPDX-License-Identifier: MIT
"""Receipt emission wrapper for benchmarks.

Ensures all benchmark runs emit PLAN/EXECUTE/VERIFY receipts
per K OS operational requirements.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class BenchmarkReceiptEmitter:
    """Emitter for benchmark-specific receipts.

    Follows K OS receipt protocol:
    - PLAN: Before execution, declares intent
    - EXECUTE: During/after execution, records mutations
    - VERIFY: After validation, confirms success/failure
    """

    correlation_id: str = ""
    benchmark_name: str = ""
    category: str = ""

    # Timing
    start_time: float = field(default_factory=time.time)

    # Accumulated data
    plan_data: dict[str, Any] = field(default_factory=dict)
    execute_data: dict[str, Any] = field(default_factory=dict)
    verify_data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.correlation_id:
            self.correlation_id = self._generate_correlation_id()

    def _generate_correlation_id(self) -> str:
        """Generate correlation ID from workspace + timestamp."""
        import os

        workspace = os.getcwd()
        timestamp = time.time()
        content = f"benchmark:{self.benchmark_name}:{workspace}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _emit(
        self,
        phase: str,
        data: dict[str, Any],
        status: str = "success",
    ) -> None:
        """Emit a receipt via K OS receipt system."""
        try:
            from kagami.core.receipts import UnifiedReceiptFacade as URF

            URF.emit(
                correlation_id=self.correlation_id,
                event_name=f"benchmark.{phase.lower()}",
                action=f"benchmark.{self.benchmark_name}",
                app="benchmarks",
                event_data={
                    "phase": phase,
                    "benchmark_name": self.benchmark_name,
                    "category": self.category,
                    **data,
                },
                status=status,
            )
            logger.debug(f"Emitted {phase} receipt for {self.benchmark_name}")

        except ImportError:
            logger.debug("UnifiedReceiptFacade not available, skipping receipt emission")
        except Exception as e:
            logger.warning(f"Failed to emit {phase} receipt: {e}")

    def emit_plan(
        self,
        description: str,
        num_samples: int,
        slo: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
    ) -> None:
        """Emit PLAN phase receipt.

        Args:
            description: What the benchmark will do.
            num_samples: Number of samples to run.
            slo: SLO targets if applicable.
            dependencies: Required dependencies.
        """
        self.plan_data = {
            "description": description,
            "num_samples": num_samples,
            "slo": slo,
            "dependencies": dependencies or [],
            "timestamp": time.time(),
        }
        self._emit("PLAN", self.plan_data)

    def emit_execute(
        self,
        samples_completed: int,
        samples_total: int,
        current_score: float | None = None,
        latencies_ms: list[float] | None = None,
    ) -> None:
        """Emit EXECUTE phase receipt.

        Args:
            samples_completed: Number of samples completed.
            samples_total: Total samples to run.
            current_score: Current aggregate score.
            latencies_ms: Latency measurements so far.
        """
        self.execute_data = {
            "samples_completed": samples_completed,
            "samples_total": samples_total,
            "current_score": current_score,
            "latencies_count": len(latencies_ms) if latencies_ms else 0,
            "duration_ms": (time.time() - self.start_time) * 1000,
        }
        self._emit("EXECUTE", self.execute_data)

    def emit_verify(
        self,
        passed: bool,
        score: float,
        slo_met: bool = True,
        validation: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Emit VERIFY phase receipt.

        Args:
            passed: Whether benchmark passed.
            score: Final score.
            slo_met: Whether SLO targets were met.
            validation: Validation details.
            error: Error message if failed.
        """
        self.verify_data = {
            "passed": passed,
            "score": score,
            "slo_met": slo_met,
            "validation": validation or {},
            "error": error,
            "duration_ms": (time.time() - self.start_time) * 1000,
        }

        status = "success" if passed else "failure"
        self._emit("VERIFY", self.verify_data, status=status)


def with_benchmark_receipts(
    benchmark_name: str,
    category: str,
    description: str,
) -> Callable[[F], F]:
    """Decorator to add receipt emission to a benchmark function.

    Wraps a benchmark function to automatically emit PLAN/VERIFY receipts.
    The function should emit EXECUTE receipts internally if needed.

    Usage:
        @with_benchmark_receipts(
            benchmark_name="my_benchmark",
            category="ai.individual",
            description="My benchmark description",
        )
        async def run_my_benchmark(num_samples: int = 10) -> dict:
            ...

    Args:
        benchmark_name: Name of the benchmark.
        category: Benchmark category.
        description: Description for PLAN receipt.

    Returns:
        Decorated function.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def async_wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            emitter = BenchmarkReceiptEmitter(
                benchmark_name=benchmark_name,
                category=category,
            )

            num_samples = kwargs.get("num_samples", 10)

            # PLAN
            emitter.emit_plan(
                description=description,
                num_samples=num_samples,
            )

            try:
                # Execute
                result = await fn(*args, **kwargs)

                # VERIFY
                passed = result.get("status") == "completed" if result else False
                score = result.get("score", 0.0) if result else 0.0

                emitter.emit_verify(
                    passed=passed,
                    score=score,
                    validation={"result_keys": list(result.keys()) if result else []},
                )

                # Add correlation_id to result
                if result:
                    result["correlation_id"] = emitter.correlation_id

                return result  # type: ignore[no-any-return]

            except Exception as e:
                emitter.emit_verify(
                    passed=False,
                    score=0.0,
                    error=str(e),
                )
                raise

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            emitter = BenchmarkReceiptEmitter(
                benchmark_name=benchmark_name,
                category=category,
            )

            num_samples = kwargs.get("num_samples", 10)

            # PLAN
            emitter.emit_plan(
                description=description,
                num_samples=num_samples,
            )

            try:
                # Execute
                result = fn(*args, **kwargs)

                # VERIFY
                passed = result.get("status") == "completed" if result else False
                score = result.get("score", 0.0) if result else 0.0

                emitter.emit_verify(
                    passed=passed,
                    score=score,
                    validation={"result_keys": list(result.keys()) if result else []},
                )

                # Add correlation_id to result
                if result:
                    result["correlation_id"] = emitter.correlation_id

                return result  # type: ignore[no-any-return]

            except Exception as e:
                emitter.emit_verify(
                    passed=False,
                    score=0.0,
                    error=str(e),
                )
                raise

        if asyncio.iscoroutinefunction(fn):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator
