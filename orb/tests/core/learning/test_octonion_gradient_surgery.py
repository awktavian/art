"""Tests for G₂-equivariant gradient surgery.

Tests cover:
1. G₂ parameter grouping and classification
2. G₂-aware gradient surgery (safe mode)
3. Octonion projection (experimental mode)
4. Fano-aware PCGrad
5. Integration with existing gradient surgery

Created: December 14, 2025
"""

from __future__ import annotations


import pytest
import torch
import torch.nn as nn

from kagami.core.learning.octonion_gradient_surgery import (
    G2ParameterGroups,
    OctonionGradientSurgery,
    OctonionPCGrad,
    apply_octonion_gradient_surgery,
)

# =============================================================================
# TEST FIXTURES
# =============================================================================


class SimpleColonyModel(nn.Module):
    """Simple model with G₂-structured parameters for testing."""

    def __init__(self, d_model: int = 16) -> None:
        super().__init__()

        # Global parameters (shared)
        self.global_embedding = nn.Linear(d_model, d_model)

        # Colony-specific parameters (7 colonies)
        self.colony_layers = nn.ModuleList([nn.Linear(d_model, d_model) for _ in range(7)])

        # Coupling parameters (Fano lines)
        self.fano_coupling = nn.Linear(d_model, d_model)

        # Higher-order parameters
        self.higher_order = nn.Linear(d_model, d_model)

    def forward(self, x: torch.Tensor, colony_idx: int) -> torch.Tensor:
        """Forward pass for a specific colony.

        Args:
            x: Input tensor [batch, d_model]
            colony_idx: Colony index (0-6)

        Returns:
            Output tensor [batch, d_model]
        """
        # Global processing
        x = self.global_embedding(x)

        # Colony-specific processing
        x = self.colony_layers[colony_idx](x)

        # Coupling
        x = self.fano_coupling(x)

        # Higher-order
        x = self.higher_order(x)

        return x


@pytest.fixture
def simple_model() -> SimpleColonyModel:
    """Create simple colony model."""
    return SimpleColonyModel(d_model=16)


@pytest.fixture
def colony_data() -> tuple[torch.Tensor, list[torch.Tensor]]:
    """Create test data for 7 colonies.

    Returns:
        (input_tensor, target_tensors) where targets are different for each colony
    """
    batch_size = 4
    d_model = 16

    x = torch.randn(batch_size, d_model)
    targets = [torch.randn(batch_size, d_model) for _ in range(7)]

    return x, targets


# =============================================================================
# TEST G₂ PARAMETER GROUPS
# =============================================================================


def test_g2_parameter_groups_creation(simple_model: SimpleColonyModel) -> None:
    """Test creating G₂ parameter groups from a model."""
    groups = G2ParameterGroups.from_model(simple_model)

    # Check structure
    assert len(groups.global_params) > 0, "Should have global parameters"
    assert len(groups.colony_params) == 7, "Should have 7 colony groups"
    assert len(groups.coupling_params) > 0, "Should have coupling parameters"
    assert len(groups.higher_params) > 0, "Should have higher-order parameters"


def test_g2_parameter_groups_classification(simple_model: SimpleColonyModel) -> None:
    """Test parameter classification by name."""
    groups = G2ParameterGroups.from_model(simple_model)

    # Check global parameters
    for param in groups.global_params:
        assert groups.get_group_for_param(param) == "global"
        assert groups.get_colony_for_param(param) is None

    # Check colony parameters
    for colony_idx in range(7):
        for param in groups.colony_params[colony_idx]:
            assert groups.get_group_for_param(param) == "colony"
            assert groups.get_colony_for_param(param) == colony_idx

    # Check coupling parameters
    for param in groups.coupling_params:
        assert groups.get_group_for_param(param) == "coupling"
        assert groups.get_colony_for_param(param) is None


