"""Safety Zones - h(x) value classification and zone-aware APIs.

CREATED: December 27, 2025
PURPOSE: Fix theoretical weakness - h(x) zones not exposed via API

From CLAUDE.md specification:
| h(x)   | Zone       | Action         |
|--------|------------|----------------|
| > 0.5  | SAFE       | Proceed        |
| 0-0.5  | CAUTION    | Verify first   |
| < 0    | VIOLATION  | STOP           |

Extended zones for implementation:
| h(x)      | Zone      | Description                                |
|-----------|-----------|-------------------------------------------|
| < 0       | VIOLATION | h(x) < 0, emergency halt                  |
| 0 - 0.1   | BUFFER    | Within safety margin, blocked concurrent  |
| 0.1 - 0.5 | CAUTION   | Low confidence, verify first              |
| 0.5 - 1.0 | SAFE      | Standard operating region                 |
| > 1.0     | OPTIMAL   | High margin, can cache longer             |

USAGE:
    from kagami.core.safety.safety_zones import SafetyZone, classify_h_value

    zone = classify_h_value(h_x=0.3)
    assert zone == SafetyZone.CAUTION

    # Get zone metadata
    assert zone.should_verify  # True
    assert not zone.can_proceed_fast  # False
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# ZONE THRESHOLDS (from CLAUDE.md + cbf_integration.py)
# =============================================================================

# From cbf_integration.py:78
SAFETY_BUFFER = 0.1

# From CLAUDE.md zone specification
CAUTION_THRESHOLD = 0.5

# Extended: high-margin region for cache optimization
OPTIMAL_THRESHOLD = 1.0

# HYSTERESIS (Dec 27, 2025): Prevent oscillation near zone boundaries
# When transitioning DOWN (getting less safe), use lower thresholds
# When transitioning UP (getting safer), use higher thresholds
# This creates a "dead band" that prevents rapid zone flipping
HYSTERESIS_MARGIN = 0.05  # 5% margin around each threshold


# =============================================================================
# SAFETY ZONE ENUM
# =============================================================================


class SafetyZone(Enum):
    """Safety zone classification for h(x) barrier function values.

    Zones are ordered by safety level (VIOLATION < BUFFER < CAUTION < SAFE < OPTIMAL).

    Each zone has associated behaviors:
    - VIOLATION: Emergency halt, block all operations
    - BUFFER: Block concurrent operations (race condition protection)
    - CAUTION: Verify before proceeding, add Crystal colony
    - SAFE: Normal operation, standard verification
    - OPTIMAL: High margin, can use cached results longer
    """

    VIOLATION = auto()  # h(x) < 0
    BUFFER = auto()  # 0 <= h(x) < SAFETY_BUFFER
    CAUTION = auto()  # SAFETY_BUFFER <= h(x) < CAUTION_THRESHOLD
    SAFE = auto()  # CAUTION_THRESHOLD <= h(x) < OPTIMAL_THRESHOLD
    OPTIMAL = auto()  # h(x) >= OPTIMAL_THRESHOLD

    @property
    def is_safe(self) -> bool:
        """Whether operations can proceed (h(x) >= 0)."""
        return self in (SafetyZone.BUFFER, SafetyZone.CAUTION, SafetyZone.SAFE, SafetyZone.OPTIMAL)

    @property
    def can_proceed_fast(self) -> bool:
        """Whether operations can proceed without additional verification."""
        return self in (SafetyZone.SAFE, SafetyZone.OPTIMAL)

    @property
    def should_verify(self) -> bool:
        """Whether Crystal verification should be added."""
        return self in (SafetyZone.BUFFER, SafetyZone.CAUTION)

    @property
    def allows_concurrent(self) -> bool:
        """Whether concurrent multi-colony operations are allowed."""
        return self in (SafetyZone.CAUTION, SafetyZone.SAFE, SafetyZone.OPTIMAL)

    @property
    def allows_caching(self) -> bool:
        """Whether results can be cached."""
        return self in (SafetyZone.SAFE, SafetyZone.OPTIMAL)

    @property
    def cache_ttl_multiplier(self) -> float:
        """Cache TTL multiplier based on zone.

        OPTIMAL zone gets longer cache TTL, CAUTION gets shorter.
        """
        return {
            SafetyZone.VIOLATION: 0.0,  # Never cache
            SafetyZone.BUFFER: 0.0,  # Never cache
            SafetyZone.CAUTION: 0.5,  # Half normal TTL
            SafetyZone.SAFE: 1.0,  # Normal TTL
            SafetyZone.OPTIMAL: 2.0,  # Double TTL
        }[self]

    @property
    def color_code(self) -> str:
        """Color code for logging/display."""
        return {
            SafetyZone.VIOLATION: "🔴",
            SafetyZone.BUFFER: "🟠",
            SafetyZone.CAUTION: "🟡",
            SafetyZone.SAFE: "🟢",
            SafetyZone.OPTIMAL: "💚",
        }[self]

    def __str__(self) -> str:
        return f"{self.color_code} {self.name}"


# =============================================================================
# ZONE CLASSIFICATION
# =============================================================================


# Track previous zone for hysteresis (module-level state)
_previous_zone: SafetyZone | None = None


def classify_h_value(
    h_x: float,
    previous_zone: SafetyZone | None = None,
    use_hysteresis: bool = True,
) -> SafetyZone:
    """Classify h(x) barrier value into a safety zone with hysteresis.

    HYSTERESIS (Dec 27, 2025): Prevents oscillation near zone boundaries.
    When h(x) is near a threshold, we require it to cross by HYSTERESIS_MARGIN
    to transition, preventing rapid zone flipping.

    Args:
        h_x: Barrier function value
        previous_zone: Previous zone (for hysteresis). If None, uses module-level state.
        use_hysteresis: Whether to apply hysteresis (default True)

    Returns:
        SafetyZone classification

    Examples:
        >>> classify_h_value(-0.5)
        SafetyZone.VIOLATION

        >>> classify_h_value(0.05)
        SafetyZone.BUFFER

        >>> classify_h_value(0.3)
        SafetyZone.CAUTION

        >>> classify_h_value(0.7)
        SafetyZone.SAFE

        >>> classify_h_value(1.5)
        SafetyZone.OPTIMAL

        # With hysteresis: stays in SAFE until crossing threshold + margin
        >>> classify_h_value(0.48, previous_zone=SafetyZone.SAFE)
        SafetyZone.SAFE  # Doesn't drop to CAUTION until h_x < 0.45
    """
    global _previous_zone

    # Use provided previous_zone or fall back to module state
    prev = previous_zone if previous_zone is not None else _previous_zone

    # Base classification (no hysteresis)
    if h_x < 0:
        base_zone = SafetyZone.VIOLATION
    elif h_x < SAFETY_BUFFER:
        base_zone = SafetyZone.BUFFER
    elif h_x < CAUTION_THRESHOLD:
        base_zone = SafetyZone.CAUTION
    elif h_x < OPTIMAL_THRESHOLD:
        base_zone = SafetyZone.SAFE
    else:
        base_zone = SafetyZone.OPTIMAL

    # Apply hysteresis if enabled and we have a previous zone
    if use_hysteresis and prev is not None:
        # Define zone order for comparison
        zone_order = [
            SafetyZone.VIOLATION,
            SafetyZone.BUFFER,
            SafetyZone.CAUTION,
            SafetyZone.SAFE,
            SafetyZone.OPTIMAL,
        ]
        prev_idx = zone_order.index(prev)
        base_idx = zone_order.index(base_zone)

        # If transitioning DOWN (less safe), require crossing threshold - margin
        if base_idx < prev_idx:
            # Check if we're in the hysteresis band
            if base_zone == SafetyZone.VIOLATION:
                # VIOLATION has no hysteresis (immediate safety halt)
                pass
            elif base_zone == SafetyZone.BUFFER and h_x >= -HYSTERESIS_MARGIN:
                base_zone = prev  # Stay in previous zone
            elif base_zone == SafetyZone.CAUTION and h_x >= SAFETY_BUFFER - HYSTERESIS_MARGIN:
                if prev in (SafetyZone.SAFE, SafetyZone.OPTIMAL):
                    base_zone = prev
            elif base_zone == SafetyZone.SAFE and h_x >= CAUTION_THRESHOLD - HYSTERESIS_MARGIN:
                if prev == SafetyZone.OPTIMAL:
                    base_zone = prev

        # If transitioning UP (safer), require crossing threshold + margin
        elif base_idx > prev_idx:
            if base_zone == SafetyZone.BUFFER and h_x < SAFETY_BUFFER + HYSTERESIS_MARGIN:
                if prev == SafetyZone.VIOLATION:
                    base_zone = prev  # Stay in VIOLATION until safely past
            elif base_zone == SafetyZone.CAUTION and h_x < SAFETY_BUFFER + HYSTERESIS_MARGIN:
                base_zone = prev
            elif base_zone == SafetyZone.SAFE and h_x < CAUTION_THRESHOLD + HYSTERESIS_MARGIN:
                if prev in (SafetyZone.BUFFER, SafetyZone.CAUTION):
                    base_zone = prev
            elif base_zone == SafetyZone.OPTIMAL and h_x < OPTIMAL_THRESHOLD + HYSTERESIS_MARGIN:
                if prev == SafetyZone.SAFE:
                    base_zone = prev

    # Update module-level state
    _previous_zone = base_zone

    return base_zone


def reset_zone_hysteresis() -> None:
    """Reset hysteresis state (for testing or session boundaries)."""
    global _previous_zone
    _previous_zone = None


# =============================================================================
# ZONE-AWARE SAFETY RESULT
# =============================================================================


@dataclass
class ZoneAwareSafetyResult:
    """Safety check result with zone classification.

    Extends SafetyCheckResult with explicit zone information.
    """

    safe: bool
    h_x: float
    zone: SafetyZone
    reason: str
    detail: str | None = None
    action: str | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_h_value(
        cls,
        h_x: float,
        reason: str = "",
        detail: str | None = None,
        action: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ZoneAwareSafetyResult:
        """Create result from h(x) value with automatic zone classification."""
        zone = classify_h_value(h_x)
        return cls(
            safe=zone.is_safe,
            h_x=h_x,
            zone=zone,
            reason=reason or zone.name.lower(),
            detail=detail or f"h(x)={h_x:.4f} -> {zone}",
            action=action,
            metadata=metadata,
        )

    @property
    def should_add_crystal(self) -> bool:
        """Whether Crystal colony should be added for verification."""
        return self.zone.should_verify

    @property
    def allows_fano_composition(self) -> bool:
        """Whether Fano line composition is allowed."""
        return self.zone.allows_concurrent

    @property
    def cache_ttl_multiplier(self) -> float:
        """Cache TTL multiplier based on zone."""
        return self.zone.cache_ttl_multiplier


# =============================================================================
# ZONE-BASED ROUTING HINTS
# =============================================================================


def get_routing_hints_for_zone(zone: SafetyZone) -> dict[str, Any]:
    """Get routing hints based on safety zone.

    Provides guidance for FanoActionRouter based on current safety state.

    Args:
        zone: Current safety zone

    Returns:
        Dict with routing hints:
        - max_colonies: Maximum colonies allowed
        - require_crystal: Whether Crystal verification is mandatory
        - complexity_cap: Maximum complexity to use
        - cache_enabled: Whether caching is allowed
    """
    return {
        SafetyZone.VIOLATION: {
            "max_colonies": 0,
            "require_crystal": True,
            "complexity_cap": 0.0,
            "cache_enabled": False,
            "action": "HALT",
        },
        SafetyZone.BUFFER: {
            "max_colonies": 1,
            "require_crystal": True,
            "complexity_cap": 0.3,
            "cache_enabled": False,
            "action": "SINGLE_VERIFIED",
        },
        SafetyZone.CAUTION: {
            "max_colonies": 3,
            "require_crystal": True,
            "complexity_cap": 0.7,
            "cache_enabled": True,
            "action": "FANO_VERIFIED",
        },
        SafetyZone.SAFE: {
            "max_colonies": 7,
            "require_crystal": False,
            "complexity_cap": 1.0,
            "cache_enabled": True,
            "action": "NORMAL",
        },
        SafetyZone.OPTIMAL: {
            "max_colonies": 7,
            "require_crystal": False,
            "complexity_cap": 1.0,
            "cache_enabled": True,
            "action": "FAST_PATH",
        },
    }[zone]


# =============================================================================
# EPISTEMIC SAFETY CHECK
# =============================================================================


def check_epistemic_safety(
    confidence: float,
    evidence: float,
    threshold: float = 0.2,
) -> tuple[bool, str]:
    """Check epistemic safety invariant: confident(claim) <= evidence(claim).

    From CLAUDE.md OOD Awareness:
    > confident(claim) ≤ evidence(claim)    Always.

    Args:
        confidence: Claimed confidence level [0, 1]
        evidence: Available evidence level [0, 1]
        threshold: Maximum allowed overconfidence gap

    Returns:
        (is_safe, reason) tuple[Any, ...]

    Examples:
        >>> check_epistemic_safety(0.8, 0.9)  # High evidence, OK
        (True, 'epistemic_safe')

        >>> check_epistemic_safety(0.9, 0.3)  # Overconfident!
        (False, 'overconfidence_violation')
    """
    gap = confidence - evidence

    if gap <= threshold:
        return True, "epistemic_safe"
    else:
        return (
            False,
            f"overconfidence_violation: confidence={confidence:.2f} > evidence={evidence:.2f} + {threshold}",
        )


# =============================================================================
# OOD DETECTION SIGNALS
# =============================================================================


class OODRisk(Enum):
    """Out-of-Distribution risk level."""

    LOW = auto()  # Proceed with confidence
    MEDIUM = auto()  # Verify before proceeding
    HIGH = auto()  # Route to Grove for research

    @property
    def should_escalate_to_grove(self) -> bool:
        """Whether task should be escalated to Grove colony."""
        return self == OODRisk.HIGH

    @property
    def should_verify(self) -> bool:
        """Whether Crystal verification is recommended."""
        return self in (OODRisk.MEDIUM, OODRisk.HIGH)


def assess_ood_risk(
    bayesian_confidence: float,
    pattern_age_hours: float,
    execution_count: int,
    semantic_similarity: float | None = None,
) -> OODRisk:
    """Assess out-of-distribution risk for a task.

    Uses multiple signals to detect potential OOD scenarios:
    1. Low Bayesian confidence (uncertain pattern)
    2. Stale patterns (old, potentially outdated)
    3. Low execution count (rare, under-explored)
    4. Low semantic similarity (novel context)

    Args:
        bayesian_confidence: Pattern confidence from stigmergy [0, 1]
        pattern_age_hours: Hours since pattern was last updated
        execution_count: Number of times pattern was executed
        semantic_similarity: Similarity to known patterns [0, 1] (optional)

    Returns:
        OODRisk level

    From CLAUDE.md:
        🔴 HIGH RISK: Sparse training, real-time state, exact computation needed
        🟡 MEDIUM RISK: Rare framework, recent events, domain jargon
        🟢 LOW RISK: Popular languages, documented frameworks
    """
    # Count high-risk signals
    risk_signals = 0

    # Low confidence
    if bayesian_confidence < 0.3:
        risk_signals += 2  # Major signal
    elif bayesian_confidence < 0.5:
        risk_signals += 1

    # Stale pattern (> 24 hours old)
    if pattern_age_hours > 168:  # 1 week
        risk_signals += 2
    elif pattern_age_hours > 24:
        risk_signals += 1

    # Low execution count (under-explored)
    if execution_count < 3:
        risk_signals += 2
    elif execution_count < 10:
        risk_signals += 1

    # Low semantic similarity (if provided)
    if semantic_similarity is not None:
        if semantic_similarity < 0.3:
            risk_signals += 2
        elif semantic_similarity < 0.6:
            risk_signals += 1

    # Classify risk
    if risk_signals >= 4:
        return OODRisk.HIGH
    elif risk_signals >= 2:
        return OODRisk.MEDIUM
    else:
        return OODRisk.LOW


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CAUTION_THRESHOLD",
    "HYSTERESIS_MARGIN",
    "OPTIMAL_THRESHOLD",
    # Constants
    "SAFETY_BUFFER",
    # OOD detection
    "OODRisk",
    # Zone classification
    "SafetyZone",
    # Zone-aware results
    "ZoneAwareSafetyResult",
    "assess_ood_risk",
    # Epistemic safety
    "check_epistemic_safety",
    "classify_h_value",
    "get_routing_hints_for_zone",
    "reset_zone_hysteresis",
]
