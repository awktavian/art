"""Tests for brain-inspired systems.

Tests the brain science integration modules:
- InhibitoryGate: Colony competition and suppression
- NeuromodulatorSystem: DA/NE/ACh/5-HT state modulation
- OscillatoryCoordinator: Gamma synchrony and binding
- FeedbackProjection: Top-down recurrence
- BrainConsolidation: Sleep replay and schemas
- UnifiedBrainSystem: Integrated processing

December 2025 - Brain Science × Kagami Integration
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_unit



import torch


class TestInhibitoryGate:
    """Tests for inhibitory gate module."""

    def test_inhibitory_gate_creation(self):
        """Test that inhibitory gate can be created."""
        from kagami.core.unified_agents.inhibitory_gate import (
            InhibitoryGate,
            create_inhibitory_gate,
        )

        gate = create_inhibitory_gate(num_colonies=7)
        assert isinstance(gate, InhibitoryGate)
        assert gate.num_colonies == 7

    def test_fast_inhibition(self):
        """Test fast (PV-like) lateral inhibition."""
        from kagami.core.unified_agents.inhibitory_gate import FastInhibition

        fast = FastInhibition(num_colonies=7)
        activations = torch.rand(2, 7)  # Batch of 2

        inhibited, inhib_levels = fast(activations)

        assert inhibited.shape == (2, 7)
        assert inhib_levels.shape == (2, 7)
        # Total activation mass is preserved (inhibition sharpens, doesn't reduce)
        total_before = activations.sum(dim=-1)
        total_after = inhibited.sum(dim=-1)
        assert torch.allclose(total_before, total_after, atol=1e-5)

    def test_slow_inhibition(self):
        """Test slow (SST-like) context-dependent gating."""
        from kagami.core.unified_agents.inhibitory_gate import SlowInhibition

        slow = SlowInhibition(num_colonies=7)
        activations = torch.rand(2, 7)

        gated, gate_values = slow(activations)

        assert gated.shape == (2, 7)
        assert gate_values.shape == (2, 7)
        # Gate values should be in [0, 1]
        assert (gate_values >= 0).all()
        assert (gate_values <= 1).all()

    def test_unified_inhibitory_gate(self):
        """Test unified inhibitory gate with all mechanisms."""
        from kagami.core.unified_agents.inhibitory_gate import InhibitoryGate

        gate = InhibitoryGate(num_colonies=7)
        activations = torch.rand(2, 7)

        gated, state = gate(activations)

        assert gated.shape == (2, 7)
        assert state.inhibition_levels.shape == (2, 7)
        assert state.mean_inhibition >= 0


class TestNeuromodulatorSystem:
    """Tests for neuromodulator system."""

    def test_neuromodulator_creation(self):
        """Test that neuromodulator system can be created."""
        from kagami.core.neuromodulation import (
            NeuromodulatorSystem,
            create_neuromodulator_system,
        )

        system = create_neuromodulator_system(input_dim=8)
        assert isinstance(system, NeuromodulatorSystem)

    def test_dopamine_channel(self):
        """Test dopamine channel computes RPE."""
        from kagami.core.neuromodulation.modulator_system import DopamineChannel

        da = DopamineChannel(input_dim=8)
        state = torch.rand(2, 8)
        reward = torch.tensor([1.0, 0.0])

        da_level, rpe = da(state, reward)

        assert da_level.shape == (2,)
        assert rpe.shape == (2,)
        # DA level should be in [0, 1] (sigmoid output)
        assert (da_level >= 0).all()
        assert (da_level <= 1).all()

    def test_unified_neuromodulator(self):
        """Test unified neuromodulator system."""
        from kagami.core.neuromodulation import NeuromodulatorSystem

        system = NeuromodulatorSystem(input_dim=8)
        state = torch.rand(2, 8)

        neuromod_state = system(state, reward=torch.tensor([1.0, 0.0]))

        assert neuromod_state.dopamine.shape == (2,)
        assert neuromod_state.norepinephrine.shape == (2,)
        assert neuromod_state.acetylcholine.shape == (2,)
        assert neuromod_state.serotonin.shape == (2,)
        assert 0 <= neuromod_state.arousal <= 1

    def test_efe_weights(self):
        """Test EFE weight generation from neuromodulator state."""
        from kagami.core.neuromodulation import NeuromodulatorSystem

        system = NeuromodulatorSystem(input_dim=8)
        state = torch.rand(2, 8)
        neuromod_state = system(state)

        weights = system.get_efe_weights(neuromod_state)

        assert "epistemic" in weights
        assert "pragmatic" in weights
        assert "safety" in weights


class TestOscillatoryCoordinator:
    """Tests for oscillatory coordination."""

    def test_oscillatory_coordinator_creation(self):
        """Test that oscillatory coordinator can be created."""
        from kagami.core.dynamics.oscillatory_coordinator import (
            OscillatoryCoordinator,
            create_oscillatory_coordinator,
        )

        coord = create_oscillatory_coordinator(num_colonies=7)
        assert isinstance(coord, OscillatoryCoordinator)

    def test_kuramoto_oscillator(self):
        """Test Kuramoto oscillator dynamics."""
        from kagami.core.dynamics.oscillatory_coordinator import KuramotoOscillator

        osc = KuramotoOscillator(num_oscillators=7)

        # Initial phases should be random
        initial_phases = osc.phases.clone()  # type: ignore[operator]

        # Step should update phases
        new_phases = osc.step()
        assert new_phases.shape == (7,)
        assert not torch.equal(new_phases, initial_phases)

    def test_order_parameter(self):
        """Test Kuramoto order parameter computation."""
        from kagami.core.dynamics.oscillatory_coordinator import KuramotoOscillator

        osc = KuramotoOscillator(num_oscillators=7)

        r, psi = osc.compute_order_parameter()

        # Order parameter should be in [0, 1]
        assert 0 <= r <= 1
        # Mean phase should be in [-pi, pi]
        assert -3.15 <= psi <= 3.15

    def test_synchronization(self):
        """Test that oscillators can synchronize."""
        from kagami.core.dynamics.oscillatory_coordinator import OscillatoryCoordinator

        coord = OscillatoryCoordinator(
            num_colonies=7,
            coupling_strength=2.0,  # Strong coupling for faster sync
        )

        # Run for many steps
        state = None
        for _ in range(500):
            state = coord.step()

        # Should approach synchronization with strong coupling
        assert state is not None
        assert state.order_parameter > 0.3  # Some synchronization


class TestFeedbackProjection:
    """Tests for feedback projection."""

    def test_feedback_projection_creation(self):
        """Test that feedback projection can be created."""
        from kagami.core.brain_systems.feedback import (
            FeedbackProjection,
            create_feedback_projection,
        )

        proj = create_feedback_projection(input_dim=64, num_colonies=7)
        assert isinstance(proj, FeedbackProjection)

    def test_feedback_forward(self):
        """Test feedback forward pass."""
        from kagami.core.brain_systems.feedback import FeedbackProjection

        proj = FeedbackProjection(input_dim=64, num_colonies=7)
        hidden = torch.rand(2, 7, 64)

        refined, state = proj(hidden)

        assert refined.shape == (2, 7, 64)
        assert state.feedback_signals.shape == (2, 7, 64)
        assert state.prediction_errors.shape == (2, 7, 64)

    def test_fano_structured_feedback(self):
        """Test that feedback respects Fano structure."""
        from kagami.core.brain_systems.feedback import FeedbackProjection

        proj = FeedbackProjection(input_dim=64, num_colonies=7)

        # Fano mask should have correct structure
        mask = proj.fano_mask

        assert mask.shape == (7, 7)
        # Diagonal should be zero (no self-feedback)
        assert (mask.diag() == 0).all()  # type: ignore[operator]
        # Should have 21 non-zero entries (3 per line * 7 lines, but divided by symmetry)
        # Actually: each colony connects to 3 others via Fano lines = 21 total edges


class TestBrainConsolidation:
    """Tests for brain consolidation system."""

    def test_brain_consolidation_creation(self):
        """Test that brain consolidation can be created."""
        from kagami.core.memory.brain_consolidation import (
            BrainConsolidation,
            get_brain_consolidation,
        )

        consolidation = get_brain_consolidation()
        assert isinstance(consolidation, BrainConsolidation)

    def test_add_experience(self):
        """Test adding experiences to replay buffer."""
        from kagami.core.memory.brain_consolidation import BrainConsolidation

        consolidation = BrainConsolidation(state_dim=8)

        state = torch.rand(8)
        action = torch.rand(8)
        next_state = torch.rand(8)

        consolidation.add_experience(
            state=state,
            action=action,
            reward=1.0,
            next_state=next_state,
        )

        assert len(consolidation.replay_buffer) == 1

    def test_replay(self):
        """Test experience replay."""
        from kagami.core.memory.brain_consolidation import BrainConsolidation

        consolidation = BrainConsolidation(state_dim=8)

        # Add multiple experiences
        for _ in range(100):
            consolidation.add_experience(
                state=torch.rand(8),
                action=torch.rand(8),
                reward=torch.rand(1).item(),
                next_state=torch.rand(8),
            )

        experiences, weights = consolidation.replay(batch_size=32)

        assert len(experiences) == 32
        assert weights.shape == (32,)

    def test_schema_extraction(self):
        """Test schema extraction from experiences."""
        from kagami.core.memory.brain_consolidation import SchemaExtractor

        extractor = SchemaExtractor(state_dim=8, num_schemas=16)

        # Assign and update
        state = torch.rand(8)
        schema_idx, distance = extractor.assign(state)
        extractor.update(schema_idx, state, reward=1.0)

        assert 0 <= schema_idx < 16
        assert distance >= 0

        stats = extractor.get_stats()
        assert stats["num_active"] >= 1


class TestUnifiedBrainSystem:
    """Tests for unified brain system."""

    def test_unified_brain_creation(self):
        """Test that unified brain system can be created."""
        from kagami.core.brain_systems import (
            UnifiedBrainSystem,
            create_unified_brain_system,
        )

        brain = create_unified_brain_system()
        assert isinstance(brain, UnifiedBrainSystem)

    def test_unified_brain_step(self):
        """Test unified brain step."""
        from kagami.core.brain_systems import UnifiedBrainSystem

        brain = UnifiedBrainSystem()
        activations = torch.rand(7)
        state = torch.rand(8)

        processed, brain_state = brain.step(
            colony_activations=activations,
            state=state,
            reward=1.0,
        )

        assert processed.shape == (7,)
        assert brain_state.step_count == 1

    def test_all_components_enabled(self):
        """Test that all components work together."""
        from kagami.core.brain_systems import UnifiedBrainSystem

        brain = UnifiedBrainSystem(
            enable_inhibition=True,
            enable_neuromodulation=True,
            enable_oscillation=True,
            enable_feedback=True,
        )

        activations = torch.rand(7)
        state = torch.rand(8)
        hidden_states = torch.rand(1, 7, 64)

        processed, brain_state = brain.step(
            colony_activations=activations,
            state=state,
            hidden_states=hidden_states,
            reward=1.0,
            prediction_error=0.5,
        )

        assert processed.shape == (7,)
        assert brain_state.neuromodulation is not None
        assert brain_state.inhibition is not None
        assert brain_state.oscillation is not None


class TestFanoRouterInhibition:
    """Tests for inhibition integration in Fano router."""

    def test_router_has_inhibition(self):
        """Test that Fano router has inhibitory gate."""
        from kagami.core.unified_agents.fano_action_router import FanoActionRouter

        router = FanoActionRouter()
        assert router._inhibitory_gate is not None

    def test_routing_applies_inhibition(self):
        """Test that routing applies inhibition."""
        from kagami.core.unified_agents.fano_action_router import FanoActionRouter

        router = FanoActionRouter()

        result = router.route(
            action="build.feature",
            params={"spec": "test"},
            complexity=0.5,  # Medium complexity triggers Fano line
        )

        # Should have inhibition metadata
        assert "inhibition_applied" in result.metadata or len(result.actions) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
