"""Test CBF timeout protection.

CREATED: December 14, 2025
PURPOSE: Verify watchdog timers prevent CBF checks from blocking forever

CRITICAL SAFETY PROPERTY:
- If safety classifier hangs, the system must not freeze
- Timeout triggers fail-closed behavior (safe=False, h(x)=-1.0)
- Metrics recorded for monitoring
"""

from __future__ import annotations
from typing import Any

import asyncio
import time
from unittest.mock import MagicMock, Mock, patch

import pytest
import torch

from kagami.core.safety.cbf_integration import (
    CBF_TIMEOUT_SECONDS,
    check_cbf_for_operation,
    check_cbf_sync,
)
from kagami.core.safety.types import SafetyCheckResult


@pytest.fixture
def mock_slow_safety_filter():
    """Mock safety filter that hangs indefinitely."""
    mock_filter = MagicMock()

    # Simulate hanging by sleeping longer than timeout
    def slow_filter_text(*args: Any, **kwargs) -> Any:
        time.sleep(CBF_TIMEOUT_SECONDS + 10.0)  # Sleep way longer to ensure timeout
        # This code should never be reached due to timeout
        return (
            torch.tensor([[0.5, 0.5]]),
            torch.tensor(0.0),
            {
                "classification": Mock(
                    is_safe=True,
                    risk_scores={},
                    max_risk=lambda: ("VIOLENCE", 0.0),
                    total_risk=lambda: 0.0,
                    confidence=1.0,
                ),
                "h_metric": torch.tensor(0.8),
            },
        )

    mock_filter.filter_text = Mock(side_effect=slow_filter_text)
    return mock_filter


@pytest.mark.asyncio
async def test_async_cbf_timeout(mock_slow_safety_filter: Any) -> None:
    """Test that async CBF check times out and fails closed."""
    with patch(
        "kagami.core.safety.cbf_integration._get_safety_filter",
        return_value=mock_slow_safety_filter,
    ):
        start = time.time()
        result = await check_cbf_for_operation(
            operation="test.timeout",
            action="test",
            user_input="test input",
        )
        elapsed = time.time() - start

        # Should timeout quickly (within timeout + reasonable overhead)
        # Note: ThreadPoolExecutor adds some overhead, so we allow 2s extra
        assert (
            elapsed < CBF_TIMEOUT_SECONDS + 2.0
        ), f"Timeout took {elapsed}s, expected ~{CBF_TIMEOUT_SECONDS}s"

        # Should fail closed
        assert result.safe is False, "Should fail closed on timeout"
        assert result.h_x == -1.0, "h(x) should be -1.0 on timeout"
        assert result.reason == "timeout", f"Expected reason='timeout', got '{result.reason}'"
        assert "timed out" in result.detail.lower(), (  # type: ignore[union-attr]
            f"Detail should mention timeout: {result.detail}"
        )

        # Metadata should include timeout value
        assert result.metadata is not None
        assert result.metadata.get("timeout_seconds") == CBF_TIMEOUT_SECONDS


def test_sync_cbf_timeout(mock_slow_safety_filter: Any) -> None:
    """Test that sync CBF check times out and fails closed."""
    with patch(
        "kagami.core.safety.cbf_integration._get_safety_filter",
        return_value=mock_slow_safety_filter,
    ):
        start = time.time()
        result = check_cbf_sync(
            operation="test.timeout.sync",
            action="test",
            user_input="test input",
        )
        elapsed = time.time() - start

        # Should timeout quickly (within timeout + reasonable overhead)
        assert (
            elapsed < CBF_TIMEOUT_SECONDS + 2.0
        ), f"Timeout took {elapsed}s, expected ~{CBF_TIMEOUT_SECONDS}s"

        # Should fail closed
        assert result.safe is False, "Should fail closed on timeout"
        assert result.h_x == -1.0, "h(x) should be -1.0 on timeout"
        assert result.reason == "timeout", f"Expected reason='timeout', got '{result.reason}'"
        assert "timed out" in result.detail.lower(), (  # type: ignore[union-attr]
            f"Detail should mention timeout: {result.detail}"
        )

        # Metadata should include timeout value
        assert result.metadata is not None
        assert result.metadata.get("timeout_seconds") == CBF_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_async_cbf_fast_path_no_timeout():
    """Test that fast CBF checks complete without timeout."""
    # Mock fast safety filter
    mock_filter = MagicMock()
    mock_filter.filter_text.return_value = (
        torch.tensor([[0.5, 0.5]]),
        torch.tensor(0.0),
        {
            "classification": Mock(
                is_safe=True,
                risk_scores={},
                max_risk=lambda: ("VIOLENCE", 0.0),
                total_risk=lambda: 0.0,
                confidence=1.0,
            ),
            "h_metric": torch.tensor(0.8),
        },
    )

    with patch("kagami.core.safety.cbf_integration._get_safety_filter", return_value=mock_filter):
        start = time.time()
        result = await check_cbf_for_operation(
            operation="test.fast",
            action="test",
            user_input="test input",
        )
        elapsed = time.time() - start

        # Should complete quickly
        assert elapsed < 1.0, f"Fast path took {elapsed}s, should be < 1s"

        # Should succeed (not timeout)
        assert result.safe is True, "Fast path should succeed"
        assert result.h_x > 0, "h(x) should be positive"  # type: ignore[operator]
        assert result.reason != "timeout", "Should not timeout on fast path"


