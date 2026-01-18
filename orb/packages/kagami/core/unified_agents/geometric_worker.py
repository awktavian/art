"""Geometric Worker - Catastrophe-Driven Agent with Markov Blanket.

This module provides a unified agent that operates via catastrophe dynamics.
(Previously split into FractalAgent + separate program selection.)

CATASTROPHE DYNAMICS:
=====================
Each worker inherits the catastrophe type of its colony:
    Fold (A₂)        - Ignition threshold, sudden burst
    Cusp (A₃)        - Decision bistability, hysteresis
    Swallowtail (A₄) - Recovery multi-stability
    Butterfly (A₅)   - Integration complexity
    Hyperbolic (D₄⁺) - Focus splitting
    Elliptic (D₄⁻)   - Search convergence
    Parabolic (D₅)   - Safety edge detection

MARKOV BLANKET (Dec 2, 2025):
=============================
Each agent has its own Markov blanket nested within the colony blanket:

    η (colony internal) → s (agent sensory) → μ (agent internal) → a (agent action)

Where:
- s = perceive(z_colony, task) → agent sensory state
- μ = (h14_position, fitness, internal_state)
- a = act(μ) → agent action (program execution)

The agent's "external" is the colony's "internal" - nested blankets!

References:
- Thom (1972): Structural Stability and Morphogenesis
- Rissanen (1978): Minimum Description Length
- Friston (2013): Markov Blankets

Created: December 2, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

import torch
import torch.nn.functional as F

# HARDENED: Direct receipt imports - no facade abstraction
from kagami.core.receipts.facade import emit_receipt
from kagami.core.utils.ids import generate_correlation_id

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS (imported from canonical source)
# =============================================================================

from kagami_math.catastrophe_constants import (
    CATASTROPHE_NAMES as CATASTROPHE_TYPES,
)
from kagami_math.catastrophe_constants import (
    COLONY_NAMES,
)

# =============================================================================
# DATA STRUCTURES
# =============================================================================


class WorkerStatus(Enum):
    """Worker lifecycle status."""

    INITIALIZING = "initializing"
    ACTIVE = "active"
    BUSY = "busy"
    IDLE = "idle"
    HIBERNATING = "hibernating"
    DEAD = "dead"


@dataclass
class WorkerConfig:
    """Configuration for geometric worker."""

    # Colony assignment
    colony_idx: int = 0  # Which colony (0-6)

    # Capacity
    max_concurrent: int = 5  # Max concurrent tasks

    # Lifecycle
    idle_timeout: float = 300.0  # Seconds before hibernation
    max_operations: int = 1000  # Max ops before retirement

    # Program Selection (MDL-based)
    use_program_library: bool = True  # Use program selection
    max_programs: int = 10  # Max programs to consider

    # Catastrophe
    catastrophe_threshold: float = 0.7  # Risk threshold

    # Learning
    learning_rate: float = 0.01
    fitness_ema_alpha: float = 0.1


@dataclass
class WorkerState:
    """Current state of a geometric worker."""

    # Identity
    worker_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    colony_idx: int = 0

    # Geometric state
    s7_section: torch.Tensor = field(default_factory=lambda: torch.zeros(8))
    h14_position: torch.Tensor = field(default_factory=lambda: torch.zeros(14))

    # Status
    status: WorkerStatus = WorkerStatus.INITIALIZING

    # Workload
    current_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0

    # Performance - Start at 0.5 (neutral) to avoid premature retirement
    # OPTIMIZED (Dec 27, 2025): Cold start fix - new workers get warm-up period
    fitness: float = 0.5
    avg_latency: float = 0.0

    # Timing
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    @property
    def success_rate(self) -> float | None:
        """Return actual success rate, or None if no tasks executed yet."""
        total = self.completed_tasks + self.failed_tasks
        return self.completed_tasks / total if total > 0 else None

    @property
    def success_rate_display(self) -> float:
        """Return success rate for display (0.0 if no data, never fake 0.5)."""
        total = self.completed_tasks + self.failed_tasks
        return self.completed_tasks / total if total > 0 else 0.0

    @property
    def colony_name(self) -> str:
        return COLONY_NAMES[self.colony_idx]

    @property
    def catastrophe_type(self) -> str:
        return CATASTROPHE_TYPES[self.colony_idx]


@dataclass
class TaskResult:
    """Result from task execution."""

    task_id: str
    success: bool
    result: Any = None
    error: str | None = None
    latency: float = 0.0
    program_used: int | None = None  # E₈ program index
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    # Receipt chain tracking (PLAN → EXECUTE → VERIFY)
    correlation_id: str | None = None  # Links related operations
    phase: str | None = None  # "PLAN", "EXECUTE", or "VERIFY"
    parent_receipt_id: str | None = None  # Previous phase's task_id


# =============================================================================
# GEOMETRIC WORKER
# =============================================================================


class GeometricWorker:
    """Unified agent operating on H¹⁴ × S⁷ manifold.

    Combines:
    - FractalAgent: DNA-based execution
    - MDL-based program selection (replaces "Solomonoff" which is incomputable)

    Key features:
    - S⁷ section defines colony identity
    - Programs selected from E₈ library (240 slots)
    - Catastrophe dynamics drive behavior
    - Simplified lifecycle (no redundant managers)
    """

    def __init__(
        self,
        config: WorkerConfig | None = None,
        colony_idx: int | None = None,
    ):
        """Initialize geometric worker.

        Args:
            config: Worker configuration
            colony_idx: Colony assignment (overrides config)
        """
        self.config = config or WorkerConfig()

        if colony_idx is not None:
            self.config.colony_idx = colony_idx

        # Initialize state
        self.state = WorkerState(
            colony_idx=self.config.colony_idx,
            s7_section=self._init_s7_section(),
            h14_position=self._init_h14_position(),
        )

        # Concurrency control
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self._task_queue: asyncio.Queue = asyncio.Queue()

        # Program library (lazy loaded)
        self._program_library = None
        self._catastrophe_dynamics = None

        # Mark as active
        self.state.status = WorkerStatus.ACTIVE

        logger.info(
            f"✅ GeometricWorker {self.state.worker_id}: "
            f"colony={self.state.colony_name}, "
            f"catastrophe={self.state.catastrophe_type}"
        )

    def _init_s7_section(self) -> torch.Tensor:
        """Initialize S⁷ section for this colony."""
        section = torch.zeros(8)
        section[self.config.colony_idx + 1] = 1.0  # e₁ at index 1
        return section

    def _init_h14_position(self) -> torch.Tensor:
        """Initialize H¹⁴ position."""
        # Start at colony-specific basis vector
        position = torch.zeros(14)
        position[self.config.colony_idx % 14] = 0.1  # Small offset from origin
        return position

    @property
    def worker_id(self) -> str:
        return self.state.worker_id

    @property
    def colony_name(self) -> str:
        return self.state.colony_name

    @property
    def is_available(self) -> bool:
        """Check if worker can accept tasks."""
        return (
            self.state.status in (WorkerStatus.ACTIVE, WorkerStatus.IDLE)
            and self.state.current_tasks < self.config.max_concurrent
        )

    @property
    def fitness(self) -> float:
        """Get current fitness (convenience property)."""
        return self.state.fitness

    @fitness.setter
    def fitness(self, value: float) -> None:
        """Set fitness (convenience property)."""
        self.state.fitness = value

    @property
    def is_active(self) -> bool:
        """Check if agent is active."""
        return self.state.status != WorkerStatus.DEAD

    @is_active.setter
    def is_active(self, value: bool) -> None:
        """Set active status."""
        if not value:
            self.state.status = WorkerStatus.DEAD
        elif self.state.status == WorkerStatus.DEAD:
            self.state.status = WorkerStatus.IDLE

    @property
    def agent_id(self) -> str:
        """Get agent ID (alias for worker_id)."""
        return self.state.worker_id

    @property
    def last_action(self) -> torch.Tensor:
        """Get last action taken (for aggregation)."""
        return self.act()  # Recompute from current state

    def get_state(self, colony_z: torch.Tensor) -> torch.Tensor:
        """Get agent state as offset from colony z.

        Used by ColonyState.get_agent_states() for aggregation.

        Args:
            colony_z: [14] colony stochastic state

        Returns:
            [14] agent state (colony_z + offset based on H¹⁴ position)
        """
        # Project H¹⁴ position to 14D offset
        offset = self.state.h14_position[:14] * 0.1  # Small offset
        return colony_z + offset

    # =========================================================================
    # AGENT-LEVEL MARKOV BLANKET INTERFACE (Dec 2, 2025)
    # =========================================================================

    def perceive(
        self,
        colony_z: torch.Tensor,
        task_context: dict[str, Any] | None = None,
    ) -> torch.Tensor:
        """AGENT SENSORY INTERFACE: colony internal → agent sensory.

        Markov blanket property:
        - s_agent is influenced by colony internal state (z)
        - s_agent influences agent internal state (h14_position)
        - s_agent is NOT influenced by agent internal directly

        The agent's "external" IS the colony's "internal" (nested blankets).

        Args:
            colony_z: [14] colony internal state (H¹⁴)
            task_context: Optional task information

        Returns:
            sensory: [14] agent sensory state
        """
        # Base sensory is colony z (agent's external)
        sensory = colony_z.clone()

        # Modulate by task context if available
        if task_context is not None:
            task_encoding = self._encode_task_context(task_context)
            sensory = sensory + 0.1 * task_encoding  # Small perturbation

        return sensory

    def act(self) -> torch.Tensor:
        """AGENT ACTIVE INTERFACE: agent internal → agent action.

        Markov blanket property:
        - a_agent is influenced by agent internal (h14_position)
        - a_agent influences colony (via program execution)
        - a_agent is NOT influenced by colony directly

        Returns:
            action: [8] E8 octonion action
        """
        # Decode from H¹⁴ position to E8 action
        # Project 14D → 8D using first 8 components + nonlinearity
        h14 = self.state.h14_position

        # Simple projection with tanh for bounded actions
        if h14.shape[-1] >= 8:
            action = torch.tanh(h14[:8])
        else:
            # Pad to 8D
            action = torch.tanh(F.pad(h14, (0, 8 - h14.shape[-1])))

        return action

    def _encode_task_context(self, context: dict[str, Any]) -> torch.Tensor:
        """Encode task context to 14D vector."""
        # Hash-based encoding for now
        context_hash = hash(str(sorted(context.items())))
        encoding = torch.tensor(
            [((context_hash >> (i * 4)) & 0xF) / 7.5 - 1.0 for i in range(14)], dtype=torch.float32
        )
        return encoding

    # =========================================================================
    # SOLOMONOFF PROGRAM INTERFACE (for ColonyRSSM integration)
    # =========================================================================

    def select_program(self, state: torch.Tensor) -> dict[str, Any]:
        """Select a program from the library based on current state.

        This is the differentiable program selection interface used by
        ColonyRSSM.step_all_agents() for Markov blanket integration.

        Args:
            state: [14] internal state (z from colony or derived)

        Returns:
            Dict with program_embedding and selection info
        """
        # If library is wired, use it for differentiable selection
        if self.program_library is not None:
            try:  # type: ignore[unreachable]
                result = self.program_library.query(
                    state,
                    colony_type=self.state.colony_idx,
                    max_results=1,
                )
                if result is not None:
                    # Get program embedding from result (handle both .embedding and .program attrs)
                    raw_emb = getattr(result, "embedding", None)
                    if raw_emb is None:
                        raw_emb = getattr(result, "program", None)
                    if raw_emb is None:
                        raw_emb = state

                    # CRITICAL: Always truncate to 8D for E8 action space
                    # Programs are 52D (F₄), but action space is 8D (E₈ octonion)
                    if raw_emb.shape[-1] > 8:
                        program_emb = raw_emb[..., :8]
                    elif raw_emb.shape[-1] < 8:
                        program_emb = F.pad(raw_emb, (0, 8 - raw_emb.shape[-1]))
                    else:
                        program_emb = raw_emb

                    return {
                        "program_embedding": program_emb,
                        "program_index": result.index if hasattr(result, "index") else 0,
                        "complexity": result.complexity if hasattr(result, "complexity") else 0.0,
                    }
            except Exception as e:
                # HARDENED: Fail-fast on program selection errors
                raise RuntimeError(f"Program selection failed in geometric worker: {e}") from e

        # Default: use state itself as program embedding (truncate to 8D)
        return {
            "program_embedding": state[:8]
            if state.shape[-1] >= 8
            else F.pad(state, (0, 8 - state.shape[-1])),
            "program_index": 0,
            "complexity": 0.0,
        }

    def execute_program(self, program_embedding: torch.Tensor) -> torch.Tensor:
        """Execute a program to produce an action.

        This is the differentiable program execution interface used by
        ColonyRSSM.step_all_agents() for Markov blanket integration.

        Uses catastrophe dynamics for execution when available.

        Args:
            program_embedding: [8] program embedding

        Returns:
            action: [8] E8 octonion action
        """
        # Ensure 8D input
        if program_embedding.shape[-1] > 8:
            program_embedding = program_embedding[..., :8]
        elif program_embedding.shape[-1] < 8:
            program_embedding = F.pad(program_embedding, (0, 8 - program_embedding.shape[-1]))

        # If catastrophe dynamics wired, use for differentiable execution
        if self.catastrophe_dynamics is not None:
            try:  # type: ignore[unreachable]
                # Use execute_by_index which accepts colony index (not colony name)
                action = self.catastrophe_dynamics.execute_by_index(
                    self.state.colony_idx,
                    program_embedding,
                )
                if action is not None and action.shape[-1] == 8:
                    return cast(torch.Tensor, action)
            except Exception as e:
                # HARDENED: Fail-fast on catastrophe dynamics execution errors
                raise RuntimeError(f"Catastrophe dynamics execution failed: {e}") from e

        # Default: program embedding IS the action (with tanh for bounds)
        action = torch.tanh(program_embedding)

        # Ensure 8D output
        if action.shape[-1] != 8:
            if action.shape[-1] > 8:
                action = action[..., :8]
            else:
                action = F.pad(action, (0, 8 - action.shape[-1]))

        # Update internal state based on action (detached for stability)
        # FIXED (Dec 4, 2025): Ensure device consistency for gradient checkpointing
        if program_embedding.shape[-1] >= 8:
            update = (
                program_embedding[..., :8].detach()
                if program_embedding.shape[-1] >= 8
                else program_embedding.detach()
            )
            if self.state.h14_position.shape[-1] >= 8:
                # Move update to same device as state
                update = update.to(self.state.h14_position.device)
                self.state.h14_position[..., :8] = self.state.h14_position[..., :8] + 0.01 * update

        return action

    def update_from_reward(
        self,
        reward: float,
        action: torch.Tensor,
        use_differentiable: bool = True,
    ) -> dict[str, Any]:
        """Update agent based on reward signal.

        Called by ColonyRSSM.step_all_agents() for online learning.

        Args:
            reward: Reward signal
            action: Action that was taken
            use_differentiable: Whether to return differentiable losses

        Returns:
            Dict with complexity_loss and update info
        """
        # Update fitness based on reward - REAL EMA update (no fake 0.5 centering)
        alpha = self.config.fitness_ema_alpha
        # Direct reward mapping: positive → increase, negative → decrease, zero → slight decay
        if reward > 0:
            target_fitness = min(1.0, self.state.fitness + 0.1)
        elif reward < 0:
            target_fitness = max(0.0, self.state.fitness - 0.1)
        else:
            target_fitness = self.state.fitness * 0.99  # Slight decay for no-op
        self.state.fitness = alpha * target_fitness + (1 - alpha) * self.state.fitness

        result = {
            "fitness": self.state.fitness,
            "reward": reward,
        }

        if use_differentiable:
            # Compute complexity loss for library learning
            # Higher complexity = penalize programs that are used but give low reward
            complexity_loss = torch.tensor(0.0)
            if self.program_library is not None and reward < 0:  # type: ignore[unreachable]
                # Negative reward increases complexity of used program
                complexity_loss = torch.tensor(abs(reward) * 0.1)  # type: ignore[unreachable]
            result["complexity_loss"] = complexity_loss  # type: ignore[assignment]

        return result

    def should_die(self) -> bool:
        """Check if agent should die (low fitness)."""
        return (
            self.state.fitness < 0.1 and (self.state.completed_tasks + self.state.failed_tasks) > 10
        )

    def should_divide(self) -> bool:
        """Check if agent should divide (high fitness)."""
        return self.state.fitness > 0.8 and self.state.completed_tasks > 5

    def divide(self) -> GeometricWorker:
        """Create a child agent through division.

        OPTIMIZED (Dec 27, 2025): Learning transfer - child inherits parent's
        learned program preferences with mutation for exploration.
        """
        child = GeometricWorker(
            config=self.config,
            colony_idx=self.config.colony_idx,
        )
        # Inherit half fitness
        child.state.fitness = self.state.fitness * 0.5
        self.state.fitness = self.state.fitness * 0.5

        # Slightly mutate H¹⁴ position
        child.state.h14_position = self.state.h14_position + 0.1 * torch.randn(14)

        # Wire shared resources
        if self._program_library is not None:
            child._program_library = self._program_library  # type: ignore[unreachable]
        if self._catastrophe_dynamics is not None:
            child._catastrophe_dynamics = self._catastrophe_dynamics  # type: ignore[unreachable]

        # LEARNING TRANSFER (Dec 27, 2025): Transfer learned patterns
        # Copy success/failure counts with decay for fresh start
        child.state.completed_tasks = max(0, self.state.completed_tasks // 4)
        child.state.failed_tasks = max(0, self.state.failed_tasks // 4)

        # Transfer S7 section with slight mutation for exploration
        child.state.s7_section = F.normalize(
            self.state.s7_section + 0.05 * torch.randn_like(self.state.s7_section),
            dim=0,
        )

        logger.debug(
            f"Worker {self.worker_id} divided → child {child.worker_id} "
            f"(fitness={child.state.fitness:.2f}, inherited patterns)"
        )

        return child

    @property
    def program_library(self) -> None:
        """Get program library (lazy loaded).

        NOTE: For gradient flow during training, set[Any] _program_library to
        model._program_library via set_program_library().
        """
        if self._program_library is None and self.config.use_program_library:
            try:
                from kagami.core.world_model.memory import ProgramLibrary

                # Dec 21, 2025: Reduced from WARNING to DEBUG to avoid noise
                # Standalone library is expected for workers not connected to training
                logger.debug(
                    "GeometricWorker: Creating standalone ProgramLibrary. "
                    "For gradient flow, use set_program_library(model._program_library)."
                )
                self._program_library = ProgramLibrary()  # type: ignore[assignment]
            except ImportError:
                logger.debug("ProgramLibrary not available")
        return self._program_library

    def set_program_library(self, library) -> None:  # type: ignore[no-untyped-def]
        """Set the program library for gradient flow."""
        self._program_library = library

    @property
    def catastrophe_dynamics(self) -> None:
        """Get catastrophe dynamics (lazy loaded).

        NOTE: differentiable_catastrophe removed in Jan 2026 training consolidation.
        """
        if self._catastrophe_dynamics is None:
            logger.debug("Catastrophe dynamics deprecated - use kagami_math.catastrophe_constants")
        return self._catastrophe_dynamics

    async def execute(
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> TaskResult:
        """Execute an action.

        Args:
            action: Action name
            params: Action parameters
            context: Execution context

        Returns:
            TaskResult with outcome
        """
        task_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        context = context or {}

        # Safety check before execution
        try:
            from kagami.core.safety.cbf_integration import check_cbf_for_operation

            cbf_result = await check_cbf_for_operation(
                operation=f"worker.{self.colony_name}.execute",
                action=action,
                target=self.worker_id,
                params=params,
                metadata={
                    "worker_id": self.worker_id,
                    "colony_idx": self.state.colony_idx,
                    "context": context,
                },
                source="worker",
            )

            if not cbf_result.safe:
                latency = time.time() - start_time
                correlation_id = context.get("correlation_id") or generate_correlation_id()

                # Emit receipt for CBF safety violation
                try:
                    emit_receipt(
                        correlation_id=correlation_id,
                        event_name="worker.task.execute",
                        phase="EXECUTE",
                        colony=self.colony_name,
                        parent_receipt_id=context.get("parent_receipt_id"),
                        action=action,
                        event_data={
                            "worker": self.worker_id,
                            "task_id": task_id,
                            "program": None,
                            "latency": latency,
                            "reason": f"Safety barrier violation: {cbf_result.reason}",
                        },
                        status="blocked",
                    )
                except Exception as receipt_error:
                    logger.debug(f"Receipt emission failed for task {task_id}: {receipt_error}")

                return TaskResult(
                    task_id=task_id,
                    success=False,
                    error=f"Safety barrier violation: {cbf_result.reason}",
                    latency=latency,
                    metadata={
                        "worker_id": self.worker_id,
                        "colony": self.colony_name,
                    },
                    correlation_id=correlation_id,
                    phase=context.get("phase"),
                    parent_receipt_id=context.get("parent_receipt_id"),
                )
        except ImportError:
            # CBF module not available - FAIL CLOSED (safety invariant)
            logger.error(f"🛑 CBF module unavailable for worker {self.worker_id} - FAIL CLOSED")
            latency = time.time() - start_time
            correlation_id = context.get("correlation_id") or generate_correlation_id()

            # Emit receipt for CBF unavailable
            try:
                emit_receipt(
                    correlation_id=correlation_id,
                    event_name="worker.task.execute",
                    phase="EXECUTE",
                    colony=self.colony_name,
                    parent_receipt_id=context.get("parent_receipt_id"),
                    action=action,
                    event_data={
                        "worker": self.worker_id,
                        "task_id": task_id,
                        "program": None,
                        "latency": latency,
                        "reason": "Safety system unavailable - operation blocked (fail-closed)",
                    },
                    status="blocked",
                )
            except Exception as receipt_error:
                logger.debug(f"Receipt emission failed for task {task_id}: {receipt_error}")

            return TaskResult(
                task_id=task_id,
                success=False,
                error="Safety system unavailable - operation blocked (fail-closed)",
                latency=latency,
                metadata={
                    "worker_id": self.worker_id,
                    "colony": self.colony_name,
                    "blocked": True,
                    "h_x": -1.0,
                    "reason": "cbf_unavailable",
                },
                correlation_id=correlation_id,
                phase=context.get("phase"),
                parent_receipt_id=context.get("parent_receipt_id"),
            )

        async with self._semaphore:
            self.state.current_tasks += 1
            self.state.status = WorkerStatus.BUSY
            self.state.last_active = time.time()

            try:
                # Select program if library available
                program_idx = None
                if self.program_library is not None:
                    program_idx = await self._select_program(action, params)  # type: ignore[unreachable]

                # Execute with catastrophe dynamics
                result = await self._execute_with_catastrophe(action, params, context, program_idx)

                # Update metrics
                latency = time.time() - start_time
                self._update_success(latency)

                # Emit receipt for successful task execution
                correlation_id = context.get("correlation_id") or generate_correlation_id()
                try:
                    emit_receipt(
                        correlation_id=correlation_id,
                        event_name="worker.task.execute",
                        phase="EXECUTE",
                        colony=self.colony_name,
                        parent_receipt_id=context.get("parent_receipt_id"),
                        action=action,
                        event_data={
                            "worker": self.worker_id,
                            "task_id": task_id,
                            "program": program_idx,
                            "latency": latency,
                        },
                        status="success",
                    )
                except Exception as e:
                    logger.debug(f"Receipt emission failed for task {task_id}: {e}")

                return TaskResult(
                    task_id=task_id,
                    success=True,
                    result=result,
                    latency=latency,
                    program_used=program_idx,
                    metadata={
                        "worker_id": self.worker_id,
                        "colony": self.colony_name,
                    },
                    correlation_id=correlation_id,
                    phase=context.get("phase"),
                    parent_receipt_id=context.get("parent_receipt_id"),
                )

            except Exception as e:
                latency = time.time() - start_time
                self._update_failure(latency)

                # Emit receipt for failed task execution
                correlation_id = context.get("correlation_id") or generate_correlation_id()
                try:
                    emit_receipt(
                        correlation_id=correlation_id,
                        event_name="worker.task.execute",
                        phase="EXECUTE",
                        colony=self.colony_name,
                        parent_receipt_id=context.get("parent_receipt_id"),
                        action=action,
                        event_data={
                            "worker": self.worker_id,
                            "task_id": task_id,
                            "program": None,
                            "latency": latency,
                            "error": str(e),
                        },
                        status="error",
                    )
                except Exception as receipt_error:
                    logger.debug(f"Receipt emission failed for task {task_id}: {receipt_error}")

                return TaskResult(
                    task_id=task_id,
                    success=False,
                    error=str(e),
                    latency=latency,
                    metadata={
                        "worker_id": self.worker_id,
                        "colony": self.colony_name,
                    },
                    correlation_id=correlation_id,
                    phase=context.get("phase"),
                    parent_receipt_id=context.get("parent_receipt_id"),
                )
            finally:
                self.state.current_tasks -= 1
                if self.state.current_tasks == 0:
                    self.state.status = WorkerStatus.IDLE

    async def _select_program(
        self,
        action: str,
        params: dict[str, Any],
    ) -> int | None:
        """Select program from MDL-based library.

        Uses P(program | action) ∝ similarity × 2^{-K(program)}

        Returns:
            E₈ program index (0-239) or None
        """
        if self.program_library is None:
            return None

        try:  # type: ignore[unreachable]
            # Encode action as query
            query = self._encode_action(action, params)

            # Query library
            program = self.program_library.query(
                query,
                colony_type=self.state.colony_idx,
                max_results=1,
            )

            return program.index if program else None

        except Exception as e:
            logger.debug(f"Program selection failed: {e}")
            return None

    def _encode_action(self, action: str, params: dict[str, Any]) -> torch.Tensor:
        """Encode action as 8D vector for program lookup."""
        # Simple hash-based encoding
        action_hash = hash(action)
        param_hash = hash(str(sorted(params.items())))

        combined = action_hash ^ param_hash

        # Convert to 8D
        encoding = torch.tensor(
            [((combined >> (i * 8)) & 0xFF) / 127.5 - 1.0 for i in range(8)], dtype=torch.float32
        )

        return F.normalize(encoding, dim=0)

    async def _execute_with_catastrophe(
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any],
        program_idx: int | None,
    ) -> Any:
        """Execute action using catastrophe dynamics.

        The catastrophe type determines execution behavior:
        - Fold: Abrupt transitions
        - Cusp: Bifurcation decisions
        - Swallowtail: Hysteresis/memory
        - Butterfly: Multi-stability
        - Hyperbolic: Splitting
        - Elliptic: Smooth exploration
        - Parabolic: Verification
        """
        # Get catastrophe risk
        risk = await self._assess_catastrophe_risk(context)

        if risk > self.config.catastrophe_threshold:
            logger.warning(
                f"High catastrophe risk {risk:.2f} for {action}, type={self.state.catastrophe_type}"
            )

        # Execute the actual action
        # In production, this would call the appropriate skill/tool
        result = await self._do_execute(action, params, context)

        # Update H¹⁴ position based on outcome
        self._update_h14_position(result)

        return result

    async def _assess_catastrophe_risk(self, context: dict[str, Any]) -> float:
        """Assess catastrophe risk for current state."""
        if self.catastrophe_dynamics is None:
            return 0.7  # Conservative high-risk when dynamics unavailable

        try:  # type: ignore[unreachable]
            risk = self.catastrophe_dynamics.compute_risk(
                state=self.state.h14_position,
                colony_type=self.state.colony_idx,
            )
            return float(risk)
        except Exception:
            return 0.8  # High risk on computation failure

    async def _do_execute(
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> Any:
        """Actually execute the action.

        This is the core execution - delegates to skills/tools.
        """
        # Simulate execution for now
        # In production, this would route to actual execution
        await asyncio.sleep(0.01)

        return {
            "action": action,
            "status": "completed",
            "worker": self.worker_id,
            "colony": self.colony_name,
        }

    def _update_h14_position(self, result: Any) -> None:
        """Update H¹⁴ position based on execution outcome."""
        # Move slightly toward/away from origin based on success
        success = result.get("status") == "completed" if isinstance(result, dict) else True

        direction = -0.01 if success else 0.01  # Toward origin on success
        self.state.h14_position = self.state.h14_position * (1 + direction)

    def _update_success(self, latency: float) -> None:
        """Update state after successful execution."""
        self.state.completed_tasks += 1

        # EMA update for latency
        alpha = self.config.fitness_ema_alpha
        self.state.avg_latency = alpha * latency + (1 - alpha) * self.state.avg_latency

        # Update fitness
        self.state.fitness = min(1.0, self.state.fitness + 0.01)

    def _update_failure(self, latency: float) -> None:
        """Update state after failed execution."""
        self.state.failed_tasks += 1

        # Update fitness
        self.state.fitness = max(0.0, self.state.fitness - 0.05)

    def should_retire(self) -> bool:
        """Check if worker should retire."""
        total_ops = self.state.completed_tasks + self.state.failed_tasks

        # Too many operations
        if total_ops >= self.config.max_operations:
            return True

        # Too low fitness
        if self.state.fitness < 0.1 and total_ops > 50:
            return True

        return False

    def should_hibernate(self) -> bool:
        """Check if worker should hibernate."""
        idle_time = time.time() - self.state.last_active
        return idle_time > self.config.idle_timeout

    async def hibernate(self) -> None:
        """Enter hibernation."""
        self.state.status = WorkerStatus.HIBERNATING
        logger.info(f"Worker {self.worker_id} entering hibernation")

    async def wake(self) -> None:
        """Wake from hibernation."""
        self.state.status = WorkerStatus.IDLE
        self.state.last_active = time.time()
        logger.info(f"Worker {self.worker_id} woke from hibernation")

    async def retire(self) -> None:
        """Retire worker (graceful shutdown)."""
        self.state.status = WorkerStatus.DEAD
        logger.info(
            f"Worker {self.worker_id} retiring: "
            f"completed={self.state.completed_tasks}, "
            f"failed={self.state.failed_tasks}, "
            f"fitness={self.state.fitness:.2f}"
        )

    def get_stats(self) -> dict[str, Any]:
        """Get worker statistics."""
        return {
            "worker_id": self.worker_id,
            "colony": self.colony_name,
            "catastrophe": self.state.catastrophe_type,
            "status": self.state.status.value,
            "completed": self.state.completed_tasks,
            "failed": self.state.failed_tasks,
            "success_rate": self.state.success_rate,
            "fitness": self.state.fitness,
            "avg_latency": self.state.avg_latency,
            "current_tasks": self.state.current_tasks,
            "age_seconds": time.time() - self.state.created_at,
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_worker(
    colony_idx: int = 0,
    config: WorkerConfig | None = None,
) -> GeometricWorker:
    """Create a geometric worker.

    Args:
        colony_idx: Colony assignment (0-6)
        config: Optional configuration

    Returns:
        Configured GeometricWorker
    """
    return GeometricWorker(config=config, colony_idx=colony_idx)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CATASTROPHE_TYPES",
    "COLONY_NAMES",
    "GeometricWorker",
    "TaskResult",
    "WorkerConfig",
    "WorkerState",
    "WorkerStatus",
    "create_worker",
]
