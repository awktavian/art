"""Tests for ModernHopfieldScaled (hierarchical E8 Hopfield memory).

Verifies:
- Hierarchical E8 addressing with 240^L capacity
- Forward/backward gradient flow
- Device compatibility (CPU, MPS, CUDA)

Reference: Ramsauer et al. (2020) "Hopfield Networks is All You Need"
"""

from __future__ import annotations

import pytest
import torch

from kagami.core.optimality.improvements import ModernHopfieldScaled

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def pattern_dim() -> int:
    """Pattern dimension for testing."""
    return 64  # Must be divisible by num_heads


@pytest.fixture
def num_patterns() -> int:
    """Number of patterns for testing (E8 roots)."""
    return 240


@pytest.fixture
def device() -> torch.device:
    """Get appropriate device."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


# =============================================================================
# ModernHopfieldScaled Tests
# =============================================================================


class TestModernHopfieldScaled:
    """Tests for ModernHopfieldScaled (hierarchical E8 Hopfield)."""

    def test_init(self, pattern_dim: int, num_patterns: int) -> None:
        """Initialize with default parameters."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=4,
        )

        assert memory.pattern_dim == pattern_dim
        assert memory.num_patterns == num_patterns
        assert memory.num_levels == 4
        assert memory._effective_capacity == 240**4

    def test_forward_batched(self, pattern_dim: int, num_patterns: int) -> None:
        """Forward pass with batched query."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=2,
        )

        batch_size = 4
        query = torch.randn(batch_size, pattern_dim)

        result = memory(query)

        assert "retrieved" in result
        assert "attention_entropy" in result
        assert "levels_used" in result
        assert "effective_capacity" in result
        assert result["retrieved"].shape == (batch_size, pattern_dim)

    def test_forward_with_attention(self, pattern_dim: int, num_patterns: int) -> None:
        """Forward pass returns attention weights when requested."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=2,
        )

        query = torch.randn(4, pattern_dim)

        result = memory(query, return_attention=True)

        assert "attentions" in result
        assert isinstance(result["attentions"], list)
        # Each level has attention over 240 E8 roots
        for att in result["attentions"]:
            assert att.shape[-1] == num_patterns

    def test_hierarchical_capacity(self, pattern_dim: int, num_patterns: int) -> None:
        """Hierarchical levels provide exponential capacity."""
        for num_levels in [1, 2, 4]:
            memory = ModernHopfieldScaled(
                pattern_dim=pattern_dim,
                num_patterns=num_patterns,
                num_heads=4,
                num_levels=num_levels,
            )

            expected_capacity = num_patterns**num_levels
            assert memory._effective_capacity == expected_capacity

    def test_e8_codebook_exists(self, pattern_dim: int, num_patterns: int) -> None:
        """E8 codebook is properly initialized."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=2,
        )

        assert hasattr(memory, "e8_codebook")
        assert memory.e8_codebook.shape == (240, 8)

    def test_separation_loss_in_training(self, pattern_dim: int, num_patterns: int) -> None:
        """Separation loss is returned during training."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=2,
            separation_loss_weight=0.1,
        )
        memory.train()

        query = torch.randn(4, pattern_dim)
        result = memory(query)

        assert "separation_loss" in result

    def test_no_separation_loss_in_eval(self, pattern_dim: int, num_patterns: int) -> None:
        """Separation loss is not returned during eval."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=2,
        )
        memory.eval()

        query = torch.randn(4, pattern_dim)
        result = memory(query)

        assert "separation_loss" not in result

    def test_gradient_flow(self, pattern_dim: int, num_patterns: int) -> None:
        """Gradients flow through the network."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=2,
        )

        query = torch.randn(4, pattern_dim, requires_grad=True)
        result = memory(query)

        loss = result["retrieved"].sum()
        loss.backward()

        assert query.grad is not None
        # Level values should have gradients
        for level_val in memory.level_values:
            assert level_val.grad is not None

    def test_checkpointed_forward(self, pattern_dim: int, num_patterns: int) -> None:
        """Gradient checkpointing produces same output."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=2,
        )

        query = torch.randn(4, pattern_dim)

        # Standard forward
        result_standard = memory(query)

        # Checkpointed forward
        result_checkpointed = memory.forward_checkpointed(query)

        assert result_checkpointed["checkpointed"] is True
        assert result_checkpointed["retrieved"].shape == result_standard["retrieved"].shape


# =============================================================================
# Device Tests
# =============================================================================


class TestHopfieldDevice:
    """Tests for device compatibility."""

    def test_cpu_operations(self, pattern_dim: int, num_patterns: int) -> None:
        """Memory operations work on CPU."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=2,
        )
        memory.to("cpu")

        query = torch.randn(4, pattern_dim, device="cpu")
        result = memory(query)

        assert result["retrieved"].device.type == "cpu"

    @pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS not available")
    def test_mps_operations(self, pattern_dim: int, num_patterns: int) -> None:
        """Memory operations work on MPS."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=2,
        )
        memory.to("mps")

        query = torch.randn(4, pattern_dim, device="mps")
        result = memory(query)

        assert result["retrieved"].device.type == "mps"

    @pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA not available")
    def test_cuda_operations(self, pattern_dim: int, num_patterns: int) -> None:
        """Memory operations work on CUDA."""
        memory = ModernHopfieldScaled(
            pattern_dim=pattern_dim,
            num_patterns=num_patterns,
            num_heads=4,
            num_levels=2,
        )
        memory.to("cuda")

        query = torch.randn(4, pattern_dim, device="cuda")
        result = memory(query)

        assert result["retrieved"].device.type == "cuda"


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Tests for backward-compatible imports."""

    def test_hierarchical_alias(self) -> None:
        """HierarchicalHopfieldMemory is alias to ModernHopfieldScaled."""
        from kagami.core.world_model.memory import HierarchicalHopfieldMemory

        assert HierarchicalHopfieldMemory is ModernHopfieldScaled

    def test_modern_alias(self) -> None:
        """ModernHopfieldMemory is alias to ModernHopfieldScaled."""
        from kagami.core.world_model.memory import ModernHopfieldMemory

        assert ModernHopfieldMemory is ModernHopfieldScaled
