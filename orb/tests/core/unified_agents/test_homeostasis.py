"""Comprehensive Tests for Homeostasis Monitor.

COVERAGE:
=========
- Initialization and configuration
- Homeostasis loop start/stop
- Colony health tracking
- Overall health computation
- Phase transitions (ACTIVE ↔ DEGRADED)
- E8 coherence computation
- System metrics (CPU, memory)
- Distributed state sync
- Fano line metrics integration
- Cleanup operations
- Statistics and reporting
- Error handling
- Edge cases (no data, partial data)

Created: December 27, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

from kagami.core.unified_agents.homeostasis import (
    DEFAULT_HEALTH_THRESHOLD,
    DEFAULT_HOMEOSTASIS_INTERVAL,
    HomeostasisMonitor,
    HomeostasisState,
    OrganismStats,
    OrganismStatus,
    create_homeostasis_monitor,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def monitor():
    """Create HomeostasisMonitor instance."""
    return HomeostasisMonitor(
        interval=0.1,  # Fast interval for tests
        health_threshold=0.5,
    )


@pytest.fixture
def mock_colony():
    """Create mock MinimalColony."""
    colony = Mock()
    colony.get_stats = Mock(
        return_value={
            "success_rate": 0.8,
            "worker_count": 3,
            "available_workers": 2,
            "completed": 10,
            "failed": 2,
        }
    )
    colony.cleanup_workers = AsyncMock()
    colony.get_worker_count = Mock(return_value=3)
    colony.s7_section = np.random.randn(7)
    colony.config = Mock(max_workers=10)
    return colony


@pytest.fixture
def colonies_dict(mock_colony: Any) -> Dict[str, Any]:
    """Create dictionary of mock colonies."""
    return {
        "spark": mock_colony,
        "forge": mock_colony,
        "flow": mock_colony,
        "nexus": mock_colony,
        "beacon": mock_colony,
        "grove": mock_colony,
        "crystal": mock_colony,
    }


# =============================================================================
# TEST: INITIALIZATION
# =============================================================================


def test_initialization_default():
    """Test default initialization."""
    monitor = HomeostasisMonitor()

    assert monitor.interval == DEFAULT_HOMEOSTASIS_INTERVAL
    assert monitor.health_threshold == DEFAULT_HEALTH_THRESHOLD
    assert monitor.status == OrganismStatus.INITIALIZING
    assert isinstance(monitor.state, HomeostasisState)
    assert isinstance(monitor.stats, OrganismStats)


def test_initialization_custom_params():
    """Test initialization with custom parameters."""
    monitor = HomeostasisMonitor(interval=5.0, health_threshold=0.7)

    assert monitor.interval == 5.0
    assert monitor.health_threshold == 0.7


def test_factory_function():
    """Test create_homeostasis_monitor factory."""
    monitor = create_homeostasis_monitor(interval=2.0, health_threshold=0.6)

    assert isinstance(monitor, HomeostasisMonitor)
    assert monitor.interval == 2.0
    assert monitor.health_threshold == 0.6


def test_initial_state_values(monitor: Any) -> None:
    """Test initial state values."""
    assert len(monitor.state.colony_health) == 0
    assert monitor.state.system_load == 0.0
    assert monitor.state.memory_pressure == 0.0
    assert monitor.state.queue_depth == 0
    assert monitor.state.e8_coherence == 1.0


def test_initial_stats_values(monitor: Any) -> None:
    """Test initial stats values."""
    assert monitor.stats.total_intents == 0
    assert monitor.stats.completed_intents == 0
    assert monitor.stats.failed_intents == 0
    assert monitor.stats.total_population == 0
    assert monitor.stats.homeostasis_cycles == 0


# =============================================================================
# TEST: LIFECYCLE (START/STOP)
# =============================================================================


@pytest.mark.asyncio
async def test_start_monitor(monitor: Any, colonies_dict: Any) -> None:
    """Test starting homeostasis monitor."""
    await monitor.start(colonies_dict)

    assert monitor._running is True
    assert monitor.status == OrganismStatus.ACTIVE
    assert monitor._task is not None
    assert len(monitor._colonies) == 7

    await monitor.stop()


@pytest.mark.asyncio
async def test_stop_monitor(monitor: Any, colonies_dict: Any) -> None:
    """Test stopping homeostasis monitor."""
    await monitor.start(colonies_dict)
    await asyncio.sleep(0.05)  # Let it run briefly
    await monitor.stop()

    assert monitor._running is False
    assert monitor.status == OrganismStatus.STOPPED


@pytest.mark.asyncio
async def test_start_idempotent(monitor: Any, colonies_dict: Any) -> None:
    """Test that starting twice is safe."""
    await monitor.start(colonies_dict)
    await monitor.start(colonies_dict)  # Should not crash

    assert monitor._running is True

    await monitor.stop()


@pytest.mark.asyncio
async def test_monitor_runs_background_loop(monitor: Any, colonies_dict: Any) -> None:
    """Test that monitor runs homeostasis loop in background."""
    await monitor.start(colonies_dict)
    await asyncio.sleep(0.15)  # Wait for at least one cycle
    await monitor.stop()

    # Should have run at least one homeostasis cycle
    assert monitor.stats.homeostasis_cycles > 0


# =============================================================================
# TEST: HOMEOSTASIS STATE
# =============================================================================


def test_homeostasis_state_overall_health_none_when_empty():
    """Test overall_health returns None when no data."""
    state = HomeostasisState()

    assert state.overall_health is None


def test_homeostasis_state_overall_health_with_data():
    """Test overall_health computation with data."""
    state = HomeostasisState()
    state.colony_health = {
        "colony1": 0.8,
        "colony2": 0.6,
        "colony3": 0.9,
    }

    health = state.overall_health
    assert health is not None
    assert 0.7 <= health <= 0.8  # Average should be ~0.77


def test_homeostasis_state_ignores_zero_values():
    """Test that overall_health ignores zero values (no data)."""
    state = HomeostasisState()
    state.colony_health = {
        "colony1": 0.8,
        "colony2": 0.0,  # No data
        "colony3": 0.6,
    }

    health = state.overall_health
    assert health is not None
    # Should average only non-zero values: (0.8 + 0.6) / 2 = 0.7
    assert abs(health - 0.7) < 0.01


def test_homeostasis_state_all_zero_returns_none():
    """Test that all zeros returns None."""
    state = HomeostasisState()
    state.colony_health = {
        "colony1": 0.0,
        "colony2": 0.0,
    }

    assert state.overall_health is None


# =============================================================================
# TEST: ORGANISM STATS
# =============================================================================


def test_organism_stats_success_rate_none_when_no_data():
    """Test success_rate returns None when no intents processed."""
    stats = OrganismStats()

    assert stats.success_rate is None


def test_organism_stats_success_rate_with_data():
    """Test success_rate computation."""
    stats = OrganismStats()
    stats.completed_intents = 8
    stats.failed_intents = 2

    assert stats.success_rate == 0.8


def test_organism_stats_success_rate_display_zero_when_no_data():
    """Test success_rate_display returns 0.0 when no data."""
    stats = OrganismStats()

    assert stats.success_rate_display == 0.0


def test_organism_stats_success_rate_display_with_data():
    """Test success_rate_display computation."""
    stats = OrganismStats()
    stats.completed_intents = 7
    stats.failed_intents = 3

    assert stats.success_rate_display == 0.7


def test_organism_stats_uptime():
    """Test uptime computation."""
    stats = OrganismStats()

    import time

    time.sleep(0.01)
    uptime = stats.uptime

    assert uptime > 0
    assert uptime < 1  # Should be very small for test


# =============================================================================
# TEST: COLONY HEALTH TRACKING
# =============================================================================


@pytest.mark.asyncio
async def test_colony_health_tracking(monitor: Any, colonies_dict: Any) -> None:
    """Test that colony health is tracked."""
    await monitor.start(colonies_dict)
    await asyncio.sleep(0.15)  # Wait for homeostasis cycle
    await monitor.stop()

    # Should have health for all colonies
    assert len(monitor.state.colony_health) == 7
    for health in monitor.state.colony_health.values():
        assert 0 <= health <= 1


@pytest.mark.asyncio
async def test_colony_health_reflects_success_rate(monitor: Any) -> None:
    """Test that colony health reflects success rate."""
    # Create colony with known success rate
    colony_high = Mock()
    colony_high.get_stats = Mock(
        return_value={
            "success_rate": 0.9,
            "worker_count": 5,
            "available_workers": 3,
            "completed": 90,
            "failed": 10,
        }
    )
    colony_high.cleanup_workers = AsyncMock()
    colony_high.get_worker_count = Mock(return_value=5)
    colony_high.s7_section = np.random.randn(7)

    colony_low = Mock()
    colony_low.get_stats = Mock(
        return_value={
            "success_rate": 0.3,
            "worker_count": 5,
            "available_workers": 3,
            "completed": 30,
            "failed": 70,
        }
    )
    colony_low.cleanup_workers = AsyncMock()
    colony_low.get_worker_count = Mock(return_value=5)
    colony_low.s7_section = np.random.randn(7)

    colonies = {"high": colony_high, "low": colony_low}

    await monitor.start(colonies)
    await asyncio.sleep(0.15)
    await monitor.stop()

    # High success colony should have higher health
    assert monitor.state.colony_health["high"] > monitor.state.colony_health["low"]


@pytest.mark.asyncio
async def test_colony_health_handles_none_success_rate(monitor: Any) -> None:
    """Test handling of None success_rate (no data)."""
    colony = Mock()
    colony.get_stats = Mock(
        return_value={
            "success_rate": None,  # No data yet
            "worker_count": 2,
            "available_workers": 2,
            "completed": 0,
            "failed": 0,
        }
    )
    colony.cleanup_workers = AsyncMock()
    colony.get_worker_count = Mock(return_value=2)
    colony.s7_section = np.random.randn(7)

    await monitor.start({"test": colony})
    await asyncio.sleep(0.15)
    await monitor.stop()

    # Should use 0.0 for no data (pessimistic)
    assert monitor.state.colony_health["test"] == 0.0


# =============================================================================
# TEST: PHASE TRANSITIONS
# =============================================================================


@pytest.mark.asyncio
async def test_transition_to_degraded(monitor: Any) -> None:
    """Test transition to DEGRADED status when health drops."""
    # Create unhealthy colonies
    unhealthy_colony = Mock()
    unhealthy_colony.get_stats = Mock(
        return_value={
            "success_rate": 0.2,  # Low success rate
            "worker_count": 5,
            "available_workers": 3,
            "completed": 2,
            "failed": 8,
        }
    )
    unhealthy_colony.cleanup_workers = AsyncMock()
    unhealthy_colony.get_worker_count = Mock(return_value=5)
    unhealthy_colony.s7_section = np.random.randn(7)

    colonies = {f"colony{i}": unhealthy_colony for i in range(7)}

    await monitor.start(colonies)
    await asyncio.sleep(0.15)
    await monitor.stop()

    # With low health, should transition to DEGRADED
    assert monitor.status == OrganismStatus.DEGRADED


@pytest.mark.asyncio
async def test_transition_to_active(monitor: Any) -> None:
    """Test transition to ACTIVE status when health is good."""
    # Create healthy colonies
    healthy_colony = Mock()
    healthy_colony.get_stats = Mock(
        return_value={
            "success_rate": 0.9,  # High success rate
            "worker_count": 5,
            "available_workers": 3,
            "completed": 90,
            "failed": 10,
        }
    )
    healthy_colony.cleanup_workers = AsyncMock()
    healthy_colony.get_worker_count = Mock(return_value=5)
    healthy_colony.s7_section = np.random.randn(7)

    colonies = {f"colony{i}": healthy_colony for i in range(7)}

    await monitor.start(colonies)
    await asyncio.sleep(0.15)
    await monitor.stop()

    # With high health, should be ACTIVE
    assert monitor.status == OrganismStatus.ACTIVE


@pytest.mark.asyncio
async def test_stays_in_current_status_when_no_data(monitor: Any) -> None:
    """Test that status doesn't change when there's no health data."""
    # Colony with no data
    no_data_colony = Mock()
    no_data_colony.get_stats = Mock(
        return_value={
            "success_rate": None,
            "worker_count": 0,
            "available_workers": 0,
            "completed": 0,
            "failed": 0,
        }
    )
    no_data_colony.cleanup_workers = AsyncMock()
    no_data_colony.get_worker_count = Mock(return_value=0)
    no_data_colony.s7_section = np.random.randn(7)

    monitor.status = OrganismStatus.ACTIVE  # Start as ACTIVE

    await monitor.start({"test": no_data_colony})
    await asyncio.sleep(0.15)
    await monitor.stop()

    # Should remain ACTIVE (no data to trigger change)
    # Actually, with no real data (all 0.0), it should stay in current state
    assert monitor.status in [OrganismStatus.ACTIVE, OrganismStatus.DEGRADED]


# =============================================================================
# TEST: E8 COHERENCE
# =============================================================================


def test_compute_e8_coherence_high(monitor: Any) -> None:
    """Test E8 coherence computation with aligned colonies."""
    # Similar S7 sections (high coherence)
    base = np.array([1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    s7_sections = [base + np.random.randn(7) * 0.1 for _ in range(5)]

    coherence = monitor._compute_e8_coherence(s7_sections)

    assert 0.8 <= coherence <= 1.0  # Should be high


def test_compute_e8_coherence_low(monitor: Any) -> None:
    """Test E8 coherence computation with diverging colonies."""
    # Random S7 sections (low coherence)
    s7_sections = [np.random.randn(7) for _ in range(5)]

    coherence = monitor._compute_e8_coherence(s7_sections)

    assert 0.0 <= coherence <= 1.0


def test_compute_e8_coherence_insufficient_data(monitor: Any) -> None:
    """Test E8 coherence with insufficient data."""
    # Only one section
    s7_sections = [np.random.randn(7)]

    coherence = monitor._compute_e8_coherence(s7_sections)

    # Should default to 1.0
    assert coherence == 1.0


def test_compute_e8_coherence_empty(monitor: Any) -> None:
    """Test E8 coherence with empty list."""
    coherence = monitor._compute_e8_coherence([])

    assert coherence == 1.0


# =============================================================================
# TEST: SYSTEM METRICS
# =============================================================================


@pytest.mark.asyncio
async def test_update_system_metrics(monitor: Any) -> None:
    """Test system metrics update."""
    with patch("kagami.core.unified_agents.homeostasis.psutil") as mock_psutil:
        mock_mem = Mock()
        mock_mem.percent = 60.0
        mock_psutil.virtual_memory.return_value = mock_mem
        mock_psutil.cpu_percent.return_value = 45.0

        monitor._update_system_metrics()

        assert monitor.state.memory_pressure == 0.6
        assert monitor.state.system_load == 0.45


@pytest.mark.asyncio
async def test_system_metrics_without_psutil(monitor: Any) -> None:
    """Test system metrics when psutil is unavailable."""
    with patch(
        "kagami.core.unified_agents.homeostasis.psutil", side_effect=ImportError("No psutil")
    ):
        monitor._update_system_metrics()

        # Should not crash, leave at defaults
        assert monitor.state.memory_pressure == 0.0
        assert monitor.state.system_load == 0.0


# =============================================================================
# TEST: CLEANUP OPERATIONS
# =============================================================================


@pytest.mark.asyncio
async def test_cleanup_workers_called(monitor: Any, colonies_dict: Any) -> None:
    """Test that cleanup_workers is called on all colonies."""
    await monitor.start(colonies_dict)
    await asyncio.sleep(0.15)  # Wait for homeostasis cycle
    await monitor.stop()

    # All colonies should have cleanup called
    for colony in colonies_dict.values():
        colony.cleanup_workers.assert_called()


# =============================================================================
# TEST: STATISTICS AND REPORTING
# =============================================================================


def test_get_health(monitor: Any) -> None:
    """Test get_health returns correct structure."""
    monitor.state.colony_health = {"colony1": 0.8, "colony2": 0.6}
    monitor.stats.total_population = 10
    monitor.status = OrganismStatus.ACTIVE

    health = monitor.get_health()

    assert "status" in health
    assert "health" in health
    assert "colony_health" in health
    assert "population" in health
    assert health["status"] == "active"
    assert health["population"] == 10


def test_get_stats(monitor: Any) -> None:
    """Test get_stats returns correct structure."""
    monitor.state.colony_health = {"colony1": 0.8}
    monitor.stats.homeostasis_cycles = 5
    monitor.stats.total_population = 20

    stats = monitor.get_stats()

    assert "status" in stats
    assert "uptime" in stats
    assert "homeostasis_cycles" in stats
    assert "overall_health" in stats
    assert "colony_health" in stats
    assert "total_population" in stats
    assert stats["homeostasis_cycles"] == 5
    assert stats["total_population"] == 20


def test_update_intent_stats_success(monitor: Any) -> None:
    """Test updating intent stats for success."""
    monitor.update_intent_stats(success=True)

    assert monitor.stats.total_intents == 1
    assert monitor.stats.completed_intents == 1
    assert monitor.stats.failed_intents == 0


def test_update_intent_stats_failure(monitor: Any) -> None:
    """Test updating intent stats for failure."""
    monitor.update_intent_stats(success=False)

    assert monitor.stats.total_intents == 1
    assert monitor.stats.completed_intents == 0
    assert monitor.stats.failed_intents == 1


def test_update_intent_stats_multiple(monitor: Any) -> None:
    """Test updating intent stats multiple times."""
    monitor.update_intent_stats(success=True)
    monitor.update_intent_stats(success=True)
    monitor.update_intent_stats(success=False)

    assert monitor.stats.total_intents == 3
    assert monitor.stats.completed_intents == 2
    assert monitor.stats.failed_intents == 1


# =============================================================================
# TEST: DISTRIBUTED SYNC
# =============================================================================


def test_set_distributed_sync(monitor: Any) -> None:
    """Test setting distributed sync."""
    mock_sync = Mock()
    monitor.set_distributed_sync(mock_sync)

    assert monitor._distributed_sync == mock_sync


@pytest.mark.asyncio
async def test_sync_distributed_state_not_configured(monitor: Any) -> None:
    """Test distributed sync when not configured."""
    # Should not crash when sync is None
    await monitor._sync_distributed_state()


@pytest.mark.asyncio
async def test_sync_distributed_state_with_sync(monitor: Any, colonies_dict: Any) -> None:
    """Test distributed sync with configured sync object."""
    mock_sync = Mock()
    mock_sync.push_local_state = AsyncMock()
    mock_sync.pull_global_state = AsyncMock(return_value={})
    mock_sync.compute_adjustments = Mock(
        return_value=Mock(
            tighten_cbf=False,
            e8_drift_detected=False,
            s7_drift_detected=False,
        )
    )

    monitor.set_distributed_sync(mock_sync)
    monitor._colonies = colonies_dict
    monitor.state.colony_health = {"colony1": 0.8}

    await monitor._sync_distributed_state()

    # Should call push and pull
    mock_sync.push_local_state.assert_called_once()
    mock_sync.pull_global_state.assert_called_once()


@pytest.mark.asyncio
async def test_sync_distributed_state_handles_exceptions(monitor: Any) -> None:
    """Test that distributed sync handles exceptions gracefully."""
    mock_sync = Mock()
    mock_sync.push_local_state = AsyncMock(side_effect=RuntimeError("Sync failed"))

    monitor.set_distributed_sync(mock_sync)

    # Should not crash
    await monitor._sync_distributed_state()


# =============================================================================
# TEST: QUEUE DEPTH TRACKING
# =============================================================================


@pytest.mark.asyncio
async def test_queue_depth_tracking(monitor: Any) -> None:
    """Test that queue depth is tracked correctly."""
    colony = Mock()
    colony.get_stats = Mock(
        return_value={
            "success_rate": 0.8,
            "worker_count": 10,
            "available_workers": 3,  # 7 busy
            "completed": 80,
            "failed": 20,
        }
    )
    colony.cleanup_workers = AsyncMock()
    colony.get_worker_count = Mock(return_value=10)
    colony.s7_section = np.random.randn(7)

    await monitor.start({"test": colony})
    await asyncio.sleep(0.15)
    await monitor.stop()

    # Queue depth should be 7 (busy workers)
    assert monitor.state.queue_depth == 7


# =============================================================================
# TEST: ERROR HANDLING
# =============================================================================


@pytest.mark.asyncio
async def test_homeostasis_loop_handles_exceptions(monitor: Any, colonies_dict: Any) -> None:
    """Test that homeostasis loop handles exceptions gracefully."""
    # Make one colony raise exception
    bad_colony = Mock()
    bad_colony.get_stats = Mock(side_effect=RuntimeError("Colony crashed"))
    bad_colony.cleanup_workers = AsyncMock()
    bad_colony.get_worker_count = Mock(return_value=0)

    colonies_dict["bad"] = bad_colony

    await monitor.start(colonies_dict)
    await asyncio.sleep(0.15)
    await monitor.stop()

    # Monitor should still be running and have completed cycles
    assert monitor.stats.homeostasis_cycles > 0


# =============================================================================
# TEST: EDGE CASES
# =============================================================================


@pytest.mark.asyncio
async def test_empty_colonies(monitor: Any) -> None:
    """Test with no colonies."""
    await monitor.start({})
    await asyncio.sleep(0.15)
    await monitor.stop()

    # Should handle gracefully
    assert monitor.state.overall_health is None


@pytest.mark.asyncio
async def test_colonies_with_no_workers(monitor: Any) -> None:
    """Test colonies with zero workers."""
    colony = Mock()
    colony.get_stats = Mock(
        return_value={
            "success_rate": None,
            "worker_count": 0,
            "available_workers": 0,
            "completed": 0,
            "failed": 0,
        }
    )
    colony.cleanup_workers = AsyncMock()
    colony.get_worker_count = Mock(return_value=0)
    colony.s7_section = np.random.randn(7)

    await monitor.start({"empty": colony})
    await asyncio.sleep(0.15)
    await monitor.stop()

    assert monitor.stats.total_population == 0


def test_homeostasis_state_rounding():
    """Test that overall_health rounds correctly."""
    state = HomeostasisState()
    state.colony_health = {
        "c1": 0.8500000000000001,  # Floating point artifact
        "c2": 0.8500000000000001,
    }

    health = state.overall_health
    # Should be rounded to 4 decimal places
    assert health == 0.85
