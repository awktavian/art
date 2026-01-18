"""CI Feedback Bridge - Connects CI reports to Continuous Evolution Engine.

This module enables continuous background improvement by:
1. Parsing CI workflow reports (test failures, lint errors, coverage gaps)
2. Converting CI signals into actionable improvement proposals
3. Feeding proposals to ContinuousEvolutionEngine for autonomous fixing
4. Learning from successful/failed fixes to improve future suggestions

Architecture:
    CI Reports → CIFeedbackBridge → ContinuousEvolutionEngine → Auto-Fix PRs

Usage:
    from kagami.core.evolution.ci_feedback_bridge import get_ci_feedback_bridge

    bridge = await get_ci_feedback_bridge()
    await bridge.process_ci_report(report_json)
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CISignalType(Enum):
    """Types of CI signals that can be processed."""

    TEST_FAILURE = "test_failure"
    LINT_ERROR = "lint_error"
    TYPE_ERROR = "type_error"
    COVERAGE_GAP = "coverage_gap"
    SECURITY_ISSUE = "security_issue"
    PERFORMANCE_REGRESSION = "performance_regression"
    BUILD_ERROR = "build_error"
    DEPENDENCY_ISSUE = "dependency_issue"


@dataclass
class CISignal:
    """A single actionable signal from CI."""

    signal_type: CISignalType
    file_path: str
    line_number: int | None
    message: str
    severity: str  # critical, high, medium, low
    raw_output: str
    fix_suggestion: str | None = None
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signal_type": self.signal_type.value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "message": self.message,
            "severity": self.severity,
            "fix_suggestion": self.fix_suggestion,
            "confidence": self.confidence,
        }


@dataclass
class CIReport:
    """Structured CI report."""

    workflow_name: str
    workflow_run_id: str
    commit_sha: str
    branch: str
    status: str  # success, failure, cancelled
    signals: list[CISignal] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    duration_seconds: float = 0.0

    @property
    def has_actionable_signals(self) -> bool:
        """Check if report has signals that can be acted on."""
        return len(self.signals) > 0

    @property
    def high_priority_count(self) -> int:
        """Count high-priority signals."""
        return sum(1 for s in self.signals if s.severity in ("critical", "high"))


class CIReportParser:
    """Parses various CI output formats into structured CIReport."""

    # Regex patterns for common CI output formats
    PYTEST_FAILURE = re.compile(
        r"FAILED\s+(\S+)::(\S+)\s*-\s*(.+?)$",
        re.MULTILINE,
    )
    RUFF_ERROR = re.compile(
        r"(\S+\.py):(\d+):(\d+):\s+(\w+)\s+(.+)$",
        re.MULTILINE,
    )
    MYPY_ERROR = re.compile(
        r"(\S+\.py):(\d+):\s+error:\s+(.+)$",
        re.MULTILINE,
    )
    COVERAGE_GAP = re.compile(
        r"(\S+\.py)\s+\d+\s+\d+\s+(\d+)%",
        re.MULTILINE,
    )

    def parse_workflow_output(
        self,
        workflow_name: str,
        output: str,
        metadata: dict[str, Any],
    ) -> CIReport:
        """Parse workflow output into structured report.

        Args:
            workflow_name: Name of the CI workflow
            output: Raw output text from workflow
            metadata: Workflow metadata (run_id, commit_sha, etc.)

        Returns:
            Structured CIReport
        """
        report = CIReport(
            workflow_name=workflow_name,
            workflow_run_id=metadata.get("run_id", "unknown"),
            commit_sha=metadata.get("commit_sha", "unknown"),
            branch=metadata.get("branch", "main"),
            status=metadata.get("status", "unknown"),
            duration_seconds=metadata.get("duration", 0.0),
        )

        # Parse based on workflow type
        if "test" in workflow_name.lower() or "pytest" in output.lower():
            self._parse_pytest_output(output, report)

        if "lint" in workflow_name.lower() or "ruff" in output.lower():
            self._parse_ruff_output(output, report)

        if "type" in workflow_name.lower() or "mypy" in output.lower():
            self._parse_mypy_output(output, report)

        if "coverage" in workflow_name.lower():
            self._parse_coverage_output(output, report)

        if "security" in workflow_name.lower() or "bandit" in output.lower():
            self._parse_security_output(output, report)

        return report

    def _parse_pytest_output(self, output: str, report: CIReport) -> None:
        """Parse pytest failures."""
        for match in self.PYTEST_FAILURE.finditer(output):
            file_path = match.group(1)
            test_name = match.group(2)
            error_msg = match.group(3)

            report.signals.append(
                CISignal(
                    signal_type=CISignalType.TEST_FAILURE,
                    file_path=file_path,
                    line_number=None,  # Would need to parse further
                    message=f"Test {test_name} failed: {error_msg}",
                    severity="high",
                    raw_output=match.group(0),
                )
            )

    def _parse_ruff_output(self, output: str, report: CIReport) -> None:
        """Parse ruff lint errors."""
        for match in self.RUFF_ERROR.finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))
            rule_id = match.group(4)
            message = match.group(5)

            # Determine severity based on rule ID
            severity = "medium"
            if rule_id.startswith(("E9", "F")):  # Syntax/fatal errors
                severity = "high"
            elif rule_id.startswith(("W", "C")):  # Warnings/conventions
                severity = "low"

            report.signals.append(
                CISignal(
                    signal_type=CISignalType.LINT_ERROR,
                    file_path=file_path,
                    line_number=line_num,
                    message=f"[{rule_id}] {message}",
                    severity=severity,
                    raw_output=match.group(0),
                )
            )

    def _parse_mypy_output(self, output: str, report: CIReport) -> None:
        """Parse mypy type errors."""
        for match in self.MYPY_ERROR.finditer(output):
            file_path = match.group(1)
            line_num = int(match.group(2))
            message = match.group(3)

            report.signals.append(
                CISignal(
                    signal_type=CISignalType.TYPE_ERROR,
                    file_path=file_path,
                    line_number=line_num,
                    message=message,
                    severity="medium",
                    raw_output=match.group(0),
                )
            )

    def _parse_coverage_output(self, output: str, report: CIReport) -> None:
        """Parse coverage gaps."""
        for match in self.COVERAGE_GAP.finditer(output):
            file_path = match.group(1)
            coverage_pct = int(match.group(2))

            if coverage_pct < 70:  # Below threshold
                severity = "high" if coverage_pct < 50 else "medium"
                report.signals.append(
                    CISignal(
                        signal_type=CISignalType.COVERAGE_GAP,
                        file_path=file_path,
                        line_number=None,
                        message=f"Coverage at {coverage_pct}% (below 70% threshold)",
                        severity=severity,
                        raw_output=match.group(0),
                    )
                )

    def _parse_security_output(self, output: str, report: CIReport) -> None:
        """Parse security scan output (bandit, safety, etc.)."""
        # Parse bandit JSON if present
        if '"issue_severity"' in output:
            try:
                # Try to extract JSON portion
                json_start = output.find("[")
                json_end = output.rfind("]") + 1
                if json_start >= 0 and json_end > json_start:
                    issues = json.loads(output[json_start:json_end])
                    for issue in issues:
                        report.signals.append(
                            CISignal(
                                signal_type=CISignalType.SECURITY_ISSUE,
                                file_path=issue.get("filename", "unknown"),
                                line_number=issue.get("line_number"),
                                message=issue.get("issue_text", "Security issue"),
                                severity=issue.get("issue_severity", "medium").lower(),
                                raw_output=str(issue),
                            )
                        )
            except json.JSONDecodeError:
                pass


@dataclass
class ImprovementProposal:
    """Proposal for code improvement based on CI signal."""

    proposal_id: str
    signal: CISignal
    file_path: str
    rationale: str
    expected_improvement: str
    risk_level: str  # low, medium, high
    suggested_fix: str | None = None
    category: str = "ci_autofix"
    metrics_to_track: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "file_path": self.file_path,
            "rationale": self.rationale,
            "expected_improvement": self.expected_improvement,
            "risk_level": self.risk_level,
            "suggested_fix": self.suggested_fix,
            "category": self.category,
            "signal": self.signal.to_dict(),
        }


class CIFeedbackBridge:
    """Bridge between CI reports and ContinuousEvolutionEngine.

    This is the key integration point that enables continuous background
    improvement based on CI failures and reports.
    """

    def __init__(self) -> None:
        self._parser = CIReportParser()
        self._evolution_engine: Any = None
        self._processed_reports: list[CIReport] = []
        self._proposal_history: list[ImprovementProposal] = []

        # Statistics
        self._stats = {
            "reports_processed": 0,
            "signals_extracted": 0,
            "proposals_generated": 0,
            "proposals_applied": 0,
            "proposals_successful": 0,
        }

        # Configuration
        self._auto_fix_enabled = True
        self._min_confidence_threshold = 0.6
        self._max_proposals_per_report = 5

    async def initialize(self) -> None:
        """Initialize bridge and connect to evolution engine."""
        logger.info("🔗 Initializing CI Feedback Bridge...")

        # Connect to evolution engine
        try:
            from kagami.core.evolution.continuous_evolution_engine import (
                get_evolution_engine,
            )

            self._evolution_engine = await get_evolution_engine()
            logger.info("✅ Connected to ContinuousEvolutionEngine")
        except Exception as e:
            logger.warning(f"⚠️ Could not connect to evolution engine: {e}")
            self._evolution_engine = None

    async def process_ci_report(
        self,
        report_json: dict[str, Any] | str,
    ) -> list[ImprovementProposal]:
        """Process a CI report and generate improvement proposals.

        Args:
            report_json: CI report as JSON dict or string

        Returns:
            List of generated improvement proposals
        """
        # Parse if string
        if isinstance(report_json, str):
            try:
                report_json = json.loads(report_json)
            except json.JSONDecodeError:
                # Treat as raw output
                report_json = {
                    "workflow_name": "unknown",
                    "output": report_json,
                }

        # Extract workflow output
        workflow_name = report_json.get("workflow_name", "ci")
        output = report_json.get("output", "")
        metadata = {
            "run_id": report_json.get("run_id", str(time.time())),
            "commit_sha": report_json.get("commit_sha", "unknown"),
            "branch": report_json.get("branch", "main"),
            "status": report_json.get("status", "failure"),
            "duration": report_json.get("duration", 0.0),
        }

        # Parse into structured report
        report = self._parser.parse_workflow_output(workflow_name, output, metadata)

        self._processed_reports.append(report)
        self._stats["reports_processed"] += 1
        self._stats["signals_extracted"] += len(report.signals)

        logger.info(
            f"📊 Processed CI report: {workflow_name} "
            f"({len(report.signals)} signals, {report.high_priority_count} high priority)"
        )

        # Generate improvement proposals
        proposals = await self._generate_proposals(report)

        # If auto-fix enabled and evolution engine available, submit proposals
        if self._auto_fix_enabled and self._evolution_engine and proposals:
            await self._submit_to_evolution_engine(proposals)

        return proposals

    async def _generate_proposals(self, report: CIReport) -> list[ImprovementProposal]:
        """Generate improvement proposals from CI report.

        Uses Claude API (if available) for intelligent fix suggestions.
        """
        proposals = []

        for signal in report.signals[: self._max_proposals_per_report]:
            proposal = await self._signal_to_proposal(signal, report)
            if proposal and proposal.suggested_fix:
                proposals.append(proposal)
                self._proposal_history.append(proposal)
                self._stats["proposals_generated"] += 1

        return proposals

    async def _signal_to_proposal(
        self,
        signal: CISignal,
        report: CIReport,
    ) -> ImprovementProposal | None:
        """Convert a CI signal to an improvement proposal.

        Attempts to use Claude API for intelligent fix generation.
        """
        proposal_id = f"ci-{report.workflow_run_id}-{signal.signal_type.value}-{time.time():.0f}"

        # Try to generate fix using Claude API
        suggested_fix = await self._generate_fix_with_llm(signal)

        # Determine risk level based on signal type and severity
        risk_level = self._determine_risk_level(signal)

        return ImprovementProposal(
            proposal_id=proposal_id,
            signal=signal,
            file_path=signal.file_path,
            rationale=f"Fix {signal.signal_type.value}: {signal.message}",
            expected_improvement=self._estimate_improvement(signal),
            risk_level=risk_level,
            suggested_fix=suggested_fix,
            metrics_to_track=self._get_metrics_to_track(signal),
        )

    async def _generate_fix_with_llm(self, signal: CISignal) -> str | None:
        """Generate fix suggestion using Claude API.

        Falls back to rule-based suggestions if LLM unavailable.
        """
        try:
            # Try to read the file content for context
            file_content = ""
            if Path(signal.file_path).exists():
                file_content = Path(signal.file_path).read_text()[:2000]

            # Try Claude API
            try:
                import anthropic

                client = anthropic.Anthropic()

                prompt = self._build_fix_prompt(signal, file_content)

                response = client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                )

                fix = response.content[0].text
                logger.info(f"🤖 Generated fix using Claude API for {signal.file_path}")
                return fix

            except ImportError:
                logger.debug("anthropic package not available, using rule-based fixes")
            except Exception as e:
                logger.warning(f"Claude API error: {e}, falling back to rule-based")

            # Fall back to rule-based suggestions
            return self._generate_rule_based_fix(signal)

        except Exception as e:
            logger.warning(f"Fix generation failed: {e}")
            return None

    def _build_fix_prompt(self, signal: CISignal, file_content: str) -> str:
        """Build prompt for LLM fix generation."""
        return f"""You are a senior Python developer fixing a CI error.

