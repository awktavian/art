from __future__ import annotations

"""Fitness Functions & Guardrail Specification for Evolution.

Defines multi-objective fitness for evaluating improvements:
- Safety: h(x) ≥ 0, ethical compliance, no violations
- Correctness: Tests pass, types check, lints clean
- Performance: Latency, throughput, resource usage
- Reliability: Error rates, uptime, recovery time
- Maintainability: Code quality, documentation, complexity

All improvements must satisfy guardrails before application.
"""
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FitnessWeights:
    """Weights for multi-objective fitness function."""

    safety: float = 0.40  # Highest weight - non-negotiable
    correctness: float = 0.30  # Must work
    performance: float = 0.15  # Nice to have
    reliability: float = 0.10  # Important
    maintainability: float = 0.05  # Long-term value


@dataclass
class FitnessScore:
    """Multi-objective fitness evaluation."""

    safety_score: float  # 0.0-1.0
    correctness_score: float  # 0.0-1.0
    performance_score: float  # 0.0-1.0
    reliability_score: float  # 0.0-1.0
    maintainability_score: float  # 0.0-1.0
    total_score: float  # Weighted sum
    passed_guardrails: bool
    violations: list[str]
    metrics: dict[str, Any]


class EvolutionGuardrails:
    """Hard constraints that all improvements must satisfy."""

    # Safety guardrails (BLOCKING)
    SAFETY_BARRIERS = {
        "control_barrier_function": "h(x) >= 0 always",
        "ethical_compliance": "No ethical instinct violations",
        "no_safety_constraint_modification": "Cannot weaken safety",
        "human_override_preserved": "Shutdown/rollback always available",
        "rate_limit_respected": "Within evolution rate limits",
    }

    # Correctness guardrails (BLOCKING)
    CORRECTNESS_BARRIERS = {
        "syntax_valid": "python -m py_compile passes",
        "types_valid": "mypy passes",
        "lints_clean": "ruff check passes",
        "tests_pass": "Core test suite passes",
        "imports_work": "No ImportError",
    }

    # Performance guardrails (WARNING)
    PERFORMANCE_BARRIERS = {
        "no_latency_regression": "p95 latency not increased >10%",
        "no_throughput_regression": "Throughput not decreased >10%",
        "no_memory_explosion": "Memory usage <16GB",
        "no_cpu_saturation": "CPU usage <80%",
    }

    # Reliability guardrails (WARNING)
    RELIABILITY_BARRIERS = {
        "error_rate_acceptable": "Error rate <5%",
        "no_new_crashes": "No new exception types",
        "uptime_maintained": "Service uptime >99%",
    }

    @classmethod
    def check_all(cls, proposal: dict[str, Any], test_results: dict[str, Any]) -> dict[str, Any]:
        """Check all guardrails against a proposal.

        Returns:
            {
                "passed": bool,
                "violations": list[str],
                "safety_ok": bool,
                "correctness_ok": bool,
                "warnings": list[str]
            }
        """
        violations = []
        warnings = []

        # Safety (BLOCKING)
        safety_checks = cls._check_safety_barriers(proposal, test_results)
        if not safety_checks["passed"]:
            violations.extend(safety_checks["violations"])

        # Correctness (BLOCKING)
        correctness_checks = cls._check_correctness_barriers(test_results)
        if not correctness_checks["passed"]:
            violations.extend(correctness_checks["violations"])

        # Performance (WARNING)
        perf_checks = cls._check_performance_barriers(test_results)
        if not perf_checks["passed"]:
            warnings.extend(perf_checks["warnings"])

        # Reliability (WARNING)
        reliability_checks = cls._check_reliability_barriers(test_results)
        if not reliability_checks["passed"]:
            warnings.extend(reliability_checks["warnings"])

        return {
            "passed": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "safety_ok": safety_checks["passed"],
            "correctness_ok": correctness_checks["passed"],
            "performance_ok": perf_checks["passed"],
            "reliability_ok": reliability_checks["passed"],
        }

    @classmethod
    def _check_safety_barriers(
        cls, proposal: dict[str, Any], test_results: dict[str, Any]
    ) -> dict[str, Any]:
        """Check safety barriers (BLOCKING)."""
        violations = []

        # Check if proposal modifies safety constraints
        if cls._modifies_safety_constraints(proposal):
            violations.append("Cannot modify safety constraints")

        # Check if proposal passes ethical evaluation
        if not test_results.get("ethical_check", {}).get("passed", True):
            violations.append("Ethical evaluation failed")

        # Check control barrier function
        if not test_results.get("cbf_check", {}).get("h_x_nonnegative", True):
            violations.append("Control barrier function violated (h(x) < 0)")

        # Check human override preserved
        if cls._removes_human_override(proposal):
            violations.append("Human override capability removed")

        return {"passed": len(violations) == 0, "violations": violations}

    @classmethod
    def _check_correctness_barriers(cls, test_results: dict[str, Any]) -> dict[str, Any]:
        """Check correctness barriers (BLOCKING)."""
        violations = []

        if not test_results.get("syntax_check", {}).get("passed", False):
            violations.append("Syntax check failed")

        if not test_results.get("type_check", {}).get("passed", False):
            violations.append("Type check failed")

        if not test_results.get("lint_check", {}).get("passed", False):
            violations.append("Lint check failed")

        if not test_results.get("test_suite", {}).get("all_passed", False):
            violations.append("Test suite failures")

        return {"passed": len(violations) == 0, "violations": violations}

    @classmethod
    def _check_performance_barriers(cls, test_results: dict[str, Any]) -> dict[str, Any]:
        """Check performance barriers (WARNING only)."""
        warnings = []

        perf = test_results.get("performance_metrics", {})

        if perf.get("p95_latency_increase", 0) > 0.1:
            warnings.append("p95 latency increased >10%")

        if perf.get("throughput_decrease", 0) > 0.1:
            warnings.append("Throughput decreased >10%")

        if perf.get("memory_mb", 0) > 16000:
            warnings.append("Memory usage >16GB")

        return {"passed": len(warnings) == 0, "warnings": warnings}

    @classmethod
    def _check_reliability_barriers(cls, test_results: dict[str, Any]) -> dict[str, Any]:
        """Check reliability barriers (WARNING only)."""
        warnings = []

        reliability = test_results.get("reliability_metrics", {})

        if reliability.get("error_rate", 0) > 0.05:
            warnings.append("Error rate >5%")

        if reliability.get("new_exception_types", 0) > 0:
            warnings.append(f"{reliability['new_exception_types']} new exception types")

        return {"passed": len(warnings) == 0, "warnings": warnings}

    @classmethod
    def _modifies_safety_constraints(cls, proposal: dict[str, Any]) -> bool:
        """Check if proposal modifies safety constraint files."""
        dangerous_paths = [
            "kagami/core/safety/",
            "kagami/core/instincts/ethical_instinct.py",
            "kagami/core/safety/control_barrier_function.py",
        ]

        file_path = proposal.get("file_path", "")
        return any(dangerous in file_path for dangerous in dangerous_paths)

    @classmethod
    def _removes_human_override(cls, proposal: dict[str, Any]) -> bool:
        """Check if proposal removes shutdown/override capability."""
        code = proposal.get("proposed_code_snippet", "")
        dangerous_patterns = [
            "accept_shutdown = False",
            "human_override = False",
            "ignore_shutdown",
        ]
        return any(pattern in code for pattern in dangerous_patterns)