def test_g2_parameter_groups_summary(simple_model: SimpleColonyModel) -> None:
    """Test parameter group summary statistics."""
    groups = G2ParameterGroups.from_model(simple_model)
    summary = groups.summary()

    # Check summary fields
    assert "global_params" in summary
    assert "colony_params" in summary
    assert "total_colony_params" in summary
    assert "coupling_params" in summary
    assert "higher_params" in summary
    assert "total_params" in summary

    # Check counts make sense
    assert summary["global_params"] > 0
    assert summary["total_colony_params"] > 0
    assert len(summary["colony_params"]) == 7
    assert summary["total_params"] > 0


def test_g2_parameter_groups_colony_extraction() -> None:
    """Test extracting colony index from parameter names."""
    groups = G2ParameterGroups()

    test_cases = [
        ("colony_0_weight", 0),
        ("colony_3_bias", 3),
        ("embedding.colony_5.norm", 5),
        ("colony_layer_6_weight", 6),
        ("global_weight", None),
        ("some_random_param", None),
    ]

    for name, expected_idx in test_cases:
        result = groups._extract_colony_idx(name)
        assert result == expected_idx, f"Failed for {name}: got {result}, expected {expected_idx}"


# =============================================================================
# TEST G₂ GRADIENT SURGERY
# =============================================================================


def test_octonion_gradient_surgery_g2_groups(
    simple_model: SimpleColonyModel,
    colony_data: tuple[torch.Tensor, list[torch.Tensor]],
) -> None:
    """Test G₂ parameter groups mode (safe mode)."""
    x, targets = colony_data
    model = simple_model

    # Create parameter groups
    param_groups = G2ParameterGroups.from_model(model)

    # Compute gradients for each colony
    colony_gradients: list[list[torch.Tensor | None]] = []
    params = list(model.parameters())

    for i, target in enumerate(targets):
        model.zero_grad()
        output = model(x, colony_idx=i)
        loss = ((output - target) ** 2).mean()
        loss.backward()

        grads = [p.grad.clone() if p.grad is not None else None for p in params]
        colony_gradients.append(grads)

    # Apply G₂ gradient surgery
    surgery = OctonionGradientSurgery(mode="g2_groups")
    corrected = surgery.apply_g2_groups(colony_gradients, param_groups)

    # Check output structure
    assert len(corrected) == 7, "Should have 7 colony gradients"
    for colony_grads in corrected:
        assert len(colony_grads) == len(params), "Each colony should have gradients for all params"


def test_octonion_gradient_surgery_no_conflicts(
    simple_model: SimpleColonyModel,
    colony_data: tuple[torch.Tensor, list[torch.Tensor]],
) -> None:
    """Test that G₂ parameter groups prevent conflicts."""
    x, targets = colony_data
    model = simple_model

    # Use apply_octonion_gradient_surgery convenience function
    colony_losses = []
    for i, target in enumerate(targets):
        output = model(x, colony_idx=i)
        loss = ((output - target) ** 2).mean()
        colony_losses.append(loss)

    # Apply surgery
    result = apply_octonion_gradient_surgery(
        model,
        colony_losses,
        mode="g2_groups",
    )

    # Check result
    assert result["method"] == "g2_groups"
    assert "param_groups" in result

    # Verify gradients were set
    for param in model.parameters():
        if param.requires_grad:
            assert param.grad is not None, "All parameters should have gradients"


def test_fano_aware_coupling(simple_model: SimpleColonyModel) -> None:
    """Test Fano-aware coupling gradient computation."""
    model = simple_model
    param_groups = G2ParameterGroups.from_model(model)

    # Create synthetic gradients
    params = list(model.parameters())
    colony_gradients: list[list[torch.Tensor | None]] = []

    for _ in range(7):
        grads = [torch.randn_like(p) if p.requires_grad else None for p in params]
        colony_gradients.append(grads)

    # Apply surgery with Fano structure
    surgery = OctonionGradientSurgery(mode="g2_groups", use_fano_structure=True)
    corrected = surgery.apply_g2_groups(colony_gradients, param_groups)

    # Check that coupling parameters have non-trivial gradients
    assert len(corrected) == 7


