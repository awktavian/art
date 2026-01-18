from __future__ import annotations

"""Reasoning Policy - Central decision service for optimal reasoning configuration.

Aggregates inputs from advisors (safety, compute, memory) and returns unified ReasoningConfig.
Grounded in existing agent patterns - perceive → reason → act with receipts.
"""
import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class ReasoningConfig:
    """Unified reasoning configuration returned by policy."""

    strategy: str  # "react_k1", "self_consistency_k3", etc.
    temperature: float
    max_tokens: int
    safety_level: str  # "full", "standard", "minimal"
    reasoning_budget_ms: int
    confidence_threshold: float = 0.7
    metadata: dict[str, Any] | None = None


class PhaseAdvisor(Protocol):
    """Protocol for phase advisors that contribute to reasoning config."""

    async def advise(
        self, context: dict[str, Any], current_config: ReasoningConfig
    ) -> ReasoningConfig:
        """Advise on reasoning configuration based on context.

        Args:
            context: Current operation context
            current_config: Current configuration (may be modified)

        Returns:
            Updated configuration
        """
        ...


class ReasoningPolicyService:
    """Central reasoning policy service.

    Aggregates:
    - Adaptive router (problem-type classification)
    - Safety advisor (ethical checks, risk assessment)
    - Compute advisor (budget, SLA)
    - Memory advisor (learned preferences from experience)
    """

    def __init__(self) -> None:
        self._advisors: list[PhaseAdvisor] = []
        self._router = None
        self._initialized = False

        # Policy store (hierarchical overrides)
        self._global_defaults = ReasoningConfig(
            strategy="react_k1",
            temperature=0.7,
            max_tokens=200,
            safety_level="standard",
            reasoning_budget_ms=3000,
        )
        self._app_overrides: dict[str, ReasoningConfig] = {}
        self._intent_overrides: dict[str, ReasoningConfig] = {}

    async def initialize(self) -> None:
        """Initialize policy service and advisors."""
        if self._initialized:
            return

        # Load ML-based adaptive router (deprecates keyword-based router)
        try:
            from kagami.core.reasoning.adaptive_router import (
                get_adaptive_router,
            )

            self._router = get_adaptive_router(mode="ml")  # type: ignore[assignment]
            logger.info("✅ Reasoning policy: ML adaptive router loaded")
        except Exception as e:
            logger.warning(f"⚠️  ML adaptive router unavailable: {e}")

        # Register built-in advisors
        try:
            from kagami.core.reasoning.advisors import (
                CausalAdvisor,
                ComputeAdvisor,
                FormalVerificationAdvisor,
                GPUAdvisor,
                MemoryAdvisor,
                SafetyAdvisor,
            )

            self.register_advisor(SafetyAdvisor())
            self.register_advisor(ComputeAdvisor())
            self.register_advisor(GPUAdvisor())
            self.register_advisor(MemoryAdvisor())
            self.register_advisor(CausalAdvisor())
            self.register_advisor(FormalVerificationAdvisor())
            logger.info("✅ Reasoning policy: 6 advisors registered")
        except Exception as e:
            logger.warning(f"⚠️  Advisors unavailable: {e}")

        self._initialized = True
        logger.info("✅ Reasoning policy service initialized")

    def register_advisor(self, advisor: PhaseAdvisor) -> None:
        """Register a phase advisor."""
        self._advisors.append(advisor)

    async def select_config(
        self,
        problem: str,
        app: str | None = None,
        intent_action: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ReasoningConfig:
        """Select optimal reasoning configuration using hierarchical policy.

        Precedence:
        1. Intent-level overrides (specific action)
        2. App-level overrides (app defaults)
        3. Router classification (problem-type based)
        4. Global defaults

        Then apply advisors for dynamic adjustments.

        Args:
            problem: Problem text to classify
            app: App name (for app-level overrides)
            intent_action: Intent action (for intent overrides)
            context: Additional context for advisors

        Returns:
            Optimal reasoning configuration
        """
        if not self._initialized:
            await self.initialize()

        context = context or {}

        # Start with global defaults
        config = ReasoningConfig(
            strategy=self._global_defaults.strategy,
            temperature=self._global_defaults.temperature,
            max_tokens=self._global_defaults.max_tokens,
            safety_level=self._global_defaults.safety_level,
            reasoning_budget_ms=self._global_defaults.reasoning_budget_ms,
        )

        # Apply router classification (if available)
        if self._router:
            try:  # type: ignore[unreachable]
                router_config = await self._router.select_config(problem, context)
                config.strategy = router_config.strategy
                config.temperature = router_config.temperature
                config.max_tokens = router_config.max_tokens
                config.safety_level = router_config.safety_level
                config.reasoning_budget_ms = router_config.reasoning_budget_ms
            except Exception as e:
                logger.debug(f"Router classification failed: {e}")

        # Apply app-level overrides
        if app and app in self._app_overrides:
            override = self._app_overrides[app]
            config.strategy = override.strategy
            config.temperature = override.temperature
            config.max_tokens = override.max_tokens
            config.safety_level = override.safety_level
            config.reasoning_budget_ms = override.reasoning_budget_ms

        # Apply intent-level overrides
        if intent_action and intent_action in self._intent_overrides:
            override = self._intent_overrides[intent_action]
            config.strategy = override.strategy
            config.temperature = override.temperature
            config.max_tokens = override.max_tokens
            config.safety_level = override.safety_level
            config.reasoning_budget_ms = override.reasoning_budget_ms

        # Run advisors (dynamic adjustments)
        for advisor in self._advisors:
            try:
                config = await advisor.advise(context, config)
            except Exception as e:
                logger.debug(f"Advisor {type(advisor).__name__} failed: {e}")

        # Emit policy decision metric
        try:
            from kagami_observability.metrics import POLICY_DECISION_TOTAL

            POLICY_DECISION_TOTAL.labels(strategy=config.strategy, safety=config.safety_level).inc()
        except Exception:
            pass

        return config

    def set_app_override(self, app: str, config: ReasoningConfig) -> None:
        """Set app-level reasoning override."""
        self._app_overrides[app] = config

    def set_intent_override(self, intent_action: str, config: ReasoningConfig) -> None:
        """Set intent-level reasoning override."""
        self._intent_overrides[intent_action] = config

    def get_current_defaults(self) -> ReasoningConfig:
        """Get current global defaults."""
        return self._global_defaults


# Global instance
_policy_service = None


def get_reasoning_policy() -> ReasoningPolicyService:
    """Get global reasoning policy service."""
    global _policy_service
    if _policy_service is None:
        _policy_service = ReasoningPolicyService()
    return _policy_service
