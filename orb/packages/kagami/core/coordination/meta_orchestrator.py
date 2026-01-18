"""Meta-Orchestrator — Coordination of Coordinators.

GENERAL PURPOSE MULTI-INSTANCE COORDINATION:
=============================================
This module provides a general-purpose meta-orchestrator that can coordinate
ANY type of instances implementing the OrchestratableInstance protocol.

DESIGN PRINCIPLES:
==================
1. GENERAL: Not locked to any specific use case (colonies, agents, workers, etc.)
2. WELL-INTEGRATED: Uses existing stigmergy, receipts, and safety systems
3. PROTOCOL-BASED: Instances implement a simple protocol for coordination
4. STIGMERGIC: Learns from execution history to improve task decomposition
5. SAFE: Aggregates safety constraints across all instances (h(x) ≥ 0)

MATHEMATICAL FOUNDATION:
========================
Sedenion-inspired coordination: Just as sedenions extend octonions to 16D,
Meta extends the 8D Kagami (1 real + 7 colonies) to coordinate multiple
octonion instances. We don't implement full sedenion algebra (which has
zero divisors), but use the structural inspiration for coordination.

Meta h(x) = min(h₁(x), h₂(x), ..., hₙ(x), h_global(x))

Where:
- hᵢ(x) = safety of instance i
- h_global(x) = global coordination safety (no conflicts, no deadlocks)

USAGE:
======
```python

# Standard library imports
import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import (
    dataclass,
    field,
)
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Protocol,
    cast,
    runtime_checkable,
)

    MetaOrchestrator,
    OrchestratableInstance,
    create_meta_orchestrator,
)

# Any instance implementing OrchestratableInstance can be coordinated
orchestrator = create_meta_orchestrator()

# Register instances (colonies, agents, workers, services, etc.)
orchestrator.register_instance("forge", forge_instance)
orchestrator.register_instance("grove", grove_instance)

# Decompose and coordinate work
result = await orchestrator.coordinate(
    task="research and implement feature X",
    context={"priority": "high"},
)
```

Created: December 28, 2025
Author: Meta-Orchestrator Design (Beacon + Forge)
Status: Production Implementation
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# =============================================================================
# PROTOCOLS - General Instance Interface
# =============================================================================


@runtime_checkable
class OrchestratableInstance(Protocol):
    """Protocol for any instance that can be coordinated by MetaOrchestrator.

    This is intentionally minimal to maximize generality. Any system that can:
    1. Execute tasks
    2. Report health/safety
    3. Report status

    Can be coordinated by the meta-orchestrator.

    IMPLEMENTATIONS:
    ================
    - UnifiedOrganism (Kagami instance with 7 colonies)
    - MinimalColony (individual colony)
    - External service wrapper
    - Worker process
    - Agent instance
    - Any system with execute/health/status
    """

    @property
    def instance_id(self) -> str:
        """Unique identifier for this instance."""
        ...

    @property
    def instance_type(self) -> str:
        """Type of instance (e.g., 'organism', 'colony', 'worker', 'agent')."""
        ...

    async def execute(
        self,
        task: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a task and return results.

        Args:
            task: Task description or intent
            params: Task parameters
            context: Execution context

        Returns:
            Execution result with at minimum:
            - success: bool
            - result: Any
            - error: str | None (if failed)
        """
        ...

    def get_health(self) -> dict[str, Any]:
        """Get current health status.

        Returns:
            Health dict[str, Any] with at minimum:
            - h_x: float (safety value, 0-1)
            - status: str (healthy/degraded/unhealthy)
            - load: float (0-1, current load)
        """
        ...

    def get_capabilities(self) -> list[str]:
        """Get list[Any] of capabilities this instance supports.

        Returns:
            List of capability strings (e.g., ['research', 'build', 'test'])
        """
        ...


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class TaskPriority(Enum):
    """Task priority levels."""

    CRITICAL = 5
    HIGH = 4
    NORMAL = 3
    LOW = 2
    BACKGROUND = 1


class CoordinationMode(Enum):
    """Mode of coordination across instances."""

    SINGLE = "single"  # Single instance executes
    PARALLEL = "parallel"  # Multiple instances execute in parallel
    SEQUENTIAL = "sequential"  # Multiple instances execute in sequence
    PIPELINE = "pipeline"  # DAG execution with dependencies