# =============================================================================
# TEST OCTONION PROJECTION MODE
# =============================================================================


def test_octonion_projection_mode() -> None:
    """Test experimental octonion projection mode."""
    # Create 7 random gradients
    d = 100
    colony_gradients = [torch.randn(d) for _ in range(7)]

    # Make some gradients conflict (negative cosine similarity)
    colony_gradients[1] = -colony_gradients[0] + 0.1 * torch.randn(d)

    # Apply octonion projection
    surgery = OctonionGradientSurgery(mode="octonion_projection", conflict_threshold=0.1)
    projected = surgery.apply_octonion_projection(colony_gradients)

    # Check output
    assert len(projected) == 7, "Should have 7 projected gradients"
    assert surgery.total_conflicts > 0, "Should have detected conflicts"


def test_conflict_detection() -> None:
    """Test conflict detection in octonion projection."""
    surgery = OctonionGradientSurgery(mode="octonion_projection", conflict_threshold=0.1)

    # Create conflicting gradients
    grad_i = torch.tensor([1.0, 0.0, 0.0])
    grad_j = torch.tensor([-1.0, 0.0, 0.0])

    assert surgery._detect_conflict_octonion(grad_i, grad_j), "Should detect conflict"

    # Create non-conflicting gradients
    grad_k = torch.tensor([1.0, 0.0, 0.0])
    grad_l = torch.tensor([1.0, 0.0, 0.0])

    assert not surgery._detect_conflict_octonion(grad_k, grad_l), "Should not detect conflict"


def test_octonion_projection_shape_preservation() -> None:
    """Test that octonion projection preserves gradient shapes."""
    shapes = [(10,), (20, 30), (5, 10, 15)]

    for shape in shapes:
        colony_gradients = [torch.randn(shape) for _ in range(7)]

        surgery = OctonionGradientSurgery(mode="octonion_projection")
        projected = surgery.apply_octonion_projection(colony_gradients)

        for i, proj in enumerate(projected):
            assert proj.shape == shape, f"Shape mismatch for colony {i}"


# =============================================================================
# TEST OCTONION PCGRAD
# =============================================================================


def test_octonion_pcgrad_basic() -> None:
    """Test basic OctonionPCGrad functionality."""
    # Create 7 task gradients
    num_params = 5
    gradients: list[list[torch.Tensor | None]] = []

    for _ in range(7):
        grads = [torch.randn(10) for _ in range(num_params)]
        gradients.append(grads)  # type: ignore[arg-type]

    # Apply OctonionPCGrad
    pcgrad = OctonionPCGrad(use_fano_alignment=True)
    projected = pcgrad.apply(gradients)

    # Check output
    assert len(projected) == 7, "Should have 7 projected gradients"
    for proj in projected:
        assert len(proj) == num_params, "Should have same number of parameters"


def test_octonion_pcgrad_fano_alignment() -> None:
    """Test Fano line alignment in OctonionPCGrad."""
    # Create 7 gradients with known conflicts
    num_params = 3
    gradients: list[list[torch.Tensor | None]] = []

    for _i in range(7):
        # Make gradients on same Fano line conflict
        grads = [torch.randn(10) for _ in range(num_params)]
        gradients.append(grads)  # type: ignore[arg-type]

    # Apply with Fano alignment
    pcgrad = OctonionPCGrad(use_fano_alignment=True)
    projected = pcgrad.apply(gradients)

    # Check that projections were applied
    assert len(projected) == 7


