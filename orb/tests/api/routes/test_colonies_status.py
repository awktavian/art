"""Tests for /api/colonies/status endpoint.

Tests the system-wide colony status endpoint that provides aggregate
metrics across all 7 colonies (Spark, Forge, Flow, Nexus, Beacon, Grove, Crystal).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from datetime import datetime
from unittest.mock import MagicMock, Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kagami_api.schemas.colonies import ColoniesStatusResponse, ColonyStatus


@pytest.fixture
def mock_organism() -> Mock:
    """Create mock unified organism with 7 colonies."""
    organism = Mock()

    # Create mock colonies with different states
    colonies = {}

    # Spark - 2 active agents
    spark = Mock()
    spark.workers = [_create_mock_worker("spark-001", 10), _create_mock_worker("spark-002", 5)]
    spark.stats = Mock(success_rate=0.95)
    spark.catastrophe_type = "A2"
    colonies["spark"] = spark

    # Forge - 1 active agent
    forge = Mock()
    forge.workers = [_create_mock_worker("forge-001", 25)]
    forge.stats = Mock(success_rate=0.98)
    forge.catastrophe_type = "A3"
    colonies["forge"] = forge

    # Flow - 1 active agent
    flow = Mock()
    flow.workers = [_create_mock_worker("flow-001", 8)]
    flow.stats = Mock(success_rate=0.92)
    flow.catastrophe_type = "A4"
    colonies["flow"] = flow

    # Nexus - idle (no workers)
    nexus = Mock()
    nexus.workers = []
    nexus.stats = Mock(success_rate=1.0)
    nexus.catastrophe_type = "A5"
    colonies["nexus"] = nexus

    # Beacon - 1 active agent
    beacon = Mock()
    beacon.workers = [_create_mock_worker("beacon-001", 15)]
    beacon.stats = Mock(success_rate=0.97)
    beacon.catastrophe_type = "D4+"
    colonies["beacon"] = beacon

    # Grove - idle (no workers)
    grove = Mock()
    grove.workers = []
    grove.stats = Mock(success_rate=1.0)
    grove.catastrophe_type = "D4-"
    colonies["grove"] = grove

    # Crystal - 1 active agent
    crystal = Mock()
    crystal.workers = [_create_mock_worker("crystal-001", 12)]
    crystal.stats = Mock(success_rate=0.96)
    crystal.catastrophe_type = "D5"
    colonies["crystal"] = crystal

    organism.colonies = colonies
    return organism


def _create_mock_worker(worker_id: str, completed_tasks: int) -> Mock:
    """Create a mock worker with state."""
    worker = Mock()
    worker.worker_id = worker_id
    worker.state = Mock(
        status=Mock(value="active"),
        completed_tasks=completed_tasks,
        created_at=0.0,
        last_active=0.0,
    )
    worker.fitness = 0.95
    return worker


@pytest.fixture
def test_app(monkeypatch: pytest.MonkeyPatch, mock_organism: Mock) -> FastAPI:
    """Create test FastAPI app with colonies router."""
    from kagami_api.routes.colonies import get_router

    # Mock auth to bypass authentication
    def mock_require_auth() -> Mock:
        return Mock(sub="test-user", roles=["user"], scopes=[], tenant_id=None, user_id="test-123")

    monkeypatch.setattr("kagami_api.routes.colonies.require_auth", mock_require_auth)

    # Mock unified organism
    def mock_get_organism() -> Mock:
        return mock_organism

    monkeypatch.setattr("kagami.core.unified_agents.get_unified_organism", mock_get_organism)

    app = FastAPI()
    app.include_router(get_router())
    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(test_app)


# ============================================================================
# Basic Endpoint Tests
# ============================================================================


def test_colonies_status_endpoint_exists(client: TestClient) -> None:
    """Test that /api/colonies/status endpoint exists."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200


def test_colonies_status_returns_valid_schema(client: TestClient) -> None:
    """Test that response conforms to ColoniesStatusResponse schema."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()

    # Validate top-level fields
    assert "colonies" in data
    assert "total_agents" in data
    assert "timestamp" in data
    assert "status" in data
    assert "avg_success_rate" in data

    # Parse as schema
    parsed = ColoniesStatusResponse(**data)
    assert parsed.total_agents >= 0
    assert parsed.status in ["operational", "degraded", "error"]
    assert 0.0 <= parsed.avg_success_rate <= 1.0


def test_colonies_status_includes_all_colonies(client: TestClient) -> None:
    """Test that response includes all 7 colonies."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()
    colonies = data["colonies"]

    expected_colonies = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
    for colony_name in expected_colonies:
        assert colony_name in colonies


