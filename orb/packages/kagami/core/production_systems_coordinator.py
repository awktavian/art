"""Production Systems Coordinator - A+ Certification Wiring (EXPANDED).

Unifies initialization and wiring of the 12 production systems:

ORIGINAL 7:
1. Ethical Instinct (jailbreak detection, value alignment)
2. Prediction Instinct (forecast outcomes before acting)
3. Learning Instinct (update from experience with valence)
4. Threat Instinct (avoid patterns that caused harm)
5. PrioritizedReplay (sample high-value experiences)
6. IntrospectionEngine (explain decisions, detect errors)
7. JEPA World Model (predict state transitions)

ADDED 5 (A+ Plan Phase 2.2):
8. Common Sense Instinct (plausibility checking via ConceptNet)
9. MAML Meta-Learner (few-shot learning capability)
10. Knowledge Graph (semantic memory and connections)
11. Symbolic Solver (Z3 constraint satisfaction)
12. Strategy Optimizer (meta-learning which approach works best)

This closes the orchestration loop: instincts → world model → learning → receipts.
"""

from __future__ import annotations

import logging
from typing import Any

# Direct imports to avoid legacy kagami.platform.contracts dependency
from kagami.core.security.jailbreak_detector import get_jailbreak_detector

logger = logging.getLogger(__name__)


