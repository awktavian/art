"""API Support - Components needed by API routes.

This module provides the minimal components that API routes need,
migrated from various fractal_agents modules.

Created: December 2, 2025
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# SHARED AWARENESS (from fractal_agents/shared_awareness.py)
# =============================================================================


class ActivityType(str, Enum):
    """Types of colony activity."""

    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    PLAN_COMPLETED = "plan_completed"
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    AGENT_SPAWNED = "agent_spawned"
    AGENT_DIED = "agent_died"
    COLLABORATION = "collaboration"
    DISCOVERY = "discovery"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class ColonyActivity:
    """A single activity/event from a colony."""

    activity_id: str = field(default_factory=lambda: str(uuid4()))
    colony_name: str = ""
    activity_type: ActivityType = ActivityType.HEARTBEAT
    timestamp: datetime = field(default_factory=datetime.now)
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict[str, Any])
    progress: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "activity_id": self.activity_id,
            "colony_name": self.colony_name,
            "activity_type": self.activity_type.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "details": self.details,
            "progress": self.progress,
        }


class SharedAwareness:
    """Shared colony awareness system."""

    def __init__(self, max_activities: int = 1000):
        self._activities: deque[ColonyActivity] = deque(maxlen=max_activities)
        self._subscribers: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def record_activity(self, activity: ColonyActivity) -> None:
        """Record a new activity."""
        async with self._lock:
            self._activities.append(activity)
            for queue in self._subscribers:
                try:
                    queue.put_nowait(activity)
                except asyncio.QueueFull:
                    pass

    def get_recent_activities(
        self,
        count: int = 50,
        colony: str | None = None,
    ) -> list[ColonyActivity]:
        """Get recent activities."""
        activities = list(self._activities)
        if colony:
            activities = [a for a in activities if a.colony_name == colony]
        return activities[-count:]

    def subscribe(self) -> asyncio.Queue:
        """Subscribe to activity stream."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from activity stream."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def get_stats(self) -> dict[str, Any]:
        """Get awareness stats."""
        return {
            "total_activities": len(self._activities),
            "subscribers": len(self._subscribers),
        }


# Singleton
_SHARED_AWARENESS: SharedAwareness | None = None


def get_shared_awareness() -> SharedAwareness:
    """Get global shared awareness instance."""
    global _SHARED_AWARENESS
    if _SHARED_AWARENESS is None:
        _SHARED_AWARENESS = SharedAwareness()
    return _SHARED_AWARENESS


# =============================================================================
# CRITICALITY FUNCTIONS - HARDENED (no manager abstraction)
# =============================================================================

# HARDENED: Direct state variables - no manager class abstraction
_target_lyapunov: float = 0.05
_measurement_window: int = 100
_adjustment_rate: float = 0.1
_success_history: deque[Any] = deque(maxlen=_measurement_window)
_agent_count_history: deque[Any] = deque(maxlen=_measurement_window)
_response_time_history: deque[Any] = deque(maxlen=_measurement_window)
_lyapunov_history: deque[Any] = deque(maxlen=50)
_current_regime = "edge_of_chaos"  # HARDENED: Direct state, no "unknown"
_last_adjustment_time = 0.0
_current_lyapunov = 0.0

# HARDENED: Direct functions - no class method abstraction


def record_operation(
    success: bool,
    agent_count: int = 0,
    response_time_ms: float = 0.0,
) -> None:
    """Record an operation for criticality analysis - HARDENED."""
    global _success_history, _agent_count_history, _response_time_history
    _success_history.append(1.0 if success else 0.0)
    _agent_count_history.append(agent_count)
    _response_time_history.append(response_time_ms)


def estimate_lyapunov() -> float:
    """Estimate Lyapunov exponent from recent history - HARDENED."""
    global _current_lyapunov, _lyapunov_history, _success_history

    if len(_success_history) < 10:
        return 0.0

    successes = np.array(list(_success_history))

    # HARDENED: Simplified variability measure
    if len(successes) > 1:
        diff = np.diff(successes)
        variability = np.std(diff) if len(diff) > 0 else 0.0
        _current_lyapunov = float(variability)

    _lyapunov_history.append(_current_lyapunov)
    return _current_lyapunov


def get_regime() -> str:
    """Determine current operating regime - HARDENED."""
    global _current_regime
    lyap = estimate_lyapunov()

    # HARDENED: Direct state update
    if lyap < -0.1:
        _current_regime = "ordered"
    elif lyap > 0.1:
        _current_regime = "chaotic"
    else:
        _current_regime = "edge_of_chaos"  # HARDENED: Always target edge

    return _current_regime


def get_criticality_metrics() -> dict[str, Any]:
    """Get criticality metrics - HARDENED."""
    lyap = estimate_lyapunov()
    return {
        "current_lyapunov": lyap,
        "average_lyapunov": np.mean(list(_lyapunov_history)) if _lyapunov_history else 0.0,
        "regime": get_regime(),
        "at_edge_of_chaos": abs(lyap) < 0.1,
        "measurement_count": len(_success_history),
    }


async def measure_and_adjust(organism: Any = None) -> dict[str, Any]:
    """Measure criticality and adjust - HARDENED."""
    lyap = estimate_lyapunov()
    regime = get_regime()
    return {
        "measured_lyapunov": lyap,
        "regime": regime,
        "adjustment_made": False,  # HARDENED: No automatic adjustments
    }


