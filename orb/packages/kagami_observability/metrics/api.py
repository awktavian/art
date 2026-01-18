"""K os Api request/response metrics.

Domain-specific metrics for API request/response metrics.
"""

from kagami_observability.metrics.catalog import get_metric

KAGAMI_HTTP_REQUESTS_TOTAL = get_metric("KAGAMI_HTTP_REQUESTS_TOTAL")
KAGAMI_HTTP_REQUEST_DURATION_SECONDS = get_metric("KAGAMI_HTTP_REQUEST_DURATION_SECONDS")
REQUEST_COUNT = get_metric("REQUEST_COUNT")
REQUEST_DURATION = get_metric("REQUEST_DURATION")
API_ERRORS = get_metric("API_ERRORS")
WS_CONNECTIONS_TOTAL = get_metric("WS_CONNECTIONS_TOTAL")
WEBSOCKET_CONNECTIONS = get_metric("WEBSOCKET_CONNECTIONS")
WS_AUTH_DURATION_SECONDS = get_metric("WS_AUTH_DURATION_SECONDS")
WS_AUTH_FAILURES_TOTAL = get_metric("WS_AUTH_FAILURES_TOTAL")
SOCKETIO_CONNECTIONS_TOTAL = get_metric("SOCKETIO_CONNECTIONS_TOTAL")
SOCKETIO_CONNECTIONS_ACTIVE = get_metric("SOCKETIO_CONNECTIONS_ACTIVE")
SOCKETIO_AUTH_DURATION_SECONDS = get_metric("SOCKETIO_AUTH_DURATION_SECONDS")
SOCKETIO_AUTH_FAILURES_TOTAL = get_metric("SOCKETIO_AUTH_FAILURES_TOTAL")
SOCKETIO_EVENTS_TOTAL = get_metric("SOCKETIO_EVENTS_TOTAL")
SOCKETIO_EVENT_LATENCY_SECONDS = get_metric("SOCKETIO_EVENT_LATENCY_SECONDS")
SOCKETIO_ROOMS_ACTIVE = get_metric("SOCKETIO_ROOMS_ACTIVE")
SOCKETIO_BACKPRESSURE_DROPS = get_metric("SOCKETIO_BACKPRESSURE_DROPS")
WS_MESSAGE_LATENCY = get_metric("WS_MESSAGE_LATENCY")
WS_MESSAGES_SENT = get_metric("WS_MESSAGES_SENT")
WS_BACKPRESSURE_TOTAL = get_metric("WS_BACKPRESSURE_TOTAL")
WS_DROPPED_MESSAGES_TOTAL = get_metric("WS_DROPPED_MESSAGES_TOTAL")
WS_BROADCAST_DROPPED = get_metric("WS_BROADCAST_DROPPED")
LIVEKIT_ERRORS_TOTAL = get_metric("LIVEKIT_ERRORS_TOTAL")
LIVEKIT_HEALTH_CHECKS_TOTAL = get_metric("LIVEKIT_HEALTH_CHECKS_TOTAL")
AR_ACK_LATENCY_MS = get_metric("AR_ACK_LATENCY_MS")
AR_FRAMES = get_metric("AR_FRAMES")
INTENT_REQUESTS = get_metric("INTENT_REQUESTS")
BACKGROUND_AGENT_RUNS = get_metric("BACKGROUND_AGENT_RUNS")
BACKGROUND_AGENT_DURATION = get_metric("BACKGROUND_AGENT_DURATION")
SCHEDULER_EVENTS_TOTAL = get_metric("SCHEDULER_EVENTS_TOTAL")
SETTLEMENT_SUBMISSIONS = get_metric("SETTLEMENT_SUBMISSIONS")
STATUS_LAST_RECEIPT_AVAILABLE = get_metric("STATUS_LAST_RECEIPT_AVAILABLE")
WORLD_JOBS_COMPLETED = get_metric("WORLD_JOBS_COMPLETED")
WORLD_ROUTE_DURATION = get_metric("WORLD_ROUTE_DURATION")
PHYSICS_API_LATENCY_SECONDS = get_metric("PHYSICS_API_LATENCY_SECONDS")
LOCAL_INFERENCE_AVAILABLE = get_metric("LOCAL_INFERENCE_AVAILABLE")
INTENT_REQUESTS_BY_ACTION_APP = get_metric("INTENT_REQUESTS_BY_ACTION_APP")
INTENT_CONFIRMATIONS = get_metric("INTENT_CONFIRMATIONS")
IDEMPOTENCY_CHECKS_TOTAL = get_metric("IDEMPOTENCY_CHECKS_TOTAL")
IDEMPOTENCY_CONFLICTS_TOTAL = get_metric("IDEMPOTENCY_CONFLICTS_TOTAL")
IDEMPOTENCY_REPLAY_TOTAL = get_metric("IDEMPOTENCY_REPLAY_TOTAL")
AUTO_RECEIPTS_TOTAL = get_metric("AUTO_RECEIPTS_TOTAL")
WS_IDEMPOTENCY_CHECKS_TOTAL = get_metric("WS_IDEMPOTENCY_CHECKS_TOTAL")
WS_MESSAGE_QUEUE_DEPTH = get_metric("WS_MESSAGE_QUEUE_DEPTH")
WS_BACKPRESSURE_DURATION_SECONDS = get_metric("WS_BACKPRESSURE_DURATION_SECONDS")
ACTIVE_REQUESTS = get_metric("ACTIVE_REQUESTS")
HTTP_REQUEST_DURATION_SECONDS = get_metric("HTTP_REQUEST_DURATION_SECONDS")
AGUI_EVENTS_SENT = get_metric("AGUI_EVENTS_SENT")
AGENT_FITNESS = get_metric("AGENT_FITNESS")
AGENT_TOOL_CALLS_TOTAL = get_metric("AGENT_TOOL_CALLS_TOTAL")


