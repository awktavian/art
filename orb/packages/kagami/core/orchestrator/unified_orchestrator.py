"""Unified Orchestrator - Central Control Loop Integrating LeCun Architecture.

This is the CANONICAL entry point for K OS cognitive operations. It integrates:

FROM LECUN ARCHITECTURE:
- ConfiguratorModule: Executive control, task-based configuration
- SkillCompiler: Mode-2 → Mode-1 distillation
- HierarchicalJEPA: Multi-level prediction
- EgoModel: Self-prediction
- EntityMemory: Entity tracking

WITH EXISTING K OS SYSTEMS:
- KagamiWorldModel: World dynamics (OrganismRSSM, TIC, E8)
- UnifiedOrganism: 7 colonies with Fano routing
- ActiveInferenceEngine: EFE planning
- UnifiedLearningCoordinator: Online/batch learning

EXECUTION MODES:
================
MODE-1 (Reactive): Fast, compiled skills, no planning
MODE-2 (Planning): Full world model + EFE optimization
HIERARCHICAL: Multi-level planning with skill composition

LeCun: "Mode-1 runs in a tight loop... Mode-2 performs iterative optimization
to find action sequences that will minimize the estimated cost."

Created: December 6, 2025
Reference: docs/LECUN_INTEGRATION_COMPLETE.md
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, cast

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami.core.world_model.ego_model import (
    EgoModel,
    EgoModelConfig,
)
from kagami.core.world_model.entity_memory import (
    EntityMemory,
    EntityMemoryConfig,
)

# LeCun modules - from canonical locations (no redundancy)
from kagami.core.world_model.hierarchical_jepa import (
    E8JEPAConfig,
    HierarchicalJEPA,
)

if TYPE_CHECKING:
    from kagami.core.executive import IntegratedExecutiveControl, TaskConfiguration
    from kagami.core.learning.skill_compiler import SkillCompiler
    from kagami.core.unified_agents import UnifiedOrganism
    from kagami.core.world_model.kagami_world_model import KagamiWorldModel

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution mode selection."""

    MODE_1 = "reactive"  # Fast reactive execution (compiled skills)
    MODE_2 = "planning"  # Full world model planning
    HIERARCHICAL = "hierarchical"  # Multi-level planning


@dataclass
class OrchestratorConfig:
    """Configuration for Unified Orchestrator."""

    # Default execution mode
    default_mode: ExecutionMode = ExecutionMode.MODE_2

    # Mode selection thresholds
    urgency_threshold: float = 0.7  # Above this → Mode-1
    complexity_threshold: float = 0.5  # Above this → Hierarchical

    # Planning parameters
    planning_horizon: int = 20
    n_planning_iterations: int = 10

    # Skill compilation
    skill_compilation_threshold: int = 5  # After N Mode-2 runs, compile skill

    # Safety
    safety_margin: float = 0.1  # CBF margin

    # Device
    device: str = "cpu"


@dataclass
class ExecutionResult:
    """Result from orchestrated execution."""

    # Action output
    action: torch.Tensor  # [8] E8 action

    # Execution metadata
    mode: ExecutionMode
    latency: float
    success: bool

    # Planning info (if Mode-2/Hierarchical)
    efe_value: float | None = None
    planning_horizon: int | None = None
    h_jepa_level: int | None = None

    # Skill info (if Mode-1)
    skill_id: str | None = None

    # Safety info
    safety_margin: float = 1.0

    # Raw outputs
    colony_outputs: torch.Tensor | None = None
    world_model_prediction: torch.Tensor | None = None

    # Error info
    error: str | None = None