def test_sync_cbf_fast_path_no_timeout():
    """Test that fast sync CBF checks complete without timeout."""
    # Mock fast safety filter
    mock_filter = MagicMock()
    mock_filter.filter_text.return_value = (
        torch.tensor([[0.5, 0.5]]),
        torch.tensor(0.0),
        {
            "classification": Mock(
                is_safe=True,
                risk_scores={},
                max_risk=lambda: ("VIOLENCE", 0.0),
                total_risk=lambda: 0.0,
                confidence=1.0,
            ),
            "h_metric": torch.tensor(0.8),
        },
    )

    with patch("kagami.core.safety.cbf_integration._get_safety_filter", return_value=mock_filter):
        start = time.time()
        result = check_cbf_sync(
            operation="test.fast.sync",
            action="test",
            user_input="test input",
        )
        elapsed = time.time() - start

        # Should complete quickly
        assert elapsed < 1.0, f"Fast path took {elapsed}s, should be < 1s"

        # Should succeed (not timeout)
        assert result.safe is True, "Fast path should succeed"
        assert result.h_x > 0, "h(x) should be positive"  # type: ignore[operator]
        assert result.reason != "timeout", "Should not timeout on fast path"


@pytest.mark.asyncio
async def test_timeout_metrics_recorded(mock_slow_safety_filter: Any) -> None:
    """Test that timeout events are recorded in metrics."""
    with (
        patch(
            "kagami.core.safety.cbf_integration._get_safety_filter",
            return_value=mock_slow_safety_filter,
        ),
        patch("kagami_observability.metrics.CBF_BLOCKS_TOTAL") as mock_metric,
    ):
        result = await check_cbf_for_operation(
            operation="test.timeout.metrics",
            action="test",
            user_input="test input",
        )

        # Should have recorded timeout metric
        assert result.reason == "timeout"
        mock_metric.labels.assert_called_with(operation="test.timeout.metrics", reason="timeout")
        mock_metric.labels.return_value.inc.assert_called_once()


@pytest.mark.asyncio
async def test_multiple_concurrent_timeouts():
    """Test that multiple concurrent CBF checks can timeout independently."""
    mock_filter = MagicMock()

    def slow_filter(*args: Any, **kwargs) -> Any:
        time.sleep(CBF_TIMEOUT_SECONDS + 10.0)  # Sleep way longer to ensure timeout
        # Should never reach here
        return (
            torch.tensor([[0.5, 0.5]]),
            torch.tensor(0.0),
            {"classification": Mock(is_safe=True), "h_metric": torch.tensor(0.8)},
        )

    mock_filter.filter_text = Mock(side_effect=slow_filter)

    with patch("kagami.core.safety.cbf_integration._get_safety_filter", return_value=mock_filter):
        # Launch 3 concurrent checks
        tasks = [
            check_cbf_for_operation(
                operation=f"test.concurrent.{i}", action="test", user_input="test"
            )
            for i in range(3)
        ]

        start = time.time()
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start

        # All should timeout
        assert all(
            r.reason == "timeout" for r in results
        ), f"All checks should timeout: {[r.reason for r in results]}"
        assert all(r.safe is False for r in results), "All checks should fail closed"

        # Should complete in parallel (roughly timeout duration, not 3x timeout)
        # Allow some overhead for thread pool management
        assert (
            elapsed < CBF_TIMEOUT_SECONDS + 3.0
        ), f"Parallel timeouts took {elapsed}s, expected ~{CBF_TIMEOUT_SECONDS}s"


@pytest.mark.parametrize("timeout_value", [1.0, 3.0, 10.0])
def test_configurable_timeout(timeout_value: Any, monkeypatch: Any) -> None:
    """Test that timeout is configurable via environment variable."""
    # Set custom timeout
    monkeypatch.setenv("KAGAMI_CBF_TIMEOUT", str(timeout_value))

    # Reimport to pick up new env var
    import importlib
    from kagami.core.safety import cbf_integration

    importlib.reload(cbf_integration)

    # Verify timeout value is set
    assert cbf_integration.CBF_TIMEOUT_SECONDS == timeout_value


def test_timeout_fail_closed_principle():
    """Test that timeout always fails closed, never open."""
    # This is a property-based test principle:
    # AXIOM: timeout → safe=False ∧ h(x)=-1.0

    mock_filter = MagicMock()

    def always_timeout(*args: Any, **kwargs) -> Any:
        time.sleep(CBF_TIMEOUT_SECONDS + 10.0)
        # Should never reach here
        return (
            torch.tensor([[0.5, 0.5]]),
            torch.tensor(0.0),
            {"classification": Mock(is_safe=True), "h_metric": torch.tensor(0.8)},
        )

    mock_filter.filter_text = Mock(side_effect=always_timeout)

    with patch("kagami.core.safety.cbf_integration._get_safety_filter", return_value=mock_filter):
        # Try many times - should ALWAYS fail closed
        for _ in range(3):  # Reduced from 5 to 3 to save test time
            result = check_cbf_sync(operation="test.fail_closed", action="test", user_input="test")
            assert result.safe is False, "Timeout must ALWAYS fail closed"
            assert result.h_x == -1.0, "Timeout must ALWAYS set h(x)=-1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