# Helper function for recording intent metrics


def record_intent_metrics(
    action: str = "",
    app: str = "",
    route: str | None = None,
    outcome: str | None = None,
    duration_seconds: float | None = None,
    risk: str | None = None,
) -> None:
    """Record intent metrics (compat layer: increment action/app and observe duration).

    Args:
        action: Intent action (e.g., 'plan.create')
        app: App name (e.g., 'Plans')
        route: API route (optional)
        outcome: Execution outcome (optional)
        duration_seconds: Duration in seconds (optional)
        risk: Risk level (optional)
    """
    try:
        INTENT_REQUESTS.labels(action=action, app=app).inc()
        INTENT_REQUESTS_BY_ACTION_APP.labels(action=action, app=app).inc()

        # If duration provided, observe it
        if duration_seconds is not None and route:
            # Try to get or create a histogram for intent execution duration
            from .core import get_histogram

            hist = get_histogram(
                "kagami_intent_execute_duration_seconds",
                "Intent execution duration",
                ["route", "outcome", "risk"],
            )
            hist.labels(
                route=route or "unknown", outcome=outcome or "unknown", risk=risk or "unknown"
            ).observe(duration_seconds)
    except Exception:
        pass  # Degrade gracefully


# ACTIVE_REQUESTS already fetched from catalog above (line 54)
# HTTP_REQUEST_DURATION_SECONDS already fetched from catalog above (line 55)

__all__ = [
    "ACTIVE_REQUESTS",
    "AGENT_FITNESS",
    "AGENT_TOOL_CALLS_TOTAL",
    "API_ERRORS",
    "AR_ACK_LATENCY_MS",
    "AR_FRAMES",
    "AUTO_RECEIPTS_TOTAL",
    "BACKGROUND_AGENT_DURATION",
    "BACKGROUND_AGENT_RUNS",
    "HTTP_REQUEST_DURATION_SECONDS",
    "IDEMPOTENCY_CHECKS_TOTAL",
    "IDEMPOTENCY_CONFLICTS_TOTAL",
    "IDEMPOTENCY_REPLAY_TOTAL",
    "INTENT_CONFIRMATIONS",
    "INTENT_REQUESTS",
    "INTENT_REQUESTS_BY_ACTION_APP",
    "KAGAMI_HTTP_REQUESTS_TOTAL",
    "KAGAMI_HTTP_REQUEST_DURATION_SECONDS",
    "LIVEKIT_ERRORS_TOTAL",
    "LIVEKIT_HEALTH_CHECKS_TOTAL",
    "LOCAL_INFERENCE_AVAILABLE",
    "PHYSICS_API_LATENCY_SECONDS",
    "REQUEST_COUNT",
    "REQUEST_DURATION",
    "SCHEDULER_EVENTS_TOTAL",
    "SETTLEMENT_SUBMISSIONS",
    "SOCKETIO_BACKPRESSURE_DROPS",
    "STATUS_LAST_RECEIPT_AVAILABLE",
    "WEBSOCKET_CONNECTIONS",
    "WORLD_JOBS_COMPLETED",
    "WORLD_ROUTE_DURATION",
    "WS_AUTH_DURATION_SECONDS",
    "WS_AUTH_FAILURES_TOTAL",
    "WS_BACKPRESSURE_DURATION_SECONDS",
    "WS_CONNECTIONS_TOTAL",
    "WS_IDEMPOTENCY_CHECKS_TOTAL",
    "WS_MESSAGE_QUEUE_DEPTH",
    "record_intent_metrics",
]
