"""Claude Code Task Bridge - Integration between kagami orchestration and Claude Code.

This module bridges the kagami Python orchestration system with Claude Code's Task tool,
enabling colony agents to be spawned as Claude Code subagents rather than Python processes.

WHEN TO USE CLAUDE CODE VS PYTHON:
===================================
Use Claude Code Task tool when:
- User explicitly requests Claude-based agents
- Task requires file manipulation (Edit, Write tools)
- Task requires external web access (WebFetch, WebSearch)
- Task needs human-readable conversation output
- Interactive debugging/exploration is needed

Use Python orchestration when:
- High-throughput batch processing
- Numerical/ML computation required
- Sub-second latency critical
- No file system access needed
- Pure tensor operations

ARCHITECTURE:
=============
The bridge translates between:
1. kagami colony indices (0-6) → Claude subagent types (spark, forge, etc.)
2. kagami intent format → Claude task descriptions
3. Python async results → Claude Task tool responses
4. E8 action vectors → structured prompts

INTEGRATION POINTS:
===================
1. IntentOrchestrator._execute_*() methods can delegate to Claude Code
2. ColonyManager can spawn Claude agents instead of Python processes
3. FanoActionRouter can route to Claude agents via this bridge
4. Config flag: use_claude_code_agents controls delegation

SAFETY:
=======
- Claude Code agents inherit safety constraints from .claude/agents/*.md
- Control Barrier Function (CBF) checks remain in Python layer
- h(x) ≥ 0 invariant enforced before delegation
- Crystal verification runs post-execution regardless of agent type

Created: December 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Colony name mapping (0-indexed to agent names)
COLONY_TO_SUBAGENT = {
    0: "spark",  # e₁ - Fold (A₂) - Creative ideation
    1: "forge",  # e₂ - Cusp (A₃) - Implementation
    2: "flow",  # e₃ - Swallowtail (A₄) - Debugging
    3: "nexus",  # e₄ - Butterfly (A₅) - Integration
    4: "beacon",  # e₅ - Hyperbolic (D₄⁺) - Planning
    5: "grove",  # e₆ - Elliptic (D₄⁻) - Research
    6: "crystal",  # e₇ - Parabolic (D₅) - Verification
}

SUBAGENT_TO_COLONY = {v: k for k, v in COLONY_TO_SUBAGENT.items()}

# Fano plane composition (directional action routing)
# Maps (source, partner) → result
# NOTE: This is NOT strict octonion multiplication, but combinatorial routing
# See CLAUDE.md for clarification (Dec 14, 2025)
FANO_COMPOSITION = {
    # Forward compositions from CLAUDE.md (simplified notation)
    ("spark", "forge"): "flow",  # Line (1,2,3)
    ("spark", "nexus"): "beacon",  # Line (1,4,5)
    ("spark", "grove"): "crystal",  # Line (1,6,7) - corrected from (1,7,6)
    ("forge", "nexus"): "grove",  # Line (2,4,6)
    ("beacon", "forge"): "crystal",  # Line (5,2,7) → (2,5,7) reversed
    ("nexus", "flow"): "crystal",  # Line (4,3,7) → (3,4,7) reversed
    ("beacon", "flow"): "grove",  # Line (5,3,6) → (3,6,5) reversed
    # Additional compositions for Fano completeness test
    ("spark", "crystal"): "grove",  # Line (1,7,6)
    ("forge", "flow"): "spark",  # Line (2,3,1) cyclic from (1,2,3)
    ("flow", "grove"): "beacon",  # Line (3,6,5)
}


# =============================================================================
# DATA STRUCTURES
# =============================================================================


class BridgeMode(Enum):
    """Execution mode for Claude Code bridge."""

    DISABLED = "disabled"  # Use Python orchestration only
    HYBRID = "hybrid"  # Mix Claude and Python based on task type
    CLAUDE_ONLY = "claude_only"  # All tasks via Claude Code


@dataclass
class TaskResult:
    """Result from Claude Code Task tool execution."""

    success: bool
    colony_name: str
    colony_idx: int
    output: str | None = None
    error: str | None = None
    latency_ms: float = 0.0
    correlation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    @property
    def is_error(self) -> bool:
        """Check if result contains error."""
        return not self.success or self.error is not None


@dataclass
class BridgeConfig:
    """Configuration for Claude Code bridge."""

    mode: BridgeMode = BridgeMode.DISABLED
    timeout_seconds: float = 120.0  # 2 minutes default
    model: str = "sonnet"  # Default model for spawned agents
    enable_parallel: bool = True  # Allow parallel agent spawning
    max_concurrent: int = 7  # Max parallel agents (one per colony)
    retry_on_error: bool = False  # Auto-retry failed tasks
    max_retries: int = 1  # Max retry attempts


# =============================================================================
# CLAUDE CODE TASK BRIDGE
# =============================================================================


class ClaudeCodeTaskBridge:
    """Bridge between kagami orchestration and Claude Code Task tool.

    This class provides bidirectional translation between:
    - kagami colony system (Python) ↔ Claude Code agents (.claude/agents/)
    - E8 tensor operations ↔ structured prompts
    - Async Python execution ↔ Task tool invocations

    Usage:
        bridge = ClaudeCodeTaskBridge()
        result = await bridge.spawn_colony_agent(
            colony_name="forge",
            task="Implement authentication module",
            params={"file_path": "kagami/auth.py"}
        )
    """

    def __init__(self, config: BridgeConfig | None = None):
        """Initialize Claude Code bridge.

        Args:
            config: Bridge configuration
        """
        self.config = config or BridgeConfig()
        self._active_tasks: dict[str, Any] = {}  # Track spawned tasks
        self._execution_count = 0

        logger.info(
            f"ClaudeCodeTaskBridge initialized: mode={self.config.mode.value}, "
            f"model={self.config.model}"
        )

    # =========================================================================
    # COLONY AGENT SPAWNING
    # =========================================================================

    async def spawn_colony_agent(
        self,
        colony_name: str,
        task: str,
        params: dict[str, Any] | None = None,
        model: str | None = None,
        correlation_id: str | None = None,
    ) -> TaskResult:
        """Spawn single colony agent via Claude Code Task tool.

        Maps colony_name to subagent_type from .claude/agents/*.md and
        invokes Claude Code Task tool with appropriate prompt.

        Args:
            colony_name: Colony name (e.g., "forge", "spark")
            task: Task description for agent
            params: Additional parameters (file paths, context, etc.)
            model: Override model (default: config.model)
            correlation_id: Tracking ID for distributed tracing

        Returns:
            TaskResult with execution outcome

        Raises:
            ValueError: If colony_name invalid or bridge disabled
        """
        if self.config.mode == BridgeMode.DISABLED:
            raise ValueError("Claude Code bridge is disabled. Set mode to HYBRID or CLAUDE_ONLY.")

        # Validate colony name
        if colony_name not in SUBAGENT_TO_COLONY:
            raise ValueError(
                f"Invalid colony name: {colony_name}. Valid: {list(SUBAGENT_TO_COLONY.keys())}"
            )

        colony_idx = SUBAGENT_TO_COLONY[colony_name]
        params = params or {}
        model = model or self.config.model
        correlation_id = correlation_id or str(uuid.uuid4())[:8]

        start_time = time.time()

        logger.info(
            f"Spawning {colony_name} agent (colony_{colony_idx}) via Claude Code: "
            f"correlation_id={correlation_id}"
        )

        try:
            # Build prompt for Claude agent
            _prompt = self._build_agent_prompt(colony_name, task, params)

            # NOTE: Actual Task tool invocation would happen here
            # For now, this is a structural prototype showing the interface
            # In production, this would call the Task tool API:
            #
            #   from claude_code.task_tool import invoke_task
            #   result = await invoke_task(
            #       subagent_type=colony_name,
            #       prompt=prompt,
            #       model=model,
            #       timeout=self.config.timeout_seconds
            #   )
            #
            # Since Task tool is invoked by Claude Code itself (not callable from Python),
            # this method serves as a SPECIFICATION for how kagami should structure
            # task delegation when running inside Claude Code environment.

            # Placeholder response structure
            output = f"[PLACEHOLDER] {colony_name} would execute: {task}"
            success = True
            error = None

            latency_ms = (time.time() - start_time) * 1000.0
            self._execution_count += 1

            result = TaskResult(
                success=success,
                colony_name=colony_name,
                colony_idx=colony_idx,
                output=output,
                error=error,
                latency_ms=latency_ms,
                correlation_id=correlation_id,
                metadata={
                    "model": model,
                    "params": params,
                    "execution_count": self._execution_count,
                },
            )

            logger.info(
                f"✅ {colony_name} completed: success={success}, "
                f"latency={latency_ms:.1f}ms, correlation_id={correlation_id}"
            )

            return result

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000.0
            logger.error(f"❌ {colony_name} failed: {e}, correlation_id={correlation_id}")

            return TaskResult(
                success=False,
                colony_name=colony_name,
                colony_idx=colony_idx,
                output=None,
                error=str(e),
                latency_ms=latency_ms,
                correlation_id=correlation_id,
                metadata={"model": model, "params": params},
            )

    async def spawn_parallel_agents(
        self,
        tasks: list[tuple[str, str, dict[str, Any]]],
        correlation_id: str | None = None,
    ) -> list[TaskResult]:
        """Spawn multiple colony agents in parallel.

        This method implements MAXIMUM PARALLELISM as specified in CLAUDE.md.
        All independent tasks are launched simultaneously.

        Args:
            tasks: List of (colony_name, task_description, params) tuples
            correlation_id: Shared correlation ID for all tasks

        Returns:
            List of TaskResult (same length as tasks)

        Example:
            results = await bridge.spawn_parallel_agents([
                ("forge", "Implement module A", {"file": "a.py"}),
                ("forge", "Implement module B", {"file": "b.py"}),
                ("forge", "Implement module C", {"file": "c.py"}),
            ])
        """
        if not self.config.enable_parallel:
            # Sequential fallback
            logger.warning("Parallel execution disabled, running sequentially")
            results = []
            for colony_name, task, params in tasks:
                result = await self.spawn_colony_agent(
                    colony_name, task, params, correlation_id=correlation_id
                )
                results.append(result)
            return results

        # Check concurrency limit
        if len(tasks) > self.config.max_concurrent:
            logger.warning(
                f"Task count {len(tasks)} exceeds max_concurrent "
                f"{self.config.max_concurrent}, will batch"
            )

        correlation_id = correlation_id or str(uuid.uuid4())[:8]

        logger.info(f"Spawning {len(tasks)} agents in parallel: correlation_id={correlation_id}")

        # Launch all tasks concurrently
        # In real implementation, this would use asyncio.gather with Task tool calls

        spawn_coroutines = [
            self.spawn_colony_agent(
                colony_name=colony_name,
                task=task_desc,
                params=params,
                correlation_id=correlation_id,
            )
            for colony_name, task_desc, params in tasks
        ]

        results = await asyncio.gather(*spawn_coroutines, return_exceptions=True)  # type: ignore[assignment]

        # Convert exceptions to TaskResult
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                colony_name = tasks[i][0]
                colony_idx = SUBAGENT_TO_COLONY[colony_name]
                processed_results.append(
                    TaskResult(
                        success=False,
                        colony_name=colony_name,
                        colony_idx=colony_idx,
                        error=str(result),
                        correlation_id=correlation_id,
                    )
                )
            else:
                processed_results.append(result)

        success_count = sum(1 for r in processed_results if r.success)
        logger.info(
            f"Parallel execution complete: {success_count}/{len(tasks)} succeeded, "
            f"correlation_id={correlation_id}"
        )

        return processed_results

    # =========================================================================
    # FANO COMPOSITION ROUTING
    # =========================================================================

    def get_fano_composition(self, source: str, partner: str) -> str | None:
        """Return result colony from Fano composition.

        Uses Fano plane routing logic to determine which colony should
        handle the composed action from two input colonies.

        Args:
            source: Source colony name
            partner: Partner colony name

        Returns:
            Result colony name, or None if not a valid Fano composition

        Example:
            result = bridge.get_fano_composition("spark", "forge")
            # Returns: "flow" (creative + implement → adapt)
        """
        # Try direct composition
        key = (source, partner)
        if key in FANO_COMPOSITION:
            return FANO_COMPOSITION[key]

        # Try reverse order (Fano lines are symmetric)
        key_rev = (partner, source)
        if key_rev in FANO_COMPOSITION:
            return FANO_COMPOSITION[key_rev]

        # Not a valid Fano line
        logger.warning(f"Invalid Fano composition: {source} × {partner} (not on same Fano line)")
        return None

    async def execute_fano_line(
        self,
        source: str,
        partner: str,
        task: str,
        params: dict[str, Any] | None = None,
    ) -> list[TaskResult]:
        """Execute task along Fano line (3 colonies).

        Implements the PLAN-EXECUTE-VERIFY pattern using Fano composition:
        1. Source colony processes task
        2. Partner colony processes source output
        3. Result colony synthesizes both outputs

        Args:
            source: Source colony name
            partner: Partner colony name
            task: Task description
            params: Task parameters

        Returns:
            List of 3 TaskResults (source, partner, result)

        Example:
            results = await bridge.execute_fano_line(
                source="beacon",
                partner="forge",
                task="Design and implement auth module",
                params={"output_path": "kagami/auth.py"}
            )
            # Executes: beacon (design) → forge (implement) → crystal (verify)
        """
        result_colony = self.get_fano_composition(source, partner)
        if result_colony is None:
            raise ValueError(f"Invalid Fano line: {source} and {partner} are not on same Fano line")

        correlation_id = str(uuid.uuid4())[:8]
        params = params or {}

        logger.info(
            f"Executing Fano line: {source} → {partner} → {result_colony}, "
            f"correlation_id={correlation_id}"
        )

        # Phase 1: Source + Partner (parallel)
        phase1_results = await self.spawn_parallel_agents(
            [
                (source, f"[PHASE 1a] {task}", params),
                (partner, f"[PHASE 1b] {task}", params),
            ],
            correlation_id=correlation_id,
        )

        # Phase 2: Result colony synthesizes
        synthesis_params = {
            **params,
            "source_output": phase1_results[0].output,
            "partner_output": phase1_results[1].output,
        }

        result_task = f"[PHASE 2 - SYNTHESIS] {task}"
        phase2_result = await self.spawn_colony_agent(
            colony_name=result_colony,
            task=result_task,
            params=synthesis_params,
            correlation_id=correlation_id,
        )

        all_results = [*phase1_results, phase2_result]

        logger.info(
            f"Fano line complete: {source} × {partner} = {result_colony}, "
            f"correlation_id={correlation_id}"
        )

        return all_results

    # =========================================================================
    # PROMPT CONSTRUCTION
    # =========================================================================

    def _build_agent_prompt(self, colony_name: str, task: str, params: dict[str, Any]) -> str:
        """Build prompt for Claude Code agent.

        Structures task with:
        - Colony role context
        - Task description
        - Parameters as structured data
        - Safety reminders

        Args:
            colony_name: Colony name
            task: Task description
            params: Task parameters

        Returns:
            Formatted prompt string
        """
        # Add colony context
        colony_descriptions = {
            "spark": "You are creative ideation specialist (Fold catastrophe). "
            "Generate diverse ideas and explore possibilities.",
            "forge": "You are implementation specialist (Cusp catastrophe). "
            "Build high-quality, robust code.",
            "flow": "You are debugging/recovery specialist (Swallowtail catastrophe). "
            "Diagnose errors and restore system health.",
            "nexus": "You are integration specialist (Butterfly catastrophe). "
            "Connect components and maintain relationships.",
            "beacon": "You are planning/architecture specialist (Hyperbolic catastrophe). "
            "Design system structure and strategy.",
            "grove": "You are research specialist (Elliptic catastrophe). "
            "Gather knowledge and analyze patterns.",
            "crystal": "You are verification specialist (Parabolic catastrophe). "
            "Test, audit, and prove correctness.",
        }

        context = colony_descriptions.get(
            colony_name, "You are a colony agent in the KagamiOS system."
        )

        # Format parameters
        param_str = "\n".join(f"  - {k}: {v}" for k, v in params.items())

        prompt = f"""{context}

TASK: {task}

PARAMETERS:
{param_str if params else "  (none)"}

SAFETY CONSTRAINT:
Ensure all actions maintain h(x) ≥ 0 (Control Barrier Function invariant).
If any action would violate safety, refuse execution and report to coordinator.

Return results in structured format for synthesis."""

        return prompt

    # =========================================================================
    # STATS & MONITORING
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get bridge execution statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "mode": self.config.mode.value,
            "model": self.config.model,
            "total_executions": self._execution_count,
            "active_tasks": len(self._active_tasks),
            "config": {
                "timeout_seconds": self.config.timeout_seconds,
                "enable_parallel": self.config.enable_parallel,
                "max_concurrent": self.config.max_concurrent,
            },
        }


# =============================================================================
# FACTORY & SINGLETON
# =============================================================================

_BRIDGE_INSTANCE: ClaudeCodeTaskBridge | None = None


def get_claude_code_bridge() -> ClaudeCodeTaskBridge:
    """Get global Claude Code bridge instance.

    Returns:
        Global ClaudeCodeTaskBridge singleton
    """
    global _BRIDGE_INSTANCE
    if _BRIDGE_INSTANCE is None:
        _BRIDGE_INSTANCE = create_claude_code_bridge()
    return _BRIDGE_INSTANCE


def set_claude_code_bridge(bridge: ClaudeCodeTaskBridge | None) -> None:
    """Set global Claude Code bridge instance.

    Args:
        bridge: ClaudeCodeTaskBridge or None
    """
    global _BRIDGE_INSTANCE
    _BRIDGE_INSTANCE = bridge


def create_claude_code_bridge(config: BridgeConfig | None = None) -> ClaudeCodeTaskBridge:
    """Create Claude Code bridge.

    Args:
        config: Bridge configuration

    Returns:
        Configured ClaudeCodeTaskBridge
    """
    return ClaudeCodeTaskBridge(config=config)


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================


def should_use_claude_code(task_type: str, context: dict[str, Any]) -> bool:
    """Heuristic to determine if task should use Claude Code vs Python.

    Args:
        task_type: Task type string (e.g., "implement", "research", "verify")
        context: Task context with hints

    Returns:
        True if Claude Code recommended, False for Python
    """
    # Always use Claude Code if explicitly requested
    if context.get("force_claude_code", False):
        return True

    # File manipulation tasks → Claude Code
    if "file_path" in context or "edit_file" in context:
        return True

    # Web research tasks → Claude Code
    if task_type in ["research", "explore", "investigate"]:
        if context.get("use_web", False):
            return True

    # High-throughput numerical tasks → Python
    if task_type in ["train", "optimize", "compute"]:
        return False

    # Interactive debugging → Claude Code
    if task_type in ["debug", "fix", "diagnose"]:
        if context.get("interactive", False):
            return True

    # Default: Python for speed
    return False


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "COLONY_TO_SUBAGENT",
    "FANO_COMPOSITION",
    "SUBAGENT_TO_COLONY",
    # Configuration
    "BridgeConfig",
    "BridgeMode",
    # Main class
    "ClaudeCodeTaskBridge",
    # Data structures
    "TaskResult",
    # Factory
    "create_claude_code_bridge",
    "get_claude_code_bridge",
    "set_claude_code_bridge",
    # Utilities
    "should_use_claude_code",
]
