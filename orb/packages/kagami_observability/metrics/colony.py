"""Colony and Organism Metrics for Prometheus.

A+ observability for fractal agent system:
- Colony population dynamics
- Workload distribution
- Task success rates
- Lifecycle events (mitosis/apoptosis)
- Resource utilization

Created: November 15, 2025 - A+ System Upgrade
"""

from __future__ import annotations

from kagami_observability.metrics.core import REGISTRY, Counter, Gauge

# Track last-seen totals per domain so we can emit proper counter deltas
_LAST_TASK_COUNTS: dict[str, tuple[int, int]] = {}
_LAST_LIFECYCLE_COUNTS: dict[str, tuple[int, int]] = {}

# ============================================================================
# Colony Population Metrics
# ============================================================================

COLONY_POPULATION = Gauge(
    "kagami_colony_population",
    "Current agent population in colony",
    ["domain", "status"],  # status: active|total|...
    registry=REGISTRY,
)

COLONY_POPULATION_MAX = Gauge(
    "kagami_colony_population_max",
    "Maximum allowed population for colony",
    ["domain"],
    registry=REGISTRY,
)

COLONY_POPULATION_UTILIZATION = Gauge(
    "kagami_colony_population_utilization",
    "Population utilization percentage (0-100)",
    ["domain"],
    registry=REGISTRY,
)

# ============================================================================
# Colony Workload Metrics
# ============================================================================

COLONY_WORKLOAD_AVG = Gauge(
    "kagami_colony_workload_avg",
    "Average workload across all agents in colony (0-1)",
    ["domain"],
    registry=REGISTRY,
)

COLONY_CAPACITY_REMAINING = Gauge(
    "kagami_colony_capacity_remaining_pct",
    "Remaining capacity percentage (0-100)",
    ["domain"],
    registry=REGISTRY,
)

# ============================================================================
# Colony Task Metrics
# ============================================================================

COLONY_TASKS_COMPLETED_TOTAL = Counter(
    "kagami_colony_tasks_completed_total",
    "Total tasks completed successfully by colony",
    ["domain"],
    registry=REGISTRY,
)

COLONY_TASKS_FAILED_TOTAL = Counter(
    "kagami_colony_tasks_failed_total",
    "Total tasks failed by colony",
    ["domain"],
    registry=REGISTRY,
)

COLONY_TASK_SUCCESS_RATE = Gauge(
    "kagami_colony_task_success_rate",
    "Current task success rate for colony (0-1)",
    ["domain"],
    registry=REGISTRY,
)

# ============================================================================
# Colony Lifecycle Metrics
# ============================================================================

COLONY_MITOSIS_EVENTS_TOTAL = Counter(
    "kagami_colony_mitosis_events_total",
    "Total mitosis (cell division) events in colony",
    ["domain", "trigger"],  # trigger: workload, backlog, specialization
    registry=REGISTRY,
)

COLONY_APOPTOSIS_EVENTS_TOTAL = Counter(
    "kagami_colony_apoptosis_events_total",
    "Total apoptosis (cell death) events in colony",
    ["domain", "reason"],  # reason: idle, errors, old_age
    registry=REGISTRY,
)

COLONY_NET_GROWTH = Gauge(
    "kagami_colony_net_growth",
    "Net population growth (mitosis*2 - apoptosis)",
    ["domain"],
    registry=REGISTRY,
)

# ============================================================================
# Colony Generation Metrics
# ============================================================================

COLONY_MAX_GENERATION = Gauge(
    "kagami_colony_max_generation",
    "Maximum generation number in colony",
    ["domain"],
    registry=REGISTRY,
)

COLONY_AVG_GENERATION = Gauge(
    "kagami_colony_avg_generation",
    "Average generation number across agents",
    ["domain"],
    registry=REGISTRY,
)

# ============================================================================
# Colony Health Metrics
# ============================================================================

COLONY_HEALTH_SCORE = Gauge(
    "kagami_colony_health_score",
    "Colony health score: 4=excellent, 3=good, 2=warning, 1=critical",
    ["domain"],
    registry=REGISTRY,
)

COLONY_RESOURCE_UTILIZATION = Gauge(
    "kagami_colony_resource_utilization",
    "Estimated resource utilization (0-1)",
    ["domain"],
    registry=REGISTRY,
)

# ============================================================================
# Organism-Wide Aggregates (Enhanced)
# ============================================================================

ORGANISM_COLONIES_TOTAL = Gauge(
    "kagami_organism_colonies_total",
    "Total number of active colonies",
    registry=REGISTRY,
)

