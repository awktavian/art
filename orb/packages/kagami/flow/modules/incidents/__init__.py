"""Flow Incidents Module — Incident Management.

Provides incident lifecycle management:
- Incident creation and tracking
- Severity classification
- Status updates
- Timeline tracking

Created: December 28, 2025
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class IncidentSeverity(Enum):
    """Incident severity levels."""

    SEV1 = "sev1"  # Critical - immediate response
    SEV2 = "sev2"  # High - urgent response
    SEV3 = "sev3"  # Medium - standard response
    SEV4 = "sev4"  # Low - scheduled response


class IncidentStatus(Enum):
    """Incident lifecycle status."""

    DETECTED = "detected"
    TRIAGING = "triaging"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"


@dataclass
class TimelineEntry:
    """An entry in the incident timeline."""

    timestamp: float
    action: str
    actor: str = "flow"
    details: dict[str, Any] = field(default_factory=dict[str, Any])

    @property
    def formatted_time(self) -> str:
        return datetime.fromtimestamp(self.timestamp).isoformat()


@dataclass
class Incident:
    """An incident being tracked."""

    incident_id: str
    title: str
    severity: IncidentSeverity
    status: IncidentStatus
    symptoms: list[str]
    created_at: float
    updated_at: float
    timeline: list[TimelineEntry] = field(default_factory=list[Any])
    affected_services: list[str] = field(default_factory=list[Any])
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    resolution: str = ""
    root_cause: str = ""

    @property
    def duration_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def is_active(self) -> bool:
        return self.status not in (IncidentStatus.RESOLVED, IncidentStatus.POSTMORTEM)


# In-memory incident store (for demo/testing)
_incidents: dict[str, Incident] = {}


def create_incident(
    title: str,
    severity: str | IncidentSeverity,
    symptoms: list[str],
    affected_services: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Incident:
    """Create a new incident.

    Args:
        title: Incident title
        severity: Severity level ("sev1", "sev2", "sev3", "sev4")
        symptoms: List of observed symptoms
        affected_services: Services affected
        metadata: Additional metadata

    Returns:
        Created Incident object

    Example:
        incident = create_incident(
            title="API latency spike",
            severity="sev2",
            symptoms=["p99 > 500ms", "error rate 5%"],
            affected_services=["auth", "api"],
        )
    """
    # Parse severity
    if isinstance(severity, str):
        severity = IncidentSeverity(severity.lower())

    now = time.time()
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"

    incident = Incident(
        incident_id=incident_id,
        title=title,
        severity=severity,
        status=IncidentStatus.DETECTED,
        symptoms=symptoms,
        created_at=now,
        updated_at=now,
        timeline=[
            TimelineEntry(
                timestamp=now,
                action="incident_created",
                details={"title": title, "severity": severity.value},
            )
        ],
        affected_services=affected_services or [],
        metadata=metadata or {},
    )

    _incidents[incident_id] = incident
    logger.info(f"🌊 Flow: Created incident {incident_id} - {title} ({severity.value})")

    # Alert based on severity
    _trigger_alert(incident)

    return incident


def update_incident(
    incident_id: str,
    status: str | IncidentStatus | None = None,
    notes: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Incident:
    """Update an incident.

    Args:
        incident_id: Incident ID to update
        status: New status (optional)
        notes: Update notes (optional)
        metadata: Additional metadata to merge

    Returns:
        Updated Incident
    """
    if incident_id not in _incidents:
        raise ValueError(f"Incident not found: {incident_id}")

    incident = _incidents[incident_id]
    now = time.time()
    incident.updated_at = now

    if status:
        if isinstance(status, str):
            status = IncidentStatus(status.lower())
        old_status = incident.status
        incident.status = status
        incident.timeline.append(
            TimelineEntry(
                timestamp=now,
                action="status_changed",
                details={"from": old_status.value, "to": status.value},
            )
        )
        logger.info(f"🌊 Flow: Incident {incident_id} status: {old_status.value} → {status.value}")

    if notes:
        incident.timeline.append(
            TimelineEntry(
                timestamp=now,
                action="note_added",
                details={"note": notes},
            )
        )

    if metadata:
        incident.metadata.update(metadata)

    return incident


def resolve_incident(
    incident_id: str,
    resolution: str,
    root_cause: str | None = None,
) -> Incident:
    """Resolve an incident.

    Args:
        incident_id: Incident ID to resolve
        resolution: Resolution description
        root_cause: Root cause if identified

    Returns:
        Resolved Incident
    """
    if incident_id not in _incidents:
        raise ValueError(f"Incident not found: {incident_id}")

    incident = _incidents[incident_id]
    now = time.time()

    incident.status = IncidentStatus.RESOLVED
    incident.resolution = resolution
    incident.root_cause = root_cause or ""
    incident.updated_at = now

    incident.timeline.append(
        TimelineEntry(
            timestamp=now,
            action="incident_resolved",
            details={
                "resolution": resolution,
                "root_cause": root_cause,
                "duration_seconds": incident.duration_seconds,
            },
        )
    )

    logger.info(f"🌊 Flow: Incident {incident_id} resolved after {incident.duration_seconds:.0f}s")

    return incident


def get_incident(incident_id: str) -> Incident | None:
    """Get an incident by ID."""
    return _incidents.get(incident_id)


def get_active_incidents() -> list[Incident]:
    """Get all active incidents."""
    return [i for i in _incidents.values() if i.is_active]


def _trigger_alert(incident: Incident) -> None:
    """Trigger alert based on incident severity."""
    try:
        from kagami_observability.alerting import Alert, AlertManager, AlertSeverity

        manager = AlertManager()

        # Map incident severity to alert severity
        severity_map = {
            IncidentSeverity.SEV1: AlertSeverity.CRITICAL,
            IncidentSeverity.SEV2: AlertSeverity.WARNING,
            IncidentSeverity.SEV3: AlertSeverity.INFO,
            IncidentSeverity.SEV4: AlertSeverity.INFO,
        }

        alert = Alert(
            severity=severity_map.get(incident.severity, AlertSeverity.INFO),
            title=f"[{incident.severity.value.upper()}] {incident.title}",
            description="\n".join(incident.symptoms),
            source="flow_incidents",
            timestamp=incident.created_at,
            metadata={
                "incident_id": incident.incident_id,
                "affected_services": incident.affected_services,
            },
        )

        manager.send_alert(alert)
    except Exception as e:
        logger.debug(f"Alert trigger failed: {e}")


__all__ = [
    "Incident",
    "IncidentSeverity",
    "IncidentStatus",
    "TimelineEntry",
    "create_incident",
    "get_active_incidents",
    "get_incident",
    "resolve_incident",
    "update_incident",
]
