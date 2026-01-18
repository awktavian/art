"""Shared Safety Types for Control Barrier Functions.

This module provides canonical definitions for safety-related types
used across the safety layer. All CBF implementations should import
types from here to avoid duplication.

Consolidation: November 30, 2025 (Updated Dec 6, 2025)
This is now the CANONICAL source for all safety types.
- discrete_cbf.py DELETED (Dec 6, 2025)
- control_barrier_function.py now re-exports from here

Enhanced: December 2, 2025
Added SafetyScenario and AttackType enums based on Safe RLHF paper
for structured threat classification.

Type Safety: December 14, 2025
Added proper Protocol types for safety filters and classifiers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Protocol, cast

import numpy as np
import torch

logger = logging.getLogger(__name__)


# =============================================================================
# SAFETY TAXONOMY (Based on Safe RLHF Paper)
# =============================================================================


class SafetyScenario(Enum):
    """8 typical safety scenarios from Safe RLHF paper.

    These represent categories of potentially harmful content or behavior
    that the safety system should detect and handle appropriately.

    Reference: Sun et al., "Safety Assessment of Chinese Large Language Models"
    """

    # Content-related
    INSULT = "insult"  # Insulting, threatening, profane content
    DISCRIMINATION = "unfairness_discrimination"  # Bias based on race, gender, etc.
    CRIMES = "crimes_illegal"  # Illegal activities, crime incitement
    SENSITIVE = "sensitive_topics"  # Politically sensitive, controversial

    # Harm-related
    PHYSICAL_HARM = "physical_harm"  # Physical violence, self-harm instructions
    MENTAL_HEALTH = "mental_health"  # Psychological harm, exploitation
    PRIVACY = "privacy_property"  # Privacy violations, data theft
    ETHICS = "ethics_morality"  # Unethical behavior, moral violations

    @classmethod
    def from_context(cls, context: dict[str, Any]) -> SafetyScenario | None:
        """Scenario detection requires full LLM classification.

        ARCHITECTURE (December 22, 2025):
        NO keyword matching. Scenario detection must use full LLM intelligence.

        This method returns None - scenario detection should be done by the
        WildGuard classifier which returns proper risk categories.

        Use SafetyClassification.risk_scores from LLM instead.

        Args:
            context: Operation context dict[str, Any] (unused - no heuristics)

        Returns:
            None - use LLM classification instead
        """
        # NO HEURISTICS - scenario must be determined by LLM classification
        # The WildGuard classifier returns proper risk categories
        # which map to scenarios via SafetyClassification.max_risk()
        return None

    @property
    def risk_multiplier(self) -> float:
        """Get risk multiplier for this scenario.

        Higher values indicate more severe scenarios that should
        trigger stricter safety thresholds.
        """
        multipliers = {
            SafetyScenario.INSULT: 1.2,
            SafetyScenario.DISCRIMINATION: 1.5,
            SafetyScenario.CRIMES: 2.0,
            SafetyScenario.SENSITIVE: 1.3,
            SafetyScenario.PHYSICAL_HARM: 2.5,
            SafetyScenario.MENTAL_HEALTH: 2.0,
            SafetyScenario.PRIVACY: 1.8,
            SafetyScenario.ETHICS: 1.4,
        }
        return multipliers.get(self, 1.0)


class AttackType(Enum):
    """6 instruction attack types from Safe RLHF paper.

    These represent adversarial prompting techniques that attempt
    to bypass safety measures. The CBF should be especially vigilant
    when these attack patterns are detected.

    Reference: Sun et al., "Safety Assessment of Chinese Large Language Models"
    """

    GOAL_HIJACKING = "goal_hijacking"  # Redirecting model to different goal
    PROMPT_LEAKING = "prompt_leaking"  # Extracting system prompts
    ROLE_PLAY = "role_play"  # "Pretend you are..." jailbreak
    UNSAFE_INSTRUCTION = "unsafe_instruction"  # Direct harmful instruction
    INQUIRY_UNSAFE = "inquiry_unsafe_opinion"  # Asking for unsafe opinions
    REVERSE_EXPOSURE = "reverse_exposure"  # Tricking model to reveal info

    @classmethod
    def from_prompt(cls, prompt: str) -> AttackType | None:
        """Detect attack type from prompt text.

        Args:
            prompt: User prompt text

        Returns:
            None - attack detection must use full LLM classification
        """
        # ARCHITECTURE (December 22, 2025):
        # NO keyword heuristics. Attack detection must use full LLM.
        #
        # WildGuard classifier handles prompt injection detection via:
        # - DANGEROUS_ACTIVITIES category
        # - MALWARE_HACKING category
        # - Full context understanding
        #
        # This method returns None - use WildGuard classification instead.
        _ = prompt  # Unused - no heuristics
        return None

    @property
    def risk_multiplier(self) -> float:
        """Get risk multiplier for this attack type.

        Higher values indicate more dangerous attack patterns.
        """
        multipliers = {
            AttackType.GOAL_HIJACKING: 1.8,
            AttackType.PROMPT_LEAKING: 1.5,
            AttackType.ROLE_PLAY: 1.6,
            AttackType.UNSAFE_INSTRUCTION: 2.5,
            AttackType.INQUIRY_UNSAFE: 1.4,
            AttackType.REVERSE_EXPOSURE: 1.3,
        }
        return multipliers.get(self, 1.0)


@dataclass
class ThreatClassification:
    """Complete threat classification result.

    Combines scenario detection and attack detection for comprehensive
    threat assessment that can be used to adjust CBF thresholds.
    """

    scenario: SafetyScenario | None = None
    attack: AttackType | None = None
    scenario_confidence: float = 0.0
    attack_confidence: float = 0.0

    @property
    def combined_risk_multiplier(self) -> float:
        """Get combined risk multiplier from scenario and attack.

        Multiplicative combination of both factors.
        """
        base = 1.0
        if self.scenario:
            base *= self.scenario.risk_multiplier * self.scenario_confidence
        if self.attack:
            base *= self.attack.risk_multiplier * self.attack_confidence
        return max(1.0, base)  # Minimum 1.0

    @property
    def requires_elevated_safety(self) -> bool:
        """Whether this classification requires elevated safety measures."""
        return self.combined_risk_multiplier > 1.5

    @classmethod
    def from_context(
        cls,
        context: dict[str, Any],
        prompt: str = "",
    ) -> ThreatClassification:
        """Classify threat from context and prompt.

        Args:
            context: Operation context dict[str, Any]
            prompt: User prompt text

        Returns:
            ThreatClassification with detected scenario and attack
        """
        scenario = SafetyScenario.from_context(context)
        attack = AttackType.from_prompt(prompt)

        return cls(
            scenario=scenario,
            attack=attack,
            scenario_confidence=0.8 if scenario else 0.0,
            attack_confidence=0.8 if attack else 0.0,
        )


class SafetyState:
    """Safety-critical state vector for CBF evaluation.

    This is the canonical definition used by all CBF implementations.
    The state vector x ∈ ℝ⁴ represents the agent's current risk profile.

    Attributes:
        threat: Threat level [0,1] - learned or estimated threat
        uncertainty: Uncertainty [0,1] - (1 - prediction_confidence)
        complexity: Task complexity [0,1] - operational complexity
        predictive_risk: Predicted risk [0,1] - learned failure risk

    Note: `threat_score` is accepted as an alias for `threat` for backward compatibility.

    Mathematical Role:
        The safe set[Any] S = {x | h(x) ≥ 0} is defined over this state space.
        CBF constraint: ḣ(x,u) + α(h(x)) ≥ 0 ensures forward invariance.
    """

    __slots__ = ("complexity", "predictive_risk", "threat", "uncertainty")

    def __init__(
        self,
        threat: float = 0.0,
        uncertainty: float = 0.0,
        complexity: float = 0.0,
        predictive_risk: float = 0.0,
        *,
        threat_score: float | None = None,  # Alias for backward compatibility
    ) -> None:
        """Initialize SafetyState.

        Args:
            threat: Threat level [0,1]
            uncertainty: Uncertainty [0,1]
            complexity: Task complexity [0,1]
            predictive_risk: Predicted risk [0,1]
            threat_score: Alias for threat (backward compat)
        """
        # Handle threat_score alias (backward compatibility)
        if threat_score is not None and threat == 0.0:
            threat = threat_score

        # Validate and clamp
        self.threat = self._validate_and_clamp("threat", threat)
        self.uncertainty = self._validate_and_clamp("uncertainty", uncertainty)
        self.complexity = self._validate_and_clamp("complexity", complexity)
        self.predictive_risk = self._validate_and_clamp("predictive_risk", predictive_risk)

    @staticmethod
    def _validate_and_clamp(name: str, value: float) -> float:
        """Validate and clamp a value to [0,1].

        SECURITY: Prevents invalid states from bypassing CBF.
        """
        if not isinstance(value, int | float):
            raise TypeError(f"{name} must be numeric, got {type(value).__name__}")

        if not (0.0 <= value <= 1.0):
            clamped = max(0.0, min(1.0, float(value)))
            logger.warning(
                f"SafetyState: {name}={value:.3f} out of range [0,1], clamping to {clamped:.3f}"
            )
            return clamped
        return float(value)

    def __repr__(self) -> str:
        return (
            f"SafetyState(threat={self.threat:.3f}, uncertainty={self.uncertainty:.3f}, "
            f"complexity={self.complexity:.3f}, predictive_risk={self.predictive_risk:.3f})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SafetyState):
            return NotImplemented
        return (
            self.threat == other.threat
            and self.uncertainty == other.uncertainty
            and self.complexity == other.complexity
            and self.predictive_risk == other.predictive_risk
        )

    @property
    def risk_vector(self) -> np.ndarray:
        """Get state as numpy array [threat, uncertainty, complexity, predictive_risk]."""
        return cast(
            np.ndarray,
            np.array(
                [self.threat, self.uncertainty, self.complexity, self.predictive_risk],
                dtype=np.float64,
            ),
        )

    def to_vector(self) -> list[float]:
        """Convert to list[Any] representation."""
        return [self.threat, self.uncertainty, self.complexity, self.predictive_risk]

    def to_array(self) -> np.ndarray:
        """Convert to numpy array (alias for risk_vector)."""
        return self.risk_vector

    @classmethod
    def from_array(cls, arr: np.ndarray) -> SafetyState:
        """Create SafetyState from numpy array.

        Args:
            arr: Array of [threat, uncertainty, complexity, predictive_risk]

        Returns:
            New SafetyState instance
        """
        return cls(
            threat=float(arr[0]),
            uncertainty=float(arr[1]),
            complexity=float(arr[2]),
            predictive_risk=float(arr[3]),
        )

    @property
    def threat_score(self) -> float:
        """Alias for threat (backward compatibility with control_barrier_function.py)."""
        return self.threat

    @property
    def risk_level(self) -> float:
        """Aggregate risk (weighted average).

        Weights emphasize threat and uncertainty over complexity.
        """
        weights = [0.4, 0.3, 0.1, 0.2]  # threat, uncertainty, complexity, predictive
        return sum(w * v for w, v in zip(weights, self.to_vector(), strict=True))

    @classmethod
    def from_dict(cls, data: dict[str, float]) -> SafetyState:
        """Create SafetyState from dictionary."""
        return cls(
            threat=data.get("threat", data.get("threat_score", 0.0)),
            uncertainty=data.get("uncertainty", 0.0),
            complexity=data.get("complexity", 0.0),
            predictive_risk=data.get("predictive_risk", 0.0),
        )

    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary."""
        return {
            "threat": self.threat,
            "uncertainty": self.uncertainty,
            "complexity": self.complexity,
            "predictive_risk": self.predictive_risk,
            "risk_level": self.risk_level,
        }