ORGANISM_AGENTS_UTILIZATION = Gauge(
    "kagami_organism_agents_utilization_pct",
    "Overall agent utilization percentage (0-100)",
    registry=REGISTRY,
)

ORGANISM_GROWTH_RATE = Gauge(
    "kagami_organism_growth_rate_per_sec",
    "Population growth rate (agents/second)",
    registry=REGISTRY,
)

ORGANISM_HOMEOSTASIS_INTERVAL = Gauge(
    "kagami_organism_homeostasis_interval_sec",
    "Current homeostasis check interval in seconds",
    registry=REGISTRY,
)

# ============================================================================
# Real-Time Mitosis Tracking (NEW - A+ Feature)
# ============================================================================

REALTIME_MITOSIS_TOTAL = Counter(
    "kagami_realtime_mitosis_total",
    "Real-time mitosis events (triggered immediately, not via homeostasis)",
    ["domain"],
    registry=REGISTRY,
)

HOMEOSTASIS_MITOSIS_TOTAL = Counter(
    "kagami_homeostasis_mitosis_total",
    "Mitosis events triggered during periodic homeostasis",
    ["domain"],
    registry=REGISTRY,
)

HOMEOSTASIS_CYCLES_TOTAL = Counter(
    "kagami_homeostasis_cycles_total",
    "Total homeostasis cycles executed",
    registry=REGISTRY,
)

HOMEOSTASIS_DURATION_MS = Gauge(
    "kagami_homeostasis_duration_ms",
    "Duration of homeostasis cycles in ms",
    registry=REGISTRY,
)

# ============================================================================
# Helper Functions
# ============================================================================


def update_colony_metrics(
    domain: str,
    *,
    population: int,
    max_population: int,
    avg_workload: float,
    tasks_completed: int,
    tasks_failed: int,
    mitosis_events: int,
    apoptosis_events: int,
    max_generation: int,
    avg_generation: float,
    health_score: int,
    resource_util: float,
) -> None:
    """Update all colony metrics for a given domain.

    Args:
        domain: Colony domain name
        population: Current agent count
        max_population: Maximum allowed agents
        avg_workload: Average workload (0-1)
        tasks_completed: Total completed tasks
        tasks_failed: Total failed tasks
        mitosis_events: Total mitosis events
        apoptosis_events: Total apoptosis events
        max_generation: Highest generation number
        avg_generation: Average generation
        health_score: Health score (1-4)
        resource_util: Resource utilization (0-1)
    """
    try:
        # Population
        COLONY_POPULATION.labels(domain=domain, status="total").set(population)
        COLONY_POPULATION_MAX.labels(domain=domain).set(max_population)

        utilization = (population / max_population * 100) if max_population > 0 else 0
        COLONY_POPULATION_UTILIZATION.labels(domain=domain).set(utilization)

        # Workload / capacity
        COLONY_WORKLOAD_AVG.labels(domain=domain).set(avg_workload)
        capacity = (1.0 - avg_workload) * 100
        COLONY_CAPACITY_REMAINING.labels(domain=domain).set(capacity)

        # Task metrics – derive success rate and increment counters by delta
        total_tasks = tasks_completed + tasks_failed
        success_rate = (tasks_completed / total_tasks) if total_tasks > 0 else 0.0
        COLONY_TASK_SUCCESS_RATE.labels(domain=domain).set(success_rate)

        prev_completed, prev_failed = _LAST_TASK_COUNTS.get(domain, (0, 0))
        delta_completed = max(0, tasks_completed - prev_completed)
        delta_failed = max(0, tasks_failed - prev_failed)
        if delta_completed:
            COLONY_TASKS_COMPLETED_TOTAL.labels(domain=domain).inc(delta_completed)
        if delta_failed:
            COLONY_TASKS_FAILED_TOTAL.labels(domain=domain).inc(delta_failed)
        _LAST_TASK_COUNTS[domain] = (tasks_completed, tasks_failed)

        # Lifecycle / growth metrics – emit net growth gauge and lifecycle counters
        net_growth = mitosis_events * 2 - apoptosis_events
        COLONY_NET_GROWTH.labels(domain=domain).set(net_growth)

        prev_mitosis, prev_apoptosis = _LAST_LIFECYCLE_COUNTS.get(domain, (0, 0))
        delta_mitosis = max(0, mitosis_events - prev_mitosis)
        delta_apoptosis = max(0, apoptosis_events - prev_apoptosis)
        if delta_mitosis:
            COLONY_MITOSIS_EVENTS_TOTAL.labels(domain=domain, trigger="homeostasis").inc(
                delta_mitosis
            )
        if delta_apoptosis:
            COLONY_APOPTOSIS_EVENTS_TOTAL.labels(domain=domain, reason="homeostasis").inc(
                delta_apoptosis
            )
        _LAST_LIFECYCLE_COUNTS[domain] = (mitosis_events, apoptosis_events)

        # Generation / health / resources
        COLONY_MAX_GENERATION.labels(domain=domain).set(max_generation)
        COLONY_AVG_GENERATION.labels(domain=domain).set(avg_generation)

        COLONY_HEALTH_SCORE.labels(domain=domain).set(health_score)
        COLONY_RESOURCE_UTILIZATION.labels(domain=domain).set(resource_util)

    except Exception:
        pass  # Safe emission - never crash on metrics