# =============================================================================
# CRITICALITY MANAGER (API wrapper for routes)
# =============================================================================


class CriticalityManager:
    """API wrapper for criticality management.

    Wraps the hardened direct-access functions for use in API routes.
    """

    def __init__(self) -> None:
        self.target_lyapunov: float = 0.0
        self.adjustment_rate: float = 0.01

    def get_criticality_metrics(self) -> dict[str, Any]:
        """Get current criticality metrics."""
        return get_criticality_metrics()

    def record_operation(self, success: bool, duration_ms: float) -> None:
        """Record an operation result."""
        record_operation(success, duration_ms)


_criticality_manager: CriticalityManager | None = None


def get_criticality_manager() -> CriticalityManager:
    """Get or create the criticality manager singleton."""
    global _criticality_manager
    if _criticality_manager is None:
        _criticality_manager = CriticalityManager()
    return _criticality_manager


# =============================================================================
# FANO VITALS (from fractal_agents/organism/fano_vitals.py)
# =============================================================================


FANO_LINE_NAMES = [
    "spark_forge_flow",
    "spark_nexus_beacon",
    "spark_grove_crystal",
    "forge_nexus_grove",
    "beacon_forge_crystal",
    "nexus_flow_crystal",
    "beacon_flow_grove",
]

SQUAD_NAMES = [
    "Catalyst",
    "Compass",
    "Prism",
    "Garden",
    "Shield",
    "Anchor",
    "Explorer",
]


@dataclass
class FanoLineVitals:
    """Health metrics for a single Fano line."""

    line_idx: int = 0
    # REAL VALUES ONLY - start at 0.0, not fake 0.5
    activation: float = 0.0
    coherence: float = 0.0
    latency_ms: float = 0.0
    synergy: float = 0.0
    collaboration_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "line_idx": self.line_idx,
            "line_name": FANO_LINE_NAMES[self.line_idx] if self.line_idx < 7 else "unknown",
            "squad_name": SQUAD_NAMES[self.line_idx] if self.line_idx < 7 else "unknown",
            "activation": self.activation,
            "coherence": self.coherence,
            "latency_ms": self.latency_ms,
            "synergy": self.synergy,
            "collaboration_count": self.collaboration_count,
        }


@dataclass
class FanoCollaborationVitals:
    """System-wide Fano collaboration health."""

    lines: list[FanoLineVitals] = field(default_factory=list[Any])
    overall_health: float = 1.0
    total_collaborations: int = 0

    def __post_init__(self) -> None:
        if not self.lines:
            self.lines = [FanoLineVitals(line_idx=i) for i in range(7)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_health": self.overall_health,
            "total_collaborations": self.total_collaborations,
            "lines": [line.to_dict() for line in self.lines],
        }


class FanoVitals:
    """Track Fano plane collaboration health."""

    def __init__(self) -> None:
        self._vitals = FanoCollaborationVitals()
        self._history: deque[Any] = deque(maxlen=1000)

    def record_collaboration(
        self,
        line_idx: int,
        success: bool,
        latency_ms: float = 0.0,
    ) -> None:
        """Record a Fano line collaboration."""
        if 0 <= line_idx < 7:
            line = self._vitals.lines[line_idx]
            line.collaboration_count += 1

            # EMA updates
            alpha = 0.1
            line.coherence = alpha * (1.0 if success else 0.0) + (1 - alpha) * line.coherence
            line.latency_ms = alpha * latency_ms + (1 - alpha) * line.latency_ms
            line.activation = min(1.0, line.activation + 0.01)

        self._vitals.total_collaborations += 1
        self._update_overall_health()

    def _update_overall_health(self) -> None:
        """Update overall health from line health."""
        coherences = [line.coherence for line in self._vitals.lines]
        self._vitals.overall_health = float(np.mean(coherences))

    def get_vitals(self) -> FanoCollaborationVitals:
        """Get current vitals."""
        return self._vitals

    def get_collaboration_health(self) -> dict[str, Any]:
        """Get health summary."""
        return self._vitals.to_dict()


# Singleton
_FANO_VITALS: FanoVitals | None = None


def get_fano_vitals() -> FanoVitals:
    """Get global Fano vitals instance."""
    global _FANO_VITALS
    if _FANO_VITALS is None:
        _FANO_VITALS = FanoVitals()
    return _FANO_VITALS


def record_fano_collaboration(
    line_idx: int,
    success: bool,
    latency_ms: float = 0.0,
) -> None:
    """Record a Fano line collaboration."""
    get_fano_vitals().record_collaboration(line_idx, success, latency_ms)


def get_collaboration_health() -> dict[str, Any]:
    """Get Fano collaboration health."""
    return get_fano_vitals().get_collaboration_health()


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "FANO_LINE_NAMES",
    "SQUAD_NAMES",
    # Shared Awareness
    "ActivityType",
    "ColonyActivity",
    "FanoCollaborationVitals",
    # Fano Vitals
    "FanoLineVitals",
    "FanoVitals",
    "SharedAwareness",
    "get_collaboration_health",
    "get_fano_vitals",
    "get_shared_awareness",
    "record_fano_collaboration",
]
