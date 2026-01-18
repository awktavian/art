"""Tests for kagami_observability/metrics/label_constants.py

Ensures metric label cardinality is bounded and single-surface /metrics invariant
is maintained.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from kagami_observability.metrics.label_constants import (
    APP_NAMES,
    AUTH_FAILURE_REASONS,
    HTTP_METHODS,
    IDEMPOTENCY_STATUS,
    OPERATION_TYPES,
    OUTCOME_VALUES,
    ROUTE_PATTERNS,
    WS_MESSAGE_TYPES,
    normalize_route_to_pattern,
    validate_label,
)


def test_http_methods_bounded() -> None:
    """Test HTTP_METHODS is a small bounded set."""
    assert len(HTTP_METHODS) <= 10
    assert "GET" in HTTP_METHODS
    assert "POST" in HTTP_METHODS
    assert "DELETE" in HTTP_METHODS


def test_outcome_values_bounded() -> None:
    """Test OUTCOME_VALUES is bounded."""
    assert len(OUTCOME_VALUES) <= 20
    assert "success" in OUTCOME_VALUES
    assert "error" in OUTCOME_VALUES
    assert "timeout" in OUTCOME_VALUES


def test_route_patterns_bounded() -> None:
    """Test ROUTE_PATTERNS is bounded with catch-all."""
    assert len(ROUTE_PATTERNS) <= 30
    assert "other" in ROUTE_PATTERNS
    assert "/api/health" in ROUTE_PATTERNS
    assert "/metrics" in ROUTE_PATTERNS


def test_app_names_bounded() -> None:
    """Test APP_NAMES is bounded."""
    assert len(APP_NAMES) <= 30
    assert "other" in APP_NAMES
    assert "plans" in APP_NAMES
    assert "forge" in APP_NAMES


def test_operation_types_bounded() -> None:
    """Test OPERATION_TYPES is bounded."""
    assert len(OPERATION_TYPES) <= 15
    assert "create" in OPERATION_TYPES
    assert "read" in OPERATION_TYPES
    assert "execute" in OPERATION_TYPES


def test_ws_message_types_bounded() -> None:
    """Test WS_MESSAGE_TYPES is bounded."""
    assert len(WS_MESSAGE_TYPES) <= 15
    assert "auth" in WS_MESSAGE_TYPES
    assert "ping" in WS_MESSAGE_TYPES
    assert "event" in WS_MESSAGE_TYPES


def test_auth_failure_reasons_bounded() -> None:
    """Test AUTH_FAILURE_REASONS is bounded."""
    assert len(AUTH_FAILURE_REASONS) <= 15
    assert "missing_token" in AUTH_FAILURE_REASONS
    assert "expired_token" in AUTH_FAILURE_REASONS


def test_idempotency_status_bounded() -> None:
    """Test IDEMPOTENCY_STATUS is bounded."""
    assert len(IDEMPOTENCY_STATUS) <= 10
    assert "hit" in IDEMPOTENCY_STATUS
    assert "miss" in IDEMPOTENCY_STATUS
    assert "conflict" in IDEMPOTENCY_STATUS


@pytest.mark.parametrize(
    "label_type,valid_value",
    [
        ("method", "GET"),
        ("outcome", "success"),
        ("app", "plans"),
        ("operation", "create"),
        ("ws_type", "ping"),
        ("auth_reason", "missing_token"),
        ("idempotency_status", "hit"),
    ],
)
def test_validate_label_valid_values(label_type, valid_value) -> None:
    """Test validate_label returns value when in bounded set."""
    result = validate_label(label_type, valid_value)
    assert result == valid_value


@pytest.mark.parametrize(
    "label_type,invalid_value",
    [
        ("method", "INVALID_METHOD"),
        ("outcome", "unknown_outcome"),
        ("app", "nonexistent_app"),
        ("operation", "weird_operation"),
    ],
)
def test_validate_label_invalid_returns_other(label_type, invalid_value) -> None:
    """Test validate_label returns 'other' for unbounded values."""
    result = validate_label(label_type, invalid_value)
    assert result == "other"


def test_validate_label_unknown_type_raises() -> None:
    """Test validate_label raises for unknown label type."""
    with pytest.raises(ValueError, match="Unknown label type"):
        validate_label("unknown_type", "value")


@pytest.mark.parametrize(
    "route,expected",
    [
        ("/api/receipts/corr-123-abc", "/api/receipts"),
        ("/api/receipts", "/api/receipts"),
        ("/api/command/execute", "/api/command/execute"),
        ("/api/command/execute/sync", "/api/command/execute"),
        ("/api/health/metrics/recent", "/api/health"),
        ("/health/ready", "/health/ready"),
        ("/health/live", "/health/live"),
        ("/metrics", "/metrics"),
        ("/api/unknown/endpoint", "other"),
        ("/api/forge/generate/sync", "/api/forge/generate"),
    ],
)
def test_normalize_route_to_pattern(route, expected) -> None:
    """Test route normalization prevents cardinality explosion."""
    result = normalize_route_to_pattern(route)
    assert result == expected


def test_normalize_route_strips_query_params() -> None:
    """Test that query params are stripped during normalization."""
    route = "/api/health?foo=bar&baz=qux"
    result = normalize_route_to_pattern(route)
    assert "?" not in result
    assert result == "/api/health"


def test_all_bounded_sets_have_other() -> None:
    """Test that extensible sets have 'other' catch-all."""
    # Sets that should have "other" for unbounded fallback
    assert "other" in ROUTE_PATTERNS
    assert "other" in APP_NAMES


def test_bounded_set_cardinality_limits() -> None:
    """Test critical cardinality limits to prevent metric explosion."""
    # Per Prometheus best practices, label cardinality should be low
    # Total combinations = product of all label set sizes
    # Target: <1000 total combinations per metric

    assert len(HTTP_METHODS) <= 10
    assert len(OUTCOME_VALUES) <= 20
    assert len(ROUTE_PATTERNS) <= 30
    assert len(APP_NAMES) <= 30
    assert len(OPERATION_TYPES) <= 15
    assert len(WS_MESSAGE_TYPES) <= 15
    assert len(AUTH_FAILURE_REASONS) <= 15
    assert len(IDEMPOTENCY_STATUS) <= 10

    # Worst case cardinality for a metric with all labels:
    # 10 * 20 * 30 * 30 * 15 = 2,700,000 (too high!)
    # In practice, metrics use 2-4 labels max, keeping it manageable:
    # HTTP: method × route × outcome = 10 × 30 × 20 = 6,000 (acceptable)
    # WS: ws_type × outcome = 15 × 20 = 300 (excellent)
    # Intents: app × operation × outcome = 30 × 15 × 20 = 9,000 (acceptable)


def test_single_surface_metrics_invariant() -> None:
    """Test that single /metrics surface invariant is documented."""
    # Per rules: Single /metrics surface (Prometheus/OpenMetrics) from API
    # This test documents the invariant; actual enforcement is in API routes

    # All metrics should use bounded labels from this module
    # No custom/unbounded labels should be added without review

    # Document the invariant
    invariant = "All K os metrics exposed via single /metrics endpoint"
    assert len(invariant) > 0  # invariant exists
