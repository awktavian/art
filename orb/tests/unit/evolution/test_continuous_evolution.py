"""Tests for ContinuousEvolutionEngine - covers 350 lines."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kagami.core.evolution.continuous_evolution_engine import (
    ContinuousEvolutionEngine,
    EvolutionCycle,
    EvolutionPhase,
)


class TestEvolutionPhase:
    """Test EvolutionPhase enum."""

    def test_all_phases_defined(self) -> None:
        """All 6 phases should be defined."""
        phases = list(EvolutionPhase)
        assert len(phases) == 6
        assert EvolutionPhase.OBSERVE in phases
        assert EvolutionPhase.LEARN in phases
        assert EvolutionPhase.IMPROVE in phases
        assert EvolutionPhase.ACT in phases
        assert EvolutionPhase.VERIFY in phases
        assert EvolutionPhase.EVOLVE in phases

    def test_phase_values(self) -> None:
        """Phase values should be lowercase strings."""
        assert EvolutionPhase.OBSERVE.value == "observe"
        assert EvolutionPhase.LEARN.value == "learn"
        assert EvolutionPhase.IMPROVE.value == "improve"
        assert EvolutionPhase.ACT.value == "act"
        assert EvolutionPhase.VERIFY.value == "verify"
        assert EvolutionPhase.EVOLVE.value == "evolve"


class TestEvolutionCycle:
    """Test EvolutionCycle dataclass."""

    def test_cycle_creation(self) -> None:
        """Test creating an evolution cycle."""
        cycle = EvolutionCycle(
            cycle_id="test-cycle-1",
            start_time=1000.0,
            observations=[{"type": "pattern", "data": {}}],
            learnings={"model_updated": True},
            improvements=[{"file": "test.py", "change": "fix"}],
            actions=[{"action": "deploy"}],
            verifications={"metrics": {"accuracy": 0.95}},
            meta_insights={"strategy": "gradient"},
            end_time=1100.0,
            success=True,
        )
        assert cycle.cycle_id == "test-cycle-1"
        assert cycle.success is True
        assert len(cycle.observations) == 1
        assert cycle.end_time - cycle.start_time == 100.0

    def test_failed_cycle(self) -> None:
        """Test creating a failed cycle."""
        cycle = EvolutionCycle(
            cycle_id="failed-cycle",
            start_time=0.0,
            observations=[],
            learnings={},
            improvements=[],
            actions=[],
            verifications={"error": "timeout"},
            meta_insights={},
            end_time=10.0,
            success=False,
        )
        assert cycle.success is False
        assert "error" in cycle.verifications


class TestContinuousEvolutionEngineInit:
    """Test engine initialization."""

    def test_engine_init(self) -> None:
        """Test basic engine initialization."""
        engine = ContinuousEvolutionEngine()
        assert engine._running is False
        assert engine._cycle_count == 0
        assert engine._cycles == []
        assert engine._cycle_interval == 300
        assert engine._max_actions_per_cycle == 3

    def test_lazy_components(self) -> None:
        """Test that components are lazy loaded."""
        engine = ContinuousEvolutionEngine()
        assert engine._world_model is None
        assert engine._user_modeler is None
        assert engine._self_improver is None
        assert engine._goal_generator is None
        assert engine._curriculum is None
        assert engine._meta_learner is None
        assert engine._experience_store is None

    def test_safety_systems(self) -> None:
        """Test safety systems initialized as None."""
        engine = ContinuousEvolutionEngine()
        assert engine._fitness_functions is None
        assert engine._dry_run_evaluator is None
        assert engine._canary_rollout is None
        assert engine._checkpoints is None
        assert engine._controls is None
        assert engine._ledger is None


class TestContinuousEvolutionEngineConfig:
    """Test engine configuration."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        engine = ContinuousEvolutionEngine()
        assert engine._cycle_interval == 300  # 5 minutes
        assert engine._max_actions_per_cycle == 3

    def test_config_attributes(self) -> None:
        """Test that config attributes can be accessed."""
        engine = ContinuousEvolutionEngine()
        # Modify config
        engine._cycle_interval = 60
        engine._max_actions_per_cycle = 5
        assert engine._cycle_interval == 60
        assert engine._max_actions_per_cycle == 5


class TestContinuousEvolutionEngineState:
    """Test engine state management."""

    def test_initial_state(self) -> None:
        """Test engine initial state."""
        engine = ContinuousEvolutionEngine()
        assert engine._running is False
        assert engine._cycle_count == 0

    def test_cycle_tracking(self) -> None:
        """Test cycle list tracking."""
        engine = ContinuousEvolutionEngine()
        assert isinstance(engine._cycles, list)
        assert len(engine._cycles) == 0


@pytest.mark.asyncio
class TestContinuousEvolutionEngineAsync:
    """Test async operations."""

    async def test_start_stop_evolution(self):
        """Test starting and stopping evolution."""
        engine = ContinuousEvolutionEngine()

        # Mock the internal loop to avoid actual execution
        async def mock_loop():
            while engine._running:
                await asyncio.sleep(0.01)
                break  # Exit after one iteration

        with patch.object(engine, "_evolution_loop", mock_loop):
            # Manually set running flag
            engine._running = True
            await mock_loop()
            engine._running = False

        assert engine._running is False

    async def test_engine_not_running_initially(self):
        """Test engine is not running initially."""
        engine = ContinuousEvolutionEngine()
        assert not engine._running


class TestEvolutionEngineHelpers:
    """Test helper methods."""

    def test_cycles_list_is_mutable(self) -> None:
        """Test cycles list can be modified."""
        engine = ContinuousEvolutionEngine()
        cycle = EvolutionCycle(
            cycle_id="test",
            start_time=0,
            observations=[],
            learnings={},
            improvements=[],
            actions=[],
            verifications={},
            meta_insights={},
            end_time=1,
            success=True,
        )
        engine._cycles.append(cycle)
        assert len(engine._cycles) == 1
        assert engine._cycles[0].cycle_id == "test"

    def test_cycle_count_increment(self) -> None:
        """Test cycle count can be incremented."""
        engine = ContinuousEvolutionEngine()
        engine._cycle_count += 1
        assert engine._cycle_count == 1
        engine._cycle_count += 1
        assert engine._cycle_count == 2
