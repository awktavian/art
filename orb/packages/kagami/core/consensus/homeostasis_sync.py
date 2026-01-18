"""Distributed Homeostasis Synchronization via etcd.

Bridges the biological organism (colonies, homeostasis, catastrophe dynamics)
with distributed coordination across K OS instances.

Architecture:
=============

Each instance runs its local homeostasis loop, but:
1. Pushes local state to etcd (vitals, population, pheromones)
2. Watches for global state changes
3. Adjusts local behavior based on global view

Key etcd Paths:
===============

/kagami/homeostasis/
├── global_state         # Aggregated state (leader writes)
├── instances/
│   ├── {instance_1}/    # Per-instance state
│   ├── {instance_2}/
│   └── ...
├── pheromones/
│   ├── spark
│   ├── forge
│   └── ... (per colony)
├── catastrophe/
│   ├── alert            # Emergency broadcasts
│   └── risk/            # Per-colony risk levels
└── world_model/
    ├── e8_code          # Consensus E8 quantized state
    └── s7_phase         # Consensus S7 phase (Fréchet mean)

Consistency Model:
==================

- Local writes: Eventually consistent (push every homeostasis cycle)
- Global reads: Strongly consistent (read from leader)
- Catastrophe: Immediate broadcast (watch triggers emergency sync)

Integration with Homeostasis:
=============================

HomeostasisManager Phase 2a (Superorganism sync) now:
1. Push local state to etcd
2. Read global state
3. Compute deltas (local vs global)
4. Adjust local behavior:
   - If global population low, relax apoptosis
   - If global catastrophe risk high, tighten safety margins
   - If pheromone gradient points elsewhere, migrate tasks

Consensus Algorithms (Dec 6, 2025):
===================================

- E8 Code: WEIGHTED VOTING by population (not simple MODE)
- S7 Phase: FRÉCHET MEAN on S⁷ manifold (not arithmetic mean)
- Consensus Quality: Entropy-based confidence scoring

Created: November 29, 2025
Updated: December 6, 2025 - Geometric consensus algorithms
Status: Production-ready
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from kagami.core.coordination.kagami_consensus import get_consensus_protocol

# Use unified identity (consolidates 8+ duplicate implementations)
from kagami.core.swarm.identity import get_instance_id

if TYPE_CHECKING:
    from kagami.core.unified_agents.unified_organism import UnifiedOrganism

logger = logging.getLogger(__name__)

# Colony domains (octonion basis)
COLONY_DOMAINS = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]


# =============================================================================
# CONSENSUS QUALITY (Dec 6, 2025)
# =============================================================================


class ConsensusStrength(Enum):
    """Consensus quality classification based on entropy and agreement."""

    STRONG = "strong"  # >80% agreement, low entropy
    WEAK = "weak"  # 50-80% agreement, medium entropy
    CONTESTED = "contested"  # <50% agreement, high entropy
    DIVERGENT = "divergent"  # No clear winner, maximum entropy


@dataclass
class ConsensusQuality:
    """Quality metrics for consensus computations.

    Tracks entropy, agreement ratios, and confidence for both E8 and S7 consensus.
    """

    # E8 consensus quality
    e8_entropy: float = 0.0  # Shannon entropy of vote distribution
    e8_agreement_ratio: float = 0.0  # Fraction voting for winner
    e8_num_candidates: int = 0  # Number of distinct codes
    e8_strength: ConsensusStrength = ConsensusStrength.DIVERGENT

    # S7 consensus quality
    s7_variance: float = 0.0  # Angular variance around Fréchet mean
    s7_convergence_iters: int = 0  # Iterations to converge
    s7_max_deviation: float = 0.0  # Max angular distance from mean

    # Overall
    num_instances: int = 0
    confidence: float = 0.0  # Combined confidence [0, 1]

    def is_trustworthy(self) -> bool:
        """Check if consensus is reliable enough for drift detection."""
        return self.confidence > 0.5 and self.e8_strength in (
            ConsensusStrength.STRONG,
            ConsensusStrength.WEAK,
        )


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class InstanceState:
    """State reported by a single K OS instance."""

    instance_id: str
    population: dict[str, int] = field(default_factory=dict[str, Any])  # colony -> count
    vitals: dict[str, float] = field(default_factory=dict[str, Any])  # metric -> value
    pheromones: dict[str, float] = field(default_factory=dict[str, Any])  # colony -> level
    catastrophe_risk: dict[str, float] = field(default_factory=dict[str, Any])  # colony -> risk
    e8_code: list[int] = field(default_factory=list[Any])  # Quantized E8 state
    s7_phase: list[float] = field(default_factory=list[Any])  # S7 phase vector
    timestamp: float = 0.0
    homeostasis_interval: float = 5.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict[str, Any]."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InstanceState:
        """Create from dict[str, Any]."""
        return cls(
            instance_id=data.get("instance_id", ""),
            population=data.get("population", {}),
            vitals=data.get("vitals", {}),
            pheromones=data.get("pheromones", {}),
            catastrophe_risk=data.get("catastrophe_risk", {}),
            e8_code=data.get("e8_code", []),
            s7_phase=data.get("s7_phase", []),
            timestamp=data.get("timestamp", 0.0),
            homeostasis_interval=data.get("homeostasis_interval", 5.0),
        )


@dataclass
class GlobalHomeostasisState:
    """Aggregated homeostasis state across all instances."""

    # Population counts per colony (SUM across instances)
    global_population: dict[str, int] = field(default_factory=dict[str, Any])

    # Pheromone concentrations (MAX across instances - strongest signal)
    pheromones: dict[str, float] = field(default_factory=dict[str, Any])

    # Catastrophe risk per colony (MAX across instances - most urgent)
    catastrophe_risk: dict[str, float] = field(default_factory=dict[str, Any])

    # Vital signs (WEIGHTED AVG by population)
    vital_signs: dict[str, float] = field(default_factory=dict[str, Any])

    # World model core state (consensus E8 code - WEIGHTED VOTING)
    consensus_e8_code: list[int] = field(default_factory=list[Any])

    # Consensus S7 phase (FRÉCHET MEAN on S⁷)
    consensus_s7_phase: list[float] = field(default_factory=list[Any])

    # Instance metadata
    instance_count: int = 0
    total_population: int = 0
    leader_instance: str | None = None

    # Sync metadata
    last_sync: float = 0.0
    sync_version: int = 0

    # Consensus quality (Dec 6, 2025)
    consensus_quality: ConsensusQuality | None = None


@dataclass
class HomeostasisAdjustments:
    """Adjustments to apply to local homeostasis based on global state."""

    # Apoptosis modifier (< 1.0 = less apoptosis, > 1.0 = more)
    apoptosis_modifier: float = 1.0

    # Mitosis modifier (< 1.0 = less mitosis, > 1.0 = more)
    mitosis_modifier: float = 1.0

    # Task migration signals
    task_migrations: list[dict[str, str]] = field(default_factory=list[Any])

    # Emergency signals (catastrophe response)
    emergency_signals: list[dict[str, str]] = field(default_factory=list[Any])

    # World model coherence
    e8_drift_detected: bool = False
    recommended_e8_code: list[int] = field(default_factory=list[Any])

    # S7 phase drift (Dec 6, 2025)
    s7_drift_detected: bool = False
    s7_angular_deviation: float = 0.0  # Radians from consensus
    recommended_s7_phase: list[float] = field(default_factory=list[Any])

    # Homeostasis interval adjustment
    interval_modifier: float = 1.0

    # Whether we should tighten CBF safety margins
    tighten_cbf: bool = False

    # Consensus trustworthiness (Dec 6, 2025)
    consensus_trustworthy: bool = True
    consensus_confidence: float = 1.0


# =============================================================================
# MAIN SYNC CLASS
# =============================================================================


class EtcdHomeostasisSync:
    """Synchronize homeostasis state across K OS instances via etcd.

    Features:
    - Push local state to etcd with TTL
    - Aggregate global state from all instances
    - Compute adjustments for local homeostasis
    - Broadcast and watch catastrophe alerts
    - Track world model coherence (E8/S7 consensus)

    Usage:
        sync = EtcdHomeostasisSync(instance_id, organism)
        await sync.initialize()

        # In homeostasis cycle:
        await sync.push_local_state(population, vitals, pheromones, risk)
        global_state = await sync.pull_global_state()
        adjustments = sync.compute_adjustments(global_state)
        await apply_adjustments(adjustments)
    """

    PREFIX = "/kagami/homeostasis"
    STATE_TTL = 60  # Seconds before instance state expires
    ALERT_TTL = 30  # Seconds for catastrophe alerts
    SYNC_INTERVAL = 5.0  # Minimum seconds between syncs

    def __init__(
        self,
        instance_id: str | None = None,
        organism: UnifiedOrganism | None = None,
    ) -> None:
        """Initialize homeostasis sync.

        Args:
            instance_id: Unique identifier for this instance
            organism: UnifiedOrganism to sync (optional, for callbacks)
        """
        # Use unified identity (consolidates 8+ duplicate implementations)
        self.instance_id = instance_id or get_instance_id()
        self.organism = organism

        # State tracking
        self._local_state: InstanceState | None = None
        self._global_state: GlobalHomeostasisState | None = None
        self._last_push: float = 0.0
        self._last_pull: float = 0.0
        self._sync_version: int = 0

        # etcd client (lazy init)
        self._etcd_available: bool | None = None

        # Watch task for catastrophe alerts
        self._watch_task: asyncio.Task | None = None
        self._shutdown: bool = False

        logger.debug(f"EtcdHomeostasisSync created for instance {self.instance_id}")

    async def initialize(self) -> bool:
        """Initialize etcd connection and start watching.

        Full Operation Mode: etcd is REQUIRED. No single-instance fallback.

        Returns:
            True if initialization succeeded

        Raises:
            RuntimeError: If etcd is not available (Full Operation Mode)
        """
        from kagami.core.consensus import get_etcd_client

        client = get_etcd_client()
        if client is None:
            raise RuntimeError(
                "etcd unavailable - Full Operation Mode requires distributed coordination. "
                "Ensure etcd is running and ETCD_ENDPOINTS is configured."
            )

        self._etcd_available = True

        # Register this instance
        await self._register_instance()

        # Start catastrophe watch
        self._watch_task = asyncio.create_task(self._watch_catastrophe_alerts())

        logger.info(f"✅ Homeostasis sync initialized (instance: {self.instance_id})")
        return True

    async def shutdown(self) -> None:
        """Shutdown sync and cleanup."""
        self._shutdown = True

        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass

        # Deregister instance
        await self._deregister_instance()
        logger.info(f"Homeostasis sync shutdown (instance: {self.instance_id})")

    # =========================================================================
    # PUSH LOCAL STATE
    # =========================================================================

    async def push_local_state(
        self,
        population: dict[str, int],
        vitals: dict[str, float],
        pheromones: dict[str, float],
        catastrophe_risk: dict[str, float],
        e8_code: list[int] | None = None,
        s7_phase: list[float] | None = None,
        homeostasis_interval: float = 5.0,
    ) -> bool:
        """Push local homeostasis state to etcd.

        Called at end of each homeostasis cycle.

        Args:
            population: Agent count per colony
            vitals: Vital sign metrics
            pheromones: Pheromone levels per colony
            catastrophe_risk: Risk level per colony [0, 1]
            e8_code: Quantized E8 lattice indices (optional)
            s7_phase: S7 phase vector (optional)
            homeostasis_interval: Current homeostasis interval

        Returns:
            True if push succeeded
        """
        if not self._etcd_available:
            return False

        # Rate limit pushes
        now = time.time()
        if now - self._last_push < 1.0:  # Max 1 push/second
            return True

        try:
            from kagami.core.consensus import etcd_operation, get_etcd_client

            # Build state
            state = InstanceState(
                instance_id=self.instance_id,
                population=population,
                vitals=vitals,
                pheromones=pheromones,
                catastrophe_risk=catastrophe_risk,
                e8_code=e8_code or [],
                s7_phase=s7_phase or [],
                timestamp=now,
                homeostasis_interval=homeostasis_interval,
            )

            self._local_state = state
            self._sync_version += 1

            # Push to etcd
            key = f"{self.PREFIX}/instances/{self.instance_id}"
            value = json.dumps(state.to_dict())

            with etcd_operation("homeostasis_push"):
                client = get_etcd_client()
                if client:
                    # Create lease for TTL
                    lease = client.lease(self.STATE_TTL)
                    client.put(key, value, lease=lease)

            self._last_push = now

            # Check if we should broadcast catastrophe alert
            max_risk = max(catastrophe_risk.values()) if catastrophe_risk else 0
            if max_risk > 0.7:
                await self._broadcast_catastrophe_alert(catastrophe_risk)

            logger.debug(
                f"Pushed homeostasis state: pop={sum(population.values())}, max_risk={max_risk:.2f}"
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to push homeostasis state: {e}")
            return False

    # =========================================================================
    # PULL GLOBAL STATE
    # =========================================================================

    async def pull_global_state(self) -> GlobalHomeostasisState:
        """Pull and aggregate global state from all instances.

        Aggregation Logic:
        - Population: SUM across instances
        - Vitals: WEIGHTED AVG by population
        - Pheromones: MAX across instances (strongest signal wins)
        - Catastrophe: MAX across instances (most urgent wins)
        - E8 code: MODE (most common quantized state)
        - S7 phase: MEAN

        Returns:
            Aggregated global state
        """
        if not self._etcd_available:
            return self._empty_global_state()

        # Rate limit pulls
        now = time.time()
        if self._global_state and now - self._last_pull < 2.0:
            return self._global_state

        try:
            from kagami.core.consensus import etcd_operation, get_etcd_client

            instances: list[InstanceState] = []

            with etcd_operation("homeostasis_pull"):
                client = get_etcd_client()
                if not client:
                    return self._empty_global_state()

                # Get all instance states
                prefix = f"{self.PREFIX}/instances/"
                for value, _metadata in client.get_prefix(prefix):
                    if value:
                        try:
                            data = json.loads(value.decode("utf-8"))
                            instances.append(InstanceState.from_dict(data))
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            logger.debug(f"Failed to parse instance state: {e}")

            if not instances:
                return self._empty_global_state()

            # Aggregate
            global_state = self._aggregate_instances(instances)
            self._global_state = global_state
            self._last_pull = now

            logger.debug(
                f"Pulled global state: {global_state.instance_count} instances, "
                f"total_pop={global_state.total_population}"
            )
            return global_state

        except Exception as e:
            logger.warning(f"Failed to pull global state: {e}")
            return self._empty_global_state()

    def _aggregate_instances(
        self,
        instances: list[InstanceState],
    ) -> GlobalHomeostasisState:
        """Aggregate instance states into global state.

        Uses geometrically correct consensus algorithms (Dec 6, 2025):
        - E8: Weighted voting by population
        - S7: Fréchet mean on the sphere
        """
        global_pop: dict[str, int] = {}
        global_vitals: dict[str, list[tuple[float, int]]] = {}  # (value, weight)
        global_pheromones: dict[str, float] = {}
        global_risk: dict[str, float] = {}
        e8_codes: list[tuple[int, ...]] = []
        e8_weights: list[int] = []  # Population weights for E8 voting
        s7_phases: list[list[float]] = []
        total_pop = 0

        for inst in instances:
            # Population: SUM
            inst_pop = sum(inst.population.values())
            total_pop += inst_pop
            for colony, count in inst.population.items():
                global_pop[colony] = global_pop.get(colony, 0) + count

            # Vitals: weighted by population
            for metric, value in inst.vitals.items():
                global_vitals.setdefault(metric, []).append((value, inst_pop))

            # Pheromones: MAX
            for colony, level in inst.pheromones.items():
                global_pheromones[colony] = max(global_pheromones.get(colony, 0.0), level)

            # Catastrophe: MAX
            for colony, risk in inst.catastrophe_risk.items():
                global_risk[colony] = max(global_risk.get(colony, 0.0), risk)

            # E8 codes for weighted consensus
            if inst.e8_code:
                e8_codes.append(tuple(inst.e8_code))
                e8_weights.append(max(1, inst_pop))  # Min weight of 1

            # S7 phases for Fréchet mean
            if inst.s7_phase:
                s7_phases.append(inst.s7_phase)

        # Compute weighted average vitals
        agg_vitals: dict[str, float] = {}
        for metric, weighted_values in global_vitals.items():
            total_weight = sum(w for _, w in weighted_values)
            if total_weight > 0:
                agg_vitals[metric] = sum(v * w for v, w in weighted_values) / total_weight
            else:
                agg_vitals[metric] = sum(v for v, _ in weighted_values) / len(weighted_values)

        # Compute E8 consensus (weighted voting)
        consensus_e8, e8_quality = self._compute_e8_consensus(e8_codes, e8_weights)

        # Compute S7 consensus (Fréchet mean on sphere)
        consensus_s7, s7_quality = self._compute_s7_consensus(s7_phases)

        # Merge quality metrics
        consensus_quality = ConsensusQuality(
            e8_entropy=e8_quality.e8_entropy,
            e8_agreement_ratio=e8_quality.e8_agreement_ratio,
            e8_num_candidates=e8_quality.e8_num_candidates,
            e8_strength=e8_quality.e8_strength,
            s7_variance=s7_quality.s7_variance,
            s7_convergence_iters=s7_quality.s7_convergence_iters,
            s7_max_deviation=s7_quality.s7_max_deviation,
            num_instances=len(instances),
            confidence=e8_quality.confidence,  # Primary confidence from E8
        )

        # Get current homeostasis leader from leader election
        leader_instance = self._get_homeostasis_leader()

        return GlobalHomeostasisState(
            global_population=global_pop,
            pheromones=global_pheromones,
            catastrophe_risk=global_risk,
            vital_signs=agg_vitals,
            consensus_e8_code=consensus_e8,
            consensus_s7_phase=consensus_s7,
            instance_count=len(instances),
            total_population=total_pop,
            leader_instance=leader_instance,
            last_sync=time.time(),
            sync_version=self._sync_version,
            consensus_quality=consensus_quality,
        )

    def _compute_e8_consensus(
        self,
        codes: list[tuple[int, ...]],
        weights: list[int] | None = None,
    ) -> tuple[list[int], ConsensusQuality]:
        """Compute consensus E8 code with WEIGHTED VOTING and quality metrics.

        Algorithm (Dec 6, 2025):
        1. Weight each vote by instance population (larger instances have more say)
        2. Compute Shannon entropy of vote distribution
        3. Classify consensus strength

        Args:
            codes: List of E8 code tuples from each instance
            weights: Population weights per instance (optional)

        Returns:
            Tuple of (consensus_code, quality_metrics)
        """
        quality = ConsensusQuality(num_instances=len(codes))

        if not codes:
            return [], quality

        # Default to equal weights
        if weights is None:
            weights = [1] * len(codes)

        # Weighted vote counting
        weighted_counter: dict[tuple[int, ...], int] = {}
        total_weight = sum(weights)

        for code, weight in zip(codes, weights, strict=True):
            weighted_counter[code] = weighted_counter.get(code, 0) + weight

        # Find winner
        winner = max(weighted_counter.items(), key=lambda x: x[1])
        consensus_code = list(winner[0])
        winner_weight = winner[1]

        # Compute quality metrics
        quality.e8_num_candidates = len(weighted_counter)
        quality.e8_agreement_ratio = winner_weight / total_weight if total_weight > 0 else 0

        # Shannon entropy: -Σ p(x) log p(x)
        entropy = 0.0
        for count in weighted_counter.values():
            p = count / total_weight if total_weight > 0 else 0
            if p > 0:
                entropy -= p * math.log2(p)

        quality.e8_entropy = entropy

        # Classify strength based on agreement ratio
        if quality.e8_agreement_ratio > 0.8:
            quality.e8_strength = ConsensusStrength.STRONG
        elif quality.e8_agreement_ratio > 0.5:
            quality.e8_strength = ConsensusStrength.WEAK
        elif quality.e8_agreement_ratio > 0.3:
            quality.e8_strength = ConsensusStrength.CONTESTED
        else:
            quality.e8_strength = ConsensusStrength.DIVERGENT

        # Overall confidence
        # High agreement + low entropy = high confidence
        max_entropy = math.log2(max(1, len(weighted_counter)))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        quality.confidence = quality.e8_agreement_ratio * (1 - normalized_entropy)

        logger.debug(
            f"E8 consensus: {len(codes)} votes, {quality.e8_num_candidates} candidates, "
            f"agreement={quality.e8_agreement_ratio:.1%}, entropy={entropy:.2f} bits, "
            f"strength={quality.e8_strength.value}"
        )

        return consensus_code, quality

    def _compute_s7_consensus(
        self,
        phases: list[list[float]],
        max_iterations: int = 100,
        tolerance: float = 1e-6,
    ) -> tuple[list[float], ConsensusQuality]:
        """Compute consensus S7 phase using FRÉCHET MEAN on the sphere.

        The Fréchet mean minimizes sum of squared geodesic distances on S⁷.
        This is geometrically correct for spherical data, unlike arithmetic mean.

        Algorithm (Dec 6, 2025):
        1. Initialize with normalized arithmetic mean
        2. Iteratively compute tangent space mean and project back
        3. Converge when movement < tolerance

        For S⁷ (unit sphere in R⁸):
        - Geodesic distance: arccos(⟨x,y⟩)
        - Log map: log_x(y) = arccos(⟨x,y⟩) * (y - ⟨x,y⟩x) / ||y - ⟨x,y⟩x||
        - Exp map: exp_x(v) = cos(||v||)x + sin(||v||) * v/||v||

        Args:
            phases: List of S7 phase vectors (should be unit norm)
            max_iterations: Maximum Fréchet iterations
            tolerance: Convergence threshold

        Returns:
            Tuple of (consensus_phase, quality_metrics)
        """
        quality = ConsensusQuality(num_instances=len(phases))

        if not phases:
            return [], quality

        # Ensure all phases have same length (should be 7 for S⁷, embedded in R⁸)
        min_len = min(len(p) for p in phases)
        if min_len == 0:
            return [], quality

        # Truncate to minimum length
        phases = [p[:min_len] for p in phases]
        n_points = len(phases)

        def normalize(v: list[float]) -> list[float]:
            """Project onto unit sphere."""
            norm = math.sqrt(sum(x * x for x in v))
            if norm < 1e-10:
                return [1.0] + [0.0] * (len(v) - 1)  # Default to first basis vector
            return [x / norm for x in v]

        def dot(a: list[float], b: list[float]) -> float:
            """Inner product."""
            return sum(ai * bi for ai, bi in zip(a, b, strict=True))

        def geodesic_distance(a: list[float], b: list[float]) -> float:
            """Geodesic (arc) distance on sphere."""
            d = dot(a, b)
            # Clamp for numerical stability
            d = max(-1.0, min(1.0, d))
            return math.acos(d)

        def log_map(base: list[float], point: list[float]) -> list[float]:
            """Log map from base to point (tangent vector at base)."""
            dp = dot(base, point)
            dp = max(-1.0, min(1.0, dp))

            # Handle antipodal or identical points
            if dp >= 1.0 - 1e-10:
                return [0.0] * len(base)  # Same point
            if dp <= -1.0 + 1e-10:
                # Antipodal - return arbitrary tangent direction
                tangent = [0.0] * len(base)
                for i in range(len(base)):
                    if abs(base[i]) < 0.9:
                        tangent[i] = 1.0
                        break
                else:
                    tangent[0] = 1.0
                return tangent

            theta = math.acos(dp)
            # v = point - dp * base, then normalize and scale by theta
            v = [point[i] - dp * base[i] for i in range(len(base))]
            v_norm = math.sqrt(sum(x * x for x in v))
            if v_norm < 1e-10:
                return [0.0] * len(base)

            return [theta * x / v_norm for x in v]

        def exp_map(base: list[float], tangent: list[float]) -> list[float]:
            """Exp map from base along tangent (back to sphere)."""
            t_norm = math.sqrt(sum(x * x for x in tangent))
            if t_norm < 1e-10:
                return base.copy()

            # exp_base(v) = cos(||v||)*base + sin(||v||)*v/||v||
            cos_t = math.cos(t_norm)
            sin_t = math.sin(t_norm)
            return [cos_t * base[i] + sin_t * tangent[i] / t_norm for i in range(len(base))]

        # Normalize all input phases
        phases = [normalize(p) for p in phases]

        # Initialize mean with arithmetic mean (projected to sphere)
        mean = [sum(p[i] for p in phases) / n_points for i in range(min_len)]
        mean = normalize(mean)

        # Fréchet iteration
        for iteration in range(max_iterations):
            # Compute mean tangent vector (average of log maps)
            tangent_sum = [0.0] * min_len
            for p in phases:
                tangent = log_map(mean, p)
                for i in range(min_len):
                    tangent_sum[i] += tangent[i]

            tangent_mean = [t / n_points for t in tangent_sum]

            # Move along mean tangent
            new_mean = exp_map(mean, tangent_mean)
            new_mean = normalize(new_mean)

            # Check convergence
            movement = geodesic_distance(mean, new_mean)
            mean = new_mean

            if movement < tolerance:
                quality.s7_convergence_iters = iteration + 1
                break
        else:
            quality.s7_convergence_iters = max_iterations

        # Compute quality metrics
        distances = [geodesic_distance(mean, p) for p in phases]
        quality.s7_variance = sum(d * d for d in distances) / n_points if n_points > 0 else 0
        quality.s7_max_deviation = max(distances) if distances else 0

        logger.debug(
            f"S7 Fréchet mean: converged in {quality.s7_convergence_iters} iters, "
            f"variance={quality.s7_variance:.4f}, max_dev={quality.s7_max_deviation:.2f} rad"
        )

        return mean, quality

    def _get_homeostasis_leader(self) -> str | None:
        """Get the current leader instance for homeostasis coordination.

        Returns:
            Instance ID of the leader, or None if not elected.
        """
        try:
            consensus = get_consensus_protocol()
            if consensus:
                state = consensus.current_state  # type: ignore[attr-defined]
                if state.converged and state.leader_id:
                    return state.leader_id  # type: ignore[no-any-return]
        except Exception as e:
            logger.debug(f"Failed to get homeostasis leader: {e}")
        return None

    # =========================================================================
    # COMPUTE ADJUSTMENTS
    # =========================================================================

    def compute_adjustments(
        self,
        global_state: GlobalHomeostasisState,
    ) -> HomeostasisAdjustments:
        """Compute adjustments for local homeostasis based on global state.

        This is the intelligence layer - deciding how local behavior should
        change based on global view.

        Updated Dec 6, 2025:
        - Only trigger E8/S7 drift if consensus is trustworthy
        - Include S7 angular deviation measurement
        - Report consensus confidence

        Args:
            global_state: Aggregated global state

        Returns:
            Adjustments to apply locally
        """
        adjustments = HomeostasisAdjustments()

        if not self._local_state:
            return adjustments

        local = self._local_state
        local_pop = sum(local.population.values())
        global_pop = global_state.total_population

        # Set consensus trustworthiness from quality metrics
        if global_state.consensus_quality:
            adjustments.consensus_trustworthy = global_state.consensus_quality.is_trustworthy()
            adjustments.consensus_confidence = global_state.consensus_quality.confidence

        # 1. Population-based adjustments
        if global_pop > 0:
            local_fraction = local_pop / global_pop

            # If we're underrepresented, reduce apoptosis pressure
            if local_fraction < 0.15:
                adjustments.apoptosis_modifier = 0.5
                adjustments.mitosis_modifier = 1.2
                logger.debug(
                    f"Population adjustment: local={local_pop}/{global_pop} "
                    f"({local_fraction:.1%}) - reducing apoptosis"
                )

            # If we're overrepresented, increase apoptosis
            elif local_fraction > 0.6:
                adjustments.apoptosis_modifier = 1.5
                adjustments.mitosis_modifier = 0.8
                logger.debug(
                    f"Population adjustment: local={local_pop}/{global_pop} "
                    f"({local_fraction:.1%}) - increasing apoptosis"
                )

        # 2. Pheromone-driven task migration
        for colony, global_level in global_state.pheromones.items():
            local_level = local.pheromones.get(colony, 0.0)

            # If global pheromone much stronger elsewhere, suggest migration
            if global_level > local_level + 0.3:
                adjustments.task_migrations.append(
                    {
                        "colony": colony,
                        "direction": "out",
                        "reason": f"global_pheromone={global_level:.2f} > local={local_level:.2f}",
                    }
                )

        # 3. Catastrophe response
        for colony, global_risk in global_state.catastrophe_risk.items():
            local_risk = local.catastrophe_risk.get(colony, 0.0)

            if global_risk > 0.7:
                adjustments.emergency_signals.append(
                    {
                        "colony": colony,
                        "action": "tighten_cbf",
                        "global_risk": str(global_risk),
                        "local_risk": str(local_risk),
                    }
                )
                adjustments.tighten_cbf = True

            if global_risk > 0.5:
                # Speed up homeostasis when risk is elevated
                adjustments.interval_modifier = min(adjustments.interval_modifier, 0.7)

        # 4. World model coherence (E8 drift)
        # Only trigger drift detection if consensus is trustworthy
        if global_state.consensus_e8_code and local.e8_code:
            if local.e8_code != global_state.consensus_e8_code:
                if adjustments.consensus_trustworthy:
                    adjustments.e8_drift_detected = True
                    adjustments.recommended_e8_code = global_state.consensus_e8_code
                    logger.info(
                        f"E8 drift detected: local={local.e8_code[:3]}... "
                        f"vs consensus={global_state.consensus_e8_code[:3]}... "
                        f"(confidence={adjustments.consensus_confidence:.1%})"
                    )
                else:
                    logger.debug(
                        f"E8 mismatch ignored: consensus not trustworthy "
                        f"(confidence={adjustments.consensus_confidence:.1%})"
                    )

        # 5. World model coherence (S7 drift) - Dec 6, 2025
        if global_state.consensus_s7_phase and local.s7_phase:
            # Compute angular deviation between local and consensus
            angular_dev = self._compute_s7_angular_distance(
                local.s7_phase, global_state.consensus_s7_phase
            )
            adjustments.s7_angular_deviation = angular_dev

            # Drift threshold: ~15 degrees (0.26 radians)
            S7_DRIFT_THRESHOLD = 0.26
            if angular_dev > S7_DRIFT_THRESHOLD:
                if adjustments.consensus_trustworthy:
                    adjustments.s7_drift_detected = True
                    adjustments.recommended_s7_phase = global_state.consensus_s7_phase
                    logger.info(
                        f"S7 drift detected: angular deviation={math.degrees(angular_dev):.1f}° "
                        f"(threshold={math.degrees(S7_DRIFT_THRESHOLD):.1f}°)"
                    )

        return adjustments

    def _compute_s7_angular_distance(
        self,
        a: list[float],
        b: list[float],
    ) -> float:
        """Compute geodesic distance between two S7 points.

        Args:
            a: First S7 phase vector
            b: Second S7 phase vector

        Returns:
            Angular distance in radians [0, π]
        """
        if not a or not b:
            return 0.0

        # Ensure same length
        min_len = min(len(a), len(b))
        if min_len == 0:
            return 0.0

        # Dot product
        dot = sum(a[i] * b[i] for i in range(min_len))
        # Clamp for numerical stability
        dot = max(-1.0, min(1.0, dot))
        return math.acos(dot)

    # =========================================================================
    # CATASTROPHE BROADCASTING
    # =========================================================================

    async def _broadcast_catastrophe_alert(
        self,
        risk: dict[str, float],
    ) -> None:
        """Broadcast high catastrophe risk to all instances.

        Uses etcd watch to trigger immediate response across cluster.
        """
        try:
            from kagami.core.consensus import etcd_operation, get_etcd_client

            alert = {
                "source": self.instance_id,
                "risk": risk,
                "timestamp": time.time(),
                "max_risk": max(risk.values()) if risk else 0,
            }

            key = f"{self.PREFIX}/catastrophe/alert"
            value = json.dumps(alert)

            with etcd_operation("catastrophe_broadcast"):
                client = get_etcd_client()
                if client:
                    lease = client.lease(self.ALERT_TTL)
                    client.put(key, value, lease=lease)

            # LOGSPAM FIX (Dec 30, 2025): Only warn for actual high-risk situations
            # Regular periodic broadcasts (max_risk=1.0 is often initialization state) should be DEBUG
            max_risk = alert["max_risk"]
            if max_risk > 0.8:
                logger.warning(f"⚠️ Catastrophe alert broadcast: max_risk={max_risk:.2f}")
            else:
                logger.debug(f"Catastrophe alert broadcast: max_risk={max_risk:.2f}")

        except Exception as e:
            logger.error(f"Failed to broadcast catastrophe alert: {e}")

    async def _watch_catastrophe_alerts(self) -> None:
        """Watch for catastrophe broadcasts from other instances.

        NOTE: etcd3's watch() is synchronous/blocking, so we run it in a thread.
        """
        if not self._etcd_available:
            return

        try:
            from kagami.core.consensus import get_etcd_client

            key = f"{self.PREFIX}/catastrophe/alert"

            def _blocking_watch() -> list[dict[str, Any]]:
                """Run blocking etcd watch in thread, collect events."""
                events: list[dict[str, Any]] = []
                try:
                    client = get_etcd_client()
                    if not client:
                        return events

                    # Use watch_once with timeout instead of blocking iterator
                    # This prevents indefinite blocking
                    try:
                        value, _ = client.get(key)
                        if value:
                            events.append({"value": value})
                    except Exception:
                        pass
                except Exception:
                    pass
                return events

            while not self._shutdown:
                try:
                    # Run blocking etcd operation in thread pool with timeout
                    events = await asyncio.wait_for(
                        asyncio.to_thread(_blocking_watch),
                        timeout=5.0,
                    )

                    for event_data in events:
                        if self._shutdown:
                            break

                        value = event_data.get("value")
                        if value:
                            try:
                                alert = json.loads(
                                    value.decode("utf-8") if isinstance(value, bytes) else value
                                )
                                if alert.get("source") != self.instance_id:
                                    await self._handle_catastrophe_alert(alert)
                            except (json.JSONDecodeError, UnicodeDecodeError):
                                pass

                    # Poll interval - don't spam etcd
                    await asyncio.sleep(5)

                except TimeoutError:
                    # Normal timeout, continue polling
                    pass
                except Exception as e:
                    if not self._shutdown:
                        logger.debug(f"Catastrophe watch error: {e}")
                        await asyncio.sleep(5)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Catastrophe watch failed: {e}")

    async def _handle_catastrophe_alert(self, alert: dict[str, Any]) -> None:
        """Handle catastrophe alert from another instance."""
        source = alert.get("source", "unknown")
        max_risk = alert.get("max_risk", 0)
        risk = alert.get("risk", {})

        logger.warning(
            f"⚠️ Received catastrophe alert from {source}: "
            f"max_risk={max_risk:.2f}, colonies={list(risk.keys())}"
        )

        # Apply emergency response
        if self.organism:
            # Tighten homeostasis interval
            if hasattr(self.organism, "homeostasis_interval"):
                self.organism.homeostasis_interval = max(
                    1.0, self.organism.homeostasis_interval * 0.5
                )
                logger.info(
                    f"Tightened homeostasis interval to {self.organism.homeostasis_interval:.1f}s"
                )

            # Signal danger to relevant colonies
            if hasattr(self.organism, "_signal_agent_danger"):
                for colony, colony_risk in risk.items():
                    if colony_risk > 0.7:
                        # This is cross-instance alert, signal to all agents in colony
                        logger.info(f"Signaling danger to colony {colony}")

    # =========================================================================
    # INSTANCE REGISTRATION
    # =========================================================================

    async def _register_instance(self) -> None:
        """Register this instance in etcd."""
        try:
            from kagami.core.consensus import etcd_operation, get_etcd_client
            from kagami.core.swarm.identity import get_instance_identity

            identity = get_instance_identity()

            registration = {
                "instance_id": self.instance_id,
                "registered_at": time.time(),
                "hostname": identity.hostname,
                "pid": identity.pid,
            }

            key = f"{self.PREFIX}/registry/{self.instance_id}"
            value = json.dumps(registration)

            with etcd_operation("instance_register"):
                client = get_etcd_client()
                if client:
                    lease = client.lease(self.STATE_TTL * 2)  # Longer TTL for registry
                    client.put(key, value, lease=lease)

            logger.debug(f"Registered instance: {self.instance_id}")

        except Exception as e:
            logger.warning(f"Failed to register instance: {e}")

    async def _deregister_instance(self) -> None:
        """Deregister this instance from etcd."""
        try:
            from kagami.core.consensus import etcd_operation, get_etcd_client

            with etcd_operation("instance_deregister"):
                client = get_etcd_client()
                if client:
                    # Delete instance state
                    client.delete(f"{self.PREFIX}/instances/{self.instance_id}")
                    # Delete registry entry
                    client.delete(f"{self.PREFIX}/registry/{self.instance_id}")

            logger.debug(f"Deregistered instance: {self.instance_id}")

        except Exception as e:
            logger.debug(f"Failed to deregister instance: {e}")

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _empty_global_state(self) -> GlobalHomeostasisState:
        """Return empty global state for single-instance mode."""
        return GlobalHomeostasisState(
            global_population={},
            pheromones={},
            catastrophe_risk={},
            vital_signs={},
            consensus_e8_code=[],
            consensus_s7_phase=[],
            instance_count=1,
            total_population=0,
            leader_instance=self.instance_id,
            last_sync=time.time(),
            sync_version=0,
        )

    @property
    def is_available(self) -> bool:
        """Check if sync is available (etcd connected)."""
        return self._etcd_available is True

    def get_local_state(self) -> InstanceState | None:
        """Get last pushed local state."""
        return self._local_state

    def get_global_state(self) -> GlobalHomeostasisState | None:
        """Get last pulled global state."""
        return self._global_state


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_homeostasis_sync: EtcdHomeostasisSync | None = None
_sync_lock = asyncio.Lock()


async def get_homeostasis_sync(
    organism: UnifiedOrganism | None = None,
    instance_id: str | None = None,
) -> EtcdHomeostasisSync:
    """Get or create homeostasis sync singleton.

    Args:
        organism: UnifiedOrganism for callbacks (first call only)
        instance_id: Instance ID override (first call only)

    Returns:
        EtcdHomeostasisSync instance
    """
    global _homeostasis_sync

    async with _sync_lock:
        if _homeostasis_sync is None:
            _homeostasis_sync = EtcdHomeostasisSync(
                instance_id=instance_id,
                organism=organism,
            )
            await _homeostasis_sync.initialize()

        return _homeostasis_sync


def get_homeostasis_sync_sync() -> EtcdHomeostasisSync | None:
    """Synchronous getter for homeostasis sync (for non-async contexts).

    Returns:
        EtcdHomeostasisSync instance or None if not initialized
    """
    return _homeostasis_sync


async def shutdown_homeostasis_sync() -> None:
    """Shutdown homeostasis sync."""
    global _homeostasis_sync

    if _homeostasis_sync:
        await _homeostasis_sync.shutdown()
        _homeostasis_sync = None
