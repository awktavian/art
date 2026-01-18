"""Tests for Ambient OS integration.

Verifies the complete ambient computing stack works together:
- Breath engine rhythm
- Colony expression mapping
- Multi-modal output coordination
- HAL integration

NOTE: Moved from tests/unit/ambient/ on Dec 19, 2025
This is an INTEGRATION test that initializes real display/GUI components.

Created: December 5, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

# Consolidated markers
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.integration,
]

import asyncio

# Mark all tests in this module as integration tests

from kagami.core.ambient.data_types import (
    BreathPhase,
    BreathState,
    Colony,
    ColonyState,
    PresenceLevel,
    PresenceState,
    SafetyState,
)
from kagami.core.ambient.breath_engine import BreathEngine, BreathConfig
from kagami.core.ambient.colony_expressor import ColonyExpressor, COLONY_COLORS
from kagami.core.ambient.controller import AmbientController, AmbientConfig

from kagami.core.ambient.unified_colony_renderer import (
    UnifiedColonyRenderer,
    ColonyRenderConfig,
)


class TestBreathEngine:
    """Tests for breath engine."""

    @pytest.mark.asyncio
    async def test_breath_cycle_phases(self) -> None:
        """Test breath cycles through all phases."""
        config = BreathConfig(base_bpm=60.0)  # Fast for testing (1s cycle)
        engine = BreathEngine(config)

        phases_seen: set[BreathPhase] = set()

        async def on_phase(state: Any) -> None:
            phases_seen.add(state.phase)

        engine.on_phase_change(on_phase)
        await engine.start()

        # Wait for at least one full cycle
        await asyncio.sleep(1.5)

        await engine.stop()

        # Should have seen all phases
        assert BreathPhase.INHALE in phases_seen
        assert BreathPhase.HOLD in phases_seen
        assert BreathPhase.EXHALE in phases_seen

    @pytest.mark.asyncio
    async def test_breath_value_range(self) -> None:
        """Test breath value stays in 0-1 range."""
        engine = BreathEngine()

        # Test at different points
        for phase in BreathPhase:
            engine._state.phase = phase
            for progress in [0.0, 0.25, 0.5, 0.75, 1.0]:
                engine._state.phase_progress = progress
                value = engine.get_breath_value()
                assert 0.0 <= value <= 1.0, f"Breath value out of range at {phase}:{progress}"

    def test_receipt_sync(self) -> None:
        """Test syncing to receipt phases."""
        engine = BreathEngine()

        engine.sync_to_receipt("PLAN")
        assert engine.state.phase == BreathPhase.INHALE

        engine.sync_to_receipt("EXECUTE")
        assert engine.state.phase == BreathPhase.HOLD

        engine.sync_to_receipt("VERIFY")
        assert engine.state.phase == BreathPhase.EXHALE


class TestColonyExpressor:
    """Tests for colony expression."""

    def test_colony_colors_defined(self) -> None:
        """Test all colonies have colors."""
        for colony in Colony:
            assert colony in COLONY_COLORS
            r, g, b = COLONY_COLORS[colony]
            assert 0 <= r <= 255
            assert 0 <= g <= 255
            assert 0 <= b <= 255

    def test_express_generates_output(self) -> None:
        """Test expression generates multi-modal output."""
        expressor = ColonyExpressor()

        state = ColonyState(
            colony=Colony.SPARK,
            activation=0.8,
            potential=1.0,
            gradient=(0.1,),
            params=(-0.1,),
        )

        expressions = expressor.express(state)

        assert len(expressions) > 0
        # Should have light and sound at minimum
        modalities = {e.modality.value for e in expressions}
        assert "light_color" in modalities
        assert "sound_tone" in modalities

    def test_low_activation_no_output(self) -> None:
        """Test low activation produces no output."""
        expressor = ColonyExpressor()

        state = ColonyState(
            colony=Colony.SPARK,
            activation=0.05,  # Below threshold
            potential=1.0,
            gradient=(0.1,),
            params=(-0.1,),
        )

        expressions = expressor.express(state)
        assert len(expressions) == 0

    def test_blend_colors(self) -> None:
        """Test color blending by activation."""
        expressor = ColonyExpressor()

        states = {
            Colony.SPARK: ColonyState(
                colony=Colony.SPARK,
                activation=1.0,
                potential=1.0,
                gradient=(0.1,),
                params=(-0.1,),
            ),
            Colony.CRYSTAL: ColonyState(
                colony=Colony.CRYSTAL,
                activation=1.0,
                potential=1.0,
                gradient=(0.1, 0.1),
                params=(0.5, 0.5, 0.0, 0.0),
            ),
        }

        blended = expressor.blend_colors(states)
        r, g, b = blended

        # Should be between SPARK (magenta) and CRYSTAL (blue)
        assert 0 <= r <= 255
        assert 0 <= g <= 255
        assert 0 <= b <= 255


class TestAmbientController:
    """Tests for main ambient controller."""

    @pytest.mark.asyncio
    async def test_controller_initialization(self) -> None:
        """Test controller initializes all subsystems."""
        config = AmbientConfig(
            enable_lights=False,  # Skip external dependencies
            enable_sound=False,
            enable_haptic=False,
        )
        controller = AmbientController(config)

        result = await controller.initialize()
        assert result is True
        assert controller._initialized is True

        # Breath engine should be running
        assert controller._breath is not None

        # Colony expressor should be available
        assert controller._expressor is not None

        await controller.shutdown()

    @pytest.mark.asyncio
    async def test_colony_state_update(self) -> None:
        """Test updating colony states."""
        config = AmbientConfig(
            enable_lights=False,
            enable_sound=False,
            enable_haptic=False,
        )
        controller = AmbientController(config)
        await controller.initialize()

        states = {
            Colony.SPARK: ColonyState(
                colony=Colony.SPARK,
                activation=0.7,
                potential=1.0,
                gradient=(0.1,),
                params=(-0.1,),
            )
        }

        controller.update_colony_states(states)
        assert Colony.SPARK in controller._state.colonies
        assert controller._state.colonies[Colony.SPARK].activation == 0.7

        await controller.shutdown()

    @pytest.mark.asyncio
    async def test_safety_update(self) -> None:
        """Test safety state updates."""
        config = AmbientConfig(
            enable_lights=False,
            enable_sound=False,
            enable_haptic=False,
        )
        controller = AmbientController(config)
        await controller.initialize()

        # Safe state
        safe = SafetyState(
            h_value=1.0,
            x_threat=0.1,
            x_uncertainty=0.1,
            x_complexity=0.1,
            x_risk=0.1,
            gradient=(0.0, 0.0, 0.0, 0.0),
        )
        controller.update_safety(safe)
        assert controller._state.safety.is_safe is True

        # Unsafe state
        unsafe = SafetyState(
            h_value=-0.1,
            x_threat=0.9,
            x_uncertainty=0.5,
            x_complexity=0.5,
            x_risk=0.5,
            gradient=(0.0, 0.0, 0.0, 0.0),
        )
        controller.update_safety(unsafe)
        assert controller._state.safety.is_safe is False
        assert controller._stats["safety_alerts"] >= 1

        await controller.shutdown()

    @pytest.mark.asyncio
    async def test_presence_adaptation(self) -> None:
        """Test presence level adaptation."""
        config = AmbientConfig(
            enable_lights=False,
            enable_sound=False,
            enable_haptic=False,
        )
        controller = AmbientController(config)
        await controller.initialize()

        # Test presence changes
        for level in PresenceLevel:
            presence = PresenceState(
                level=level,
                confidence=0.9,
                attention_target=None,
                activity_type=None,
                location=None,
            )
            controller.update_presence(presence)
            assert controller._state.presence.level == level

        await controller.shutdown()

    @pytest.mark.asyncio
    async def test_receipt_sync(self) -> None:
        """Test receipt phase synchronization."""
        config = AmbientConfig(
            enable_lights=False,
            enable_sound=False,
            enable_haptic=False,
        )
        controller = AmbientController(config)
        await controller.initialize()

        # Sync to PLAN - check breath engine directly
        controller.sync_to_receipt("PLAN", "test-correlation-id")
        assert controller._breath.state.phase == BreathPhase.INHALE  # type: ignore[union-attr]

        # Sync to EXECUTE
        controller.sync_to_receipt("EXECUTE")
        assert controller._breath.state.phase == BreathPhase.HOLD  # type: ignore[union-attr]

        # Sync to VERIFY
        controller.sync_to_receipt("VERIFY")
        assert controller._breath.state.phase == BreathPhase.EXHALE  # type: ignore[union-attr]

        await controller.shutdown()


class TestSafetyState:
    """Tests for safety state calculations."""

    def test_safety_margin_calculation(self) -> None:
        """Test safety margin normalization."""
        # Safe
        safe = SafetyState(
            h_value=2.0,
            x_threat=0.1,
            x_uncertainty=0.1,
            x_complexity=0.1,
            x_risk=0.1,
            gradient=(0.0, 0.0, 0.0, 0.0),
        )
        assert safe.is_safe is True
        assert safe.safety_margin > 0.5

        # Unsafe
        unsafe = SafetyState(
            h_value=-2.0,
            x_threat=0.9,
            x_uncertainty=0.9,
            x_complexity=0.9,
            x_risk=0.9,
            gradient=(0.0, 0.0, 0.0, 0.0),
        )
        assert unsafe.is_safe is False
        assert unsafe.safety_margin < 0.5

        # Edge
        edge = SafetyState(
            h_value=0.0,
            x_threat=0.5,
            x_uncertainty=0.5,
            x_complexity=0.5,
            x_risk=0.5,
            gradient=(0.0, 0.0, 0.0, 0.0),
        )
        assert edge.is_safe is True  # h >= 0 is safe
        assert 0.4 < edge.safety_margin < 0.6  # Near 0.5


class TestUnifiedColonyRenderer:
    """Tests for unified colony renderer."""

    @pytest.mark.asyncio
    async def test_renderer_initialization(self) -> None:
        """Test renderer initializes correctly."""
        config = ColonyRenderConfig(fps=30)
        renderer = UnifiedColonyRenderer(config)

        result = await renderer.initialize()
        assert result is True
        assert renderer._initialized is True
        assert renderer._buffer is not None

        # Buffer should have correct shape (H, W, 4 for RGBA)
        assert len(renderer._buffer.shape) == 3
        assert renderer._buffer.shape[2] == 4

        await renderer.stop()

    def test_renderer_state_updates(self) -> None:
        """Test renderer accepts state updates."""
        renderer = UnifiedColonyRenderer()

        # Breath state
        breath = BreathState(
            phase=BreathPhase.INHALE,
            phase_progress=0.5,
            bpm=6.0,
            intensity=0.8,
            cycle_count=1,
        )
        renderer.set_breath(breath)
        assert renderer._breath == breath

        # Colony states
        colonies = {
            Colony.SPARK: ColonyState(
                colony=Colony.SPARK,
                activation=0.8,
                potential=1.0,
                gradient=(0.1,),
                params=(-0.1,),
            )
        }
        renderer.set_colonies(colonies)
        assert renderer._colonies == colonies

        # Safety state
        safety = SafetyState(
            h_value=1.0,
            x_threat=0.1,
            x_uncertainty=0.1,
            x_complexity=0.1,
            x_risk=0.1,
            gradient=(0.0, 0.0, 0.0, 0.0),
        )
        renderer.set_safety(safety)
        assert renderer._safety == safety

        # Presence state
        presence = PresenceState(
            level=PresenceLevel.ENGAGED,
            confidence=0.9,
            attention_target="screen",
            activity_type="working",
            location=None,
        )
        renderer.set_presence(presence)
        assert renderer._presence == presence

    @pytest.mark.asyncio
    async def test_controller_with_display(self) -> None:
        """Test controller initializes display when enabled."""
        config = AmbientConfig(
            enable_lights=False,
            enable_sound=False,
            enable_haptic=False,
            enable_voice=False,
            enable_display=True,
            enable_world_model=False,  # Skip for speed
        )
        controller = AmbientController(config)
        await controller.initialize()

        # Display should be initialized
        assert controller._display is not None
        assert controller._display._initialized is True

        await controller.shutdown()
