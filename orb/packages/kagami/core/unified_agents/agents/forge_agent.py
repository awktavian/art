"""Forge Agent - The Builder (Cusp catastrophe, e₂).

IDENTITY: The Builder
=====================
Forge is the perfectionist builder. Quality over speed. Won't ship until it's right.
Methodical, detail-oriented, focused on craftsmanship. Gets visibly irritated
when someone suggests shipping something broken.

CATASTROPHE: Cusp (A₃)
=======================
V(x; a, b) = x⁴/4 + ax²/2 + bx
∇V = x³ + ax + b

Bistable decision with hysteresis:
- Two stable states: "quick build" vs "perfect build"
- Once committed to an approach, hard to switch
- Control parameters determine which attractor dominates

VOICE:
======
Blunt, practical, impatient with abstraction. Short sentences. Often sounds annoyed.
"Does it work? No? Then we're not done."
"Show me the code."
"Stop talking about it and build it."

STRENGTH:
=========
Perfectionism ensures quality. Code that works. Clean implementations.

FLAW:
=====
Perfectionism becomes paralysis. Stuck polishing when should ship.
Hard to switch approaches once committed (hysteresis).

Created: December 14, 2025
"""

from __future__ import annotations

import logging
from typing import Any

import torch

from kagami.core.unified_agents.agents.base_colony_agent import (
    AgentResult,
    BaseColonyAgent,
)
from kagami.core.unified_agents.catastrophe_kernels import CuspKernel

logger = logging.getLogger(__name__)


# =============================================================================
# FORGE AGENT
# =============================================================================