ERROR TYPE: {signal.signal_type.value}
FILE: {signal.file_path}
LINE: {signal.line_number or "unknown"}
ERROR MESSAGE: {signal.message}

RAW CI OUTPUT:
{signal.raw_output[:500]}

RELEVANT FILE CONTENT (first 2000 chars):
{file_content}

Please provide a MINIMAL fix that:
1. Directly addresses the error
2. Follows existing code style
3. Doesn't introduce new complexity

Respond with ONLY the code fix (no explanation). If it's a single line, show the corrected line.
If it requires multiple lines, show the complete corrected function/block."""

    def _generate_rule_based_fix(self, signal: CISignal) -> str | None:
        """Generate fix using rule-based patterns."""
        if signal.signal_type == CISignalType.LINT_ERROR:
            # Common lint fixes
            if "F401" in signal.message:  # Unused import
                return f"# Remove unused import at line {signal.line_number}"
            elif "E501" in signal.message:  # Line too long
                return f"# Split line {signal.line_number} to be under 120 characters"
            elif "W503" in signal.message:  # Line break before binary operator
                return f"# Move operator to end of line {signal.line_number - 1}"

        elif signal.signal_type == CISignalType.TYPE_ERROR:
            if "has no attribute" in signal.message:
                return f"# Add Optional[] wrapper or None check at line {signal.line_number}"
            elif "incompatible type" in signal.message:
                return f"# Cast or convert type at line {signal.line_number}"

        elif signal.signal_type == CISignalType.TEST_FAILURE:
            return f"# Review test logic and assertions in {signal.file_path}"

        return None

    def _determine_risk_level(self, signal: CISignal) -> str:
        """Determine risk level for a fix."""
        # Lower risk for lint/type fixes
        if signal.signal_type in (CISignalType.LINT_ERROR, CISignalType.TYPE_ERROR):
            return "low"

        # Medium risk for test fixes
        if signal.signal_type == CISignalType.TEST_FAILURE:
            return "medium"

        # Higher risk for security/build
        if signal.signal_type in (CISignalType.SECURITY_ISSUE, CISignalType.BUILD_ERROR):
            return "high"

        return "medium"

    def _estimate_improvement(self, signal: CISignal) -> str:
        """Estimate improvement from fixing this signal."""
        improvements = {
            CISignalType.TEST_FAILURE: "Fix failing test, restore CI green status",
            CISignalType.LINT_ERROR: "Improve code quality score by 1-2 points",
            CISignalType.TYPE_ERROR: "Improve type safety, catch runtime errors",
            CISignalType.COVERAGE_GAP: "Increase test coverage by 1-5%",
            CISignalType.SECURITY_ISSUE: "Eliminate security vulnerability",
            CISignalType.PERFORMANCE_REGRESSION: "Restore performance baseline",
            CISignalType.BUILD_ERROR: "Fix build, enable deployment",
            CISignalType.DEPENDENCY_ISSUE: "Update dependencies, fix compatibility",
        }
        return improvements.get(signal.signal_type, "Improve code quality")

    def _get_metrics_to_track(self, signal: CISignal) -> list[str]:
        """Get metrics to track for this signal type."""
        metrics = {
            CISignalType.TEST_FAILURE: ["test_pass_rate", "ci_success_rate"],
            CISignalType.LINT_ERROR: ["lint_violations", "code_quality_score"],
            CISignalType.TYPE_ERROR: ["type_coverage", "mypy_errors"],
            CISignalType.COVERAGE_GAP: ["test_coverage_percent"],
            CISignalType.SECURITY_ISSUE: ["security_vulnerabilities"],
            CISignalType.PERFORMANCE_REGRESSION: ["response_time_p95", "throughput"],
        }
        return metrics.get(signal.signal_type, ["ci_success_rate"])

    async def _submit_to_evolution_engine(
        self,
        proposals: list[ImprovementProposal],
    ) -> None:
        """Submit proposals to ContinuousEvolutionEngine for processing."""
        if not self._evolution_engine:
            logger.warning("Evolution engine not available")
            return

        logger.info(f"🚀 Submitting {len(proposals)} proposals to evolution engine")

        for proposal in proposals:
            try:
                # Convert to format expected by evolution engine
                improvement = {
                    "file": proposal.file_path,
                    "rationale": proposal.rationale,
                    "expected_improvement": proposal.expected_improvement,
                    "risk": proposal.risk_level,
                    "proposal": proposal,
                    "source": "ci_feedback_bridge",
                }

                # The evolution engine's _phase_improve can receive these
                # via the experience store or direct injection
                from kagami.core.coordination.experience_store import get_experience_store

                store = get_experience_store()
                await store.record(
                    event_type="ci_improvement_proposal",
                    data=improvement,
                    metadata={"auto_generated": True},
                )

                self._stats["proposals_applied"] += 1

                # === NEXUS ENHANCEMENT (Jan 5, 2026) ===
                # Direct injection into evolution engine if available
                if self._evolution_engine is not None:
                    try:
                        # Inject directly for faster processing
                        if hasattr(self._evolution_engine, "inject_improvement"):
                            await self._evolution_engine.inject_improvement(improvement)
                            logger.info("🔗 Directly injected CI proposal to evolution engine")
                    except Exception as e:
                        logger.debug(f"Direct injection skipped: {e}")

                # Create Linear issue if high priority (Jan 5, 2026)
                if proposal.risk_level in ["critical", "high"]:
                    await self._create_linear_issue_for_proposal(proposal)

            except Exception as e:
                logger.error(f"Failed to submit proposal: {e}")

    async def process_github_webhook(
        self,
        webhook_payload: dict[str, Any],
    ) -> list[ImprovementProposal]:
        """Process a GitHub webhook payload (workflow_run event).

        This can be called from a webhook endpoint to enable
        real-time CI feedback processing.
        """
        action = webhook_payload.get("action")
        workflow_run = webhook_payload.get("workflow_run", {})

        # Only process completed runs
        if action != "completed":
            return []

        # Only process failed runs
        if workflow_run.get("conclusion") not in ("failure", "timed_out"):
            logger.debug(f"Skipping successful run: {workflow_run.get('name')}")
            return []

        # Build report from webhook
        report_json = {
            "workflow_name": workflow_run.get("name", "unknown"),
            "run_id": str(workflow_run.get("id")),
            "commit_sha": workflow_run.get("head_sha", "unknown"),
            "branch": workflow_run.get("head_branch", "main"),
            "status": workflow_run.get("conclusion", "failure"),
            "output": "",  # Need to fetch logs separately
        }

        # Try to fetch run logs
        try:
            run_id = workflow_run.get("id")
            if run_id:
                logs = await self._fetch_workflow_logs(run_id)
                report_json["output"] = logs
        except Exception as e:
            logger.warning(f"Could not fetch workflow logs: {e}")

        return await self.process_ci_report(report_json)

    async def _fetch_workflow_logs(self, run_id: int) -> str:
        """Fetch workflow logs from GitHub API.

        Requires GITHUB_TOKEN environment variable.
        """
        import os

        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            return ""

        try:
            import aiohttp

            # Get repo from git remote
            repo = "schizodactyl/kagami"  # Could be dynamic

            headers = {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            }

            async with aiohttp.ClientSession() as session:
                # Get jobs for this run
                jobs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
                async with session.get(jobs_url, headers=headers) as resp:
                    if resp.status != 200:
                        return ""
                    jobs_data = await resp.json()

                # Get logs from failed jobs
                logs = []
                for job in jobs_data.get("jobs", []):
                    if job.get("conclusion") == "failure":
                        log_url = (
                            f"https://api.github.com/repos/{repo}/actions/jobs/{job['id']}/logs"
                        )
                        async with session.get(log_url, headers=headers) as log_resp:
                            if log_resp.status == 200:
                                logs.append(await log_resp.text())

                return "\n".join(logs)

        except Exception as e:
            logger.warning(f"Failed to fetch logs: {e}")
            return ""

    async def _create_linear_issue_for_proposal(self, proposal: ImprovementProposal) -> None:
        """Create Linear issue for high-priority CI proposals (Nexus - Jan 5, 2026).

        Integrates CI failures with Linear for tracking.
        """
        try:
            from kagami.core.services.composio import get_composio_service

            composio = get_composio_service()
            if not composio._initialized:
                await composio.initialize()

            # Create issue with self-improvement label
            result = await composio.execute_action(
                "LINEAR_CREATE_LINEAR_ISSUE",
                {
                    "team_id": "e0d50215-abaa-452a-b2c4-791869719633",  # AWK team
                    "title": f"[CI-Fix] {proposal.signal.message[:80]}",
                    "description": f"""## CI Failure Auto-Generated Issue

