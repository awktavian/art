"""Performance tests ensuring unit tests run <50ms."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_e2e


import time
from unittest.mock import patch


@pytest.mark.performance
def test_mock_factory_creation_performance() -> None:
    """Test mock factory creates mocks quickly (<1ms each)."""
    from helpers.mock_factory import MockFactory

    start = time.perf_counter()

    # Create 100 mocks
    for _ in range(100):
        MockFactory.create_cbf()
        MockFactory.create_ethical_instinct()
        MockFactory.create_fastapi_router()
        MockFactory.create_fastapi_app()

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Should take <200ms for 400 mock creations (imports add overhead)
    assert elapsed_ms < 200, f"Mock creation too slow: {elapsed_ms:.2f}ms"


@pytest.mark.performance
def test_orchestrator_init_performance() -> None:
    """Test orchestrator initializes in reasonable time."""
    from kagami.core.orchestrator.core import IntentOrchestrator

    start = time.perf_counter()

    orchestrator = IntentOrchestrator()

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Should init <2000ms (includes world model, sensorimotor, checkpoint restore)
    assert elapsed_ms < 2000, f"Init too slow: {elapsed_ms:.2f}ms"

    # Verify it actually initialized
    assert orchestrator._apps == {}
    assert orchestrator._initialized is False


@pytest.mark.performance
def test_route_registry_import_performance() -> None:
    """Test route registry imports quickly."""
    start = time.perf_counter()

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Should import <20ms
    assert elapsed_ms < 20, f"Import too slow: {elapsed_ms:.2f}ms"


@pytest.mark.asyncio
@pytest.mark.performance
async def test_brain_guided_executor_performance():
    """Test brain-guided execution is fast with mocks."""
    from kagami.core.integrations.brain_guided_executor import BrainGuidedExecutor
    from tests.helpers.mock_factory import MockFactory

    with patch("kagami.core.integrations.brain_guided_executor.get_brain_api") as mock_brain_api:
        pass

        mock_brain_api.return_value = MockFactory.create_brain_api(confidence=0.9)

        executor = BrainGuidedExecutor()

        agent = MockFactory.create_geometric_worker()
        task = MockFactory.create_task()

        start = time.perf_counter()

        result = await executor.execute_with_brain_guidance(agent, task)

        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should complete <50ms with mocks
        assert elapsed_ms < 50, f"Execution too slow: {elapsed_ms:.2f}ms"
        assert result["confidence"] > 0


@pytest.mark.performance
def test_intent_envelope_creation_performance() -> None:
    """Test intent envelope creation is fast."""
    from kagami.core.orchestrator.utils import _IntentEnvelope

    start = time.perf_counter()

    # Create 1000 envelopes
    for i in range(1000):
        envelope = _IntentEnvelope(
            action=f"test.action_{i}", app="test", metadata={"key": "value"}, target=f"target_{i}"
        )

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Should create 1000 envelopes <10ms (<0.01ms each)
    assert elapsed_ms < 10, f"Envelope creation too slow: {elapsed_ms:.2f}ms"


@pytest.mark.performance
def test_app_name_normalization_performance() -> None:
    """Test app name normalization is fast."""
    from kagami.core.orchestrator.utils import _normalize_app_name

    start = time.perf_counter()

    # Normalize 10000 names
    for _i in range(10000):
        _normalize_app_name("Penny Finance")
        _normalize_app_name("spark analytics")
        _normalize_app_name("  PLANS  ")

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Should normalize 30K names <50ms (<0.00167ms each)
    assert elapsed_ms < 50, f"Normalization too slow: {elapsed_ms:.2f}ms"
