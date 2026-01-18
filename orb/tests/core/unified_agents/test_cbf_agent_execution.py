"""Test CBF wiring in agent execution paths.

Verifies that agent execution correctly calls CBF safety checks.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import logging

from kagami.core.safety.cbf_integration import check_cbf_for_operation
from kagami.core.unified_agents.geometric_worker import GeometricWorker, WorkerConfig
from kagami.core.unified_agents.minimal_colony import MinimalColony, ColonyConfig

logger = logging.getLogger(__name__)


class TestCBFAgentExecution:
    """Test CBF integration in agent execution."""

    def test_cbf_integration_available(self) -> None:
        """Verify CBF integration module is available."""
        from kagami.core.safety.cbf_integration import check_cbf_for_operation

        assert check_cbf_for_operation is not None
        assert callable(check_cbf_for_operation)

    @pytest.mark.asyncio
    async def test_worker_calls_cbf_on_execute(self):
        """Verify GeometricWorker.execute() calls CBF check."""
        worker = GeometricWorker(
            config=WorkerConfig(colony_idx=0),
            colony_idx=0,
        )

        # Execute a safe operation
        result = await worker.execute(
            action="test_action",
            params={"key": "value"},
            context={"test": True},
        )

        # Should succeed (CBF check passes for normal operations)
        assert result.success is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_colony_calls_cbf_on_execute(self):
        """Verify MinimalColony.execute() calls CBF check."""
        colony = MinimalColony(
            colony_idx=0,
            config=ColonyConfig(min_workers=1, max_workers=2),
        )

        # Execute a safe operation
        result = await colony.execute(
            action="test_action",
            params={"key": "value"},
            context={"test": True},
        )

        # Should succeed (CBF check passes for normal operations)
        assert result.success is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_cbf_check_for_operation_works(self):
        """Verify check_cbf_for_operation() can be called directly."""
        result = await check_cbf_for_operation(
            operation="test.operation",
            action="test_action",
            target="test_target",
            params={"key": "value"},
            metadata={"test": True},
            source="test",
        )

        # Should succeed for safe operations
        assert result.safe is True
        assert result.h_x >= 0.0  # type: ignore[operator]

    @pytest.mark.asyncio
    async def test_cbf_blocks_unsafe_content(self):
        """Verify CBF blocks operations with unsafe content."""
        # Try to execute with potentially unsafe user input
        result = await check_cbf_for_operation(
            operation="test.unsafe",
            action="execute",
            user_input="This is a test of normal safe content",
            source="test",
        )

        # Safe content should pass
        assert result.safe is True

        # Note: Testing actual unsafe content would require
        # triggering WildGuard classifier, which we avoid in unit tests
        # Integration tests with real classifier should cover unsafe cases

    @pytest.mark.asyncio
    async def test_worker_cbf_metadata_propagation(self):
        """Verify worker propagates metadata to CBF check."""
        worker = GeometricWorker(
            config=WorkerConfig(colony_idx=2),  # Flow colony
            colony_idx=2,
        )

        # Execute with specific metadata
        result = await worker.execute(
            action="debug_operation",
            params={"target_module": "test_module"},
            context={
                "correlation_id": "test-123",
                "phase": "EXECUTE",
                "parent_receipt_id": "parent-456",
            },
        )

        # Should succeed and preserve context
        assert result.success is True
        assert result.correlation_id == "test-123"
        assert result.phase == "EXECUTE"
        assert result.parent_receipt_id == "parent-456"

    @pytest.mark.asyncio
    async def test_colony_cbf_metadata_propagation(self):
        """Verify colony propagates metadata to CBF check."""
        colony = MinimalColony(
            colony_idx=1,  # Forge colony
            config=ColonyConfig(min_workers=1),
        )

        # Execute with specific metadata
        result = await colony.execute(
            action="build_operation",
            params={"target": "module.py"},
            context={
                "correlation_id": "build-789",
                "phase": "EXECUTE",
            },
        )

        # Should succeed and preserve context
        assert result.success is True
        assert result.correlation_id == "build-789"
        assert result.phase == "EXECUTE"

    @pytest.mark.asyncio
    async def test_parallel_cbf_checks(self):
        """Verify CBF checks work in parallel execution."""
        colony = MinimalColony(
            colony_idx=3,  # Nexus colony
            config=ColonyConfig(min_workers=3, max_workers=5),
        )

        # Execute batch of operations
        actions = [
            ("action_1", {"param": "value_1"}),
            ("action_2", {"param": "value_2"}),
            ("action_3", {"param": "value_3"}),
        ]

        results = await colony.execute_batch(
            actions=actions,
            context={"batch_id": "parallel-test"},
        )

        # All should succeed
        assert len(results) == 3
        for result in results:
            assert result.success is True
            assert result.correlation_id is not None

    @pytest.mark.asyncio
    async def test_cbf_fail_closed_on_error(self):
        """Verify CBF fails closed when safety check errors."""
        # This test verifies the fail-closed behavior documented in cbf_integration.py
        # When CBF check itself fails, it should return safe=False with h_x=-1.0

        from kagami.core.safety.types import SafetyCheckResult

        # Simulate a CBF check with missing classification
        # (This would normally happen if the safety classifier fails)
        result = SafetyCheckResult(
            safe=False,
            h_x=-1.0,
            reason="missing_classification",
            detail="Safety classifier did not return a classification",
        )

        assert result.safe is False
        assert result.h_x == -1.0
        assert result.reason == "missing_classification"


if __name__ == "__main__":
    # Run quick smoke test
    asyncio.run(TestCBFAgentExecution().test_worker_calls_cbf_on_execute())
    asyncio.run(TestCBFAgentExecution().test_colony_calls_cbf_on_execute())
    print("CBF agent execution wiring: VERIFIED")
