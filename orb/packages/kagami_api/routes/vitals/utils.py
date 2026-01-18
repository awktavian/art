"""Shared utilities for vitals/health check endpoints.

Created: December 2025
"""

from __future__ import annotations

from kagami_api.schemas.vitals import DependencyCheck


def determine_overall_status(checks: dict[str, DependencyCheck]) -> str:
    """Determine overall status from individual dependency checks.

    Aggregates multiple DependencyCheck results into a single overall status.

    Status priority (worst case wins):
    1. unhealthy/error - any component unhealthy makes system unhealthy
    2. degraded/unavailable - any component degraded/unavailable makes system degraded
    3. healthy - all components healthy

    Args:
        checks: Dictionary mapping component names to their DependencyCheck results

    Returns:
        Overall status: "unhealthy", "degraded", or "healthy"

    Example:
        >>> checks = {
        ...     "database": DependencyCheck(status="healthy"),
        ...     "redis": DependencyCheck(status="degraded"),
        ... }
        >>> determine_overall_status(checks)
        'degraded'
    """
    overall = "healthy"
    for check in checks.values():
        status = check.status
        if status in ("unhealthy", "error"):
            return "unhealthy"
        elif status in ("degraded", "unavailable"):
            overall = "degraded"
    return overall


__all__ = ["determine_overall_status"]
