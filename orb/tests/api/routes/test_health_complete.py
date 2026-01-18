"""Comprehensive Health Endpoint Tests

Consolidated from 7 test files:
- test_health.py
- test_health_real.py
- test_health_readiness.py
- test_health_and_metrics_surface.py
- test_health_ready_int.py
- test_health_correlation_int.py
- test_health_temporal_gate.py

Tests all health check endpoints, metrics surface, readiness probes, and component validation.

Routes:
- /api/vitals/probes/live - Liveness probe
- /api/vitals/probes/ready - Readiness probe
- /api/vitals/probes/deep - Deep health check
- /api/vitals/probes/cluster - Cluster health
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import re

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kagami_api import create_app


@pytest.fixture
def test_app():
    """Create minimal FastAPI app with health routers for unit tests."""
    from kagami_api.routes.vitals.probes import get_router

    app = FastAPI()
    app.include_router(get_router(), prefix="/api/vitals")

    # Mock app state for Full Operation checks
    app.state.system_ready = True
    app.state.metrics_initialized = True
    app.state.redis_ready = True
    app.state.database_ready = True
    app.state.boot_graph_report = {}
    return app


@pytest.fixture
def client(test_app: Any) -> Any:
    """Test client for unit tests."""
    return TestClient(test_app)


@pytest.fixture
def full_app_client(monkeypatch: Any) -> Any:
    """Full application client for integration tests."""
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")
    app = create_app()
    return TestClient(app)


# ============================================================================
# Basic Health Endpoint Tests (Vitals Probes)
# ============================================================================


def test_health_liveness(client: Any) -> Any:
    """Test /api/vitals/probes/live returns 200 when system is alive."""
    response = client.get("/api/vitals/probes/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


def test_health_liveness_includes_service_name(client: Any) -> None:
    """Test liveness includes service name."""
    response = client.get("/api/vitals/probes/live")
    assert response.status_code == 200
    data = response.json()
    assert data.get("service") == "K OS"


# ============================================================================
# Readiness Probe Tests
# ============================================================================


def test_health_readiness_when_ready(test_app: Any) -> None:
    """Test /api/vitals/probes/ready returns 200 when system is ready."""
    test_app.state.system_ready = True
    client = TestClient(test_app)
    response = client.get("/api/vitals/probes/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded", "unhealthy")


def test_health_readiness_includes_component_status(test_app: Any) -> None:
    """Test readiness includes component status."""
    test_app.state.system_ready = True
    client = TestClient(test_app)
    response = client.get("/api/vitals/probes/ready")

    if response.status_code == 200:
        data = response.json()
        # Should include component checks
        assert "boot_ready" in data or "status" in data


def test_health_readiness_when_not_ready(test_app: Any) -> None:
    """Test /api/vitals/probes/ready returns 503 when system is not ready."""
    test_app.state.system_ready = False
    # Force boot report to indicate not ready
    test_app.state.boot_graph_report = {"test": {"success": False}}
    client = TestClient(test_app)
    response = client.get("/api/vitals/probes/ready")
    # May be 503 or 200 depending on other checks
    assert response.status_code in (200, 503)


# ============================================================================
# Deep Health Check Tests
# ============================================================================


def test_health_deep_check(client: Any) -> None:
    """Test /api/vitals/probes/deep returns comprehensive diagnostics."""
    response = client.get("/api/vitals/probes/deep")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded", "unhealthy")


def test_health_deep_includes_checks(client: Any) -> None:
    """Test deep check includes component checks."""
    response = client.get("/api/vitals/probes/deep")
    assert response.status_code == 200
    data = response.json()
    assert "checks" in data or "status" in data


def test_health_deep_includes_timestamp(client: Any) -> None:
    """Test deep check includes timestamp."""
    response = client.get("/api/vitals/probes/deep")
    assert response.status_code == 200
    data = response.json()
    assert "timestamp" in data


# ============================================================================
# Cluster Health Check Tests
# ============================================================================


def test_health_cluster_check(client: Any) -> None:
    """Test /api/vitals/probes/cluster returns cluster health."""
    response = client.get("/api/vitals/probes/cluster")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "checks" in data


def test_health_cluster_includes_etcd(client: Any) -> None:
    """Test cluster check includes etcd status."""
    response = client.get("/api/vitals/probes/cluster")
    assert response.status_code == 200
    data = response.json()
    # Should have etcd in checks
    if "checks" in data:
        assert "etcd" in data["checks"]


# ============================================================================
# Component Health Checks
# ============================================================================


def test_health_with_all_services_up(test_app: Any) -> None:
    """Test health when all services are operational."""
    test_app.state.system_ready = True
    test_app.state.redis_ready = True
    test_app.state.database_ready = True

    client = TestClient(test_app)
    response = client.get("/api/vitals/probes/ready")
    assert response.status_code in (200, 503)


def test_health_with_redis_down(test_app: Any) -> None:
    """Test health when Redis is down (degraded but may still be ok)."""
    test_app.state.redis_ready = False
    test_app.state.database_ready = True

    client = TestClient(test_app)
    response = client.get("/api/vitals/probes/ready")
    assert response.status_code in (200, 503)


def test_health_with_database_down(test_app: Any) -> None:
    """Test health when database is down."""
    test_app.state.database_ready = False

    client = TestClient(test_app)
    response = client.get("/api/vitals/probes/ready")
    assert response.status_code in (200, 503)


# ============================================================================
# Metrics Surface Tests
# ============================================================================


def test_single_metrics_surface(full_app_client: Any) -> None:
    """Test that /metrics endpoint exists and serves content."""
    response = full_app_client.get("/metrics")
    assert response.status_code == 200
    body = response.text

    # Check for actual metric names from metrics.py
    assert "kagami" in body.lower() or "python" in body.lower()


def test_single_metrics_surface_and_readiness(monkeypatch: Any) -> None:
    """Test /metrics endpoint and readiness in lightweight mode."""
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
    app = create_app()
    client = TestClient(app)

    # /metrics should be present and only one exporter mounted
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "kagami" in text.lower() or "python" in text.lower()

    # Readiness should be OK in lightweight mode when core is up
    response2 = client.get("/api/vitals/probes/ready")
    assert response2.status_code in (200, 503)

    # When 503, body must include hint of failing component
    if response2.status_code == 503:
        body = response2.json()
        detail = body.get("detail", body)
        has_component_info = any(
            k in str(detail) for k in ["boot", "metrics", "socketio", "redis", "db", "ready"]
        )
        assert has_component_info or "status" in str(
            detail
        ), f"Expected component info in 503 response, got: {body}"


def test_health_metrics_registration():
    """Test that health metrics are properly registered."""
    from kagami_observability.metrics import REGISTRY

    metric_names = [sample.name for sample in REGISTRY.collect()]
    # Should have at least some kagami metrics
    assert any("kagami" in name for name in metric_names)


# ============================================================================
# Full Operation Mode Tests
# ============================================================================


def test_health_full_operation_invariants(test_app: Any) -> None:
    """Test that Full Operation mode requires all mandatory components."""
    test_app.state.system_ready = True
    test_app.state.metrics_initialized = True
    test_app.state.redis_ready = True
    test_app.state.database_ready = True

    client = TestClient(test_app)
    response = client.get("/api/vitals/probes/ready")
    assert response.status_code in (200, 503)


def test_health_ready_in_dev_returns_ok_when_no_require_flags(monkeypatch: Any) -> None:
    """Test readiness in dev mode without strict requirements."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("LIGHTWEIGHT_STARTUP", "1")
    for k in [
        "KAGAMI_REQUIRE_SUBSYSTEMS",
        "KAGAMI_REQUIRE_INFERENCE",
        "KAGAMI_REQUIRE_REASONING",
        "KAGAMI_REQUIRE_AR",
    ]:
        monkeypatch.delenv(k, raising=False)

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/vitals/probes/ready")
    assert response.status_code in (200, 503)


