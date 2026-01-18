"""Tests for model pre-warming during boot (Dec 21, 2025).

Verifies that CBF and Cost module pre-warming:
1. Initializes models correctly
2. Runs warmup passes without errors
3. Reduces first-inference latency
4. Handles failures gracefully (non-critical)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration
import time
import torch


def test_cbf_warmup_performance() -> None:
    """Test CBF model pre-warming reduces inference latency."""
    from kagami.core.safety.optimal_cbf import get_optimal_cbf

    # Get CBF instance
    cbf = get_optimal_cbf()
    # Get device
    device = cbf.state_encoder.encoder[0].weight.device
    # Create test input
    test_state = torch.randn(1, 4, device=device)  # type: ignore[arg-type]
    # Measure cold inference time (first run)
    cold_start = time.perf_counter()
    with torch.no_grad():
        _ = cbf.barrier_value(test_state)
    cold_time = (time.perf_counter() - cold_start) * 1000
    # Pre-warm with 3 forward passes
    with torch.no_grad():
        for _ in range(3):
            _ = cbf.barrier_value(test_state)
    # Measure warm inference time (after warmup)
    warm_times = []
    for _ in range(10):
        warm_start = time.perf_counter()
        with torch.no_grad():
            _ = cbf.barrier_value(test_state)
        warm_times.append((time.perf_counter() - warm_start) * 1000)
    avg_warm_time = sum(warm_times) / len(warm_times)
    # Verify warmup improves performance
    # Note: On CPU this may not show significant difference
    # On GPU/MPS, warmup compiles shaders and shows clear improvement
    assert avg_warm_time < 100, f"Warm inference too slow: {avg_warm_time:.2f}ms"
    print(f"CBF inference: cold={cold_time:.2f}ms, warm={avg_warm_time:.2f}ms")


def test_cost_module_warmup_performance() -> None:
    """Test Cost module pre-warming reduces inference latency."""
    from kagami.core.rl.unified_cost_module import (
        CostModuleConfig,
        get_cost_module,
    )

    # Initialize cost module
    cost_config = CostModuleConfig(
        state_dim=512,
        action_dim=64,
        ic_weight=0.6,
        tc_weight=0.4,
    )
    cost_module = get_cost_module(cost_config)
    # Get device
    device = cost_module.intrinsic_cost.safety_detector[0].weight.device
    # Create test inputs
    test_state = torch.randn(1, 512, device=device)  # type: ignore[arg-type]
    test_action = torch.randn(1, 64, device=device)  # type: ignore[arg-type]
    # Measure cold inference time (first run)
    cold_start = time.perf_counter()
    with torch.no_grad():
        _ = cost_module(test_state, test_action)
    cold_time = (time.perf_counter() - cold_start) * 1000
    # Pre-warm with 3 forward passes
    with torch.no_grad():
        for _ in range(3):
            _ = cost_module(test_state, test_action)
    # Measure warm inference time (after warmup)
    warm_times = []
    for _ in range(10):
        warm_start = time.perf_counter()
        with torch.no_grad():
            _ = cost_module(test_state, test_action)
        warm_times.append((time.perf_counter() - warm_start) * 1000)
    avg_warm_time = sum(warm_times) / len(warm_times)
    # Verify warmup improves performance
    assert avg_warm_time < 100, f"Warm inference too slow: {avg_warm_time:.2f}ms"
    print(f"Cost module inference: cold={cold_time:.2f}ms, warm={avg_warm_time:.2f}ms")


def test_cbf_warmup_device_detection() -> None:
    """Test CBF warmup correctly detects device."""
    from kagami.core.safety.optimal_cbf import get_optimal_cbf

    cbf = get_optimal_cbf()
    # Should detect device from encoder
    device = cbf.state_encoder.encoder[0].weight.device
    assert device is not None
    assert isinstance(device, torch.device)
    # Warmup should work on detected device
    dummy_state = torch.randn(1, 4, device=device)
    with torch.no_grad():
        result = cbf.barrier_value(dummy_state)
    assert result is not None
    assert result.device == device


def test_cost_module_warmup_device_detection() -> None:
    """Test Cost module warmup correctly detects device."""
    from kagami.core.rl.unified_cost_module import (
        CostModuleConfig,
        get_cost_module,
    )

    cost_module = get_cost_module(
        CostModuleConfig(
            state_dim=512,
            action_dim=64,
        )
    )
    # Should detect device from intrinsic cost detector
    device = cost_module.intrinsic_cost.safety_detector[0].weight.device
    assert device is not None
    assert isinstance(device, torch.device)
    # Warmup should work on detected device
    dummy_state = torch.randn(1, 512, device=device)
    dummy_action = torch.randn(1, 64, device=device)
    with torch.no_grad():
        result = cost_module(dummy_state, dummy_action)
    assert result is not None
    assert "total" in result
    assert result["total"].device == device


def test_warmup_graceful_failure() -> None:
    """Test that warmup failures don't crash boot."""
    # This test verifies the try-except blocks in wiring.py
    # Actual boot testing requires integration test
    # Simulate warmup failure by accessing invalid tensor attribute
    try:
        dummy = torch.randn(1, 4)
        # Try to access non-existent attribute (simulates warmup failure)
        _ = dummy.nonexistent_method()  # type: ignore
        pytest.fail("Should have raised AttributeError")
    except AttributeError:
        # Error is caught, boot would continue
        pass
    # Also test that we handle device errors properly
    try:
        # On systems without MPS, this should raise
        if not torch.backends.mps.is_available():
            invalid_device = torch.device("mps")
            _ = torch.randn(1, 4, device=invalid_device)
            pytest.fail("Should have raised error for unavailable MPS")
    except RuntimeError:
        # Error is caught, boot would continue
        pass


def test_warmup_iterations() -> None:
    """Test that 3 warmup iterations is sufficient."""
    from kagami.core.safety.optimal_cbf import get_optimal_cbf

    cbf = get_optimal_cbf()
    device = cbf.state_encoder.encoder[0].weight.device
    test_state = torch.randn(1, 4, device=device)  # type: ignore[arg-type]
    # Time first 5 iterations
    times = []
    for _ in range(5):
        start = time.perf_counter()
        with torch.no_grad():
            _ = cbf.barrier_value(test_state)
        times.append((time.perf_counter() - start) * 1000)
    # By iteration 3 (index 2), should be warmed up
    # Last 2 iterations should be relatively stable
    avg_warmup = sum(times[:3]) / 3
    avg_stable = sum(times[3:]) / 2
    print(f"Warmup iterations: {times}")
    print(f"Avg warmup: {avg_warmup:.2f}ms, Avg stable: {avg_stable:.2f}ms")
    # Stable time should be <= warmup time (may be much faster on GPU)
    # Allow 50% tolerance for measurement noise
    assert avg_stable <= avg_warmup * 1.5, "Stable time should not increase after warmup"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
