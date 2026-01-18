"""Flow Diagnosis Module — Root Cause Analysis.

Provides diagnostic capabilities:
- Symptom analysis
- Root cause identification
- Hypothesis generation
- Evidence collection

Created: December 28, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CauseCategory(Enum):
    """Categories of root causes."""

    CODE = "code"  # Bug, regression
    CONFIG = "configuration"  # Misconfiguration
    CAPACITY = "capacity"  # Resource exhaustion
    DEPENDENCY = "dependency"  # External dependency failure
    NETWORK = "network"  # Network issues
    DATA = "data"  # Data corruption, inconsistency
    SECURITY = "security"  # Security incident
    UNKNOWN = "unknown"


@dataclass
class RootCause:
    """An identified root cause."""

    description: str
    category: CauseCategory
    confidence: float  # 0-1
    evidence: list[str] = field(default_factory=list[Any])
    recommended_fix: str = ""


@dataclass
class Diagnosis:
    """Diagnosis result."""

    symptoms: list[str]
    hypotheses: list[RootCause]
    recommended_strategy: str
    confidence: float
    analysis_time_ms: float = 0.0
    metrics_checked: list[str] = field(default_factory=list[Any])
    flow_voice: str = ""

    def __post_init__(self) -> None:
        if not self.flow_voice and self.hypotheses:
            top_cause = self.hypotheses[0]
            self.flow_voice = (
                f"Let me trace this back... The symptoms point to "
                f"{top_cause.category.value}: {top_cause.description}. "
                f"I'm {top_cause.confidence:.0%} confident."
            )


# Symptom to cause mapping patterns
SYMPTOM_PATTERNS = {
    "high_latency": [
        RootCause(
            description="Database query performance degradation",
            category=CauseCategory.CODE,
            confidence=0.6,
            evidence=["Latency correlated with DB query time"],
            recommended_fix="Check slow query log, add indexes",
        ),
        RootCause(
            description="Resource exhaustion (CPU/memory)",
            category=CauseCategory.CAPACITY,
            confidence=0.5,
            evidence=["High resource utilization metrics"],
            recommended_fix="Scale up or optimize resource usage",
        ),
    ],
    "error_rate": [
        RootCause(
            description="Recent deployment introduced bug",
            category=CauseCategory.CODE,
            confidence=0.7,
            evidence=["Error rate increase correlates with deploy"],
            recommended_fix="Rollback deployment",
        ),
        RootCause(
            description="Dependency service failure",
            category=CauseCategory.DEPENDENCY,
            confidence=0.5,
            evidence=["Errors from external service calls"],
            recommended_fix="Enable circuit breaker, check dependency health",
        ),
    ],
    "service_down": [
        RootCause(
            description="Process crash due to OOM",
            category=CauseCategory.CAPACITY,
            confidence=0.6,
            evidence=["Memory usage spike before crash"],
            recommended_fix="Increase memory limit, fix memory leak",
        ),
        RootCause(
            description="Configuration error",
            category=CauseCategory.CONFIG,
            confidence=0.4,
            evidence=["Recent config change"],
            recommended_fix="Review and revert configuration",
        ),
    ],
    "data_inconsistency": [
        RootCause(
            description="Race condition in concurrent writes",
            category=CauseCategory.CODE,
            confidence=0.5,
            evidence=["Inconsistency correlates with high concurrency"],
            recommended_fix="Add proper locking/transactions",
        ),
        RootCause(
            description="Replication lag",
            category=CauseCategory.DATA,
            confidence=0.4,
            evidence=["Read-after-write inconsistency"],
            recommended_fix="Read from primary, increase replication",
        ),
    ],
}


def diagnose_issue(
    symptoms: list[str],
    context: dict[str, Any] | None = None,
) -> Diagnosis:
    """Diagnose an issue from symptoms.

    Analyzes symptoms and generates hypotheses about root causes.

    Args:
        symptoms: List of observed symptoms
        context: Additional context (service, metrics, recent changes)

    Returns:
        Diagnosis with hypotheses and recommendations

    Example:
        diagnosis = diagnose_issue(
            symptoms=["p99 latency > 500ms", "error rate up 5%"],
            context={"service": "api", "recent_deploy": True},
        )
    """
    import time

    start = time.perf_counter()

    context = context or {}
    hypotheses: list[RootCause] = []
    metrics_checked: list[str] = []

    # Normalize symptoms
    symptoms_lower = [s.lower() for s in symptoms]

    # Match symptoms to patterns
    for symptom in symptoms_lower:
        for pattern, causes in SYMPTOM_PATTERNS.items():
            if pattern.replace("_", " ") in symptom or pattern in symptom:
                hypotheses.extend(causes)
                metrics_checked.append(pattern)

    # Adjust confidence based on context
    if context.get("recent_deploy"):
        for h in hypotheses:
            if h.category == CauseCategory.CODE:
                h.confidence = min(1.0, h.confidence + 0.2)
                h.evidence.append("Recent deployment detected")

    if context.get("high_load"):
        for h in hypotheses:
            if h.category == CauseCategory.CAPACITY:
                h.confidence = min(1.0, h.confidence + 0.2)
                h.evidence.append("High load detected")

    # Remove duplicates and sort by confidence
    seen = set()
    unique_hypotheses = []
    for h in hypotheses:
        key = (h.description, h.category)
        if key not in seen:
            seen.add(key)
            unique_hypotheses.append(h)

    unique_hypotheses.sort(key=lambda h: h.confidence, reverse=True)

    # Determine recommended strategy
    if unique_hypotheses:
        top_cause = unique_hypotheses[0]
        if top_cause.category == CauseCategory.CODE:
            recommended = "rollback_deploy"
        elif top_cause.category == CauseCategory.CAPACITY:
            recommended = "scale_up"
        elif top_cause.category == CauseCategory.DEPENDENCY:
            recommended = "circuit_breaker"
        else:
            recommended = "restart_service"
    else:
        recommended = "restart_service"

    # Calculate overall confidence
    confidence = max(h.confidence for h in unique_hypotheses) if unique_hypotheses else 0.0

    return Diagnosis(
        symptoms=symptoms,
        hypotheses=unique_hypotheses[:5],  # Top 5 hypotheses
        recommended_strategy=recommended,
        confidence=confidence,
        analysis_time_ms=(time.perf_counter() - start) * 1000,
        metrics_checked=metrics_checked,
    )


def find_root_cause(
    symptoms: list[str],
    metrics: dict[str, float] | None = None,
    logs: list[str] | None = None,
) -> RootCause | None:
    """Find most likely root cause from symptoms and evidence.

    More detailed analysis using metrics and logs.

    Args:
        symptoms: Observed symptoms
        metrics: Relevant metrics values
        logs: Recent log entries

    Returns:
        Most likely RootCause or None
    """
    diagnosis = diagnose_issue(symptoms, context={"metrics": metrics})

    if not diagnosis.hypotheses:
        return None

    # Refine with metrics
    if metrics:
        for h in diagnosis.hypotheses:
            if h.category == CauseCategory.CAPACITY:
                if metrics.get("cpu_usage", 0) > 0.8:
                    h.confidence = min(1.0, h.confidence + 0.2)
                    h.evidence.append(f"CPU at {metrics['cpu_usage']:.0%}")
                if metrics.get("memory_usage", 0) > 0.9:
                    h.confidence = min(1.0, h.confidence + 0.2)
                    h.evidence.append(f"Memory at {metrics['memory_usage']:.0%}")

    # Refine with logs
    if logs:
        log_text = " ".join(logs).lower()
        for h in diagnosis.hypotheses:
            if "error" in log_text and h.category == CauseCategory.CODE:
                h.confidence = min(1.0, h.confidence + 0.1)
            if "timeout" in log_text and h.category == CauseCategory.DEPENDENCY:
                h.confidence = min(1.0, h.confidence + 0.1)

    # Re-sort and return top
    diagnosis.hypotheses.sort(key=lambda h: h.confidence, reverse=True)
    return diagnosis.hypotheses[0] if diagnosis.hypotheses else None


__all__ = [
    "CauseCategory",
    "Diagnosis",
    "RootCause",
    "diagnose_issue",
    "find_root_cause",
]
