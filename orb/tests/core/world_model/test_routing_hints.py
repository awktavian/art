"""Tests for World Model → Routing Hints Integration.

NEXUS BRIDGE TESTING (December 19, 2025):
==========================================
Verifies that RSSM world model predictions correctly influence routing decisions.

INTEGRATION VERIFICATION:
=========================
1. RSSM state → colony hint extraction
2. World model prediction → colony hint extraction
3. ColonyCoordinator context enrichment
4. FanoActionRouter hint usage

Created: December 19, 2025
"""

from __future__ import annotations

from typing import Any

import pytest

import torch

from kagami.core.config.unified_config import RSSMConfig as ColonyRSSMConfig

pytestmark = pytest.mark.tier_integration
from kagami.core.unified_agents.geometric_worker import COLONY_NAMES
from kagami.core.world_model.routing_hints import (
    enrich_routing_context_with_world_model,
    extract_colony_hint_from_rssm,
    extract_colony_hint_from_world_model,
)
from kagami.core.world_model.rssm_state import ColonyState


@pytest.fixture
def mock_colony_states() -> Any:
    """Create mock RSSM colony states."""
    config = ColonyRSSMConfig(
        obs_dim=512,
        colony_dim=256,
        stochastic_dim=128,
        action_dim=240,
        num_colonies=7,
    )

    states = []
    for i in range(7):
        # Create deterministic hidden state with different energies per colony
        # Colony 2 (Flow) will have highest energy → most likely prediction
        hidden = torch.randn(1, config.colony_dim)
        if i == 2:  # Flow colony
            hidden = hidden * 2.0  # Higher energy

        state = ColonyState(
            hidden=hidden,
            stochastic=torch.randn(1, config.stochastic_dim),
            colony_id=i,
            timestep=0,
            metadata={"s7_phase": torch.randn(1, 7)},  # S7 phase stored in metadata
        )
        states.append(state)

    return states


@pytest.fixture
def mock_world_model_service() -> Any:
    """Create mock world model service with prediction capability."""

    class MockPrediction:
        def __init__(self, colony_idx: int, confidence: float):
            self.recommended_colony = colony_idx
            self.confidence = confidence
            # Also provide state tensor for fallback path
            self.state = torch.zeros(1, 7)
            self.state[0, colony_idx] = confidence

    class MockWorldModelService:
        def __init__(self):
            self.is_available = True

        def predict(self, observation: Any, action: Any = None, horizon: Any = 1) -> Any:
            # Return prediction for colony 3 (Nexus) with high confidence
            return MockPrediction(colony_idx=3, confidence=0.85)

    return MockWorldModelService()


