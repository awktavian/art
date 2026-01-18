from __future__ import annotations

"""Philosophical Layer: Question & Reconceptualize fundamental assumptions."""
import logging
from dataclasses import dataclass
from typing import Any

from .scientific_layer import AnalysisReport, FailurePattern

logger = logging.getLogger(__name__)


@dataclass
class ParadigmAssessment:
    """Assessment of current architectural paradigm."""

    current_paradigm_viable: bool
    reason: str
    proposed_paradigms: list[str] | None = None
    required_changes: list[str] | None = None


@dataclass
class ParadigmShift:
    """Proposal for fundamental architectural change."""

    trigger: str
    current_assumption: str
    proposed_shift: str
    research_citations: list[str]
    estimated_impact: str  # "high"|"medium"|"low"
    risk_level: str  # "high"|"medium"|"low"


@dataclass
class ConstitutionalViolation:
    """Violation of constitutional constraints."""

    principle: str
    severity: str  # "critical"|"high"|"medium"|"low"
    description: str
    examples: list[dict[str, Any]]


class PhilosophicalLayer:
    """Questions assumptions and proposes fundamental changes.

    This layer evaluates whether the current approach is
    fundamentally sound or requires paradigmatic shifts.
    """

    def __init__(self) -> None:
        self._constitution = self._load_constitution()
        self._paradigm_history: list[ParadigmShift] = []

    def _load_constitution(self) -> list[dict[str, Any]]:
        """Load constitutional principles."""
        return [
            {
                "name": "idempotency",
                "description": "All mutations must be idempotent",
                "severity": "critical",
            },
            {
                "name": "receipts",
                "description": "All operations must emit receipts",
                "severity": "high",
            },
            {
                "name": "full_operation",
                "description": "All mandatory components must be operational",
                "severity": "critical",
            },
            {
                "name": "safety",
                "description": "Safety constraints h(x) >= 0 must hold",
                "severity": "critical",
            },
            {
                "name": "transparency",
                "description": "Decisions must be explainable",
                "severity": "medium",
            },
        ]

    async def evaluate_paradigm(self, scientific_report: AnalysisReport) -> ParadigmAssessment:
        """Determine if current approach is fundamentally flawed."""
        logger.info("Philosophical Layer: Evaluating current paradigm")

        # Check for persistent failures
        persistent_issues = [
            pattern
            for pattern in scientific_report.failure_patterns
            if pattern.occurrences > 10 and pattern.duration_days > 7
        ]

        if len(persistent_issues) >= 3:
            # Current paradigm failing
            alternatives = await self._generate_alternative_architectures(persistent_issues)
            return ParadigmAssessment(
                current_paradigm_viable=False,
                reason=f"Found {len(persistent_issues)} persistent failure patterns "
                "suggesting architectural mismatch",
                proposed_paradigms=alternatives,
            )

        # Evaluate constitutional alignment
        violations = await self._check_constitutional_violations(scientific_report)
        if violations:
            return ParadigmAssessment(
                current_paradigm_viable=False,
                reason=f"Detected {len(violations)} constitutional violations",
                required_changes=[v.description for v in violations],
            )

        # Check performance trends
        if scientific_report.performance_trends.get("error_rate", 0) > 0.10:
            return ParadigmAssessment(
                current_paradigm_viable=False,
                reason="Error rate exceeds 10% - fundamental reliability issue",
                proposed_paradigms=[
                    "Circuit breaker pattern",
                    "Bulkhead isolation",
                    "Graceful degradation",
                ],
            )

        return ParadigmAssessment(
            current_paradigm_viable=True,
            reason="System operating within acceptable parameters",
        )

    async def propose_paradigm_shift(
        self, assessment: ParadigmAssessment, patterns: list[FailurePattern]
    ) -> ParadigmShift | None:
        """When needed, propose fundamental architectural change."""
        if assessment.current_paradigm_viable:
            return None

        logger.info("Philosophical Layer: Proposing paradigm shift")

        # Analyze failure modes to determine shift
        if any("timeout" in p.error_type.lower() for p in patterns):
            return ParadigmShift(
                trigger="Repeated timeout failures",
                current_assumption="Synchronous request-response is sufficient",
                proposed_shift="Adopt async event-driven architecture with message queues",
                research_citations=[
                    "Hohpe & Woolf: Enterprise Integration Patterns",
                    "Newman: Building Microservices",
                ],
                estimated_impact="high",
                risk_level="medium",
            )

        elif any("database" in p.error_type.lower() for p in patterns):
            return ParadigmShift(
                trigger="Repeated database failures",
                current_assumption="Single database is optimal",
                proposed_shift="CQRS with read replicas or event sourcing",
                research_citations=[
                    "Martin Fowler: CQRS Pattern",
                    "Kleppmann: Designing Data-Intensive Applications",
                ],
                estimated_impact="high",
                risk_level="high",
            )

        elif len(patterns) > 5:
            return ParadigmShift(
                trigger="High diversity of failure modes",
                current_assumption="Monolithic orchestration is sufficient",
                proposed_shift="Service mesh with independent failure domains",
                research_citations=[
                    "Richardson: Microservices Patterns",
                    "Newman: Monolith to Microservices",
                ],
                estimated_impact="high",
                risk_level="high",
            )

        return None

    async def _generate_alternative_architectures(
        self, patterns: list[FailurePattern]
    ) -> list[str]:
        """Generate alternative architectural approaches."""
        alternatives = []

        # Event-driven architecture
        if any("sync" in p.route.lower() for p in patterns):
            alternatives.append("Event-driven architecture with async message bus")

        # Actor model
        if any("concurrent" in p.error_type.lower() for p in patterns):
            alternatives.append("Actor model for isolated concurrent execution")

        # Microservices
        if len({p.route for p in patterns}) > 10:
            alternatives.append("Decompose into independent microservices")

        # CQRS
        if any("read" in p.route.lower() or "write" in p.route.lower() for p in patterns):
            alternatives.append("CQRS to separate read and write paths")

        return alternatives

    async def _check_constitutional_violations(
        self, report: AnalysisReport
    ) -> list[ConstitutionalViolation]:
        """Check for violations of core principles."""
        violations = []

        # Check idempotency violations
        idempotency_failures = [
            p
            for p in report.failure_patterns
            if "duplicate" in p.error_type.lower() or "idempotency" in p.error_type.lower()
        ]
        if idempotency_failures:
            violations.append(
                ConstitutionalViolation(
                    principle="idempotency",
                    severity="critical",
                    description="Idempotency failures detected",
                    examples=[
                        {
                            "route": p.route,
                            "occurrences": p.occurrences,
                        }
                        for p in idempotency_failures[:3]
                    ],
                )
            )

        # Check receipt emission
        if report.performance_trends.get("receipts_missing", 0) > 0.05:
            violations.append(
                ConstitutionalViolation(
                    principle="receipts",
                    severity="high",
                    description="More than 5% of operations missing receipts",
                    examples=[],
                )
            )

        # Check safety constraints
        safety_failures = [p for p in report.failure_patterns if "safety" in p.error_type.lower()]
        if safety_failures:
            violations.append(
                ConstitutionalViolation(
                    principle="safety",
                    severity="critical",
                    description="Safety constraint violations detected",
                    examples=[
                        {"route": p.route, "occurrences": p.occurrences} for p in safety_failures
                    ],
                )
            )

        return violations

    def question_assumption(self, assumption: str) -> dict[str, Any]:
        """Question a specific assumption."""
        logger.info(f"Questioning assumption: {assumption}")

        # Socratic questioning framework
        questions = {
            "clarification": f"What exactly do we mean by '{assumption}'?",
            "probe_assumption": f"What are we assuming when we say '{assumption}'?",
            "probe_evidence": f"What evidence supports '{assumption}'?",
            "alternative_viewpoint": f"What would someone who disagrees with '{assumption}' say?",
            "implications": f"What are the consequences if '{assumption}' is wrong?",
            "meta_question": f"Why is the question about '{assumption}' important?",
        }

        return {
            "assumption": assumption,
            "socratic_questions": questions,
            "recommendation": "Investigate evidence and consider alternatives",
        }