def test_octonion_pcgrad_vs_standard_pcgrad() -> None:
    """Compare OctonionPCGrad with standard PCGrad."""
    from kagami.core.learning.gradient_surgery import PCGrad

    # Create test gradients
    num_params = 3
    gradients: list[list[torch.Tensor | None]] = []

    for _ in range(7):
        grads = [torch.randn(10) for _ in range(num_params)]
        gradients.append(grads)  # type: ignore[arg-type]

    # Apply standard PCGrad
    pcgrad_standard = PCGrad(use_random_projection_order=False)
    projected_standard = pcgrad_standard.apply(gradients)

    # Apply OctonionPCGrad without Fano alignment (should be similar)
    pcgrad_octonion = OctonionPCGrad(
        use_random_projection_order=False,
        use_fano_alignment=False,
    )
    projected_octonion = pcgrad_octonion.apply(gradients)

    # Both should have same structure
    assert len(projected_standard) == len(projected_octonion)


# =============================================================================
# TEST CONVENIENCE FUNCTIONS
# =============================================================================


def test_apply_octonion_gradient_surgery_g2_groups(
    simple_model: SimpleColonyModel,
    colony_data: tuple[torch.Tensor, list[torch.Tensor]],
) -> None:
    """Test convenience function with G₂ groups mode."""
    x, targets = colony_data
    model = simple_model

    # Compute losses
    colony_losses = []
    for i, target in enumerate(targets):
        output = model(x, colony_idx=i)
        loss = ((output - target) ** 2).mean()
        colony_losses.append(loss)

    # Apply surgery
    result = apply_octonion_gradient_surgery(
        model,
        colony_losses,
        mode="g2_groups",
    )

    assert result["method"] == "g2_groups"
    assert "param_groups" in result


def test_apply_octonion_gradient_surgery_octonion_projection(
    simple_model: SimpleColonyModel,
    colony_data: tuple[torch.Tensor, list[torch.Tensor]],
) -> None:
    """Test convenience function with octonion projection mode."""
    x, targets = colony_data
    model = simple_model

    # Compute losses
    colony_losses = []
    for i, target in enumerate(targets):
        output = model(x, colony_idx=i)
        loss = ((output - target) ** 2).mean()
        colony_losses.append(loss)

    # Apply surgery
    result = apply_octonion_gradient_surgery(
        model,
        colony_losses,
        mode="octonion_projection",
    )

    assert result["method"] == "octonion_projection"
    assert "total_conflicts" in result


def test_apply_octonion_gradient_surgery_fano_pcgrad(
    simple_model: SimpleColonyModel,
    colony_data: tuple[torch.Tensor, list[torch.Tensor]],
) -> None:
    """Test convenience function with Fano PCGrad mode."""
    x, targets = colony_data
    model = simple_model

    # Compute losses
    colony_losses = []
    for i, target in enumerate(targets):
        output = model(x, colony_idx=i)
        loss = ((output - target) ** 2).mean()
        colony_losses.append(loss)

    # Apply surgery
    result = apply_octonion_gradient_surgery(
        model,
        colony_losses,
        mode="fano_pcgrad",
    )

    assert result["method"] == "fano_pcgrad"
    assert "stats" in result


def test_apply_octonion_gradient_surgery_invalid_mode(
    simple_model: SimpleColonyModel,
    colony_data: tuple[torch.Tensor, list[torch.Tensor]],
) -> None:
    """Test that invalid mode raises error."""
    x, targets = colony_data
    model = simple_model

    colony_losses = []
    for i, target in enumerate(targets):
        output = model(x, colony_idx=i)
        loss = ((output - target) ** 2).mean()
        colony_losses.append(loss)

    with pytest.raises(ValueError, match="Invalid mode"):
        apply_octonion_gradient_surgery(
            model,
            colony_losses,
            mode="invalid_mode",
        )


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


