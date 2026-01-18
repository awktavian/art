"""Homeostasis Monitor - System Health and Balance Management.

Monitors organism health, manages population balance, and triggers
corrective actions to maintain homeostatic equilibrium.

HOMEOSTASIS LOOP:
=================
Every N seconds (configurable):
1. Check colony health (success rates)
2. Track population levels
3. Compute overall system health
4. Trigger adjustments if needed
5. Cleanup retired workers

HEALTH METRICS:
===============
- Colony health: Per-colony success rate
- System load: CPU/memory pressure
- Memory pressure: Memory usage
- Queue depth: Pending task count
- E8 coherence: Colony alignment measure
- Overall health: Weighted average of all metrics

DEGRADATION HANDLING:
=====================
When overall_health < threshold:
- Status → DEGRADED
- Emit warning
- Optionally spawn new workers
- Optionally reduce task load

Created: December 14, 2025
Extracted from: unified_organism.py (refactor)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.unified_agents.minimal_colony import MinimalColony

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Default homeostasis interval (seconds)
# OPTIMIZED (Dec 21, 2025): Reduced from 60s to 30s for faster responsiveness
# OPTIMIZED (Dec 27, 2025): Reduced to 1s for real-time adaptation
DEFAULT_HOMEOSTASIS_INTERVAL = 1.0

# Health thresholds
DEFAULT_HEALTH_THRESHOLD = 0.5  # Below = DEGRADED


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class OrganismStatus(Enum):
    """Organism lifecycle status."""

    INITIALIZING = "initializing"
    ACTIVE = "active"
    DEGRADED = "degraded"
    HIBERNATING = "hibernating"
    STOPPED = "stopped"


@dataclass
class HomeostasisState:
    """Current homeostasis state."""

    # Per-colony health
    colony_health: dict[str, float] = field(default_factory=dict[str, Any])

    # System-wide metrics
    system_load: float = 0.0
    memory_pressure: float = 0.0
    queue_depth: int = 0

    # E8 coherence (how well-aligned are colony outputs)
    e8_coherence: float = 1.0

    @property
    def overall_health(self) -> float | None:
        """Compute overall system health. Returns None if no data."""
        if not self.colony_health:
            return None  # No data, not fake 1.0
        # Filter out zero values that indicate "no data" colonies
        real_values = [v for v in self.colony_health.values() if v > 0]
        if not real_values:
            return None  # All colonies have no data
        # NOTE: Float math can produce tiny representation artifacts (e.g. 0.8500000000000001).
        # We round to keep health signals stable for UI/tests while preserving usable precision.
        return round(sum(real_values) / len(real_values), 4)


@dataclass
class OrganismStats:
    """Organism-wide statistics."""

    total_intents: int = 0
    completed_intents: int = 0
    failed_intents: int = 0

    total_population: int = 0
    active_colonies: int = 0

    homeostasis_cycles: int = 0
    last_homeostasis: float = 0.0

    created_at: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float | None:
        """Return actual success rate, or None if no intents processed yet."""
        total = self.completed_intents + self.failed_intents
        return self.completed_intents / total if total > 0 else None

    @property
    def success_rate_display(self) -> float:
        """Return success rate for display (0.0 if no data, never fake 0.5)."""
        total = self.completed_intents + self.failed_intents
        return self.completed_intents / total if total > 0 else 0.0

    @property
    def uptime(self) -> float:
        return time.time() - self.created_at


# =============================================================================
# HOMEOSTASIS MONITOR
# =============================================================================


class HomeostasisMonitor:
    """Monitors organism health and triggers homeostatic adjustments.

    Runs a background loop that:
    1. Tracks colony health metrics
    2. Computes overall system health
    3. Triggers status changes (ACTIVE → DEGRADED)
    4. Performs cleanup (retired workers)
    """

    def __init__(
        self,
        interval: float = DEFAULT_HOMEOSTASIS_INTERVAL,
        health_threshold: float = DEFAULT_HEALTH_THRESHOLD,
    ):
        """Initialize homeostasis monitor.

        Args:
            interval: Check interval in seconds
            health_threshold: Threshold for DEGRADED status
        """
        self.interval = interval
        self.health_threshold = health_threshold

        # State
        self.state = HomeostasisState()
        self.stats = OrganismStats()
        self.status = OrganismStatus.INITIALIZING

        # Background task
        self._task: asyncio.Task | None = None
        self._running = False
        self._lock = asyncio.Lock()

        # Colonies (injected)
        self._colonies: dict[str, MinimalColony] = {}

        # Distributed sync (optional, wired by boot/actions/wiring.py)
        self._distributed_sync: Any = None

    # =========================================================================
    # LIFECYCLE
    # =========================================================================

    async def start(self, colonies: dict[str, MinimalColony]) -> None:
        """Start homeostasis loop.

        Args:
            colonies: Dictionary of colony_name → MinimalColony
        """
        if self._running:
            return

        self._colonies = colonies
        self._running = True
        self.status = OrganismStatus.ACTIVE

        # Start background loop
        self._task = asyncio.create_task(self._homeostasis_loop())

        logger.info(f"🏥 Homeostasis monitor started (interval={self.interval}s)")

    async def stop(self) -> None:
        """Stop homeostasis loop."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self.status = OrganismStatus.STOPPED
        logger.info("🛑 Homeostasis monitor stopped")

    def set_distributed_sync(self, sync: Any) -> None:
        """Set distributed homeostasis sync.

        Enables multi-instance coordination via etcd.

        Args:
            sync: EtcdHomeostasisSync instance
        """
        self._distributed_sync = sync
        logger.debug("Distributed homeostasis sync attached")

    # =========================================================================
    # HOMEOSTASIS LOOP
    # =========================================================================

    async def _homeostasis_loop(self) -> None:
        """Background homeostasis loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                await self._run_homeostasis()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Homeostasis error: {e}")

    async def _run_homeostasis(self) -> None:
        """Run homeostasis check."""
        import time as time_module

        start_time = time_module.perf_counter()

        async with self._lock:
            self.stats.homeostasis_cycles += 1
            self.stats.last_homeostasis = time.time()

            # Update system-level metrics (Dec 24, 2025)
            self._update_system_metrics()

            # Update colony health and collect S7 sections for E8 coherence
            total_population = 0
            total_queue_depth = 0
            s7_sections = []

            for name, colony in self._colonies.items():
                colony_stats = colony.get_stats()
                # REAL VALUES ONLY - None means no data
                raw_success_rate = colony_stats["success_rate"]
                # For health tracking, use 0.0 if no data (honest pessimism)
                self.state.colony_health[name] = (
                    raw_success_rate if raw_success_rate is not None else 0.0
                )
                total_population += colony_stats["worker_count"]
                # Queue depth = busy workers (worker_count - available_workers)
                busy_workers = colony_stats["worker_count"] - colony_stats.get(
                    "available_workers", 0
                )
                total_queue_depth += max(0, busy_workers)

                # Collect S7 section for E8 coherence computation
                if hasattr(colony, "s7_section"):
                    s7_sections.append(colony.s7_section)

                # Emit colony metrics (Dec 21, 2025 - Forge) - REAL VALUES ONLY
                try:
                    from kagami_observability.metrics.colony import update_colony_metrics

                    # Use display rate (0.0 if no data, not fake 0.5)
                    display_rate = raw_success_rate if raw_success_rate is not None else 0.0
                    update_colony_metrics(
                        domain=name,
                        population=colony_stats.get("worker_count", 0),
                        max_population=colony.config.max_workers
                        if hasattr(colony, "config")
                        else 10,
                        avg_workload=1.0 - display_rate,  # Proxy
                        tasks_completed=colony_stats.get("completed", 0),
                        tasks_failed=colony_stats.get("failed", 0),
                        mitosis_events=0,  # Not tracked in MinimalColony
                        apoptosis_events=0,
                        max_generation=0,
                        avg_generation=0.0,
                        health_score=4
                        if display_rate > 0.8
                        else (3 if raw_success_rate is not None else 0),
                        resource_util=display_rate,
                    )
                except Exception as e:
                    logger.debug(f"Colony metrics emission failed for {name}: {e}")

            self.stats.total_population = total_population
            self.state.queue_depth = total_queue_depth

            # Compute E8 coherence from S7 sections (Dec 21, 2025 - Forge)
            # E8 coherence measures alignment of colony outputs via cosine similarity
            self.state.e8_coherence = self._compute_e8_coherence(s7_sections)

            # Check overall health - handle None gracefully (no data yet)
            health = self.state.overall_health
            if health is None:
                # No data yet - stay in current status, don't change
                logger.debug("Homeostasis: No health data yet, maintaining current status")
            elif health < self.health_threshold:
                self.status = OrganismStatus.DEGRADED
                logger.warning(f"⚠️ System health degraded: {health:.2f}")
            else:
                self.status = OrganismStatus.ACTIVE

            # Cleanup retired workers in parallel
            await asyncio.gather(
                *[colony.cleanup_workers() for colony in self._colonies.values()],
                return_exceptions=True,
            )

            # Emit homeostasis cycle metrics
            try:
                from kagami_observability.metrics.colony import (
                    HOMEOSTASIS_CYCLES_TOTAL,
                    HOMEOSTASIS_DURATION_MS,
                    update_organism_aggregates,
                )

                HOMEOSTASIS_CYCLES_TOTAL.inc()
                duration_ms = (time_module.perf_counter() - start_time) * 1000
                HOMEOSTASIS_DURATION_MS.set(duration_ms)

                update_organism_aggregates(
                    total_colonies=len(self._colonies),
                    total_agents=total_population,
                    max_agents=len(self._colonies) * 10,  # Default max
                    growth_rate=0.0,  # Not tracked
                    homeostasis_interval=self.interval,
                )
            except Exception as e:
                logger.debug(f"Homeostasis metrics emission failed: {e}")

            # Distributed sync: push local state and apply adjustments (Dec 26, 2025)
            await self._sync_distributed_state()

            # Publish to E8 bus for Slack presence (Jan 5, 2026)
            await self._publish_to_e8_bus()

    async def _sync_distributed_state(self) -> None:
        """Sync state with distributed homeostasis via etcd.

        Pushes local state to etcd and pulls global adjustments.
        This enables multi-instance coordination.

        Dec 26, 2025: Wired to EtcdHomeostasisSync.
        """
        if self._distributed_sync is None:
            return

        try:
            # Gather local state for push
            population = {
                name: colony.get_worker_count() for name, colony in self._colonies.items()
            }

            vitals = {
                "system_load": self.state.system_load,
                "memory_pressure": self.state.memory_pressure,
                "e8_coherence": self.state.e8_coherence,
            }

            pheromones = {name: self.state.colony_health.get(name, 0.0) for name in self._colonies}

            # Compute catastrophe risk from health (low health = high risk)
            catastrophe_risk = {
                name: max(0.0, 1.0 - health) for name, health in self.state.colony_health.items()
            }

            # Collect S7 sections for consensus
            s7_phases = []
            for colony in self._colonies.values():
                if hasattr(colony, "s7_section"):
                    s7_phases.extend(colony.s7_section.tolist())
            s7_phase = s7_phases[:7] if s7_phases else []

            # Push local state
            await self._distributed_sync.push_local_state(
                population=population,
                vitals=vitals,
                pheromones=pheromones,
                catastrophe_risk=catastrophe_risk,
                e8_code=[],  # E8 code not tracked at colony level
                s7_phase=s7_phase,
                homeostasis_interval=self.interval,
            )

            # Pull global state and compute adjustments
            global_state = await self._distributed_sync.pull_global_state()
            adjustments = self._distributed_sync.compute_adjustments(global_state)

            # Apply adjustments
            if adjustments.tighten_cbf:
                logger.info("Tightening CBF margins per global catastrophe risk")

            if adjustments.e8_drift_detected:
                logger.info(
                    f"E8 drift detected: local differs from consensus "
                    f"(confidence={adjustments.consensus_confidence:.1%})"
                )

            if adjustments.s7_drift_detected:
                logger.info(
                    f"S7 drift detected: angular deviation={adjustments.s7_angular_deviation:.2f} rad"
                )

        except Exception as e:
            logger.debug(f"Distributed sync failed: {e}")

    async def _publish_to_e8_bus(self) -> None:
        """Publish organism status to E8 bus for Slack presence sync.

        Publishes organism.status events that the SlackBridge picks up
        and reflects to Slack channels.

        Jan 5, 2026: Added for real-time Slack presence.
        """
        try:
            from kagami.core.events.unified_e8_bus import get_unified_bus

            bus = get_unified_bus()

            # Get active colonies (those with activity)
            active_colonies = [
                name
                for name, health in self.state.colony_health.items()
                if health > 0.3  # Active if health > 30%
            ]

            # Compute safety score (inverse of catastrophe risk)
            # Based on overall health and system load
            overall_health = self.state.overall_health or 0.85
            safety = max(0.0, min(1.0, overall_health - self.state.system_load * 0.3))

            # Publish status event
            await bus.publish(
                "organism.status",
                {
                    "safety": round(safety, 3),
                    "load": round(self.state.system_load, 3),
                    "memory": round(self.state.memory_pressure, 3),
                    "e8_coherence": round(self.state.e8_coherence, 3),
                    "active_colonies": active_colonies,
                    "status": self.status.value,
                    "population": self.stats.total_population,
                    "queue_depth": self.state.queue_depth,
                },
            )

        except Exception as e:
            logger.debug(f"E8 bus publish failed: {e}")

    def _update_system_metrics(self) -> None:
        """Update system-level resource metrics.

        Populates system_load and memory_pressure fields using psutil.
        These were previously left unpopulated (always 0.0).

        Dec 24, 2025: Added per feedback on resource monitoring integration.
        """
        try:
            import psutil

            # Memory pressure: percentage of RAM used [0, 1]
            mem = psutil.virtual_memory()
            self.state.memory_pressure = mem.percent / 100.0

            # System load: average CPU utilization across cores [0, 1]
            # Using 1-second interval for responsiveness
            cpu_percent = psutil.cpu_percent(interval=None)  # Non-blocking
            if cpu_percent is not None:
                self.state.system_load = cpu_percent / 100.0
            else:
                # First call returns None, use 0.0
                self.state.system_load = 0.0  # type: ignore[unreachable]

        except ImportError:
            # psutil not available, leave at defaults
            logger.debug("psutil not available for system metrics")
        except Exception as e:
            logger.debug(f"Failed to update system metrics: {e}")

    def _compute_e8_coherence(self, s7_sections: list[Any]) -> float:
        """Compute E8 coherence from colony S7 sections.

        E8 coherence measures how well-aligned colony outputs are.
        Uses average pairwise cosine similarity of S7 unit vectors.

        High coherence (→1.0): Colonies aligned, coordinated behavior
        Low coherence (→0.0): Colonies diverging, potential jamming

        Args:
            s7_sections: List of S7 unit vectors from colonies

        Returns:
            E8 coherence score [0.0, 1.0]
        """
        if len(s7_sections) < 2:
            return 1.0  # Default to coherent if insufficient data

        try:
            import numpy as np

            # Convert to numpy arrays if needed
            sections = [np.asarray(s, dtype=np.float32) for s in s7_sections]

            # Compute pairwise cosine similarities
            similarities = []
            for i, s1 in enumerate(sections):
                for s2 in sections[i + 1 :]:
                    # Cosine similarity: dot(a, b) / (||a|| * ||b||)
                    norm1 = np.linalg.norm(s1)
                    norm2 = np.linalg.norm(s2)
                    if norm1 > 0 and norm2 > 0:
                        sim = np.dot(s1, s2) / (norm1 * norm2)
                        similarities.append(float(sim))

            if not similarities:
                return 1.0

            # E8 coherence = average cosine similarity
            # Map from [-1, 1] to [0, 1] range
            avg_sim = np.mean(similarities)
            coherence = (avg_sim + 1.0) / 2.0

            return round(float(coherence), 4)

        except Exception as e:
            logger.debug(f"E8 coherence computation failed: {e}")
            return 1.0  # Default to coherent on error

    # =========================================================================
    # API
    # =========================================================================

    def get_health(self) -> dict[str, Any]:
        """Get current health status.

        Returns:
            Health status dictionary
        """
        return {
            "status": self.status.value,
            "health": self.state.overall_health,
            "colony_health": self.state.colony_health,
            "population": self.stats.total_population,
        }

    def get_stats(self) -> dict[str, Any]:
        """Get homeostasis statistics.

        Returns:
            Stats dictionary
        """
        return {
            "status": self.status.value,
            "uptime": self.stats.uptime,
            "homeostasis_cycles": self.stats.homeostasis_cycles,
            "last_homeostasis": self.stats.last_homeostasis,
            "overall_health": self.state.overall_health,
            "colony_health": self.state.colony_health,
            "total_population": self.stats.total_population,
        }

    def update_intent_stats(self, success: bool) -> None:
        """Update intent execution statistics.

        Args:
            success: Whether intent succeeded
        """
        self.stats.total_intents += 1
        if success:
            self.stats.completed_intents += 1
        else:
            self.stats.failed_intents += 1


# =============================================================================
# FACTORY
# =============================================================================


def create_homeostasis_monitor(
    interval: float = DEFAULT_HOMEOSTASIS_INTERVAL,
    health_threshold: float = DEFAULT_HEALTH_THRESHOLD,
) -> HomeostasisMonitor:
    """Create a homeostasis monitor.

    Args:
        interval: Check interval in seconds
        health_threshold: Threshold for DEGRADED status

    Returns:
        Configured HomeostasisMonitor
    """
    return HomeostasisMonitor(
        interval=interval,
        health_threshold=health_threshold,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "DEFAULT_HEALTH_THRESHOLD",
    "DEFAULT_HOMEOSTASIS_INTERVAL",
    "HomeostasisMonitor",
    "HomeostasisState",
    "OrganismStats",
    "OrganismStatus",
    "create_homeostasis_monitor",
]
