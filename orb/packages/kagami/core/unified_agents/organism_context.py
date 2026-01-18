"""Structured Context Types for Organism Execution.

Replaces loosely-typed dict[str, Any] context passing with structured
dataclasses for type safety and documentation.

Created: December 24, 2025
Based on feedback: "Introduce a Structured Context/Result Object"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Avoid circular imports
from kagami.core.unified_agents.geometric_worker import TaskResult


class SafetyZone(str, Enum):
    """CBF safety zone classification.

    Based on h(x) value:
    - GREEN: h(x) >= 0.5 (safe with margin)
    - YELLOW: 0 <= h(x) < 0.5 (proceed with caution)
    - RED: h(x) < 0 (blocked - should not reach execution)
    """

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass
class WorldModelHint:
    """Hint from world model about colony routing.

    Attributes:
        colony_idx: Recommended colony index (0-6)
        colony_name: Name of recommended colony
        confidence: Confidence level [0, 1]
        source: Where the hint came from (e.g., "world_model", "world_model_state")
    """

    colony_idx: int
    colony_name: str
    confidence: float = 0.5
    source: str = "world_model"


@dataclass
class KnowledgeGraphSuggestion:
    """Suggestion from knowledge graph reasoning.

    Attributes:
        action: Recommended action
        confidence: Confidence level [0, 1]
        rationale: Why this action is suggested
        success_rate: Historical success rate
        required_tools: Tools needed for this action
        potential_pitfalls: Known issues to avoid
    """

    action: str
    confidence: float = 0.5
    rationale: str = ""
    success_rate: float = 0.0
    required_tools: list[str] = field(default_factory=list[Any])
    potential_pitfalls: list[str] = field(default_factory=list[Any])


@dataclass
class CostEvaluation:
    """Result of cost module evaluation.

    Attributes:
        total: Total cost (IC + TC)
        ic: Intrinsic cost (immutable safety)
        tc: Trainable cost (learned value prediction)
        safety: Safety-specific cost component
        routing_mode: Routing mode evaluated
        primary_colony: Primary colony selected
    """

    total: float
    ic: float
    tc: float
    safety: float
    routing_mode: str
    primary_colony: str


@dataclass
class PerceptionState:
    """Result of perception module processing.

    Attributes:
        state: Unified perceptual state tensor (if available)
        modalities_present: List of observed modalities
        perception_time_ms: Processing time in milliseconds
    """

    state: Any = None  # torch.Tensor when available
    modalities_present: list[str] = field(default_factory=list[Any])
    perception_time_ms: float = 0.0


@dataclass
class OrganismContext:
    """Structured context for organism intent execution.

    Replaces the loosely-typed dict[str, Any] context with explicit fields.
    All fields are optional with sensible defaults.

    Attributes:
        safety_zone: CBF safety zone (GREEN/YELLOW/RED)
        safety_h_x: Raw h(x) value from CBF check
        wm_colony_hint: World model routing hint
        kg_suggestions: Knowledge graph action suggestions
        cost_evaluation: Cost module evaluation result
        perception_state: Perception module output
        sensors: Raw sensor inputs for perception
        query: Original user query (for complexity inference)
        domain: Task domain hint
        complexity: Explicit complexity override [0, 1]
        correlation_id: Tracking ID for receipts
        colony_states: Current colony state vectors (for CBF)
        shared_resources: Shared resource state (for CBF)
    """

    # Safety
    safety_zone: SafetyZone = SafetyZone.GREEN
    safety_h_x: float | None = None

    # Routing hints
    wm_colony_hint: WorldModelHint | None = None
    kg_suggestions: list[KnowledgeGraphSuggestion] = field(default_factory=list[Any])

    # Cost evaluation
    cost_evaluation: CostEvaluation | None = None

    # Perception
    perception_state: PerceptionState | None = None
    sensors: dict[str, Any] | None = None

    # Task context
    query: str | None = None
    domain: str | None = None
    complexity: float | None = None

    # Tracking
    correlation_id: str | None = None

    # CBF state (for routing safety validation)
    colony_states: dict[int, Any] | None = None
    shared_resources: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> OrganismContext:
        """Create OrganismContext from legacy dict[str, Any] format.

        Provides backward compatibility with existing code that passes
        dict[str, Any] as context.
        """
        ctx = cls()

        # Safety zone
        if "safety_zone" in d:
            zone = d["safety_zone"]
            if isinstance(zone, SafetyZone):
                ctx.safety_zone = zone
            elif isinstance(zone, str):
                ctx.safety_zone = SafetyZone(zone)

        ctx.safety_h_x = d.get("safety_h_x")

        # World model hint
        wm_hint = d.get("wm_colony_hint")
        if isinstance(wm_hint, WorldModelHint):
            ctx.wm_colony_hint = wm_hint
        elif isinstance(wm_hint, dict):
            ctx.wm_colony_hint = WorldModelHint(
                colony_idx=wm_hint.get("colony_idx", 0),
                colony_name=wm_hint.get("colony_name", ""),
                confidence=wm_hint.get("confidence", 0.5),
                source=wm_hint.get("source", "world_model"),
            )

        # KG suggestions
        kg = d.get("kg_suggestions", [])
        if kg:
            ctx.kg_suggestions = []
            for item in kg:
                if isinstance(item, KnowledgeGraphSuggestion):
                    ctx.kg_suggestions.append(item)
                elif isinstance(item, dict):
                    ctx.kg_suggestions.append(
                        KnowledgeGraphSuggestion(
                            action=item.get("action", ""),
                            confidence=item.get("confidence", 0.5),
                            rationale=item.get("rationale", ""),
                            success_rate=item.get("success_rate", 0.0),
                            required_tools=item.get("required_tools", []),
                            potential_pitfalls=item.get("potential_pitfalls", []),
                        )
                    )

        # Cost evaluation
        cost = d.get("cost_evaluation")
        if isinstance(cost, CostEvaluation):
            ctx.cost_evaluation = cost
        elif isinstance(cost, dict):
            ctx.cost_evaluation = CostEvaluation(
                total=cost.get("total", 0.0),
                ic=cost.get("ic", 0.0),
                tc=cost.get("tc", 0.0),
                safety=cost.get("safety", 0.0),
                routing_mode=cost.get("routing_mode", ""),
                primary_colony=cost.get("primary_colony", ""),
            )

        # Perception
        perception = d.get("perception_state")
        if isinstance(perception, PerceptionState):
            ctx.perception_state = perception
        elif perception is not None:
            ctx.perception_state = PerceptionState(
                state=perception,
                modalities_present=d.get("modalities_observed", []),
            )

        # Simple fields
        ctx.sensors = d.get("sensors")
        ctx.query = d.get("query")
        ctx.domain = d.get("domain")
        ctx.complexity = d.get("complexity")
        ctx.correlation_id = d.get("correlation_id")
        ctx.colony_states = d.get("colony_states")
        ctx.shared_resources = d.get("shared_resources")

        return ctx

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict[str, Any] for backward compatibility.

        Returns dict[str, Any] format that legacy code expects.
        """
        d: dict[str, Any] = {}

        # Safety
        d["safety_zone"] = self.safety_zone.value
        if self.safety_h_x is not None:
            d["safety_h_x"] = self.safety_h_x

        # World model hint
        if self.wm_colony_hint:
            d["wm_colony_hint"] = {
                "colony_idx": self.wm_colony_hint.colony_idx,
                "colony_name": self.wm_colony_hint.colony_name,
                "confidence": self.wm_colony_hint.confidence,
                "source": self.wm_colony_hint.source,
            }

        # KG suggestions
        if self.kg_suggestions:
            d["kg_suggestions"] = [
                {
                    "action": s.action,
                    "confidence": s.confidence,
                    "rationale": s.rationale,
                    "success_rate": s.success_rate,
                    "required_tools": s.required_tools,
                    "potential_pitfalls": s.potential_pitfalls,
                }
                for s in self.kg_suggestions
            ]

        # Cost evaluation
        if self.cost_evaluation:
            d["cost_evaluation"] = {
                "total": self.cost_evaluation.total,
                "ic": self.cost_evaluation.ic,
                "tc": self.cost_evaluation.tc,
                "safety": self.cost_evaluation.safety,
                "routing_mode": self.cost_evaluation.routing_mode,
                "primary_colony": self.cost_evaluation.primary_colony,
            }

        # Perception
        if self.perception_state:
            d["perception_state"] = self.perception_state.state
            d["modalities_observed"] = self.perception_state.modalities_present

        # Simple fields
        if self.sensors is not None:
            d["sensors"] = self.sensors
        if self.query is not None:
            d["query"] = self.query
        if self.domain is not None:
            d["domain"] = self.domain
        if self.complexity is not None:
            d["complexity"] = self.complexity
        if self.correlation_id is not None:
            d["correlation_id"] = self.correlation_id
        if self.colony_states is not None:
            d["colony_states"] = self.colony_states
        if self.shared_resources is not None:
            d["shared_resources"] = self.shared_resources

        return d