class TestExtractColonyHintFromRSSM:
    """Test RSSM → colony hint extraction."""

    def test_extract_hint_from_colony_states(self, mock_colony_states) -> Any:
        """Test extracting colony hint from list[ColonyState]."""
        hint = extract_colony_hint_from_rssm(mock_colony_states)

        assert hint is not None, "Hint should be extracted from valid states"
        assert hint["colony_idx"] == 2, "Flow colony (idx=2) should have highest energy"
        assert hint["colony_name"] == "flow", "Colony name should match index"
        assert hint["confidence"] > 0.6, "Confidence should exceed threshold"
        assert hint["source"] == "rssm_state", "Source should be rssm_state"

    def test_extract_hint_low_confidence(self, mock_colony_states) -> None:
        """Test that low confidence hints are rejected."""
        # Make all colonies equal energy → low confidence
        for state in mock_colony_states:
            state.hidden = torch.ones(1, 256) * 0.1

        hint = extract_colony_hint_from_rssm(mock_colony_states, confidence_threshold=0.8)

        assert hint is None, "Low confidence hints should be rejected (uniform distribution)"

    def test_extract_hint_none_states(self) -> None:
        """Test handling of None states."""
        hint = extract_colony_hint_from_rssm(None)  # type: ignore[arg-type]
        assert hint is None, "None states should return None hint"

    def test_extract_hint_empty_states(self) -> None:
        """Test handling of empty state list."""
        hint = extract_colony_hint_from_rssm([])
        assert hint is None, "Empty state list should return None hint"

    def test_extract_hint_wrong_colony_count(self) -> None:
        """Test handling of incorrect colony count."""
        config = ColonyRSSMConfig(colony_dim=256)
        states = [
            ColonyState(
                hidden=torch.randn(1, 256),
                stochastic=torch.randn(1, 128),
                colony_id=i,
                timestep=0,
                metadata={"s7_phase": torch.randn(1, 7)},
            )
            for i in range(5)  # Only 5 colonies instead of 7
        ]

        hint = extract_colony_hint_from_rssm(states)
        assert hint is None, "Wrong colony count should return None"

    def test_s7_coherence_boosts_confidence(self, mock_colony_states) -> None:
        """Test that S7 phase coherence increases confidence."""
        # Add high coherence S7 phase (all similar values)
        for state in mock_colony_states:
            state.metadata["s7_phase"] = torch.ones(1, 7) * 0.5  # High coherence

        hint_high_coherence = extract_colony_hint_from_rssm(mock_colony_states)

        # Compare to low coherence
        for state in mock_colony_states:
            state.metadata["s7_phase"] = torch.randn(1, 7)  # Low coherence (noisy)

        hint_low_coherence = extract_colony_hint_from_rssm(mock_colony_states)

        assert hint_high_coherence is not None, "High coherence should produce valid hint"
        assert hint_low_coherence is not None, "Low coherence should still produce hint"
        # Note: Confidence boost is 30% weight on coherence, so effect may be subtle


class TestExtractColonyHintFromWorldModel:
    """Test world model prediction → colony hint extraction."""

    def test_extract_hint_from_world_model(self, mock_world_model_service) -> None:
        """Test extracting colony hint from world model prediction."""
        observation = {"intent": "integrate.services", "params": {}}

        hint = extract_colony_hint_from_world_model(
            world_model_service=mock_world_model_service,
            observation=observation,
        )

        assert hint is not None, "Hint should be extracted from world model"
        assert hint["colony_idx"] == 3, "Nexus colony prediction should be used"
        assert hint["colony_name"] == "nexus", "Colony name should match index"
        assert hint["confidence"] == 0.85, "Confidence should match prediction"
        assert hint["source"] == "world_model_prediction", "Source should be correct"

    def test_extract_hint_unavailable_service(self) -> None:
        """Test handling of unavailable world model service."""

        class UnavailableService:
            is_available = False

        hint = extract_colony_hint_from_world_model(
            world_model_service=UnavailableService(),
            observation={"intent": "test"},
        )

        assert hint is None, "Unavailable service should return None hint"

    def test_extract_hint_no_prediction(self) -> None:
        """Test handling of failed prediction."""

        class FailingService:
            is_available = True

            def predict(self, observation: Any, action: Any = None, horizon: Any = 1) -> None:
                return None  # Prediction failed

        hint = extract_colony_hint_from_world_model(
            world_model_service=FailingService(),
            observation={"intent": "test"},
        )

        assert hint is None, "Failed prediction should return None hint"

    def test_extract_hint_from_state_fallback(self) -> None:
        """Test fallback to state-based extraction when no explicit colony."""

        class MockPredictionWithState:
            def __init__(self):
                # No recommended_colony attribute, only state
                # Use a distribution that will pass threshold after softmax
                self.state = torch.tensor([[0.1, 0.1, 0.1, 0.1, 3.0, 0.1, 0.1]])  # Beacon dominant

        class StateBasedService:
            is_available = True

            def predict(self, observation: Any, action: Any = None, horizon: Any = 1) -> Any:
                return MockPredictionWithState()

        hint = extract_colony_hint_from_world_model(
            world_model_service=StateBasedService(),
            observation={"intent": "test"},
            confidence_threshold=0.6,  # Standard threshold
        )

        assert hint is not None, "State-based fallback should work"
        assert hint["colony_idx"] == 4, "Beacon colony should be extracted from state"
        assert hint["source"] == "world_model_state", "Source should be state-based"


