"""Integration tests for K os observability stack focusing on real behavior."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import logging


class TestLoggingSetup:
    """Ensure logging configuration actually updates loggers."""

    def test_logging_configuration(self) -> None:
        from kagami_observability.logging_setup import setup_logging

        setup_logging(level=logging.INFO)
        logger = logging.getLogger("kagami.test.observability")
        logger.info("observability smoke test")

        # Logger level should be INFO or 0 (inheriting from root)
        assert logger.level in (0, logging.INFO)

        # Verify we can get effective level
        effective = logger.getEffectiveLevel()
        assert effective <= logging.INFO, "Effective level should allow INFO logging"

    def test_logging_configuration_warning_level(self) -> None:
        """Test that WARNING level filters out INFO messages."""
        from kagami_observability.logging_setup import setup_logging

        setup_logging(level=logging.WARNING)
        logger = logging.getLogger("kagami.test.warning_level")

        # Effective level should be WARNING or higher
        effective = logger.getEffectiveLevel()
        assert effective >= logging.WARNING, "Effective level should be WARNING or higher"


class TestTracing:
    """Validate tracing decorators wrap real callables."""

    @pytest.mark.asyncio
    async def test_traced_async_function(self) -> None:
        from kagami_observability.trace import traced

        trace_payload = {"executed": False, "call_count": 0}

        @traced("test_async_trace")
        async def test_func() -> Any:
            trace_payload["executed"] = True
            trace_payload["call_count"] += 1
            return "success"

        result = await test_func()

    def test_traced_sync_function(self) -> None:
        from kagami_observability.trace import traced

    def test_traced_sync_function_executes_and_returns(self) -> None:
        """Test that traced sync function executes properly and returns correct value."""
        from kagami_observability.trace import traced

        span_metadata = {"executed": False, "call_count": 0}

        @traced("test_sync_trace")
        def test_func() -> Any:
            span_metadata["executed"] = True
            span_metadata["call_count"] += 1
            return "success"

        result = test_func()

        assert result == "success", "Return value should be preserved"
        assert span_metadata["executed"] is True, "Function body should execute"
        assert span_metadata["call_count"] == 1, "Function should be called exactly once"

    @pytest.mark.asyncio
    async def test_traced_async_function_propagates_exceptions(self) -> None:
        """Test that traced decorator propagates exceptions properly."""
        from kagami_observability.trace import traced

        @traced("test_async_exception")
        async def failing_func() -> None:
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await failing_func()

    def test_traced_sync_function_propagates_exceptions(self) -> None:
        """Test that traced sync decorator propagates exceptions properly."""
        from kagami_observability.trace import traced

        @traced("test_sync_exception")
        def failing_func() -> None:
            raise RuntimeError("Sync test error")

        with pytest.raises(RuntimeError, match="Sync test error"):
            failing_func()


class TestTelemetry:
    """Validate telemetry decorator emits tracking events."""

    @pytest.mark.asyncio
    async def test_track_operation_decorator(self) -> None:
        from kagami_observability.telemetry import track_operation

        recorded = {"called": False, "arg_received": None}

        @track_operation("test-operation")
        async def test_func() -> bool:
            recorded["called"] = True
            recorded["arg_received"] = value
            return True

        result = await test_func(42)

        assert result is True, "Return value should be preserved"
        assert recorded["called"] is True, "Function should be called"
        assert recorded["arg_received"] == 42, "Arguments should be passed through"

    @pytest.mark.asyncio
    async def test_track_operation_preserves_return_types(self) -> None:
        """Test that track_operation preserves various return types."""
        from kagami_observability.telemetry import track_operation

        @track_operation("test-dict-return")
        async def dict_func() -> dict[str, Any]:
            return {"key": "value", "number": 123}

        result = await dict_func()
        assert result == {"key": "value", "number": 123}
        assert isinstance(result, dict)


class TestMetricsCollection:
    """Exercise Prometheus metrics objects rather than existence checks."""

    def test_counter_increment(self) -> None:
        from kagami_observability.metrics.api import KAGAMI_HTTP_REQUESTS_TOTAL

        metric = KAGAMI_HTTP_REQUESTS_TOTAL.labels(
            method="GET", route="/api/test", status_code="200"
        )
        before = metric._value.get()

        metric.inc()
        after = metric._value.get()

        assert after == pytest.approx(before + 1)

    def test_histogram_observation(self) -> None:
        from kagami_observability.metrics.api import KAGAMI_HTTP_REQUEST_DURATION_SECONDS

        histogram = KAGAMI_HTTP_REQUEST_DURATION_SECONDS.labels(method="POST", route="/api/test")
        histogram.observe(0.042)
        # Prometheus histograms store sum/count
        assert histogram._sum.get() >= 0.042

    def test_gauge_set(self) -> None:
        from kagami_observability.metrics.system import SYSTEM_CPU_USAGE

        SYSTEM_CPU_USAGE.set(0.45)
        assert SYSTEM_CPU_USAGE._value.get() == pytest.approx(0.45)


class TestMetricsExport:
    """Ensure Prometheus exporter returns data."""

    def test_prometheus_format(self) -> None:
        from prometheus_client import generate_latest

        metrics_output = generate_latest()

        assert isinstance(metrics_output, bytes), "Output should be bytes"
        assert b"# HELP" in metrics_output, "Should contain HELP comments"
        assert b"# TYPE" in metrics_output, "Should contain TYPE declarations"

    def test_prometheus_format_contains_kagami_metrics(self) -> None:
        """Test that export contains kagami-specific metrics after they're used."""
        from kagami_observability.metrics.api import KAGAMI_HTTP_REQUESTS_TOTAL
        from prometheus_client import generate_latest

        # Ensure metric has been used
        KAGAMI_HTTP_REQUESTS_TOTAL.labels(
            method="GET", route="/api/export_test", status_code="200"
        ).inc()

        metrics_output = generate_latest()
        output_str = metrics_output.decode("utf-8")

        # Should contain the kagami HTTP metric
        assert "kagami_http_requests_total" in output_str

    def test_prometheus_format_is_valid_text(self) -> None:
        """Test that Prometheus output is valid UTF-8 text format."""
        from prometheus_client import generate_latest

        metrics_output = generate_latest()

        # Should be decodable as UTF-8
        decoded = metrics_output.decode("utf-8")
        assert isinstance(decoded, str)

        # Should have multiple lines
        lines = decoded.strip().split("\n")
        assert len(lines) > 0, "Should have at least one line"

        # Each HELP line should be followed by TYPE line
        for i, line in enumerate(lines):
            if line.startswith("# HELP"):
                # Next line should typically be TYPE (or another HELP for different metric)
                assert i < len(lines) - 1, "HELP should not be last line"


class TestMetricsLabels:
    """Test that metric labels work correctly."""

    def test_counter_different_labels_are_independent(self) -> None:
        """Test that different label combinations create independent counters."""
        from kagami_observability.metrics.api import KAGAMI_HTTP_REQUESTS_TOTAL

        counter_get = KAGAMI_HTTP_REQUESTS_TOTAL.labels(
            method="GET", route="/api/label_test", status_code="200"
        )
        counter_post = KAGAMI_HTTP_REQUESTS_TOTAL.labels(
            method="POST", route="/api/label_test", status_code="200"
        )

        before_get = counter_get._value.get()
        before_post = counter_post._value.get()

        counter_get.inc()

        after_get = counter_get._value.get()
        after_post = counter_post._value.get()

        assert after_get == pytest.approx(before_get + 1), "GET counter should increment"
        assert after_post == pytest.approx(before_post), "POST counter should not change"
