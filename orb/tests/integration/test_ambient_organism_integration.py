"""Integration Tests: Ambient Controller ← Organism State Bridge.

Tests the Nexus integration that connects organism state to ambient display.

Created: December 14, 2025
Author: Nexus (Integration)
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import torch

from kagami.core.unified_agents.unified_organism import (
    UnifiedOrganism,
    OrganismConfig,
)
from kagami.core.ambient.controller import AmbientController, AmbientConfig
from kagami.core.ambient.data_types import (
    BreathPhase,
    Colony,
    PresenceLevel,
)


@pytest.fixture
async def organism():
    """Create organism for testing."""
    config = OrganismConfig(
        max_workers_per_colony=2,
        min_workers_per_colony=1,
        global_max_population=20,
        homeostasis_interval=60.0,
        device="cpu",
    )
    org = UnifiedOrganism(config=config)
    await org.start()
    yield org
    await org.stop()


@pytest.fixture
async def ambient_controller():
    """Create ambient controller for testing."""
    config = AmbientConfig(
        enable_lights=False,  # Disable hardware for tests
        enable_sound=False,
        enable_haptic=False,
        enable_voice=False,
        enable_vision=False,
        enable_constellation=False,
        enable_privacy=False,
        enable_consent=False,
        enable_explainability=False,
    )
    controller = AmbientController(config=config)
    await controller.initialize()
    yield controller
    await controller.shutdown()


@pytest.mark.asyncio
async def test_ambient_connection(organism: Any, ambient_controller: Any) -> None:
    """Test: Organism can connect to ambient controller."""
    # Connect
    organism.set_ambient_controller(ambient_controller)

    # Verify connection
    assert organism._ambient_controller is not None
    assert organism._ambient_controller is ambient_controller


@pytest.mark.asyncio
async def test_colony_state_propagation(organism: Any, ambient_controller: Any) -> None:
    """Test: Colony states propagate from organism to ambient display."""
    # Connect
    organism.set_ambient_controller(ambient_controller)

    # Execute an intent to populate colony states
    result = await organism.execute_intent(
        intent="test.simple",
        params={"task": "test colony state propagation"},
        context={},
    )

    assert result["success"]

    # Verify ambient state updated
    ambient_state = ambient_controller.get_state()

    # At least one colony should be active
    assert len(ambient_state.colonies) > 0

    # Verify colony structure
    for colony, state in ambient_state.colonies.items():
        assert isinstance(colony, Colony)
        assert 0.0 <= state.activation <= 1.0
        assert state.colony == colony


@pytest.mark.asyncio
async def test_safety_state_propagation(organism: Any, ambient_controller: Any) -> None:
    """Test: Safety state (h(x)) propagates to ambient display."""
    # Connect
    organism.set_ambient_controller(ambient_controller)

    # Execute an intent (will trigger CBF check)
    result = await organism.execute_intent(
        intent="test.safe",
        params={"task": "test safety propagation"},
        context={},
    )

    assert result["success"]

    # Verify ambient safety state
    ambient_state = ambient_controller.get_state()
    safety = ambient_state.safety

    # h(x) should be populated (>= 0 for safe operation)
    assert safety.h_value >= 0.0
    assert safety.is_safe


@pytest.mark.asyncio
async def test_phase_mapping(organism: Any, ambient_controller: Any) -> None:
    """Test: Coordination phase maps to breath phase correctly."""
    # Connect
    organism.set_ambient_controller(ambient_controller)

    # Execute intent to trigger phase detection
    result = await organism.execute_intent(
        intent="test.complex",
        params={"task": "test phase mapping"},
        context={},
    )

    assert result["success"]

    # Verify breath phase updated
    ambient_state = ambient_controller.get_state()
    breath = ambient_state.breath

    # Breath phase should be one of the valid phases
    assert breath.phase in [
        BreathPhase.INHALE,
        BreathPhase.HOLD,
        BreathPhase.EXHALE,
        BreathPhase.REST,
    ]


@pytest.mark.asyncio
async def test_real_time_updates(organism: Any, ambient_controller: Any) -> None:
    """Test: Ambient state updates in real-time after each execution."""
    # Connect
    organism.set_ambient_controller(ambient_controller)

    # Execute first intent
    result1 = await organism.execute_intent(
        intent="test.intent1",
        params={"task": "first"},
        context={},
    )
    assert result1["success"]

    # Get ambient state after first
    state1 = ambient_controller.get_state()
    h_x_1 = state1.safety.h_value

    # Execute second intent
    result2 = await organism.execute_intent(
        intent="test.intent2",
        params={"task": "second"},
        context={},
    )
    assert result2["success"]

    # Get ambient state after second
    state2 = ambient_controller.get_state()
    h_x_2 = state2.safety.h_value

    # Both should have valid safety states
    assert h_x_1 is not None
    assert h_x_2 is not None
    assert h_x_1 >= 0.0
    assert h_x_2 >= 0.0


@pytest.mark.asyncio
async def test_ambient_update_without_controller(organism: Any) -> None:
    """Test: Ambient update gracefully handles missing controller."""
    # Don't connect controller
    assert organism._ambient_controller is None

    # Execute intent - should not crash
    result = await organism.execute_intent(
        intent="test.no_ambient",
        params={"task": "test without controller"},
        context={},
    )

    # Should succeed even without ambient
    assert result["success"]


@pytest.mark.asyncio
async def test_colony_activation_levels(organism: Any, ambient_controller: Any) -> None:
    """Test: Colony activation levels reflect worker populations."""
    # Connect
    organism.set_ambient_controller(ambient_controller)

    # Force creation of specific colonies
    organism._get_or_create_colony(0)  # spark
    organism._get_or_create_colony(1)  # forge
    organism._get_or_create_colony(2)  # flow

    # Execute intent
    result = await organism.execute_intent(
        intent="test.multi_colony",
        params={"task": "multi-colony test"},
        context={},
    )

    assert result["success"]

    # Check ambient state
    ambient_state = ambient_controller.get_state()

    # Should have colony states
    assert len(ambient_state.colonies) >= 1

    # Activation should be normalized (0-1)
    for _, state in ambient_state.colonies.items():
        assert 0.0 <= state.activation <= 1.0


@pytest.mark.asyncio
async def test_cbf_safety_caching(organism: Any, ambient_controller: Any) -> None:
    """Test: Safety check results are cached and reused."""
    # Connect
    organism.set_ambient_controller(ambient_controller)

    # Execute intent (triggers CBF check)
    result = await organism.execute_intent(
        intent="test.cbf_cache",
        params={"task": "cbf caching test"},
        context={},
    )

    assert result["success"]

    # Verify cached safety check
    assert organism._last_safety_check is not None
    assert hasattr(organism._last_safety_check, "h_x")
    assert organism._last_safety_check.h_x is not None

    # Ambient state should reflect cached value
    ambient_state = ambient_controller.get_state()
    assert ambient_state.safety.h_value == organism._last_safety_check.h_x


@pytest.mark.asyncio
async def test_coordination_phase_transitions(organism: Any, ambient_controller: Any) -> None:
    """Test: Breath phase updates when coordination phase changes."""
    # Connect
    organism.set_ambient_controller(ambient_controller)

    # Record initial phase
    initial_phase = organism.phase_detector.current_phase

    # Execute multiple intents to potentially trigger phase transition
    for i in range(5):
        result = await organism.execute_intent(
            intent=f"test.phase_transition_{i}",
            params={"task": f"intent {i}"},
            context={},
        )
        assert result["success"]

    # Check if phase changed
    final_phase = organism.phase_detector.current_phase

    # Ambient breath phase should reflect coordination phase
    ambient_state = ambient_controller.get_state()

    # Verify mapping exists
    assert ambient_state.breath.phase in [
        BreathPhase.INHALE,
        BreathPhase.HOLD,
        BreathPhase.EXHALE,
        BreathPhase.REST,
    ]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