def test_colonies_status_colony_fields(client: TestClient) -> None:
    """Test that each colony has correct fields."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()

    for colony_name, colony_data in data["colonies"].items():
        # Validate colony schema
        colony = ColonyStatus(**colony_data)
        assert colony.name == colony_name
        assert colony.active_agents >= 0
        assert colony.status in ["active", "idle", "error"]
        assert 0.0 <= colony.success_rate <= 1.0
        assert colony.tasks_completed >= 0
        assert colony.catastrophe_type  # Should not be empty


# ============================================================================
# Metric Calculation Tests
# ============================================================================


def test_colonies_status_total_agents(client: TestClient) -> None:
    """Test that total_agents sums correctly."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()

    # From mock: spark=2, forge=1, flow=1, nexus=0, beacon=1, grove=0, crystal=1
    expected_total = 6
    assert data["total_agents"] == expected_total

    # Verify sum matches
    actual_sum = sum(colony["active_agents"] for colony in data["colonies"].values())
    assert data["total_agents"] == actual_sum


def test_colonies_status_avg_success_rate(client: TestClient) -> None:
    """Test that avg_success_rate is calculated correctly."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()

    # From mock: spark=0.95, forge=0.98, flow=0.92, nexus=1.0, beacon=0.97, grove=1.0, crystal=0.96
    expected_avg = (0.95 + 0.98 + 0.92 + 1.0 + 0.97 + 1.0 + 0.96) / 7
    assert abs(data["avg_success_rate"] - expected_avg) < 0.01


def test_colonies_status_system_status_operational(client: TestClient) -> None:
    """Test that system status is 'operational' when avg_success >= 0.8."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()

    # Mock has avg_success ~0.97, should be operational
    assert data["status"] == "operational"


def test_colonies_status_system_status_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that system status is 'degraded' when 0.5 <= avg_success < 0.8."""
    from kagami_api.routes.colonies import get_router

    # Create organism with lower success rates
    organism = Mock()
    colonies = {}

    for name in ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]:
        colony = Mock()
        colony.workers = [_create_mock_worker(f"{name}-001", 5)]
        colony.stats = Mock(success_rate=0.6)  # Degraded
        colony.catastrophe_type = "A2"
        colonies[name] = colony

    organism.colonies = colonies

    def mock_get_organism() -> Mock:
        return organism

    def mock_require_auth() -> Mock:
        return Mock(sub="test-user", roles=["user"], scopes=[], tenant_id=None, user_id="test-123")

    monkeypatch.setattr("kagami.core.unified_agents.get_unified_organism", mock_get_organism)
    monkeypatch.setattr("kagami_api.routes.colonies.require_auth", mock_require_auth)

    app = FastAPI()
    app.include_router(get_router())
    client = TestClient(app)

    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "degraded"


def test_colonies_status_timestamp_format(client: TestClient) -> None:
    """Test that timestamp is valid ISO format."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()

    # Should be parseable as ISO datetime
    timestamp_str = data["timestamp"]
    parsed_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    assert isinstance(parsed_time, datetime)


# ============================================================================
# Colony Status Tests
# ============================================================================


def test_colony_status_active_when_workers_present(client: TestClient) -> None:
    """Test that colony status is 'active' when workers exist."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()

    # Spark has 2 workers, should be active
    assert data["colonies"]["spark"]["status"] == "active"
    assert data["colonies"]["spark"]["active_agents"] == 2


def test_colony_status_idle_when_no_workers(client: TestClient) -> None:
    """Test that colony status is 'idle' when no workers."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()

    # Nexus has 0 workers, should be idle
    assert data["colonies"]["nexus"]["status"] == "idle"
    assert data["colonies"]["nexus"]["active_agents"] == 0


def test_colony_tasks_completed_sum(client: TestClient) -> None:
    """Test that tasks_completed aggregates across workers."""
    response = client.get("/api/colonies/status")
    assert response.status_code == 200

    data = response.json()

    # Spark has 2 workers with 10 and 5 tasks
    assert data["colonies"]["spark"]["tasks_completed"] == 15


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_colonies_status_error_handling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that endpoint returns error status on exception."""
    from kagami_api.routes.colonies import get_router

    def mock_get_organism() -> None:
        raise RuntimeError("Test error")

    def mock_require_auth() -> Mock:
        return Mock(sub="test-user", roles=["user"], scopes=[], tenant_id=None, user_id="test-123")

    monkeypatch.setattr("kagami.core.unified_agents.get_unified_organism", mock_get_organism)
    monkeypatch.setattr("kagami_api.routes.colonies.require_auth", mock_require_auth)

    app = FastAPI()
    app.include_router(get_router())
    client = TestClient(app)

    response = client.get("/api/colonies/status")
    assert response.status_code == 200  # Should not raise

    data = response.json()
    assert data["status"] == "error"
    assert data["total_agents"] == 0
    assert data["colonies"] == {}


# ============================================================================
# Authentication Tests
# ============================================================================


def test_colonies_status_requires_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that endpoint requires authentication."""
    from fastapi import HTTPException

    from kagami_api.routes.colonies import get_router

    def mock_require_auth() -> None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    monkeypatch.setattr("kagami_api.routes.colonies.require_auth", mock_require_auth)

    app = FastAPI()
    app.include_router(get_router())
    client = TestClient(app)

    response = client.get("/api/colonies/status")
    assert response.status_code == 401
