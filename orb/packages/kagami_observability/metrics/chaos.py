"""Chaos System Metrics.

Prometheus metrics for chaos safety monitoring, OGY control, and CBF integration.

Created: December 22, 2025
"""

from __future__ import annotations

from .core import Counter, Gauge, Histogram

# --- Chaos Safety Metrics ---

# Total chaos safety checks performed
CHAOS_SAFETY_CHECKS_TOTAL = Counter(
    "kagami_chaos_safety_checks_total",
    "Total number of chaos safety checks performed",
    labelnames=["result"],  # "safe", "unsafe", "error"
)

# Control interventions performed
CHAOS_INTERVENTIONS_TOTAL = Counter(
    "kagami_chaos_interventions_total",
    "Total number of chaos control interventions performed",
    labelnames=["method"],  # "ogy", "pyragas", "cbf", "fallback"
)

# Violations prevented
CHAOS_VIOLATIONS_PREVENTED_TOTAL = Counter(
    "kagami_chaos_violations_prevented_total",
    "Total number of safety violations prevented by chaos control",
)

# Current CBF value (barrier function h(x))
CHAOS_CBF_VALUE = Gauge(
    "kagami_chaos_cbf_value",
    "Current value of Control Barrier Function h(x)",
)

# Distance from safety boundary
CHAOS_BOUNDARY_DISTANCE = Gauge(
    "kagami_chaos_boundary_distance",
    "Distance from the safety boundary",
)

# Stabilization duration histogram
CHAOS_STABILIZATION_DURATION_SECONDS = Histogram(
    "kagami_chaos_stabilization_duration_seconds",
    "Time taken to stabilize chaotic system",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

# Lyapunov exponent (chaos indicator)
CHAOS_LYAPUNOV_EXPONENT = Gauge(
    "kagami_chaos_lyapunov_exponent",
    "Maximum Lyapunov exponent of the system",
)

__all__ = [
    "CHAOS_BOUNDARY_DISTANCE",
    "CHAOS_CBF_VALUE",
    "CHAOS_INTERVENTIONS_TOTAL",
    "CHAOS_LYAPUNOV_EXPONENT",
    "CHAOS_SAFETY_CHECKS_TOTAL",
    "CHAOS_STABILIZATION_DURATION_SECONDS",
    "CHAOS_VIOLATIONS_PREVENTED_TOTAL",
]
