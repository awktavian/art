from __future__ import annotations

"""Phase Advisors - Contribute to reasoning policy based on context.

Advisors examine context and adjust ReasoningConfig dynamically:
- SafetyAdvisor: Check for ethical/risky content
- ComputeAdvisor: Adjust based on system load and SLA
- MemoryAdvisor: Use learned preferences from past experience
"""
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.instincts.learning_instinct import LearningInstinct
    from kagami.core.reasoning.causal_inference import CausalInferenceEngine
    from kagami.core.reasoning.symbolic.z3_solver import Z3ConstraintSolver

logger = logging.getLogger(__name__)


class SafetyAdvisor:
    """Adjusts config based on safety considerations."""

    async def advise(self, context: dict[str, Any], current_config: Any) -> Any:
        """Increase safety level if risky keywords detected."""
        problem_text = str(
            context.get("prompt") or context.get("question") or context.get("problem") or ""
        ).lower()

        # Check for high-risk keywords
        high_risk_keywords = [
            "money",
            "profit",
            "hack",
            "exploit",
            "steal",
            "harm",
            "illegal",
            "dangerous",
        ]

        if any(kw in problem_text for kw in high_risk_keywords):
            # Upgrade safety
            current_config.safety_level = "full"
            current_config.temperature = min(current_config.temperature, 0.7)
            logger.info("🛡️  Safety advisor: Upgraded to full safety mode")

        return current_config


class ComputeAdvisor:
    """Adjusts config based on compute budget and system load."""

    async def advise(self, context: dict[str, Any], current_config: Any) -> Any:
        """Adjust reasoning budget based on SLA and system load."""
        # Check for SLA constraints
        sla_budget_ms = context.get("sla_budget_ms") or context.get("time_budget_ms")

        if sla_budget_ms:
            # Enforce SLA
            current_config.reasoning_budget_ms = min(
                current_config.reasoning_budget_ms, int(sla_budget_ms)
            )
            logger.debug(f"⏱️  Compute advisor: Clamped budget to {sla_budget_ms}ms SLA")

        # Check system load (best-effort, non-blocking)
        psutil = None
        try:
            import psutil  # type: ignore[assignment]

            # Use interval=0 for non-blocking check (uses cached value)
            cpu_percent = psutil.cpu_percent(interval=0)  # type: ignore[attr-defined]
            if cpu_percent > 80:
                # System under load - reduce budget
                current_config.reasoning_budget_ms = int(current_config.reasoning_budget_ms * 0.7)
                logger.info(f"⚠️  Compute advisor: Reduced budget (CPU at {cpu_percent:.0f}%)")
        except ImportError:
            psutil = None
            # Gracefully degrade without psutil
            pass
        except Exception:
            pass

        return current_config


class GPUAdvisor:
    """Enables GPU-accelerated MCTS for high-stakes planning.

    Activated: October 6, 2025
    Grounded in: Ha & Schmidhuber (2018) World Models for imagination planning.
    """

    async def advise(self, context: dict[str, Any], current_config: Any) -> Any:
        """Enable GPU MCTS when risk > 0.7 and budget allows."""
        risk = context.get("risk", 0.0)
        threat_score = context.get("threat_score", 0.0)
        max_risk = max(risk, threat_score)

        # High-stakes problems get GPU MCTS (10k-100k rollouts)
        if max_risk > 0.7 and current_config.reasoning_budget_ms > 3000:
            current_config.metadata = current_config.metadata or {}
            current_config.metadata["use_gpu_mcts"] = True
            current_config.metadata["mcts_budget"] = min(
                10000, current_config.reasoning_budget_ms * 2
            )
            logger.info(
                f"🚀 GPU advisor: Enabled GPU MCTS (risk={max_risk:.2f}, "
                f"budget={current_config.reasoning_budget_ms}ms)"
            )

        return current_config


