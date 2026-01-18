"""K os System health and resource metrics.

Domain-specific metrics for system health, resilience, and resource metrics.
"""

from typing import Any

from kagami_observability.metrics.catalog import get_metric
from kagami_observability.metrics.core import Counter, Gauge, Histogram

BOOT_PHASE_DURATION_MS = get_metric("BOOT_PHASE_DURATION_MS")
BOOT_TIME_TO_READY_MS = get_metric("BOOT_TIME_TO_READY_MS")
BOOT_NODE_DURATION_MS = get_metric("BOOT_NODE_DURATION_MS")
BOOT_MEMORY_PEAK_MB = get_metric("BOOT_MEMORY_PEAK_MB")
BOOT_CPU_AVERAGE_PERCENT = get_metric("BOOT_CPU_AVERAGE_PERCENT")
RELATIONSHIP_GRAPH_EDGES_TOTAL = get_metric("RELATIONSHIP_GRAPH_EDGES_TOTAL")
RELATIONSHIP_GRAPH_NODES_TOTAL = get_metric("RELATIONSHIP_GRAPH_NODES_TOTAL")
EXTERNAL_ERRORS_TOTAL = get_metric("EXTERNAL_ERRORS_TOTAL")
EXTERNAL_REQUEST_DURATION = get_metric("EXTERNAL_REQUEST_DURATION")
PRODUCTION_CONTROL_CIRCUIT_OPEN = get_metric("PRODUCTION_CONTROL_CIRCUIT_OPEN")
PRODUCTION_CONTROL_DEGRADATION = get_metric("PRODUCTION_CONTROL_DEGRADATION")
REFLECTION_DURATION_SECONDS = get_metric("REFLECTION_DURATION_SECONDS")
REFLECTION_INSIGHTS_TOTAL = get_metric("REFLECTION_INSIGHTS_TOTAL")
DB_QUERY_SECONDS = get_metric("DB_QUERY_SECONDS")
DB_QUERY_ERRORS = get_metric("DB_QUERY_ERRORS")
DB_CONNECTION_POOL_SIZE = get_metric("DB_CONNECTION_POOL_SIZE")
SYSTEM_CPU_PERCENT = get_metric("SYSTEM_CPU_PERCENT")
SYSTEM_CPU_USAGE = get_metric("SYSTEM_CPU_USAGE")
SYSTEM_MEMORY_BYTES = get_metric("SYSTEM_MEMORY_BYTES")
SYSTEM_MEMORY_USAGE = get_metric("SYSTEM_MEMORY_USAGE")
SYSTEM_DISK_BYTES = get_metric("SYSTEM_DISK_BYTES")
REFLECTIONS_TOTAL = get_metric("REFLECTIONS_TOTAL")
PRODUCTION_CONTROL_LIMIT_HIT = get_metric("PRODUCTION_CONTROL_LIMIT_HIT")
CHARACTER_GENERATIONS = get_metric("CHARACTER_GENERATIONS")
COLLABORATION_TASKS = get_metric("COLLABORATION_TASKS")
PLUGIN_LOADS = get_metric("PLUGIN_LOADS")
QUALITY_SCORES = get_metric("QUALITY_SCORES")
GENUI_CACHE_HITS = get_metric("GENUI_CACHE_HITS")
GENUI_GENERATE_DURATION = get_metric("GENUI_GENERATE_DURATION")
GENUI_REQUESTS = get_metric("GENUI_REQUESTS")
MEMORY_MIRROR_ATTEMPTS_TOTAL = get_metric("MEMORY_MIRROR_ATTEMPTS_TOTAL")
MEMORY_MIRROR_ERRORS_TOTAL = get_metric("MEMORY_MIRROR_ERRORS_TOTAL")
MEMORY_MIRROR_SUCCESS_TOTAL = get_metric("MEMORY_MIRROR_SUCCESS_TOTAL")
RAG_INVOCATIONS_TOTAL = get_metric("RAG_INVOCATIONS_TOTAL")
RAG_RESULTS_TOTAL = get_metric("RAG_RESULTS_TOTAL")
LINEAR_WEBHOOKS = get_metric("LINEAR_WEBHOOKS")
AUTH_LOCKOUTS = get_metric("AUTH_LOCKOUTS")
POLICY_DECISION_TOTAL = get_metric("POLICY_DECISION_TOTAL")
QUORUM_DECISIONS_TOTAL = get_metric("QUORUM_DECISIONS_TOTAL")
RATE_LIMIT_BLOCKS = get_metric("RATE_LIMIT_BLOCKS")
FEATURE_FLAGS_ACTIVE = get_metric("FEATURE_FLAGS_ACTIVE")