@dataclass
class ExecutionResult:
    """Structured result from organism intent execution.

    Replaces dict[str, Any] return value with explicit fields.

    Attributes:
        intent_id: Unique identifier for this execution
        success: Whether execution succeeded
        mode: Routing mode used (single/fano/all)
        complexity: Task complexity estimate
        results: List of TaskResult from each colony
        e8_action: Fused E8 action code (index and vector)
        latency: Total execution time in seconds
        coordination_phase: Current coordination phase
        error: Error message if failed
    """

    intent_id: str
    success: bool
    latency: float

    # Success fields
    mode: str | None = None
    complexity: float | None = None
    results: list[TaskResult] | None = None
    e8_action: dict[str, Any] | None = None
    coordination_phase: str | None = None

    # Failure fields
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict[str, Any] for backward compatibility."""
        d: dict[str, Any] = {
            "intent_id": self.intent_id,
            "success": self.success,
            "latency": self.latency,
        }

        if self.success:
            if self.mode is not None:
                d["mode"] = self.mode
            if self.complexity is not None:
                d["complexity"] = self.complexity
            if self.results is not None:
                d["results"] = self.results
            if self.e8_action is not None:
                d["e8_action"] = self.e8_action
            if self.coordination_phase is not None:
                d["coordination_phase"] = self.coordination_phase
        else:
            if self.error is not None:
                d["error"] = self.error

        return d


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "CostEvaluation",
    "ExecutionResult",
    "KnowledgeGraphSuggestion",
    "OrganismContext",
    "PerceptionState",
    "SafetyZone",
    "WorldModelHint",
]
