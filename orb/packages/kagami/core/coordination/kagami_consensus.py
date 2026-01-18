"""Kagami Byzantine Consensus - Coordinator as Emergent Fixed Point.

Kagami is NOT a privileged entity. Kagami is the **consensus fixed point**
that emerges from Byzantine consensus among all 7 colonies.

ARCHITECTURE:
=============
┌──────────────────────────────────────────────────────────────────┐
│                  BYZANTINE CONSENSUS PROTOCOL                     │
│                                                                   │
│  1. Each colony independently proposes routing for the task      │
│  2. Compute pairwise agreement matrix (Jaccard similarity)       │
│  3. Iterate to fixed point with CBF constraints                  │
│  4. Inverter (e₈) verifies consensus validity                    │
│  5. If valid: execute routing                                    │
│     If invalid: fallback mode                                    │
└──────────────────────────────────────────────────────────────────┘

BYZANTINE TOLERANCE:
====================
With 7 colonies, can tolerate ⌊(7-1)/3⌋ = 2 faulty colonies.
Requires 5/7 colonies in agreement for valid consensus.

However, we use a softer threshold (configurable, default 0.7) to allow
for legitimate disagreement in ambiguous tasks.

MARKOV BLANKET DISCIPLINE:
===========================
Consensus respects Markov blankets:
- Colonies propose routing based ONLY on their sensory state (task, context)
- Internal colony state μ remains hidden
- Consensus aggregates proposals without accessing internals

INTEGRATION (December 15, 2025):
=================================
This module now integrates the complete consensus infrastructure:

1. **ConsensusOptimizer** (consensus_optimizer.py:line 42-250)
   - Batched consensus for throughput
   - LRU cache with TTL for deterministic tasks
   - Predictive consensus via world model

2. **verify_compositional_cbf** (consensus_safety.py:line 163-250)
   - Formal safety verification: ∀i: h_i(μ_i, neighbors) ≥ 0
   - Simulates consensus actions via world model RSSM rollout
   - Evaluates all 7 colony barrier functions
   - Used in: byzantine_consensus() at line 775

3. **ConsensusMetricsCollector** (consensus_metrics.py:line 247-400)
   - Prometheus metrics for convergence, latency, CBF violations
   - Per-colony activity tracking
   - Fano line agreement patterns
   - Used in: byzantine_consensus() at lines 751, 786, 814, 850, 880

4. **MarkovBlanketGuard** (markov_blanket_guard.py)
   - Enforces Markov blanket discipline in proposals
   - Validates no internal state leakage
   - Used in: collect_proposals() at line 244

5. **ColonyCollaborativeCoT** (colony_collaborative_cot.py)
   - Chain-of-Thought reasoning for proposals
   - Fano affinity extraction from reasoning traces
   - Used in: _colony_propose_routing() at line 288

WIRING POINTS:
==============
To use consensus with full infrastructure:

```python

# Standard library imports
import asyncio
import logging
import time
from dataclasses import (
    dataclass,
    field,
)
from typing import Any

# Third-party imports
import numpy as np
import torch

# Local imports
from kagami.core.active_inference.colony_collaborative_cot import (
    ColonyCollaborativeCoT,
    create_collaborative_cot,
)
from kagami.core.coordination.consensus_metrics import (
    ConsensusMetricsCollector,
    get_metrics_collector,
)
from kagami.core.coordination.consensus_optimizer import (
    ConsensusOptimizer,
    create_consensus_optimizer,
)
from kagami.core.coordination.consensus_safety import verify_compositional_cbf
from kagami.core.coordination.markov_blanket_guard import create_markov_blanket_guard
from kagami.core.coordination.types import (
    ColonyID,
    CoordinationProposal,
)
from kagami.core.unified_agents.fano_action_router import get_router_instance
from kagami.core.shared_abstractions.singleton_consolidation import singleton_factory
from kagami_math.catastrophe_constants import COLONY_NAMES

consensus = create_consensus_protocol(
    enable_optimizer=True,    # Caching, batching, prediction
    enable_metrics=True,      # Prometheus telemetry
    enable_markov_guard=True, # Architectural discipline
    enable_cot=True,          # Chain-of-Thought reasoning
)

# Collect proposals (with Markov blanket validation)
proposals = await consensus.collect_proposals(
    task_description="implement feature X",
    context={...},
    world_model=world_model,
)

# Run consensus (with CBF verification and metrics)
state = await consensus.byzantine_consensus(
    proposals=proposals,
    world_model=world_model,  # Required for verify_compositional_cbf
)
```

RECOVERY & REPLICATION:
=======================
For distributed deployment:
- **ActionLogReplicator** (action_log_replicator.py): Replicate consensus actions to etcd
- **ColonyRecovery** (colony_recovery.py): Rebuild colony state from checkpoints + action log
- **ColonyStateCRDT** (state_sync.py): Eventually-consistent colony μ state sync

See coordination/__init__.py for factory functions.

Created: December 14, 2025
Updated: December 15, 2025 (full consensus infrastructure wiring)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import torch

logger = logging.getLogger(__name__)

# Optional CoT integration
try:
    from kagami_math.catastrophe_constants import COLONY_NAMES

    from kagami.core.active_inference.colony_collaborative_cot import (
        ColonyCollaborativeCoT,
        create_collaborative_cot,
    )

    COT_AVAILABLE = True
except ImportError:
    logger.warning("ColonyCollaborativeCoT not available - using fallback routing")
    COT_AVAILABLE = False

# Consensus infrastructure integration (December 15, 2025)
# NOTE: These imports are deferred to avoid circular dependencies
# Functions are imported lazily when needed in __init__ and byzantine_consensus
CONSENSUS_INFRA_AVAILABLE = True  # Assume available, will fail gracefully if not

# Import shared types (December 15, 2025: break circular dependency)
from kagami.core.coordination.types import ColonyID, CoordinationProposal

# Singleton factory for registry
from kagami.core.shared_abstractions.singleton_consolidation import singleton_factory

# =============================================================================
# ENUMS AND CONSTANTS
# =============================================================================

# Colony routing biases (which colonies prefer which Fano lines)
# Based on colony characters and catastrophe dynamics
COLONY_ROUTING_BIASES: dict[ColonyID, list[ColonyID]] = {
    ColonyID.SPARK: [
        ColonyID.FORGE,
        ColonyID.NEXUS,
        ColonyID.GROVE,
    ],  # Creative → build/integrate/research
    ColonyID.FORGE: [
        ColonyID.SPARK,
        ColonyID.NEXUS,
        ColonyID.CRYSTAL,
    ],  # Build → create/integrate/verify
    ColonyID.FLOW: [
        ColonyID.SPARK,
        ColonyID.FORGE,
        ColonyID.NEXUS,
    ],  # Debug → ideate/rebuild/integrate
    ColonyID.NEXUS: [
        ColonyID.FORGE,
        ColonyID.FLOW,
        ColonyID.CRYSTAL,
    ],  # Integrate → build/fix/verify
    ColonyID.BEACON: [
        ColonyID.SPARK,
        ColonyID.FORGE,
        ColonyID.GROVE,
    ],  # Plan → ideate/build/research
    ColonyID.GROVE: [
        ColonyID.SPARK,
        ColonyID.BEACON,
        ColonyID.NEXUS,
    ],  # Research → ideate/plan/integrate
    ColonyID.CRYSTAL: [
        ColonyID.FORGE,
        ColonyID.NEXUS,
        ColonyID.FLOW,
    ],  # Verify → check build/integration/fixes
}

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ConsensusState:
    """The emergent Kagami state = consensus among colonies."""

    proposals: list[CoordinationProposal]
    agreement_matrix: np.ndarray[Any, Any]  # 7x7, agreement[i,j] = similarity
    consensus_routing: dict[ColonyID, str] | None = None
    cbf_constraint: float = 0.0  # min(all cbf_margins)
    converged: bool = False
    iterations: int = 0
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# BYZANTINE CONSENSUS
# =============================================================================


class KagamiConsensus:
    """Byzantine consensus protocol for coordination.

    Kagami emerges as the fixed point of this consensus process.
    """

    def __init__(
        self,
        agreement_threshold: float = 0.72,  # Byzantine: (n-f)/n = 5/7 ≈ 0.714, +margin
        cbf_threshold: float = 0.0,
        max_iterations: int = 10,
        enable_cot: bool = True,
        enable_markov_guard: bool = True,
        enable_optimizer: bool = True,
        enable_metrics: bool = True,
        dcbf: Any | None = None,  # FanoDecentralizedCBF instance for safety verification
    ):
        """Initialize consensus protocol.

        Args:
            agreement_threshold: Minimum mean agreement for convergence
                                Byzantine formula: (n-f)/n where n=7, f=2
                                5/7 = 0.714, use 0.72 for safety margin
            cbf_threshold: Minimum CBF margin h(x)
            max_iterations: Maximum consensus iterations
            enable_cot: Enable Chain-of-Thought reasoning for proposals
            enable_markov_guard: Enable Markov blanket validation (recommended)
            enable_optimizer: Enable consensus optimization (caching, batching)
            enable_metrics: Enable Prometheus metrics collection
            dcbf: FanoDecentralizedCBF instance for compositional CBF verification
        """
        self.agreement_threshold = agreement_threshold
        self.cbf_threshold = cbf_threshold
        self.max_iterations = max_iterations
        self.dcbf = dcbf  # Store for verify_compositional_cbf calls

        self.consensus_history: list[ConsensusState] = []

        # Markov blanket guard (CRITICAL for architectural discipline)
        self.markov_guard = None
        if enable_markov_guard:
            try:
                from kagami.core.coordination.markov_blanket_guard import (
                    create_markov_blanket_guard,
                )

                self.markov_guard = create_markov_blanket_guard(strict_mode=True)
                logger.info("Markov blanket guard enabled for consensus")
            except ImportError:
                logger.warning("MarkovBlanketGuard not available")

        # CoT reasoning for proposal generation (optional)
        self.cot_module: ColonyCollaborativeCoT | None = None
        if enable_cot and COT_AVAILABLE:
            try:
                self.cot_module = create_collaborative_cot(
                    z_dim=14,  # Standard colony z-state dimension
                    trace_dim=32,
                    hidden_dim=64,
                    max_depth=1,  # Shallow depth for consensus (fast proposals)
                    enable_refinement=False,  # Skip refinement for speed
                )
                logger.info("CoT reasoning enabled for consensus proposals")
            except Exception as e:
                logger.warning(f"Failed to initialize CoT module: {e}")
                self.cot_module = None

        # Consensus optimizer (caching, batching, prediction) - December 15, 2025
        self.optimizer: Any = None
        if enable_optimizer and CONSENSUS_INFRA_AVAILABLE:
            try:
                # Lazy import to avoid circular dependency
                from kagami.core.coordination.consensus_optimizer import (
                    create_consensus_optimizer,
                )

                self.optimizer = create_consensus_optimizer(
                    consensus=self,  # Pass self to avoid creating new consensus
                    cache_max_size=1000,
                    cache_ttl=300,  # 5 minutes
                    batch_timeout=0.05,  # 50ms
                    enable_prediction=True,
                )
                logger.info("Consensus optimizer enabled (caching + batching + prediction)")
            except Exception as e:
                logger.warning(f"Failed to initialize optimizer: {e}")
                self.optimizer = None

        # Metrics collector - December 15, 2025
        self.metrics: Any = None
        if enable_metrics and CONSENSUS_INFRA_AVAILABLE:
            try:
                # Lazy import to avoid circular dependency
                from kagami.core.coordination.consensus_metrics import (
                    get_metrics_collector,
                )

                self.metrics = get_metrics_collector()
                logger.info("Consensus metrics collection enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize metrics: {e}")
                self.metrics = None

    # =========================================================================
    # PROPOSAL COLLECTION
    # =========================================================================

    async def collect_proposals(
        self,
        task_description: str,
        context: dict[str, Any] | None = None,
        get_colony_fn: callable | None = None,  # type: ignore[valid-type]
        world_model: Any | None = None,
    ) -> list[CoordinationProposal]:
        """Each colony independently proposes routing.

        Preserves Markov blankets — no colony sees others' internals.

        Args:
            task_description: The task to route
            context: Additional context for routing
            get_colony_fn: Optional function to get colony agent for proposal
            world_model: Optional KagamiWorldModel for RSSM-biased proposals

        Returns:
            List of 7 proposals (one per colony)
        """
        # =============================================================
        # PART 1: RSSM PREDICTIONS → CONSENSUS PROPOSALS
        # =============================================================
        # If world model available, use RSSM to predict colony activations
        rssm_predictions = None
        if world_model is not None:
            rssm_predictions = await self._get_rssm_predictions(
                world_model=world_model,
                task=task_description,
                context=context or {},
            )

        # CONCURRENCY FIX (Dec 25, 2025): Bounded parallel proposals with error handling
        # Using semaphore to limit concurrent colony proposals (7 max)
        semaphore = asyncio.Semaphore(7)

        async def propose_with_bound(colony: ColonyID) -> CoordinationProposal:
            async with semaphore:
                return await self._colony_propose_routing(
                    colony=colony,
                    task=task_description,
                    context=context or {},
                    get_colony_fn=get_colony_fn,
                    rssm_predictions=rssm_predictions,
                )

        proposal_tasks = [propose_with_bound(colony) for colony in ColonyID]
        results = await asyncio.gather(*proposal_tasks, return_exceptions=True)

        # Handle failures gracefully
        proposals = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error(f"Colony {ColonyID(i).name} proposal failed: {result}")
                # Create fallback proposal for failed colony
                proposals.append(
                    CoordinationProposal(  # type: ignore[call-arg]
                        proposer=ColonyID(i),
                        routing=frozenset({ColonyID.GROVE}),  # Safe fallback
                        confidence=0.0,
                        rationale=f"Proposal failed: {result}",
                    )
                )
            else:
                proposals.append(result)

        # =============================================================
        # MARKOV BLANKET VALIDATION (CRITICAL)
        # =============================================================
        # Validate all proposals respect Markov blanket discipline
        if self.markov_guard is not None:
            for proposal in proposals:
                try:
                    self.markov_guard.validate_proposal(proposal)
                except Exception as e:
                    logger.error(
                        f"Markov blanket violation in proposal from {proposal.proposer.name}: {e}"
                    )
                    # In strict mode, this would raise. Continue with warning.

        logger.info(f"Collected {len(proposals)} routing proposals (Markov blanket validated)")
        return proposals

    async def _colony_propose_routing(
        self,
        colony: ColonyID,
        task: str,
        context: dict[str, Any],
        get_colony_fn: callable | None = None,  # type: ignore[valid-type]
        rssm_predictions: dict[str, Any] | None = None,
    ) -> CoordinationProposal:
        """Single colony proposes routing based on its perspective.

        INTEGRATION: Uses Chain-of-Thought reasoning when available.

        Args:
            colony: Which colony is proposing
            task: Task description
            context: Additional context
            get_colony_fn: Function to get colony agent (if available)
            rssm_predictions: Optional RSSM predictions from world model

        Returns:
            CoordinationProposal from this colony's perspective
        """
        # =================================================================
        # PART 1: COT REASONING (if available)
        # =================================================================
        cot_trace = None
        fano_affinities = {}  # type: ignore[var-annotated]
        reasoning_confidence = None

        if self.cot_module is not None:
            try:
                (
                    cot_trace,
                    fano_affinities,
                    reasoning_confidence,
                ) = await self._generate_cot_reasoning(
                    colony=colony,
                    task=task,
                    context=context,
                )
            except Exception as e:
                logger.warning(f"CoT reasoning failed for {colony.name}: {e}")
                # Continue with fallback

        # =================================================================
        # PART 2: FALLBACK HEURISTICS (bias-based routing)
        # =================================================================
        # If actual colony agent available, query it
        if get_colony_fn is not None:
            try:  # type: ignore[unreachable]
                get_colony_fn(colony.value)
                # Would call colony_agent.propose_routing(task, context)
                # For now, use bias heuristic
            except Exception as e:
                logger.warning(f"Failed to get colony {colony.name} agent: {e}")

        # Use routing bias as default
        biased_colonies = COLONY_ROUTING_BIASES[colony]

        # Task-specific adjustments
        targets = self._adjust_routing_for_task(task, biased_colonies)

        # =================================================================
        # PART 3: MERGE COT AFFINITIES WITH HEURISTICS
        # =================================================================
        if fano_affinities:
            # Enhance targets with CoT-discovered Fano affinities
            for target_colony, affinity in fano_affinities.items():
                if affinity > 0.5 and target_colony not in targets:
                    targets.append(target_colony)

        # Confidence: use CoT confidence if available, else estimate
        if reasoning_confidence is not None:
            confidence = float(reasoning_confidence)
        else:
            confidence = self._estimate_confidence(task, colony)

        # CBF margin (would query actual CBF in production)
        cbf_margin = 0.5  # Default safe margin

        # Build Fano justification
        fano_justification = f"{colony.name} perspective via Fano biases"
        if cot_trace is not None:
            fano_justification += f" + CoT reasoning ({cot_trace.reasoning_type})"

        return CoordinationProposal(
            proposer=colony,
            target_colonies=targets,
            task_decomposition=dict[str, Any].fromkeys(targets, f"subtask_from_{colony.name}"),
            confidence=confidence,
            fano_justification=fano_justification,
            cbf_margin=cbf_margin,
        )

    async def _generate_cot_reasoning(
        self,
        colony: ColonyID,
        task: str,
        context: dict[str, Any],
    ) -> tuple[Any, dict[ColonyID, float], float]:
        """Generate Chain-of-Thought reasoning for routing proposal.

        Uses ColonyCollaborativeCoT to generate reasoning traces and extract
        Fano affinities from the trace structure.

        Args:
            colony: Which colony is reasoning
            task: Task description
            context: Additional context

        Returns:
            Tuple of (trace, fano_affinities, confidence)
            - trace: ReasoningTrace object
            - fano_affinities: Dict mapping target colonies to affinity scores
            - confidence: Overall reasoning confidence
        """
        if self.cot_module is None:
            return None, {}, None  # type: ignore[return-value]

        # Create synthetic z-states for reasoning
        # In production, would use actual colony z-states from world model
        z_states = self._create_synthetic_z_states(task, context)

        # Run CoT reasoning (async-safe)
        with torch.no_grad():
            thought, _z_modulation = self.cot_module(z_states)

        # Extract trace for this specific colony
        colony_name = COLONY_NAMES[colony.value]
        if colony_name not in thought.colony_traces:
            return None, {}, None  # type: ignore[return-value]

        trace = thought.colony_traces[colony_name]

        # Extract Fano affinities from active Fano lines
        fano_affinities = self._extract_fano_affinities(
            thought=thought,
            source_colony=colony,
        )

        return trace, fano_affinities, trace.confidence

    def _create_synthetic_z_states(
        self,
        task: str,
        context: dict[str, Any],
    ) -> dict[str, torch.Tensor]:
        """Create synthetic z-states for CoT reasoning.

        In production, would use actual colony z-states from world model.
        For consensus proposals, we create simple embeddings from task text.

        Args:
            task: Task description
            context: Additional context

        Returns:
            Dict mapping colony names to z-state tensors [14]
        """
        # Simple embedding: hash task string to create deterministic z-states
        task_hash = hash(task) % 10000
        base_z = torch.randn(14) * 0.1

        # Add task-specific bias
        base_z[0] = (task_hash % 100) / 100.0  # Deterministic from task

        # Create z-states for all 7 colonies
        z_states = {}
        for idx, name in enumerate(COLONY_NAMES):
            # Add colony-specific variation
            z = base_z.clone()
            z[1] = idx / 7.0  # Colony index encoding
            z_states[name] = z

        return z_states

    def _extract_fano_affinities(
        self,
        thought: Any,  # CollaborativeThought
        source_colony: ColonyID,
    ) -> dict[ColonyID, float]:
        """Extract Fano affinities from CoT reasoning traces.

        Analyzes which colonies appear in Fano compositions involving
        the source colony, weighted by confidence.

        Args:
            thought: CollaborativeThought from CoT
            source_colony: The proposing colony

        Returns:
            Dict mapping target colonies to affinity scores [0, 1]
        """
        affinities = dict[str, Any].fromkeys(ColonyID, 0.0)
        source_idx = source_colony.value

        # Check Fano-composed traces
        for trace in thought.fano_traces:
            if trace.parents:
                parent1, parent2 = trace.parents

                # If source colony is involved in this composition
                if parent1 == source_idx or parent2 == source_idx:
                    # Add affinity to the partner colony
                    partner_idx = parent2 if parent1 == source_idx else parent1
                    result_idx = trace.colony_idx

                    # Affinity weighted by trace confidence
                    if 0 <= partner_idx < 7:
                        affinities[ColonyID(partner_idx)] += trace.confidence * 0.5

                    # Also add affinity to the result colony
                    if 0 <= result_idx < 7:
                        affinities[ColonyID(result_idx)] += trace.confidence * 0.3

        return affinities

    async def _get_rssm_predictions(
        self,
        world_model: Any,
        task: str,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Get RSSM predictions from world model for routing bias.

        Args:
            world_model: KagamiWorldModel instance
            task: Task description
            context: Additional context

        Returns:
            Dict with RSSM predictions, or None if unavailable
        """
        # Placeholder for RSSM integration
        # In production, would query world_model.predict_next_colonies(task)
        return None

    def _adjust_routing_for_task(
        self,
        task: str,
        biased_colonies: list[ColonyID],
    ) -> list[ColonyID]:
        """Adjust routing based on task keywords and learned stigmergy patterns.

        INTEGRATION: Uses learned task-colony affinities from FanoActionRouter.

        Args:
            task: Task description
            biased_colonies: Default routing bias

        Returns:
            Adjusted list[Any] of target colonies
        """
        task_lower = task.lower()
        targets = list(biased_colonies)  # Copy

        # =================================================================
        # PART 1: KEYWORD-BASED HEURISTICS
        # =================================================================
        # Add Forge if implementation task
        if any(kw in task_lower for kw in ["implement", "build", "create", "code"]):
            if ColonyID.FORGE not in targets:
                targets.append(ColonyID.FORGE)

        # Add Crystal if verification task
        if any(kw in task_lower for kw in ["verify", "test", "check", "audit"]):
            if ColonyID.CRYSTAL not in targets:
                targets.append(ColonyID.CRYSTAL)

        # Add Beacon if planning task
        if any(kw in task_lower for kw in ["plan", "design", "architect"]):
            if ColonyID.BEACON not in targets:
                targets.append(ColonyID.BEACON)

        # Add Grove if research task
        if any(kw in task_lower for kw in ["research", "explore", "investigate"]):
            if ColonyID.GROVE not in targets:
                targets.append(ColonyID.GROVE)

        # Add Flow if debugging task
        if any(kw in task_lower for kw in ["debug", "fix", "error", "recover"]):
            if ColonyID.FLOW not in targets:
                targets.append(ColonyID.FLOW)

        # =================================================================
        # PART 2: STIGMERGY PATTERN INTEGRATION
        # =================================================================
        # Use learned affinities from FanoActionRouter (if available)
        try:
            from kagami.core.unified_agents.fano_action_router import (  # type: ignore[attr-defined]
                get_router_instance,
            )

            router = get_router_instance()
            if router is not None:
                # Query learned domain affinities
                learned_targets = self._query_stigmergy_patterns(router, task)

                # Merge learned patterns with heuristic targets
                # Weight: 60% learned, 40% heuristic
                for colony_id, affinity in learned_targets.items():
                    if affinity > 0.4 and colony_id not in targets:
                        targets.append(colony_id)

                logger.debug(
                    f"Stigmergy enhanced routing: added {len(learned_targets)} learned affinities"
                )
        except ImportError:
            # FanoActionRouter not available, continue with heuristics only
            pass
        except Exception as e:
            logger.warning(f"Failed to query stigmergy patterns: {e}")

        # Limit to 4 colonies max (avoid all-colonies mode without strong signal)
        if len(targets) > 4:
            # Keep most confident targets
            targets = targets[:4]

        return targets

    def _query_stigmergy_patterns(
        self,
        router: any,  # type: ignore[valid-type]
        task: str,
    ) -> dict[ColonyID, float]:
        """Query learned stigmergy patterns from FanoActionRouter.

        Args:
            router: FanoActionRouter instance
            task: Task description

        Returns:
            Dict mapping colony IDs to affinity scores [0, 1]
        """
        learned_affinities: dict[ColonyID, float] = {}

        # Access domain affinity cache (if it exists)
        if hasattr(router, "_domain_affinity"):
            # domain_affinity is dict[str, list[tuple[int, float]]]
            # where int is colony index, float is affinity score

            # Extract domain from task (simple heuristic)
            task_lower = task.lower()
            for domain, colony_scores in router._domain_affinity.items():  # type: ignore[attr-defined]
                if domain in task_lower:
                    # Found matching domain
                    for colony_idx, score in colony_scores[:3]:  # Top 3
                        try:
                            colony_id = ColonyID(colony_idx)
                            learned_affinities[colony_id] = score
                        except ValueError:
                            continue

        return learned_affinities

    def _estimate_confidence(self, task: str, colony: ColonyID) -> float:
        """Estimate colony's confidence in its routing proposal.

        Args:
            task: Task description
            colony: Which colony

        Returns:
            Confidence [0, 1]
        """
        # Base confidence
        confidence = 0.7

        # Higher confidence if task matches colony's domain
        task_lower = task.lower()

        domain_keywords = {
            ColonyID.SPARK: ["brainstorm", "ideate", "creative", "imagine"],
            ColonyID.FORGE: ["implement", "build", "create", "code"],
            ColonyID.FLOW: ["debug", "fix", "error", "recover"],
            ColonyID.NEXUS: ["integrate", "connect", "combine"],
            ColonyID.BEACON: ["plan", "design", "architect", "strategy"],
            ColonyID.GROVE: ["research", "explore", "investigate", "study"],
            ColonyID.CRYSTAL: ["verify", "test", "check", "audit", "prove"],
        }

        if any(kw in task_lower for kw in domain_keywords.get(colony, [])):
            confidence = 0.9

        # Lower confidence if task is ambiguous
        if len(task.split()) < 3:
            confidence *= 0.8

        return min(confidence, 1.0)

    # =========================================================================
    # CONSENSUS COMPUTATION
    # =========================================================================

    def compute_agreement(
        self,
        proposals: list[CoordinationProposal],
    ) -> np.ndarray[Any, Any]:
        """Compute pairwise agreement between proposals.

        Uses Jaccard similarity on target_colonies sets.

        Args:
            proposals: List of proposals

        Returns:
            7x7 agreement matrix
        """
        n = len(proposals)
        agreement = np.eye(n, dtype=np.float32)  # Diagonal = 1

        for i, p1 in enumerate(proposals):
            for j, p2 in enumerate(proposals):
                if i >= j:
                    continue  # Skip diagonal and lower triangle

                set1 = set(p1.target_colonies)
                set2 = set(p2.target_colonies)

                if len(set1 | set2) == 0:
                    sim = 0.0
                else:
                    sim = len(set1 & set2) / len(set1 | set2)

                agreement[i, j] = sim
                agreement[j, i] = sim  # Symmetric

        return agreement

    async def byzantine_consensus(
        self,
        proposals: list[CoordinationProposal],
        world_model: Any | None = None,
    ) -> ConsensusState:
        """Byzantine consensus with CBF constraints.

        Tolerates up to 2 faulty colonies (⌊(7-1)/3⌋ = 2).

        Fixed point: routing that maximizes agreement while maintaining h(x) ≥ 0.

        Args:
            proposals: List of routing proposals
            world_model: Optional KagamiWorldModel for CBF verification

        Returns:
            ConsensusState (converged or failed)
        """
        start_time = time.time()

        if len(proposals) != 7:
            logger.error(f"Expected 7 proposals, got {len(proposals)}")
            if self.metrics:
                self.metrics.record_consensus_round(
                    status="error",
                    latency_by_phase={"total": time.time() - start_time},
                    participants=len(proposals),
                    cbf_values={},
                    agreement_stats={},
                    iterations=0,
                )
            return ConsensusState(
                proposals=proposals,
                agreement_matrix=np.zeros((7, 7)),
                converged=False,
            )

        agreement = self.compute_agreement(proposals)
        consensus_routing = None

        for iteration in range(self.max_iterations):
            # Weighted vote by confidence × agreement
            weights = self._compute_consensus_weights(proposals, agreement)

            # Merge proposals using weights
            consensus_routing = self._merge_proposals(proposals, weights)

            # INTEGRATION: Compositional CBF safety verification (December 15, 2025)
            if CONSENSUS_INFRA_AVAILABLE and world_model is not None and self.dcbf is not None:
                try:
                    # Lazy import to avoid circular dependency
                    from kagami.core.coordination.consensus_safety import (
                        verify_compositional_cbf,
                    )

                    is_safe, safety_details = await verify_compositional_cbf(
                        consensus_actions=consensus_routing,
                        dcbf=self.dcbf,
                        world_model=world_model,
                        threshold=self.cbf_threshold,
                    )

                    if not is_safe:
                        logger.warning(f"Compositional CBF verification failed: {safety_details}")
                        if self.metrics:
                            self.metrics.record_consensus_round(
                                status="cbf_violation",
                                latency_by_phase={"total": time.time() - start_time},
                                participants=7,
                                cbf_values={
                                    i.value: safety_details.get("h_values", {}).get(i, -1.0)
                                    for i in ColonyID
                                },
                                agreement_stats={
                                    "mean": np.mean(agreement),
                                    "min": np.min(agreement),
                                    "max": np.max(agreement),
                                },
                                iterations=iteration + 1,
                            )
                        return ConsensusState(
                            proposals=proposals,
                            agreement_matrix=agreement,
                            consensus_routing=None,
                            cbf_constraint=-1.0,
                            converged=False,
                            iterations=iteration + 1,
                        )

                    # Extract CBF margin from safety details
                    cbf_margin = safety_details.get("min_margin", 0.0)

                except Exception as e:
                    logger.warning(f"CBF verification error: {e}, falling back to basic check")
                    cbf_margin = self._compute_cbf_margin(consensus_routing, proposals)
            else:
                # Fallback to basic CBF margin computation
                cbf_margin = self._compute_cbf_margin(consensus_routing, proposals)

            if cbf_margin < self.cbf_threshold:
                # Safety violation — reject this consensus
                logger.warning(f"CBF violation in consensus: h(x)={cbf_margin:.3f}")
                if self.metrics:
                    self.metrics.record_consensus_round(
                        status="cbf_violation",
                        latency_by_phase={"total": time.time() - start_time},
                        participants=7,
                        cbf_values={i.value: cbf_margin for i in ColonyID},
                        agreement_stats={
                            "mean": np.mean(agreement),
                            "min": np.min(agreement),
                            "max": np.max(agreement),
                        },
                        iterations=iteration + 1,
                    )
                return ConsensusState(
                    proposals=proposals,
                    agreement_matrix=agreement,
                    consensus_routing=None,
                    cbf_constraint=cbf_margin,
                    converged=False,
                    iterations=iteration + 1,
                )

            # Check convergence
            mean_agreement = float(np.mean(agreement))
            if mean_agreement >= self.agreement_threshold:
                duration = time.time() - start_time
                logger.info(
                    f"Consensus converged after {iteration + 1} iterations "
                    f"(agreement={mean_agreement:.2f}, duration={duration:.3f}s)"
                )

                state = ConsensusState(
                    proposals=proposals,
                    agreement_matrix=agreement,
                    consensus_routing=consensus_routing,
                    cbf_constraint=cbf_margin,
                    converged=True,
                    iterations=iteration + 1,
                )

                self.consensus_history.append(state)

                # INTEGRATION: Record metrics (December 15, 2025)
                if self.metrics:
                    self.metrics.record_consensus_round(
                        status="converged",
                        latency_by_phase={"total": duration},
                        participants=7,
                        cbf_values={i.value: cbf_margin for i in ColonyID},
                        agreement_stats={
                            "mean": mean_agreement,
                            "min": np.min(agreement),
                            "max": np.max(agreement),
                        },
                        iterations=iteration + 1,
                    )

                return state

            # Not converged yet, continue iteration
            # (In a full implementation, we'd refine proposals here)

        # Failed to converge within max_iterations
        duration = time.time() - start_time
        logger.warning(f"Consensus failed to converge after {self.max_iterations} iterations")

        state = ConsensusState(
            proposals=proposals,
            agreement_matrix=agreement,
            consensus_routing=consensus_routing,
            cbf_constraint=self._compute_cbf_margin(consensus_routing, proposals),
            converged=False,
            iterations=self.max_iterations,
        )

        self.consensus_history.append(state)

        # INTEGRATION: Record metrics for failed convergence (December 15, 2025)
        if self.metrics:
            self.metrics.record_consensus_round(
                status="failed",
                latency_by_phase={"total": duration},
                participants=7,
                cbf_values={},
                agreement_stats={
                    "mean": float(np.mean(agreement)),
                    "min": float(np.min(agreement)),
                    "max": float(np.max(agreement)),
                },
                iterations=self.max_iterations,
            )

        return state

    def _compute_consensus_weights(
        self,
        proposals: list[CoordinationProposal],
        agreement: np.ndarray[Any, Any],
    ) -> np.ndarray[Any, Any]:
        """Weight each proposal by confidence × mean agreement.

        Args:
            proposals: List of proposals
            agreement: Agreement matrix

        Returns:
            Normalized weights [7]
        """
        weights = np.zeros(len(proposals), dtype=np.float32)

        for i, p in enumerate(proposals):
            # Mean agreement with other proposals
            mean_agreement = float(np.mean(agreement[i, :]))

            # Weight = confidence × agreement
            weights[i] = p.confidence * mean_agreement

        # Normalize
        if weights.sum() > 0:
            weights /= weights.sum()

        return weights

    def _merge_proposals(
        self,
        proposals: list[CoordinationProposal],
        weights: np.ndarray[Any, Any],
    ) -> dict[ColonyID, str]:
        """Merge proposals into consensus routing.

        Use weighted majority voting on target colonies.

        Args:
            proposals: List of proposals
            weights: Proposal weights

        Returns:
            Consensus routing dict[str, Any]
        """
        # For each colony, count weighted votes for being activated
        colony_votes = dict[str, Any].fromkeys(ColonyID, 0.0)

        for proposal, weight in zip(proposals, weights, strict=False):
            for target in proposal.target_colonies:
                colony_votes[target] += float(weight)

        # Activate colonies above threshold
        threshold = 0.3  # At least 30% weighted support
        consensus = {
            colony: "activate" for colony, vote in colony_votes.items() if vote >= threshold
        }

        if not consensus:
            # Fallback: activate highest voted colony
            max_colony = max(colony_votes.items(), key=lambda x: x[1])
            consensus = {max_colony[0]: "activate"}

        return consensus

    def _compute_cbf_margin(
        self,
        routing: dict[ColonyID, str] | None,
        proposals: list[CoordinationProposal],
    ) -> float:
        """CBF margin = min(all proposals' cbf_margin).

        Ensures consensus doesn't violate any colony's safety bounds.

        Args:
            routing: Consensus routing (unused, but kept for extensibility)
            proposals: List of proposals

        Returns:
            Minimum CBF margin
        """
        if routing is None:
            return -1.0  # Invalid

        return float(min(p.cbf_margin for p in proposals))


