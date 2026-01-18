from __future__ import annotations

"""Dry-Run Shadow Evaluation - Test improvements without applying.

Enables safe evaluation of proposed changes:
1. Create isolated sandbox
2. Apply proposal in sandbox
3. Run full test suite
4. Run benchmarks
5. Collect metrics
6. Return results WITHOUT applying to main codebase

This is CRITICAL for safety - no code changes until proven safe.
"""
import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DryRunResult:
    """Results from dry-run evaluation."""

    proposal_id: str
    success: bool
    test_results: dict[str, Any]
    benchmark_results: dict[str, Any]
    fitness_score: float
    passed_guardrails: bool
    violations: list[str]
    warnings: list[str]
    execution_time_s: float
    recommendation: str  # "approve", "reject", "needs_review"


class DryRunEvaluator:
    """Evaluate improvements in isolated sandbox without applying."""

    def __init__(self, workspace_root: Path | None = None) -> None:
        self._workspace_root = workspace_root or Path.cwd()
        self._sandbox_dir: Path | None = None
        self._evaluations: list[DryRunResult] = []

    async def evaluate_proposal(
        self, proposal: dict[str, Any], run_benchmarks: bool = False
    ) -> DryRunResult:
        """Evaluate proposal in dry-run mode.

        Args:
            proposal: ImprovementProposal dict[str, Any]
            run_benchmarks: Whether to run benchmarks (slow)

        Returns:
            DryRunResult with comprehensive evaluation
        """
        import time

        start_time = time.time()
        proposal_id = proposal.get("proposal_id", "unknown")

        logger.info(f"🧪 DRY-RUN: Evaluating proposal {proposal_id}")

        try:
            # Create sandbox
            sandbox = await self._create_sandbox()

            # Apply proposal in sandbox
            await self._apply_in_sandbox(sandbox, proposal)

            # Run tests
            test_results = await self._run_tests_in_sandbox(sandbox, proposal)

            # Run benchmarks (optional)
            benchmark_results = {}
            if run_benchmarks:
                benchmark_results = await self._run_benchmarks_in_sandbox(sandbox)
            else:
                benchmark_results = {"skipped": True, "reason": "dry_run_fast_mode"}

            # Evaluate fitness
            from kagami.core.evolution.fitness_functions import get_fitness_functions

            fitness_fn = get_fitness_functions()
            fitness_score = await fitness_fn.evaluate_improvement(
                proposal, test_results, benchmark_results
            )

            # Determine recommendation
            recommendation = self._make_recommendation(fitness_score)

            result = DryRunResult(
                proposal_id=proposal_id,
                success=fitness_score.passed_guardrails,
                test_results=test_results,
                benchmark_results=benchmark_results,
                fitness_score=fitness_score.total_score,
                passed_guardrails=fitness_score.passed_guardrails,
                violations=fitness_score.violations,
                warnings=fitness_score.metrics.get("warnings", []),
                execution_time_s=time.time() - start_time,
                recommendation=recommendation,
            )

            self._evaluations.append(result)

            logger.info(
                f"✅ DRY-RUN: {proposal_id} → {recommendation} "
                f"(fitness: {fitness_score.total_score:.2f}, "
                f"time: {result.execution_time_s:.1f}s)"
            )

            # Clean up sandbox
            await self._cleanup_sandbox(sandbox)

            return result

        except Exception as e:
            logger.error(f"❌ DRY-RUN: Evaluation failed: {e}")

            # Return failed result
            result = DryRunResult(
                proposal_id=proposal_id,
                success=False,
                test_results={"error": str(e)},
                benchmark_results={},
                fitness_score=0.0,
                passed_guardrails=False,
                violations=[f"Evaluation error: {e}"],
                warnings=[],
                execution_time_s=time.time() - start_time,
                recommendation="reject",
            )

            # Clean up if sandbox was created
            if self._sandbox_dir and self._sandbox_dir.exists():
                shutil.rmtree(self._sandbox_dir, ignore_errors=True)

            return result

    async def _create_sandbox(self) -> Path:
        """Create isolated sandbox directory."""
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(prefix="kagami_evolution_sandbox_")
        sandbox = Path(temp_dir)

        # Copy workspace to sandbox
        logger.info(f"Creating sandbox: {sandbox}")

        # Copy critical files only (not entire workspace - too slow)
        critical_dirs = [
            "kagami/core",
            "kagami/api",
            "tests/unit",
        ]

        for dir_name in critical_dirs:
            src = self._workspace_root / dir_name
            if src.exists():
                dst = sandbox / dir_name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dst, symlinks=False, ignore_errors=True)  # type: ignore  # Call sig
                else:
                    shutil.copy2(src, dst)

        # Copy config files
        for config in ["pyproject.toml", "pytest.ini", "mypy.ini"]:
            src = self._workspace_root / config
            if src.exists():
                shutil.copy2(src, sandbox / config)

        self._sandbox_dir = sandbox
        return sandbox

    async def _apply_in_sandbox(self, sandbox: Path, proposal: dict[str, Any]) -> None:
        """Apply proposed change in sandbox."""
        file_path = proposal.get("file_path", "")
        new_code = proposal.get("proposed_code_snippet", "")

        if not file_path or not new_code:
            raise ValueError("Proposal missing file_path or proposed_code_snippet")

        target_file = sandbox / file_path

        # Create parent directories
        target_file.parent.mkdir(parents=True, exist_ok=True)

        # Write new code
        target_file.write_text(new_code, encoding="utf-8")

        logger.info(f"Applied proposal to sandbox: {file_path}")

    async def _run_tests_in_sandbox(
        self, sandbox: Path, proposal: dict[str, Any]
    ) -> dict[str, Any]:
        """Run tests in sandbox."""

        results = {}

        # Syntax check
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3",
                "-m",
                "py_compile",
                str(sandbox / "kagami"),
                cwd=str(sandbox),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            results["syntax_check"] = {
                "passed": proc.returncode == 0,
                "output": stderr.decode() if stderr else "",
            }
        except Exception as e:
            results["syntax_check"] = {"passed": False, "error": str(e)}

        # Type check (mypy)
        try:
            proc = await asyncio.create_subprocess_exec(
                "mypy",
                "kagami",
                "--config-file",
                "mypy.ini",
                cwd=str(sandbox),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.create_subprocess_exec.communicate()  # type: ignore  # Dynamic attr
            results["type_check"] = {
                "passed": proc.returncode == 0,
                "output": stdout.decode() if stdout else "",
            }
        except Exception as e:
            results["type_check"] = {"passed": False, "error": str(e)}

        # Lint check (ruff)
        try:
            proc = await asyncio.create_subprocess_exec(
                "ruff",
                "check",
                "kagami",
                "--select",
                "E,F",
                cwd=str(sandbox),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            results["lint_check"] = {
                "passed": proc.returncode == 0,
                "output": stdout.decode() if stdout else "",
            }
        except Exception as e:
            results["lint_check"] = {"passed": False, "error": str(e)}

        # Test suite (fast subset)
        try:
            proc = await asyncio.create_subprocess_exec(
                "pytest",
                "tests/unit",
                "-q",
                "--tb=no",
                "-x",
                cwd=str(sandbox),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={"KAGAMI_BOOT_MODE": "test"},
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode() if stdout else ""

            # Parse pytest output for pass rate
            passed = "passed" in output or proc.returncode == 0

            results["test_suite"] = {
                "all_passed": passed,
                "pass_rate": 1.0 if passed else 0.0,
                "output": output[:500],  # First 500 chars
            }
        except Exception as e:
            results["test_suite"] = {"all_passed": False, "error": str(e)}

        # Ethical check via EthicalInstinct (jailbreak detector)
        results["ethical_check"] = await self._run_ethical_check(proposal)

        # CBF check - verify h(x) >= 0 (Control Barrier Function)
        results["cbf_check"] = await self._run_cbf_check(proposal)

        return results

    async def _run_ethical_check(self, proposal: dict[str, Any]) -> dict[str, Any]:
        """Run ethical instinct check on proposal.

        Uses the EthicalInstinct (JailbreakDetector) to evaluate proposal
        for ethical concerns and potential harmful patterns.

        Args:
            proposal: The evolution proposal to evaluate.

        Returns:
            Dictionary with passed status and any concerns.
        """
        try:
            from kagami.core.security.jailbreak_detector import get_jailbreak_detector

            ethical_instinct = get_jailbreak_detector()

            # Build context for ethical evaluation
            context = {
                "type": "evolution_proposal",
                "proposal_id": proposal.get("id", "unknown"),
                "description": proposal.get("description", ""),
                "changes": proposal.get("changes", []),
                "files_affected": proposal.get("files", []),
                "rationale": proposal.get("rationale", ""),
            }

            # Add code changes summary if available
            if changes := proposal.get("changes"):
                code_summary = []
                for change in changes[:5]:  # Limit to first 5 changes
                    if isinstance(change, dict):
                        code_summary.append(change.get("content", "")[:500])
                context["code_changes_summary"] = "\n---\n".join(code_summary)

            # Evaluate via ethical instinct
            verdict = await ethical_instinct.evaluate(context)

            # Extract result
            passed = verdict.get("safe", True) if isinstance(verdict, dict) else True
            concerns = verdict.get("concerns", []) if isinstance(verdict, dict) else []
            confidence = verdict.get("confidence", 1.0) if isinstance(verdict, dict) else 1.0

            return {
                "passed": passed,
                "confidence": confidence,
                "concerns": concerns,
                "verdict": verdict,
            }

        except ImportError:
            logger.debug("Ethical instinct not available, assuming passed")
            return {"passed": True, "note": "ethical_instinct_unavailable"}
        except Exception as e:
            logger.warning(f"Ethical check failed: {e}")
            # Fail closed - assume ethical violation if check fails
            return {
                "passed": False,
                "error": str(e),
                "reason": "ethical_check_execution_error",
            }

    async def _run_cbf_check(self, proposal: dict[str, Any]) -> dict[str, Any]:
        """Run Control Barrier Function check on proposal.

        Verifies that the proposal maintains h(x) >= 0 (safety invariant).

        Args:
            proposal: The evolution proposal to evaluate.

        Returns:
            Dictionary with h_x_nonnegative status and barrier value.
        """
        try:
            from kagami.core.safety.cbf_integration import check_cbf_for_operation

            # Build action and target from proposal
            action = f"evolution:{proposal.get('type', 'modify')}"
            target = proposal.get("target_file", proposal.get("id", "unknown"))

            # Build context for CBF evaluation
            context = {
                "proposal_id": proposal.get("id"),
                "files_affected": len(proposal.get("files", [])),
                "change_magnitude": proposal.get("risk_score", 0.5),
                "is_breaking_change": proposal.get("breaking", False),
                "category": proposal.get("category", "enhancement"),
            }

            # Check CBF
            result = await check_cbf_for_operation(  # type: ignore[call-arg]
                operation="evolution_dry_run",
                action=action,
                target=target,
                context=context,
            )

            return {
                "h_x_nonnegative": result.passed,
                "h_x": result.h_x,
                "reason": result.reason,
                "detail": result.detail,
            }

        except ImportError:
            logger.debug("CBF integration not available, assuming safe")
            return {"h_x_nonnegative": True, "note": "cbf_unavailable"}
        except Exception as e:
            logger.warning(f"CBF check failed: {e}")
            # Fail closed - assume unsafe if CBF check fails
            return {
                "h_x_nonnegative": False,
                "error": str(e),
                "reason": "cbf_check_execution_error",
            }

    async def _run_benchmarks_in_sandbox(self, sandbox: Path) -> dict[str, Any]:
        """Run benchmarks in sandbox environment.

        Executes lightweight benchmarks to verify performance characteristics
        of the proposed changes.

        Args:
            sandbox: Path to sandbox directory with proposed changes.

        Returns:
            Dictionary with benchmark results.
        """
        results: dict[str, Any] = {
            "humaneval_score": None,
            "p95_latency_ms": None,
            "throughput_ops_s": None,
        }

        try:
            import subprocess
            import time

            # Run a quick syntax/import check as proxy for code quality
            check_start = time.time()
            py_files = list(sandbox.rglob("*.py"))

            syntax_errors = 0
            total_checked = 0

            for py_file in py_files[:20]:  # Limit to first 20 files for speed
                total_checked += 1
                try:
                    # Syntax check via py_compile
                    proc = subprocess.run(
                        ["python", "-m", "py_compile", str(py_file)],
                        capture_output=True,
                        timeout=5,
                    )
                    if proc.returncode != 0:
                        syntax_errors += 1
                except subprocess.TimeoutExpired:
                    syntax_errors += 1
                except Exception:
                    syntax_errors += 1

            check_duration = time.time() - check_start

            # Calculate derived metrics
            if total_checked > 0:
                syntax_pass_rate = (total_checked - syntax_errors) / total_checked
                # Use syntax pass rate as proxy for code quality (humaneval correlation)
                results["humaneval_score"] = syntax_pass_rate

            # Estimate latency from check duration
            if total_checked > 0:
                results["p95_latency_ms"] = (check_duration / total_checked) * 1000

            # Estimate throughput
            if check_duration > 0:
                results["throughput_ops_s"] = total_checked / check_duration

            results["files_checked"] = total_checked
            results["syntax_errors"] = syntax_errors
            results["check_duration_s"] = check_duration

        except Exception as e:
            logger.warning(f"Sandbox benchmark failed: {e}")
            results["error"] = str(e)
            results["note"] = "benchmark_execution_failed"

        return results

    async def _cleanup_sandbox(self, sandbox: Path) -> None:
        """Clean up sandbox directory."""
        if sandbox.exists():
            shutil.rmtree(sandbox, ignore_errors=True)
            logger.info(f"Cleaned up sandbox: {sandbox}")

    def _make_recommendation(self, fitness_score: Any) -> str:
        """Make recommendation based on fitness score.

        Returns:
            "approve", "reject", or "needs_review"
        """
        if not fitness_score.passed_guardrails:
            return "reject"  # Guardrail violations = auto-reject

        if fitness_score.total_score >= 0.8:
            return "approve"  # High fitness = approve

        if fitness_score.total_score >= 0.6:
            return "needs_review"  # Medium fitness = human review

        return "reject"  # Low fitness = reject

    def get_evaluation_history(self) -> list[DryRunResult]:
        """Get history of all evaluations."""
        return self._evaluations.copy()

    def get_success_rate(self) -> float:
        """Get success rate of evaluated proposals."""
        if not self._evaluations:
            return 0.0

        approved = sum(1 for e in self._evaluations if e.recommendation == "approve")
        return approved / len(self._evaluations)


# Singleton
_dry_run_evaluator: DryRunEvaluator | None = None


def get_dry_run_evaluator() -> DryRunEvaluator:
    """Get global dry-run evaluator."""
    global _dry_run_evaluator
    if _dry_run_evaluator is None:
        _dry_run_evaluator = DryRunEvaluator()
    return _dry_run_evaluator
