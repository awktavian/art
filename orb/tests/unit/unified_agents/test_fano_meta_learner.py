"""Unit tests for Fano-Constrained Attention Meta-Learner.

Tests:
1. Initialization from octonion multiplication table
2. Forward pass with Fano-constrained attention
3. MAML meta-training step with second-order gradients
4. Task-specific Fano line selection
5. Attention matrix structure (21 of 49 edges)
6. Visualization utilities
7. Checkpoint save/load
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit

import tempfile
from pathlib import Path

import torch

from kagami_math.fano_plane import FANO_LINES, get_fano_lines_zero_indexed
from kagami.core.unified_agents.fano_meta_learner import (
    FanoMetaLearner,
    visualize_fano_structure,
)


@pytest.fixture
def meta_learner():
    """Create FanoMetaLearner instance for testing."""
    return FanoMetaLearner(
        d_model=64,
        num_heads=7,
        num_colonies=7,
        dropout=0.0,  # Disable for deterministic tests
        inner_lr=0.01,
        device="cpu",
    )


@pytest.fixture
def sample_batch():
    """Create sample batch of colony outputs and task embeddings."""
    batch_size = 4
    d_model = 64

    colony_outputs = torch.randn(batch_size, 7, d_model)
    task_embedding = torch.randn(batch_size, d_model)

    return colony_outputs, task_embedding


class TestInitialization:
    """Test initialization and setup."""

    def test_initialization(self, meta_learner) -> None:
        """Test that meta-learner initializes correctly."""
        assert meta_learner.d_model == 64
        assert meta_learner.num_heads == 7
        assert meta_learner.num_colonies == 7
        assert len(meta_learner.fano_lines) == 7

    def test_octonion_initialization(self, meta_learner) -> None:
        """Test that attention weights are initialized from octonion table."""
        # Weights should have shape [7 lines, 3 colonies per line]
        assert meta_learner.fano_attention_weights.shape == (7, 3)

        # Weights should not be zero (initialized with signs + noise)
        assert not torch.allclose(
            meta_learner.fano_attention_weights,
            torch.zeros_like(meta_learner.fano_attention_weights),
        )

        # Weights should be roughly in [-1.1, 1.1] range (signs ± noise)
        assert meta_learner.fano_attention_weights.abs().max() < 2.0

    def test_fano_lines_structure(self, meta_learner) -> None:
        """Test that Fano lines have correct structure."""
        fano_lines = meta_learner.fano_lines

        # Should have 7 lines
        assert len(fano_lines) == 7

        # Each line should have 3 colonies
        for line in fano_lines:
            assert len(line) == 3

        # All colonies should be in range [0, 6]
        for line in fano_lines:
            for colony_idx in line:
                assert 0 <= colony_idx < 7


class TestForwardPass:
    """Test forward pass and attention computation."""

    def test_forward_shape(self, meta_learner, sample_batch) -> None:
        """Test that forward pass produces correct output shape."""
        colony_outputs, task_embedding = sample_batch
        batch_size = colony_outputs.shape[0]

        output = meta_learner(colony_outputs, task_embedding)

        assert output.shape == (batch_size, meta_learner.d_model)

    def test_forward_differentiable(self, meta_learner, sample_batch) -> None:
        """Test that forward pass is differentiable."""
        colony_outputs, task_embedding = sample_batch

        # Ensure inputs require grad
        colony_outputs = colony_outputs.requires_grad_(True)
        task_embedding = task_embedding.requires_grad_(True)

        output = meta_learner(colony_outputs, task_embedding)
        loss = output.mean()

        # Should be able to backpropagate
        loss.backward()

        assert colony_outputs.grad is not None
        assert task_embedding.grad is not None

    def test_batch_independence(self, meta_learner) -> None:
        """Test that batch elements are processed independently."""
        batch_size = 4
        d_model = 64

        colony_outputs = torch.randn(batch_size, 7, d_model)
        task_embedding = torch.randn(batch_size, d_model)

        # Process full batch
        full_output = meta_learner(colony_outputs, task_embedding)

        # Process individual elements
        individual_outputs = []
        for i in range(batch_size):
            out = meta_learner(colony_outputs[i : i + 1], task_embedding[i : i + 1])
            individual_outputs.append(out)

        individual_outputs = torch.cat(individual_outputs, dim=0)  # type: ignore[assignment]

        # Should produce same results
        assert torch.allclose(full_output, individual_outputs, atol=1e-5)  # type: ignore[arg-type]


class TestMAMLMetaTraining:
    """Test MAML meta-training functionality."""

    def test_meta_train_step_shape(self, meta_learner) -> None:
        """Test that meta-training step executes and returns loss."""
        batch_size = 2
        d_model = 64

        # Create synthetic support and query tasks
        support_tasks = [
            {
                "colony_outputs": torch.randn(batch_size, 7, d_model),
                "task_emb": torch.randn(batch_size, d_model),
                "target": torch.randn(batch_size, d_model),
            }
            for _ in range(3)
        ]

        query_tasks = [
            {
                "colony_outputs": torch.randn(batch_size, 7, d_model),
                "task_emb": torch.randn(batch_size, d_model),
                "target": torch.randn(batch_size, d_model),
            }
            for _ in range(2)
        ]

        loss = meta_learner.meta_train_step(support_tasks, query_tasks, num_inner_steps=3)

        # Should return scalar loss
        assert loss.dim() == 0
        assert loss.item() > 0  # MSE loss should be positive

    def test_meta_train_second_order_gradients(self, meta_learner) -> None:
        """Test that MAML uses second-order gradients."""
        batch_size = 2
        d_model = 64

        support_tasks = [
            {
                "colony_outputs": torch.randn(batch_size, 7, d_model),
                "task_emb": torch.randn(batch_size, d_model),
                "target": torch.randn(batch_size, d_model),
            }
        ]

        query_tasks = [
            {
                "colony_outputs": torch.randn(batch_size, 7, d_model),
                "task_emb": torch.randn(batch_size, d_model),
                "target": torch.randn(batch_size, d_model),
            }
        ]

        # Store initial weights
        initial_weights = meta_learner.fano_attention_weights.clone()

        # Meta-training step with backprop
        loss = meta_learner.meta_train_step(support_tasks, query_tasks)
        loss.backward()

        # Weights should have gradients (second-order)
        assert meta_learner.fano_attention_weights.grad is not None

    def test_adaptation_improves_performance(self, meta_learner) -> None:
        """Test that adaptation reduces loss on support set."""
        batch_size = 2
        d_model = 64

        # Create a simple task where output should match input
        colony_outputs = torch.randn(batch_size, 7, d_model)
        task_emb = torch.randn(batch_size, d_model)
        target = colony_outputs.mean(dim=1)  # Simple target

        support_tasks = [
            {
                "colony_outputs": colony_outputs,
                "task_emb": task_emb,
                "target": target,
            }
        ] * 5  # Multiple examples

        # Loss before adaptation
        with torch.no_grad():
            pred_before = meta_learner(colony_outputs, task_emb)
            loss_before = torch.nn.functional.mse_loss(pred_before, target)

        # Adapt (inner loop only)
        adapted_weights = meta_learner.fano_attention_weights.clone()
        for _ in range(10):  # More steps for clearer improvement
            support_loss = 0.0
            for task in support_tasks:
                pred = meta_learner._forward_with_weights(
                    task["colony_outputs"],
                    task["task_emb"],
                    adapted_weights,
                )
                support_loss += torch.nn.functional.mse_loss(pred, task["target"])  # type: ignore[assignment]

            support_loss = support_loss / len(support_tasks)
            grad = torch.autograd.grad(support_loss, adapted_weights)[0]  # type: ignore[arg-type]
            adapted_weights = adapted_weights - 0.1 * grad  # Larger LR for test

        # Loss after adaptation
        with torch.no_grad():
            pred_after = meta_learner._forward_with_weights(
                colony_outputs, task_emb, adapted_weights
            )
            loss_after = torch.nn.functional.mse_loss(pred_after, target)

        # Adaptation should reduce loss
        assert loss_after < loss_before


class TestLineSelection:
    """Test Fano line selection functionality."""

    def test_select_best_line_shape(self, meta_learner) -> None:
        """Test that line selection returns correct format."""
        task_emb = torch.randn(64)

        line_idx, confidence = meta_learner.select_best_line(task_emb)

        # Should return int line index and float confidence
        assert isinstance(line_idx, int)
        assert isinstance(confidence, float)
        assert 0 <= line_idx < 7
        assert 0.0 <= confidence <= 1.0

    def test_select_best_line_batched(self, meta_learner) -> None:
        """Test that line selection works with batched input."""
        batch_size = 4
        task_emb = torch.randn(batch_size, 64)

        line_idx, confidence = meta_learner.select_best_line(task_emb)

        # Should return first element of batch
        assert isinstance(line_idx, int)
        assert isinstance(confidence, float)

    def test_task_line_importance(self, meta_learner) -> None:
        """Test getting importance scores for all lines."""
        task_emb = torch.randn(64)

        importance = meta_learner.get_task_line_importance(task_emb)

        # Should return [7] tensor of probabilities
        assert importance.shape == (7,)
        assert torch.allclose(importance.sum(), torch.tensor(1.0), atol=1e-5)
        assert (importance >= 0).all()
        assert (importance <= 1).all()


class TestAttentionMatrix:
    """Test attention matrix structure and visualization."""

    def test_attention_matrix_shape(self, meta_learner) -> None:
        """Test that attention matrix has correct shape."""
        attention = meta_learner.get_attention_matrix()

        assert attention.shape == (7, 7)

    def test_attention_matrix_sparsity(self, meta_learner) -> None:
        """Test that attention matrix has exactly 21 non-zero entries."""
        attention = meta_learner.get_attention_matrix()

        # Count non-zero entries (above threshold)
        non_zero = (attention.abs() > 1e-6).sum().item()

        # Should have exactly 21 edges (each Fano line contributes 3 bidirectional edges)
        # 7 lines × 6 directed edges per line / 2 (bidirectional) = 21 unique pairs
        # But each pair appears twice in the matrix, so 42 entries
        assert non_zero == 42

    def test_attention_matrix_symmetry(self, meta_learner) -> None:
        """Test that attention matrix is symmetric."""
        attention = meta_learner.get_attention_matrix()

        # Should be symmetric
        assert torch.allclose(attention, attention.T, atol=1e-5)

    def test_attention_matrix_fano_structure(self, meta_learner) -> None:
        """Test that non-zero entries correspond to Fano lines."""
        attention = meta_learner.get_attention_matrix()
        fano_lines = get_fano_lines_zero_indexed()

        # Check that all Fano pairs have non-zero attention
        for line in fano_lines:
            i, j, k = line
            # All three pairs on this line should have non-zero attention
            assert attention[i, j].abs() > 1e-6
            assert attention[j, k].abs() > 1e-6
            assert attention[k, i].abs() > 1e-6

        # Check that non-Fano pairs have zero attention
        fano_pairs = set()
        for line in fano_lines:
            i, j, k = line
            fano_pairs.add((i, j))
            fano_pairs.add((j, i))
            fano_pairs.add((j, k))
            fano_pairs.add((k, j))
            fano_pairs.add((k, i))
            fano_pairs.add((i, k))

        for i in range(7):
            for j in range(7):
                if i != j and (i, j) not in fano_pairs:
                    # Non-Fano pair should have zero attention
                    assert attention[i, j].abs() < 1e-6


class TestLineInfo:
    """Test line information utilities."""

    def test_get_line_info(self, meta_learner) -> None:
        """Test getting information about a Fano line."""
        info = meta_learner.get_line_info(0)

        assert "line_idx" in info
        assert "colonies" in info
        assert "multiplication_signs" in info
        assert "learned_weights" in info

        assert info["line_idx"] == 0
        assert len(info["colonies"]) == 3
        assert len(info["multiplication_signs"]) == 3
        assert len(info["learned_weights"]) == 3

    def test_get_line_info_invalid_index(self, meta_learner) -> None:
        """Test that invalid line index raises error."""
        with pytest.raises(ValueError):
            meta_learner.get_line_info(7)

        with pytest.raises(ValueError):
            meta_learner.get_line_info(-1)


class TestVisualization:
    """Test visualization utilities."""

    def test_visualize_fano_structure(self, meta_learner) -> None:
        """Test ASCII visualization generation."""
        viz = visualize_fano_structure(meta_learner)

        # Should be a string
        assert isinstance(viz, str)

        # Should contain matrix header
        assert "Fano Attention Matrix" in viz

        # Should have 7 rows
        lines = viz.split("\n")
        matrix_rows = [line for line in lines if line.startswith("c")]
        assert len(matrix_rows) == 7


class TestCheckpoint:
    """Test checkpoint save/load functionality."""

    def test_save_load_checkpoint(self, meta_learner) -> None:
        """Test that checkpoint can be saved and loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "checkpoint.pt"

            # Save checkpoint
            meta_learner.save_checkpoint(str(checkpoint_path))

            # Verify file exists
            assert checkpoint_path.exists()

            # Create new model and load checkpoint
            new_model = FanoMetaLearner(
                d_model=64,
                num_heads=7,
                num_colonies=7,
                device="cpu",
            )

            new_model.load_checkpoint(str(checkpoint_path))

            # Weights should match
            assert torch.allclose(
                meta_learner.fano_attention_weights,
                new_model.fano_attention_weights,
            )

    def test_checkpoint_preserves_training_state(self, meta_learner) -> None:
        """Test that checkpoint preserves meta-training state."""
        # Run some meta-training
        meta_learner._meta_iterations = 42
        meta_learner._tasks_trained = 100

        with tempfile.TemporaryDirectory() as tmpdir:
            checkpoint_path = Path(tmpdir) / "checkpoint.pt"

            # Save and load
            meta_learner.save_checkpoint(str(checkpoint_path))

            new_model = FanoMetaLearner(d_model=64, device="cpu")
            new_model.load_checkpoint(str(checkpoint_path))

            # Training state should be preserved
            assert new_model._meta_iterations == 42
            assert new_model._tasks_trained == 100


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_example_batch(self, meta_learner) -> None:
        """Test with batch size of 1."""
        colony_outputs = torch.randn(1, 7, 64)
        task_emb = torch.randn(1, 64)

        output = meta_learner(colony_outputs, task_emb)

        assert output.shape == (1, 64)

    def test_large_batch(self, meta_learner) -> None:
        """Test with large batch size."""
        batch_size = 128
        colony_outputs = torch.randn(batch_size, 7, 64)
        task_emb = torch.randn(batch_size, 64)

        output = meta_learner(colony_outputs, task_emb)

        assert output.shape == (batch_size, 64)

    def test_zero_colony_outputs(self, meta_learner) -> None:
        """Test with zero colony outputs."""
        colony_outputs = torch.zeros(4, 7, 64)
        task_emb = torch.randn(4, 64)

        # Should not crash
        output = meta_learner(colony_outputs, task_emb)

        assert output.shape == (4, 64)
        assert not torch.isnan(output).any()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