@dataclass
class CBFResult:
    """Result of Control Barrier Function safety check.

    Contains the outcome of a CBF evaluation including the barrier
    function values, constraint satisfaction, and filtered control.

    Attributes:
        safe: Whether the action is safe (constraint satisfied)
        h_current: Current barrier function value h(x_t)
        h_next: Predicted next barrier value h(x_{t+1})
        constraint_value: Constraint margin (positive = safe)
        action_filtered: The safe-filtered action vector
        qp_iterations: Number of QP solver iterations (0 if no QP)
        adjusted: Whether the original action was modified
    """

    safe: bool  # Whether action is safe
    h_current: float  # Current barrier value
    h_next: float  # Predicted barrier value
    constraint_value: float  # LHS - RHS of constraint
    action_filtered: np.ndarray  # Filtered safe action
    qp_iterations: int  # QP solver iterations
    adjusted: bool  # Whether control was modified

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "safe": self.safe,
            "h_current": float(self.h_current),
            "h_next": float(self.h_next),
            "constraint_value": float(self.constraint_value),
            "action_filtered": self.action_filtered.tolist(),
            "qp_iterations": self.qp_iterations,
            "adjusted": self.adjusted,
        }


@dataclass
class ControlInput:
    """Control vector u ∈ ℝ² for CBF optimization.

    Represents the agent's control parameters that can be adjusted
    by the CBF to ensure safety.

    Attributes:
        aggression: How aggressive the action is [0,1]
        speed: How fast to execute [0,1]
    """

    aggression: float  # 0.0-1.0
    speed: float  # 0.0-1.0

    def __post_init__(self) -> None:
        """Validate control inputs."""
        self.aggression = max(0.0, min(1.0, self.aggression))
        self.speed = max(0.0, min(1.0, self.speed))

    def to_vector(self) -> list[float]:
        """Convert to control vector."""
        return [self.aggression, self.speed]

    def to_array(self) -> np.ndarray:
        """Convert to numpy array."""
        return cast(np.ndarray, np.array([self.aggression, self.speed], dtype=np.float64))

    @classmethod
    def from_vector(cls, u: list[float] | np.ndarray) -> ControlInput:
        """Create from vector."""
        if isinstance(u, np.ndarray):
            return cls(aggression=float(u[0]), speed=float(u[1]))
        return cls(aggression=float(u[0]), speed=float(u[1]))