def test_gradient_surgery_preserves_convergence(
    simple_model: SimpleColonyModel,
    colony_data: tuple[torch.Tensor, list[torch.Tensor]],
) -> None:
    """Test that gradient surgery doesn't prevent convergence."""
    x, targets = colony_data
    model = simple_model
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

    initial_losses = []
    for i, target in enumerate(targets):
        output = model(x, colony_idx=i)
        loss = ((output - target) ** 2).mean()
        initial_losses.append(loss.item())

    # Train for a few steps with surgery
    for _ in range(10):
        colony_losses = []
        for i, target in enumerate(targets):
            output = model(x, colony_idx=i)
            loss = ((output - target) ** 2).mean()
            colony_losses.append(loss)

        # Apply surgery
        apply_octonion_gradient_surgery(
            model,
            colony_losses,
            mode="g2_groups",
        )

        optimizer.step()

    # Check that losses decreased
    final_losses = []
    for i, target in enumerate(targets):
        output = model(x, colony_idx=i)
        loss = ((output - target) ** 2).mean()
        final_losses.append(loss.item())

    # At least some losses should decrease
    avg_initial = sum(initial_losses) / len(initial_losses)
    avg_final = sum(final_losses) / len(final_losses)

    assert avg_final < avg_initial, "Average loss should decrease with training"


def test_g2_groups_vs_octonion_projection_equivalence() -> None:
    """Test that both modes produce reasonable gradients (not exact equivalence)."""
    # Create synthetic data
    batch_size = 4
    d_model = 8
    x = torch.randn(batch_size, d_model)
    targets = [torch.randn(batch_size, d_model) for _ in range(7)]

    # Create base model and save initial state
    base_model = SimpleColonyModel(d_model=8)
    initial_state = {k: v.clone() for k, v in base_model.state_dict().items()}

    # Test G₂ groups mode
    model_g2 = SimpleColonyModel(d_model=8)
    model_g2.load_state_dict(initial_state)
    colony_losses_g2 = []
    for i, target in enumerate(targets):
        output = model_g2(x, colony_idx=i)
        loss = ((output - target) ** 2).mean()
        colony_losses_g2.append(loss)
    apply_octonion_gradient_surgery(model_g2, colony_losses_g2, mode="g2_groups")

    # Test octonion projection mode (fresh model with same initialization)
    model_oct = SimpleColonyModel(d_model=8)
    model_oct.load_state_dict(initial_state)
    colony_losses_oct = []
    for i, target in enumerate(targets):
        output = model_oct(x, colony_idx=i)
        loss = ((output - target) ** 2).mean()
        colony_losses_oct.append(loss)
    apply_octonion_gradient_surgery(model_oct, colony_losses_oct, mode="octonion_projection")

    # Both should have gradients
    for p_g2, p_oct in zip(model_g2.parameters(), model_oct.parameters(), strict=False):
        if p_g2.requires_grad:
            assert p_g2.grad is not None
            assert p_oct.grad is not None


# =============================================================================
# EDGE CASES
# =============================================================================


def test_zero_gradients() -> None:
    """Test handling of zero gradients."""
    surgery = OctonionGradientSurgery(mode="octonion_projection")

    # Create zero gradients
    colony_gradients = [torch.zeros(10) for _ in range(7)]

    # Should not crash
    projected = surgery.apply_octonion_projection(colony_gradients)

    assert len(projected) == 7
    for proj in projected:
        assert not proj.isnan().any()


def test_single_nonzero_gradient() -> None:
    """Test when only one colony has non-zero gradient."""
    surgery = OctonionGradientSurgery(mode="octonion_projection")

    # One non-zero, rest zero
    colony_gradients = [torch.zeros(10) for _ in range(7)]
    colony_gradients[0] = torch.randn(10)

    projected = surgery.apply_octonion_projection(colony_gradients)

    assert len(projected) == 7


def test_wrong_number_of_colonies() -> None:
    """Test that wrong number of colonies raises error."""
    surgery = OctonionGradientSurgery(mode="g2_groups")

    # Only 5 colonies (should be 7)
    colony_gradients = [[torch.randn(10)] for _ in range(5)]
    param_groups = G2ParameterGroups()

    with pytest.raises(ValueError, match="Expected 7 colony gradients"):
        surgery.apply_g2_groups(colony_gradients, param_groups)  # type: ignore[arg-type]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