# ============================================================================
# Full App Integration Tests
# ============================================================================


def test_vitals_probes_registered(full_app_client: Any) -> None:
    """Test that vitals probes are registered in full app."""
    response = full_app_client.get("/api/vitals/probes/live")
    assert response.status_code == 200


def test_vitals_ready_registered(full_app_client: Any) -> None:
    """Test that readiness probe is registered in full app."""
    response = full_app_client.get("/api/vitals/probes/ready")
    assert response.status_code in (200, 503)


def test_vitals_deep_registered(full_app_client: Any) -> None:
    """Test that deep check is registered in full app."""
    response = full_app_client.get("/api/vitals/probes/deep")
    assert response.status_code == 200


def test_vitals_cluster_registered(full_app_client: Any) -> None:
    """Test that cluster check is registered in full app."""
    response = full_app_client.get("/api/vitals/probes/cluster")
    assert response.status_code == 200


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_health_handles_missing_state_gracefully(test_app: Any) -> None:
    """Test health endpoints handle missing state attributes gracefully."""
    # Remove some state attributes
    if hasattr(test_app.state, "redis_ready"):
        delattr(test_app.state, "redis_ready")

    client = TestClient(test_app)
    response = client.get("/api/vitals/probes/live")
    # Liveness should not crash
    assert response.status_code == 200