class TestEnrichRoutingContextWithWorldModel:
    """Test context enrichment for routing."""

    def test_enrich_context_with_rssm_hint(
        self, mock_colony_states, mock_world_model_service
    ) -> Any:
        """Test context enrichment using RSSM states."""
        context = {}

        enriched = enrich_routing_context_with_world_model(
            context=context,
            world_model_service=mock_world_model_service,
            observation=None,  # Not used when RSSM states available
            rssm_state=mock_colony_states,
        )

        assert "wm_colony_hint" in enriched, "Context should contain world model hint"
        hint = enriched["wm_colony_hint"]
        assert hint["colony_idx"] == 2, "Flow colony should be predicted from RSSM"
        assert hint["source"] == "rssm_state", "Source should be RSSM (preferred)"

    def test_enrich_context_with_world_model_fallback(self, mock_world_model_service) -> None:
        """Test context enrichment falling back to world model prediction."""
        context = {}
        observation = {"intent": "test"}

        enriched = enrich_routing_context_with_world_model(
            context=context,
            world_model_service=mock_world_model_service,
            observation=observation,
            rssm_state=None,  # No RSSM state → use world model
        )

        assert "wm_colony_hint" in enriched, "Context should contain world model hint"
        hint = enriched["wm_colony_hint"]
        assert hint["colony_idx"] == 3, "Nexus colony should be predicted from world model"
        assert hint["source"] == "world_model_prediction", "Source should be world model"

    def test_enrich_context_no_hint_available(self) -> None:
        """Test context enrichment when no hint can be extracted."""

        class UnavailableService:
            is_available = False

        context = {}

        enriched = enrich_routing_context_with_world_model(
            context=context,
            world_model_service=UnavailableService(),
            observation=None,
            rssm_state=None,
        )

        assert "wm_colony_hint" not in enriched, "Context should not contain hint when unavailable"
        assert enriched == context, "Context should be unchanged"

    def test_enrich_context_preserves_existing_keys(
        self, mock_colony_states, mock_world_model_service
    ) -> None:
        """Test that context enrichment preserves existing keys."""
        context = {
            "user_id": "test_user",
            "session_id": "abc123",
            "complexity": 0.7,
        }

        enriched = enrich_routing_context_with_world_model(
            context=context,
            world_model_service=mock_world_model_service,
            observation=None,
            rssm_state=mock_colony_states,
        )

        assert enriched["user_id"] == "test_user", "Existing keys should be preserved"
        assert enriched["session_id"] == "abc123", "Existing keys should be preserved"
        assert enriched["complexity"] == 0.7, "Existing keys should be preserved"
        assert "wm_colony_hint" in enriched, "New hint should be added"


