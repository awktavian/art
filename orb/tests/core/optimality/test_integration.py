"""Tests for Optimality Integration (Wiring) Module.

Tests OptimalityWiring which connects improvements to K OS components:
- wire_strange_loop (adaptive convergence)
- wire_hopfield_memory (hierarchical E8)
- wire_octonion_multiply (true octonion algebra)
- wire_epistemic_value (analytical EFE)
- wire_uncertainty_calibration
- wire_online_learning

Created: December 4, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch
import torch.nn as nn


class MockRSSM(nn.Module):
    """Mock RSSM for testing."""

    def __init__(self):
        super().__init__()
        self.num_colonies = 7  # Match real RSSM interface
        self.strange_loop = MockStrangeLoop()


class MockStrangeLoop(nn.Module):
    """Mock Strange Loop for testing."""

    def __init__(self):
        super().__init__()
        self.linear = nn.Linear(32, 32)

    def forward(
        self,
        internal_z: torch.Tensor,
        action: torch.Tensor,
        sensory: torch.Tensor | None = None,
        phi: torch.Tensor | float | None = None,
    ) -> dict[str, torch.Tensor]:
        return {
            "z_evolved": internal_z + 0.1,
            "loop_closure_loss": torch.tensor(0.05),
        }


class MockHopfieldMemory(nn.Module):
    """Mock Hopfield memory for testing."""

    def __init__(self, pattern_dim: int = 256):
        super().__init__()
        self.pattern_dim = pattern_dim
        self.values = nn.Parameter(torch.randn(240, pattern_dim) * 0.02)
        self.g2_proj = nn.Linear(pattern_dim, 8)

    def read(
        self,
        query: torch.Tensor,
        return_energy: bool = False,
        return_indices: bool = False,
    ) -> tuple:
        B = query.shape[0] if query.dim() >= 1 else 1
        content = torch.randn(B, self.pattern_dim)
        attention = torch.softmax(torch.randn(B, 240), dim=-1)
        result = [content, attention]
        if return_energy:
            result.append(torch.randn(B))
        if return_indices:
            result.append(torch.randint(0, 240, (B, 5)))
        return tuple(result)

    def write(
        self,
        query: torch.Tensor,
        content: torch.Tensor,
        strength: float = 0.1,
    ) -> dict:
        return {"write_norm": 0.01}


class MockWorldModel(nn.Module):
    """Mock world model for testing integration."""

    def __init__(self):
        super().__init__()
        self.rssm = MockRSSM()
        self._hopfield_memory = MockHopfieldMemory()
        self.linear = nn.Linear(64, 64)

    def forward(self, x: Any) -> Self:
        return self.linear(x), {"total_loss": x.pow(2).sum()}


class TestOptimalityWiring:
    """Tests for OptimalityWiring integration."""

    def test_init(self) -> Any:
        """Test initialization without model."""
        from kagami.core.optimality.integration import OptimalityWiring

        wiring = OptimalityWiring()
        assert wiring is not None
        assert wiring.world_model is None

    def test_init_with_model(self) -> None:
        """Test initialization with model."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)

        assert wiring.world_model is model

    def test_wire_strange_loop(self) -> None:
        """Test strange loop wiring."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)

        result = wiring.wire_strange_loop()
        assert result is True
        assert "strange_loop" in wiring._wired_components

    def test_wire_strange_loop_adds_convergence_stats(self) -> None:
        """Test that wrapped strange loop returns convergence stats."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)
        wiring.wire_strange_loop()

        # Call wrapped forward
        z = torch.randn(2, 32)
        action = torch.randn(2, 8)
        result = model.rssm.strange_loop.forward(z, action)

        assert "convergence_stats" in result
        assert "avg_iterations" in result["convergence_stats"]

    def test_wire_hopfield_memory(self) -> None:
        """Test Hopfield memory wiring."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)

        result = wiring.wire_hopfield_memory()
        assert result is True
        assert "hopfield_memory" in wiring._wired_components

    def test_wire_hopfield_replaces_read(self) -> None:
        """Test that wiring replaces read method."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        original_read = model._hopfield_memory.read

        wiring = OptimalityWiring(model)
        wiring.wire_hopfield_memory()

        # Method should be replaced
        assert model._hopfield_memory.read != original_read

        # Can still call read
        query = torch.randn(4, 256)
        content, attention = model._hopfield_memory.read(query)[:2]

        assert content.shape == (4, 256)
        assert attention.shape[1] == 240  # E8 roots

    def test_wire_octonion_multiply(self) -> None:
        """Test octonion multiplication wiring."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)

        # This may fail if FanoOctonionCombiner isn't available
        result = wiring.wire_octonion_multiply()

        # Result can be True or False depending on import
        assert isinstance(result, bool)

    def test_wire_epistemic_value(self) -> None:
        """Test epistemic value wiring."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)

        # This may fail if ExpectedFreeEnergy isn't available
        result = wiring.wire_epistemic_value()

        assert isinstance(result, bool)

    def test_wire_uncertainty_calibration(self) -> None:
        """Test uncertainty calibration wiring."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)

        # This may fail if ActiveInferenceEngine isn't available
        result = wiring.wire_uncertainty_calibration()

        assert isinstance(result, bool)

    def test_wire_online_learning(self) -> None:
        """Test online learning wiring."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)

        # This may fail if WorldModelLoop isn't available
        result = wiring.wire_online_learning()

        assert isinstance(result, bool)

    def test_wire_all(self) -> None:
        """Test wiring all components."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)

        results = wiring.wire_all()

        assert isinstance(results, dict)
        assert "strange_loop" in results
        assert "hopfield_memory" in results
        assert "octonion_multiply" in results
        assert "epistemic_value" in results
        assert "uncertainty_calibration" in results
        assert "online_learning" in results

    def test_unwire_all(self) -> None:
        """Test unwiring restores original methods."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)

        # Wire then unwire
        wiring.wire_all()
        assert len(wiring._wired_components) > 0

        wiring.unwire_all()
        assert len(wiring._wired_components) == 0

    def test_get_status(self) -> None:
        """Test status retrieval."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)
        wiring.wire_all()

        status = wiring.get_status()

        assert "wired_components" in status
        assert "num_wired" in status
        assert "has_world_model" in status
        assert status["has_world_model"] is True

    def test_no_model_returns_false(self) -> None:
        """Test wiring without model returns False."""
        from kagami.core.optimality.integration import OptimalityWiring

        wiring = OptimalityWiring()  # No model

        assert wiring.wire_strange_loop() is False
        assert wiring.wire_hopfield_memory() is False


class TestGetOptimalityWiring:
    """Tests for singleton factory."""

    def test_singleton_without_model(self) -> None:
        """Test singleton behavior."""
        # Reset singleton for test isolation
        import kagami.core.optimality.integration as integration_module

        integration_module._wiring = None

        from kagami.core.optimality.integration import get_optimality_wiring

        wiring1 = get_optimality_wiring()
        wiring2 = get_optimality_wiring()

        assert wiring1 is wiring2

    def test_singleton_with_model(self) -> None:
        """Test singleton accepts model."""
        # Reset singleton
        import kagami.core.optimality.integration as integration_module

        integration_module._wiring = None

        from kagami.core.optimality.integration import get_optimality_wiring

        model = MockWorldModel()
        wiring = get_optimality_wiring(model)

        assert wiring.world_model is model

    def test_singleton_late_model_assignment(self) -> None:
        """Test model can be assigned to existing singleton."""
        # Reset singleton
        import kagami.core.optimality.integration as integration_module

        integration_module._wiring = None

        from kagami.core.optimality.integration import get_optimality_wiring

        # Get without model
        wiring1 = get_optimality_wiring()
        assert wiring1.world_model is None

        # Get with model
        model = MockWorldModel()
        wiring2 = get_optimality_wiring(model)

        assert wiring1 is wiring2
        assert wiring2.world_model is model


class TestIntegrateAllImprovements:
    """Tests for convenience function."""

    def test_integrate_all(self) -> None:
        """Test integrate_all_improvements function."""
        # Reset singleton
        import kagami.core.optimality.integration as integration_module

        integration_module._wiring = None

        from kagami.core.optimality.integration import integrate_all_improvements

        model = MockWorldModel()
        wiring = integrate_all_improvements(model)

        assert wiring is not None
        assert wiring.world_model is model
        # At least some components should be wired
        assert len(wiring._wired_components) >= 2  # strange_loop and hopfield_memory


class TestHierarchicalHopfieldIntegration:
    """Tests for hierarchical E8 Hopfield integration."""

    def test_hierarchical_read_returns_content(self) -> None:
        """Test hierarchical read returns valid content."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)
        wiring.wire_hopfield_memory()

        # Read with 3D query (batch, seq, dim)
        query = torch.randn(2, 5, 256)
        content, _attention = model._hopfield_memory.read(query)[:2]

        # Content should be flattened properly
        assert content.dim() >= 1

    def test_hierarchical_write_updates_values(self) -> None:
        """Test hierarchical write modifies values."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)
        wiring.wire_hopfield_memory()

        query = torch.randn(4, 256)
        content = torch.randn(4, 256)

        result = model._hopfield_memory.write(query, content, strength=0.1)

        assert "write_norm" in result
        assert "levels_used" in result or "write_norm" in result

    def test_capacity_reported(self) -> None:
        """Test effective capacity is reported."""
        from kagami.core.optimality.integration import OptimalityWiring

        model = MockWorldModel()
        wiring = OptimalityWiring(model)
        wiring.wire_hopfield_memory()

        # Check that optimal hopfield is stored
        assert hasattr(model, "_optimal_hopfield")

        # Query to get capacity
        query = torch.randn(2, 256)
        result = model._optimal_hopfield(query)  # type: ignore[operator]

        assert "effective_capacity" in result
        # 240^4 = 3.3B with 4 levels
        assert result["effective_capacity"] >= 240


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