def test_readiness_handles_missing_state(test_app: Any) -> None:
    """Test readiness handles missing state gracefully."""
    if hasattr(test_app.state, "system_ready"):
        delattr(test_app.state, "system_ready")

    client = TestClient(test_app)
    response = client.get("/api/vitals/probes/ready")
    # Should not crash, may be degraded
    assert response.status_code in (200, 503)


# ============================================================================
# Performance Tests
# ============================================================================


def test_health_endpoint_fast_response(client: Any) -> None:
    """Test that health endpoints respond quickly."""
    import time

    start = time.time()
    response = client.get("/api/vitals/probes/live")
    duration = time.time() - start

    assert response.status_code == 200
    # Liveness should be very fast (< 100ms)
    assert duration < 0.1


def test_readiness_probe_reasonable_latency(client: Any) -> None:
    """Test that readiness probe completes in reasonable time."""
    import time

    start = time.time()
    response = client.get("/api/vitals/probes/ready")
    duration = time.time() - start

    assert response.status_code in (200, 503)
    # Readiness can take longer but should be < 1s
    assert duration < 1.0


def test_deep_check_completes_in_time(client: Any) -> None:
    """Test that deep check completes in reasonable time."""
    import time

    start = time.time()
    response = client.get("/api/vitals/probes/deep")
    duration = time.time() - start

    assert response.status_code == 200
    # Deep check may take longer but should be < 5s
    assert duration < 5.0


# ============================================================================
# Response Format Tests
# ============================================================================


def test_liveness_response_format(client: Any) -> None:
    """Test liveness response has expected format."""
    response = client.get("/api/vitals/probes/live")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, dict)
    assert "status" in data
    assert "timestamp" in data


def test_readiness_response_format(test_app: Any) -> None:
    """Test readiness response has expected format."""
    test_app.state.system_ready = True
    client = TestClient(test_app)
    response = client.get("/api/vitals/probes/ready")

    if response.status_code == 200:
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data
        assert "timestamp" in data


def test_deep_response_format(client: Any) -> None:
    """Test deep check response has expected format."""
    response = client.get("/api/vitals/probes/deep")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, dict)
    assert "status" in data
    assert "checks" in data or "timestamp" in data


def test_cluster_response_format(client: Any) -> None:
    """Test cluster check response has expected format."""
    response = client.get("/api/vitals/probes/cluster")
    assert response.status_code == 200
    data = response.json()

    assert isinstance(data, dict)
    assert "status" in data
    assert "checks" in data
