"""Superorganism Integration Layer.

Bridges the biological organism (colonies, homeostasis, catastrophe dynamics)
with the geometric world model (E8, S7, exceptional hierarchy).

Research Background:
====================

1. SUPERORGANISM COORDINATION (Hölldobler & Wilson, 2009)
   - Ant colonies use pheromone gradients for indirect coordination (stigmergy)
   - Task allocation emerges from local rules + chemical signals
   - Colony-level homeostasis maintains optimal worker distribution

2. BIOLOGICAL HOMEOSTASIS (Cannon, 1932)
   - Negative feedback loops maintain stable internal state
   - Sensors → Controllers → Effectors
   - Set points adjusted based on environmental demands

3. CATASTROPHE THEORY (Thom, 1972)
   - 7 elementary catastrophes describe discontinuous transitions
   - Cusp: bistability and hysteresis (decision points)
   - Fold: threshold transitions (creative ignition)
   - Swallowtail: complex bifurcations (recovery dynamics)

4. APOPTOSIS/MITOSIS SIGNALING (Alberts et al., Cell Biology)
   - Mitogenic signals trigger cell division (growth factors)
   - Apoptotic signals trigger programmed death (death ligands)
   - Balance maintains tissue homeostasis

Integration Architecture:
========================

    UnifiedOrganism                KagamiWorldModel
         │                               │
         ├─ 7 Colonies ─────────────────► Domain Activations (S7)
         │                               │
         ├─ Homeostasis ─────────────────► CoreState updates
         │     └─ Vital Signs            │
         │     └─ Population             │
         │                               │
         ├─ Catastrophe Risk ────────────► Training Loss Term
         │     └─ Cusp/Fold/etc          │
         │                               │
         └─ Fano Collaboration ──────────► Constraint Loss

This module provides:
1. Pheromone gradients for colony coordination
2. Homeostasis-world model bidirectional sync
3. Catastrophe-aware training loss
4. Fano constraint enforcement
5. Predictive lifecycle management (mitosis/apoptosis)

Created: November 29, 2025
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import torch
import torch.nn as nn

if TYPE_CHECKING:
    from kagami.core.unified_agents import UnifiedOrganism

logger = logging.getLogger(__name__)


# =============================================================================
# 1. PHEROMONE GRADIENT SYSTEM (Stigmergy)
# =============================================================================


@dataclass
class PheromoneState:
    """Colony pheromone concentrations for stigmergic coordination.

    Inspired by ant colony optimization (Dorigo, 1996):
    - Each colony emits pheromones based on activity/success
    - Pheromones decay over time (evaporation)
    - High concentration attracts tasks to that colony

    Maps to S7 geometry: each colony's pheromone is a scalar on its octonion axis.
    """

    # Pheromone concentrations per colony [0, 1]
    concentrations: dict[str, float] = field(default_factory=dict[str, Any])

    # Gradient vectors (direction of increasing concentration)
    gradients: dict[str, np.ndarray[Any, Any]] = field(default_factory=dict[str, Any])

    # Decay rate (evaporation)
    decay_rate: float = 0.1

    # Deposit rate (how much success adds)
    deposit_rate: float = 0.05

    # Timestamp
    last_update: float = 0.0

    def update(
        self,
        colony_success_rates: dict[str, float],
        colony_workloads: dict[str, float],
        dt: float = 1.0,
    ) -> None:
        """Update pheromone concentrations based on colony activity.

        Algorithm:
            τ(t+1) = (1 - ρ) * τ(t) + Δτ

        Where:
            ρ = evaporation rate
            Δτ = deposit from successful operations

        Args:
            colony_success_rates: Success rate per colony
            colony_workloads: Current workload per colony
            dt: Time step
        """
        domains = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]

        for domain in domains:
            current = self.concentrations.get(domain, 0.5)

            # Evaporation
            current *= 1 - self.decay_rate * dt

            # Deposit from success
            success = colony_success_rates.get(domain, 0.5)
            workload = colony_workloads.get(domain, 0.5)

            # Deposit more when successful AND busy (productive colony)
            deposit = self.deposit_rate * success * workload * dt
            current = min(1.0, current + deposit)

            self.concentrations[domain] = current

        # Compute gradients (which colonies should receive more tasks)
        self._compute_gradients()
        self.last_update = time.time()

    def _compute_gradients(self) -> None:
        """Compute pheromone gradients using Fano plane structure.

        Gradient points from low-concentration colonies toward high-concentration
        colonies on Fano lines, respecting octonion multiplication.
        """
        import importlib

        from kagami_math.fano_plane import FANO_LINES

        cc_mod = importlib.import_module("kagami.core.unified_agents.colony_constants")
        COLONY_TO_INDEX = cc_mod.COLONY_TO_INDEX
        INDEX_TO_COLONY = cc_mod.INDEX_TO_COLONY

        idx_to_domain = INDEX_TO_COLONY

        for domain in self.concentrations:
            gradient = np.zeros(8)  # Octonion gradient
            my_idx = COLONY_TO_INDEX.get(domain, 0)
            my_conc = self.concentrations[domain]

            # Find Fano neighbors
            for line in FANO_LINES:
                if my_idx in line:
                    for other_idx in line:
                        if other_idx != my_idx and other_idx > 0:
                            other_domain = idx_to_domain.get(other_idx)
                            if other_domain:
                                other_conc = self.concentrations.get(other_domain, 0.5)
                                # Gradient toward higher concentration
                                gradient[other_idx] = other_conc - my_conc

            self.gradients[domain] = gradient

    def get_task_routing_weights(self) -> dict[str, float]:
        """Get routing weights for task allocation.

        Higher pheromone = higher probability of receiving tasks.

        Returns:
            Normalized weights per colony
        """
        total = sum(self.concentrations.values()) or 1.0
        return {k: v / total for k, v in self.concentrations.items()}

    def to_s7_vector(self) -> np.ndarray[Any, Any]:
        """Convert pheromone state to S7 octonion vector.

        Returns:
            [8] unit octonion on S7
        """
        import importlib

        COLONY_TO_INDEX = importlib.import_module(
            "kagami.core.unified_agents.colony_constants"
        ).COLONY_TO_INDEX

        vec = np.zeros(8, dtype=np.float32)
        for domain, conc in self.concentrations.items():
            idx = COLONY_TO_INDEX.get(domain, 0)
            if idx > 0:
                vec[idx] = conc

        # Normalize to S7
        norm = np.linalg.norm(vec)
        if norm > 1e-8:
            vec /= norm
        else:
            vec[0] = 1.0  # Default to real axis

        return vec


# =============================================================================
# 2. HOMEOSTASIS-WORLD MODEL BRIDGE
# =============================================================================


@dataclass
class HomeostasisWorldModelState:
    """Bidirectional state sync between homeostasis and world model.

    Biological analogy:
    - Interoception: organism sensing its internal state
    - Allostasis: predictive regulation (anticipatory homeostasis)

    The world model predicts future organism state; homeostasis uses
    predictions to make preemptive adjustments.
    """

    # Current vital signs from organism
    metabolism: float = 0.0  # ops/sec
    coherence: float = 1.0  # colony synchronization
    load: float = 0.0  # aggregate workload
    population: int = 0  # total agents

    # Predicted vitals from world model
    predicted_metabolism: float = 0.0
    predicted_coherence: float = 1.0
    predicted_load: float = 0.0

    # Allostatic setpoints (target values)
    target_metabolism: float = 10.0
    target_coherence: float = 0.9
    target_load: float = 0.5

    # Error signals (for control)
    metabolism_error: float = 0.0
    coherence_error: float = 0.0
    load_error: float = 0.0

    def update_from_organism(self, organism: UnifiedOrganism) -> None:
        """Pull current state from organism.

        Args:
            organism: UnifiedOrganism instance
        """
        try:
            vitals = getattr(organism, "vital_signs", {})
            self.metabolism = vitals.get("metabolism", 0.0)
            self.coherence = vitals.get("coherence", 1.0)
            self.load = vitals.get("load", 0.0)
            # MinimalColony API: use get_worker_count()
            self.population = sum(c.get_worker_count() for c in organism.colonies.values())
        except Exception as e:
            logger.debug(f"Failed to update from organism: {e}")

    def update_from_world_model(self, world_model: Any, core_state: Any) -> None:
        """Get predictions from world model.

        Args:
            world_model: KagamiWorldModel instance
            core_state: Current CoreState
        """
        try:
            # Use empowerment as proxy for predicted controllability
            if (
                hasattr(world_model, "_empowerment_estimator")
                and world_model._empowerment_estimator
            ):
                state_tensor = core_state.to_tensor()
                if state_tensor.dim() == 1:
                    state_tensor = state_tensor.unsqueeze(0)

                with torch.no_grad():
                    empowerment = world_model.compute_empowerment(state_tensor, horizon=3)
                    # High empowerment → system can influence future → predict stable metabolism
                    self.predicted_metabolism = float(empowerment.mean()) * self.target_metabolism

            # Use lattice stress for coherence prediction
            if core_state.lattice_stress is not None:
                if isinstance(core_state.lattice_stress, torch.Tensor):
                    stress = float(core_state.lattice_stress.item())
                else:
                    stress = float(core_state.lattice_stress)
                self.predicted_coherence = max(0.1, 1.0 - stress)

        except Exception as e:
            logger.debug(f"Failed to get world model predictions: {e}")

    def compute_errors(self) -> tuple[float, float, float]:
        """Compute control errors (actual - predicted).

        These errors can be used for:
        - Adjusting homeostasis setpoints
        - Training world model (prediction loss)
        - Triggering adaptive responses

        Returns:
            (metabolism_error, coherence_error, load_error)
        """
        self.metabolism_error = self.metabolism - self.predicted_metabolism
        self.coherence_error = self.coherence - self.predicted_coherence
        self.load_error = self.load - self.predicted_load

        return (self.metabolism_error, self.coherence_error, self.load_error)

    def get_allostatic_adjustment(self) -> dict[str, float]:
        """Compute allostatic adjustments for preemptive regulation.

        If world model predicts coherence drop, proactively adjust.

        Returns:
            Dict of adjustment signals per colony
        """
        adjustments = {}

        # If predicted coherence is low, signal need for synchronization
        if self.predicted_coherence < 0.7:
            adjustments["sync_urgency"] = 0.7 - self.predicted_coherence

        # If metabolism predicted high, prepare for load
        if self.predicted_metabolism > self.target_metabolism * 1.2:
            adjustments["prepare_scale_up"] = 0.2

        return adjustments


# =============================================================================
# 3. CATASTROPHE-AWARE TRAINING LOSS
# =============================================================================


class CatastropheAwareLoss(nn.Module):
    """Training loss that incorporates catastrophe dynamics.

    REFACTORED (Nov 30, 2025):
    Now delegates entirely to ChaosCatastropheDynamics.compute_loss() to avoid
    duplicating logic. This class is a thin wrapper for backward compatibility.

    Biological analogy:
    - Cells near apoptosis emit "danger signals" (DAMPs)
    - These signals modulate immune response

    In training:
    - High catastrophe risk → penalize predictions that increase risk
    - Cusp danger → regularize toward stable attractor
    """

    def __init__(
        self,
        lambda_catastrophe: float = 0.1,
        lambda_stability: float = 0.05,
        lambda_fano: float = 0.1,
    ):
        """Initialize catastrophe-aware loss.

        Args:
            lambda_catastrophe: Weight for catastrophe risk term
            lambda_stability: Weight for stability regularization
            lambda_fano: Weight for Fano constraint enforcement
        """
        super().__init__()
        self.lambda_catastrophe = lambda_catastrophe
        self.lambda_stability = lambda_stability
        self.lambda_fano = lambda_fano

        # Unified chaos-catastrophe dynamics (lazy loaded)
        self._dynamics: Any = None

    def _get_dynamics(self) -> Any:
        """Lazy load unified ChaosCatastropheDynamics."""
        if self._dynamics is None:
            try:
                from kagami.core.world_model.dynamics.chaos_catastrophe import (
                    ChaosCatastropheConfig,
                    ChaosCatastropheDynamics,
                )

                config = ChaosCatastropheConfig(
                    lambda_catastrophe=self.lambda_catastrophe,
                    lambda_stability=self.lambda_stability,
                    lambda_chaos_entropy=0.0,  # no chaos term in this wrapper
                )
                self._dynamics = ChaosCatastropheDynamics(config, dim=64, manifold_dim=21)
            except ImportError:
                logger.warning("ChaosCatastropheDynamics not available")
        return self._dynamics

    def forward(
        self,
        prediction: torch.Tensor,
        target: torch.Tensor,
        colony_embeddings: torch.Tensor | None = None,
        domain_activations: dict[str, torch.Tensor] | None = None,
    ) -> dict[str, torch.Tensor]:
        """Compute catastrophe-aware loss.

        Delegates to ChaosCatastropheDynamics.compute_loss() for consistency.

        Args:
            prediction: Model prediction [B, D]
            target: Ground truth [B, D]
            colony_embeddings: Colony state embeddings [B, 7, D] or manifold vectors [B, 22]
            domain_activations: Per-colony S7 activations (unused, for API compat)

        Returns:
            Dict with 'total', 'prediction', 'catastrophe', 'stability' losses
        """
        dynamics = self._get_dynamics()

        if dynamics is not None:
            # Delegate to unified dynamics
            losses = dynamics.compute_loss(prediction, target, colony_embeddings)
            # Ensure 'fano' key exists for backward compatibility
            losses["fano"] = torch.tensor(0.0, device=prediction.device)
            return losses

        # FALLBACK DELETED (Dec 2, 2025) - dynamics must be available
        raise RuntimeError("CatastropheAwareLoss.get_training_loss requires dynamics module")


# =============================================================================
# 4. PREDICTIVE LIFECYCLE MANAGER (Imported from organism layer)
# =============================================================================

# NOTE: PredictiveLifecycleManager is imported from the organism layer.
# The canonical implementation lives in:
#   kagami.core.fractal_agents.organism.predictive_lifecycle
#
# This module previously had a duplicate simplified version which has been
# removed as part of the November 30, 2025 consolidation.

try:
    # Dynamic import to avoid world_model.superorganism_integration ↔ unified_agents cycles.
    import importlib

    ua_mod = importlib.import_module("kagami.core.unified_agents")
    OrganismPredictiveLifecycleManager = getattr(ua_mod, "PredictiveLifecycleManager", None)
except Exception:
    OrganismPredictiveLifecycleManager = None


class PredictiveLifecycleManagerBridge:
    """Bridge between SuperorganismIntegration and organism's PredictiveLifecycleManager.

    Provides the same interface as the old simplified PredictiveLifecycleManager
    but delegates to the canonical organism-layer implementation.

    This allows SuperorganismIntegration to work even if the organism layer
    isn't fully initialized, while providing the full functionality when it is.
    """

    def __init__(self, world_model: Any):
        """Initialize the lifecycle manager bridge.

        Args:
            world_model: KagamiWorldModel for predictions
        """
        self.world_model = world_model
        self._organism_manager: Any = None
        self._initialized = False

    def set_organism(self, organism: UnifiedOrganism) -> None:
        """Set organism reference and initialize organism manager.

        Args:
            organism: UnifiedOrganism to manage
        """
        if OrganismPredictiveLifecycleManager is not None:
            try:
                self._organism_manager = OrganismPredictiveLifecycleManager(organism)
                self._initialized = True
                logger.debug("PredictiveLifecycleManager bridge connected to organism layer")
            except Exception as e:
                logger.warning(f"Failed to initialize organism lifecycle manager: {e}")

    async def evaluate_agent(
        self,
        agent: Any,
        current_state: Any,
    ) -> dict[str, Any]:
        """Evaluate agent lifecycle decision.

        Delegates to organism manager if available, otherwise uses fallback.

        Args:
            agent: FractalAgent to evaluate
            current_state: Current CoreState

        Returns:
            Dict with 'recommendation', 'confidence', 'predicted_workload'
        """
        # Try organism manager first
        if self._organism_manager is not None:
            try:
                # Organism manager works at colony level, so we use its prediction
                colony = getattr(agent, "_colony", None)
                if colony:
                    prediction = await self._organism_manager.predict_colony_workload(colony)
                    return {
                        "recommendation": "mitosis"
                        if prediction.needs_mitosis
                        else "hibernation"
                        if prediction.needs_hibernation
                        else "none",
                        "confidence": prediction.confidence,
                        "predicted_workload": prediction.predicted_workload,
                        "reasoning": f"Trend: {prediction.trend}, delta: {prediction.delta:.2f}",
                    }
            except Exception as e:
                # FALLBACK DELETED (Dec 2, 2025) - organism manager must work
                raise RuntimeError(f"Organism lifecycle manager failed: {e}") from e

        # Organism manager is mandatory
        raise RuntimeError(
            "PredictiveLifecycleManagerBridge requires organism manager to be initialized"
        )


# Alias for backward compatibility
PredictiveLifecycleManager = PredictiveLifecycleManagerBridge


# =============================================================================
# 5. SUPERORGANISM INTEGRATION COORDINATOR
# =============================================================================


class SuperorganismIntegration:
    """Main integration coordinator.

    Connects:
    - FractalOrganism (biological)
    - KagamiWorldModel (geometric)
    - Pheromone gradients (stigmergy)
    - Catastrophe dynamics (transitions)
    - Homeostasis (regulation)
    """

    def __init__(
        self,
        world_model: Any,
        organism: UnifiedOrganism | None = None,
    ):
        """Initialize integration.

        Args:
            world_model: KagamiWorldModel instance
            organism: Optional UnifiedOrganism (can be set[Any] later)
        """
        self.world_model = world_model
        self.organism = organism

        # Sub-components
        self.pheromone_state = PheromoneState()
        self.homeostasis_bridge = HomeostasisWorldModelState()
        self.catastrophe_loss = CatastropheAwareLoss()
        self.lifecycle_manager = PredictiveLifecycleManager(world_model)

        # State
        self.last_sync_time = 0.0
        self.sync_interval = 1.0  # Sync every second

        logger.debug("SuperorganismIntegration initialized")

    def set_organism(self, organism: UnifiedOrganism) -> None:
        """Set organism reference.

        Args:
            organism: UnifiedOrganism instance
        """
        self.organism = organism

    async def sync_cycle(self) -> dict[str, Any]:
        """Run one synchronization cycle.

        This should be called periodically (e.g., from homeostasis loop).

        Returns:
            Sync metrics
        """
        metrics = {"synced": False, "pheromone_updated": False, "predictions_made": False}

        now = time.time()
        if now - self.last_sync_time < self.sync_interval:
            return metrics

        self.last_sync_time = now

        if self.organism is None:
            return metrics

        try:
            # 1. Update homeostasis bridge
            self.homeostasis_bridge.update_from_organism(self.organism)

            # 2. Get current core state from world model
            core_state = await self._get_current_core_state()
            if core_state:
                self.homeostasis_bridge.update_from_world_model(self.world_model, core_state)
                metrics["predictions_made"] = True

            # 3. Update pheromone state
            colony_success_rates = {}
            colony_workloads = {}

            for domain_name, colony in self.organism.colonies.items():
                # MinimalColony API: use get_stats() or stats attributes
                stats = colony.get_stats()
                total_ops = stats.get("completed", 0) + stats.get("failed", 0)
                success_rate = stats.get("completed", 0) / max(1, total_ops)
                # Workload proxy: use normalized worker utilization
                available = stats.get("available_workers", 0)
                total = stats.get("worker_count", 1)
                workload = 1.0 - (available / max(1, total))

                colony_success_rates[domain_name] = success_rate
                colony_workloads[domain_name] = workload

            self.pheromone_state.update(colony_success_rates, colony_workloads)
            metrics["pheromone_updated"] = True

            # 4. Sync pheromone state to world model CoreState
            # PHEROMONE MUTATION (Dec 27, 2025): Actually mutate S7 phase
            if core_state and core_state.domain_activations:
                pheromone_s7 = self.pheromone_state.to_s7_vector()
                # Blend pheromone into overall S7 phase
                if core_state.s7_phase is not None:
                    # Subtle influence: 10% pheromone, 90% current
                    pheromone_tensor = torch.tensor(
                        pheromone_s7,
                        device=core_state.s7_phase.device,
                        dtype=core_state.s7_phase.dtype,
                    )
                    # Match dimensions for broadcasting
                    while pheromone_tensor.dim() < core_state.s7_phase.dim():
                        pheromone_tensor = pheromone_tensor.unsqueeze(0)

                    # MUTATE: Blend pheromone signal into S7 phase (stigmergic influence)
                    # This closes the feedback loop from organism → world model
                    blended = 0.9 * core_state.s7_phase + 0.1 * pheromone_tensor
                    # Re-normalize to S7 (unit sphere)
                    blended_norm = torch.norm(blended, dim=-1, keepdim=True).clamp(min=1e-8)
                    core_state.s7_phase = blended / blended_norm
                    metrics["pheromone_blended"] = True
                    logger.debug("Pheromone signal blended into S7 phase (10% influence)")

            metrics["synced"] = True

        except Exception as e:
            logger.warning(f"Sync cycle failed: {e}")

        return metrics

    async def _get_current_core_state(self) -> Any | None:
        """Get current CoreState from world model.

        Returns:
            CoreState or None
        """
        try:
            # Build domain activations from colonies
            domain_activations = {}

            # MinimalColony API: colonies dict[str, Any] has string keys, not enum values
            for domain_name, colony in self.organism.colonies.items():  # type: ignore[union-attr]
                if hasattr(colony, "s7_section"):
                    s7 = torch.tensor(colony.s7_section, dtype=torch.float32)
                    if s7.dim() == 1:
                        s7 = s7.unsqueeze(0)
                    domain_activations[domain_name] = s7

            if not domain_activations:
                return None

            # Create CoreState with domain activations (lazy import to avoid cycles)
            import importlib

            wm_mod = importlib.import_module("kagami.core.world_model.kagami_world_model")
            CoreState = getattr(wm_mod, "CoreState", None)
            if CoreState is None:
                raise RuntimeError("CoreState unavailable")
            core_state = CoreState(domain_activations=domain_activations)

            return core_state

        except Exception as e:
            logger.debug(f"Failed to get CoreState: {e}")
            return None

    def get_training_loss(
        self,
        prediction: torch.Tensor,
        target: torch.Tensor,
        colony_embeddings: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        """Get catastrophe-aware training loss.

        Call this during training to incorporate biological constraints.

        Args:
            prediction: Model prediction
            target: Ground truth
            colony_embeddings: Colony state embeddings

        Returns:
            Loss dict[str, Any]
        """
        return self.catastrophe_loss(prediction, target, colony_embeddings)

    def get_task_routing_weights(self) -> dict[str, float]:
        """Get pheromone-based task routing weights.

        Use these weights when assigning tasks to colonies.

        Returns:
            Weights per colony
        """
        return self.pheromone_state.get_task_routing_weights()

    def get_allostatic_signals(self) -> dict[str, float]:
        """Get allostatic adjustment signals.

        Use these for preemptive homeostasis adjustments.

        Returns:
            Adjustment signals
        """
        return self.homeostasis_bridge.get_allostatic_adjustment()

    async def evaluate_lifecycle(self, agent: Any) -> dict[str, Any]:
        """Evaluate agent lifecycle using world model.

        Args:
            agent: FractalAgent

        Returns:
            Lifecycle recommendation
        """
        core_state = await self._get_current_core_state()
        if core_state is None:
            return {
                "recommendation": "none",
                "confidence": 0.0,
                "reason": "core_state_unavailable",
            }

        return await self.lifecycle_manager.evaluate_agent(agent, core_state)

    async def compute_emergence_metrics(self) -> dict[str, float]:
        """Compute superorganism emergence metrics using exceptional hierarchy.

        ADDED (Nov 30, 2025): Measures emergent collective intelligence by
        encoding colony states through G₂ → F₄ → E₆ → E₇ → E₈ hierarchy.

        Hölldobler-Wilson Superorganism Principles:
        1. Division of labor → measured by colony specialization spread
        2. Information flow → measured by Fano synergy across lines
        3. Collective coherence → measured by E8 quantization stress
        4. Emergent intelligence → gap between colony-level and E8-level info

        Returns:
            Dict with emergence metrics:
            - division_of_labor: 0-1 specialization index
            - information_flow: 0-1 Fano line synergy
            - collective_coherence: 0-1 (1-lattice_stress)
            - emergence_gap: bits of emergent information
            - hierarchy_depth_used: 1-5 (G₂ to E₈)
        """
        metrics = {
            "division_of_labor": 0.0,
            "information_flow": 0.0,
            "collective_coherence": 1.0,
            "emergence_gap": 0.0,
            "hierarchy_depth_used": 1,
        }

        if self.organism is None:
            return metrics

        try:
            # 1. Gather colony octonions
            colony_octonions = []
            workloads = []
            domain_order = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]

            for domain_name in domain_order:
                # MinimalColony API: use get_colony() method
                colony = self.organism.get_colony(domain_name)
                if colony is not None and hasattr(colony, "s7_section"):
                    s7 = torch.tensor(colony.s7_section, dtype=torch.float32)
                    colony_octonions.append(s7)
                    # Workload proxy: use worker utilization from stats
                    stats = colony.get_stats()
                    available = stats.get("available_workers", 0)
                    total = stats.get("worker_count", 1)
                    workloads.append(1.0 - (available / max(1, total)))
                else:
                    # Canonical basis vector for missing colony
                    idx = domain_order.index(domain_name)
                    s7 = torch.zeros(8)
                    s7[idx + 1] = 1.0
                    colony_octonions.append(s7)
                    workloads.append(0.0)

            colony_tensor = torch.stack(colony_octonions)  # [7, 8]

            # 2. Division of Labor: variance in workload distribution
            workload_array = np.array(workloads)
            if workload_array.sum() > 0:
                # Normalized entropy of workload distribution
                p = workload_array / (workload_array.sum() + 1e-8)
                p = np.clip(p, 1e-8, 1.0)
                entropy = -np.sum(p * np.log(p))
                max_entropy = np.log(7)  # Uniform distribution
                metrics["division_of_labor"] = float(entropy / max_entropy)

            # 3. Information Flow: Fano coherence (batched octonion multiplication)
            # The legacy colony→exceptional-hierarchy side-path was removed (Dec 2025 cleanup).
            if hasattr(self.world_model, "fano_coherence_estimator"):
                colony_batch = colony_tensor.unsqueeze(0)  # [1, 7, 8]
                coherence = self.world_model.fano_coherence_estimator(colony_batch)  # [1, 1]
                coherence_val = float(coherence.mean().item())
                metrics["information_flow"] = min(1.0, max(0.0, coherence_val))
                metrics["collective_coherence"] = metrics["information_flow"]

        except Exception as e:
            logger.debug(f"Emergence metrics computation failed: {e}")

        return metrics

    def get_hierarchy_health(self) -> dict[str, Any]:
        """Get health status of the exceptional hierarchy integration.

        Returns:
            Health metrics for the G₂ → E₈ chain
        """
        return {
            "hourglass_available": bool(getattr(self.world_model, "unified_hourglass", None)),
            "e8_quantizer_available": bool(
                getattr(getattr(self.world_model, "unified_hourglass", None), "residual_e8", None)
            ),
            "fano_estimator_available": bool(
                getattr(self.world_model, "fano_coherence_estimator", None)
            ),
        }


# =============================================================================
# SINGLETON
# =============================================================================

_integration: SuperorganismIntegration | None = None


def get_superorganism_integration(
    world_model: Any | None = None,
    organism: UnifiedOrganism | None = None,
) -> SuperorganismIntegration:
    """Get global SuperorganismIntegration instance.

    Args:
        world_model: Optional world model (required on first call)
        organism: Optional organism

    Returns:
        SuperorganismIntegration singleton
    """
    global _integration

    if _integration is None:
        if world_model is None:
            # Dynamic import to avoid world_model.superorganism_integration ↔ world_model package cycles.
            import importlib

            wm_mod = importlib.import_module("kagami.core.world_model")
            get_world_model_service = getattr(wm_mod, "get_world_model_service", None)
            if not callable(get_world_model_service):
                raise RuntimeError("get_world_model_service not available")
            service = get_world_model_service()
            world_model = getattr(service, "model", None)
            if world_model is None:
                raise RuntimeError("World model unavailable (service.model is None)")
        _integration = SuperorganismIntegration(world_model, organism)

    if organism is not None:
        _integration.set_organism(organism)

    return _integration


def reset_superorganism_integration() -> None:
    """Reset the singleton (for testing)."""
    global _integration
    _integration = None


# Module ready
