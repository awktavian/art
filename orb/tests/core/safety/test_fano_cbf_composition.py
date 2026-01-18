"""Tests for Fano CBF composition module.

CREATED: December 14, 2025
COVERAGE TARGET: >90%

Tests verify:
1. Shared resource barrier computation
2. Pairwise colony barrier composition
3. Full Fano line checking
4. Integration with DecentralizedCBF
5. Integration with FanoActionRouter
6. Edge cases (NaN, missing states, violations)
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch

from kagami.core.safety.fano_cbf_composition import (
    DEFAULT_RESOURCE_THRESHOLDS,
    FANO_LINES_0IDX,
    CompositionBarrierResult,
    FanoCompositionChecker,
    check_fano_routing_safety,
    compose_fano_barriers,
    compose_fano_barriers_detailed,
    compute_shared_resource_barrier,
)

# =============================================================================
# SHARED RESOURCE BARRIER TESTS
# =============================================================================


class TestSharedResourceBarrier:
    """Test shared resource barrier computation."""

    def test_safe_resources(self):
        """Test that low utilization yields positive barrier."""
        shared_resources = {
            "memory": 0.5,  # 50% utilization
            "compute": 0.6,  # 60% utilization
        }

        h_shared, per_resource = compute_shared_resource_barrier(shared_resources)

        # Should be safe (positive barrier)
        assert h_shared > 0.0
        assert all(h > 0.0 for h in per_resource.values())

    def test_unsafe_resources(self):
        """Test that high utilization yields negative barrier."""
        shared_resources = {
            "memory": 0.95,  # 95% > 85% threshold
        }

        h_shared, per_resource = compute_shared_resource_barrier(shared_resources)

        # Should be unsafe (negative barrier)
        assert h_shared < 0.0
        assert per_resource["memory"] < 0.0

    def test_mixed_resources(self):
        """Test mixed safe/unsafe resources returns minimum."""
        shared_resources = {
            "memory": 0.5,  # Safe
            "compute": 0.95,  # Unsafe
        }

        h_shared, per_resource = compute_shared_resource_barrier(shared_resources)

        # Overall barrier should be minimum (unsafe)
        assert h_shared < 0.0
        assert h_shared == min(per_resource.values())
        assert per_resource["memory"] > 0.0
        assert per_resource["compute"] < 0.0

    def test_custom_thresholds(self):
        """Test custom resource thresholds."""
        shared_resources = {"memory": 0.7}

        # Default threshold: 0.85 → safe
        h_default, _ = compute_shared_resource_barrier(shared_resources)
        assert h_default > 0.0

        # Custom threshold: 0.6 → unsafe
        custom_thresholds = {"memory": 0.6}
        h_custom, _ = compute_shared_resource_barrier(
            shared_resources, thresholds=custom_thresholds
        )
        assert h_custom < 0.0

    def test_empty_resources(self):
        """Test empty resource dict returns fully safe."""
        h_shared, per_resource = compute_shared_resource_barrier({})

        assert h_shared == 1.0
        assert len(per_resource) == 0

    def test_unknown_resource_uses_default(self):
        """Test unknown resource type uses default threshold."""
        shared_resources = {"custom_resource": 0.9}

        _h_shared, per_resource = compute_shared_resource_barrier(shared_resources)

        # Should use default threshold (0.85)
        assert "custom_resource" in per_resource
        # 0.85 - 0.9 = -0.05 (unsafe)
        assert per_resource["custom_resource"] < 0.0


# =============================================================================
# BARRIER COMPOSITION TESTS
# =============================================================================


class TestComposeBarriers:
    """Test barrier composition function."""

    def test_both_safe_returns_minimum(self):
        """Test that composition returns minimum of safe barriers."""
        h_AB = compose_fano_barriers(
            h_A=0.3,
            h_B=0.2,
            shared_resources={"memory": 0.5},
            fano_line=0,
        )

        # Should return minimum
        # min(0.3, 0.2, (0.85 - 0.5)) = min(0.3, 0.2, 0.35) = 0.2
        assert h_AB == 0.2

    def test_one_unsafe_returns_negative(self):
        """Test that one unsafe colony makes composition unsafe."""
        h_AB = compose_fano_barriers(
            h_A=-0.1,  # Unsafe
            h_B=0.5,  # Safe
            shared_resources={"memory": 0.5},
            fano_line=0,
        )

        # Should return negative (colony A unsafe)
        assert h_AB < 0.0
        assert h_AB == -0.1

    def test_resource_violation_dominates(self):
        """Test that resource violation makes composition unsafe."""
        h_AB = compose_fano_barriers(
            h_A=0.3,  # Safe
            h_B=0.2,  # Safe
            shared_resources={"memory": 0.95},  # Unsafe: 0.95 > 0.85
            fano_line=0,
        )

        # Should be unsafe due to memory
        assert h_AB < 0.0

    def test_all_fano_lines_valid(self):
        """Test composition works for all 7 Fano lines."""
        for line_id in range(7):
            h_AB = compose_fano_barriers(
                h_A=0.3,
                h_B=0.2,
                shared_resources={"memory": 0.5},
                fano_line=line_id,
            )
            # Should succeed without error
            assert isinstance(h_AB, float)

    def test_invalid_fano_line_raises(self):
        """Test invalid fano_line raises ValueError."""
        with pytest.raises(ValueError, match="fano_line must be 0-6"):
            compose_fano_barriers(
                h_A=0.3,
                h_B=0.2,
                shared_resources={"memory": 0.5},
                fano_line=7,  # Invalid
            )

    def test_detailed_composition(self):
        """Test detailed composition returns full diagnostics."""
        result = compose_fano_barriers_detailed(
            h_A=0.3,
            h_B=0.2,
            shared_resources={"memory": 0.5, "compute": 0.7},
            fano_line=0,
        )

        assert isinstance(result, CompositionBarrierResult)
        assert result.h_A == 0.3
        assert result.h_B == 0.2
        assert result.h_composed == 0.2  # min
        assert result.is_safe is True
        assert result.limiting_factor == "colony_B"
        assert result.fano_line == 0
        assert "per_resource_barriers" in result.metadata

    def test_detailed_resource_limiting(self):
        """Test detailed result identifies resource as limiting factor."""
        result = compose_fano_barriers_detailed(
            h_A=0.5,
            h_B=0.4,
            shared_resources={"memory": 0.9},  # This will limit
            fano_line=0,
        )

        # h_shared = 0.85 - 0.9 = -0.05
        assert result.h_shared < 0.0
        assert result.limiting_factor.startswith("resource_")
        assert result.is_safe is False


# =============================================================================
# FANO COMPOSITION CHECKER TESTS
# =============================================================================


class TestFanoCompositionChecker:
    """Test FanoCompositionChecker class."""

    def test_checker_initialization(self):
        """Test checker can be initialized."""
        checker = FanoCompositionChecker()
        assert checker.cbf_registry is None
        assert checker.resource_thresholds == DEFAULT_RESOURCE_THRESHOLDS

    def test_check_line_with_precomputed_barriers(self):
        """Test checking a line with pre-computed barriers."""
        checker = FanoCompositionChecker()

        # Line 0: {0, 1, 2} — Spark × Forge = Flow (0-indexed)
        colony_barriers = {
            0: 0.3,  # Spark safe
            1: 0.2,  # Forge safe
            2: 0.4,  # Flow safe
        }

        h_line = checker.check_line(
            line_id=0,
            colony_states={},  # Not needed with pre-computed barriers
            shared_resources={"memory": 0.5},
            colony_barriers=colony_barriers,
        )

        # Should be safe (all positive or zero)
        # min(0.3, 0.2, (0.85-0.5), 0.4) = min(0.3, 0.2, 0.35, 0.4) = 0.2
        assert h_line >= 0.0
        assert h_line == pytest.approx(0.2, abs=0.01)

    def test_check_line_with_cbf_registry(self):
        """Test checking a line with DecentralizedCBF."""
        from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

        cbf = FanoDecentralizedCBF(state_dim=4, hidden_dim=32)
        checker = FanoCompositionChecker(cbf_registry=cbf)

        # Create safe states (low risk)
        colony_states = torch.randn(1, 7, 4) * 0.1  # [B=1, 7, state_dim=4]

        h_line = checker.check_line(
            line_id=0,
            colony_states=colony_states,
            shared_resources={"memory": 0.5},
        )

        # Should compute without error
        assert isinstance(h_line, float)

    def test_check_line_missing_data_raises(self):
        """Test that missing required data raises ValueError."""
        checker = FanoCompositionChecker()  # No CBF registry

        with pytest.raises(
            ValueError, match="Either colony_barriers or cbf_registry must be provided"
        ):
            checker.check_line(
                line_id=0,
                colony_states={},  # No states
                shared_resources={"memory": 0.5},
                colony_barriers=None,  # No barriers
            )

    def test_check_all_lines(self):
        """Test checking all 7 Fano lines."""
        checker = FanoCompositionChecker()

        # All colonies safe
        colony_barriers = dict.fromkeys(range(7), 0.3)

        results = checker.check_all_lines(
            colony_states={},
            shared_resources={"memory": 0.5},
            colony_barriers=colony_barriers,
        )

        assert len(results) == 7
        for line_id, h_line in results.items():
            assert 0 <= line_id < 7
            assert h_line > 0.0  # All safe

    def test_get_unsafe_lines(self):
        """Test getting list of unsafe lines."""
        checker = FanoCompositionChecker()

        # Make colonies 0, 1 unsafe
        colony_barriers = {
            0: -0.1,  # Unsafe
            1: -0.05,  # Unsafe
            2: 0.3,
            3: 0.3,
            4: 0.3,
            5: 0.3,
            6: 0.3,
        }

        unsafe_lines = checker.get_unsafe_lines(
            colony_states={},
            shared_resources={"memory": 0.5},
            colony_barriers=colony_barriers,
        )

        # Line 0: {0, 1, 3} should be unsafe (0 and 1 are unsafe)
        # Line 1: {0, 2, 4} should be unsafe (0 is unsafe)
        # Line 2: {0, 5, 6} should be unsafe (0 is unsafe)
        # Line 3: {1, 2, 5} should be unsafe (1 is unsafe)
        # Line 4: {1, 4, 6} should be unsafe (1 is unsafe)

        assert len(unsafe_lines) > 0
        for _line_id, h_line in unsafe_lines:
            assert h_line < 0.0

    def test_verify_compositional_safety_all_safe(self):
        """Test comprehensive verification when all safe."""
        checker = FanoCompositionChecker()

        colony_barriers = dict.fromkeys(range(7), 0.3)

        verification = checker.verify_compositional_safety(
            colony_states={},
            shared_resources={"memory": 0.5},
            colony_barriers=colony_barriers,
        )

        assert verification["all_safe"] is True
        assert len(verification["unsafe_lines"]) == 0
        assert verification["num_violations"] == 0
        assert verification["min_barrier"] > 0.0

    def test_verify_compositional_safety_with_violations(self):
        """Test comprehensive verification with violations."""
        checker = FanoCompositionChecker()

        # Colony 0 (Spark) unsafe
        colony_barriers = {
            0: -0.2,  # Unsafe
            1: 0.3,
            2: 0.3,
            3: 0.3,
            4: 0.3,
            5: 0.3,
            6: 0.3,
        }

        verification = checker.verify_compositional_safety(
            colony_states={},
            shared_resources={"memory": 0.5},
            colony_barriers=colony_barriers,
        )

        assert verification["all_safe"] is False
        assert len(verification["unsafe_lines"]) > 0
        assert verification["num_violations"] > 0
        assert verification["min_barrier"] < 0.0

        # Check violation details
        for violation in verification["violations"]:
            assert "line_id" in violation
            assert "colonies" in violation
            assert "barrier" in violation
            assert 0 in violation["colonies"]  # Colony 0 involved

    def test_check_line_with_dict_states(self):
        """Test check_line accepts dict of colony states."""
        from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

        cbf = FanoDecentralizedCBF(state_dim=4)
        checker = FanoCompositionChecker(cbf_registry=cbf)

        # Dict format
        colony_states = {i: torch.randn(4) * 0.1 for i in range(7)}

        h_line = checker.check_line(
            line_id=0,
            colony_states=colony_states,
            shared_resources={"memory": 0.5},
        )

        assert isinstance(h_line, float)

    def test_check_line_with_tensor_states(self):
        """Test check_line accepts tensor colony states."""
        from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

        cbf = FanoDecentralizedCBF(state_dim=4)
        checker = FanoCompositionChecker(cbf_registry=cbf)

        # Tensor format [7, state_dim]
        colony_states = torch.randn(7, 4) * 0.1

        h_line = checker.check_line(
            line_id=0,
            colony_states=colony_states,
            shared_resources={"memory": 0.5},
        )

        assert isinstance(h_line, float)

    def test_check_line_handles_missing_colony_in_dict(self):
        """Test check_line handles missing colonies in dict gracefully."""
        from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

        cbf = FanoDecentralizedCBF(state_dim=4)
        checker = FanoCompositionChecker(cbf_registry=cbf)

        # Only provide some colonies
        colony_states = {
            0: torch.randn(4) * 0.1,
            1: torch.randn(4) * 0.1,
            # Missing 2, 3, 4, 5, 6
        }

        # Should handle gracefully (use zeros for missing)
        h_line = checker.check_line(
            line_id=0,
            colony_states=colony_states,
            shared_resources={"memory": 0.5},
        )

        assert isinstance(h_line, float)


# =============================================================================
# FANO ACTION ROUTER INTEGRATION TESTS
# =============================================================================


class TestFanoRouterIntegration:
    """Test integration with FanoActionRouter."""

    def test_single_colony_routing_safe(self):
        """Test safety check for single colony routing."""
        from kagami.core.unified_agents.fano_action_router import (
            ActionMode,
            ColonyAction,
            RoutingResult,
        )

        routing_result = RoutingResult(
            mode=ActionMode.SINGLE,
            actions=[
                ColonyAction(
                    colony_idx=0,
                    colony_name="spark",
                    action="test",
                    params={},
                    weight=1.0,
                    is_primary=True,
                )
            ],
            complexity=0.2,
        )

        from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

        cbf = FanoDecentralizedCBF(state_dim=4)
        colony_states = torch.randn(7, 4) * 0.1  # Safe states

        _is_safe, info = check_fano_routing_safety(
            routing_result=routing_result,
            colony_states=colony_states,
            shared_resources={"memory": 0.5},
            cbf_registry=cbf,
        )

        assert "h_colony" in info
        assert "colony_idx" in info

    def test_fano_line_routing_safe(self):
        """Test safety check for Fano line routing."""
        from kagami.core.unified_agents.fano_action_router import (
            ActionMode,
            ColonyAction,
            RoutingResult,
        )

        routing_result = RoutingResult(
            mode=ActionMode.FANO_LINE,
            actions=[
                ColonyAction(0, "spark", "test", {}, 0.5, True, "source"),
                ColonyAction(1, "forge", "test", {}, 0.3, False, "partner"),
                ColonyAction(2, "flow", "test", {}, 0.2, False, "result"),
            ],
            complexity=0.5,
            fano_line=(0, 1, 2),  # Line 0: Spark × Forge = Flow (0-indexed)
        )

        from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

        cbf = FanoDecentralizedCBF(state_dim=4)
        colony_states = torch.randn(7, 4) * 0.1

        _is_safe, info = check_fano_routing_safety(
            routing_result=routing_result,
            colony_states=colony_states,
            shared_resources={"memory": 0.5},
            cbf_registry=cbf,
        )

        assert "h_line" in info
        assert "line_id" in info
        assert info["line_id"] == 0

    def test_all_colonies_routing_safe(self):
        """Test safety check for all colonies routing."""
        from kagami.core.unified_agents.fano_action_router import (
            ActionMode,
            ColonyAction,
            RoutingResult,
        )

        routing_result = RoutingResult(
            mode=ActionMode.ALL_COLONIES,
            actions=[ColonyAction(i, f"colony_{i}", "test", {}, 0.14, i == 0) for i in range(7)],
            complexity=0.8,
        )

        from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

        cbf = FanoDecentralizedCBF(state_dim=4)
        colony_states = torch.randn(7, 4) * 0.1

        _is_safe, info = check_fano_routing_safety(
            routing_result=routing_result,
            colony_states=colony_states,
            shared_resources={"memory": 0.5},
            cbf_registry=cbf,
        )

        assert "all_safe" in info
        assert "per_line_barriers" in info


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_nan_barriers_handled(self):
        """Test NaN barrier values are handled properly."""
        # Composition with NaN should propagate NaN
        h_AB = compose_fano_barriers(
            h_A=float("nan"),
            h_B=0.3,
            shared_resources={"memory": 0.5},
            fano_line=0,
        )

        import math

        assert math.isnan(h_AB)

    def test_extreme_barrier_values(self):
        """Test very large/small barrier values."""
        h_AB = compose_fano_barriers(
            h_A=1e6,  # Very safe
            h_B=-1e6,  # Very unsafe
            shared_resources={"memory": 0.5},
            fano_line=0,
        )

        # Should return minimum (very unsafe)
        assert h_AB < 0.0

    def test_zero_barrier_threshold(self):
        """Test behavior at exactly zero barrier."""
        h_AB = compose_fano_barriers(
            h_A=0.0,  # Exactly on boundary
            h_B=0.3,
            shared_resources={"memory": 0.5},
            fano_line=0,
        )

        # Should be zero (on boundary)
        assert h_AB == 0.0

    def test_all_resources_at_threshold(self):
        """Test all resources exactly at threshold."""
        shared_resources = {
            "memory": 0.85,  # Exactly at threshold
            "compute": 0.90,  # Exactly at threshold
        }

        h_shared, _ = compute_shared_resource_barrier(shared_resources)

        # Should be zero (on boundary)
        assert h_shared == 0.0

    def test_empty_fano_line_dict(self):
        """Test checker with no colonies on a line (shouldn't happen but handle)."""
        checker = FanoCompositionChecker()

        # All colonies unsafe
        colony_barriers = dict.fromkeys(range(7), -0.5)

        # Should still work for all lines
        results = checker.check_all_lines(
            colony_states={},
            colony_barriers=colony_barriers,
        )

        assert len(results) == 7

    def test_batch_dimension_handling(self):
        """Test handling of batch dimensions in colony states."""
        from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF

        cbf = FanoDecentralizedCBF(state_dim=4)
        checker = FanoCompositionChecker(cbf_registry=cbf)

        # Batch of states [B=4, 7, state_dim=4]
        colony_states = torch.randn(4, 7, 4) * 0.1

        # Should handle first batch element
        h_line = checker.check_line(
            line_id=0,
            colony_states=colony_states,
            shared_resources={"memory": 0.5},
        )

        assert isinstance(h_line, float)


# =============================================================================
# INTEGRATION EXAMPLE TEST
# =============================================================================


class TestIntegrationExample:
    """Test realistic integration scenario."""

    def test_full_workflow(self):
        """Test complete workflow: routing → safety check → execution."""
        from kagami.core.safety.decentralized_cbf import FanoDecentralizedCBF
        from kagami.core.unified_agents.fano_action_router import create_fano_router

        # 1. Create router and CBF
        router = create_fano_router()
        cbf = FanoDecentralizedCBF(state_dim=4)

        # 2. Route an action
        routing_result = router.route(
            action="build.feature",
            params={"feature": "test"},
            complexity=0.5,  # Fano line mode
        )

        # 3. Get current colony states
        colony_states = torch.randn(7, 4) * 0.1  # Low risk states

        # 4. Check routing safety
        is_safe, info = check_fano_routing_safety(
            routing_result=routing_result,
            colony_states=colony_states,
            shared_resources={
                "memory": 0.6,
                "compute": 0.7,
            },
            cbf_registry=cbf,
        )

        # 5. Verify result structure
        assert isinstance(is_safe, bool)
        assert isinstance(info, dict)

        # If safe, execution would proceed
        # If unsafe, would need to adjust or reject


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