def record_learning_observation(app: str, event_type: str, **kwargs: Any) -> None:
    """Record a learning observation to metrics.

    Args:
        app: Application name
        event_type: Event type
        **kwargs: Additional label key-value pairs (e.g., backlog_size=3)
    """
    try:
        import re

        # Sanitize labels: lowercase, replace special chars with underscores
        def sanitize_label(value: str) -> str:
            # Remove leading/trailing whitespace
            clean = value.strip()
            # Lowercase
            clean = clean.lower()
            # Replace non-alphanumeric (except dash) with underscore
            clean = re.sub(r"[^a-z0-9-]", "_", clean)
            # Remove consecutive underscores
            clean = re.sub(r"_+", "_", clean)
            # Remove trailing underscores
            clean = clean.strip("_")
            return clean

        sanitized_app = sanitize_label(app)
        sanitized_event = sanitize_label(event_type)

        # Create or get counter for learning observations
        from .core import Counter

        metric = Counter(
            "kagami_learning_observation_events_total",
            "Learning observation events",
            ["app", "event_type"],
        )
        metric.labels(app=sanitized_app, event_type=sanitized_event).inc()

    except Exception as e:
        import logging

        logging.getLogger(__name__).debug(f"Failed to record learning observation: {e}")


# AUTH_LOCKOUTS, POLICY_DECISION_TOTAL, QUORUM_DECISIONS_TOTAL, RATE_LIMIT_BLOCKS
# already fetched from catalog above (lines 43-46)

__all__ = [
    "EXPERIENCE_BUS_EVENTS_TOTAL",
    "ORCH_TEMPLATES_SECONDS",
    "ORCH_TEMPLATES_TOTAL",
    "REENTRANT_PASS_SECONDS",
    "SYSTEM_MEMORY_ALERTS_TOTAL",
    "WORKSPACE_COMPETITION_RATE",
]

SYSTEM_MEMORY_ALERTS_TOTAL = Counter(
    "kagami_system_memory_alerts_total",
    "System Memory Alerts Total",
)

REENTRANT_PASS_SECONDS = Histogram(
    "kagami_reentrant_pass_seconds",
    "Reentrant Pass Seconds",
)

EXPERIENCE_BUS_EVENTS_TOTAL = Counter(
    "kagami_experience_bus_events_total",
    "Experience Bus Events Total",
    ["event_type"],
)

ORCH_TEMPLATES_SECONDS = Histogram(
    "kagami_orch_templates_seconds",
    "Orch Templates Seconds",
)
ORCH_TEMPLATES_TOTAL = Counter(
    "kagami_orch_templates_total",
    "Orch Templates Total",
)

WORKSPACE_COMPETITION_RATE = Gauge(
    "kagami_workspace_competition_rate",
    "Workspace Competition Rate",
)

__all__.extend(
    [
        "EXPERIENCE_BUS_EVENTS_TOTAL",
        "ORCH_TEMPLATES_SECONDS",
        "ORCH_TEMPLATES_TOTAL",
        "REENTRANT_PASS_SECONDS",
        "SYSTEM_MEMORY_ALERTS_TOTAL",
        "WORKSPACE_COMPETITION_RATE",
    ]
)