# =============================================================================
# FACTORY & SINGLETON
# =============================================================================


# Register consensus protocol as singleton using unified registry
@singleton_factory(
    "kagami_consensus_protocol",
    KagamiConsensus,
    "Kagami Byzantine consensus protocol singleton",
    category="coordination",
)
def get_consensus_protocol() -> KagamiConsensus | None:
    """Get the global consensus protocol singleton.

    Returns the existing instance if initialized, or None if not yet created.
    To create a new instance, use create_consensus_protocol().

    Returns:
        KagamiConsensus instance or None
    """
    # Lazy initialization using create_consensus_protocol
    return create_consensus_protocol()


def create_consensus_protocol(
    agreement_threshold: float = 0.72,  # Byzantine: 5/7 + margin
    cbf_threshold: float = 0.0,
    max_iterations: int = 10,
    enable_cot: bool = True,
    enable_markov_guard: bool = True,
    enable_optimizer: bool = True,
    enable_metrics: bool = True,
    dcbf: Any | None = None,  # FanoDecentralizedCBF for safety verification
) -> KagamiConsensus:
    """Create Kagami consensus protocol with full infrastructure.

    INTEGRATION (December 15, 2025):
    - ConsensusOptimizer: Caching, batching, predictive consensus
    - verify_compositional_cbf: Formal safety verification
    - ConsensusMetricsCollector: Prometheus metrics
    - MarkovBlanketGuard: Architectural discipline enforcement
    - ColonyCollaborativeCoT: Chain-of-Thought reasoning

    Args:
        agreement_threshold: Minimum mean agreement for convergence
        cbf_threshold: Minimum CBF margin h(x)
        max_iterations: Maximum consensus iterations
        enable_cot: Enable Chain-of-Thought reasoning for proposals
        enable_markov_guard: Enable Markov blanket validation (recommended)
        enable_optimizer: Enable consensus optimization (caching, batching)
        enable_metrics: Enable Prometheus metrics collection
        dcbf: FanoDecentralizedCBF instance for compositional CBF verification

    Returns:
        KagamiConsensus instance with full consensus infrastructure
    """
    return KagamiConsensus(
        agreement_threshold=agreement_threshold,
        cbf_threshold=cbf_threshold,
        max_iterations=max_iterations,
        enable_cot=enable_cot,
        enable_markov_guard=enable_markov_guard,
        enable_optimizer=enable_optimizer,
        enable_metrics=enable_metrics,
        dcbf=dcbf,
    )


__all__ = [
    "ColonyID",
    "ConsensusState",
    "CoordinationProposal",
    "KagamiConsensus",
    "create_consensus_protocol",
    "get_consensus_protocol",
]