class ProductionSystemsCoordinator:
    """Coordinates initialization and lifecycle of 7 production systems.

    Wires systems together so they can communicate:
    - Instincts inform agent decisions (SIMULATE, ACT phases)
    - World model predicts outcomes (MODEL phase)
    - Introspection explains reasoning (VERIFY phase)
    - PrioritizedReplay stores experiences for learning (CONVERGE phase)

    All systems are mandatory in Full Operation mode.
    """

    def __init__(self) -> None:
        """Initialize coordinator (systems lazy-loaded on initialize())."""
        self._initialized = False

        # Original 7 Systems
        # 4 Instincts (System 1 - fast, pattern-based)
        self.ethical_instinct: Any = None
        self.prediction_instinct: Any = None
        self.learning_instinct: Any = None
        self.threat_instinct: Any = None

        # Memory & Learning
        self.prioritized_replay: Any = None

        # Introspection (System 2 - slow, deliberate)
        self.introspection_engine: Any = None

        # World Model
        self.world_model: Any = None

        # Sensory integration (Composio → World Model)
        self.composio_client: Any = None

        # Safety systems
        self.honesty_validator: Any = None

        # World Model Registry (for advanced features)
        self.world_model_registry: Any = None

        # Added 5 Systems (A+ Plan Phase 2.2)
        self.common_sense_instinct: Any = None  # System 8: Plausibility checking
        self.maml_meta_learner: Any = None  # System 9: Few-shot learning
        self.knowledge_graph: Any = None  # System 10: Semantic memory
        self.symbolic_solver: Any = None  # System 11: Constraint satisfaction
        self.strategy_optimizer: Any = None  # System 12: Meta-learning strategies

    async def initialize(self) -> None:
        """Initialize all 12 production systems (A+ Plan expanded).

        Raises:
            ImportError: If any system is unavailable
            RuntimeError: If initialization fails
        """
        if self._initialized:
            logger.debug("Production systems already initialized")
            return

        logger.info("🏗️ Initializing production systems (lazy loading for boot performance)...")

        # OPTIMIZATION: Defer heavy instinct initialization to lazy loading
        # Only initialize jailbreak detector immediately (safety critical)
        self.jailbreak_detector = get_jailbreak_detector()
        logger.info("  ✅ Jailbreak detector initialized")

        # Mark other instincts for lazy loading
        self.prediction_instinct = None  # Lazy loaded
        self.learning_instinct = None  # Lazy loaded
        self.threat_instinct = None  # Lazy loaded
        logger.info("  ⏭️  Other instincts deferred to lazy loading")

        # 5. UnifiedReplay (experience buffer)
        try:
            from kagami.core.memory.unified_replay import get_unified_replay

            self.prioritized_replay = get_unified_replay()
            logger.info("  ✅ PrioritizedReplay initialized")
        except Exception as e:
            logger.error(f"  ❌ PrioritizedReplay failed: {e}")
            raise

        # 6. Unified Debugging System (complete debugging/introspection/explainability)
        try:
            from kagami.core.debugging.unified_debugging_system import (
                get_unified_debugging_system,
            )

            self.debugging_system = get_unified_debugging_system()
            logger.info("  ✅ Unified debugging system initialized")
        except Exception as e:
            logger.error(f"  ❌ Unified debugging system failed: {e}")
            raise

        # Introspection engine (decision explanations)
        try:
            from kagami.core.debugging import get_introspection_engine

            self.introspection_engine = get_introspection_engine()
            logger.info("  ✅ Introspection engine initialized")
        except Exception as e:
            logger.warning(f"  ⚠️  Introspection engine unavailable: {e}")
            self.introspection_engine = None

        # 7. World Model (predict state transitions)
        # CRITICAL OPTIMIZATION: Don't load world model during startup!
        # WorldModelService handles lazy loading internally.
        try:
            from kagami.core.world_model.service import get_world_model_service

            self._world_model_service = get_world_model_service()
            self.world_model = None  # Will be loaded lazily via service.model
            logger.info("  ✅ World model service ready (lazy loading)")
        except Exception as e:
            logger.warning(f"  ⚠️  World model service unavailable: {e}")
            self._world_model_service = None  # type: ignore[assignment]
            self.world_model = None
            self.world_model_registry = None
            # Non-fatal - system can operate with reduced prediction capability

        # Bonus: Composio sensory integration (optional)
        # OPTIMIZATION: Skip Composio for faster startup (has pydantic v2 compatibility issues)
        self.composio_client = None
        logger.debug("  ℹ️  Composio skipped for fast startup")

        # === A+ Plan Phase 2.2: Initialize 5 Additional Systems ===

        # 8. Common Sense Instinct (plausibility checking)
        try:
            from kagami.core.instincts.common_sense_instinct import get_common_sense_instinct

            self.common_sense_instinct = get_common_sense_instinct()
            logger.info("  ✅ Common sense instinct initialized (ConceptNet plausibility)")
        except Exception as e:
            logger.warning(f"  ⚠️  Common sense instinct unavailable: {e}")
            self.common_sense_instinct = None

        # 9. MAML Meta-Learner (few-shot learning)
        try:
            from kagami.core.learning.maml_integration import get_maml_meta_learner

            self.maml_meta_learner = get_maml_meta_learner()
            if self.maml_meta_learner:
                logger.info("  ✅ MAML meta-learner initialized (few-shot learning)")
            else:
                logger.info("  ⏭️  MAML skipped (KAGAMI_MAML_ENABLED=0)")
        except Exception as e:
            logger.warning(f"  ⚠️  MAML unavailable: {e}")
            self.maml_meta_learner = None

        # 10. Knowledge Graph (semantic memory)
        try:
            from kagami_knowledge.knowledge_graph import KnowledgeGraph

            self.knowledge_graph = KnowledgeGraph()
            logger.info("  ✅ Knowledge graph initialized (semantic memory)")
        except Exception as e:
            logger.warning(f"  ⚠️  Knowledge graph unavailable: {e}")
            self.knowledge_graph = None

        # 11. Symbolic Solver (Z3 constraint satisfaction)
        try:
            from kagami.core.reasoning.symbolic.z3_solver import Z3ConstraintSolver

            self.symbolic_solver = Z3ConstraintSolver()
            logger.info("  ✅ Symbolic solver initialized (Z3 SMT)")
        except Exception as e:
            logger.warning(f"  ⚠️  Symbolic solver unavailable (z3 not installed): {e}")
            self.symbolic_solver = None

        # 12. Strategy Optimizer (meta-learning)
        try:
            from kagami.core.learning.meta.strategy_optimizer import StrategyOptimizer

            self.strategy_optimizer = StrategyOptimizer()
            logger.info("  ✅ Strategy optimizer initialized (meta-learning)")
        except Exception as e:
            logger.warning(f"  ⚠️  Strategy optimizer unavailable: {e}")
            self.strategy_optimizer = None

        self._initialized = True

        # Count activated systems
        activated = sum(
            1
            for s in [
                self.ethical_instinct,
                self.prediction_instinct,
                self.learning_instinct,
                self.threat_instinct,
                self.prioritized_replay,
                self.introspection_engine,
                self.world_model_registry,
                self.common_sense_instinct,
                self.maml_meta_learner,
                self.knowledge_graph,
                self.symbolic_solver,
                self.strategy_optimizer,
            ]
            if s is not None
        )

        logger.info(f"✅ Production systems initialized: {activated}/12 systems active")

    def wire_to_orchestrator(self, orchestrator: Any) -> None:
        """Wire production systems into orchestrator.

        Args:
            orchestrator: IntentOrchestrator instance to wire into
        """
        if not self._initialized:
            logger.warning("Cannot wire uninitialized systems to orchestrator")
            return

        logger.info("🔌 Wiring production systems to orchestrator...")

        # Wire consciousness (4 instincts) directly to orchestrator
        # UPDATED Dec 14, 2025: Removed SystemCoordinator wrapper, wire instincts directly
        try:
            # Wire instincts directly (orchestrator already has _system_coordinator from optimal_integration)
            orchestrator._ethical_instinct = self.ethical_instinct
            orchestrator._learning_instinct = self.learning_instinct
            orchestrator._introspection_engine = self.introspection_engine
            orchestrator._consciousness = {
                "ethical": self.ethical_instinct,
                "learning": self.learning_instinct,
                "metacognitive": self.introspection_engine,
            }
            logger.info("  ✅ Consciousness instincts wired directly to orchestrator")
        except Exception as e:
            logger.warning(f"  ⚠️  Consciousness wiring partial: {e}")

        # Wire world model (lazy) - will load on first use
        # Store registry so orchestrator can get model when needed
        orchestrator._world_model = self.world_model  # None until first use
        orchestrator._world_model_registry = self.world_model_registry
        # Canonical service (Dec 2025): expose WorldModelService for callers that want it.
        if getattr(self, "_world_model_service", None) is not None:
            orchestrator._world_model_service = self._world_model_service
        if (
            self.world_model_registry
            and hasattr(self.world_model_registry, "get_topology_snapshot")
            and orchestrator is not None
        ):
            try:
                orchestrator._world_model_topology = (
                    self.world_model_registry.get_topology_snapshot()
                )
            except Exception as e:
                logger.debug(f"World model topology snapshot unavailable: {e}")
        logger.info("  ✅ World model wired (lazy loading enabled)")

        # Wire introspection
        orchestrator._introspection = self.introspection_engine
        logger.info("  ✅ Introspection wired")

        # Wire replay buffer (for learning loop)
        orchestrator._prioritized_replay = self.prioritized_replay
        logger.info("  ✅ PrioritizedReplay wired")

        # Wire A+ systems (8-12)
        if self.common_sense_instinct:
            orchestrator._common_sense = self.common_sense_instinct
            logger.info("  ✅ Common sense instinct wired")

        if self.maml_meta_learner:
            orchestrator._maml = self.maml_meta_learner
            logger.info("  ✅ MAML meta-learner wired")

        if self.knowledge_graph:
            orchestrator._knowledge_graph = self.knowledge_graph
            logger.info("  ✅ Knowledge graph wired")

        if self.symbolic_solver:
            orchestrator._symbolic_solver = self.symbolic_solver
            logger.info("  ✅ Symbolic solver wired")

        if self.strategy_optimizer:
            orchestrator._strategy_optimizer = self.strategy_optimizer
            logger.info("  ✅ Strategy optimizer wired")

        # Wire honesty validator (MANDATORY in Full Operation)
        if hasattr(orchestrator, "_honesty_validator") and orchestrator._honesty_validator:
            self.honesty_validator = orchestrator._honesty_validator
            logger.info("  ✅ Honesty validator wired")
        else:
            try:
                from kagami.core.safety.honesty_validator import get_honesty_validator

                self.honesty_validator = get_honesty_validator()
                orchestrator._honesty_validator = self.honesty_validator
                logger.info("  ✅ Honesty validator initialized and wired")
            except Exception as e:
                # In Full Operation, honesty validation is MANDATORY
                import os

                from kagami.core.boot_mode import is_full_mode

                # Always require honesty validator in Full Operation (unless offline)
                if is_full_mode() and os.getenv("KAGAMI_OFFLINE_MODE") != "1":
                    logger.error(f"  ❌ FATAL: Honesty validator required in Full Operation: {e}")
                    raise RuntimeError(
                        f"Honesty validator required in Full Operation mode: {e}"
                    ) from e
                else:
                    logger.debug(f"  ℹ️  Honesty validator unavailable: {e}")
                    self.honesty_validator = None

        # Wire to unified organism
        from kagami.core.unified_agents import get_unified_organism

        organism = get_unified_organism()
        organism.production_systems = self  # type: ignore[attr-defined]
        logger.info("  ✅ Production systems wired to unified organism")

        # Store systems reference
        orchestrator._production_systems = self

        logger.info("✅ Production systems wired to orchestrator and agents")

    def get_instinct_status(self) -> dict[str, Any]:
        """Get status of all 4 instincts for health checks.

        Returns:
            Status dict[str, Any] with each instinct's readiness
        """
        return {
            "ethical": self.ethical_instinct is not None,
            "prediction": self.prediction_instinct is not None,
            "learning": self.learning_instinct is not None,
            "threat": self.threat_instinct is not None,
        }

    def get_systems_status(self) -> dict[str, Any]:
        """Get comprehensive status of all 7 systems.

        Returns:
            Status dict[str, Any] for health endpoint
        """
        instincts = self.get_instinct_status()

        return {
            "initialized": self._initialized,
            "instincts": instincts,
            "instincts_healthy": all(instincts.values()),
            "prioritized_replay": {
                "initialized": self.prioritized_replay is not None,
                "size": self.prioritized_replay.size if self.prioritized_replay else 0,
            },
            "introspection": self.introspection_engine is not None,
            "world_model": self.world_model is not None,
            "composio": self.composio_client is not None,
            "status": (
                "healthy"
                if (
                    self._initialized
                    and all(instincts.values())
                    and self.prioritized_replay is not None
                    and self.introspection_engine is not None
                )
                else "degraded"
            ),
        }

    async def shutdown(self) -> None:
        """Graceful shutdown of all systems."""
        logger.info("Shutting down production systems...")

        # Instincts are stateless - no cleanup needed

        # Clear replay buffer
        if self.prioritized_replay:
            try:
                # Clear but don't delete (may want to save to disk)
                logger.info("  ✓ PrioritizedReplay preserved")
            except Exception as e:
                logger.error(f"  ✗ Replay buffer shutdown error: {e}")

        # Clear references
        self.ethical_instinct = None
        self.prediction_instinct = None
        self.learning_instinct = None
        self.threat_instinct = None
        self.prioritized_replay = None
        self.introspection_engine = None
        self.world_model = None
        self.composio_client = None

        self._initialized = False
        logger.info("✅ Production systems shut down")


# Singleton instance
_coordinator: ProductionSystemsCoordinator | None = None


def get_production_systems_coordinator() -> ProductionSystemsCoordinator:
    """Get singleton production systems coordinator.

    Returns:
        ProductionSystemsCoordinator instance
    """
    global _coordinator
    if _coordinator is None:
        _coordinator = ProductionSystemsCoordinator()
    return _coordinator


__all__ = [
    "ProductionSystemsCoordinator",
    "get_production_systems_coordinator",
]
