# SPDX-License-Identifier: MIT
"""Benchmark Registry - Central catalog of all K OS benchmarks.

Provides:
- Unified registration of all benchmarks
- Metadata (category, description, SLOs, dependencies)
- Discovery and filtering
- Execution orchestration with receipt emission
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from kagami_benchmarks.core.reproducibility import get_reproducibility_info
from kagami_benchmarks.core.result import (
    BenchmarkResult,
    BenchmarkStatus,
    BenchmarkSuite,
)

logger = logging.getLogger(__name__)


class BenchmarkCategory(str, Enum):
    """Categories of benchmarks aligned with K OS architecture."""

    # AI/ML Benchmarks
    AI_INDIVIDUAL = "ai.individual"  # HumanEval, MMLU, GSM8K
    AI_AGENTIC = "ai.agentic"  # SWE-bench, WebArena
    AI_HIVE = "ai.hive"  # Collective intelligence

    # Active Inference Benchmarks
    ACTIVE_INFERENCE = "active_inference"  # EFE, world model

    # System Benchmarks
    SYSTEM_API = "system.api"  # REST latency
    SYSTEM_WS = "system.ws"  # WebSocket latency
    SYSTEM_BOOT = "system.boot"  # Boot time
    SYSTEM_MEMORY = "system.memory"  # Memory profiling

    # Kernel Benchmarks
    KERNEL_SYSCALL = "kernel.syscall"  # Syscall latency

    # Formal Verification
    FORMAL = "formal"  # Z3 proofs, Lean

    # Scientific Validation
    SCIENTIFIC = "scientific"  # Chaos, G2, CBF validation

    # Reasoning
    REASONING = "reasoning"  # ARC-AGI


@dataclass
class SLOSpec:
    """Service Level Objective specification."""

    p95_ms: float  # p95 latency target
    p99_ms: float  # p99 latency target
    min_score: float = 0.0  # Minimum acceptable score
    max_error_rate: float = 0.05  # Maximum error rate (5%)


@dataclass
class BenchmarkSpec:
    """Specification for a registered benchmark."""

    name: str
    category: BenchmarkCategory
    description: str
    runner: Callable[..., dict[str, Any] | Coroutine[Any, Any, dict[str, Any]]]

    # Execution parameters
    is_async: bool = True
    default_samples: int = 10
    timeout_seconds: int = 300

    # SLO
    slo: SLOSpec | None = None

    # Dependencies
    requires_llm: bool = False
    requires_gpu: bool = False
    requires_network: bool = False
    requires_database: bool = False
    requires_redis: bool = False

    # Metadata
    tags: list[str] = field(default_factory=list)
    weight: float = 1.0  # Weight in aggregate scoring
    enabled: bool = True

    def check_dependencies(self) -> tuple[bool, list[str]]:
        """Check if dependencies are satisfied.

        Returns:
            Tuple of (satisfied, missing_dependencies).
        """
        missing = []

        if self.requires_gpu:
            try:
                import torch

                if not torch.cuda.is_available() and not torch.backends.mps.is_available():
                    missing.append("GPU (CUDA or MPS)")
            except ImportError:
                missing.append("PyTorch")

        if self.requires_redis:
            try:
                from kagami.core.caching.redis import RedisClientFactory

                client = RedisClientFactory.get_client(purpose="health_check")  # type: ignore[arg-type]
                client.ping()
            except Exception:
                missing.append("Redis")

        if self.requires_database:
            try:
                from kagami.core.database.connection import (
                    test_connection,  # type: ignore[attr-defined]
                )

                if not test_connection():
                    missing.append("Database")
            except Exception:
                missing.append("Database")

        return len(missing) == 0, missing


class BenchmarkRegistry:
    """Central registry for all K OS benchmarks.

    Singleton pattern ensures consistent registration across the system.
    """

    _instance: BenchmarkRegistry | None = None

    def __new__(cls) -> BenchmarkRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._benchmarks = {}
            cls._instance._initialized = False  # type: ignore[has-type]
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:  # type: ignore[has-type]
            return
        self._benchmarks: dict[str, BenchmarkSpec] = {}
        self._initialized = True

    def register(  # type: ignore[no-untyped-def]
        self,
        name: str,
        category: BenchmarkCategory,
        description: str,
        runner: Callable[..., dict[str, Any] | Coroutine[Any, Any, dict[str, Any]]],
        **kwargs,
    ) -> BenchmarkSpec:
        """Register a benchmark.

        Args:
            name: Unique benchmark name.
            category: Benchmark category.
            description: Human-readable description.
            runner: Function or coroutine that runs the benchmark.
            **kwargs: Additional BenchmarkSpec fields.

        Returns:
            The registered BenchmarkSpec.
        """
        spec = BenchmarkSpec(
            name=name,
            category=category,
            description=description,
            runner=runner,
            **kwargs,
        )
        self._benchmarks[name] = spec
        logger.debug(f"Registered benchmark: {name} ({category.value})")
        return spec

    def get(self, name: str) -> BenchmarkSpec | None:
        """Get a benchmark by name."""
        return self._benchmarks.get(name)

    def list_all(self) -> list[BenchmarkSpec]:
        """List all registered benchmarks."""
        return list(self._benchmarks.values())

    def list_by_category(self, category: BenchmarkCategory) -> list[BenchmarkSpec]:
        """List benchmarks in a category."""
        return [b for b in self._benchmarks.values() if b.category == category]

    def list_by_tag(self, tag: str) -> list[BenchmarkSpec]:
        """List benchmarks with a specific tag."""
        return [b for b in self._benchmarks.values() if tag in b.tags]

    def list_enabled(self) -> list[BenchmarkSpec]:
        """List enabled benchmarks."""
        return [b for b in self._benchmarks.values() if b.enabled]

    def generate_correlation_id(self) -> str:
        """Generate correlation ID for benchmark run."""
        import os

        workspace = os.getcwd()
        timestamp = time.time()
        content = f"benchmark:{workspace}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def run_benchmark(  # type: ignore[no-untyped-def]
        self,
        name: str,
        num_samples: int | None = None,
        correlation_id: str | None = None,
        emit_receipts: bool = True,
        **kwargs,
    ) -> BenchmarkResult:
        """Run a single benchmark with receipt emission.

        Args:
            name: Benchmark name.
            num_samples: Number of samples (None = use default).
            correlation_id: Correlation ID for receipts.
            emit_receipts: Whether to emit PLAN/EXECUTE/VERIFY receipts.
            **kwargs: Additional runner arguments.

        Returns:
            BenchmarkResult with full metadata.
        """
        spec = self.get(name)
        if spec is None:
            return BenchmarkResult(
                task_id=name,
                benchmark_name=name,
                category="unknown",
                passed=False,
                status=BenchmarkStatus.FAILED,
                error=f"Unknown benchmark: {name}",
            )

        correlation_id = correlation_id or self.generate_correlation_id()
        samples = num_samples or spec.default_samples

        # Check dependencies
        deps_ok, missing = spec.check_dependencies()
        if not deps_ok:
            return BenchmarkResult(
                task_id=name,
                benchmark_name=name,
                category=spec.category.value,
                passed=False,
                status=BenchmarkStatus.SKIPPED,
                error=f"Missing dependencies: {', '.join(missing)}",
                correlation_id=correlation_id,
            )

        # Emit PLAN receipt
        if emit_receipts:
            self._emit_receipt(
                correlation_id=correlation_id,
                phase="PLAN",
                benchmark_name=name,
                data={
                    "category": spec.category.value,
                    "samples": samples,
                    "slo": spec.slo.__dict__ if spec.slo else None,
                },
            )

        start_time = time.time()

        try:
            # Execute benchmark
            if spec.is_async:
                if asyncio.iscoroutinefunction(spec.runner):
                    raw_result = await spec.runner(num_samples=samples, **kwargs)
                else:
                    raw_result = await asyncio.to_thread(spec.runner, num_samples=samples, **kwargs)
            else:
                raw_result = spec.runner(num_samples=samples, **kwargs)

            duration_ms = (time.time() - start_time) * 1000

            # Emit EXECUTE receipt
            if emit_receipts:
                self._emit_receipt(
                    correlation_id=correlation_id,
                    phase="EXECUTE",
                    benchmark_name=name,
                    data={
                        "duration_ms": duration_ms,
                        "raw_keys": list(raw_result.keys()) if raw_result else [],
                    },
                )

            # Build result
            score = raw_result.get("score", 0.0) if raw_result else 0.0
            passed = raw_result.get("status") == "completed" if raw_result else False

            # Check SLO if applicable
            slo_passed = True
            if spec.slo and "p95_ms" in (raw_result or {}):
                p95 = raw_result.get("p95_ms", float("inf"))
                p99 = raw_result.get("p99_ms", float("inf"))
                slo_passed = p95 <= spec.slo.p95_ms and p99 <= spec.slo.p99_ms

            result = BenchmarkResult(
                task_id=name,
                benchmark_name=name,
                category=spec.category.value,
                passed=passed and slo_passed,
                score=score,
                status=BenchmarkStatus.COMPLETED,
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                reproducibility_info=get_reproducibility_info(),
                metadata=raw_result or {},
            )

            # Emit VERIFY receipt
            if emit_receipts:
                self._emit_receipt(
                    correlation_id=correlation_id,
                    phase="VERIFY",
                    benchmark_name=name,
                    data={
                        "passed": result.passed,
                        "score": result.score,
                        "slo_passed": slo_passed,
                        "duration_ms": duration_ms,
                    },
                    status="success" if result.passed else "failure",
                )

            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(f"Benchmark {name} failed: {e}")

            if emit_receipts:
                self._emit_receipt(
                    correlation_id=correlation_id,
                    phase="VERIFY",
                    benchmark_name=name,
                    data={"error": str(e), "duration_ms": duration_ms},
                    status="failure",
                )

            return BenchmarkResult(
                task_id=name,
                benchmark_name=name,
                category=spec.category.value,
                passed=False,
                status=BenchmarkStatus.FAILED,
                duration_ms=duration_ms,
                error=str(e),
                correlation_id=correlation_id,
            )

    async def run_suite(  # type: ignore[no-untyped-def]
        self,
        categories: list[BenchmarkCategory] | None = None,
        tags: list[str] | None = None,
        num_samples: int | None = None,
        emit_receipts: bool = True,
        **kwargs,
    ) -> BenchmarkSuite:
        """Run a suite of benchmarks.

        Args:
            categories: Categories to run (None = all).
            tags: Tags to filter by.
            num_samples: Samples per benchmark.
            emit_receipts: Whether to emit receipts.
            **kwargs: Additional runner arguments.

        Returns:
            BenchmarkSuite with all results.
        """
        correlation_id = self.generate_correlation_id()
        start_time = time.time()

        # Filter benchmarks
        benchmarks = self.list_enabled()

        if categories:
            benchmarks = [b for b in benchmarks if b.category in categories]

        if tags:
            benchmarks = [b for b in benchmarks if any(t in b.tags for t in tags)]

        # Create suite
        suite = BenchmarkSuite(
            name="K OS Benchmark Suite",
            description=f"Categories: {[c.value for c in categories] if categories else 'all'}",
            correlation_id=correlation_id,
            reproducibility_info=get_reproducibility_info(),
        )

        # Run benchmarks
        for spec in benchmarks:
            logger.info(f"Running {spec.name}...")
            result = await self.run_benchmark(
                spec.name,
                num_samples=num_samples,
                correlation_id=correlation_id,
                emit_receipts=emit_receipts,
                **kwargs,
            )
            suite.add_result(result)

        suite.duration_s = time.time() - start_time

        # Compute aggregate scores with category weights
        category_weights = {
            BenchmarkCategory.AI_INDIVIDUAL.value: 0.25,
            BenchmarkCategory.AI_AGENTIC.value: 0.20,
            BenchmarkCategory.AI_HIVE.value: 0.15,
            BenchmarkCategory.ACTIVE_INFERENCE.value: 0.15,
            BenchmarkCategory.SYSTEM_API.value: 0.10,
            BenchmarkCategory.SYSTEM_WS.value: 0.05,
            BenchmarkCategory.SCIENTIFIC.value: 0.10,
        }
        suite.compute_aggregate_scores(category_weights)

        logger.info(suite.summary())

        return suite

    def _emit_receipt(
        self,
        correlation_id: str,
        phase: str,
        benchmark_name: str,
        data: dict[str, Any],
        status: str = "success",
    ) -> None:
        """Emit benchmark receipt."""
        try:
            from kagami.core.receipts import UnifiedReceiptFacade as URF

            URF.emit(
                correlation_id=correlation_id,
                event_name=f"benchmark.{phase.lower()}",
                action=f"benchmark.{benchmark_name}",
                app="benchmarks",
                event_data={
                    "phase": phase,
                    "benchmark": benchmark_name,
                    **data,
                },
                status=status,
            )
        except ImportError:
            logger.debug("Receipt emission not available")
        except Exception as e:
            logger.warning(f"Failed to emit receipt: {e}")


# Singleton accessor
_registry: BenchmarkRegistry | None = None


def get_registry() -> BenchmarkRegistry:
    """Get the global benchmark registry."""
    global _registry
    if _registry is None:
        _registry = BenchmarkRegistry()
    return _registry


def register_benchmark(  # type: ignore[no-untyped-def]
    name: str,
    category: BenchmarkCategory,
    description: str,
    **kwargs,
) -> Callable:
    """Decorator to register a benchmark function.

    Usage:
        @register_benchmark(
            name="my_benchmark",
            category=BenchmarkCategory.AI_INDIVIDUAL,
            description="My benchmark",
        )
        async def run_my_benchmark(num_samples: int = 10) -> dict:
            ...
    """

    def decorator(fn: Callable) -> Callable:
        get_registry().register(
            name=name,
            category=category,
            description=description,
            runner=fn,
            **kwargs,
        )
        return fn

    return decorator
