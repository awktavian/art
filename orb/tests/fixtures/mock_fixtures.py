"""Mock fixtures for K os tests.

Provides mock implementations ONLY for truly external dependencies (Composio, external APIs).

IMPORTANT: Use these mocks SPARINGLY. Most tests should use real implementations.
Only mock when:
1. External API (Composio, OpenAI, etc.)
2. Heavy model loading (>1GB)
3. Network calls to external services

DO NOT mock internal K os components - use real implementations for better coverage.
"""

from unittest.mock import MagicMock

import pytest
import pytest_asyncio


@pytest.fixture
def mock_composio(monkeypatch: pytest.MonkeyPatch) -> "MockComposioClient":
    """Mock Composio for tests."""

    class MockComposioClient:
        """Mock Composio client."""

        def __init__(self, *args: Any, **kwargs) -> None:
            self.api_key = kwargs.get("api_key", "test_key")

        @property
        def tools(self) -> "MockComposioClient":
            """Mock tools."""
            return self

        @property
        def toolkits(self) -> "MockComposioClient":
            """Mock toolkits."""
            return self

        @property
        def connected_accounts(self) -> "MockComposioClient":
            """Mock connected accounts."""
            return self

        async def execute(self, *args: Any, **kwargs) -> dict[str, Any]:
            """Mock execute."""
            return {
                "status": "success",
                "result": "mocked composio action result",
                "data": {"key": "value"},
            }

        def list(self, *args: Any, **kwargs) -> list:  # noqa: A003
            """Mock list."""
            return []

    mock_client = MockComposioClient()

    # Patch Composio
    try:
        monkeypatch.setattr("composio.Composio", lambda *args, **kwargs: mock_client)
    except Exception:
        pass

    return mock_client


@pytest_asyncio.fixture
async def production_systems(monkeypatch: pytest.MonkeyPatch) -> "MockProductionSystems":
    """Mock production systems coordinator for tests."""

    class MockProductionSystems:
        """Mock production systems."""

        def __init__(self) -> None:
            self.initialized = False
            self.ethical_instinct = MagicMock()
            self.prediction_instinct = MagicMock()
            self.learning_instinct = MagicMock()
            self.threat_instinct = MagicMock()
            self.replay_buffer = MagicMock()
            self.introspection_engine = MagicMock()
            self.world_model = MagicMock()

        async def initialize(self) -> None:
            """Mock initialize."""
            self.initialized = True

        async def shutdown(self) -> None:
            """Mock shutdown."""
            self.initialized = False

        def wire_to_orchestrator(self, orchestrator: Any) -> None:
            """Mock wiring."""

    systems = MockProductionSystems()
    await systems.initialize()

    yield systems

    await systems.shutdown()


__all__ = [
    "mock_composio",  # Keep - external API
    "production_systems",
]