@dataclass
class TaskNode:
    """Node in task decomposition DAG.

    Represents a single task that can be executed by an instance.
    """

    task_id: str
    description: str
    params: dict[str, Any] = field(default_factory=dict[str, Any])
    dependencies: list[str] = field(default_factory=list[Any])  # Task IDs this depends on
    assigned_instance: str | None = None
    required_capabilities: list[str] = field(default_factory=list[Any])
    priority: TaskPriority = TaskPriority.NORMAL
    status: str = "pending"  # pending, running, completed, failed
    result: dict[str, Any] | None = None
    started_at: float | None = None
    completed_at: float | None = None
    h_x_at_start: float | None = None  # Safety value when task started

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "description": self.description,
            "params": self.params,
            "dependencies": self.dependencies,
            "assigned_instance": self.assigned_instance,
            "required_capabilities": self.required_capabilities,
            "priority": self.priority.value,
            "status": self.status,
            "result": self.result,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "h_x_at_start": self.h_x_at_start,
        }


@dataclass
class TaskDAG:
    """Directed Acyclic Graph of tasks for coordination."""

    dag_id: str
    root_task: str  # Original task description
    nodes: dict[str, TaskNode] = field(default_factory=dict[str, Any])
    created_at: float = field(default_factory=time.time)
    mode: CoordinationMode = CoordinationMode.PIPELINE
    context: dict[str, Any] = field(default_factory=dict[str, Any])

    def add_task(
        self,
        description: str,
        params: dict[str, Any] | None = None,
        dependencies: list[str] | None = None,
        required_capabilities: list[str] | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> TaskNode:
        """Add a task to the DAG."""
        task_id = f"{self.dag_id}_{len(self.nodes)}"
        node = TaskNode(
            task_id=task_id,
            description=description,
            params=params or {},
            dependencies=dependencies or [],
            required_capabilities=required_capabilities or [],
            priority=priority,
        )
        self.nodes[task_id] = node
        return node

    def get_ready_tasks(self) -> list[TaskNode]:
        """Get tasks that are ready to execute (all dependencies satisfied)."""
        ready = []
        for node in self.nodes.values():
            if node.status != "pending":
                continue
            # Check all dependencies are completed
            deps_satisfied = all(
                self.nodes.get(dep, TaskNode(task_id="", description="")).status == "completed"
                for dep in node.dependencies
            )
            if deps_satisfied:
                ready.append(node)
        # Sort by priority
        ready.sort(key=lambda n: n.priority.value, reverse=True)
        return ready

    def is_complete(self) -> bool:
        """Check if all tasks are completed."""
        return all(n.status in ("completed", "failed") for n in self.nodes.values())

    def get_failed_tasks(self) -> list[TaskNode]:
        """Get failed tasks."""
        return [n for n in self.nodes.values() if n.status == "failed"]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dag_id": self.dag_id,
            "root_task": self.root_task,
            "mode": self.mode.value,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "created_at": self.created_at,
            "context": self.context,
            "is_complete": self.is_complete(),
            "progress": (
                f"{sum(1 for n in self.nodes.values() if n.status == 'completed')}"
                f"/{len(self.nodes)}"
            ),
        }


