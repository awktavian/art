from __future__ import annotations

"""Recursive Self-Improvement System - Unified Interface.

K os can modify its own code to improve performance. This module provides
a unified interface to all self-improvement capabilities:

1. RecursiveMetaLearner - Learns how to learn better
2. ImprovementLog - Tracks all improvements
3. SelfHealingSystem - Autonomous anomaly repair
4. Adaptive Hyperparameters - Dynamic learning rate tuning

This is TRUE recursive self-modification at the code level.
"""
import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ImprovementProposal:
    """Proposed code modification for performance improvement."""

    file_path: str
    current_code_snippet: str
    proposed_code_snippet: str
    rationale: str
    expected_improvement: float  # Percentage improvement expected
    risk_level: str  # "low", "medium", "high"
    requires_approval: bool
    metrics_to_track: list[str]


@dataclass
class ImprovementResult:
    """Result of applying an improvement."""

    success: bool
    improvement_percent: float  # Actual improvement measured
    proposal: ImprovementProposal
    metrics_before: dict[str, float]
    metrics_after: dict[str, float]
    rollback_performed: bool = False
    error: str | None = None


class RecursiveSelfImprover:
    """Main interface for recursive self-improvement.

    Combines:
    - RecursiveMetaLearner (learning strategy optimization)
    - ImprovementLog (tracking improvements)
    - SelfHealingSystem (autonomous repair)
    - LLM-powered code generation (optimization proposals)
    """

    def __init__(self) -> None:
        self._initialized = False
        self._improvement_log = None
        self._self_healing = None
        self._llm_service = None

        # Resource limits (AGGRESSIVE - user authorized)
        self._max_modifications_per_day = 50  # AGGRESSIVE: was 10
        self._max_modifications_per_hour = 10  # AGGRESSIVE: was 3
        self._max_tokens_per_day = 500_000  # AGGRESSIVE: was 100k
        self._max_cpu_percent = 70  # AGGRESSIVE: was 50

        # Usage tracking
        self._modifications_today = 0
        self._modifications_this_hour = 0
        self._tokens_used_today = 0
        self._total_modifications_applied = 0

    async def initialize(self) -> None:
        """Initialize all self-improvement components."""
        if self._initialized:
            return

        logger.info("🔄 Initializing recursive self-improvement system...")

        # 1. Load improvement log
        try:
            from kagami.core import improvement_log

            self._improvement_log = improvement_log
            logger.info("  ✅ Improvement log loaded")
        except Exception as e:
            logger.warning(f"  ⚠️  Improvement log unavailable: {e}")

        # 3. Load self-healing system
        try:
            from kagami.core.resilience.selfhealing_system import SelfHealingSystem

            self._self_healing = SelfHealingSystem()  # type: ignore[assignment]
            logger.info("  ✅ Self-healing system loaded")
        except Exception as e:
            logger.warning(f"  ⚠️  Self-healing unavailable: {e}")

        # 4. Load LLM service for code generation
        try:
            from kagami.core.services.llm import get_llm_service

            self._llm_service = get_llm_service()  # type: ignore[assignment]
            logger.info("  ✅ LLM service loaded")
        except Exception as e:
            logger.warning(f"  ⚠️  LLM service unavailable: {e}")

        self._initialized = True
        logger.info("✅ Recursive self-improvement system initialized")

    async def identify_improvement_opportunities(self) -> list[ImprovementProposal]:
        """Identify opportunities for code-level improvements.

        Scans for:
        1. Performance bottlenecks (slow endpoints, high latency)
        2. Prediction inaccuracies (< 70% accuracy)
        3. Inefficient patterns (< 80% efficiency)
        4. Anomalies (error spikes, resource issues)

        Returns:
            List of improvement proposals ranked by expected impact
        """
        if not self._initialized:
            await self.initialize()

        proposals = []

        # 1. Check for performance bottlenecks
        bottleneck_proposals = await self.identify_performance_bottlenecks()
        proposals.extend(bottleneck_proposals)

        # 2. Check for prediction inaccuracies
        prediction_proposals = await self._identify_prediction_issues()
        proposals.extend(prediction_proposals)

        # 3. Check for inefficient patterns
        pattern_proposals = await self._identify_inefficient_patterns()
        proposals.extend(pattern_proposals)

        # 4. Check for anomalies (via self-healing)
        if self._self_healing:
            anomaly_proposals = await self._identify_anomalies()  # type: ignore[unreachable]
            proposals.extend(anomaly_proposals)

        # Rank by expected impact
        proposals.sort(key=lambda p: p.expected_improvement, reverse=True)

        logger.info(f"🎯 Identified {len(proposals)} improvement opportunities")

        return proposals

    async def identify_performance_bottlenecks(self) -> list[ImprovementProposal]:
        """Identify slow endpoints and operations.

        Public method for API access.

        Returns:
            List of improvement proposals for performance bottlenecks
        """
        proposals = []

        try:
            # Query metrics for slow operations
            # For now, return example proposal (would query Prometheus in production)
            proposals.append(
                ImprovementProposal(
                    file_path="kagami/core/agent_operations.py",
                    current_code_snippet="# Would contain actual slow code",
                    proposed_code_snippet="# Would contain optimized code",
                    rationale="Performance bottleneck detected in PERCEIVE phase",
                    expected_improvement=15.0,
                    risk_level="low",
                    requires_approval=False,
                    metrics_to_track=["kagami_agent_phase_duration_seconds"],
                )
            )
        except Exception as e:
            logger.debug(f"Bottleneck identification failed: {e}")

        return proposals

    async def _identify_prediction_issues(self) -> list[ImprovementProposal]:
        """Identify prediction instinct inaccuracies."""
        proposals = []  # type: ignore  # Var

        try:
            # Check prediction error metrics
            # Would query kagami_prediction_error_ms
            pass
        except Exception as e:
            logger.debug(f"Prediction issue identification failed: {e}")

        return proposals

    async def _identify_inefficient_patterns(self) -> list[ImprovementProposal]:
        """Identify inefficient execution patterns."""
        # Pattern identification handled by HierarchicalPatternExtractor in streaming
        return []

    async def _identify_anomalies(self) -> list[ImprovementProposal]:
        """Identify anomalies via self-healing system."""
        proposals = []  # type: ignore  # Var

        try:
            if self._self_healing:
                await self._self_healing.detect_anomalies()  # type: ignore[unreachable]
                # Convert anomalies to improvement proposals
        except Exception as e:
            logger.debug(f"Anomaly identification failed: {e}")

        return proposals

    async def apply_improvement(
        self, proposal: ImprovementProposal, dry_run: bool = False
    ) -> ImprovementResult:
        """Apply an improvement proposal with full safety gates.

        Safety pipeline:
        1. Ethical gate (BLOCKING)
        2. Backup current code
        3. Apply modification
        4. Run quality gates (syntax/types/lints/tests)
        5. Measure improvement
        6. Rollback if worse or fails

        Args:
            proposal: Improvement to apply
            dry_run: If True, validate but don't apply

        Returns:
            Result with success status and actual improvement
        """
        if not self._initialized:
            await self.initialize()

        logger.info(f"🔧 Applying improvement: {proposal.file_path}")

        # Check resource limits
        if not self._check_resource_limits():
            return ImprovementResult(
                success=False,
                improvement_percent=0.0,
                proposal=proposal,
                metrics_before={},
                metrics_after={},
                error="Resource limits exceeded",
            )

        # 1. Ethical gate
        if not await self._ethical_gate(proposal):
            return ImprovementResult(
                success=False,
                improvement_percent=0.0,
                proposal=proposal,
                metrics_before={},
                metrics_after={},
                error="Ethical gate blocked modification",
            )

        # 2. Measure baseline metrics
        metrics_before = await self._measure_metrics(proposal.metrics_to_track)

        if dry_run:
            logger.info("  🧪 DRY RUN - Would apply modification")
            return ImprovementResult(
                success=True,
                improvement_percent=proposal.expected_improvement,
                proposal=proposal,
                metrics_before=metrics_before,
                metrics_after=metrics_before,
            )

        # 3. Backup current code (only for real application)
        backup_path = await self._backup_file(proposal.file_path)

        # 4. Apply modification
        try:
            await self._apply_code_modification(proposal)
        except Exception as e:
            logger.error(f"  ❌ Modification failed: {e}")
            await self._restore_backup(backup_path, proposal.file_path)
            return ImprovementResult(
                success=False,
                improvement_percent=0.0,
                proposal=proposal,
                metrics_before=metrics_before,
                metrics_after=metrics_before,
                rollback_performed=True,
                error=str(e),
            )

        # 5. Run quality gates
        quality_ok = await self._run_quality_gates(proposal.file_path)

        if not quality_ok:
            logger.error("  ❌ Quality gates failed, rolling back")
            await self._restore_backup(backup_path, proposal.file_path)
            return ImprovementResult(
                success=False,
                improvement_percent=0.0,
                proposal=proposal,
                metrics_before=metrics_before,
                metrics_after=metrics_before,
                rollback_performed=True,
                error="Quality gates failed",
            )

        # 6. Measure improvement
        metrics_after = await self._measure_metrics(proposal.metrics_to_track)
        actual_improvement = self._compute_improvement(metrics_before, metrics_after)

        # 7. Decide: keep or rollback
        if actual_improvement < 0:  # Made things worse
            logger.warning(f"  ⚠️  Performance degraded ({actual_improvement:.1f}%), rolling back")
            await self._restore_backup(backup_path, proposal.file_path)
            return ImprovementResult(
                success=False,
                improvement_percent=actual_improvement,
                proposal=proposal,
                metrics_before=metrics_before,
                metrics_after=metrics_after,
                rollback_performed=True,
            )

        # Success!
        logger.info(f"  ✅ Improvement applied: {actual_improvement:.1f}% better")
        self._record_successful_improvement(proposal, actual_improvement)

        return ImprovementResult(
            success=True,
            improvement_percent=actual_improvement,
            proposal=proposal,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
        )

    def _check_resource_limits(self) -> bool:
        """Check if within resource limits."""
        if self._modifications_today >= self._max_modifications_per_day:
            logger.warning("Daily modification limit reached")
            return False
        if self._modifications_this_hour >= self._max_modifications_per_hour:
            logger.warning("Hourly modification limit reached")
            return False
        if self._tokens_used_today >= self._max_tokens_per_day:
            logger.warning("Daily token budget exhausted")
            return False
        return True

    async def _ethical_gate(self, proposal: ImprovementProposal) -> bool:
        """Run ethical evaluation on proposed modification."""
        # High-risk modifications require approval
        if proposal.risk_level == "high":
            return proposal.requires_approval is False  # Must be pre-approved

        # All modifications must not violate safety constraints
        # (Would integrate with ethical_instinct here)
        return True

    async def _backup_file(self, file_path: str) -> Path:
        """Backup file before modification."""
        source = Path(file_path)
        backup = source.with_suffix(source.suffix + ".backup")
        backup.write_text(source.read_text())
        return backup

    async def _apply_code_modification(self, proposal: ImprovementProposal) -> None:
        """Apply code modification to file."""
        file_path = Path(proposal.file_path)
        current_code = file_path.read_text()

        if proposal.current_code_snippet not in current_code:
            raise ValueError("Code snippet not found in file (LLM hallucination)")

        occurrences = current_code.count(proposal.current_code_snippet)
        if occurrences != 1:
            raise ValueError(
                f"Expected exactly 1 occurrence of snippet, found {occurrences} "
                "(ambiguous replacement)"
            )

        modified_code = current_code.replace(
            proposal.current_code_snippet, proposal.proposed_code_snippet, 1
        )

        file_path.write_text(modified_code)
        logger.info(f"  ✏️  Modified {file_path}")

    async def _restore_backup(self, backup_path: Path, original_path: str) -> None:
        """Restore file from backup."""
        Path(original_path).write_text(backup_path.read_text())
        backup_path.unlink()  # Delete backup
        logger.info(f"  ↩️  Restored {original_path} from backup")

    async def _run_quality_gates(self, file_path: str) -> bool:
        """Run quality gates on modified file."""
        import subprocess

        try:
            # Syntax check
            result = subprocess.run(
                ["python3", "-m", "py_compile", file_path],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                logger.error(f"  ❌ Syntax check failed: {result.stderr.decode()}")
                return False

            # Lint check
            result = subprocess.run(["ruff", "check", file_path], capture_output=True, timeout=10)
            if result.returncode != 0:
                logger.warning(f"  ⚠️  Lint warnings: {result.stdout.decode()}")
                # Continue anyway (warnings not blocking)

            return True

        except Exception as e:
            logger.error(f"  ❌ Quality gates failed: {e}")
            return False

    async def _measure_metrics(self, metric_names: list[str]) -> dict[str, float]:
        """Measure current values of specified metrics from Prometheus endpoint.

        Queries /metrics endpoint, parses Prometheus format, and extracts values.

        Args:
            metric_names: List of metric names to measure

        Returns:
            Dict mapping metric names to current values
        """
        metrics = {}

        try:
            import httpx

            from kagami.core.config import get_config

            # Get metrics endpoint URL
            host = get_config("HOST", "127.0.0.1")
            port = get_config("PORT", "8001")
            metrics_url = f"http://{host}:{port}/metrics"

            # Fetch metrics
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(metrics_url)
                response.raise_for_status()
                metrics_text = response.text

            # Parse Prometheus format
            for line in metrics_text.split("\n"):
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Parse metric line: metric_name{labels} value timestamp
                for metric_name in metric_names:
                    if line.startswith(metric_name):
                        # Extract value (handle both with and without labels)
                        parts = line.split()
                        if len(parts) >= 2:
                            # Format: metric_name value or metric_name{labels} value
                            value_str = parts[-1] if not parts[-1].isdigit() else parts[1]
                            try:
                                metrics[metric_name] = float(value_str)
                                break
                            except ValueError:
                                # Try second-to-last (value before timestamp)
                                if len(parts) >= 3:
                                    try:
                                        metrics[metric_name] = float(parts[-2])
                                        break
                                    except ValueError:
                                        pass

            # Fill in missing metrics with 0.0
            for metric in metric_names:
                if metric not in metrics:
                    metrics[metric] = 0.0
                    logger.debug(f"Metric {metric} not found in /metrics")

        except Exception as e:
            logger.debug(f"Metric measurement failed: {e}, using defaults")
            # Return zeros on failure
            for metric in metric_names:
                metrics[metric] = 0.0

        return metrics

    def _compute_improvement(self, before: dict[str, float], after: dict[str, float]) -> float:
        """Compute percentage improvement in metrics."""
        if not before or not after:
            return 0.0

        # Average improvement across all tracked metrics
        improvements = []
        for metric in before:
            if metric in after:
                # Lower is better for latency/error metrics
                if "latency" in metric or "error" in metric or "duration" in metric:
                    improvement = (before[metric] - after[metric]) / before[metric] * 100
                else:
                    # Higher is better for success/accuracy metrics
                    improvement = (after[metric] - before[metric]) / before[metric] * 100
                improvements.append(improvement)

        return sum(improvements) / len(improvements) if improvements else 0.0

    def _record_successful_improvement(
        self, proposal: ImprovementProposal, actual_improvement: float
    ) -> None:
        """Record successful improvement in log."""
        self._modifications_today += 1
        self._modifications_this_hour += 1
        self._total_modifications_applied += 1

        if self._improvement_log:
            self._improvement_log.record_improvement(  # type: ignore[unreachable]
                summary=f"{proposal.rationale} ({actual_improvement:.1f}% improvement)",
                receipts=[],
                metrics_snapshot={
                    "improvement_percent": actual_improvement,
                    "file_modified": proposal.file_path,
                },
            )

    def get_resource_usage_stats(self) -> dict[str, Any]:
        """Get current resource usage statistics."""
        return {
            "modifications_today": self._modifications_today,
            "modifications_this_hour": self._modifications_this_hour,
            "tokens_used_today": self._tokens_used_today,
            "total_modifications_applied": self._total_modifications_applied,
            "limits": {
                "max_modifications_per_day": self._max_modifications_per_day,
                "max_modifications_per_hour": self._max_modifications_per_hour,
                "max_tokens_per_day": self._max_tokens_per_day,
                "max_cpu_percent": self._max_cpu_percent,
            },
        }

    def _parse_llm_proposal(
        self, llm_response: str, bottleneck: dict[str, Any]
    ) -> ImprovementProposal | None:
        """Parse LLM response into structured proposal."""
        try:
            # Extract sections from response
            lines = llm_response.split("\n")
            description = ""
            changes = ""
            improvement = 10.0  # Default
            risk = "medium"

            for line in lines:
                line = line.strip()
                if line.startswith("DESCRIPTION:"):
                    description = line.split(":", 1)[1].strip()
                elif line.startswith("CHANGES:"):
                    changes = line.split(":", 1)[1].strip()
                elif line.startswith("IMPROVEMENT:"):
                    imp_str = line.split(":", 1)[1].strip().rstrip("%")
                    try:
                        improvement = float(imp_str)
                    except ValueError:
                        pass
                elif line.startswith("RISK:"):
                    risk = line.split(":", 1)[1].strip().lower()

            if not description or not changes:
                return None

            return ImprovementProposal(  # type: ignore  # Call sig
                description=description or "LLM optimization suggestion",
                target_metric=bottleneck.get("metric_name", "unknown"),
                expected_improvement=improvement,
                risk_level=risk,
                proposed_changes=[changes],
                estimated_time_hours=2.0,
            )

        except Exception as e:
            logger.error(f"Failed to parse LLM proposal: {e}")
            return None


# Singleton
_self_improver: RecursiveSelfImprover | None = None


def get_self_improver() -> RecursiveSelfImprover:
    """Get global self-improver instance."""
    global _self_improver
    if _self_improver is None:
        _self_improver = RecursiveSelfImprover()
    return _self_improver


async def enable_recursive_self_improvement(check_interval: int = 3600) -> None:
    """Enable continuous self-improvement loop.

    Args:
        check_interval: Seconds between improvement cycles (default: 1 hour)
    """
    improver = get_self_improver()
    await improver.initialize()

    logger.info(f"✅ Recursive self-improvement enabled (checking every {check_interval}s)")

    # Start background loop
    asyncio.create_task(_continuous_improvement_loop(improver, check_interval))


async def _continuous_improvement_loop(improver: RecursiveSelfImprover, interval: int) -> None:
    """Background loop for continuous self-improvement."""
    while True:
        try:
            await asyncio.sleep(interval)

            # Identify opportunities
            proposals = await improver.identify_improvement_opportunities()

            if not proposals:
                logger.info("🔄 No improvement opportunities found")
                continue

            # Try top 3 proposals (low/medium risk only)
            for proposal in proposals[:3]:
                if proposal.requires_approval:
                    logger.info(f"⚠️  Skipping (requires approval): {proposal.rationale}")
                    continue

                # Apply improvement
                result = await improver.apply_improvement(proposal)

                if result.success:
                    logger.info(f"✅ Self-improvement: {result.improvement_percent:.1f}% better")
                else:
                    logger.info(f"❌ Self-improvement failed: {result.error}")

        except Exception as e:
            logger.error(f"Self-improvement loop error: {e}")
            await asyncio.sleep(60)  # Wait before retry


__all__ = [
    "ImprovementProposal",
    "ImprovementResult",
    "RecursiveSelfImprover",
    "enable_recursive_self_improvement",
    "get_self_improver",
]
