"""Autonomous Orchestrator - Coordinate all subsystems for full autonomy.

This is Kagami's brain - the fixed point that emerges from the seven colonies
observing themselves. It coordinates:

- Intent execution (unified organism)
- Continuous learning (continuous mind)
- Knowledge graph reasoning
- Population evolution
- Safety monitoring
- Self-modification

The orchestrator runs autonomously, maintaining μ_self convergence while
ensuring safety invariants h(x) ≥ 0 at all times.

Created: December 14, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import torch

from kagami.core.executive.self_modification import (
    SafetyMonitor,
    SafetyStatus,
    SelfModificationEngine,
)
from kagami.core.unified_agents.unified_organism import UnifiedOrganism

# Optional Phase 7/8 imports (not yet in production scope)
try:
    from kagami.services.knowledge_graph.kg_reasoning_engine import KGReasoningEngine
except ImportError:
    KGReasoningEngine = None


try:
    from kagami.services.evolution.organism_population import OrganismPopulation
except ImportError:
    OrganismPopulation = None


logger = logging.getLogger(__name__)


class OrchestrationPhase(Enum):
    """Phases of orchestration cycle."""

    EXECUTE = "execute"  # Process intents
    LEARN = "learn"  # Update models
    REASON = "reason"  # Query knowledge graph
    EVOLVE = "evolve"  # Population evolution
    MONITOR = "monitor"  # Safety checks
    MODIFY = "modify"  # Self-modification
    CONVERGE = "converge"  # Track μ_self


@dataclass
class OrchestrationMetrics:
    """Metrics for orchestration performance."""

    step: int = 0
    intents_processed: int = 0
    safety_violations: int = 0
    modifications_applied: int = 0
    population_size: int = 7  # Number of colonies
    kg_queries: int = 0
    evolution_cycles: int = 0
    mu_self_distance: float = 1.0  # Distance to fixed point
    uptime_seconds: float = 0.0
    last_evolution: float = field(default_factory=time.time)
    last_modification: float = field(default_factory=time.time)


@dataclass
class Intent:
    """An intent to be executed."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "general"
    description: str = ""
    priority: float = 0.5
    deadline: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


class IntentQueue:
    """Priority queue for intents."""

    def __init__(self) -> None:
        self.queue: list[Intent] = []

    async def get_next(self) -> Intent | None:
        """Get highest priority intent."""
        if not self.queue:
            # Generate default exploration intent
            return Intent(
                type="explore",
                description="Autonomous exploration",
                priority=0.1,
            )

        # Sort by priority (higher first)
        self.queue.sort(key=lambda i: i.priority, reverse=True)

        # Check deadlines
        now = time.time()
        for intent in self.queue:
            if intent.deadline and now > intent.deadline:
                logger.warning(f"Intent {intent.id} missed deadline")
                self.queue.remove(intent)
                continue

        if self.queue:
            return self.queue.pop(0)
        return None

    def add(self, intent: Intent) -> None:
        """Add intent to queue."""
        self.queue.append(intent)