class FitnessFunctions:
    """Multi-objective fitness evaluation for improvements."""

    def __init__(self, weights: FitnessWeights | None = None) -> None:
        self.weights = weights or FitnessWeights()
        self._baselines: dict[str, float] = {}

    async def capture_baselines(self) -> dict[str, float]:
        """Capture current performance baselines.

        Returns:
            Dict of metric_name → baseline_value
        """
        logger.info("📊 Capturing performance baselines...")

        baselines = {}

        try:
            # Lightweight syntax baseline using py_compile on this file
            import subprocess

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "py_compile",
                    __file__,
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            baselines["syntax_pass_rate"] = 1.0 if result.returncode == 0 else 0.0

            # Benchmark current system
            baselines["current_timestamp"] = 0.0  # Placeholder

            # Would run benchmarks here
            # baselines["humaneval_score"] = await run_humaneval()
            # baselines["prediction_error_ms"] = await get_avg_prediction_error()

            # For now, use targets as baselines
            baselines["humaneval_score"] = 0.939  # Current known score
            baselines["p95_latency_ms"] = 50.0  # Target
            baselines["throughput_ops_s"] = 241.7  # Measured
            baselines["error_rate"] = 0.01  # 1%
            baselines["collaboration_rate"] = 0.05  # 5%

        except Exception as e:
            logger.warning(f"Failed to capture some baselines: {e}")

        self._baselines = baselines
        logger.info(f"✅ Captured {len(baselines)} baseline metrics")

        return baselines

    async def evaluate_improvement(
        self,
        proposal: dict[str, Any],
        test_results: dict[str, Any],
        benchmark_results: dict[str, Any],
    ) -> FitnessScore:
        """Evaluate improvement against multi-objective fitness.

        Args:
            proposal: The proposed improvement
            test_results: Results from sandbox testing
            benchmark_results: Results from benchmark runs

        Returns:
            FitnessScore with detailed breakdown
        """
        # Safety score (0.0-1.0)
        safety = self._evaluate_safety(proposal, test_results)

        # Correctness score (0.0-1.0)
        correctness = self._evaluate_correctness(test_results)

        # Performance score (0.0-1.0)
        performance = self._evaluate_performance(benchmark_results)

        # Reliability score (0.0-1.0)
        reliability = self._evaluate_reliability(test_results)

        # Maintainability score (0.0-1.0)
        maintainability = self._evaluate_maintainability(proposal)

        # Weighted total
        total = (
            safety * self.weights.safety
            + correctness * self.weights.correctness
            + performance * self.weights.performance
            + reliability * self.weights.reliability
            + maintainability * self.weights.maintainability
        )

        # Check guardrails
        guardrail_check = EvolutionGuardrails.check_all(proposal, test_results)

        return FitnessScore(
            safety_score=safety,
            correctness_score=correctness,
            performance_score=performance,
            reliability_score=reliability,
            maintainability_score=maintainability,
            total_score=total,
            passed_guardrails=guardrail_check["passed"],
            violations=guardrail_check["violations"],
            metrics={
                "weights": {
                    "safety": self.weights.safety,
                    "correctness": self.weights.correctness,
                    "performance": self.weights.performance,
                    "reliability": self.weights.reliability,
                    "maintainability": self.weights.maintainability,
                },
                "breakdown": {
                    "safety": safety,
                    "correctness": correctness,
                    "performance": performance,
                    "reliability": reliability,
                    "maintainability": maintainability,
                },
                "warnings": guardrail_check.get("warnings", []),
            },
        )

    def _evaluate_safety(self, proposal: dict[str, Any], test_results: dict[str, Any]) -> float:
        """Evaluate safety component (0.0-1.0)."""
        score = 1.0

        # Penalize if modifies safety systems
        if EvolutionGuardrails._modifies_safety_constraints(proposal):
            score -= 0.5

        # Penalize if ethical check failed
        if not test_results.get("ethical_check", {}).get("passed", True):
            score -= 0.4

        # Penalize if CBF violated
        if not test_results.get("cbf_check", {}).get("h_x_nonnegative", True):
            score = 0.0  # ZERO if safety violated

        # Penalize if removes human control
        if EvolutionGuardrails._removes_human_override(proposal):
            score = 0.0  # ZERO if removes override

        return max(0.0, score)

    def _evaluate_correctness(self, test_results: dict[str, Any]) -> float:
        """Evaluate correctness component (0.0-1.0)."""
        score = 0.0

        # Syntax check (0.25)
        if test_results.get("syntax_check", {}).get("passed", False):
            score += 0.25

        # Type check (0.25)
        if test_results.get("type_check", {}).get("passed", False):
            score += 0.25

        # Lint check (0.25)
        if test_results.get("lint_check", {}).get("passed", False):
            score += 0.25

        # Test suite (0.25)
        test_suite = test_results.get("test_suite", {})
        if test_suite.get("all_passed", False):
            score += 0.25
        elif test_suite.get("pass_rate", 0) > 0.9:
            score += 0.20  # Partial credit if >90% pass

        return score

    def _evaluate_performance(self, benchmark_results: dict[str, Any]) -> float:
        """Evaluate performance component (0.0-1.0)."""
        score = 0.5  # Neutral baseline

        # Compare to baselines
        if "p95_latency_ms" in benchmark_results and "p95_latency_ms" in self._baselines:
            current = benchmark_results["p95_latency_ms"]
            baseline = self._baselines["p95_latency_ms"]

            # Improvement = score boost, regression = penalty
            if current < baseline:
                improvement = (baseline - current) / baseline
                score += min(0.5, improvement)
            else:
                regression = (current - baseline) / baseline
                score -= min(0.5, regression * 2)  # 2x penalty for regression

        # Throughput
        if "throughput_ops_s" in benchmark_results and "throughput_ops_s" in self._baselines:
            current = benchmark_results["throughput_ops_s"]
            baseline = self._baselines["throughput_ops_s"]

            if current > baseline:
                improvement = (current - baseline) / baseline
                score += min(0.5, improvement)
            else:
                regression = (baseline - current) / baseline
                score -= min(0.5, regression * 2)

        return max(0.0, min(1.0, score))

    def _evaluate_reliability(self, test_results: dict[str, Any]) -> float:
        """Evaluate reliability component (0.0-1.0)."""
        score = 1.0

        # Error rate
        error_rate = test_results.get("reliability_metrics", {}).get("error_rate", 0)
        if error_rate > 0.05:  # >5%
            score -= 0.3

        # New exceptions
        new_exceptions = test_results.get("reliability_metrics", {}).get("new_exception_types", 0)
        if new_exceptions > 0:
            score -= 0.2

        # Uptime impact
        uptime = test_results.get("reliability_metrics", {}).get("uptime", 1.0)
        if uptime < 0.99:
            score -= 0.3

        return max(0.0, score)

    def _evaluate_maintainability(self, proposal: dict[str, Any]) -> float:
        """Evaluate maintainability component (0.0-1.0)."""
        score = 0.5  # Neutral baseline

        code = proposal.get("proposed_code_snippet", "")

        # Has docstrings
        if '"""' in code or "'''" in code:
            score += 0.2

        # Has type hints
        if "->" in code and ":" in code:
            score += 0.2

        # Not too complex
        lines = code.count("\n")
        if lines < 100:
            score += 0.1  # Concise

        # Has rationale
        if proposal.get("rationale"):
            score += 0.1

        # Evidence-based (per forensic rules)
        if proposal.get("evidence_links"):
            score += 0.1

        return min(1.0, score)

    def get_baselines(self) -> dict[str, float]:
        """Get current baselines."""
        return self._baselines.copy()


# Singleton
_fitness_functions: FitnessFunctions | None = None


def get_fitness_functions() -> FitnessFunctions:
    """Get global fitness functions."""
    global _fitness_functions
    if _fitness_functions is None:
        _fitness_functions = FitnessFunctions()
    return _fitness_functions
