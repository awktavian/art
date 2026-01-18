from __future__ import annotations

"""Central registry for K os observability metrics."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from kagami_observability.metrics.core import Counter, Gauge, Histogram

MetricKind = Literal["counter", "gauge", "histogram"]


@dataclass(frozen=True)
class MetricSpec:
    kind: MetricKind
    metric_name: str
    description: str
    labels: Sequence[str] = ()


_TYPE_MAP: dict[MetricKind, Any] = {
    "counter": Counter,
    "gauge": Gauge,
    "histogram": Histogram,
}


_METRIC_SPECS: dict[str, MetricSpec] = {
    # API metrics
    "KAGAMI_HTTP_REQUESTS_TOTAL": MetricSpec(
        "counter",
        "kagami_http_requests_total",
        "Total HTTP requests",
        ("method", "route", "status_code"),
    ),
    "KAGAMI_HTTP_REQUEST_DURATION_SECONDS": MetricSpec(
        "histogram",
        "kagami_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ("method", "route"),
    ),
    "API_ERRORS": MetricSpec(
        "counter",
        "kagami_api_errors",
        "Total API errors",
        ("route", "error_type"),
    ),
    "WS_CONNECTIONS_TOTAL": MetricSpec(
        "counter",
        "kagami_ws_connections",
        "Total WebSocket connections",
        ("status",),
    ),
    "WEBSOCKET_CONNECTIONS": MetricSpec(
        "gauge",
        "kagami_websocket_connections_active",
        "Active WebSocket connections",
    ),
    "WS_AUTH_DURATION_SECONDS": MetricSpec(
        "histogram",
        "kagami_ws_auth_duration_seconds",
        "WebSocket authentication duration",
    ),
    "WS_AUTH_FAILURES_TOTAL": MetricSpec(
        "counter",
        "kagami_ws_auth_failures",
        "Total WebSocket auth failures by reason and K-8XXX error code",
        ("reason", "error_code"),
    ),
    "SOCKETIO_CONNECTIONS_TOTAL": MetricSpec(
        "counter",
        "kagami_socketio_connections",
        "Total Socket.IO connections",
        ("namespace", "status"),
    ),
    "SOCKETIO_CONNECTIONS_ACTIVE": MetricSpec(
        "gauge",
        "kagami_socketio_connections_active",
        "Active Socket.IO connections",
        ("namespace",),
    ),
    "SOCKETIO_AUTH_DURATION_SECONDS": MetricSpec(
        "histogram",
        "kagami_socketio_auth_duration_seconds",
        "Socket.IO authentication duration",
        ("auth_type",),
    ),
    "SOCKETIO_AUTH_FAILURES_TOTAL": MetricSpec(
        "counter",
        "kagami_socketio_auth_failures",
        "Total Socket.IO auth failures",
        ("reason",),
    ),
    "SOCKETIO_EVENTS_TOTAL": MetricSpec(
        "counter",
        "kagami_socketio_events",
        "Total Socket.IO events",
        ("namespace", "event_type", "direction"),
    ),
    "AGUI_EVENTS_SENT": MetricSpec(
        "counter",
        "kagami_agui_events_sent",
        "Total AGUI WebSocket events sent to frontend",
        ("event_type",),
    ),
    "SOCKETIO_EVENT_LATENCY_SECONDS": MetricSpec(
        "histogram",
        "kagami_socketio_event_latency_seconds",
        "Socket.IO event processing latency",
        ("namespace", "event_type"),
    ),
    "SOCKETIO_ROOMS_ACTIVE": MetricSpec(
        "gauge",
        "kagami_socketio_rooms_active",
        "Active Socket.IO rooms",
        ("namespace",),
    ),
    "SOCKETIO_BACKPRESSURE_DROPS": MetricSpec(
        "counter",
        "kagami_socketio_backpressure_drops_total",
        "Socket.IO events dropped due to backpressure",
        ("namespace", "reason"),
    ),
    "WS_MESSAGE_LATENCY": MetricSpec(
        "histogram",
        "kagami_ws_message_latency_seconds",
        "WebSocket message send latency",
        ("namespace",),
    ),
    "WS_MESSAGES_SENT": MetricSpec(
        "counter",
        "kagami_ws_messages_sent",
        "WebSocket messages sent",
        ("namespace",),
    ),
    "WS_BACKPRESSURE_TOTAL": MetricSpec(
        "counter",
        "kagami_ws_backpressure",
        "WebSocket backpressure events",
        ("namespace",),
    ),
    "WS_DROPPED_MESSAGES_TOTAL": MetricSpec(
        "counter",
        "kagami_ws_dropped_messages",
        "WebSocket messages dropped due to backpressure",
        ("namespace",),
    ),
    "WS_BROADCAST_DROPPED": MetricSpec(
        "counter",
        "kagami_ws_broadcast_dropped",
        "WebSocket broadcasts dropped",
        ("event",),
    ),
    "LIVEKIT_ERRORS_TOTAL": MetricSpec(
        "counter",
        "kagami_livekit_errors",
        "Total LiveKit errors",
        ("error_type",),
    ),
    "LIVEKIT_HEALTH_CHECKS_TOTAL": MetricSpec(
        "counter",
        "kagami_livekit_health_checks",
        "Total LiveKit health checks",
        ("status",),
    ),
    "AR_ACK_LATENCY_MS": MetricSpec(
        "histogram",
        "kagami_ar_ack_latency_milliseconds",
        "AR acknowledgement latency in milliseconds",
    ),
    "AR_FRAMES": MetricSpec(
        "counter",
        "kagami_ar_frames",
        "AR frames processed",
        ("frame_type",),
    ),
    "INTENT_REQUESTS": MetricSpec(
        "counter",
        "kagami_intent_requests",
        "Total intent requests",
        ("action", "app"),
    ),
    "BACKGROUND_AGENT_RUNS": MetricSpec(
        "counter",
        "kagami_background_agent_runs",
        "Background agent executions",
        ("agent_type", "status"),
    ),
    "BACKGROUND_AGENT_DURATION": MetricSpec(
        "histogram",
        "kagami_background_agent_duration_seconds",
        "Background agent execution duration",
        ("agent_type",),
    ),
    "SCHEDULER_EVENTS_TOTAL": MetricSpec(
        "counter",
        "kagami_scheduler_events",
        "Total scheduler events",
        ("event_type",),
    ),
    "SETTLEMENT_SUBMISSIONS": MetricSpec(
        "counter",
        "kagami_settlement_submissions",
        "Settlement submissions",
        ("status",),
    ),
    "STATUS_LAST_RECEIPT_AVAILABLE": MetricSpec(
        "gauge",
        "kagami_status_last_receipt_available",
        "Whether last receipt is available",
    ),
    "WORLD_JOBS_COMPLETED": MetricSpec(
        "counter",
        "kagami_world_jobs_completed",
        "World model jobs completed",
        ("job_type",),
    ),
    "WORLD_ROUTE_DURATION": MetricSpec(
        "histogram",
        "kagami_world_route_duration_seconds",
        "World route duration",
        ("route",),
    ),
    "PHYSICS_API_LATENCY_SECONDS": MetricSpec(
        "histogram",
        "kagami_physics_api_latency_seconds",
        "Physics API latency",
        ("operation",),
    ),
    "LOCAL_INFERENCE_AVAILABLE": MetricSpec(
        "gauge",
        "kagami_local_inference_available",
        "Whether local inference is available",
    ),
    "INTENT_REQUESTS_BY_ACTION_APP": MetricSpec(
        "counter",
        "kagami_intent_requests_by_action_app",
        "Intent requests broken down by action and app",
        ("action", "app"),
    ),
    "INTENT_CONFIRMATIONS": MetricSpec(
        "counter",
        "kagami_intent_confirmations",
        "Intent confirmation requests",
        ("intent_type", "confirmed"),
    ),
    "IDEMPOTENCY_CHECKS_TOTAL": MetricSpec(
        "counter",
        "kagami_idempotency_checks_total",
        "Total idempotency checks (middleware and Redis)",
        ("status",),
    ),
    "IDEMPOTENCY_CONFLICTS_TOTAL": MetricSpec(
        "counter",
        "kagami_idempotency_conflicts_total",
        "Total idempotency conflicts (HTTP)",
    ),
    "IDEMPOTENCY_REPLAY_TOTAL": MetricSpec(
        "counter",
        "kagami_idempotency_replay_total",
        "Total idempotency response replays (HTTP)",
    ),
    "AUTO_RECEIPTS_TOTAL": MetricSpec(
        "counter",
        "kagami_auto_receipts_total",
        "Auto-emitted receipts via middleware",
        ("app", "method", "status"),
    ),
    "WS_IDEMPOTENCY_CHECKS_TOTAL": MetricSpec(
        "counter",
        "kagami_ws_idempotency_checks_total",
        "Total WebSocket idempotency checks",
        ("result",),
    ),
    "WS_MESSAGE_QUEUE_DEPTH": MetricSpec(
        "gauge",
        "kagami_ws_message_queue_depth",
        "WebSocket message queue depth",
        ("namespace",),
    ),
    "WS_BACKPRESSURE_DURATION_SECONDS": MetricSpec(
        "histogram",
        "kagami_ws_backpressure_duration_seconds",
        "Duration of backpressure events",
        ("namespace",),
    ),
    "ACTIVE_REQUESTS": MetricSpec(
        "gauge",
        "kagami_active_requests",
        "Active Requests",
    ),
    # System metrics
    "BOOT_PHASE_DURATION_MS": MetricSpec(
        "histogram",
        "kagami_boot_phase_duration_ms",
        "Duration of boot phases (ms)",
        ("phase",),
    ),
    "BOOT_TIME_TO_READY_MS": MetricSpec(
        "gauge",
        "kagami_boot_time_to_ready_ms",
        "Time to application ready (ms)",
    ),
    "BOOT_NODE_DURATION_MS": MetricSpec(
        "histogram",
        "kagami_boot_node_duration_ms",
        "Duration of individual boot nodes (ms)",
        ("node",),
    ),
    "BOOT_MEMORY_PEAK_MB": MetricSpec(
        "gauge",
        "kagami_boot_memory_peak_mb",
        "Peak memory usage during boot (MB)",
    ),
    "BOOT_CPU_AVERAGE_PERCENT": MetricSpec(
        "gauge",
        "kagami_boot_cpu_average_percent",
        "Average CPU usage during boot (%)",
    ),
    "RELATIONSHIP_GRAPH_EDGES_TOTAL": MetricSpec(
        "gauge",
        "kagami_relationship_graph_edges_total",
        "Total edges in the relationship graph",
    ),
    "RELATIONSHIP_GRAPH_NODES_TOTAL": MetricSpec(
        "gauge",
        "kagami_relationship_graph_nodes_total",
        "Total nodes in the relationship graph",
    ),
    "EXTERNAL_ERRORS_TOTAL": MetricSpec(
        "counter",
        "kagami_external_errors_total",
        "Total external API/service errors",
        ("service", "error_type"),
    ),
    "EXTERNAL_REQUEST_DURATION": MetricSpec(
        "histogram",
        "kagami_external_request_duration_seconds",
        "External request duration",
        ("service", "endpoint"),
    ),
    "PRODUCTION_CONTROL_CIRCUIT_OPEN": MetricSpec(
        "counter",
        "kagami_production_control_circuit_open_total",
        "Total production control circuit openings",
        ("operation", "error_type"),
    ),
    "PRODUCTION_CONTROL_DEGRADATION": MetricSpec(
        "gauge",
        "kagami_production_control_degradation",
        "Current degradation level (0=none, 1=full)",
        ("control_name",),
    ),
    "REFLECTION_DURATION_SECONDS": MetricSpec(
        "histogram",
        "kagami_reflection_duration_seconds",
        "Duration of reflection operations",
        ("reflection_type",),
    ),
    "REFLECTION_INSIGHTS_TOTAL": MetricSpec(
        "counter",
        "kagami_reflection_insights_total",
        "Total insights generated from reflection",
        ("insight_type",),
    ),
    "DB_QUERY_SECONDS": MetricSpec(
        "histogram",
        "kagami_db_query_duration_seconds",
        "Database query duration",
        ("operation",),
    ),
    "DB_QUERY_ERRORS": MetricSpec(
        "counter",
        "kagami_db_query_errors_total",
        "Database query errors",
        ("operation", "error_type"),
    ),
    "DB_CONNECTION_POOL_SIZE": MetricSpec(
        "gauge",
        "kagami_db_connection_pool_size",
        "Database connection pool size",
        ("state",),
    ),
    "SYSTEM_CPU_PERCENT": MetricSpec(
        "gauge",
        "kagami_system_cpu_percent",
        "System CPU utilization (0-100)",
    ),
    "SYSTEM_CPU_USAGE": MetricSpec(
        "gauge",
        "kagami_system_cpu_usage",
        "Normalized system CPU usage (0.0-1.0)",
    ),
    "SYSTEM_MEMORY_BYTES": MetricSpec(
        "gauge",
        "kagami_system_memory_bytes",
        "System memory usage in bytes",
        ("type",),
    ),
    "SYSTEM_MEMORY_USAGE": MetricSpec(
        "gauge",
        "kagami_system_memory_usage",
        "Normalized system memory usage (0.0-1.0)",
    ),
    "SYSTEM_DISK_BYTES": MetricSpec(
        "gauge",
        "kagami_system_disk_bytes",
        "System disk usage in bytes",
        ("mount_point", "type"),
    ),
    "REFLECTIONS_TOTAL": MetricSpec(
        "counter",
        "kagami_reflections_total",
        "Total reflection operations",
        ("type", "status"),
    ),
    "PRODUCTION_CONTROL_LIMIT_HIT": MetricSpec(
        "counter",
        "kagami_production_control_limit_hit_total",
        "Total times production control limits were hit",
        ("limit_type",),
    ),
    "CHARACTER_GENERATIONS": MetricSpec(
        "counter",
        "kagami_character_generations",
        "Character generation outcomes",
        ("status", "quality"),  # status: success/success_cached/error, quality: preview/draft/final
    ),
    "COLLABORATION_TASKS": MetricSpec(
        "counter",
        "kagami_collaboration_tasks",
        "Collaboration task outcomes",
        ("type", "status"),
    ),
    "PLUGIN_LOADS": MetricSpec(
        "counter",
        "kagami_plugin_loads",
        "Plugin load outcomes",
        ("plugin", "status"),
    ),
    "QUALITY_SCORES": MetricSpec(
        "histogram",
        "kagami_quality_scores",
        "Quality scores by category",
        ("category",),
    ),
    "GENUI_CACHE_HITS": MetricSpec(
        "counter",
        "kagami_genui_cache_hits",
        "Cache hits for GenUI operations",
        ("operation",),
    ),
    "GENUI_GENERATE_DURATION": MetricSpec(
        "histogram",
        "kagami_genui_generate_duration_seconds",
        "GenUI generate duration in seconds",
        ("operation",),
    ),
    "GENUI_REQUESTS": MetricSpec(
        "counter",
        "kagami_genui_requests",
        "GenUI requests",
        ("operation", "status"),
    ),
    "MEMORY_MIRROR_ATTEMPTS_TOTAL": MetricSpec(
        "counter",
        "kagami_memory_mirror_attempts_total",
        "Total memory mirror attempts",
        ("source",),
    ),
    "MEMORY_MIRROR_ERRORS_TOTAL": MetricSpec(
        "counter",
        "kagami_memory_mirror_errors_total",
        "Total memory mirror errors",
        ("source", "error_type"),
    ),
    "MEMORY_MIRROR_SUCCESS_TOTAL": MetricSpec(
        "counter",
        "kagami_memory_mirror_success_total",
        "Total successful memory mirror operations",
        ("source",),
    ),
    "RAG_INVOCATIONS_TOTAL": MetricSpec(
        "counter",
        "kagami_rag_invocations_total",
        "Total RAG invocations",
        ("domain",),
    ),
    "RAG_RESULTS_TOTAL": MetricSpec(
        "counter",
        "kagami_rag_results_total",
        "Total RAG results returned",
        ("domain",),
    ),
    "LINEAR_WEBHOOKS": MetricSpec(
        "counter",
        "kagami_linear_webhooks",
        "Linear webhook events",
        ("event", "status"),
    ),
    "AUTH_LOCKOUTS": MetricSpec(
        "gauge",
        "kagami_auth_lockouts",
        "Auth Lockouts",
        ("reason",),
    ),
    "POLICY_DECISION_TOTAL": MetricSpec(
        "counter",
        "kagami_policy_decision_total",
        "Policy Decision Total",
    ),
    "QUORUM_DECISIONS_TOTAL": MetricSpec(
        "counter",
        "kagami_quorum_decisions_total",
        "Quorum Decisions Total",
    ),
    "RATE_LIMIT_BLOCKS": MetricSpec(
        "gauge",
        "kagami_rate_limit_blocks",
        "Rate Limit Blocks",
    ),
    "FEATURE_FLAGS_ACTIVE": MetricSpec(
        "gauge",
        "kagami_feature_flags_active",
        "Active feature flags configuration (Q1 2026)",
        ("feature", "state"),
    ),
    # Agent metrics
    "AGENT_FITNESS": MetricSpec(
        "gauge",
        "kagami_agent_fitness",
        "Agent fitness score (0-1)",
        ("domain",),
    ),
    "AGENT_TOOL_CALLS_TOTAL": MetricSpec(
        "counter",
        "kagami_agent_tool_calls_total",
        "Total agent tool calls",
        ("agent", "tool", "status"),
    ),
}

_ALIAS_MAP: dict[str, str] = {
    "REQUEST_COUNT": "KAGAMI_HTTP_REQUESTS_TOTAL",
    "REQUEST_DURATION": "KAGAMI_HTTP_REQUEST_DURATION_SECONDS",
    "HTTP_REQUEST_DURATION_SECONDS": "KAGAMI_HTTP_REQUEST_DURATION_SECONDS",
}

_METRIC_CACHE: dict[str, Any] = {}


def get_metric(key: str) -> Any:
    """Return (and memoize) a metric instance for the given registry key."""

    canonical = _ALIAS_MAP.get(key, key)
    if canonical not in _METRIC_SPECS:
        raise KeyError(f"Unknown metric key '{key}'")

    if canonical not in _METRIC_CACHE:
        spec = _METRIC_SPECS[canonical]
        metric_cls = _TYPE_MAP[spec.kind]
        _METRIC_CACHE[canonical] = metric_cls(spec.metric_name, spec.description, list(spec.labels))
    return _METRIC_CACHE[canonical]


__all__ = ["MetricSpec", "get_metric"]
