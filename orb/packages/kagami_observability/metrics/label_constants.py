"""Metric Label Constants and Validators.

Bounded label sets for all K os metrics to prevent cardinality explosion.
All metrics must use labels from these predefined sets.

Per Strange Loop Rules (.cursor/rules/11-StrangeLoopRules.mdc):
- Bounded label sets only (method, route, outcome, app, operation)
- No unbounded labels (user IDs, correlation IDs, etc.)
"""

from typing import Literal

# HTTP Methods (bounded set)
HTTP_METHODS: set[str] = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
    "HEAD",
}

# HTTP/API Outcomes (bounded set)
OUTCOME_VALUES: set[str] = {
    "success",
    "error",
    "timeout",
    "validation_error",
    "auth_error",
    "not_found",
    "conflict",
    "rate_limited",
}

# Common Route Patterns (bounded set - extensible but capped)
# Note: Actual route paths should be normalized to patterns
ROUTE_PATTERNS: set[str] = {
    "/api/health",
    "/api/command/execute",
    "/api/receipts",
    "/api/status/summary",
    "/api/forge/generate",
    "/api/reasoning/chat",
    "/health/live",
    "/health/ready",
    "/metrics",
    "other",  # catch-all for less frequent routes
}

# App Names (bounded set for metrics labels)
# Keep in sync with `kagami.core.unified_agents.app_registry` and API routes.
APP_NAMES: set[str] = {
    "plans",
    "forge",
    "notes",
    "files",
    "calendar",
    "health",
    "finance",
    "travel",
    "learning",
    "research",
    "marketplace",
    "sandbox",
    "adaptive",
    "ar",
    "world",
    "other",
}

# Operation Types (for intents/actions)
OPERATION_TYPES: set[str] = {
    "create",
    "read",
    "update",
    "delete",
    "list",
    "execute",
    "validate",
    "transform",
}

# WebSocket Message Types (bounded set)
WS_MESSAGE_TYPES: set[str] = {
    "auth",
    "ping",
    "pong",
    "subscribe",
    "unsubscribe",
    "event",
    "error",
}

# Auth Failure Reasons (bounded set)
AUTH_FAILURE_REASONS: set[str] = {
    "missing_token",
    "invalid_token",
    "expired_token",
    "insufficient_permissions",
    "invalid_signature",
    "missing_claims",
    "timeout",
}

# Idempotency Status (bounded set)
IDEMPOTENCY_STATUS: set[str] = {
    "hit",
    "miss",
    "expired",
    "conflict",
}


# Type aliases for type-safe label usage
HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
Outcome = Literal[
    "success",
    "error",
    "timeout",
    "validation_error",
    "auth_error",
    "not_found",
    "conflict",
    "rate_limited",
]
Operation = Literal[
    "create", "read", "update", "delete", "list", "execute", "validate", "transform"
]


def validate_label(label_type: str, value: str) -> str:
    """Validate label value against bounded set.

    Args:
        label_type: Type of label (method, outcome, app, operation, etc.)
        value: Label value to validate

    Returns:
        Validated value or "other" if not in bounded set

    Raises:
        ValueError: If label_type is unknown
    """
    label_sets = {
        "method": HTTP_METHODS,
        "outcome": OUTCOME_VALUES,
        "route": ROUTE_PATTERNS,
        "app": APP_NAMES,
        "operation": OPERATION_TYPES,
        "ws_type": WS_MESSAGE_TYPES,
        "auth_reason": AUTH_FAILURE_REASONS,
        "idempotency_status": IDEMPOTENCY_STATUS,
    }

    if label_type not in label_sets:
        raise ValueError(f"Unknown label type: {label_type}")

    valid_set = label_sets[label_type]

    # Return value if valid, else return "other" catch-all
    return value if value in valid_set else "other"


def normalize_route_to_pattern(route: str) -> str:
    """Normalize route path to bounded pattern.

    Prevents cardinality explosion from dynamic route parameters.

    Args:
        route: Full route path (e.g., "/api/receipts/corr-123-abc")

    Returns:
        Normalized pattern (e.g., "/api/receipts")
    """
    # Strip query params
    route = route.split("?")[0]

    # Known patterns
    if route.startswith("/api/receipts"):
        return "/api/receipts"
    elif route.startswith("/api/command"):
        return "/api/command/execute"
    elif route.startswith("/api/health"):
        return "/api/health"
    elif route.startswith("/api/status"):
        return "/api/status/summary"
    elif route.startswith("/api/forge"):
        return "/api/forge/generate"
    elif route.startswith("/api/reasoning"):
        return "/api/reasoning/chat"
    elif route.startswith("/health"):
        if "ready" in route:
            return "/health/ready"
        elif "live" in route:
            return "/health/live"
        return "/health"
    elif route == "/metrics":
        return "/metrics"
    else:
        return "other"


__all__ = [
    "APP_NAMES",
    "AUTH_FAILURE_REASONS",
    "HTTP_METHODS",
    "IDEMPOTENCY_STATUS",
    "OPERATION_TYPES",
    "OUTCOME_VALUES",
    "ROUTE_PATTERNS",
    "WS_MESSAGE_TYPES",
    "HttpMethod",
    "Operation",
    "Outcome",
    "normalize_route_to_pattern",
    "validate_label",
]
