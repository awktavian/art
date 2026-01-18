"""Minimal Colony - Catastrophe-Driven Agent Colony.

This module replaces the 1050-line legacy colony.py with a minimal
implementation using the unified agent architecture.

CATASTROPHE DYNAMICS:
=====================
Each colony embodies one of Thom's 7 elementary catastrophes:
    Spark   → Fold (A₂)        - Sudden ignition
    Forge   → Cusp (A₃)        - Bistable decision
    Flow    → Swallowtail (A₄) - Multi-stable recovery
    Nexus   → Butterfly (A₅)   - Complex integration
    Beacon  → Hyperbolic (D₄⁺) - Outward focus
    Grove   → Elliptic (D₄⁻)   - Inward search
    Crystal → Parabolic (D₅)   - Safety boundary

ARCHITECTURE:
=============
MinimalColony manages a pool of GeometricWorkers for a single domain.
- Workers are created on-demand (lazy initialization)
- Routing uses FanoActionRouter (1/3/7 action modes)
- Catastrophe dynamics govern phase transitions

KERNEL INTEGRATION (December 14, 2025):
========================================
Each colony now includes a catastrophe decision kernel that computes
S⁷-normalized outputs based on the colony's catastrophe type:
- execute_kernel(): Computes S⁷ decision output from action/params/context
- Dual-process routing: k_value < 3 → fast path, k_value ≥ 3 → slow path
- Fallback to S⁷ section if catastrophe_kernels module unavailable

Enable kernel computation by passing use_kernel=True in context:
    result = await colony.execute(action, params, {"use_kernel": True, "k_value": 2})

Created: December 2, 2025
Updated: December 14, 2025 (kernel integration)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import torch
import torch.nn.functional as F

if TYPE_CHECKING:
    from kagami.core.unified_agents.unified_organism import UnifiedOrganism

# HARDENED: Direct receipt imports - no facade abstraction
from kagami.core.receipts.facade import emit_receipt
from kagami.core.unified_agents.colony_constants import DomainType
from kagami.core.unified_agents.fano_action_router import (
    get_fano_router,
)
from kagami.core.unified_agents.geometric_worker import (
    COLONY_NAMES,
    GeometricWorker,
    TaskResult,
    WorkerConfig,
    create_worker,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CATASTROPHE EMBEDDINGS
# =============================================================================

# Catastrophe type names
CATASTROPHE_TYPES = (
    "fold",
    "cusp",
    "swallowtail",
    "butterfly",
    "hyperbolic",
    "elliptic",
    "parabolic",
)

# Colony to catastrophe type
COLONY_TO_CATASTROPHE: dict[str, str] = dict(zip(COLONY_NAMES, CATASTROPHE_TYPES, strict=False))

# Unit vectors for each colony's catastrophe embedding (7D)
DOMAIN_TO_S7: dict[str, np.ndarray[Any, Any]] = {
    name: np.eye(7, dtype=np.float32)[i] for i, name in enumerate(COLONY_NAMES)
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ColonyConfig:
    """Configuration for minimal colony.

    OPTIMIZED (Dec 21, 2025 - Forge):
    - min_workers: 1 → 2 (redundancy for fault tolerance)
    """

    colony_idx: int = 0  # Which colony (0-6)
    min_workers: int = 2  # Min workers to maintain (increased from 1)
    max_workers: int = 10  # Max workers to spawn
    worker_config: WorkerConfig | None = None


@dataclass
class ColonyStats:
    """Colony statistics."""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    active_workers: int = 0
    avg_latency: float = 0.0
    created_at: float = field(default_factory=time.time)

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


# =============================================================================
# MINIMAL COLONY
# =============================================================================


class MinimalColony:
    """Simplified colony using GeometricWorker.

    Replaces the 1050-line legacy AgentColony with a minimal
    implementation focused on:
    - Worker pool management
    - Task routing via FanoActionRouter
    - S⁷ geometric state tracking
    """

    def __init__(
        self,
        colony_idx: int = 0,
        config: ColonyConfig | None = None,
    ):
        """Initialize minimal colony.

        Args:
            colony_idx: Colony index (0-6)
            config: Optional configuration
        """
        self.config = config or ColonyConfig(colony_idx=colony_idx)
        self.colony_idx = self.config.colony_idx
        self.colony_name = COLONY_NAMES[self.colony_idx]

        # S⁷ section for this colony
        self.s7_section = DOMAIN_TO_S7[self.colony_name].copy()

        # Catastrophe decision kernel
        self.kernel = self._create_kernel()

        # Worker pool
        self._workers: list[GeometricWorker] = []
        self._worker_lock = asyncio.Lock()

        # Router (use singleton to avoid 7x initialization overhead)
        self._router = get_fano_router()

        # Stats
        self.stats = ColonyStats()

        # Last kernel output for state extraction
        self._last_kernel_output: dict[str, Any] | None = None

        # Inter-colony communication
        self._organism: UnifiedOrganism | None = None  # Set by organism

        # Initialize minimum workers
        self._ensure_min_workers()

        logger.debug(
            "MinimalColony '%s' initialized with %s kernel",
            self.colony_name,
            CATASTROPHE_TYPES[self.colony_idx],
        )

        # Preload specialized agent for real processing
        self._preload_specialized_agent()

    @property
    def domain(self) -> DomainType:
        """Get the domain type for this colony."""
        return DomainType(self.colony_name)

    @property
    def workers(self) -> list[GeometricWorker]:
        """Worker pool accessor."""
        return self._workers

    def _create_kernel(self) -> Any:
        """Create catastrophe decision kernel for this colony.

        Returns:
            Kernel module (or None if catastrophe_kernels not available)
        """
        try:
            from kagami.core.unified_agents.catastrophe_kernels import create_colony_kernel

            # Default state dimension - can be overridden by config
            state_dim = 256

            kernel = create_colony_kernel(
                colony_idx=self.colony_idx,
                state_dim=state_dim,
            )
            logger.debug(
                f"Initialized {CATASTROPHE_TYPES[self.colony_idx]} kernel for {self.colony_name}"
            )
            return kernel

        except ImportError:
            logger.warning(
                f"catastrophe_kernels module not available for {self.colony_name}, using fallback"
            )
            return None

    def _encode_state(
        self, action: str, params: dict[str, Any], context: dict[str, Any]
    ) -> torch.Tensor:
        """Encode action + params + context into state tensor.

        Uses simple hashing for strings, concatenates numeric params.

        Args:
            action: Action name
            params: Action parameters
            context: Execution context

        Returns:
            State tensor [1, state_dim] (state_dim=256)
        """
        state_dim = 256
        state = torch.zeros(1, state_dim)

        # Hash action string into first 64 dimensions
        action_hash = hash(action) % (2**32)
        for i in range(64):
            state[0, i] = float((action_hash >> i) & 1)

        # Extract numeric values from params and encode into next 64 dims
        param_idx = 64
        for key in sorted(params.keys())[:32]:  # Take first 32 keys
            val = params[key]
            if isinstance(val, int | float):
                if param_idx < 128:
                    state[0, param_idx] = float(val)
                    param_idx += 1
                if param_idx < 128:
                    # Store key hash as well
                    state[0, param_idx] = float(hash(key) % 256) / 256.0
                    param_idx += 1

        # Encode context metadata into remaining dims
        context_idx = 128
        if "k_value" in context and context_idx < state_dim:
            state[0, context_idx] = float(context["k_value"])
            context_idx += 1

        if "phase" in context and context_idx < state_dim:
            phase_hash = hash(str(context["phase"])) % 256
            state[0, context_idx] = float(phase_hash) / 256.0
            context_idx += 1

        # Colony index encoding
        if context_idx + 7 < state_dim:
            state[0, context_idx : context_idx + 7] = torch.tensor(self.s7_section[:7])

        return state

    def _ensure_min_workers(self) -> None:
        """Ensure minimum workers are available."""
        while len(self._workers) < self.config.min_workers:
            worker = create_worker(
                colony_idx=self.colony_idx,
                config=self.config.worker_config,
            )
            self._workers.append(worker)

    def _get_available_worker(self) -> GeometricWorker | None:
        """Get an available worker from the pool."""
        for worker in self._workers:
            if worker.is_available:
                return worker

        # Spawn new worker if under limit
        if len(self._workers) < self.config.max_workers:
            worker = create_worker(
                colony_idx=self.colony_idx,
                config=self.config.worker_config,
            )
            self._workers.append(worker)
            return worker

        return None

    def process_with_catastrophe(self, task: str, context: dict[str, Any] | None = None) -> Any:
        """Process task using the REAL colony agent's catastrophe dynamics.

        This method delegates to the actual specialized agent implementation
        (CrystalAgent, FlowAgent, etc.) instead of just running the kernel.

        Args:
            task: Task description
            context: Execution context

        Returns:
            AgentResult from the specialized agent
        """
        context = context or {}

        # Get the REAL specialized agent for this colony
        agent = self._get_specialized_agent()

        if agent is not None:
            return agent.process_with_catastrophe(task, context)

        # Fallback: use kernel computation if no specialized agent
        logger.debug(f"{self.colony_name}: Using kernel fallback (no specialized agent)")
        kernel_result = self.execute_kernel(task, {}, context)
        return kernel_result

    def _preload_specialized_agent(self) -> None:
        """Preload specialized agent at colony initialization."""
        try:
            self._get_specialized_agent()
        except Exception as e:
            logger.debug(f"Deferred specialized agent loading for {self.colony_name}: {e}")

    def _get_specialized_agent(self) -> Any:
        """Get the specialized agent for this colony.

        Returns the actual agent class (CrystalAgent, FlowAgent, etc.)
        that contains the full catastrophe processing logic.
        """
        if not hasattr(self, "_specialized_agent"):
            self._specialized_agent = None
            try:
                # Import the appropriate agent based on colony name
                agent_map = {
                    "spark": ("kagami.core.unified_agents.agents.spark_agent", "SparkAgent"),
                    "forge": ("kagami.core.unified_agents.agents.forge_agent", "ForgeAgent"),
                    "flow": ("kagami.core.unified_agents.agents.flow_agent", "FlowAgent"),
                    "nexus": ("kagami.core.unified_agents.agents.nexus_agent", "NexusAgent"),
                    "beacon": ("kagami.core.unified_agents.agents.beacon_agent", "BeaconAgent"),
                    "grove": ("kagami.core.unified_agents.agents.grove_agent", "GroveAgent"),
                    "crystal": ("kagami.core.unified_agents.agents.crystal_agent", "CrystalAgent"),
                }

                if self.colony_name in agent_map:
                    module_path, class_name = agent_map[self.colony_name]
                    import importlib

                    module = importlib.import_module(module_path)
                    agent_class = getattr(module, class_name)
                    self._specialized_agent = agent_class(state_dim=256)
                    logger.info(f"{self.colony_name}: Loaded specialized agent {class_name}")
            except Exception as e:
                logger.warning(f"Failed to load specialized agent for {self.colony_name}: {e}")

        return self._specialized_agent

    def execute_kernel(
        self, action: str, params: dict[str, Any], context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute catastrophe kernel computation.

        Computes S⁷-normalized decision output based on action, params, and context.
        This is the core catastrophe decision mechanism for the colony.

        Args:
            action: Action name
            params: Action parameters
            context: Execution context (must include k_value for dual-process routing)

        Returns:
            Dictionary with:
                - success: bool
                - s7_output: torch.Tensor [1, 8] normalized to S⁷
                - kernel_type: "fast" | "slow"
                - colony_idx: int
                - metadata: dict[str, Any] with k_value, catastrophe_type
        """
        try:
            # 1. Encode state
            state = self._encode_state(action, params, context)

            # 2. Get k-value (determines fast/slow path)
            k_value = context.get("k_value", 1)  # Default to fast path

            # 3. Compute kernel output
            if self.kernel is not None:
                # Real kernel computation
                kernel_output = self.kernel(state, k_value)
            else:
                # Fallback: use S⁷ section as output
                logger.debug(f"Using fallback S⁷ section for {self.colony_name}")
                # Expand s7_section to 8D (add real part)
                s7_full = np.zeros(8, dtype=np.float32)
                s7_full[1:8] = self.s7_section[:7]  # Imaginary parts
                kernel_output = torch.from_numpy(s7_full).unsqueeze(0)

            # 4. Normalize to S⁷
            s7_output = F.normalize(kernel_output, dim=-1)

            # 5. Build and cache result for state extraction
            result = {
                "success": True,
                "s7_output": s7_output,  # [1, 8]
                "kernel_type": "fast" if k_value < 3 else "slow",
                "colony_idx": self.colony_idx,
                "metadata": {
                    "k_value": k_value,
                    "catastrophe_type": CATASTROPHE_TYPES[self.colony_idx],
                    "action": action,
                },
            }
            self._last_kernel_output = result
            return result

        except Exception as e:
            logger.error(
                f"Colony {self.colony_idx} ({self.colony_name}) kernel execution failed: {e}"
            )
            # Return safe fallback (don't cache failures)
            return {
                "success": False,
                "error": str(e),
                "colony_idx": self.colony_idx,
            }

    async def send_e8_message(
        self,
        target_colony_idx: int,
        data: torch.Tensor,
        message_type: str = "inform",
        correlation_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Send E8-encoded message to peer colony.

        Uses the E8 lattice (240 roots) to quantize 8D data for
        inter-colony communication. Messages are sent via the organism's
        coordinator which handles encoding and routing.

        Args:
            target_colony_idx: Recipient colony (0-6)
            data: 8D tensor to encode (will be normalized to S⁷)
            message_type: Message type (inform, query, request_decision)
            correlation_id: Optional trace ID for correlation

        Returns:
            Encoded message dict[str, Any] with e8_index, or None if organism not available
        """
        if self._organism is None:
            logger.warning(
                f"Colony {self.colony_name} cannot send E8 message: organism reference not set[Any]"
            )
            return None

        # Use organism's coordinator to encode
        try:
            encoded = self._organism.encode_e8_message(
                source_colony=self.colony_idx,
                target_colony=target_colony_idx,
                data=data,
            )

            # Add message metadata
            import uuid

            encoded["message_type"] = message_type
            encoded["correlation_id"] = correlation_id or str(uuid.uuid4())[:8]
            encoded["timestamp"] = time.time()

            logger.debug(
                f"Colony {self.colony_name} encoded E8 message to "
                f"{COLONY_NAMES[target_colony_idx]}: e8_index={encoded['e8_index']}"
            )

            return encoded

        except Exception as e:
            logger.error(f"E8 message encoding failed: {e}")
            return None

    def set_organism(self, organism: UnifiedOrganism) -> None:
        """Set organism reference for inter-colony communication.

        Called by UnifiedOrganism when creating/registering colonies.

        Args:
            organism: Parent UnifiedOrganism instance
        """
        self._organism = organism
        logger.debug(f"Colony {self.colony_name} linked to organism")

    async def spawn_worker(self, task: dict[str, Any] | None = None) -> GeometricWorker:
        """Spawn a new worker in this colony.

        Args:
            task: Optional spawn context (e.g., syscall metadata).

        Returns:
            Newly created worker.

        Raises:
            RuntimeError: If max worker limit is reached.
        """
        _ = task  # reserved for future receipts/metrics
        async with self._worker_lock:
            if len(self._workers) >= self.config.max_workers:
                raise RuntimeError(
                    f"Colony '{self.colony_name}' at max workers ({self.config.max_workers})"
                )

            worker = create_worker(
                colony_idx=self.colony_idx,
                config=self.config.worker_config,
            )
            # Optional back-reference used by some lifecycle logic.
            worker._colony = self  # type: ignore[attr-defined]
            self._workers.append(worker)
            return worker

    async def execute(
        self,
        action: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> TaskResult:
        """Execute an action in this colony.

        Args:
            action: Action name
            params: Action parameters
            context: Execution context

        Returns:
            TaskResult with outcome
        """
        context = context or {}
        start_time = time.perf_counter()

        # Ensure correlation_id for receipt chain tracking
        if "correlation_id" not in context:
            import uuid

            context["correlation_id"] = str(uuid.uuid4())[:8]

        correlation_id = context["correlation_id"]

        # RECEIPT: PLAN phase - before CBF check
        try:
            emit_receipt(
                correlation_id=correlation_id,
                event_name="colony.execute.plan",
                phase="PLAN",
                action=action,
                app="colony",
                colony=self.colony_name,
                event_data={
                    "colony": self.colony_name,
                    "colony_idx": self.colony_idx,
                    "action": action,
                    "use_kernel": context.get("use_kernel", False),
                },
            )
        except Exception as e:
            logger.debug(f"PLAN receipt emission failed: {e}")

        # Safety check before execution (INVIOLABLE: h(x) >= 0)
        # CBF is ALWAYS enforced - fast path in test mode (~0.002ms)
        try:
            from kagami.core.safety.cbf_integration import check_cbf_for_operation

            cbf_result = await check_cbf_for_operation(
                operation=f"colony.{self.colony_name}.execute",
                action=action,
                target=self.colony_name,
                params=params,
                metadata={"colony_idx": self.colony_idx, "context": context},
                source="colony",
            )

            if not cbf_result.safe:
                # Log blocked execution
                logger.warning(
                    f"CBF BLOCKED colony execution: colony={self.colony_name}, "
                    f"action={action}, reason={cbf_result.reason}, h(x)={cbf_result.h_x:.3f}"
                )

                # RECEIPT: PLAN phase error - CBF block
                try:
                    emit_receipt(
                        correlation_id=correlation_id,
                        event_name="colony.execute.error.cbf_block",
                        phase="PLAN",
                        action=action,
                        app="colony",
                        colony=self.colony_name,
                        status="error",
                        event_data={
                            "error_type": "cbf_block",
                            "colony": self.colony_name,
                            "h_x": cbf_result.h_x,
                            "reason": cbf_result.reason,
                            "detail": cbf_result.detail,
                        },
                    )
                except Exception as e:
                    logger.debug(f"PLAN error receipt emission failed: {e}")

                # Count as failed task
                self.stats.failed_tasks += 1

                # Return blocked result with safety metadata
                return TaskResult(
                    task_id=str(__import__("uuid").uuid4())[:8],
                    success=False,
                    error=f"Safety barrier violation: {cbf_result.reason}",
                    latency=time.perf_counter() - start_time,
                    correlation_id=context.get("correlation_id"),
                    phase=context.get("phase"),
                    parent_receipt_id=context.get("parent_receipt_id"),
                    metadata={
                        "blocked": True,
                        "h_x": cbf_result.h_x,
                        "reason": cbf_result.reason,
                        "detail": cbf_result.detail,
                        "colony": self.colony_name,
                    },
                )
        except ImportError as e:
            # CBF module not available - FAIL CLOSED (mandatory safety layer)
            logger.error(f"CBF module unavailable for colony {self.colony_name} - FAIL CLOSED: {e}")

            # RECEIPT: PLAN phase error - CBF unavailable
            try:
                emit_receipt(
                    correlation_id=correlation_id,
                    event_name="colony.execute.error.cbf_unavailable",
                    phase="PLAN",
                    action=action,
                    app="colony",
                    colony=self.colony_name,
                    status="error",
                    event_data={
                        "error_type": "cbf_unavailable",
                        "colony": self.colony_name,
                        "detail": str(e),
                    },
                )
            except Exception as emit_error:
                logger.debug(f"PLAN error receipt emission failed: {emit_error}")

            self.stats.failed_tasks += 1
            return TaskResult(
                task_id=str(__import__("uuid").uuid4())[:8],
                success=False,
                error="Safety system unavailable - operation blocked (fail-closed)",
                latency=time.perf_counter() - start_time,
                correlation_id=context.get("correlation_id"),
                phase=context.get("phase"),
                parent_receipt_id=context.get("parent_receipt_id"),
                metadata={
                    "blocked": True,
                    "h_x": -1.0,
                    "reason": "cbf_unavailable",
                    "detail": "Safety module failed to load",
                    "colony": self.colony_name,
                },
            )
        except Exception as e:
            # CBF check failed - FAIL CLOSED
            logger.error(f"CBF check failed for colony {self.colony_name}: {e}", exc_info=True)

            # RECEIPT: PLAN phase error - CBF execution failure
            try:
                emit_receipt(
                    correlation_id=correlation_id,
                    event_name="colony.execute.error.cbf_execution_failure",
                    phase="PLAN",
                    action=action,
                    app="colony",
                    colony=self.colony_name,
                    status="error",
                    event_data={
                        "error_type": "cbf_execution_failure",
                        "colony": self.colony_name,
                        "detail": str(e),
                    },
                )
            except Exception as emit_error:
                logger.debug(f"PLAN error receipt emission failed: {emit_error}")

            self.stats.failed_tasks += 1
            return TaskResult(
                task_id=str(__import__("uuid").uuid4())[:8],
                success=False,
                error=f"Safety check failed - operation blocked (fail-closed): {e}",
                latency=time.perf_counter() - start_time,
                correlation_id=context.get("correlation_id"),
                phase=context.get("phase"),
                parent_receipt_id=context.get("parent_receipt_id"),
                metadata={
                    "blocked": True,
                    "h_x": -1.0,
                    "reason": "cbf_execution_failure",
                    "detail": str(e),
                    "colony": self.colony_name,
                },
            )

        self.stats.total_tasks += 1

        # Compute kernel decision (if enabled in context)
        kernel_result = None
        if context.get("use_kernel", False):
            try:
                kernel_result = self.execute_kernel(action, params, context)
                logger.debug(
                    f"Kernel computation for {self.colony_name}: "
                    f"{kernel_result.get('kernel_type', 'unknown')}"
                )
            except Exception as e:
                logger.warning(f"Kernel computation failed for {self.colony_name}: {e}")

        # Get routing decision
        self._router.route(action, params, context=context)

        # Find available worker
        async with self._worker_lock:
            worker = self._get_available_worker()

        if worker is None:
            # RECEIPT: EXECUTE phase error - no workers
            try:
                emit_receipt(
                    correlation_id=correlation_id,
                    event_name="colony.execute.error.no_workers",
                    phase="EXECUTE",
                    action=action,
                    app="colony",
                    colony=self.colony_name,
                    status="error",
                    event_data={
                        "error_type": "no_workers",
                        "colony": self.colony_name,
                    },
                )
            except Exception as e:
                logger.debug(f"EXECUTE error receipt emission failed: {e}")
            self.stats.failed_tasks += 1
            return TaskResult(
                task_id="none",
                success=False,
                error="No available workers",
                correlation_id=context.get("correlation_id"),
                phase=context.get("phase"),
                parent_receipt_id=context.get("parent_receipt_id"),
            )

        # RECEIPT: EXECUTE phase - worker selected, about to execute
        try:
            emit_receipt(
                correlation_id=correlation_id,
                event_name="colony.execute.action",
                phase="EXECUTE",
                action=action,
                app="colony",
                colony=self.colony_name,
                parent_receipt_id=correlation_id,
                event_data={
                    "colony": self.colony_name,
                    "worker": worker.name,  # type: ignore[attr-defined]
                    "worker_id": worker.worker_id,
                    "kernel_enabled": context.get("use_kernel", False),
                },
            )
        except Exception as e:
            logger.debug(f"EXECUTE receipt emission failed: {e}")

        # Execute on worker
        result = await worker.execute(action, params, context)

        # Attach kernel result to worker output if computed
        if kernel_result is not None and kernel_result.get("success", False):
            if result.result is None:
                result.result = {}
            if isinstance(result.result, dict):
                s7_out = kernel_result["s7_output"]
                s7_serialized = s7_out.tolist() if hasattr(s7_out, "tolist") else s7_out
                result.result["kernel_output"] = {
                    "s7_output": s7_serialized,
                    "kernel_type": kernel_result["kernel_type"],
                    "metadata": kernel_result["metadata"],
                }

        # Update stats
        if result.success:
            self.stats.completed_tasks += 1
        else:
            self.stats.failed_tasks += 1

        # EMA latency update
        alpha = 0.1
        self.stats.avg_latency = alpha * result.latency + (1 - alpha) * self.stats.avg_latency

        # RECEIPT: VERIFY phase - task completed
        try:
            # Truncate output for receipt (max 100 chars)
            output_snippet = None
            if result.result is not None:
                result_str = str(result.result)
                output_snippet = result_str[:100] + "..." if len(result_str) > 100 else result_str

            emit_receipt(
                correlation_id=correlation_id,
                event_name="colony.execute.verify",
                phase="VERIFY",
                action=action,
                app="colony",
                colony=self.colony_name,
                parent_receipt_id=correlation_id,
                status="success" if result.success else "error",
                event_data={
                    "colony": self.colony_name,
                    "success": result.success,
                    "latency": result.latency,
                    "output_snippet": output_snippet,
                    "error": result.error if not result.success else None,
                },
            )
        except Exception as e:
            logger.debug(f"VERIFY receipt emission failed: {e}")

        return result

    async def execute_batch(
        self,
        actions: list[tuple[str, dict[str, Any]]],
        context: dict[str, Any] | None = None,
        max_concurrent: int | None = None,
    ) -> list[TaskResult]:
        """Execute multiple actions in parallel with bounded concurrency.

        CONCURRENCY FIX (Dec 25, 2025): Added semaphore-based rate limiting
        to prevent resource exhaustion during batch execution.

        Args:
            actions: List of (action, params) tuples
            context: Shared context
            max_concurrent: Max concurrent tasks (default: config.max_workers)

        Returns:
            List of TaskResults
        """
        # Use config-based limit if not specified
        limit = max_concurrent or self.config.max_workers
        semaphore = asyncio.Semaphore(limit)

        async def execute_with_limit(action: str, params: dict[str, Any]) -> TaskResult:
            async with semaphore:
                return await self.execute(action, params, context)

        tasks = [execute_with_limit(action, params) for action, params in actions]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed TaskResults
        processed: list[TaskResult] = []
        for i, result in enumerate(results):
            if isinstance(result, BaseException):
                logger.error(f"Batch action {actions[i][0]} failed: {result}")
                processed.append(
                    TaskResult(  # type: ignore[call-arg]
                        success=False,
                        result={},
                        error=str(result),
                        latency=0.0,
                    )
                )
            else:
                processed.append(result)

        return processed

    def get_worker_count(self) -> int:
        """Get current worker count."""
        return len(self._workers)

    def get_available_count(self) -> int:
        """Get available worker count."""
        return sum(1 for w in self._workers if w.is_available)

    async def cleanup_workers(self) -> int:
        """Clean up retired/dead workers."""
        async with self._worker_lock:
            before = len(self._workers)

            # Retire workers that should retire
            for worker in self._workers:
                if worker.should_retire():
                    await worker.retire()

            # Remove dead workers
            self._workers = [w for w in self._workers if w.state.status.value != "dead"]

            # Ensure minimum
            self._ensure_min_workers()

            return before - len(self._workers)

    async def adapt_worker_population(self) -> int:
        """Dynamically scale worker population based on load.

        OPTIMIZED (Dec 27, 2025): Adaptive scaling based on queue depth and latency.
        - High load (all workers busy): Spawn more workers up to max
        - Low load (many idle): Let workers hibernate naturally
        - Latency spike: Proactive scaling

        Returns:
            Net change in worker count (positive = grew, negative = shrank)
        """
        async with self._worker_lock:
            before = len(self._workers)

            # Compute load metrics
            busy_workers = sum(1 for w in self._workers if w.state.current_tasks > 0)
            total_workers = len(self._workers)

            # High load: All workers busy or nearly busy
            utilization = busy_workers / max(total_workers, 1)

            if utilization > 0.8 and total_workers < self.config.max_workers:
                # Scale up: Add workers proportional to overload
                workers_needed = min(
                    2,  # Max 2 at a time to avoid explosion
                    self.config.max_workers - total_workers,
                )
                for _ in range(workers_needed):
                    worker = create_worker(
                        colony_idx=self.colony_idx,
                        config=self.config.worker_config,
                    )
                    worker._colony = self  # type: ignore[attr-defined]
                    self._workers.append(worker)

                logger.info(
                    f"📈 {self.colony_name}: Scaled up by {workers_needed} workers "
                    f"(utilization={utilization:.0%}, now={len(self._workers)})"
                )

            elif utilization < 0.2 and total_workers > self.config.min_workers:
                # Low load: Let excess workers hibernate (don't force kill)
                # The homeostasis loop will clean them up naturally
                logger.debug(
                    f"📉 {self.colony_name}: Low utilization ({utilization:.0%}), "
                    f"workers will hibernate naturally"
                )

            # Also scale based on latency if available
            if self.stats.avg_latency > 1.0 and total_workers < self.config.max_workers:
                # High latency indicates overload
                worker = create_worker(
                    colony_idx=self.colony_idx,
                    config=self.config.worker_config,
                )
                worker._colony = self  # type: ignore[attr-defined]
                self._workers.append(worker)
                logger.info(
                    f"📈 {self.colony_name}: Latency-triggered scale up "
                    f"(avg_latency={self.stats.avg_latency:.2f}s)"
                )

            return len(self._workers) - before

    async def ensure_critical_redundancy(self) -> list[str]:
        """Ensure critical capabilities have redundant workers.

        For MinimalColony, this ensures at least min_workers are available.
        Returns list[Any] of any newly created capabilities.

        Returns:
            List of capability names that were created for redundancy.
        """
        created: list[str] = []

        async with self._worker_lock:
            # Ensure we have minimum workers for basic redundancy
            initial_count = len(self._workers)
            self._ensure_min_workers()
            new_count = len(self._workers)

            if new_count > initial_count:
                created.append(f"{self.colony_name}:worker×{new_count - initial_count}")

        return created

    def get_stats(self) -> dict[str, Any]:
        """Get colony statistics."""
        return {
            "colony": self.colony_name,
            "colony_idx": self.colony_idx,
            "total_tasks": self.stats.total_tasks,
            "completed": self.stats.completed_tasks,
            "failed": self.stats.failed_tasks,
            "success_rate": self.stats.success_rate,
            "avg_latency": self.stats.avg_latency,
            "worker_count": self.get_worker_count(),
            "available_workers": self.get_available_count(),
            "age_seconds": time.time() - self.stats.created_at,
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_colony(
    colony_idx: int = 0,
    config: ColonyConfig | None = None,
) -> MinimalColony:
    """Create a minimal colony.

    Args:
        colony_idx: Colony index (0-6)
        config: Optional configuration

    Returns:
        Configured MinimalColony
    """
    return MinimalColony(colony_idx=colony_idx, config=config)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "DOMAIN_TO_S7",
    "ColonyConfig",
    "ColonyStats",
    "MinimalColony",
    "create_colony",
]
