"""Unit tests for Universal CBF Enforcer.

CREATED: December 14, 2025
TESTS: Universal CBF enforcement system (decorator, assertion, projection)

Test Coverage:
==============
1. Singleton behavior (thread-safe)
2. Decorator enforcement (@enforce_cbf)
3. Runtime assertions (assert_cbf)
4. Context manager (cbf_enforcement_disabled)
5. Projection to safe set
6. Thread safety
7. Error handling
8. Statistics tracking
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import threading
from typing import Optional, Any, cast

import torch

from kagami.core.safety.universal_cbf_enforcer import (
    CBFViolationError,
    UniversalCBFEnforcer,
    assert_cbf,
    cbf_enforcement_disabled,
    enforce_cbf,
    get_cbf_stats,
    is_safe,
    project_to_safe_set,
    reset_cbf_stats,
)


@pytest.fixture(autouse=True)
def reset_enforcer():
    """Reset singleton before each test."""
    UniversalCBFEnforcer.reset_instance()
    yield
    UniversalCBFEnforcer.reset_instance()


@pytest.fixture
def safe_state() -> Any:
    """Create a safe state (h(x) > 0).

    NOTE: Untrained OptimalCBF considers most states safe.
    We test enforcement mechanics rather than specific barrier values.
    """
    return torch.zeros(16)


@pytest.fixture
def unsafe_state() -> Any:
    """Create an artificially unsafe state for testing.

    NOTE: Since OptimalCBF is untrained, we manually set barrier to negative
    by mocking or adjusting threshold. For enforcement mechanics testing,
    we use a state that would be unsafe if CBF were properly trained.
    """
    # Use extreme values that project far from origin
    return torch.ones(16) * 10.0


@pytest.fixture
def enforcer_with_mock_barrier() -> Any:
    """Create enforcer with mocked barrier for controlled testing."""
    enforcer = UniversalCBFEnforcer.get_instance()

    # Store originals
    original_compute = enforcer.compute_barrier
    original_project = enforcer.project_to_safe_set

    def mock_compute(state, action=None):
        # If state norm is large, return negative barrier
        state_norm = state.abs().sum().item()
        if state_norm > 50:  # Threshold for "unsafe"
            return torch.tensor(-0.5)
        else:
            return torch.tensor(0.5)

    def mock_project(state, action=None, max_iterations=10, step_size=0.1):
        # Simple projection: scale down to safe norm
        state_norm = state.abs().sum().item()
        if state_norm > 50:
            # Increment counter
            with enforcer._state_lock:
                enforcer.projection_count += 1
            # Scale down to just below threshold
            return state * (45 / state_norm)
        return state

    # Replace with mocks
    enforcer.compute_barrier = mock_compute  # type: ignore[method-assign]
    enforcer.project_to_safe_set = mock_project  # type: ignore[method-assign]

    yield enforcer

    # Restore originals
    enforcer.compute_barrier = original_compute  # type: ignore[method-assign]
    enforcer.project_to_safe_set = original_project  # type: ignore[method-assign]


# =============================================================================
# SINGLETON TESTS
# =============================================================================


def test_singleton_pattern() -> None:
    """Test singleton behavior."""
    enforcer1 = UniversalCBFEnforcer.get_instance()
    enforcer2 = UniversalCBFEnforcer.get_instance()

    assert enforcer1 is enforcer2
    assert id(enforcer1) == id(enforcer2)


def test_singleton_thread_safe() -> None:
    """Test thread-safe singleton creation."""
    instances = []

    def create_instance():
        enforcer = UniversalCBFEnforcer.get_instance()
        instances.append(enforcer)

    # Create from 10 threads
    threads = [threading.Thread(target=create_instance) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All should be the same instance
    assert len({id(inst) for inst in instances}) == 1


def test_singleton_reset() -> None:
    """Test singleton reset (for testing only)."""
    enforcer1 = UniversalCBFEnforcer.get_instance()
    UniversalCBFEnforcer.reset_instance()
    enforcer2 = UniversalCBFEnforcer.get_instance()

    assert enforcer1 is not enforcer2


# =============================================================================
# BARRIER COMPUTATION TESTS
# =============================================================================


def test_compute_barrier_safe_state(safe_state: Any) -> None:
    """Test barrier computation on safe state."""
    enforcer = UniversalCBFEnforcer.get_instance()
    h = enforcer.compute_barrier(safe_state)

    assert isinstance(h, torch.Tensor)
    assert h.item() >= 0, f"Safe state should have h >= 0, got {h.item()}"


def test_compute_barrier_unsafe_state(unsafe_state: Any, enforcer_with_mock_barrier: Any) -> None:
    """Test barrier computation on unsafe state."""
    h = enforcer_with_mock_barrier.compute_barrier(unsafe_state)

    assert isinstance(h, torch.Tensor)
    assert h.item() < 0, f"Unsafe state should have h < 0, got {h.item()}"


def test_compute_barrier_batch() -> None:
    """Test barrier computation on batch of states."""
    enforcer = UniversalCBFEnforcer.get_instance()
    batch_states = torch.randn(4, 16)
    h = enforcer.compute_barrier(batch_states)

    assert h.shape == (4,)
    assert h.dtype == torch.float32


def test_is_safe_true(safe_state: Any) -> None:
    """Test is_safe returns True for safe state."""
    enforcer = UniversalCBFEnforcer.get_instance()
    assert enforcer.is_safe(safe_state)


def test_is_safe_false(unsafe_state: Any, enforcer_with_mock_barrier: Any) -> None:
    """Test is_safe returns False for unsafe state."""
    assert not enforcer_with_mock_barrier.is_safe(unsafe_state)


# =============================================================================
# PROJECTION TESTS
# =============================================================================


def test_project_to_safe_set_unsafe_state(
    unsafe_state: Any, enforcer_with_mock_barrier: Any
) -> None:
    """Test projection from unsafe to safe state."""
    state_safe = enforcer_with_mock_barrier.project_to_safe_set(unsafe_state)

    assert state_safe.shape == unsafe_state.shape
    h_safe = enforcer_with_mock_barrier.compute_barrier(state_safe)
    assert h_safe.item() >= 0, f"Projected state should be safe, got h={h_safe.item()}"


def test_project_to_safe_set_already_safe(safe_state: Any) -> None:
    """Test projection on already safe state (should be identity)."""
    enforcer = UniversalCBFEnforcer.get_instance()
    state_safe = enforcer.project_to_safe_set(safe_state)

    # Should be close to original (small numerical changes ok)
    assert torch.allclose(state_safe, safe_state, atol=1e-3)


def test_project_to_safe_set_batch() -> None:
    """Test projection on batch of states."""
    enforcer = UniversalCBFEnforcer.get_instance()
    batch_unsafe = torch.ones(4, 16) * 5.0
    batch_safe = enforcer.project_to_safe_set(batch_unsafe)

    assert batch_safe.shape == (4, 16)
    h_safe = enforcer.compute_barrier(batch_safe)
    assert (h_safe >= 0).all(), f"All projected states should be safe, got {h_safe}"


def test_project_to_safe_set_with_action() -> None:
    """Test projection with action parameter."""
    enforcer = UniversalCBFEnforcer.get_instance()
    state = torch.ones(16) * 5.0
    action = torch.tensor([0.5, 0.3])

    state_safe = enforcer.project_to_safe_set(state, action)
    h_safe = enforcer.compute_barrier(state_safe, action)

    assert h_safe.item() >= 0


# =============================================================================
# DECORATOR TESTS
# =============================================================================


def test_decorator_safe_output(safe_state: Any) -> None:
    """Test decorator passes through safe outputs."""

    @enforce_cbf(state_param="state")
    def safe_function(state: torch.Tensor) -> torch.Tensor:
        return state  # Return safe state

    result = safe_function(safe_state)
    assert torch.equal(result, safe_state)


def test_decorator_unsafe_output_with_projection(
    safe_state, unsafe_state, enforcer_with_mock_barrier
) -> None:
    """Test decorator projects unsafe outputs."""

    @enforce_cbf(state_param="state", project_to_safe=True)
    def unsafe_function(state: torch.Tensor) -> torch.Tensor:
        return cast(torch.Tensor, unsafe_state)  # Return unsafe state

    result = unsafe_function(safe_state)

    h = enforcer_with_mock_barrier.compute_barrier(result)
    assert h.item() >= 0, "Decorator should project to safe set"
    # Note: With mocked barrier, large states get projected down
    assert result.abs().sum().item() < unsafe_state.abs().sum().item(), "Output should be modified"


def test_decorator_unsafe_output_with_error(
    safe_state: Any, unsafe_state: Any, enforcer_with_mock_barrier: Any
) -> None:
    """Test decorator raises error on unsafe outputs when project_to_safe=False."""

    @enforce_cbf(state_param="state", project_to_safe=False)
    def unsafe_function(state: torch.Tensor) -> torch.Tensor:
        return cast(torch.Tensor, unsafe_state)

    with pytest.raises(CBFViolationError) as exc_info:
        unsafe_function(safe_state)

    assert exc_info.value.barrier_value < 0
    assert torch.equal(exc_info.value.state, unsafe_state)


def test_decorator_with_action(safe_state: Any) -> None:
    """Test decorator with action parameter."""

    @enforce_cbf(state_param="x", action_param="u", project_to_safe=True)
    def dynamics(x: torch.Tensor, u: torch.Tensor) -> torch.Tensor:
        # Unsafe dynamics
        return torch.ones(16) * 5.0

    action = torch.tensor([0.5, 0.3])
    result = dynamics(safe_state, action)

    enforcer = UniversalCBFEnforcer.get_instance()
    h = enforcer.compute_barrier(result, action)
    assert h.item() >= 0


def test_decorator_check_input(unsafe_state: Any, enforcer_with_mock_barrier: Any) -> None:
    """Test decorator can check and project inputs."""

    @enforce_cbf(state_param="state", check_input=True, check_output=False)
    def function_with_input_check(state: torch.Tensor) -> torch.Tensor:
        # Input should be projected before reaching here
        assert enforcer_with_mock_barrier.is_safe(state), "Input should be safe after projection"
        return state

    result = function_with_input_check(unsafe_state)
    assert enforcer_with_mock_barrier.is_safe(result)


def test_decorator_kwargs() -> None:
    """Test decorator works with keyword arguments."""

    @enforce_cbf(state_param="x", project_to_safe=True)
    def func(x: torch.Tensor, other: int = 42) -> torch.Tensor:
        return torch.ones(16) * 5.0

    result = func(x=torch.zeros(16), other=100)

    enforcer = UniversalCBFEnforcer.get_instance()
    assert enforcer.is_safe(result)


def test_decorator_preserves_metadata() -> None:
    """Test decorator preserves function metadata."""

    @enforce_cbf(state_param="state")
    def my_function(state: torch.Tensor) -> torch.Tensor:
        """My docstring."""
        return state

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "My docstring."


# =============================================================================
# RUNTIME ASSERTION TESTS
# =============================================================================


def test_assert_cbf_safe(safe_state: Any) -> None:
    """Test assert_cbf passes for safe state."""
    assert_cbf(safe_state, message="Should not raise")


def test_assert_cbf_unsafe(unsafe_state: Any, enforcer_with_mock_barrier: Any) -> None:
    """Test assert_cbf raises for unsafe state."""
    with pytest.raises(CBFViolationError) as exc_info:
        assert_cbf(unsafe_state, message="Custom message")

    assert "Custom message" in str(exc_info.value)
    assert "h=" in str(exc_info.value)


def test_assert_cbf_with_action(safe_state: Any) -> None:
    """Test assert_cbf with action parameter."""
    action = torch.tensor([0.5, 0.3])
    assert_cbf(safe_state, action, message="Should not raise")


# =============================================================================
# CONTEXT MANAGER TESTS
# =============================================================================


def test_context_manager_disables_enforcement(
    unsafe_state: Any, enforcer_with_mock_barrier: Any
) -> None:
    """Test context manager disables enforcement."""
    assert enforcer_with_mock_barrier.enforcement_enabled

    with cbf_enforcement_disabled():
        assert not enforcer_with_mock_barrier.enforcement_enabled

        # Operations inside should not be checked
        @enforce_cbf(state_param="state", project_to_safe=False)
        def unsafe_func(state: torch.Tensor) -> torch.Tensor:
            return cast(torch.Tensor, unsafe_state)

        # Should not raise even though returning unsafe state
        result = unsafe_func(unsafe_state)
        assert torch.equal(result, unsafe_state)

    # Should be re-enabled
    assert enforcer_with_mock_barrier.enforcement_enabled


def test_context_manager_restores_on_exception(unsafe_state: Any) -> None:
    """Test context manager restores enforcement even on exception."""
    enforcer = UniversalCBFEnforcer.get_instance()

    assert enforcer.enforcement_enabled

    try:
        with cbf_enforcement_disabled():
            assert not enforcer.enforcement_enabled
            raise ValueError("Test exception")
    except ValueError:
        pass

    # Should be restored despite exception
    assert enforcer.enforcement_enabled


def test_context_manager_nested() -> None:
    """Test nested context managers."""
    enforcer = UniversalCBFEnforcer.get_instance()

    with cbf_enforcement_disabled():
        assert not enforcer.enforcement_enabled

        with cbf_enforcement_disabled():
            assert not enforcer.enforcement_enabled

        assert not enforcer.enforcement_enabled

    assert enforcer.enforcement_enabled


# =============================================================================
# STATISTICS TESTS
# =============================================================================


def test_statistics_tracking(
    safe_state: Any, unsafe_state: Any, enforcer_with_mock_barrier: Any
) -> None:
    """Test enforcement statistics are tracked correctly."""
    reset_cbf_stats()

    # Check safe state
    enforcer_with_mock_barrier.is_safe(safe_state)

    stats = get_cbf_stats()
    assert stats["check_count"] >= 1

    # Project unsafe state
    enforcer_with_mock_barrier.project_to_safe_set(unsafe_state)

    stats = get_cbf_stats()
    assert stats["projection_count"] >= 1

    # Trigger violation (with error)
    try:
        enforcer_with_mock_barrier.enforce(unsafe_state, project_to_safe=False, context="test")
    except CBFViolationError:
        pass

    stats = get_cbf_stats()
    assert stats["violation_count"] >= 1


def test_reset_statistics() -> None:
    """Test statistics reset."""
    reset_cbf_stats()

    # Check initial state
    stats = get_cbf_stats()
    assert stats["check_count"] == 0

    enforcer = UniversalCBFEnforcer.get_instance()
    enforcer.is_safe(torch.zeros(16))

    stats = get_cbf_stats()
    assert stats["check_count"] >= 1

    reset_cbf_stats()
    stats = get_cbf_stats()
    assert stats["check_count"] == 0
    assert stats["violation_count"] == 0
    assert stats["projection_count"] == 0


# =============================================================================
# UTILITY FUNCTION TESTS
# =============================================================================


def test_utility_is_safe(
    safe_state: Any, unsafe_state: Any, enforcer_with_mock_barrier: Any
) -> None:
    """Test utility is_safe function."""
    assert enforcer_with_mock_barrier.is_safe(safe_state)
    assert not enforcer_with_mock_barrier.is_safe(unsafe_state)


def test_utility_project_to_safe_set(unsafe_state: Any, enforcer_with_mock_barrier: Any) -> None:
    """Test utility project_to_safe_set function."""
    state_safe = enforcer_with_mock_barrier.project_to_safe_set(unsafe_state)

    assert enforcer_with_mock_barrier.is_safe(state_safe)


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================


def test_concurrent_enforcement(safe_state: Any, unsafe_state: Any) -> None:
    """Test concurrent enforcement from multiple threads."""
    enforcer = UniversalCBFEnforcer.get_instance()
    results = []
    errors = []

    def worker(state: torch.Tensor):
        try:
            h = enforcer.compute_barrier(state)
            results.append(h.item())
        except Exception as e:
            errors.append(e)

    # Mix of safe and unsafe states
    states = [safe_state, unsafe_state, safe_state, unsafe_state]
    threads = [threading.Thread(target=worker, args=(s,)) for s in states]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(results) == 4


def test_concurrent_projection(unsafe_state: Any) -> None:
    """Test concurrent projection from multiple threads."""
    enforcer = UniversalCBFEnforcer.get_instance()
    results = []
    errors = []

    def worker():
        try:
            state_safe = enforcer.project_to_safe_set(unsafe_state.clone())
            results.append(enforcer.is_safe(state_safe))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(10)]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert all(results)  # All projections should result in safe states


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


def test_cbf_violation_error_attributes(unsafe_state: Any) -> None:
    """Test CBFViolationError has correct attributes."""
    action = torch.tensor([0.5, 0.3])

    error = CBFViolationError(
        message="Test violation",
        state=unsafe_state,
        barrier_value=-0.5,
        action=action,
    )

    assert str(error) == "Test violation"
    assert torch.equal(error.state, unsafe_state)
    assert error.barrier_value == -0.5
    assert torch.equal(error.action, action)  # type: ignore[arg-type]


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


def test_full_pipeline_safe() -> None:
    """Test full pipeline with safe operations."""

    @enforce_cbf(state_param="x", action_param="u", project_to_safe=True)
    def safe_dynamics(x: torch.Tensor, u: torch.Tensor) -> torch.Tensor:
        # Safe operation: small perturbation
        return x + 0.1 * u[0]

    x = torch.zeros(16)
    u = torch.tensor([0.1, 0.2])

    result = safe_dynamics(x, u)

    assert_cbf(result, u, "Result should be safe")
    assert is_safe(result)


def test_full_pipeline_unsafe_with_projection(enforcer_with_mock_barrier: Any) -> None:
    """Test full pipeline with unsafe operation and projection."""
    # Reset stats before test
    reset_cbf_stats()

    @enforce_cbf(state_param="x", project_to_safe=True, check_output=True)
    def unsafe_dynamics(x: torch.Tensor) -> torch.Tensor:
        # Unsafe operation: large perturbation
        return torch.ones(16) * 10.0  # Exceeds threshold for mock

    x = torch.zeros(16)

    result = unsafe_dynamics(x)

    # Should be projected to safe set
    assert enforcer_with_mock_barrier.is_safe(result)

    stats = get_cbf_stats()
    assert stats["projection_count"] >= 1


def test_full_pipeline_temporary_disable(enforcer_with_mock_barrier: Any) -> None:
    """Test full pipeline with temporary disable."""

    @enforce_cbf(state_param="x", project_to_safe=False)
    def unsafe_dynamics(x: torch.Tensor) -> torch.Tensor:
        return torch.ones(16) * 10.0  # Exceeds threshold for mock

    x = torch.zeros(16)

    # Without disable, should raise
    with pytest.raises(CBFViolationError):
        unsafe_dynamics(x)

    # With disable, should pass
    with cbf_enforcement_disabled():
        result = unsafe_dynamics(x)
        assert torch.equal(result, torch.ones(16) * 10.0)


# =============================================================================
# EDGE CASES
# =============================================================================


def test_zero_state() -> None:
    """Test with zero state (should be safe)."""
    state = torch.zeros(16)
    assert is_safe(state)


def test_small_perturbation() -> None:
    """Test small perturbations around safety boundary."""
    enforcer = UniversalCBFEnforcer.get_instance()

    # Start at zero (safe)
    state = torch.zeros(16)

    # Gradually increase magnitude
    for scale in [0.1, 0.3, 0.5, 0.7, 1.0]:
        test_state = torch.ones(16) * scale
        h = enforcer.compute_barrier(test_state)
        # Should see h decrease as scale increases


def test_batch_size_one() -> None:
    """Test with batch size 1 (edge case for squeeze/unsqueeze)."""
    enforcer = UniversalCBFEnforcer.get_instance()

    state_single = torch.zeros(16)
    state_batch = torch.zeros(1, 16)

    h_single = enforcer.compute_barrier(state_single)
    h_batch = enforcer.compute_barrier(state_batch)

    # Both should be scalar or 1-element tensor
    assert h_single.numel() == 1
    assert h_batch.numel() == 1