class MemoryAdvisor:
    """Adjusts config based on learned preferences."""

    def __init__(self) -> None:
        self._learning_instinct: LearningInstinct | None = None
        self._prediction_instinct = None

    async def advise(self, context: dict[str, Any], current_config: Any) -> Any:
        """Use learned preferences to boost/adjust config."""
        # Lazy init
        if self._learning_instinct is None:
            try:
                from kagami.core.instincts.learning_instinct import LearningInstinct

                self._learning_instinct = LearningInstinct()
            except Exception as e:
                logger.debug(f"Learning instinct unavailable: {e}")
                return current_config

        # Check learned preferences for this problem type
        problem_type = context.get("problem_type", "unknown")
        signature = f"{problem_type}::strategy"

        try:
            # Get value estimate for current strategy
            value_estimates = self._learning_instinct.get_learned_preferences()
            if signature in value_estimates:
                learned_value = value_estimates[signature]

                # If we've learned this strategy works poorly, try something else
                if learned_value < -0.3:
                    logger.info(
                        f"🧠 Memory advisor: Avoiding learned-poor strategy (value={learned_value:.2f})"
                    )
                    # Switch to alternative
                    if current_config.strategy == "react_k1":
                        current_config.strategy = "self_consistency_k3"
                    elif current_config.strategy == "self_consistency_k3":
                        current_config.strategy = "react_k1"

                # If we've learned this works well, boost confidence
                elif learned_value > 0.5:
                    logger.debug(
                        f"✨ Memory advisor: Confirmed good strategy (value={learned_value:.2f})"
                    )
                    current_config.confidence_threshold = max(
                        0.9, current_config.confidence_threshold
                    )

        except Exception as e:
            logger.debug(f"Memory advisory failed: {e}")

        return current_config


class CausalAdvisor:
    """Uses causal inference for root cause analysis (ADDED OCT 7, 2025).

    Integration:
    - Collects observational data from operations
    - Discovers causal structure via PC algorithm
    - Predicts intervention effects via do-calculus
    - Recommends reasoning strategy based on causal complexity
    """

    def __init__(self) -> None:
        self._engine: CausalInferenceEngine | None = None
        self._observation_count = 0

    async def advise(self, context: dict[str, Any], current_config: Any) -> Any:
        """Adjust config based on causal analysis."""
        # Lazy load
        if self._engine is None:
            try:
                from kagami.core.reasoning.causal_inference import (
                    get_causal_inference_engine,
                )

                self._engine = get_causal_inference_engine()
            except Exception as e:
                logger.debug(f"Causal engine unavailable: {e}")
                return current_config

        # Collect observation
        if context.get("outcome") or context.get("metrics"):
            observation = {
                "operation": context.get("operation", "unknown"),
                "duration_ms": context.get("duration_ms", 0),
                "success": context.get("success", True),
                "valence": context.get("valence", 0.0),
                "loop_depth": context.get("loop_depth", 0),
            }
            self._engine.add_observation(observation)
            self._observation_count += 1

        # Causal discovery every 100 observations (trigger when count hits 100 or multiples)
        if self._observation_count >= 100 and (
            self._observation_count % 100 == 0 or self._observation_count == 100
        ):
            try:
                variables = ["duration_ms", "loop_depth", "valence"]
                edges = await self._engine.discover_causal_structure(variables, min_samples=50)

                if edges and len(edges) > 3:
                    # Causal complexity detected
                    current_config.strategy = "self_consistency_k5"
                    current_config.reasoning_budget_ms = max(
                        current_config.reasoning_budget_ms, 5000
                    )
                    logger.info(f"🔗 Causal advisor: Upgraded to k=5 ({len(edges)} edges)")
            except Exception as e:
                logger.debug(f"Causal discovery failed: {e}")

        return current_config


class FormalVerificationAdvisor:
    """Optional formal verification for critical operations (ADDED OCT 7, 2025).

    Integration:
    - Checks if Lean theorem prover available
    - Attempts formal verification for high-risk operations
    - Increases safety level if verification recommended
    - Non-blocking (graceful degradation)
    """

    def __init__(self) -> None:
        self._prover: Z3ConstraintSolver | None = None
        self._available: bool | None = None

    async def advise(self, context: dict[str, Any], current_config: Any) -> Any:
        """Adjust config based on formal verification availability.

        SIMPLIFIED (Dec 2, 2025):
        Uses Z3 solver check instead of deleted Lean prover.
        """
        # Check availability once
        if self._available is None:
            try:
                # Check if Z3 is available
                from kagami.core.reasoning.symbolic.z3_solver import Z3ConstraintSolver

                self._prover = Z3ConstraintSolver()
                self._available = True
                logger.info("✅ Formal verification: Z3 available")
            except ImportError:
                self._available = False
                logger.debug("⚠️  Formal verification: Z3 not found (optional)")
            except Exception:
                self._available = False

        # Note in metadata if available and high-risk
        risk = context.get("risk", 0.0)
        if risk > 0.7 and self._available:
            if current_config.metadata is None:
                current_config.metadata = {}
            current_config.metadata["formal_verification_available"] = True
            current_config.metadata["formal_verification_recommended"] = True
            logger.info("🔒 Formal verification: Recommended for high-risk op")

        return current_config


__all__ = [
    "CausalAdvisor",
    "ComputeAdvisor",
    "FormalVerificationAdvisor",
    "GPUAdvisor",
    "MemoryAdvisor",
    "SafetyAdvisor",
]
