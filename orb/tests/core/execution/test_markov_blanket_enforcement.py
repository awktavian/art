"""Test Markov blanket discipline enforcement.

Validates three invariants:
1. NO INSTANTANEOUS FEEDBACK: a_t depends on μ_t, but μ_t+1 depends on a_t-1
2. BLANKET CLOSURE: μ not directly observable from η
3. NESTED HIERARCHY: Organism.blanket ⊃ Colony.blanket ⊃ Agent.blanket

References:
- Friston (2013): Active Inference and Markov Blankets
- CLAUDE.md: "Action isolation - no instantaneous feedback"

Created: December 14, 2025 (Forge)
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch

from kagami.core.execution.markov_blanket import (
    OrganismMarkovBlanket,
    ValidationResult,
    BlanketViolation,
    SensoryState,
    ActiveState,
)


class TestMarkovBlanketValidation:
    """Test Markov blanket validation logic."""

    def test_blanket_initialization(self):
        """Test blanket initializes with correct level."""
        blanket = OrganismMarkovBlanket(level="organism")
        assert blanket.level == "organism"
        assert blanket.parent_blanket is None
        assert blanket._validation_enabled is True

    def test_blanket_hierarchy_initialization(self):
        """Test blanket hierarchy (organism → colony → agent)."""
        organism_blanket = OrganismMarkovBlanket(level="organism")
        colony_blanket = OrganismMarkovBlanket(level="colony", parent_blanket=organism_blanket)
        agent_blanket = OrganismMarkovBlanket(level="agent", parent_blanket=colony_blanket)

        assert organism_blanket.parent_blanket is None
        assert colony_blanket.parent_blanket is organism_blanket
        assert agent_blanket.parent_blanket is colony_blanket

    def test_validate_empty_blanket(self):
        """Test validation with no state (should pass)."""
        blanket = OrganismMarkovBlanket(level="organism")
        result = blanket.validate_blanket_discipline()

        assert result.valid is True
        assert len(result.violations) == 0

    def test_internal_state_update(self):
        """Test internal state (μ) update."""
        blanket = OrganismMarkovBlanket(level="organism")
        mu = torch.randn(256)

        blanket.update_internal_state(mu)

        assert blanket._mu is not None
        assert torch.equal(blanket._mu, mu)

    def test_action_isolation_no_feedback(self):
        """Test action isolation: different actions should pass."""
        blanket = OrganismMarkovBlanket(level="organism")

        action1 = torch.randn(8)
        action2 = torch.randn(8)

        # First action
        assert blanket.check_action_isolation(action1) is True

        # Different second action (should pass)
        assert blanket.check_action_isolation(action2) is True
        assert blanket._action_feedback_detected is False

    def test_action_isolation_feedback_detected(self):
        """Test action isolation: same action should fail (instantaneous feedback)."""
        blanket = OrganismMarkovBlanket(level="organism")

        action = torch.randn(8)

        # Create active state with this action
        blanket._current_active = ActiveState(e8_action=action)

        # First check (establishes previous)
        blanket.check_action_isolation(action)

        # Same action again (should detect feedback)
        blanket._current_active = ActiveState(e8_action=action)
        result = blanket.check_action_isolation(action)

        assert result is False
        assert blanket._action_feedback_detected is True

    def test_validate_with_feedback_violation(self):
        """Test validation detects instantaneous feedback violation."""
        blanket = OrganismMarkovBlanket(level="organism")
        blanket._action_feedback_detected = True

        result = blanket.validate_blanket_discipline()

        assert result.valid is False
        assert len(result.error_violations) == 1
        assert result.error_violations[0].violation_type == "instantaneous_feedback"

    def test_blanket_closure_check(self):
        """Test blanket closure: μ should not appear directly in sensory."""
        blanket = OrganismMarkovBlanket(level="organism")

        # Set internal state
        mu = torch.randn(256)
        blanket.update_internal_state(mu)

        # Set sensory state with DIFFERENT observation
        sensory = SensoryState()
        sensory.hal_observation = torch.randn(512)
        blanket._current_sensory = sensory

        result = blanket.validate_blanket_discipline()

        # Should pass - μ not directly in sensory
        assert result.valid is True

    def test_blanket_closure_violation_warning(self):
        """Test blanket closure warning when μ appears in sensory."""
        blanket = OrganismMarkovBlanket(level="organism")

        # Set internal state
        mu = torch.randn(256)
        blanket.update_internal_state(mu)

        # Set sensory state with SAME data (leaked internal state)
        sensory = SensoryState()
        sensory.hal_observation = torch.zeros(512)
        sensory.hal_observation[:256] = mu  # Direct leak
        blanket._current_sensory = sensory

        result = blanket.validate_blanket_discipline()

        # Should warn (not error, as this is hard to enforce strictly)
        assert len(result.warning_violations) == 1
        assert result.warning_violations[0].violation_type == "closure_broken"

    def test_hierarchy_containment_root(self):
        """Test hierarchy containment for root blanket (organism)."""
        blanket = OrganismMarkovBlanket(level="organism")

        # Root blanket always passes containment
        assert blanket._check_hierarchy_containment() is True

    def test_hierarchy_containment_child(self):
        """Test hierarchy containment for child blanket."""
        organism_blanket = OrganismMarkovBlanket(level="organism")
        colony_blanket = OrganismMarkovBlanket(level="colony", parent_blanket=organism_blanket)

        # Set parent sensory state
        parent_sensory = SensoryState()
        parent_sensory.hal_observation = torch.randn(512)
        organism_blanket._current_sensory = parent_sensory

        # Set child sensory state (smaller)
        child_sensory = SensoryState()
        child_sensory.hal_observation = torch.randn(256)
        colony_blanket._current_sensory = child_sensory

        # Should pass - child observation is smaller
        assert colony_blanket._check_hierarchy_containment() is True

    def test_hierarchy_violation_child_larger(self):
        """Test hierarchy violation when child observation larger than parent."""
        organism_blanket = OrganismMarkovBlanket(level="organism")
        colony_blanket = OrganismMarkovBlanket(level="colony", parent_blanket=organism_blanket)

        # Set parent sensory state (small)
        parent_sensory = SensoryState()
        parent_sensory.hal_observation = torch.randn(128)
        organism_blanket._current_sensory = parent_sensory

        # Set child sensory state (LARGER than parent - violation)
        child_sensory = SensoryState()
        child_sensory.hal_observation = torch.randn(512)
        colony_blanket._current_sensory = child_sensory

        # Should fail - child observation larger
        assert colony_blanket._check_hierarchy_containment() is False

    def test_hierarchy_violation_in_validation(self):
        """Test hierarchy violation detected in full validation."""
        organism_blanket = OrganismMarkovBlanket(level="organism")
        colony_blanket = OrganismMarkovBlanket(level="colony", parent_blanket=organism_blanket)

        # Create hierarchy violation
        parent_sensory = SensoryState()
        parent_sensory.hal_observation = torch.randn(128)
        organism_blanket._current_sensory = parent_sensory

        child_sensory = SensoryState()
        child_sensory.hal_observation = torch.randn(512)
        colony_blanket._current_sensory = child_sensory

        result = colony_blanket.validate_blanket_discipline()

        # Should fail validation
        assert result.valid is False
        assert len(result.error_violations) == 1
        assert result.error_violations[0].violation_type == "hierarchy_broken"

    def test_validation_disabled(self):
        """Test validation can be disabled."""
        blanket = OrganismMarkovBlanket(level="organism")

        # Create a violation
        blanket._action_feedback_detected = True

        # Disable validation
        blanket.set_validation_enabled(False)

        result = blanket.validate_blanket_discipline()

        # Should pass even with violation
        assert result.valid is True
        assert len(result.violations) == 0

    def test_validation_enabled_by_default(self):
        """Test validation is enabled by default."""
        blanket = OrganismMarkovBlanket(level="organism")
        assert blanket._validation_enabled is True


class TestMarkovBlanketNestedHierarchy:
    """Test nested Markov blanket hierarchy (Organism ⊃ Colony ⊃ Agent)."""

    def test_three_level_hierarchy(self):
        """Test complete three-level hierarchy."""
        organism = OrganismMarkovBlanket(level="organism")
        colony = OrganismMarkovBlanket(level="colony", parent_blanket=organism)
        agent = OrganismMarkovBlanket(level="agent", parent_blanket=colony)

        # Verify chain
        assert agent.parent_blanket is colony
        assert colony.parent_blanket is organism
        assert organism.parent_blanket is None

    def test_hierarchy_with_state_flow(self):
        """Test state flows through hierarchy correctly."""
        organism = OrganismMarkovBlanket(level="organism")
        colony = OrganismMarkovBlanket(level="colony", parent_blanket=organism)

        # Organism receives external observation
        organism_sensory = SensoryState()
        organism_sensory.hal_observation = torch.randn(512)
        organism._current_sensory = organism_sensory

        # Colony processes subset of organism observation
        colony_sensory = SensoryState()
        colony_sensory.hal_observation = torch.randn(256)  # Smaller than organism
        colony._current_sensory = colony_sensory

        # Both should validate
        assert organism.validate_blanket_discipline().valid is True
        assert colony.validate_blanket_discipline().valid is True

    def test_hierarchy_containment_transitive(self):
        """Test hierarchy containment is transitive (agent ⊂ colony ⊂ organism)."""
        organism = OrganismMarkovBlanket(level="organism")
        colony = OrganismMarkovBlanket(level="colony", parent_blanket=organism)
        agent = OrganismMarkovBlanket(level="agent", parent_blanket=colony)

        # Set state at each level (decreasing size)
        organism._current_sensory = SensoryState()
        organism._current_sensory.hal_observation = torch.randn(512)

        colony._current_sensory = SensoryState()
        colony._current_sensory.hal_observation = torch.randn(256)

        agent._current_sensory = SensoryState()
        agent._current_sensory.hal_observation = torch.randn(128)

        # All levels should validate
        assert organism.validate_blanket_discipline().valid is True
        assert colony.validate_blanket_discipline().valid is True
        assert agent.validate_blanket_discipline().valid is True


class TestMarkovBlanketActionIsolation:
    """Test action isolation property (no instantaneous feedback)."""

    def test_action_temporal_sequence(self):
        """Test actions follow proper temporal sequence (t → t+1)."""
        blanket = OrganismMarkovBlanket(level="organism")

        # Timestep t
        action_t = torch.randn(8)
        blanket._current_active = ActiveState(e8_action=action_t)
        blanket.check_action_isolation(action_t)

        # Timestep t+1 (different action)
        action_t1 = torch.randn(8)
        blanket._current_active = ActiveState(e8_action=action_t1)
        result = blanket.check_action_isolation(action_t1)

        assert result is True
        assert blanket._previous_active is not None

    def test_action_feedback_loop_prevented(self):
        """Test action feedback loop is prevented."""
        blanket = OrganismMarkovBlanket(level="organism")

        # Create action
        action = torch.randn(8)

        # Set current active state
        blanket._current_active = ActiveState(e8_action=action)

        # Try to use same action immediately (feedback loop)
        blanket._previous_active = ActiveState(e8_action=action)

        result = blanket.check_action_isolation(action)

        # Should detect and prevent feedback
        assert result is False
        assert blanket._action_feedback_detected is True

    def test_multiple_timesteps_no_feedback(self):
        """Test multiple timesteps with different actions."""
        blanket = OrganismMarkovBlanket(level="organism")

        actions = [torch.randn(8) for _ in range(5)]

        for action in actions:
            blanket._current_active = ActiveState(e8_action=action)
            result = blanket.check_action_isolation(action)
            assert result is True

        # No feedback detected across timesteps
        assert blanket._action_feedback_detected is False


@pytest.mark.property
class TestMarkovBlanketProperties:
    """Property-based tests for Markov blanket invariants."""

    def test_property_no_instantaneous_feedback(self):
        """Property: Actions at time t cannot observe actions at time t."""
        blanket = OrganismMarkovBlanket(level="organism")

        # Generate random action sequence
        actions = [torch.randn(8) for _ in range(10)]

        for i, action in enumerate(actions):
            # Each action should be independent of current action
            result = blanket.check_action_isolation(action)

            # Should pass (all actions are different)
            assert result is True, f"Action {i} failed isolation check"

    def test_property_hierarchy_transitive(self):
        """Property: If A ⊂ B and B ⊂ C, then A ⊂ C."""
        organism = OrganismMarkovBlanket(level="organism")
        colony = OrganismMarkovBlanket(level="colony", parent_blanket=organism)
        agent = OrganismMarkovBlanket(level="agent", parent_blanket=colony)

        # Verify transitive containment
        # Agent's parent's parent should be organism
        assert agent.parent_blanket.parent_blanket is organism  # type: ignore[union-attr]

    def test_property_blanket_closure_maintained(self):
        """Property: Internal state μ never directly observable from η."""
        blanket = OrganismMarkovBlanket(level="organism")

        # Set internal state
        mu = torch.randn(256)
        blanket.update_internal_state(mu)

        # Set external observation (random, independent)
        sensory = SensoryState()
        sensory.hal_observation = torch.randn(512)
        blanket._current_sensory = sensory

        result = blanket.validate_blanket_discipline()

        # Closure maintained (μ not in sensory)
        assert result.valid is True
        assert all(v.violation_type != "closure_broken" for v in result.error_violations)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