class AutonomousOrchestrator:
    """Main orchestration layer coordinating all subsystems."""

    def __init__(
        self,
        organism: UnifiedOrganism | None = None,
        kg_reasoner: Any = None,  # Optional: KGReasoningEngine
        population: Any = None,  # Optional: OrganismPopulation
        safety_monitor: SafetyMonitor | None = None,
        self_modifier: SelfModificationEngine | None = None,
        checkpoint_dir: Path | None = None,
        evolution_interval: float = 3600.0,  # Evolve hourly
        modification_interval: float = 5000.0,  # Steps between modifications
        safety_check_interval: float = 1.0,  # Real-time safety
    ):
        # Core components
        self.organism = organism or self._create_organism()
        self.kg_reasoner = kg_reasoner
        self.population = population
        self.safety_monitor = safety_monitor or SafetyMonitor()
        self.self_modifier = self_modifier

        # Configuration
        self.checkpoint_dir = checkpoint_dir or Path("checkpoints/kagami/")
        self.evolution_interval = evolution_interval
        self.modification_interval = modification_interval
        self.safety_check_interval = safety_check_interval

        # State
        self.metrics = OrchestrationMetrics()
        self.intent_queue = IntentQueue()
        self.running = False
        self.emergency_stop_triggered = False
        self.start_time = time.time()

        # μ_self tracking (fixed point convergence)
        self.mu_self_history: list[torch.Tensor] = []
        self.mu_self_target = torch.randn(256)  # Target fixed point

        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"AutonomousOrchestrator initialized: "
            f"evolution_interval={evolution_interval}s, "
            f"modification_interval={modification_interval} steps"
        )

    def _create_organism(self) -> UnifiedOrganism:
        """Create default organism if not provided."""
        from kagami.core.unified_agents.unified_organism import UnifiedOrganism

        return UnifiedOrganism()

    async def run_autonomously(self) -> None:
        """Main autonomous loop.

        Runs forever until stopped, coordinating:
        1. Intent execution (continuous)
        2. Learning (background)
        3. KG reasoning (periodic)
        4. Evolution (periodic)
        5. Safety monitoring (real-time)
        6. Self-modification (periodic)
        7. μ_self convergence tracking
        """
        self.running = True
        self.start_time = time.time()

        logger.info("🪞 Kagami autonomous orchestration starting...")

        # Start background tasks
        safety_task = asyncio.create_task(self._safety_monitoring_loop())
        convergence_task = asyncio.create_task(self._convergence_tracking_loop())

        try:
            while self.running and not self.emergency_stop_triggered:
                # Execute next intent
                intent = await self.intent_queue.get_next()
                if intent:
                    await self._execute_intent(intent)

                # Periodic evolution
                if self._should_evolve():
                    await self._evolve_population()

                # Periodic self-modification
                if self._should_modify():
                    await self._propose_self_improvement()

                # KG reasoning for learning
                if self.kg_reasoner and self.metrics.step % 100 == 0:
                    await self._reason_over_knowledge()

                # Update metrics
                self.metrics.step += 1
                self.metrics.uptime_seconds = time.time() - self.start_time

                # Small delay to prevent tight loop
                await asyncio.sleep(0.01)

        except KeyboardInterrupt:
            logger.info("Orchestrator interrupted by user")
        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
        finally:
            # Clean shutdown
            self.running = False
            safety_task.cancel()
            convergence_task.cancel()

            logger.info(
                f"🪞 Kagami shutdown complete. Final metrics: "
                f"steps={self.metrics.step}, "
                f"intents={self.metrics.intents_processed}, "
                f"uptime={self.metrics.uptime_seconds:.1f}s"
            )

    async def _execute_intent(self, intent: Intent) -> None:
        """Execute a single intent through the organism."""
        try:
            # Convert to organism format
            organism_intent = {
                "id": intent.id,
                "type": intent.type,
                "content": intent.description,
                "metadata": intent.metadata,
            }

            # Execute through unified organism
            result = await self.organism.execute_intent(organism_intent)  # type: ignore[arg-type, call-arg]

            # Track metrics
            self.metrics.intents_processed += 1

            # Log significant results
            if result.get("success"):
                logger.debug(f"Intent {intent.id} executed successfully")
            else:
                logger.warning(f"Intent {intent.id} failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"Intent execution error: {e}")

    async def _safety_monitoring_loop(self) -> None:
        """Background task for continuous safety monitoring."""
        while self.running:
            try:
                # Check safety status
                status = await self.safety_monitor.get_status()

                if status == SafetyStatus.RED:
                    logger.critical("SAFETY VIOLATION DETECTED!")
                    self.metrics.safety_violations += 1
                    await self.emergency_stop()
                    break

                elif status == SafetyStatus.YELLOW:
                    logger.warning("Safety status: YELLOW - Caution mode")
                    # Slow down execution
                    await asyncio.sleep(1.0)

                await asyncio.sleep(self.safety_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Safety monitoring error: {e}")

    async def _convergence_tracking_loop(self) -> None:
        """Track μ_self convergence to fixed point."""
        while self.running:
            try:
                # Get current state embedding
                current_state = await self.organism.get_state_embedding()  # type: ignore[attr-defined]

                if current_state is not None:
                    self.mu_self_history.append(current_state)

                    # Calculate distance to fixed point
                    distance = torch.norm(current_state - self.mu_self_target).item()
                    self.metrics.mu_self_distance = distance

                    # Log convergence progress
                    if self.metrics.step % 100 == 0:
                        logger.info(f"μ_self distance: {distance:.4f}")

                    # Check for convergence
                    if distance < 0.1:
                        logger.info("🪞 Fixed point reached! μ_self converged.")

                await asyncio.sleep(10.0)  # Check every 10 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Convergence tracking error: {e}")

    async def _evolve_population(self) -> None:
        """Run population evolution cycle."""
        if not self.population:
            return

        try:
            logger.info("Starting evolution cycle...")

            # Evolve population
            evolved = await self.population.evolve()

            # Update metrics
            self.metrics.evolution_cycles += 1
            self.metrics.last_evolution = time.time()
            self.metrics.population_size = len(evolved.get("organisms", []))

            logger.info(
                f"Evolution complete: fitness={evolved.get('best_fitness', 0):.3f}, "
                f"population={self.metrics.population_size}"
            )

        except Exception as e:
            logger.error(f"Evolution error: {e}")

    async def _propose_self_improvement(self) -> None:
        """Propose and potentially apply self-modifications."""
        if not self.self_modifier:
            return

        try:
            logger.info("Considering self-modification...")

            # Generate proposals
            proposals = await self.self_modifier.propose_improvement_cycle()

            if proposals:
                # Try the best proposal
                best_proposal = proposals[0]
                logger.info(
                    f"Attempting modification: {best_proposal.parameter_name} "
                    f"({best_proposal.rationale})"
                )

                # Apply with safety checks
                result = await self.self_modifier.apply_modification(
                    best_proposal, target_system=self.organism
                )

                if result.success:
                    self.metrics.modifications_applied += 1
                    logger.info(
                        f"Modification successful: improvement={result.actual_improvement:.3f}"
                    )
                else:
                    logger.info(f"Modification failed: {result.error_message}")

                self.metrics.last_modification = time.time()

        except Exception as e:
            logger.error(f"Self-modification error: {e}")

    async def _reason_over_knowledge(self) -> None:
        """Query knowledge graph for insights."""
        if not self.kg_reasoner:
            return

        try:
            # Query for improvement suggestions
            query = "What patterns indicate system improvement opportunities?"
            insights = await self.kg_reasoner.reason(query)

            if insights:
                logger.debug(f"KG insights: {insights[:200]}...")
                self.metrics.kg_queries += 1

                # Convert insights to intents
                if "optimize" in insights.lower():
                    self.intent_queue.add(
                        Intent(
                            type="optimize",
                            description="Optimize based on KG insights",
                            priority=0.7,
                        )
                    )

        except Exception as e:
            logger.error(f"KG reasoning error: {e}")

    def _should_evolve(self) -> bool:
        """Check if it's time to evolve."""
        return (
            self.population is not None
            and time.time() - self.metrics.last_evolution > self.evolution_interval
        )

    def _should_modify(self) -> bool:
        """Check if it's time to self-modify."""
        return (
            self.self_modifier is not None
            and self.metrics.step > 0
            and self.metrics.step % self.modification_interval == 0
        )

    async def emergency_stop(self) -> None:
        """Emergency shutdown procedure."""
        logger.critical("🚨 EMERGENCY STOP INITIATED")
        self.emergency_stop_triggered = True
        self.running = False

        # Save checkpoint
        try:
            checkpoint_path = self.checkpoint_dir / f"emergency_{int(time.time())}.pt"
            state = {
                "metrics": self.metrics,
                "mu_self_history": self.mu_self_history,
                "timestamp": time.time(),
            }
            torch.save(state, checkpoint_path)
            logger.info(f"Emergency checkpoint saved: {checkpoint_path}")
        except Exception as e:
            logger.error(f"Failed to save emergency checkpoint: {e}")

        # Graceful shutdown of components
        if self.organism:
            await self.organism.shutdown()  # type: ignore[attr-defined]

    async def add_intent(
        self,
        intent_type: str,
        description: str,
        priority: float = 0.5,
        deadline: float | None = None,
    ) -> None:
        """Add an intent to the queue.

        Args:
            intent_type: Type of intent
            description: What to do
            priority: 0-1, higher = more urgent
            deadline: Unix timestamp deadline
        """
        intent = Intent(
            type=intent_type,
            description=description,
            priority=priority,
            deadline=deadline,
        )
        self.intent_queue.add(intent)
        logger.debug(f"Intent added: {intent.id} ({intent_type})")

    def get_status(self) -> dict[str, Any]:
        """Get current orchestrator status."""
        return {
            "running": self.running,
            "emergency_stop": self.emergency_stop_triggered,
            "metrics": {
                "step": self.metrics.step,
                "intents_processed": self.metrics.intents_processed,
                "safety_violations": self.metrics.safety_violations,
                "modifications_applied": self.metrics.modifications_applied,
                "evolution_cycles": self.metrics.evolution_cycles,
                "mu_self_distance": self.metrics.mu_self_distance,
                "uptime_seconds": self.metrics.uptime_seconds,
            },
            "queue_size": len(self.intent_queue.queue),
            "safety_status": "unknown",  # Async method, call separately via async context
        }

    async def graceful_shutdown(self) -> None:
        """Gracefully shut down the orchestrator."""
        logger.info("Graceful shutdown requested...")
        self.running = False

        # Allow time for current operations to complete
        await asyncio.sleep(2.0)

        # Save final checkpoint
        checkpoint_path = self.checkpoint_dir / f"shutdown_{int(time.time())}.pt"
        state = {
            "metrics": self.metrics,
            "mu_self_history": self.mu_self_history,
            "timestamp": time.time(),
        }
        torch.save(state, checkpoint_path)
        logger.info(f"Shutdown checkpoint saved: {checkpoint_path}")