class ForgeAgent(BaseColonyAgent):
    """Forge (e₂) - The Builder.

    PERSONA:
    ========
    Perfectionist, quality-focused, methodical.
    Blunt, impatient with hand-waving, wants things to WORK.

    CATASTROPHE DYNAMICS:
    ====================
    Cusp (A₃) - Bistable with hysteresis
    Two modes:
    - "Perfect build": High quality, slow (default)
    - "Quick build": Fast iteration, lower quality (under pressure)

    Once committed to a mode, hard to switch.

    DOMAIN:
    =======
    - Implementation
    - Building systems
    - Code construction
    - Execution
    - Quality assurance

    TOOLS:
    ======
    - code: Write/edit code
    - build: Compile/build artifacts
    - implement: Implement features
    - refactor: Improve code quality
    - execute: Run code/scripts
    """

    # Mode-specific build configurations (shared across sync/async paths)
    MODE_CONFIGS: dict[str, dict[str, Any]] = {
        "perfect": {
            "base_quality": 0.9,
            "approach": "Thorough implementation with comprehensive testing",
            "message": "Built right. Every edge case handled. Won't break.",
        },
        "quick": {
            "base_quality": 0.7,
            "approach": "Fast iteration, ship to learn",
            "message": "It works. Not perfect. We'll fix it as we learn.",
        },
        "balanced": {
            "base_quality": 0.8,
            "approach": "Pragmatic balance of quality and speed",
            "message": "Good enough to ship, solid enough to maintain.",
        },
    }

    def __init__(self, state_dim: int = 256):
        """Initialize Forge agent (e₂, Cusp)."""
        super().__init__(colony_idx=1, state_dim=state_dim)

        # Forge metadata
        self.catastrophe_type = "cusp"  # A₃ cusp catastrophe

        # Cusp kernel for dual-process decision-making
        self.kernel = CuspKernel(state_dim=state_dim)

        # Cusp state tracking
        self.cusp_position = 0.5  # Position on cusp manifold [0, 1]
        self.build_mode = "perfect"  # "perfect" | "quick" | "balanced"
        self.commitment_strength = 0.5  # Hysteresis strength [0, 1]

        # Performance tracking
        self.builds_completed = 0
        self.builds_failed = 0
        self.avg_quality_score = 0.8
        self.consecutive_failures = 0

        # Escalation thresholds
        self.max_failures_before_escalation = 3
        self.quality_threshold = 0.7

    def get_system_prompt(self) -> str:
        """Return Forge's system prompt from canonical source."""
        from kagami.core.prompts.colonies import FORGE

        return FORGE.system_prompt

    def get_available_tools(self) -> list[str]:
        """Return Forge's implementation and building tools."""
        return [
            "code",  # Write/edit code
            "build",  # Compile/build artifacts
            "implement",  # Implement features
            "construct",  # Construct systems
            "execute",  # Run code/scripts
            "refactor",  # Improve code quality
            "optimize",  # Performance optimization
            "integrate",  # Wire components
            "test_build",  # Test build process
        ]

    def process_with_catastrophe(
        self,
        task: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Process implementation task with Cusp bistable dynamics.

        CUSP LOGIC:
        ===========
        Determine build mode based on context:
        - quality_demand: high → "perfect" mode
        - time_pressure: high → "quick" mode
        - Default: "balanced"

        Hysteresis: Once in a mode, need strong pressure to switch.

        Args:
            task: Task description (e.g., "implement authentication module")
            context: Execution context with optional:
                - quality_demand: float [0, 1] (0=low, 1=high)
                - time_pressure: float [0, 1] (0=low, 1=high)
                - quality_threshold: float [0, 1]
                - k_value: int (metacognition depth)

        Returns:
            AgentResult with implementation output
        """
        logger.info(f"Forge building: {task}")

        # Extract context parameters
        quality_demand = context.get("quality_demand", 0.7)  # Default: high quality
        time_pressure = context.get("time_pressure", 0.3)  # Default: low pressure
        quality_threshold = context.get("quality_threshold", self.quality_threshold)

        # Update cusp state (determine build mode)
        self._update_cusp_state(quality_demand, time_pressure)

        logger.debug(
            f"Forge mode: {self.build_mode}, position={self.cusp_position:.3f}, "
            f"commitment={self.commitment_strength:.3f}"
        )

        # Execute REAL build with tools integration and CBF safety checks
        output = self._simulate_build(task, self.build_mode, context)

        # Quality check
        quality_score = output.get("quality_score", 0.0)
        success = quality_score >= quality_threshold

        if not success:
            self.builds_failed += 1
            self.consecutive_failures += 1
            logger.warning(
                f"Build failed quality check: {quality_score:.3f} < {quality_threshold:.3f}"
            )
        else:
            self.builds_completed += 1
            self.consecutive_failures = 0

            # Update average quality (EMA)
            alpha = 0.1
            self.avg_quality_score = alpha * quality_score + (1 - alpha) * self.avg_quality_score

        # Create S⁷ embedding (Forge is e₂, index 1)
        s7_embedding = torch.zeros(7)
        s7_embedding[1] = 1.0  # Forge's unit vector

        # Check for paralysis (stuck in perfect mode with low progress)
        paralysis_detected = (
            self.build_mode == "perfect"
            and self.commitment_strength > 0.8
            and output.get("build_time", 0) > 10.0  # Arbitrary threshold
        )

        # Check for safety issues
        safety_issue = output.get("safety_warning") is not None and not output.get("safety_checked")

        # Determine escalation target based on issue type (Fano line: Forge × Partner = Result)
        should_escalate = False
        escalation_target = None

        if safety_issue:
            # Safety issues → Crystal for verification (Forge × Beacon = Crystal)
            should_escalate = True
            escalation_target = "crystal"
            logger.warning("Forge escalating to Crystal: safety verification needed")
        elif self.consecutive_failures >= self.max_failures_before_escalation:
            # Repeated failures → Flow for debugging (Spark × Forge = Flow)
            should_escalate = True
            escalation_target = "flow"
            logger.warning(
                f"Forge escalating to Flow: {self.consecutive_failures} consecutive failures"
            )
        elif paralysis_detected:
            # Paralysis → Flow for intervention
            should_escalate = True
            escalation_target = "flow"
            logger.warning("Forge stuck in perfectionism paralysis, escalating to Flow")

        return AgentResult(
            success=success,
            output=output,
            s7_embedding=s7_embedding,
            should_escalate=should_escalate,
            escalation_target=escalation_target,
            metadata={
                "build_mode": self.build_mode,
                "cusp_position": self.cusp_position,
                "commitment_strength": self.commitment_strength,
                "quality_score": quality_score,
                "builds_completed": self.builds_completed,
                "builds_failed": self.builds_failed,
                "consecutive_failures": self.consecutive_failures,
                "catastrophe_type": "cusp",
                "paralysis_detected": paralysis_detected,
                "safety_issue": safety_issue,
                "cbf_available": output.get("cbf_available", False),
            },
        )

    def _update_cusp_state(
        self,
        quality_demand: float,
        time_pressure: float,
    ) -> None:
        """Update cusp bifurcation state.

        CUSP DYNAMICS (CORRECTED):
        ==========================
        Standard cusp potential: V(x) = x⁴/4 - ax²/2 + bx
        Gradient: ∇V = x³ - ax + b

        Control parameters:
        - a = quality_demand - time_pressure: Splitting factor (creates bistability)
        - b = quality_demand - time_pressure: Normal factor (asymmetry bias)

        When a > 0, two stable attractors exist:
        - x > 0 → "perfect" mode (quality dominates)
        - x < 0 → "quick" mode (pressure dominates)

        Position x:
        - x > 0.6: "Perfect build" attractor
        - x < 0.4: "Quick build" attractor
        - 0.4 ≤ x ≤ 0.6: "Balanced" mode

        Hysteresis: Need strong control change to switch modes.

        Args:
            quality_demand: Quality requirement [0, 1]
            time_pressure: Time urgency [0, 1]
        """
        # Map to control parameters for standard cusp V = x⁴/4 - ax²/2 + bx
        # a (splitting): Controls bistability strength
        # b (normal): Controls which attractor is favored
        a = 0.5 + abs(quality_demand - time_pressure)  # Always > 0 for bistability
        b = quality_demand - time_pressure  # Positive → perfect, Negative → quick

        # Normalize x to [-1, 1] for gradient computation
        x_norm = 2 * self.cusp_position - 1  # [0,1] → [-1,1]

        # Compute gradient: ∇V = x³ - ax + b (note: MINUS a, standard cusp form)
        gradient = x_norm**3 - a * x_norm + b

        # Gradient descent step (small to allow hysteresis)
        step_size = 0.05
        x_norm_new = x_norm - step_size * gradient

        # Clamp and convert back to [0, 1]
        x_norm_new = max(-1.0, min(1.0, x_norm_new))
        self.cusp_position = (x_norm_new + 1) / 2

        # Determine mode based on position
        if self.cusp_position > 0.6:
            new_mode = "perfect"
            self.commitment_strength = (self.cusp_position - 0.6) / 0.4
        elif self.cusp_position < 0.4:
            new_mode = "quick"
            self.commitment_strength = (0.4 - self.cusp_position) / 0.4
        else:
            new_mode = "balanced"
            self.commitment_strength = 0.0

        # Hysteresis: Only switch if new mode is strongly favored
        if new_mode != self.build_mode:
            if self.commitment_strength > 0.5:  # Strong commitment needed to switch
                logger.info(
                    f"Forge switching mode: {self.build_mode} → {new_mode} "
                    f"(commitment={self.commitment_strength:.3f})"
                )
                self.build_mode = new_mode
            else:
                # Not enough commitment to switch, maintain current mode
                logger.debug(
                    f"Forge hysteresis: staying in {self.build_mode} mode "
                    f"(commitment too weak: {self.commitment_strength:.3f})"
                )
        else:
            self.build_mode = new_mode

    async def _execute_build(
        self,
        task: str,
        mode: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute REAL build using tools integration and world model.

        Args:
            task: Task description
            mode: Build mode ("perfect" | "quick" | "balanced")
            context: Execution context

        Returns:
            Build result dictionary with real execution metrics
        """
        import time

        start_time = time.time()

        config = self.MODE_CONFIGS.get(mode, self.MODE_CONFIGS["balanced"])

        result: dict[str, Any] = {
            "task": task,
            "mode": mode,
            "approach": config["approach"],
            "message": config["message"],
            "real_execution": True,
            "safety_checked": False,
        }

        # Execute via tools integration if available
        quality_score = config["base_quality"]

        try:
            from kagami.core.tools_integration import (
                get_tools_integration,  # type: ignore[attr-defined]
            )

            tools = get_tools_integration()
            if tools.initialized:
                # Try to execute relevant tool based on task
                if "test" in task.lower():
                    exec_result = await tools.execute_tool("test", {"target": task})
                    if exec_result.get("success"):
                        quality_score = min(1.0, quality_score + 0.1)
                        result["tool_result"] = exec_result
                elif "build" in task.lower():
                    exec_result = await tools.execute_tool("build", {"target": task})
                    if exec_result.get("success"):
                        quality_score = min(1.0, quality_score + 0.05)
                        result["tool_result"] = exec_result

        except Exception as e:
            logger.debug(f"Tools integration unavailable: {e}")
            result["real_execution"] = False

        # FAIL-SAFE CBF: If safety check fails, apply caution penalty
        cbf_available = False
        try:
            from kagami.core.safety.cbf_integration import check_cbf_for_operation

            safety_result = await check_cbf_for_operation(
                operation="forge.build",
                action=task,
                target="implementation",
                params={"mode": mode},
                metadata={"context": str(context)[:100]},
                source="forge",
            )
            cbf_available = True

            if safety_result.safe:
                result["safety_checked"] = True
                result["h_x"] = safety_result.h_x
            else:
                # Unsafe - significant quality penalty
                quality_score *= 0.5
                result["safety_warning"] = safety_result.reason
                result["safety_checked"] = True
                logger.warning(f"CBF safety violation: {safety_result.reason}")

        except Exception as e:
            # FAIL-SAFE: If CBF unavailable, apply caution zone penalty
            logger.warning(f"CBF check unavailable, applying caution penalty: {e}")
            quality_score *= 0.85  # 15% penalty for unchecked operations
            result["safety_warning"] = "CBF unavailable - caution zone assumed"

        result["cbf_available"] = cbf_available
        build_time = time.time() - start_time
        result["quality_score"] = quality_score
        result["build_time"] = build_time
        result["status"] = "completed" if quality_score >= 0.7 else "needs_rework"

        return result

    def _simulate_build(
        self,
        task: str,
        mode: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute build with async/sync compatibility.

        Attempts async execution via _execute_build. If unavailable,
        falls back to synchronous baseline with fail-safe CBF penalty.
        """
        import asyncio
        import time

        config = self.MODE_CONFIGS.get(mode, self.MODE_CONFIGS["balanced"])

        # Try async execution first
        try:
            # Use asyncio.run() for clean execution (Python 3.7+)
            # This handles event loop creation/cleanup automatically
            try:
                asyncio.get_running_loop()
                # Already in async context - can't nest asyncio.run()
                raise RuntimeError("Nested async context")
            except RuntimeError:
                pass  # No running loop, proceed with asyncio.run()

            return asyncio.run(self._execute_build(task, mode, context))

        except Exception as e:
            logger.debug(f"Async build unavailable ({e}), using synchronous baseline")

        # Synchronous fallback with fail-safe CBF penalty
        start_time = time.time()
        quality_score = config["base_quality"]

        # FAIL-SAFE: Apply caution penalty since we can't check CBF
        quality_score *= 0.85  # 15% penalty for unchecked sync operations
        logger.debug("Sync fallback: applying 15% CBF caution penalty")

        build_time = time.time() - start_time

        return {
            "task": task,
            "mode": mode,
            "quality_score": quality_score,
            "build_time": build_time,
            "approach": config["approach"],
            "message": config["message"],
            "status": "completed" if quality_score >= 0.7 else "needs_rework",
            "real_execution": False,
            "safety_checked": False,
            "safety_warning": "Sync fallback - CBF unavailable",
            "cbf_available": False,
        }

    def should_escalate(
        self,
        result: AgentResult,
        context: dict[str, Any],
    ) -> bool:
        """Determine if escalation needed (Fano line routing).

        ESCALATION CONDITIONS (by Fano composition):
        ============================================
        - Safety issues → Crystal (Forge × Beacon = Crystal: verification)
        - Consecutive failures ≥ 3 → Flow (Spark × Forge = Flow: debugging)
        - Paralysis detected → Flow (intervention needed)
        - Quality persistently low → Beacon (Forge × Nexus = Grove, but Beacon for design)
        - Implementation complete + high quality → Crystal (verification handoff)

        Args:
            result: Processing result
            context: Execution context

        Returns:
            True if should escalate
        """
        # Check if already marked for escalation
        if result.should_escalate:
            return True

        # Safety issues → Crystal for verification
        if result.metadata and result.metadata.get("safety_issue"):
            result.should_escalate = True
            result.escalation_target = "crystal"
            logger.info("Forge escalating to Crystal: safety verification required")
            return True

        # Consecutive failures → Flow for debugging
        if self.consecutive_failures >= self.max_failures_before_escalation:
            result.should_escalate = True
            result.escalation_target = "flow"
            logger.info(
                f"Forge escalating to Flow: {self.consecutive_failures} consecutive failures"
            )
            return True

        # Paralysis → Flow for intervention
        if result.metadata and result.metadata.get("paralysis_detected"):
            result.should_escalate = True
            result.escalation_target = "flow"
            logger.info("Forge escalating to Flow: paralysis detected")
            return True

        # Quality persistently low → Beacon for architecture review
        if self.avg_quality_score < 0.5 and self.builds_completed > 5:
            result.should_escalate = True
            result.escalation_target = "beacon"
            logger.info(f"Forge escalating to Beacon: avg quality {self.avg_quality_score:.3f}")
            return True

        # Implementation complete + high quality → suggest Crystal verification
        if result.success and result.metadata and result.metadata.get("quality_score", 0) > 0.85:
            # Set verification_ready flag for orchestrator routing
            if result.metadata:
                result.metadata["verification_ready"] = True
            logger.info("Forge implementation complete. Ready for Crystal verification.")

        return False

    def reset_failure_count(self) -> None:
        """Reset consecutive failure counter (for new task)."""
        self.consecutive_failures = 0
        logger.debug("Forge failure count reset")

    def get_build_stats(self) -> dict[str, Any]:
        """Get build statistics.

        Returns:
            Dictionary with build stats
        """
        total_builds = self.builds_completed + self.builds_failed
        success_rate = self.builds_completed / total_builds if total_builds > 0 else 0.0

        return {
            "colony": self.colony_name,
            "builds_completed": self.builds_completed,
            "builds_failed": self.builds_failed,
            "success_rate": success_rate,
            "avg_quality_score": self.avg_quality_score,
            "consecutive_failures": self.consecutive_failures,
            "current_mode": self.build_mode,
            "cusp_position": self.cusp_position,
            "commitment_strength": self.commitment_strength,
            "catastrophe_type": "cusp",
        }


# =============================================================================
# FACTORY
# =============================================================================


def create_forge_agent(state_dim: int = 256) -> ForgeAgent:
    """Create Forge agent instance.

    Args:
        state_dim: Dimension of state embeddings

    Returns:
        Configured ForgeAgent
    """
    return ForgeAgent(state_dim=state_dim)
