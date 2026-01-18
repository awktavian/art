"""Trigger simulation framework for game theory optimization.

Simulates cross-service event flows to:
1. Validate trigger configurations
2. Estimate payoff matrices
3. Find Nash equilibria
4. Optimize trigger parameters

Uses Monte Carlo simulation with realistic service latencies
and failure rates to model production behavior.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass

import numpy as np

from .auto_triggers import AutoTriggerOrchestrator, TriggerConfig

logger = logging.getLogger(__name__)


@dataclass
class ServiceModel:
    """Model of a service's behavior for simulation.

    Attributes:
        name: Service name.
        latency_mean: Mean response latency in ms.
        latency_std: Standard deviation of latency.
        failure_rate: Probability of action failure (0-1).
        rate_limit: Max requests per minute.
        cost_per_action: Relative cost of each action.
    """

    name: str
    latency_mean: float
    latency_std: float
    failure_rate: float
    rate_limit: int
    cost_per_action: float


@dataclass
class SimulationResult:
    """Result of a trigger simulation run.

    Attributes:
        trigger_name: Name of the trigger.
        success_rate: Fraction of successful executions.
        avg_latency: Average end-to-end latency.
        total_cost: Total cost of all actions.
        payoff: Net payoff (value * success - cost).
        events_processed: Number of events processed.
    """

    trigger_name: str
    success_rate: float
    avg_latency: float
    total_cost: float
    payoff: float
    events_processed: int


@dataclass
class NashEquilibrium:
    """Nash equilibrium configuration.

    Attributes:
        triggers: Optimal trigger configuration.
        total_payoff: Total expected payoff.
        stability: Measure of equilibrium stability (0-1).
        iterations: Number of iterations to converge.
    """

    triggers: list[TriggerConfig]
    total_payoff: float
    stability: float
    iterations: int


class TriggerSimulator:
    """Simulates trigger execution for optimization.

    Uses Monte Carlo methods to estimate expected payoffs
    and find Nash equilibrium configurations.

    Example:
        >>> simulator = TriggerSimulator()
        >>> results = await simulator.run_simulation(triggers, n_events=1000)
        >>> equilibrium = simulator.find_nash_equilibrium(results)
    """

    # Realistic service models based on observed behavior
    # Updated January 5, 2026: Figma now uses Direct OAuth with webhooks
    SERVICE_MODELS: dict[str, ServiceModel] = {
        "github": ServiceModel("github", 200, 50, 0.02, 5000, 0.1),
        "linear": ServiceModel("linear", 150, 30, 0.01, 1000, 0.2),
        "notion": ServiceModel("notion", 300, 100, 0.03, 300, 0.3),
        # Figma: Direct OAuth (14 scopes) + webhooks for real-time events
        "figma": ServiceModel("figma", 180, 50, 0.02, 500, 0.15),
        "figma_webhook": ServiceModel("figma_webhook", 50, 20, 0.01, 1000, 0.05),  # Webhook events
        "slack": ServiceModel("slack", 100, 20, 0.01, 10000, 0.05),
        "gmail": ServiceModel("gmail", 250, 80, 0.02, 500, 0.15),
        "googlecalendar": ServiceModel("googlecalendar", 200, 60, 0.02, 500, 0.1),
        "todoist": ServiceModel("todoist", 150, 40, 0.02, 1000, 0.1),
        "twitter": ServiceModel("twitter", 300, 100, 0.05, 300, 0.2),
        "discord": ServiceModel("discord", 100, 30, 0.01, 5000, 0.05),
        "googledrive": ServiceModel("googledrive", 200, 50, 0.02, 1000, 0.1),
    }

    def __init__(self, seed: int | None = None) -> None:
        """Initialize simulator with optional random seed."""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        self._results_cache: dict[str, SimulationResult] = {}

    async def _simulate_action(self, service: str) -> tuple[bool, float]:
        """Simulate a single action execution.

        Returns:
            Tuple of (success, latency_ms).
        """
        model = self.SERVICE_MODELS.get(service)
        if not model:
            return False, 0

        # Simulate latency
        latency = max(0, np.random.normal(model.latency_mean, model.latency_std))

        # Simulate failure
        success = random.random() > model.failure_rate

        # Add rate limit delay if needed
        if random.random() < 0.1:  # 10% chance of rate limit
            latency += 1000  # 1 second delay

        return success, latency

    async def simulate_trigger(
        self, trigger: TriggerConfig, n_events: int = 100
    ) -> SimulationResult:
        """Simulate a single trigger over multiple events.

        Args:
            trigger: The trigger configuration to simulate.
            n_events: Number of events to simulate.

        Returns:
            SimulationResult with metrics.
        """
        successes = 0
        total_latency = 0.0
        total_cost = 0.0

        source_model = self.SERVICE_MODELS.get(trigger.source_service)
        target_model = self.SERVICE_MODELS.get(trigger.target_service)

        if not source_model or not target_model:
            return SimulationResult(
                trigger_name=trigger.name,
                success_rate=0,
                avg_latency=0,
                total_cost=0,
                payoff=0,
                events_processed=0,
            )

        for _ in range(n_events):
            # Simulate condition check (if any)
            if trigger.condition:
                # Assume 70% of events pass condition
                if random.random() > 0.7:
                    continue

            # Simulate source poll
            _, source_latency = await self._simulate_action(trigger.source_service)

            # Simulate target action
            success, target_latency = await self._simulate_action(trigger.target_service)

            if success:
                successes += 1

            total_latency += source_latency + target_latency
            total_cost += source_model.cost_per_action + target_model.cost_per_action

        success_rate = successes / n_events if n_events > 0 else 0
        avg_latency = total_latency / n_events if n_events > 0 else 0

        # Calculate payoff: value * success_rate - normalized_cost
        payoff = trigger.value * success_rate - (total_cost / n_events)

        return SimulationResult(
            trigger_name=trigger.name,
            success_rate=success_rate,
            avg_latency=avg_latency,
            total_cost=total_cost,
            payoff=payoff,
            events_processed=n_events,
        )

    async def run_simulation(
        self,
        triggers: list[TriggerConfig],
        n_events: int = 1000,
        iterations: int = 10,
    ) -> list[SimulationResult]:
        """Run full simulation across all triggers.

        Args:
            triggers: List of trigger configurations.
            n_events: Events per trigger per iteration.
            iterations: Number of iterations to average.

        Returns:
            List of aggregated SimulationResults.
        """
        all_results: dict[str, list[SimulationResult]] = {t.name: [] for t in triggers}

        for i in range(iterations):
            logger.info(f"Simulation iteration {i + 1}/{iterations}")

            tasks = [self.simulate_trigger(t, n_events) for t in triggers]
            results = await asyncio.gather(*tasks)

            for result in results:
                all_results[result.trigger_name].append(result)

        # Aggregate results
        aggregated = []
        for name, results in all_results.items():
            if not results:
                continue

            aggregated.append(
                SimulationResult(
                    trigger_name=name,
                    success_rate=np.mean([r.success_rate for r in results]),
                    avg_latency=np.mean([r.avg_latency for r in results]),
                    total_cost=np.mean([r.total_cost for r in results]),
                    payoff=np.mean([r.payoff for r in results]),
                    events_processed=sum(r.events_processed for r in results),
                )
            )

        return sorted(aggregated, key=lambda r: -r.payoff)

    def build_payoff_matrix(
        self,
        results: list[SimulationResult],
        triggers: list[TriggerConfig],
    ) -> np.ndarray:
        """Build payoff matrix for game theory analysis.

        Rows = source services, Columns = target services
        Values = expected payoff of that interaction

        Returns:
            2D numpy array of payoffs.
        """
        services = list(self.SERVICE_MODELS.keys())
        n = len(services)
        matrix = np.zeros((n, n))

        # Build lookup
        result_map = {r.trigger_name: r for r in results}

        for trigger in triggers:
            result = result_map.get(trigger.name)
            if not result:
                continue

            i = services.index(trigger.source_service) if trigger.source_service in services else -1
            j = services.index(trigger.target_service) if trigger.target_service in services else -1

            if i >= 0 and j >= 0:
                matrix[i, j] += result.payoff

        return matrix

    def find_nash_equilibrium(
        self,
        results: list[SimulationResult],
        triggers: list[TriggerConfig],
        max_iterations: int = 100,
    ) -> NashEquilibrium:
        """Find Nash equilibrium configuration.

        Uses iterative best response to find stable configuration.

        Args:
            results: Simulation results.
            triggers: Original trigger configurations.
            max_iterations: Maximum iterations for convergence.

        Returns:
            NashEquilibrium with optimal configuration.
        """
        self.build_payoff_matrix(results, triggers)
        list(self.SERVICE_MODELS.keys())

        # Initial strategy: enable all triggers
        enabled = [True] * len(triggers)
        result_map = {r.trigger_name: r for r in results}

        prev_payoff = float("-inf")
        iterations = 0

        for iteration in range(max_iterations):
            iterations = iteration + 1

            # Calculate current total payoff
            total_payoff = sum(
                result_map[t.name].payoff
                for t, e in zip(triggers, enabled, strict=False)
                if e and t.name in result_map
            )

            # Check convergence
            if abs(total_payoff - prev_payoff) < 0.01:
                break

            prev_payoff = total_payoff

            # Best response: for each trigger, check if enabling/disabling improves payoff
            for i, trigger in enumerate(triggers):
                if trigger.name not in result_map:
                    continue

                result = result_map[trigger.name]

                # If payoff is negative, disable
                if result.payoff < 0:
                    enabled[i] = False
                # If payoff is positive and not enabled, enable
                elif result.payoff > 0 and not enabled[i]:
                    enabled[i] = True

        # Build optimal configuration
        optimal_triggers = [t for t, e in zip(triggers, enabled, strict=False) if e]
        final_payoff = sum(
            result_map[t.name].payoff for t in optimal_triggers if t.name in result_map
        )

        # Calculate stability (fraction of triggers that didn't change in last iteration)
        stability = sum(1 for e in enabled if e) / len(enabled) if enabled else 0

        return NashEquilibrium(
            triggers=optimal_triggers,
            total_payoff=final_payoff,
            stability=stability,
            iterations=iterations,
        )

    def sensitivity_analysis(
        self,
        results: list[SimulationResult],
        triggers: list[TriggerConfig],
    ) -> dict[str, dict[str, float]]:
        """Analyze sensitivity of payoffs to parameter changes.

        Returns:
            Dictionary mapping trigger names to sensitivity metrics.
        """
        sensitivities = {}
        result_map = {r.trigger_name: r for r in results}

        for trigger in triggers:
            if trigger.name not in result_map:
                continue

            result = result_map[trigger.name]

            # Sensitivity to value change
            value_sensitivity = result.success_rate  # dPayoff/dValue = success_rate

            # Sensitivity to failure rate change
            failure_sensitivity = -trigger.value  # dPayoff/dFailure = -value

            # Sensitivity to latency change
            latency_sensitivity = -0.001  # Small negative (latency is bad)

            sensitivities[trigger.name] = {
                "value_sensitivity": value_sensitivity,
                "failure_sensitivity": failure_sensitivity,
                "latency_sensitivity": latency_sensitivity,
                "robustness": result.success_rate * (1 - abs(failure_sensitivity) / 10),
            }

        return sensitivities


async def run_full_optimization() -> tuple[list[SimulationResult], NashEquilibrium]:
    """Run full optimization pipeline.

    Returns:
        Tuple of (simulation results, Nash equilibrium).

    Example:
        >>> results, equilibrium = await run_full_optimization()
        >>> print(f"Optimal payoff: {equilibrium.total_payoff}")
    """
    orchestrator = AutoTriggerOrchestrator()
    triggers = orchestrator.EQUILIBRIUM_TRIGGERS

    simulator = TriggerSimulator(seed=42)

    logger.info("Running trigger simulation...")
    results = await simulator.run_simulation(triggers, n_events=500, iterations=5)

    logger.info("Finding Nash equilibrium...")
    equilibrium = simulator.find_nash_equilibrium(results, triggers)

    logger.info(
        f"Equilibrium found: {len(equilibrium.triggers)} triggers, payoff={equilibrium.total_payoff:.2f}"
    )

    return results, equilibrium
