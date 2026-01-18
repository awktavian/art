"""Centralized Metrics Module.

All Prometheus metrics organized by category.
Streamlined after audit - removed 23 unused modules (Dec 22, 2025).
"""

from __future__ import annotations

import logging
from typing import Any

# Re-export core helpers and single REGISTRY (single source of truth)
from .core import (
    METRIC_EMISSION_FAILURES_TOTAL,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    Summary,  # alias via decorators contract
    counter,
    emit_counter,
    emit_gauge,
    emit_histogram,
    gauge,
    get_counter,
    get_current_metrics,
    get_histogram,
    get_prometheus_metrics,
    histogram,
    safe_emit,
    summary,
)

__all__ = [
    # Re-exported metrics from submodules
    "API_ERRORS",
    "CHARACTER_GENERATIONS",
    # Constants
    "METRIC_EMISSION_FAILURES_TOTAL",
    "REFLECTIONS_TOTAL",
    "REFLECTION_DURATION_SECONDS",
    "REGISTRY",
    # Core types
    "Counter",
    "Gauge",
    "Histogram",
    "Summary",
    # Helper functions
    "counter",
    "emit_counter",
    "emit_gauge",
    "emit_histogram",
    "gauge",
    "get_counter",
    "get_current_metrics",
    "get_histogram",
    "get_prometheus_metrics",
    "histogram",
    "safe_emit",
    "summary",
]

# Logging for deterministic import tracking
logger = logging.getLogger(__name__)
MISSING_METRICS_MODULES: list[str] = []


def _record_import_failure(module: str, exc: Exception) -> None:
    if module not in MISSING_METRICS_MODULES:
        MISSING_METRICS_MODULES.append(module)
    logger.warning("Metrics module '%s' failed to import: %s", module, exc)


# --- Submodules (streamlined after audit) ---
# Only modules that are actually imported elsewhere

try:
    from . import api
    from .api import API_ERRORS  # Re-export commonly used metrics
except Exception as exc:
    api = None  # type: ignore[assignment]
    _record_import_failure("api", exc)

try:
    from . import cognitive
except Exception as exc:
    cognitive = None  # type: ignore[assignment]
    _record_import_failure("cognitive", exc)

try:
    from . import chaos
except Exception as exc:
    chaos = None  # type: ignore[assignment]
    _record_import_failure("chaos", exc)

try:
    from . import colony
except Exception as exc:
    colony = None  # type: ignore[assignment]
    _record_import_failure("colony", exc)

try:
    from . import emu
except Exception as exc:
    emu = None  # type: ignore[assignment]
    _record_import_failure("emu", exc)

try:
    from . import forge
except Exception as exc:
    forge = None  # type: ignore[assignment]
    _record_import_failure("forge", exc)

try:
    from . import hal
except Exception as exc:
    hal = None  # type: ignore[assignment]
    _record_import_failure("hal", exc)

try:
    from . import infrastructure
except Exception as exc:
    infrastructure = None  # type: ignore[assignment]
    _record_import_failure("infrastructure", exc)

try:
    from . import intelligence
except Exception as exc:
    intelligence = None  # type: ignore[assignment]
    _record_import_failure("intelligence", exc)

try:
    from . import learning
except Exception as exc:
    learning = None  # type: ignore[assignment]
    _record_import_failure("learning", exc)

try:
    from . import receipts
except Exception as exc:
    receipts = None  # type: ignore[assignment]
    _record_import_failure("receipts", exc)

try:
    from . import safety
except Exception as exc:
    safety = None  # type: ignore[assignment]
    _record_import_failure("safety", exc)

try:
    from . import system
    from .system import (  # Re-export commonly used metrics
        CHARACTER_GENERATIONS,
        REFLECTION_DURATION_SECONDS,
        REFLECTIONS_TOTAL,
    )
except Exception as exc:
    system = None  # type: ignore[assignment]
    _record_import_failure("system", exc)

try:
    from . import ui_performance
except Exception as exc:
    ui_performance = None  # type: ignore[assignment]
    _record_import_failure("ui_performance", exc)


def _update_runtime_metrics() -> None:
    """Update runtime metrics (CPU, memory, etc.) if psutil available."""
    try:
        import psutil

        process = psutil.Process()
        process.memory_info()
    except Exception:
        pass


def __getattr__(name: str) -> Any:
    """Provide dynamic attribute access for lazily-loaded metric symbols.

    The metrics package conditionally imports many submodules inside try/except
    blocks.  During static analysis this can appear as if attributes are missing,
    generating mypy ``[attr-defined]`` errors.  Exposing ``__getattr__`` that
    returns ``Any`` informs the type checker that arbitrary metric names may be
    retrieved at runtime while preserving actual lookup behaviour.
    """

    try:
        return globals()[name]
    except KeyError as exc:  # pragma: no cover - defensive
        # Try finding in submodules (legacy fallback)
        # Iterate over known modules and check if they have the attribute
        # This is slow but safe for migration

        # Only check modules that were successfully imported (post-audit list)
        _g = globals()
        module_names = [
            "api",
            "chaos",
            "cognitive",
            "colony",
            "emu",
            "forge",
            "hal",
            "infrastructure",
            "intelligence",
            "learning",
            "receipts",
            "safety",
            "system",
            "ui_performance",
        ]

        for mod_name in module_names:
            mod = _g.get(mod_name)
            if mod is not None and hasattr(mod, name):
                return getattr(mod, name)

        raise AttributeError(f"Metric '{name}' not found in any submodule") from exc
