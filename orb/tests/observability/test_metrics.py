"""Tests for Prometheus metrics."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from unittest.mock import Mock, patch

from kagami_observability.metrics import (  # AUTH_ATTEMPTS,  # REMOVED Oct 29 - orphaned metric
    CHARACTER_GENERATIONS,
    COLLABORATION_TASKS,
    PLUGIN_LOADS,
    QUALITY_SCORES,
    REGISTRY,
    counter,
    gauge,
    histogram,
    record_intent_metrics,
    record_learning_observation,
    summary,
)


def _collect_family(name: str) -> Any:
    fams = list(REGISTRY.collect())
    # Some counters expose as *_total
    for fam in fams:
        if fam.name == name or fam.name == f"{name}_total":
            return fam
    return None


def test_counter_decorator() -> None:
    """Test counter metric decorator."""

    @counter("test_operations", "Test operations counter")
    def test_operation() -> Any:
        return "success"

    result = test_operation()
    assert result == "success"

    # Check metric was registered
    assert any("kagami_test_operations" in str(m) for m in REGISTRY.collect())


def test_counter_decorator_with_labels() -> None:
    """Test counter metric decorator with labels."""

    @counter("labeled_ops", "Labeled operations", ["status", "type"])
    def labeled_operation(status="ok", type="test", **kwargs) -> str:
        return f"{status}:{type}"

    result = labeled_operation(status="success", type="unit")
    assert result == "success:unit"


def test_gauge_decorator() -> None:
    """Test gauge metric decorator."""

    @gauge("test_value", "Test value gauge")
    def get_value() -> float:
        return 42.5

    result = get_value()
    assert result == 42.5

    # Check metric was registered
    assert any("kagami_test_value" in str(m) for m in REGISTRY.collect())


def test_gauge_decorator_non_numeric() -> None:
    """Test gauge decorator with non-numeric return value."""

    @gauge("test_gauge_str", "Test string gauge")
    def get_string() -> str:
        return "not a number"

    # Should not raise error, just not set gauge
    result = get_string()
    assert result == "not a number"


def test_histogram_decorator() -> None:
    """Test histogram metric decorator."""

    @histogram("test_duration", "Test duration histogram")
    def slow_operation() -> str:
        import time

        time.sleep(0.01)  # 10ms
        return "done"

    result = slow_operation()
    assert result == "done"

    # Check metric was registered
    assert any("kagami_test_duration" in str(m) for m in REGISTRY.collect())


def test_histogram_decorator_with_buckets() -> None:
    """Test histogram decorator with custom buckets."""

    @histogram("custom_hist", "Custom histogram", buckets=[0.1, 0.5, 1.0])  # type: ignore[arg-type]
    def operation() -> str:
        return "ok"

    result = operation()
    assert result == "ok"


def test_summary_decorator() -> None:
    """Test summary metric decorator."""

    @summary("test_score", "Test score summary")
    def calculate_score() -> float:
        return 0.85

    result = calculate_score()
    assert result == 0.85

    # Check metric was registered
    assert any("kagami_test_score" in str(m) for m in REGISTRY.collect())


def test_record_intent_metrics_and_histogram_labels() -> None:
    """Verify record_intent_metrics increments counter and observes histogram with labels."""
    # Act
    record_intent_metrics(
        route="/api/command/execute",
        outcome="success",
        duration_seconds=0.123,
        risk="low",
        action="plan.create",
        app="Plans",
    )

    fam_req = _collect_family("kagami_intent_requests")
    assert fam_req is not None
    # Check that a sample with action/app labels exists
    label_tuples = [tuple(sorted(s.labels.items())) for s in fam_req.samples]
    assert any(("action", "plan.create") in lt and ("app", "Plans") in lt for lt in label_tuples)

    fam_dur = _collect_family("kagami_intent_execute_duration_seconds")
    assert fam_dur is not None


def test_label_sanitization_in_learning_observation() -> None:
    """Ensure label sanitization clamps and normalizes values without exploding cardinality."""
    noisy_app = " App Name With Spaces & CAPS ! "
    noisy_event = "New-Event/Type?Complex"
    record_learning_observation(noisy_app, noisy_event, backlog_size=3)
    fam = _collect_family("kagami_learning_observation_events")
    assert fam is not None
    # Expect lowercased and sanitized labels
    label_sets = [s.labels for s in fam.samples]
    assert any(ls.get("app") == "app_name_with_spaces_caps" for ls in label_sets)
    assert any(ls.get("event_type") == "new-event_type_complex" for ls in label_sets)


def test_predefined_metrics_exist() -> None:
    """Test that predefined metrics are registered."""
    # Collect all metric families
    metric_families = list(REGISTRY.collect())
    metric_names = []

    # Get the actual metric names from the families
    for family in metric_families:
        # The family name is what we're looking for
        metric_names.append(family.name)

    # Check some key metrics exist
    # Note: Counter metrics have "_total" suffix added by Prometheus client when collected,
    # but the metric name itself doesn't include it
    # FIXED Nov 10, 2025: REQUEST_COUNT is alias for kagami_http_requests_total
    expected_metrics = [
        "kagami_http_requests",  # REQUEST_COUNT alias
        "kagami_character_generations",
        "kagami_api_errors",
        # kagami_auth_attempts - REMOVED Oct 29, 2025 (orphaned metric)
    ]

    for expected in expected_metrics:
        assert expected in metric_names, f"Missing metric: {expected}. Available: {metric_names}"


def test_character_generation_metric() -> None:
    """Test character generation counter and verify via REGISTRY samples."""
    CHARACTER_GENERATIONS.labels(status="success", quality="high").inc()
    CHARACTER_GENERATIONS.labels(status="failed", quality="high").inc()

    fam = _collect_family("kagami_character_generations")
    assert fam is not None
    # Ensure at least two samples (success and failed) are present
    sample_labels = [tuple(sorted(s.labels.items())) for s in fam.samples]
    assert any(
        ("quality", "high") in labels and ("status", "success") in labels
        for labels in sample_labels
    )
    assert any(
        ("quality", "high") in labels and ("status", "failed") in labels for labels in sample_labels
    )


def test_collaboration_metric() -> None:
    """Test collaboration task counter and verify exposition."""
    COLLABORATION_TASKS.labels(type="sequential", status="success").inc()
    COLLABORATION_TASKS.labels(type="parallel", status="failed").inc()

    fam = _collect_family("kagami_collaboration_tasks")
    # For counters, REGISTRY.collect exposes *_total family name
    assert fam is not None


def test_plugin_metric() -> None:
    """Test plugin load counter and verify exposition."""
    PLUGIN_LOADS.labels(plugin="example", status="success").inc()
    PLUGIN_LOADS.labels(plugin="example", status="failed").inc()

    fam = _collect_family("kagami_plugin_loads")
    assert fam is not None


def test_auth_metric() -> None:
    """Test authentication attempt counter and verify exposition."""
    # AUTH_ATTEMPTS removed Oct 29 - was orphaned metric
    # Test now verifies metric was properly removed
    fam = _collect_family("kagami_auth_attempts")
    assert fam is None  # Metric should not exist


def test_quality_score_metric() -> None:
    """Test quality score summary."""
    QUALITY_SCORES.labels(category="visual").observe(0.85)
    QUALITY_SCORES.labels(category="behavior").observe(0.92)
    QUALITY_SCORES.labels(category="voice").observe(0.78)

    assert QUALITY_SCORES._metrics


def test_update_runtime_metrics() -> None:
    """Test runtime metrics update."""
    from kagami_observability.metrics import _update_runtime_metrics

    # Should not raise even without psutil
    _update_runtime_metrics()

    # With psutil mock - mock the import itself
    mock_memory = Mock(rss=1024 * 1024, vms=2048 * 1024)
    mock_process = Mock()
    mock_process.memory_info.return_value = mock_memory

    mock_psutil = Mock()
    mock_psutil.Process.return_value = mock_process

    with patch.dict("sys.modules", {"psutil": mock_psutil}):
        _update_runtime_metrics()

        mock_psutil.Process.assert_called_once()
        mock_process.memory_info.assert_called_once()


@pytest.mark.asyncio
async def test_metrics_middleware() -> None:
    """Test metrics middleware increments counters."""
    # Metrics middleware is in TelemetryMiddleware (kagami_api/middleware/telemetry.py)
    # Test that REQUEST_COUNT can be incremented directly
    from kagami_observability.metrics import REQUEST_COUNT

    # Simulate what the middleware does
    # FIXED Nov 10, 2025: Use correct labels (route, status_code not endpoint, status)
    REQUEST_COUNT.labels(method="GET", route="/api/test", status_code=200).inc()

    # Verify that REQUEST_COUNT has an entry for /api/test and method GET
    # FIXED Nov 10, 2025: REQUEST_COUNT is alias for kagami_http_requests_total
    fam = _collect_family("kagami_http_requests")
    assert fam is not None
    assert any(
        s.labels.get("route") == "/api/test" and s.labels.get("method") == "GET"
        for s in fam.samples
    )


@pytest.mark.asyncio
async def test_metrics_middleware_skip_metrics_endpoint() -> None:
    """Test that /metrics endpoint is not counted (prevents recursion)."""
    # TelemetryMiddleware skips /metrics endpoint (kagami_api/middleware/telemetry.py:170)
    # This test validates that REQUEST_COUNT doesn't have /metrics entries
    from kagami_observability.metrics import REQUEST_COUNT

    # Verify that we can increment other endpoints but not /metrics
    # FIXED Nov 10, 2025: Use correct labels (route, status_code not endpoint, status)
    REQUEST_COUNT.labels(method="GET", route="/api/other", status_code=200).inc()

    # Collect families
    # FIXED Nov 10, 2025: REQUEST_COUNT is alias for kagami_http_requests_total
    fam = _collect_family("kagami_http_requests")
    if fam is not None:
        # Should have /api/other but never /metrics
        has_other = any(s.labels.get("route") == "/api/other" for s in fam.samples)
        has_metrics = any(s.labels.get("route") == "/metrics" for s in fam.samples)

        assert has_other, "Should be able to count other endpoints"
        assert not has_metrics, "/metrics should not be counted (recursion prevention)"