@dataclass
class StrategicMemory:
    """Persistent memory for task decomposition patterns.

    Learns optimal decomposition strategies from execution history.
    """

    # Task type → successful decomposition patterns
    decomposition_patterns: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: defaultdict(list[Any])
    )
    # Instance → capability → success rate
    instance_capabilities: dict[str, dict[str, float]] = field(
        default_factory=lambda: defaultdict(dict[str, Any])
    )
    # Global coordination statistics
    stats: dict[str, Any] = field(default_factory=dict[str, Any])
    # Last update time
    last_updated: float = field(default_factory=time.time)

    def record_success(
        self,
        task_type: str,
        decomposition: list[dict[str, Any]],
        instance_assignments: dict[str, str],
    ) -> None:
        """Record a successful decomposition pattern."""
        self.decomposition_patterns[task_type].append(
            {
                "decomposition": decomposition,
                "assignments": instance_assignments,
                "timestamp": time.time(),
            }
        )
        # Keep last 100 patterns per task type
        if len(self.decomposition_patterns[task_type]) > 100:
            self.decomposition_patterns[task_type] = self.decomposition_patterns[task_type][-100:]
        self.last_updated = time.time()

    def update_capability(
        self,
        instance_id: str,
        capability: str,
        success: bool,
    ) -> None:
        """Update capability success rate for an instance."""
        current = self.instance_capabilities[instance_id].get(capability, 0.5)
        # Exponential moving average
        alpha = 0.1
        new_rate = current * (1 - alpha) + (1.0 if success else 0.0) * alpha
        self.instance_capabilities[instance_id][capability] = new_rate
        self.last_updated = time.time()

    def get_best_decomposition(self, task_type: str) -> list[dict[str, Any]] | None:
        """Get best decomposition pattern for task type."""
        from typing import cast

        patterns = self.decomposition_patterns.get(task_type, [])
        if not patterns:
            return None
        # Return most recent successful pattern
        return cast(list[dict[str, Any]], patterns[-1]["decomposition"])

    def get_best_instance_for_capability(
        self, capability: str, available_instances: list[str]
    ) -> str | None:
        """Get best instance for a capability based on history."""
        best_instance = None
        best_rate = -1.0
        for instance_id in available_instances:
            rate = self.instance_capabilities.get(instance_id, {}).get(capability, 0.5)
            if rate > best_rate:
                best_rate = rate
                best_instance = instance_id
        return best_instance

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "decomposition_patterns": dict(self.decomposition_patterns),
            "instance_capabilities": dict(self.instance_capabilities),
            "stats": self.stats,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategicMemory:
        """Deserialize from dictionary."""
        memory = cls()
        memory.decomposition_patterns = defaultdict(
            list[Any], data.get("decomposition_patterns", {})
        )
        memory.instance_capabilities = defaultdict(
            dict[str, Any], data.get("instance_capabilities", {})
        )
        memory.stats = data.get("stats", {})
        memory.last_updated = data.get("last_updated", time.time())
        return memory


@dataclass
class CoordinationResult:
    """Result of meta-orchestration."""

    dag_id: str
    success: bool
    results: dict[str, Any]  # task_id → result
    failed_tasks: list[str]
    duration_seconds: float
    instances_used: list[str]
    meta_h_x: float  # Global safety value
    mode: CoordinationMode
    context: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "dag_id": self.dag_id,
            "success": self.success,
            "results": self.results,
            "failed_tasks": self.failed_tasks,
            "duration_seconds": self.duration_seconds,
            "instances_used": self.instances_used,
            "meta_h_x": self.meta_h_x,
            "mode": self.mode.value,
            "context": self.context,
        }


# =============================================================================
# TASK DECOMPOSER
# =============================================================================