class UnifiedOrchestrator(nn.Module):
    """Central control loop integrating LeCun architecture with K OS.

    This orchestrator implements the full cognitive architecture:

    1. CONFIGURATOR (Executive Control)
       - Takes task description
       - Configures all modules (perception, world model, cost, actor)
       - Selects execution mode

    2. WORLD MODEL (Prediction)
       - KagamiWorldModel (OrganismRSSM + TIC)
       - HierarchicalJEPA for multi-level prediction
       - EgoModel for self-prediction

    3. COST (Evaluation)
       - ActiveInferenceEngine (EFE)
       - Intrinsic costs (curiosity, empowerment)
       - Trainable critic

    4. ACTOR (Execution)
       - UnifiedOrganism (7 colonies)
       - Mode-1: Compiled skills (fast)
       - Mode-2: EFE-optimized planning

    5. MEMORY (Entity Tracking)
       - EntityMemory for sparse entity updates
       - Hopfield-E8 for associative memory
       - Episodic memory for experience

    Usage:
        orchestrator = get_orchestrator()

        result = await orchestrator.execute(
            task_embedding=task_emb,
            task_type="planning",
            observation=current_obs,
        )

        # Result contains action, mode used, and diagnostics
    """

    def __init__(self, config: OrchestratorConfig | None = None):
        super().__init__()
        self.config = config or OrchestratorConfig()

        # === LECUN COMPONENTS ===
        # H-JEPA for hierarchical prediction
        self.h_jepa = HierarchicalJEPA(E8JEPAConfig())

        # Ego model for self-prediction
        self.ego_model = EgoModel(EgoModelConfig())

        # Entity memory for world state
        self.entity_memory = EntityMemory(EntityMemoryConfig())

        # === LAZY-LOADED K OS COMPONENTS ===
        self._executive: IntegratedExecutiveControl | None = None
        self._skill_compiler: SkillCompiler | None = None
        self._world_model: KagamiWorldModel | None = None
        self._organism: UnifiedOrganism | None = None
        self._active_inference: Any = None
        self._learning_coordinator: Any = None

        # === SKILL TRACKING ===
        self._task_execution_counts: dict[str, int] = {}

        # === METRICS ===
        self._total_executions = 0
        self._mode_1_count = 0
        self._mode_2_count = 0
        self._hierarchical_count = 0

        logger.info(
            f"UnifiedOrchestrator initialized: default_mode={self.config.default_mode.value}"
        )

    # =========================================================================
    # LAZY LOADING
    # =========================================================================

    def _get_executive(self) -> IntegratedExecutiveControl:
        """Lazy load executive control."""
        if self._executive is None:
            from kagami.core.executive import get_executive_control

            self._executive = get_executive_control()
        return self._executive

    def _get_skill_compiler(self) -> SkillCompiler:
        """Lazy load skill compiler."""
        if self._skill_compiler is None:
            from kagami.core.learning.skill_compiler import get_skill_compiler

            self._skill_compiler = get_skill_compiler()

            # Wire to world model and planner
            if self._world_model is not None:
                self._skill_compiler.set_world_model(self._world_model)
        return self._skill_compiler

    def _get_world_model(self) -> KagamiWorldModel | None:
        """Lazy load world model via canonical service.

        NOTE (Dec 6, 2025): Strange Loop wiring is now handled by WorldModelService.
        """
        if self._world_model is None:
            # Use canonical service (handles Strange Loop wiring internally)
            from kagami.core.world_model.service import get_world_model_service

            service = get_world_model_service()
            self._world_model = service.model

            # Wire local EgoModel to Strange Loop if service has it
            strange_loop = service.strange_loop
            if strange_loop and hasattr(self.ego_model, "connect_strange_loop"):
                self.ego_model.connect_strange_loop(strange_loop)
                logger.debug("Wired orchestrator EgoModel to Strange Loop")
        return self._world_model

    def _get_organism(self) -> UnifiedOrganism:
        """Lazy load unified organism."""
        if self._organism is None:
            from kagami.core.unified_agents import get_unified_organism

            self._organism = get_unified_organism()
        return self._organism

    def _get_active_inference(self) -> Any:
        """Lazy load active inference engine.

        NOTE (Dec 6, 2025): Strange Loop wiring is handled by WorldModelService.
        """
        if self._active_inference is None:
            from kagami.core.active_inference.engine import get_active_inference_engine

            self._active_inference = get_active_inference_engine()

            # Wire to world model's RSSM
            wm = self._get_world_model()
            if wm and hasattr(wm, "rssm"):
                self._active_inference.set_world_model(wm.rssm)
        return self._active_inference

    def _get_learning_coordinator(self) -> Any:
        """Lazy load learning coordinator."""
        if self._learning_coordinator is None:
            from kagami.core.learning.coordinator import get_learning_coordinator

            self._learning_coordinator = get_learning_coordinator()
        return self._learning_coordinator

    # =========================================================================
    # MAIN EXECUTION
    # =========================================================================

    async def execute(
        self,
        task_embedding: torch.Tensor,
        task_type: str = "general",
        task_description: str = "",
        observation: torch.Tensor | None = None,
        goal: torch.Tensor | None = None,
        mode_override: ExecutionMode | None = None,
        context: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        """Execute a task using the full cognitive architecture.

        This is the main entry point for all K OS operations.

        Args:
            task_embedding: [task_dim] semantic task embedding
            task_type: Type of task (planning, reactive, creative, etc.)
            task_description: Text description for routing
            observation: [obs_dim] current observation (optional)
            goal: [goal_dim] goal specification (optional)
            mode_override: Force specific execution mode
            context: Additional context

        Returns:
            ExecutionResult with action and diagnostics
        """
        start_time = time.time()
        context = context or {}
        self._total_executions += 1

        try:
            # Ensure batch dimension
            if task_embedding.dim() == 1:
                task_embedding = task_embedding.unsqueeze(0)

            # 1. CONFIGURATOR: Get task configuration
            executive = self._get_executive()
            config = await executive.configure_for_task(
                task_embedding=task_embedding,
                task_type=task_type,
                task_description=task_description,
                context=context,
            )

            # 2. SELECT EXECUTION MODE
            mode = self._select_mode(config, mode_override)

            # 3. EXECUTE BASED ON MODE
            if mode == ExecutionMode.MODE_1:
                result = await self._execute_mode_1(task_type, task_embedding, observation, config)
            elif mode == ExecutionMode.MODE_2:
                result = await self._execute_mode_2(task_embedding, observation, goal, config)
            else:  # HIERARCHICAL
                result = await self._execute_hierarchical(task_embedding, observation, goal, config)

            # 4. UPDATE ENTITY MEMORY
            if observation is not None:
                self.entity_memory.step()

            # 5. SKILL COMPILATION CHECK
            await self._check_skill_compilation(task_type, mode)

            # 6. RECORD RESULT
            latency = time.time() - start_time
            result.latency = latency

            return result

        except Exception as e:
            logger.error(f"Orchestrator execution failed: {e}")
            return ExecutionResult(
                action=torch.zeros(8),
                mode=mode_override or self.config.default_mode,
                latency=time.time() - start_time,
                success=False,
                error=str(e),
            )

    def _select_mode(
        self,
        config: TaskConfiguration,
        override: ExecutionMode | None = None,
    ) -> ExecutionMode:
        """Select execution mode based on configuration.

        LeCun: "Mode-1 is reactive and fast, while Mode-2 plans ahead."

        Selection criteria:
        - High urgency → Mode-1 (fast reaction)
        - High complexity → Hierarchical (multi-level)
        - Compiled skill available → Mode-1
        - Otherwise → Mode-2 (planning)
        """
        if override is not None:
            return override

        # Check urgency
        if config.urgency > self.config.urgency_threshold:
            self._mode_1_count += 1
            return ExecutionMode.MODE_1

        # Check for compiled skill
        task_type = config.task_type
        skill_compiler = self._get_skill_compiler()
        if skill_compiler.get_skill_for_task(task_type) is not None:
            self._mode_1_count += 1
            return ExecutionMode.MODE_1

        # Check complexity for hierarchical
        # (Infer from world model config horizon)
        if config.world_model.horizon > 30:
            self._hierarchical_count += 1
            return ExecutionMode.HIERARCHICAL

        self._mode_2_count += 1
        return ExecutionMode.MODE_2

    async def _execute_mode_1(
        self,
        task_type: str,
        task_embedding: torch.Tensor,
        observation: torch.Tensor | None,
        config: TaskConfiguration,
    ) -> ExecutionResult:
        """Mode-1: Reactive execution using compiled skills.

        LeCun: "The policy module produces a single action proposal...
        without planning."
        """
        skill_compiler = self._get_skill_compiler()
        skill = skill_compiler.get_skill_for_task(task_type)

        if skill is not None:
            # Use compiled skill
            state = observation if observation is not None else torch.zeros(256)
            if state.dim() == 1:
                state = state.unsqueeze(0)

            # Pad/truncate to skill input dim
            if state.shape[-1] != skill.policy.config.state_dim:
                state = F.pad(state, (0, max(0, 256 - state.shape[-1])))
                state = state[..., :256]

            action = skill.execute(state)

            return ExecutionResult(
                action=action.squeeze(0),
                mode=ExecutionMode.MODE_1,
                latency=0.0,
                success=True,
                skill_id=skill.skill_id,
            )

        # Fallback: Direct policy from active inference
        ai_engine = self._get_active_inference()

        # Initialize state if needed
        if observation is not None:
            await ai_engine.perceive({"state_embedding": observation})

        # Get direct action (no planning)
        if ai_engine._h is not None and ai_engine._z is not None:
            action = ai_engine.policy_generator.get_action(ai_engine._h, ai_engine._z)
        else:
            action = torch.zeros(8)

        return ExecutionResult(
            action=action.squeeze(0) if action.dim() > 1 else action,
            mode=ExecutionMode.MODE_1,
            latency=0.0,
            success=True,
        )

    async def _execute_mode_2(
        self,
        task_embedding: torch.Tensor,
        observation: torch.Tensor | None,
        goal: torch.Tensor | None,
        config: TaskConfiguration,
    ) -> ExecutionResult:
        """Mode-2: Planning with world model and EFE optimization.

        LeCun: "Mode-2 involves iterative optimization of action sequences
        to minimize expected cost."
        """
        ai_engine = self._get_active_inference()
        self._get_world_model()
        organism = self._get_organism()

        # Update state from observation
        if observation is not None:
            await ai_engine.perceive({"state_embedding": observation})

        # Set planning horizon from config
        horizon = config.world_model.horizon
        k_value = min(11, horizon // 5 + 1)  # Map horizon to k-value

        # Run EFE planning
        plan_result = await ai_engine.select_action(
            goals=goal,
            k_value=k_value,
        )

        action = plan_result["action"]

        # Execute via organism
        result = await organism.execute_intent(
            intent="planned.action",
            params={"action_tensor": action.tolist()},
            context={"config": config.__dict__ if hasattr(config, "__dict__") else {}},
        )

        # Self-prediction for safety check
        if observation is not None:
            proprio_state = (
                observation[:32]
                if observation.shape[-1] >= 32
                else F.pad(observation, (0, 32 - observation.shape[-1]))
            )
            if proprio_state.dim() == 1:
                proprio_state = proprio_state.unsqueeze(0)

            # Pad proprio_state to ego model input dim
            total_dim = 32 + 16 + 4  # proprio + internal + energy
            if proprio_state.shape[-1] < total_dim:
                proprio_state = F.pad(proprio_state, (0, total_dim - proprio_state.shape[-1]))

            ego_pred = self.ego_model(
                proprio_state, action.unsqueeze(0) if action.dim() == 1 else action
            )
            safety_margin = 1.0 - ego_pred["constraints"]["max_violation"].max().item()
        else:
            safety_margin = 1.0

        return ExecutionResult(
            action=action,
            mode=ExecutionMode.MODE_2,
            latency=0.0,
            success=result.get("success", True),
            efe_value=plan_result.get("G", None),
            planning_horizon=horizon,
            safety_margin=safety_margin,
            colony_outputs=result.get("e8_action", {}).get("code"),
        )

    async def _execute_hierarchical(
        self,
        task_embedding: torch.Tensor,
        observation: torch.Tensor | None,
        goal: torch.Tensor | None,
        config: TaskConfiguration,
    ) -> ExecutionResult:
        """Hierarchical: Multi-level planning with H-JEPA.

        Uses hierarchical prediction for long-horizon planning.
        """
        # Encode observation sequence for H-JEPA
        if observation is not None:
            obs_seq = observation.unsqueeze(0).unsqueeze(0)  # [1, 1, D]

            # Pad to H-JEPA input dim
            if obs_seq.shape[-1] < 21:
                obs_seq = F.pad(obs_seq, (0, 21 - obs_seq.shape[-1]))

            # Get hierarchical prediction
            h_jepa_result = self.h_jepa(obs_seq)

            # Select appropriate level based on horizon
            horizon = config.world_model.horizon
            level = 0
            level_horizons = [lv.prediction_horizon for lv in self.h_jepa.config.levels]
            for i, h in enumerate(level_horizons):
                if horizon <= h:
                    level = i
                    break
            else:
                level = len(level_horizons) - 1

            # Get prediction at selected level
            pred = h_jepa_result.predictions[level][:, 0]  # First step prediction
        else:
            pred = None
            level = 0

        # Run Mode-2 planning with H-JEPA prior
        result = await self._execute_mode_2(task_embedding, observation, goal, config)

        # Update result with H-JEPA info
        result.mode = ExecutionMode.HIERARCHICAL
        result.h_jepa_level = level
        if pred is not None:
            result.world_model_prediction = pred

        return result

    async def _check_skill_compilation(
        self,
        task_type: str,
        mode: ExecutionMode,
    ) -> None:
        """Check if task should be compiled to skill.

        LeCun: "Once an optimal action sequence is obtained through
        planning... one can use the actions as targets to train a
        policy network."
        """
        if mode == ExecutionMode.MODE_1:
            return  # Already using skill

        # Increment execution count
        self._task_execution_counts[task_type] = self._task_execution_counts.get(task_type, 0) + 1

        # Check if should compile
        count = self._task_execution_counts[task_type]
        if count >= self.config.skill_compilation_threshold:
            skill_compiler = self._get_skill_compiler()

            # Check if skill already exists
            if skill_compiler.get_skill_for_task(task_type) is None:
                logger.info(f"Triggering skill compilation for '{task_type}'")

                # Schedule compilation (don't block)
                asyncio.create_task(
                    skill_compiler.compile_skill(
                        task_type=task_type,
                        n_episodes=50,  # Reduced for faster compilation
                    )
                )

    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================

    def update_entity(
        self,
        key: str,
        embedding: torch.Tensor,
        key_embedding: torch.Tensor | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Upsert an entity into `EntityMemory`.

        Note: `EntityMemory` is key-value (string key) + optional learned key embedding.
        """
        self.entity_memory.add_entity(
            key=key,
            embedding=embedding,
            key_embedding=key_embedding,
            attributes=attributes,
        )
        return {"key": key, "n_entities": int(self.entity_memory.n_entities)}

    def query_entities(
        self,
        query: torch.Tensor,
    ) -> torch.Tensor:
        """Query entity states from memory.

        Args:
            query: Query vector

        Returns:
            Entity state
        """
        result, _weights = self.entity_memory.query(query)
        return result

    def predict_self(
        self,
        action: torch.Tensor,
        current_state: torch.Tensor,
    ) -> dict[str, Any]:
        """Predict own next state (ego model).

        Args:
            action: Proposed action
            current_state: Current proprioceptive state

        Returns:
            Prediction with next_state, energy_cost, constraints
        """
        return cast(dict[str, Any], self.ego_model(current_state, action))

    def predict_hierarchical(
        self,
        observation: torch.Tensor,
        horizon: int,
    ) -> torch.Tensor:
        """Predict at specific horizon using H-JEPA.

        Args:
            observation: Current observation
            horizon: Prediction horizon

        Returns:
            Predicted state at horizon
        """
        # H-JEPA operates over an E8 nucleus sequence [B, L, 8]. For single observations,
        # we treat the observation as a length-1 sequence.
        if observation.dim() == 1:
            e8_seq = observation.unsqueeze(0).unsqueeze(0)
        elif observation.dim() == 2:
            e8_seq = observation.unsqueeze(1)
        else:
            e8_seq = observation

        preds = self.h_jepa.predict_hierarchy(e8_seq)

        # Map horizon → closest configured level horizon.
        level_horizons = [
            int(getattr(lvl, "prediction_horizon", 1)) for lvl in self.h_jepa.config.levels
        ]
        best = min(range(len(level_horizons)), key=lambda i: abs(level_horizons[i] - int(horizon)))
        return preds[f"level_{best}_pred"]

    # =========================================================================
    # DIAGNOSTICS
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "total_executions": self._total_executions,
            "mode_1_count": self._mode_1_count,
            "mode_2_count": self._mode_2_count,
            "hierarchical_count": self._hierarchical_count,
            "mode_1_ratio": self._mode_1_count / max(1, self._total_executions),
            "task_execution_counts": self._task_execution_counts.copy(),
            "active_entities": int(self.entity_memory.n_entities),
            "h_jepa_levels": len(self.h_jepa.config.levels),
        }

    def get_components(self) -> dict[str, Any]:
        """Get references to all integrated components."""
        return {
            "h_jepa": self.h_jepa,
            "ego_model": self.ego_model,
            "entity_memory": self.entity_memory,
            "executive": self._executive,
            "skill_compiler": self._skill_compiler,
            "world_model": self._world_model,
            "organism": self._organism,
            "active_inference": self._active_inference,
        }


# =============================================================================
# SINGLETON
# =============================================================================

_orchestrator: UnifiedOrchestrator | None = None


def get_orchestrator(config: OrchestratorConfig | None = None) -> UnifiedOrchestrator:
    """Get or create global UnifiedOrchestrator instance.

    This is the CANONICAL entry point for K OS operations.
    """
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = UnifiedOrchestrator(config)
        logger.info("Created global UnifiedOrchestrator")
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset global orchestrator (for testing)."""
    global _orchestrator
    _orchestrator = None


__all__ = [
    "ExecutionMode",
    "ExecutionResult",
    "OrchestratorConfig",
    "UnifiedOrchestrator",
    "get_orchestrator",
    "reset_orchestrator",
]