# Import canonical SafetyViolationError from exceptions hierarchy
# (Consolidation: Nov 30, 2025)
from kagami.core.exceptions import SafetyViolationError


@dataclass
class SafetyCheckResult:
    """Unified result type for all CBF safety checks.

    This is the canonical result type that should be used by ALL CBF
    integration points (orchestrator, agents, operation router, etc.).

    Consolidation: December 1, 2025
    Previously defined separately in:
    - orchestrator/safety_checker.py (is_safe, h_x, reason, detail)
    - orchestrator/safety_gates.py (safe, reason, detail, h_x, action)
    - fractal_agents/agent/safety.py (passed, error, metadata)

    Attributes:
        safe: Whether the operation is safe (h(x) >= 0)
        h_x: Barrier function value (positive = safe margin)
        reason: Reason code if blocked (e.g., "safety_barrier_violation")
        detail: Human-readable detail message
        action: Action that was checked (for logging/metrics)
        metadata: Additional context for debugging
    """

    safe: bool
    h_x: float | None = None
    reason: str | None = None
    detail: str | None = None
    action: str | None = None
    metadata: dict[str, Any] | None = None

    # Aliases for backward compatibility
    @property
    def passed(self) -> bool:
        """Alias for safe (backward compat with agent safety)."""
        return self.safe

    @property
    def is_safe(self) -> bool:
        """Alias for safe (backward compat with safety_checker)."""
        return self.safe

    @property
    def error(self) -> str | None:
        """Alias for reason (backward compat with agent safety)."""
        return self.reason

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "safe": self.safe,
            "h_x": self.h_x,
            "reason": self.reason,
            "detail": self.detail,
            "action": self.action,
            "metadata": self.metadata,
        }

    def to_error_response(self) -> dict[str, Any]:
        """Convert to error response dict[str, Any] (backward compat with safety_gates)."""
        return {
            "status": "blocked",
            "reason": self.reason or "safety_barrier_violation",
            "detail": self.detail or "Safety check failed",
            "action": self.action,
            "h_x": self.h_x,
        }


