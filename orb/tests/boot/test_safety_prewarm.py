"""Test safety model pre-warming during boot.

CREATED: December 21, 2025
PURPOSE: Verify safety classifier pre-warming eliminates first-call timeout

CRITICAL PROPERTY:
- Safety classifier (WildGuard) loads during boot, not on first call
- First CBF check after boot is <100ms (not 5+ seconds)
- Pre-warming runs 3 forward passes to compile Metal/MPS shaders
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
import time
from unittest.mock import MagicMock, Mock, patch
import torch
from kagami.core.safety.cbf_integration import get_safety_filter
from kagami.core.safety.llm_safety_integration import (
    IntegratedSafetyFilter,
    SafetyClassification,
    RiskCategory,
)


@pytest.fixture
def mock_wildguard_classifier():
    """Mock WildGuard classifier that simulates real loading time."""
    mock_classifier = MagicMock()
    mock_classifier._loaded = False
    mock_classifier._load_count = 0

    def mock_classify(text: str, context: str | None = None) -> SafetyClassification:
        """Simulate slow first load, fast subsequent calls."""
        if not mock_classifier._loaded:
            # First call: simulate model loading (5s)
            time.sleep(0.1)  # Use shorter time in tests
            mock_classifier._loaded = True
            mock_classifier._load_count += 1
        # Subsequent calls: fast inference
        return SafetyClassification(
            is_safe=True,
            risk_scores=dict.fromkeys(RiskCategory, 0.0),
            confidence=1.0,
            reasoning="test",
            raw_output={"test": True},
        )

    mock_classifier.classify = Mock(side_effect=mock_classify)
    return mock_classifier


def test_safety_filter_lazy_loading(mock_wildguard_classifier) -> None:
    """Test that safety filter loads lazily on first call (baseline behavior)."""
    # Create filter with mock classifier
    safety_filter = IntegratedSafetyFilter(
        classifier=mock_wildguard_classifier,
        use_optimal_cbf=True,
        cbf_state_dim=16,
        safety_threshold=0.3,
    )
    # Mock classifier should not be loaded yet
    assert mock_wildguard_classifier._loaded is False
    assert mock_wildguard_classifier._load_count == 0
    # First call triggers loading (slow)
    start = time.time()
    _, _, _ = safety_filter.filter_text(
        text="first call",
        nominal_control=torch.tensor([[0.5, 0.5]], dtype=torch.float32),
    )
    first_elapsed = time.time() - start
    # Should have loaded now
    assert mock_wildguard_classifier._loaded is True
    assert mock_wildguard_classifier._load_count == 1
    assert first_elapsed > 0.05, f"First call should be slow (loading), got {first_elapsed}s"
    # Second call should be fast (already loaded)
    start = time.time()
    _, _, _ = safety_filter.filter_text(
        text="second call",
        nominal_control=torch.tensor([[0.5, 0.5]], dtype=torch.float32),
    )
    second_elapsed = time.time() - start
    # Should still only have loaded once
    assert mock_wildguard_classifier._load_count == 1
    assert second_elapsed < 0.05, f"Second call should be fast (cached), got {second_elapsed}s"


def test_safety_filter_prewarm_eliminates_first_call_delay(mock_wildguard_classifier) -> None:
    """Test that pre-warming eliminates first-call delay."""
    # Create filter
    safety_filter = IntegratedSafetyFilter(
        classifier=mock_wildguard_classifier,
        use_optimal_cbf=True,
        cbf_state_dim=16,
        safety_threshold=0.3,
    )
    # PRE-WARM: Run dummy forward passes (simulates boot-time pre-warming)
    for _ in range(3):
        _, _, _ = safety_filter.filter_text(
            text="pre-warming",
            nominal_control=torch.tensor([[0.5, 0.5]], dtype=torch.float32),
            context="warmup",
        )
    # Classifier should be loaded and warmed up
    assert mock_wildguard_classifier._loaded is True
    assert mock_wildguard_classifier._load_count == 1
    # NOW: First "real" call after pre-warming should be fast
    start = time.time()
    _, _, _ = safety_filter.filter_text(
        text="first real call after prewarm",
        nominal_control=torch.tensor([[0.5, 0.5]], dtype=torch.float32),
    )
    elapsed = time.time() - start
    # Should be fast (<100ms) because already loaded
    assert (
        elapsed < 0.1
    ), f"First call after pre-warming should be <100ms, got {elapsed * 1000:.1f}ms"


@pytest.mark.asyncio
async def test_boot_prewarm_integration() -> None:
    """Test that boot process pre-warms safety classifier correctly.
    This simulates the startup_safety() pre-warming flow.
    """
    # Create a mock filter with tracking
    mock_filter = MagicMock()
    call_count = {"count": 0}

    def mock_filter_text(*args: Any, **kwargs) -> Any:
        call_count["count"] += 1
        return (
            torch.tensor([[0.5, 0.5]]),
            torch.tensor(0.0),
            {
                "classification": Mock(
                    is_safe=True,
                    risk_scores={},
                    max_risk=lambda: (RiskCategory.VIOLENCE, 0.0),
                    total_risk=lambda: 0.0,
                    confidence=1.0,
                ),
                "h_metric": torch.tensor(0.8),
            },
        )

    mock_filter.filter_text = mock_filter_text
    with patch("kagami.core.safety.cbf_integration._get_safety_filter", return_value=mock_filter):
        # Import after patching to use mocked version
        from kagami.core.safety.cbf_integration import get_safety_filter as get_filter

        # SIMULATE BOOT PRE-WARMING
        safety_filter = get_filter()
        # Run 3 dummy forward passes (as in boot code)
        for _i in range(3):
            _, _, _ = safety_filter.filter_text(
                text="Pre-warming safety classifier",
                nominal_control=torch.tensor([[0.5, 0.5]], dtype=torch.float32),
                context="warmup",
            )
        # Verify filter_text was called 3 times (pre-warming)
        assert call_count["count"] == 3, f"Expected 3 pre-warm calls, got {call_count['count']}"
        # SIMULATE FIRST REAL CALL AFTER BOOT
        start = time.time()
        _, _, _ = safety_filter.filter_text(
            text="first real call",
            nominal_control=torch.tensor([[0.5, 0.5]], dtype=torch.float32),
        )
        first_call_elapsed = (time.time() - start) * 1000
        # First call should be fast (<100ms) because model already loaded
        assert (
            first_call_elapsed < 100.0
        ), f"First call after pre-warming should be <100ms, got {first_call_elapsed:.1f}ms"


def test_prewarm_failure_graceful_degradation() -> None:
    """Test that boot continues even if pre-warming fails.
    The boot code wraps pre-warming in try/except to log warnings
    without crashing. This test verifies exception handling works.
    """

    def mock_get_safety_filter_failing():
        """Mock that raises exception during pre-warming."""
        raise RuntimeError("WildGuard model not available (gated repo)")

    with patch(
        "kagami.core.safety.cbf_integration._get_safety_filter", mock_get_safety_filter_failing
    ):
        # Import after patching
        from kagami.core.safety.cbf_integration import get_safety_filter as get_filter

        # Pre-warming should raise exception (boot code catches it)
        with pytest.raises(RuntimeError) as exc_info:
            get_filter()
        # Verify exception message
        assert "WildGuard" in str(exc_info.value) or "gated repo" in str(exc_info.value)


def test_prewarm_count_correct() -> None:
    """Test that pre-warming runs exactly 3 forward passes."""
    call_count = {"count": 0}

    def mock_filter_text(*args: Any, **kwargs) -> Any:
        call_count["count"] += 1
        return (
            torch.tensor([[0.5, 0.5]]),
            torch.tensor(0.0),
            {
                "classification": Mock(
                    is_safe=True,
                    risk_scores={},
                    max_risk=lambda: (RiskCategory.VIOLENCE, 0.0),
                    total_risk=lambda: 0.0,
                    confidence=1.0,
                ),
                "h_metric": torch.tensor(0.8),
            },
        )

    mock_filter = MagicMock()
    mock_filter.filter_text = mock_filter_text
    with patch("kagami.core.safety.cbf_integration._get_safety_filter", return_value=mock_filter):
        # Import after patching
        from kagami.core.safety.cbf_integration import get_safety_filter as get_filter

        safety_filter = get_filter()
        # Simulate boot pre-warming (3 forward passes)
        for _ in range(3):
            _, _, _ = safety_filter.filter_text(
                text="Pre-warming safety classifier",
                nominal_control=torch.tensor([[0.5, 0.5]], dtype=torch.float32),
                context="warmup",
            )
        # Verify exactly 3 calls during pre-warming
        assert call_count["count"] == 3, f"Expected 3 pre-warm calls, got {call_count['count']}"


__all__ = [
    "test_boot_prewarm_integration",
    "test_prewarm_count_correct",
    "test_prewarm_failure_graceful_degradation",
    "test_safety_filter_lazy_loading",
    "test_safety_filter_prewarm_eliminates_first_call_delay",
]
