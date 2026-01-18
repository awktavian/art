"""Flow Capability Layer — Operations Infrastructure.

Flow (e₃, Swallowtail catastrophe, A₄) is The Healer.
This package provides incident management, recovery, and diagnostic tools.

MODULES:
========
- incidents: Incident tracking and management
- recovery: Multi-path recovery strategies
- diagnosis: Root cause analysis

USAGE:
======
from kagami.flow import (
    create_incident,
    diagnose_issue,
    execute_recovery,
)

# Create incident
incident = create_incident(
    title="API latency spike",
    severity="high",
    symptoms=["p99 > 500ms", "error rate up"],
)

# Diagnose
diagnosis = diagnose_issue(
    symptoms=incident.symptoms,
    context={"service": "auth"},
)

# Execute recovery
result = await execute_recovery(
    strategy=diagnosis.recommended_strategy,
    incident=incident,
)

Created: December 28, 2025
"""

from kagami.flow.modules.diagnosis import (
    Diagnosis,
    RootCause,
    diagnose_issue,
    find_root_cause,
)
from kagami.flow.modules.incidents import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    create_incident,
    resolve_incident,
    update_incident,
)
from kagami.flow.modules.recovery import (
    RecoveryResult,
    RecoveryStrategy,
    execute_recovery,
    plan_recovery,
)

__all__ = [
    "Diagnosis",
    "Incident",
    "IncidentSeverity",
    "IncidentStatus",
    "RecoveryResult",
    "RecoveryStrategy",
    "RootCause",
    # Incidents
    "create_incident",
    # Diagnosis
    "diagnose_issue",
    # Recovery
    "execute_recovery",
    "find_root_cause",
    "plan_recovery",
    "resolve_incident",
    "update_incident",
]