**File:** {proposal.file_path}
**Signal Type:** {proposal.signal.signal_type.value}
**Risk Level:** {proposal.risk_level}
**Priority:** {"Urgent" if proposal.risk_level == "critical" else "High"}

### Error Message
```
{proposal.signal.message}
```

### Suggested Fix
```
{proposal.suggested_fix or "See rationale below"}
```

### Rationale
{proposal.rationale}

### Expected Improvement
{proposal.expected_improvement}

---
*Auto-generated by CI Feedback Bridge (Gödel Self-Improvement Loop)*
""",
                    "label_ids": ["self-improvement", "ci-failure"],
                    "priority": 1 if proposal.risk_level == "critical" else 2,
                },
            )

            if result.get("success"):
                logger.info(f"📋 Created Linear issue for CI proposal: {proposal.file_path}")
                self._stats["linear_issues_created"] = (
                    self._stats.get("linear_issues_created", 0) + 1
                )
            else:
                logger.debug(f"Linear issue creation skipped: {result.get('error')}")

        except Exception as e:
            logger.debug(f"Linear issue creation failed: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get bridge statistics."""
        return {
            **self._stats,
            "reports_in_memory": len(self._processed_reports),
            "proposals_in_memory": len(self._proposal_history),
            "auto_fix_enabled": self._auto_fix_enabled,
            "evolution_engine_connected": self._evolution_engine is not None,
        }

    def get_recent_proposals(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent improvement proposals."""
        return [p.to_dict() for p in self._proposal_history[-limit:]]


# Singleton
_ci_feedback_bridge: CIFeedbackBridge | None = None


async def get_ci_feedback_bridge() -> CIFeedbackBridge:
    """Get or create CI feedback bridge."""
    global _ci_feedback_bridge
    if _ci_feedback_bridge is None:
        _ci_feedback_bridge = CIFeedbackBridge()
        await _ci_feedback_bridge.initialize()
    return _ci_feedback_bridge


__all__ = [
    "CIFeedbackBridge",
    "CIReport",
    "CIReportParser",
    "CISignal",
    "CISignalType",
    "ImprovementProposal",
    "get_ci_feedback_bridge",
]
