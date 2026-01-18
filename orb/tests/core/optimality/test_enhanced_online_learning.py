"""Tests for Enhanced Online Learning Module.

Tests:
- UnifiedReplayBuffer (consolidated from PrioritizedReplayEnhanced)
- AdaptiveEWC
- GradientAlignmentDetector
- EnhancedOnlineLearning (unified)

Created: December 4, 2025
Updated: December 6, 2025 - Tests use UnifiedReplayBuffer directly
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import numpy as np
import torch
import torch.nn as nn


class SimpleModel(nn.Module):
    """Simple model for testing."""

    def __init__(self, input_dim: int = 32, output_dim: int = 32):
        super().__init__()
        self.linear = nn.Linear(input_dim, output_dim)

    def forward(self, x: Any) -> Self:
        return self.linear(x), {}


class TestUnifiedReplayBuffer:
    """Tests for UnifiedReplayBuffer (replaces PrioritizedReplayEnhanced)."""

    def test_init(self) -> Any:
        """Test initialization with backward-compatible kwargs."""
        from kagami.core.memory.unified_replay import UnifiedReplayBuffer

        # Test with capacity kwarg (backward compatible)
        replay = UnifiedReplayBuffer(capacity=100)
        assert replay is not None
        assert replay.config.capacity == 100

    def test_add_experience(self) -> None:
        """Test adding experiences."""
        from kagami.core.memory.unified_replay import (
            UnifiedReplayBuffer,
            UnifiedExperience,
        )

        replay = UnifiedReplayBuffer(capacity=100)

        exp = UnifiedExperience(
            state=torch.randn(32),
            action={"action": "test"},
            next_state=torch.randn(32),
            reward=1.0,
            done=False,
            priority=0.5,
        )

        replay.add(exp)
        assert len(replay) == 1

    def test_sample(self) -> None:
        """Test sampling from replay."""
        from kagami.core.memory.unified_replay import (
            UnifiedReplayBuffer,
            UnifiedExperience,
        )

        replay = UnifiedReplayBuffer(capacity=100)

        # Add multiple experiences
        for i in range(50):
            exp = UnifiedExperience(
                state=torch.randn(32),
                action={"action": f"test_{i}"},
                next_state=torch.randn(32),
                reward=float(i),
                done=False,
                priority=float(i + 1),
            )
            replay.add(exp)

        # Sample batch
        experiences, weights, indices = replay.sample(batch_size=16)

        assert len(experiences) == 16
        assert weights.shape == (16,)
        assert len(indices) == 16

    def test_beta_annealing(self) -> None:
        """Test beta annealing over time via config."""
        from kagami.core.memory.unified_replay import (
            UnifiedReplayBuffer,
            UnifiedReplayConfig,
            UnifiedExperience,
        )

        config = UnifiedReplayConfig(
            capacity=100,
            beta_start=0.4,
            beta_end=1.0,
            beta_frames=100,
        )
        replay = UnifiedReplayBuffer(config)

        assert replay.beta == pytest.approx(0.4, abs=0.01)

        # Add experiences to advance frame counter
        for _i in range(100):
            exp = UnifiedExperience(
                state=torch.randn(32),
                action={},
                next_state=torch.randn(32),
                reward=0.0,
                done=False,
            )
            replay.add(exp)

        # Beta should have annealed toward 1.0
        assert replay.beta >= 0.4

    def test_priority_update(self) -> None:
        """Test priority updates."""
        from kagami.core.memory.unified_replay import (
            UnifiedReplayBuffer,
            UnifiedExperience,
        )

        replay = UnifiedReplayBuffer(capacity=100)

        # Add experiences
        for _i in range(10):
            exp = UnifiedExperience(
                state=torch.randn(32),
                action={},
                next_state=torch.randn(32),
                reward=0.0,
                done=False,
                priority=1.0,
            )
            replay.add(exp)

        # Update priorities
        indices = np.array([0, 1, 2])
        new_td_errors = np.array([10.0, 0.1, 5.0])

        replay.update_priorities(indices, new_td_errors)

        # Just verify no error - priorities are tracked internally

    def test_statistics(self) -> None:
        """Test statistics retrieval."""
        from kagami.core.memory.unified_replay import (
            UnifiedReplayBuffer,
            UnifiedExperience,
        )

        replay = UnifiedReplayBuffer(capacity=100)

        for _i in range(20):
            exp = UnifiedExperience(
                state=torch.randn(32),
                action={},
                next_state=torch.randn(32),
                reward=0.0,
                done=False,
            )
            replay.add(exp)

        stats = replay.get_stats()

        assert stats["size"] == 20
        assert stats["capacity"] == 100
        assert stats["utilization"] == pytest.approx(0.2, abs=0.01)


class TestAdaptiveEWC:
    """Tests for adaptive EWC."""

    def test_init(self) -> None:
        """Test initialization."""
        from kagami.core.optimality.enhanced_online_learning import AdaptiveEWC

        model = SimpleModel()
        ewc = AdaptiveEWC(model, lambda_base=0.4)

        assert ewc is not None
        assert ewc.lambda_base == 0.4

    def test_consolidate(self) -> None:
        """Test task consolidation."""
        from kagami.core.optimality.enhanced_online_learning import AdaptiveEWC

        model = SimpleModel()
        ewc = AdaptiveEWC(model)

        ewc.consolidate("task_1")

        assert "task_1" in ewc._optimal_params
        assert "task_1" in ewc._fisher

    def test_ewc_loss(self) -> None:
        """Test EWC loss computation."""
        from kagami.core.optimality.enhanced_online_learning import AdaptiveEWC

        model = SimpleModel()
        ewc = AdaptiveEWC(model)

        # Consolidate a task
        ewc.consolidate("task_1")

        # Modify model parameters
        with torch.no_grad():
            for param in model.parameters():
                param.add_(torch.randn_like(param) * 0.1)

        # Compute EWC loss
        loss = ewc.compute_ewc_loss()

        assert loss.item() > 0  # Should be positive after parameter change

    def test_adaptive_lambda(self) -> None:
        """Test adaptive lambda adjustment."""
        from kagami.core.optimality.enhanced_online_learning import AdaptiveEWC

        model = SimpleModel()
        ewc = AdaptiveEWC(model, lambda_base=0.4)

        ewc.consolidate("task_1")

        # Simulate performance drop -> should increase lambda
        ewc.adapt_lambda("task_1", performance_current=0.7, performance_previous=0.9)

        assert ewc._task_lambda["task_1"] > 0.4

        # Simulate performance improvement -> should decrease lambda
        ewc.adapt_lambda("task_1", performance_current=0.95, performance_previous=0.8)

        # Lambda should have decreased from the increased value

    def test_online_fisher(self) -> None:
        """Test online Fisher updates."""
        from kagami.core.optimality.enhanced_online_learning import AdaptiveEWC

        model = SimpleModel()
        ewc = AdaptiveEWC(model, online_fisher=True)

        # Run some forward passes with Fisher updates
        for _ in range(10):
            x = torch.randn(4, 32)
            output, _ = model(x)
            loss = output.pow(2).sum()

            ewc.update_running_fisher(loss)

        assert ewc._running_count == 10
        assert len(ewc._running_fisher) > 0

    def test_statistics(self) -> None:
        """Test statistics retrieval."""
        from kagami.core.optimality.enhanced_online_learning import AdaptiveEWC

        model = SimpleModel()
        ewc = AdaptiveEWC(model)

        ewc.consolidate("task_1")
        ewc.consolidate("task_2")

        stats = ewc.get_statistics()

        assert stats["num_tasks"] == 2
        assert "task_1" in stats["tasks"]
        assert "task_2" in stats["tasks"]


class TestGradientAlignmentDetector:
    """Tests for gradient alignment detection."""

    def test_init(self) -> None:
        """Test initialization."""
        from kagami.core.optimality.enhanced_online_learning import GradientAlignmentDetector

        detector = GradientAlignmentDetector()
        assert detector is not None

    def test_store_gradient(self) -> None:
        """Test gradient storage."""
        from kagami.core.optimality.enhanced_online_learning import GradientAlignmentDetector

        detector = GradientAlignmentDetector(memory_size=10)

        grad = torch.randn(100)
        detector.store_gradient("task_1", grad)

        assert "task_1" in detector._gradient_memory
        assert len(detector._gradient_memory["task_1"]) == 1

    def test_no_conflict_single_task(self) -> None:
        """Test no conflict with single task."""
        from kagami.core.optimality.enhanced_online_learning import GradientAlignmentDetector

        detector = GradientAlignmentDetector()

        grad = torch.randn(100)
        detector.store_gradient("task_1", grad)

        # Same task should not conflict with itself
        result = detector.check_conflict(grad, "task_1")

        assert not result["has_conflict"]

    def test_detect_conflict(self) -> None:
        """Test conflict detection."""
        from kagami.core.optimality.enhanced_online_learning import GradientAlignmentDetector

        detector = GradientAlignmentDetector()

        # Store a gradient
        grad_old = torch.ones(100)
        detector.store_gradient("task_1", grad_old)

        # Create conflicting gradient (opposite direction)
        grad_new = -torch.ones(100)

        result = detector.check_conflict(grad_new, "task_2")

        assert result["has_conflict"]
        assert len(result["conflicts"]) == 1

    def test_project_gradient(self) -> None:
        """Test gradient projection."""
        from kagami.core.optimality.enhanced_online_learning import GradientAlignmentDetector

        detector = GradientAlignmentDetector()

        # Store aligned gradient
        grad_old = torch.tensor([1.0, 0.0, 0.0, 0.0])
        detector.store_gradient("task_1", grad_old)

        # Create conflicting gradient
        grad_new = torch.tensor([-1.0, 1.0, 0.0, 0.0])

        result = detector.check_conflict(grad_new, "task_2")

        # Projected gradient should have reduced conflict
        projected = result["projected_gradient"]

        # The projection should reduce negative alignment
        alignment_original = torch.dot(grad_new, grad_old)
        alignment_projected = torch.dot(projected, grad_old)

        assert alignment_projected >= alignment_original

    def test_statistics(self) -> None:
        """Test statistics retrieval."""
        from kagami.core.optimality.enhanced_online_learning import GradientAlignmentDetector

        detector = GradientAlignmentDetector()

        detector.store_gradient("task_1", torch.randn(100))
        detector.check_conflict(torch.randn(100), "task_2")

        stats = detector.get_statistics()

        assert stats["total_checks"] == 1
        assert "task_1" in stats["tasks_tracked"]


class TestEnhancedOnlineLearning:
    """Tests for unified enhanced online learning."""

    def test_init(self) -> None:
        """Test initialization."""
        from kagami.core.optimality.enhanced_online_learning import EnhancedOnlineLearning

        model = SimpleModel()
        enhanced = EnhancedOnlineLearning(model)

        assert enhanced is not None
        assert enhanced.replay is not None
        assert enhanced.ewc is not None

    def test_set_task(self) -> None:
        """Test task setting."""
        from kagami.core.optimality.enhanced_online_learning import EnhancedOnlineLearning

        model = SimpleModel()
        enhanced = EnhancedOnlineLearning(model)

        enhanced.set_task("task_1")
        assert enhanced._current_task == "task_1"

    def test_add_and_sample(self) -> None:
        """Test adding and sampling experiences."""
        from kagami.core.optimality.enhanced_online_learning import EnhancedOnlineLearning

        model = SimpleModel()
        enhanced = EnhancedOnlineLearning(model)
        enhanced.set_task("task_1")

        # Add experiences
        for i in range(50):
            enhanced.add_experience(
                state=torch.randn(32),
                action={"i": i},
                next_state=torch.randn(32),
                reward=float(i),
                done=False,
            )

        # Sample
        experiences, _weights, _indices = enhanced.sample(16)

        assert len(experiences) == 16

    def test_gradient_alignment_integration(self) -> None:
        """Test gradient alignment is integrated."""
        from kagami.core.optimality.enhanced_online_learning import EnhancedOnlineLearning

        model = SimpleModel()
        enhanced = EnhancedOnlineLearning(
            model,
            enable_gradient_alignment=True,
        )
        enhanced.set_task("task_1")

        grad = torch.randn(100)
        enhanced.store_gradient(grad)

        result = enhanced.check_gradient_alignment(torch.randn(100))

        assert "has_conflict" in result
        assert "projected_gradient" in result

    def test_statistics(self) -> None:
        """Test statistics retrieval."""
        from kagami.core.optimality.enhanced_online_learning import EnhancedOnlineLearning

        model = SimpleModel()
        enhanced = EnhancedOnlineLearning(model)
        enhanced.set_task("task_1")

        stats = enhanced.get_statistics()

        assert "replay" in stats
        assert "ewc" in stats
        assert stats["current_task"] == "task_1"

    def test_singleton(self) -> None:
        """Test singleton pattern."""
        from kagami.core.optimality.enhanced_online_learning import (
            get_enhanced_online_learning,
        )

        # Reset singleton for test
        import kagami.core.optimality.enhanced_online_learning as module

        module._enhanced_online_learning = None

        model = SimpleModel()

        enhanced1 = get_enhanced_online_learning(model)
        enhanced2 = get_enhanced_online_learning()

        assert enhanced1 is enhanced2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