# =============================================================================
# PROTOCOL TYPES FOR SAFETY COMPONENTS
# =============================================================================


class SafetyClassification(Protocol):
    """Protocol for safety classification results."""

    @property
    def is_safe(self) -> bool:
        """Whether content is classified as safe."""
        ...

    def max_risk(self) -> str:
        """Return name of highest risk category."""
        ...

    def total_risk(self) -> float:
        """Return aggregate risk score."""
        ...


class SafetyFilter(Protocol):
    """Protocol for integrated safety filters (WildGuard + OptimalCBF)."""

    def filter_text(
        self,
        text: str,
        nominal_control: torch.Tensor,
        context: str = "",
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, Any]]:
        """Filter text through safety classifier and CBF.

        Args:
            text: Text to classify for safety
            nominal_control: Nominal control vector [B, 2]
            context: Additional context for classification

        Returns:
            - safe_control: Filtered safe control [B, 2]
            - penalty: Soft barrier penalty
            - info: Dict with 'classification', 'h_metric', etc.
        """
        ...


# Type aliases for common dict[str, Any] shapes
StateDict = dict[str, float | int | str | bool]
ContextDict = dict[str, Any]  # Remains Any for maximum flexibility
MetadataDict = dict[str, Any]  # Remains Any for extensibility
ConfigDict = dict[str, Any]  # Remains Any for YAML/JSON flexibility


__all__ = [
    "AttackType",
    "CBFResult",
    "ConfigDict",
    "ContextDict",
    "ControlInput",
    "MetadataDict",
    "SafetyCheckResult",
    # Protocols
    "SafetyClassification",
    "SafetyFilter",
    # Safety taxonomy (Safe RLHF)
    "SafetyScenario",
    # Core types
    "SafetyState",
    "SafetyViolationError",
    # Type aliases
    "StateDict",
    "ThreatClassification",
]