class TaskDecomposer:
    """Decomposes complex tasks into executable subtasks.

    Uses strategic memory to learn optimal decomposition patterns.
    Falls back to heuristic decomposition for unknown task types.
    """

    def __init__(
        self,
        memory: StrategicMemory,
        available_capabilities: set[str] | None = None,
    ):
        """Initialize task decomposer.

        Args:
            memory: Strategic memory for learned patterns
            available_capabilities: Set of available capabilities
        """
        self.memory = memory
        self.available_capabilities = available_capabilities or set()

        # Heuristic patterns for common task types
        self._heuristic_patterns = {
            "research": [
                {"action": "explore", "capability": "research"},
                {"action": "analyze", "capability": "research"},
                {"action": "synthesize", "capability": "research"},
            ],
            "build": [
                {"action": "plan", "capability": "plan"},
                {"action": "implement", "capability": "build"},
                {"action": "test", "capability": "test"},
            ],
            "fix": [
                {"action": "diagnose", "capability": "debug"},
                {"action": "fix", "capability": "build"},
                {"action": "verify", "capability": "test"},
            ],
            "analyze": [
                {"action": "gather", "capability": "research"},
                {"action": "process", "capability": "build"},
                {"action": "report", "capability": "research"},
            ],
        }

    def extract_task_type(self, task: str) -> str:
        """Extract task type from task description."""
        task_lower = task.lower()

        # Order matters - more specific patterns first
        type_keywords = [
            ("test", ["test", "verify", "validate", "check", "audit"]),
            ("fix", ["fix", "repair", "debug", "patch", "resolve"]),
            ("research", ["research", "explore", "investigate", "learn", "study"]),
            ("plan", ["plan", "design", "architect", "organize", "structure"]),
            ("analyze", ["analyze", "examine", "review", "assess", "evaluate"]),
            ("build", ["build", "implement", "create", "code", "construct", "develop"]),
        ]

        for task_type, keywords in type_keywords:
            if any(kw in task_lower for kw in keywords):
                return task_type

        return "general"

    def decompose(
        self,
        task: str,
        params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> TaskDAG:
        """Decompose a task into a DAG of subtasks.

        Args:
            task: Task description
            params: Task parameters
            context: Execution context

        Returns:
            TaskDAG with decomposed subtasks
        """
        params = params or {}
        context = context or {}

        dag_id = f"dag_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        dag = TaskDAG(dag_id=dag_id, root_task=task, context=context)

        # Extract task type
        task_type = self.extract_task_type(task)

        # Try learned decomposition first
        learned = self.memory.get_best_decomposition(task_type)
        if learned:
            logger.debug(f"Using learned decomposition for task type: {task_type}")
            self._apply_learned_decomposition(dag, task, learned, params)
        else:
            # Fall back to heuristic decomposition
            logger.debug(f"Using heuristic decomposition for task type: {task_type}")
            self._apply_heuristic_decomposition(dag, task, task_type, params)

        return dag

    def _apply_learned_decomposition(
        self,
        dag: TaskDAG,
        task: str,
        pattern: list[dict[str, Any]],
        params: dict[str, Any],
    ) -> None:
        """Apply a learned decomposition pattern."""
        prev_task_id = None
        for step in pattern:
            node = dag.add_task(
                description=f"{step.get('action', 'execute')}: {task}",
                params={**params, "action": step.get("action")},
                dependencies=[prev_task_id] if prev_task_id else [],
                required_capabilities=[step.get("capability", "general")],
            )
            prev_task_id = node.task_id

    def _apply_heuristic_decomposition(
        self,
        dag: TaskDAG,
        task: str,
        task_type: str,
        params: dict[str, Any],
    ) -> None:
        """Apply heuristic decomposition based on task type."""
        pattern = self._heuristic_patterns.get(
            task_type,
            [{"action": "execute", "capability": "general"}],
        )

        prev_task_id = None
        for step in pattern:
            node = dag.add_task(
                description=f"{step.get('action', 'execute')}: {task}",
                params={**params, "action": step.get("action")},
                dependencies=[prev_task_id] if prev_task_id else [],
                required_capabilities=[step.get("capability", "general")],
            )
            prev_task_id = node.task_id


# =============================================================================
# INSTANCE ASSIGNER
# =============================================================================


class InstanceAssigner:
    """Assigns tasks to instances based on capabilities and load."""

    def __init__(
        self,
        memory: StrategicMemory,
    ):
        """Initialize instance assigner.

        Args:
            memory: Strategic memory for learned instance preferences
        """
        self.memory = memory

    def assign(
        self,
        task: TaskNode,
        instances: dict[str, OrchestratableInstance],
    ) -> str | None:
        """Assign a task to the best available instance.

        Args:
            task: Task to assign
            instances: Available instances

        Returns:
            Instance ID or None if no suitable instance
        """
        if not instances:
            return None

        # Filter instances by required capabilities
        capable_instances = []
        for instance_id, instance in instances.items():
            capabilities = instance.get_capabilities()
            if not task.required_capabilities or any(
                cap in capabilities for cap in task.required_capabilities
            ):
                capable_instances.append(instance_id)

        if not capable_instances:
            # Fallback: use any available instance
            capable_instances = list(instances.keys())

        # Get health/load for capable instances
        instance_scores: list[tuple[str, float]] = []
        for instance_id in capable_instances:
            instance = instances[instance_id]
            health = instance.get_health()

            # Score = capability_score * (1 - load) * h_x
            h_x = health.get("h_x", 1.0)
            load = health.get("load", 0.0)

            # Get capability score from memory
            cap_score = 0.5
            for cap in task.required_capabilities:
                cap_score = max(
                    cap_score,
                    self.memory.instance_capabilities.get(instance_id, {}).get(cap, 0.5),
                )

            score = cap_score * (1 - load) * h_x
            instance_scores.append((instance_id, score))

        # Sort by score descending
        instance_scores.sort(key=lambda x: x[1], reverse=True)

        if instance_scores:
            return instance_scores[0][0]
        return None


# =============================================================================
# META ORCHESTRATOR
# =============================================================================


class MetaOrchestrator:
    """Meta-level orchestrator for coordinating multiple instances.

    GENERAL DESIGN:
    ===============
    This orchestrator works with ANY instances implementing OrchestratableInstance.
    It is not tied to any specific use case (colonies, agents, workers, etc.).

    CAPABILITIES:
    =============
    1. Task decomposition into executable DAGs
    2. Instance assignment based on capabilities and load
    3. Parallel/sequential/pipeline execution
    4. Safety aggregation (meta h(x) = min of all instances)
    5. Strategic memory (learns from execution history)
    6. Persistence (saves/loads state)

    SAFETY INVARIANT:
    =================
    meta_h_x = min(h₁, h₂, ..., hₙ, h_global) ≥ 0 Always.

    If any instance violates safety, the entire coordination is blocked.
    """

    def __init__(
        self,
        memory_path: Path | None = None,
        safety_threshold: float = 0.0,
        enable_persistence: bool = True,
    ):
        """Initialize meta-orchestrator.

        Args:
            memory_path: Path for persistent memory (default: .cursor/meta_memory.json)
            safety_threshold: Minimum h(x) to allow execution (default: 0.0)
            enable_persistence: Enable persistent memory (default: True)
        """
        self.memory_path = memory_path or Path(".cursor/meta_memory.json")
        self.safety_threshold = safety_threshold
        self.enable_persistence = enable_persistence

        # Instance registry
        self._instances: dict[str, OrchestratableInstance] = {}

        # Strategic memory
        self._memory = StrategicMemory()

        # Task decomposer and assigner
        self._decomposer: TaskDecomposer | None = None
        self._assigner: InstanceAssigner | None = None

        # Active DAGs (in-progress coordinations)
        self._active_dags: dict[str, TaskDAG] = {}

        # Execution lock (prevent concurrent modifications)
        self._lock = asyncio.Lock()

        # Statistics
        self._stats = {
            "total_coordinations": 0,
            "successful_coordinations": 0,
            "failed_coordinations": 0,
            "total_tasks_executed": 0,
            "safety_blocks": 0,
        }

        # Load persistent memory
        if enable_persistence:
            self._load_memory()

        logger.info(
            f"✅ MetaOrchestrator initialized: "
            f"memory_path={self.memory_path}, "
            f"safety_threshold={safety_threshold}"
        )

    # =========================================================================
    # INSTANCE MANAGEMENT
    # =========================================================================

    def register_instance(
        self,
        instance_id: str,
        instance: OrchestratableInstance,
    ) -> None:
        """Register an instance for coordination.

        Args:
            instance_id: Unique identifier for instance
            instance: Instance implementing OrchestratableInstance protocol
        """
        self._instances[instance_id] = instance
        self._rebuild_decomposer()
        inst_type = getattr(instance, "instance_type", "unknown")
        logger.info(f"Registered instance: {instance_id} (type={inst_type})")

    def unregister_instance(self, instance_id: str) -> None:
        """Unregister an instance.

        Args:
            instance_id: Instance to unregister
        """
        if instance_id in self._instances:
            del self._instances[instance_id]
            self._rebuild_decomposer()
            logger.info(f"Unregistered instance: {instance_id}")

    def get_instance(self, instance_id: str) -> OrchestratableInstance | None:
        """Get instance by ID."""
        return self._instances.get(instance_id)

    def list_instances(self) -> list[str]:
        """List all registered instance IDs."""
        return list(self._instances.keys())

    def _rebuild_decomposer(self) -> None:
        """Rebuild decomposer with current capabilities."""
        all_capabilities: set[str] = set()
        for instance in self._instances.values():
            all_capabilities.update(instance.get_capabilities())

        self._decomposer = TaskDecomposer(
            memory=self._memory,
            available_capabilities=all_capabilities,
        )
        self._assigner = InstanceAssigner(memory=self._memory)

    # =========================================================================
    # SAFETY
    # =========================================================================

    def get_meta_h_x(self) -> float:
        """Get global safety value (minimum across all instances).

        meta_h_x = min(h₁, h₂, ..., hₙ)

        Returns:
            Minimum h(x) across all instances
        """
        if not self._instances:
            return 1.0  # No instances = safe

        h_values = []
        for instance in self._instances.values():
            health = instance.get_health()
            h_x = health.get("h_x", 1.0)
            h_values.append(h_x)

        return min(h_values) if h_values else 1.0

    def check_safety(self) -> tuple[bool, float]:
        """Check if coordination is safe to proceed.

        Returns:
            (is_safe, meta_h_x) tuple[Any, ...]
        """
        meta_h_x = self.get_meta_h_x()
        is_safe = meta_h_x >= self.safety_threshold
        return is_safe, meta_h_x

    # =========================================================================
    # COORDINATION
    # =========================================================================

    async def coordinate(
        self,
        task: str,
        params: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        mode: CoordinationMode | None = None,
        timeout: float | None = None,
    ) -> CoordinationResult:
        """Coordinate execution of a task across instances.

        This is the main entry point for meta-orchestration.

        Args:
            task: Task description
            params: Task parameters
            context: Execution context
            mode: Coordination mode (default: auto-detect)
            timeout: Timeout in seconds (default: None)

        Returns:
            CoordinationResult with execution results

        Raises:
            SafetyError: If meta h(x) < safety_threshold
        """
        params = params or {}
        context = context or {}
        start_time = time.time()

        async with self._lock:
            # Safety check
            is_safe, meta_h_x = self.check_safety()
            if not is_safe:
                self._stats["safety_blocks"] += 1
                logger.error(
                    f"🛑 SAFETY BLOCK: meta_h_x={meta_h_x:.3f} < threshold={self.safety_threshold}"
                )
                return CoordinationResult(
                    dag_id="blocked",
                    success=False,
                    results={},
                    failed_tasks=[],
                    duration_seconds=time.time() - start_time,
                    instances_used=[],
                    meta_h_x=meta_h_x,
                    mode=mode or CoordinationMode.SINGLE,
                    context={"error": "Safety threshold not met"},
                )

            self._stats["total_coordinations"] += 1

            # Decompose task
            if self._decomposer is None:
                self._rebuild_decomposer()

            dag = self._decomposer.decompose(task, params, context)  # type: ignore[union-attr]
            dag.mode = mode or self._infer_mode(dag)
            self._active_dags[dag.dag_id] = dag

            logger.info(
                f"📋 Coordinating: {task} "
                f"(dag_id={dag.dag_id}, mode={dag.mode.value}, "
                f"tasks={len(dag.nodes)}, meta_h_x={meta_h_x:.3f})"
            )

            # Execute DAG
            try:
                result = await self._execute_dag(dag, timeout)

                # Update strategic memory on success
                if result.success:
                    self._stats["successful_coordinations"] += 1
                    task_type = self._decomposer.extract_task_type(task)  # type: ignore[union-attr]
                    self._memory.record_success(
                        task_type=task_type,
                        decomposition=[
                            {
                                "action": n.description,
                                "capability": n.required_capabilities[0]
                                if n.required_capabilities
                                else "general",
                            }
                            for n in dag.nodes.values()
                        ],
                        instance_assignments={
                            n.task_id: n.assigned_instance or "" for n in dag.nodes.values()
                        },
                    )
                else:
                    self._stats["failed_coordinations"] += 1

                # Persist memory
                if self.enable_persistence:
                    self._save_memory()

                return result

            finally:
                # Cleanup active DAG
                if dag.dag_id in self._active_dags:
                    del self._active_dags[dag.dag_id]

    def _infer_mode(self, dag: TaskDAG) -> CoordinationMode:
        """Infer coordination mode from DAG structure."""
        if len(dag.nodes) == 1:
            return CoordinationMode.SINGLE

        # Check if tasks have dependencies (pipeline) or are independent (parallel)
        has_dependencies = any(n.dependencies for n in dag.nodes.values())
        if has_dependencies:
            return CoordinationMode.PIPELINE
        return CoordinationMode.PARALLEL

    async def _execute_dag(
        self,
        dag: TaskDAG,
        timeout: float | None,
    ) -> CoordinationResult:
        """Execute a task DAG."""
        start_time = time.time()
        results: dict[str, Any] = {}
        instances_used: set[str] = set()

        # Execute until complete or timeout
        while not dag.is_complete():
            # Check timeout
            if timeout and (time.time() - start_time) > timeout:
                logger.warning(f"DAG {dag.dag_id} timed out after {timeout}s")
                break

            # Get ready tasks
            ready_tasks = dag.get_ready_tasks()
            if not ready_tasks:
                # No ready tasks but not complete - deadlock or waiting
                await asyncio.sleep(0.01)
                continue

            # Execute ready tasks based on mode
            if dag.mode == CoordinationMode.SEQUENTIAL:
                # Execute one at a time
                for task_node in ready_tasks[:1]:
                    result = await self._execute_task(dag, task_node)
                    results[task_node.task_id] = result
                    if task_node.assigned_instance:
                        instances_used.add(task_node.assigned_instance)
            else:
                # Execute all ready tasks in parallel
                tasks_coros = [self._execute_task(dag, task_node) for task_node in ready_tasks]
                task_results = await asyncio.gather(*tasks_coros, return_exceptions=True)
                for task_node, result in zip(ready_tasks, task_results, strict=False):  # type: ignore[assignment]
                    if isinstance(result, BaseException):  # type: ignore[unreachable]
                        results[task_node.task_id] = {"success": False, "error": str(result)}  # type: ignore[unreachable]
                        task_node.status = "failed"
                    else:
                        results[task_node.task_id] = result
                    if task_node.assigned_instance:
                        instances_used.add(task_node.assigned_instance)

            self._stats["total_tasks_executed"] += len(ready_tasks)

        # Compute final result
        failed_tasks = [n.task_id for n in dag.get_failed_tasks()]
        success = len(failed_tasks) == 0 and dag.is_complete()

        return CoordinationResult(
            dag_id=dag.dag_id,
            success=success,
            results=results,
            failed_tasks=failed_tasks,
            duration_seconds=time.time() - start_time,
            instances_used=list(instances_used),
            meta_h_x=self.get_meta_h_x(),
            mode=dag.mode,
            context=dag.context,
        )

    async def _execute_task(
        self,
        dag: TaskDAG,
        task_node: TaskNode,
    ) -> dict[str, Any]:
        """Execute a single task on an assigned instance."""
        # Assign instance if not already assigned
        if not task_node.assigned_instance:
            if self._assigner is None:
                self._rebuild_decomposer()
            task_node.assigned_instance = self._assigner.assign(  # type: ignore[union-attr]
                task_node, self._instances
            )

        if not task_node.assigned_instance:
            task_node.status = "failed"
            return {"success": False, "error": "No suitable instance available"}

        instance = self._instances.get(task_node.assigned_instance)
        if not instance:
            task_node.status = "failed"
            return {"success": False, "error": f"Instance {task_node.assigned_instance} not found"}

        # Check instance safety before execution
        health = instance.get_health()
        h_x = health.get("h_x", 1.0)
        if h_x < self.safety_threshold:
            task_node.status = "failed"
            return {
                "success": False,
                "error": f"Instance {task_node.assigned_instance} h(x)={h_x:.3f} < threshold",
            }

        task_node.h_x_at_start = h_x
        task_node.status = "running"
        task_node.started_at = time.time()

        try:
            # Execute on instance
            result = await instance.execute(
                task=task_node.description,
                params=task_node.params,
                context=dag.context,
            )

            task_node.completed_at = time.time()
            success = result.get("success", False)
            task_node.status = "completed" if success else "failed"
            task_node.result = result

            # Update memory with capability success/failure
            for cap in task_node.required_capabilities:
                self._memory.update_capability(
                    task_node.assigned_instance,
                    cap,
                    success,
                )

            return result

        except Exception as e:
            task_node.completed_at = time.time()
            task_node.status = "failed"
            task_node.result = {"success": False, "error": str(e)}
            logger.error(f"Task {task_node.task_id} failed: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # PERSISTENCE
    # =========================================================================

    def _save_memory(self) -> None:
        """Save strategic memory to disk."""
        try:
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "memory": self._memory.to_dict(),
                "stats": self._stats,
                "version": "1.0.0",
            }
            with open(self.memory_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            logger.debug(f"Saved meta-orchestrator memory to {self.memory_path}")
        except Exception as e:
            logger.warning(f"Failed to save meta-orchestrator memory: {e}")

    def _load_memory(self) -> None:
        """Load strategic memory from disk."""
        try:
            if self.memory_path.exists():
                with open(self.memory_path) as f:
                    data = json.load(f)
                self._memory = StrategicMemory.from_dict(data.get("memory", {}))
                self._stats.update(data.get("stats", {}))
                logger.info(f"Loaded meta-orchestrator memory from {self.memory_path}")
        except Exception as e:
            logger.warning(f"Failed to load meta-orchestrator memory: {e}")

    # =========================================================================
    # STATISTICS & MONITORING
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "instances": {
                instance_id: {
                    "type": getattr(instance, "instance_type", "unknown"),
                    "health": instance.get_health(),
                    "capabilities": instance.get_capabilities(),
                }
                for instance_id, instance in self._instances.items()
            },
            "stats": self._stats,
            "meta_h_x": self.get_meta_h_x(),
            "active_dags": len(self._active_dags),
            "memory_patterns": len(self._memory.decomposition_patterns),
        }

    def get_active_coordinations(self) -> list[dict[str, Any]]:
        """Get list[Any] of active coordinations."""
        return [dag.to_dict() for dag in self._active_dags.values()]


# =============================================================================
# ORGANISM ADAPTER - Makes UnifiedOrganism implement OrchestratableInstance
# =============================================================================


class OrganismInstanceAdapter:
    """Adapts UnifiedOrganism to OrchestratableInstance protocol.

    This adapter allows existing UnifiedOrganism instances to be coordinated
    by the MetaOrchestrator without modifying their implementation.
    """

    def __init__(
        self,
        organism: Any,  # UnifiedOrganism
        instance_id: str | None = None,
    ):
        """Initialize adapter.

        Args:
            organism: UnifiedOrganism instance
            instance_id: Optional custom instance ID
        """
        self._organism = organism
        self._instance_id = instance_id or f"organism_{uuid.uuid4().hex[:8]}"

    @property
    def instance_id(self) -> str:
        """Unique identifier."""
        return self._instance_id

    @property
    def instance_type(self) -> str:
        """Instance type."""
        return "organism"

    async def execute(
        self,
        task: str,
        params: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute via organism's execute_intent."""
        try:
            result = await self._organism.execute_intent(
                intent=task,
                params=params,
                context=context,
            )
            return {
                "success": result.get("success", False),
                "result": result,
                "error": result.get("error"),
            }
        except Exception as e:
            return {"success": False, "result": None, "error": str(e)}

    def get_health(self) -> dict[str, Any]:
        """Get organism health."""
        try:
            health = self._organism.get_health()
            # Map organism health to protocol
            return {
                "h_x": health.get("health", 1.0),
                "status": health.get("status", "healthy"),
                "load": 1.0 - health.get("health", 1.0),  # Inverse of health as load
            }
        except Exception:
            return {"h_x": 0.5, "status": "unknown", "load": 0.5}

    def get_capabilities(self) -> list[str]:
        """Get organism capabilities (all 7 colony capabilities)."""
        return [
            "research",
            "build",
            "debug",
            "integrate",
            "plan",
            "explore",
            "test",
            # Standard capability aliases
            "create",
            "implement",
            "fix",
            "connect",
            "verify",
        ]


# =============================================================================
# FACTORY
# =============================================================================

_meta_orchestrator: MetaOrchestrator | None = None


def get_meta_orchestrator() -> MetaOrchestrator:
    """Get global meta-orchestrator instance."""
    global _meta_orchestrator
    if _meta_orchestrator is None:
        _meta_orchestrator = MetaOrchestrator()
    return _meta_orchestrator


def create_meta_orchestrator(
    memory_path: Path | str | None = None,
    safety_threshold: float = 0.0,
    enable_persistence: bool = True,
) -> MetaOrchestrator:
    """Create a new meta-orchestrator instance.

    Args:
        memory_path: Path for persistent memory
        safety_threshold: Minimum h(x) for execution
        enable_persistence: Enable persistent memory

    Returns:
        Configured MetaOrchestrator
    """
    return MetaOrchestrator(
        memory_path=Path(memory_path) if memory_path else None,
        safety_threshold=safety_threshold,
        enable_persistence=enable_persistence,
    )


def reset_meta_orchestrator() -> None:
    """Reset global meta-orchestrator (for testing)."""
    global _meta_orchestrator
    _meta_orchestrator = None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CoordinationMode",
    "CoordinationResult",
    "InstanceAssigner",
    "MetaOrchestrator",
    "OrchestratableInstance",
    "OrganismInstanceAdapter",
    "StrategicMemory",
    "TaskDAG",
    "TaskDecomposer",
    "TaskNode",
    "TaskPriority",
    "create_meta_orchestrator",
    "get_meta_orchestrator",
    "reset_meta_orchestrator",
]