def update_organism_aggregates(
    *,
    total_colonies: int,
    total_agents: int,
    max_agents: int,
    growth_rate: float,
    homeostasis_interval: float,
) -> None:
    """Update organism-wide aggregate metrics.

    Args:
        total_colonies: Number of active colonies
        total_agents: Total agent population
        max_agents: Maximum allowed agents
        growth_rate: Growth rate (agents/second)
        homeostasis_interval: Current homeostasis interval
    """
    try:
        ORGANISM_COLONIES_TOTAL.set(total_colonies)

        utilization = (total_agents / max_agents * 100) if max_agents > 0 else 0
        ORGANISM_AGENTS_UTILIZATION.set(utilization)

        ORGANISM_GROWTH_RATE.set(growth_rate)
        ORGANISM_HOMEOSTASIS_INTERVAL.set(homeostasis_interval)

    except Exception:
        pass  # Safe emission


def record_realtime_mitosis(domain: str) -> None:
    """Record a real-time mitosis event (A+ feature).

    Args:
        domain: Colony domain where mitosis occurred
    """
    try:
        REALTIME_MITOSIS_TOTAL.labels(domain=domain).inc()
    except Exception:
        pass


def record_homeostasis_mitosis(domain: str) -> None:
    """Record a homeostasis-triggered mitosis event.

    Args:
        domain: Colony domain where mitosis occurred
    """
    try:
        HOMEOSTASIS_MITOSIS_TOTAL.labels(domain=domain).inc()
    except Exception:
        pass


__all__ = [
    # Agent importance trigger metrics
    "AGENT_ADAPTIVE_THRESHOLD",
    "AGENT_LONELINESS",
    "AGENT_SOLO_STREAK",
    "COLONY_APOPTOSIS_EVENTS_TOTAL",
    "COLONY_AVG_GENERATION",
    "COLONY_CAPACITY_REMAINING",
    "COLONY_HEALTH_SCORE",
    "COLONY_MAX_GENERATION",
    "COLONY_MITOSIS_EVENTS_TOTAL",
    "COLONY_NET_GROWTH",
    "COLONY_POPULATION",
    "COLONY_POPULATION_MAX",
    "COLONY_POPULATION_UTILIZATION",
    "COLONY_RESOURCE_UTILIZATION",
    "COLONY_TASKS_COMPLETED_TOTAL",
    "COLONY_TASKS_FAILED_TOTAL",
    "COLONY_TASK_SUCCESS_RATE",
    "COLONY_WORKLOAD_AVG",
    "HOMEOSTASIS_CYCLES_TOTAL",
    "HOMEOSTASIS_DURATION_MS",
    "HOMEOSTASIS_MITOSIS_TOTAL",
    "ORGANISM_AGENTS_UTILIZATION",
    "ORGANISM_COLONIES_TOTAL",
    "ORGANISM_GROWTH_RATE",
    "ORGANISM_HOMEOSTASIS_INTERVAL",
    "REALTIME_MITOSIS_TOTAL",
    "record_homeostasis_mitosis",
    "record_realtime_mitosis",
    "update_colony_metrics",
    "update_organism_aggregates",
]

# ============================================================================
# Agent Importance Trigger Metrics
# ============================================================================

AGENT_ADAPTIVE_THRESHOLD = Gauge(
    "kagami_agent_adaptive_threshold",
    "Current adaptive threshold for agent importance triggers",
    ["agent_type"],
    registry=REGISTRY,
)

AGENT_LONELINESS = Gauge(
    "kagami_agent_loneliness",
    "Agent loneliness score (0-1, higher = more isolated)",
    ["agent_id"],
    registry=REGISTRY,
)

AGENT_SOLO_STREAK = Counter(
    "kagami_agent_solo_streak_total",
    "Consecutive solo operations without collaboration",
    ["agent_id"],
    registry=REGISTRY,
)