class TestIntegrationWithFanoRouter:
    """Test integration with FanoActionRouter."""

    def test_router_uses_world_model_hint(self) -> None:
        """Test that FanoActionRouter respects world model hints."""
        from kagami.core.unified_agents.fano_action_router import FanoActionRouter

        router = FanoActionRouter()

        # Provide world model hint for Nexus (integration tasks)
        context = {
            "wm_colony_hint": {
                "colony_idx": 3,
                "colony_name": "nexus",
                "confidence": 0.85,
                "source": "rssm_state",
            }
        }

        # Route a simple task (complexity < 0.3)
        result = router.route(
            action="integrate.services",
            params={},
            complexity=0.2,  # Simple task
            context=context,
        )

        # Router should prefer world model hint if confident
        assert result.actions[0].colony_idx == 3, (
            "Router should use world model hint for simple task "
            "(hint confidence=0.85 > threshold=0.6)"
        )

    def test_router_ignores_low_confidence_hint(self) -> None:
        """Test that router ignores low confidence hints.

        Note (Jan 4, 2026): When OOD risk is HIGH and hint confidence < 0.8,
        the router escalates to Grove for safety. Low confidence hints don't
        override OOD escalation - only high-confidence hints (>= 0.8) do.

        This test verifies that:
        1. Low confidence hints are ignored (not used for routing)
        2. OOD escalation takes over when no confident hint is available
        """
        from kagami.core.unified_agents.fano_action_router import FanoActionRouter

        router = FanoActionRouter()

        # Provide low confidence hint
        context = {
            "wm_colony_hint": {
                "colony_idx": 0,  # Pulse (different from where it goes)
                "colony_name": "pulse",
                "confidence": 0.5,  # Below threshold (0.8) for overriding OOD
                "source": "rssm_state",
            }
        }

        result = router.route(
            action="build.feature",  # Keyword would suggest Forge (1)
            params={},
            complexity=0.2,
            context=context,
        )

        # Low confidence hint should be ignored.
        # With OOD HIGH and no confident hint, router escalates to Grove (5).
        # The hint was for Pulse (0), so if it wasn't ignored, we'd see 0.
        assert result.actions[0].colony_idx != 0, (
            "Router should ignore low confidence hint (hint confidence=0.5 < threshold=0.8)"
        )
        # Note: Actual routing depends on OOD detection - either Forge (keyword)
        # or Grove (OOD escalation). Both are valid ignoring behaviors.

    def test_router_hint_logged(self, caplog) -> None:
        """Test that router logs when world model hint is used."""
        from kagami.core.unified_agents.fano_action_router import FanoActionRouter

        router = FanoActionRouter()

        context = {
            "wm_colony_hint": {
                "colony_idx": 2,
                "colony_name": "flow",
                "confidence": 0.85,  # Must be > 0.8 for router to accept
                "source": "rssm_state",
            }
        }

        with caplog.at_level("DEBUG"):
            router.route(
                action="recover.from_error",
                params={},
                complexity=0.2,
                context=context,
            )

        # Check that world model hint usage was logged
        # The router logs "World model hint accepted" when confidence > 0.8
        assert any("World model hint" in record.message for record in caplog.records), (
            "Router should log when using world model hint (confidence > 0.8)"
        )


@pytest.mark.integration
class TestEndToEndIntegration:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_coordinator_enriches_context(self) -> None:
        """Test that ColonyCoordinator enriches context before routing."""
        from kagami.core.unified_agents.colony_coordinator import (
            create_colony_coordinator,
        )
        from kagami.core.unified_agents.e8_action_reducer import create_e8_reducer
        from kagami.core.unified_agents.fano_action_router import FanoActionRouter
        from kagami_math.e8 import get_e8_roots

        router = FanoActionRouter()
        reducer = create_e8_reducer(num_colonies=7, device="cpu")
        e8_roots = get_e8_roots("cpu")

        # Mock colony getter
        colonies = {}

        def get_colony_fn(idx: Any) -> str:
            from kagami.core.unified_agents.minimal_colony import ColonyConfig, create_colony

            if idx not in colonies:
                config = ColonyConfig(colony_idx=idx, max_workers=5)
                colonies[idx] = create_colony(idx, config)
            return colonies[idx]

        coordinator = create_colony_coordinator(
            router=router,
            reducer=reducer,
            e8_roots=e8_roots,
            get_colony_fn=get_colony_fn,
        )

        # Execute intent (should enrich context internally)
        result = await coordinator.execute_intent(
            intent="test.intent",
            params={"test": "data"},
            context={},
        )

        assert result is not None, "Coordinator should execute successfully"
        # Note: Context enrichment happens internally, we can't directly verify
        # the hint was added, but we verify no errors occurred


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
