"""Base Colony Agent - Simplified interface for Forge/Flow/Nexus/Grove.

This provides a simpler base class interface than the canonical BaseColonyAgent.
It's used by agents that don't need the full catastrophe kernel machinery.

For the full-featured base with AgentConfig, use:
    from kagami.core.unified_agents.agents.base_colony_agent import BaseColonyAgent

COHERENCY REFACTOR (December 27, 2025):
=======================================
- Added OctonionState integration for unified state representation
- s7_unit is now derived from OctonionState
- e8_unit provides full 8D octonion embedding
- AgentResult includes e8_code for E8 lattice integration

Created: December 14, 2025
Status: Simplified base for backward compatibility
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import torch
import torch.nn.functional as F

from kagami.core.unified_agents.colony_constants import COLONY_NAMES


@dataclass
class AgentResult:
    """Result from agent execution (simplified interface).

    COHERENCY UPDATE (Dec 27, 2025): Added e8_code for unified state flow.

    Attributes:
        success: Whether execution succeeded
        output: Agent output (text or dict[str, Any])
        e8_code: 8D octonion embedding (unified state)
        s7_embedding: 7D S⁷ embedding (legacy, derived from e8_code)
        should_escalate: Whether to escalate to another colony
        escalation_target: Target colony for escalation
        escalation_reason: Reason for escalation
        metadata: Additional execution metadata
        catastrophe_state: Catastrophe kernel state (activation, params)
        thoughts: Chain of thought reasoning
        latency: Execution time in seconds
    """

    success: bool
    output: str | dict[str, Any]
    e8_code: torch.Tensor | None = None  # [8] - Full octonion (Dec 27, 2025)
    s7_embedding: torch.Tensor | None = None  # [7] - Imaginary part (legacy)
    should_escalate: bool = False
    escalation_target: str | None = None
    escalation_reason: str = ""
    metadata: dict[str, Any] | None = None
    catastrophe_state: dict[str, Any] = field(default_factory=dict[str, Any])
    thoughts: list[str] = field(default_factory=list[Any])
    latency: float = 0.0

    def __post_init__(self) -> None:
        """Ensure coherency between e8_code and s7_embedding."""
        # If e8_code is set[Any], derive s7_embedding from it
        if self.e8_code is not None and self.s7_embedding is None:
            self.s7_embedding = F.normalize(self.e8_code[1:], dim=-1)  # e₁..e₇
        # If s7_embedding is set[Any] but not e8_code, reconstruct
        elif self.s7_embedding is not None and self.e8_code is None:
            real_part = 0.5 if self.success else -0.5
            # Handle both 1D and 2D embeddings
            s7_normalized = F.normalize(self.s7_embedding, dim=-1)
            if s7_normalized.dim() == 1:
                self.e8_code = torch.cat([torch.tensor([real_part]), s7_normalized])
            else:
                # 2D: prepend real_part to each row
                batch_size = s7_normalized.shape[0]
                real_tensor = torch.full((batch_size, 1), real_part)
                self.e8_code = torch.cat([real_tensor, s7_normalized], dim=-1)

    def to_octonion_state(self) -> Any:
        """Convert to OctonionState for unified pipeline.

        Returns:
            OctonionState with this result's embedding
        """
        from kagami.core.unified_agents.octonion_state import OctonionState

        if self.e8_code is not None:
            return OctonionState(
                e8_code=self.e8_code,
                confidence=0.9 if self.success else 0.3,
                metadata={"source": "agent_result", "success": self.success},
            )
        # Fallback
        return OctonionState.zeros()


class BaseColonyAgent(ABC):
    """Abstract base for catastrophe-specialized colony agents (simplified).

    This is a lightweight base class for agents that don't need the full
    AgentConfig/AgentState machinery. Agents using this base:
    - Forge, Flow, Nexus, Grove

    For full-featured agents with catastrophe kernels and worker pools, see:
        kagami.core.unified_agents.base_colony_agent.BaseColonyAgent

    Each agent embodies:
    - Catastrophe dynamics (fold, cusp, swallowtail, etc.)
    - Colony persona (Spark, Forge, Flow, etc.)
    - Domain expertise (creative, build, debug, etc.)
    - Tool access (research, code, test, etc.)

    COHERENCY UPDATE (Dec 27, 2025):
    - e8_unit: 8D octonion embedding (canonical)
    - s7_unit: 7D S⁷ embedding (derived from e8_unit)

    Args:
        colony_idx: Index of colony (0-6)
        state_dim: Dimension of state embeddings
    """

    def __init__(self, colony_idx: int, state_dim: int = 256):
        if not 0 <= colony_idx < 7:
            raise ValueError(f"colony_idx must be 0-6, got {colony_idx}")

        self.colony_idx = colony_idx
        self.colony_name = COLONY_NAMES[colony_idx]
        self.state_dim = state_dim

        # E8 unit embedding for this colony (canonical 8D octonion)
        # e₀=0 (real part), e_{i+1}=1 for colony i (imaginary basis)
        self.e8_unit = torch.zeros(8)
        self.e8_unit[colony_idx + 1] = 1.0  # e₁ at index 1, e₂ at index 2, etc.

        # S⁷ unit embedding (7D imaginary part, derived from e8_unit)
        self.s7_unit = self.e8_unit[1:]  # e₁..e₇

        # Execution history tracking
        self._history: list[dict[str, Any]] = []

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return system prompt defining agent personality.

        Should include:
        - Colony identity and persona
        - Catastrophe dynamics
        - Voice/tone
        - Core competencies
        - Collaboration patterns
        """

    @abstractmethod
    def get_available_tools(self) -> list[str]:
        """Return list[Any] of tool names available to this agent.

        Examples:
        - Spark: ["brainstorm", "ideate", "explore"]
        - Forge: ["implement", "build", "code"]
        - Flow: ["debug", "fix", "recover"]
        - Grove: ["research", "explore", "document"]
        """

    @abstractmethod
    def process_with_catastrophe(self, task: str, context: dict[str, Any]) -> AgentResult:
        """Process task using colony's catastrophe dynamics.

        Args:
            task: Task description
            context: Execution context

        Returns:
            AgentResult with output and metadata
        """

    @abstractmethod
    def should_escalate(self, result: AgentResult, context: dict[str, Any]) -> bool:
        """Determine if result needs escalation to another colony.

        Args:
            result: Result from processing
            context: Execution context

        Returns:
            True if escalation needed
        """

    def get_embedding(self) -> torch.Tensor:
        """Get S⁷ embedding for this colony (7D imaginary part).

        Returns:
            7D unit vector on S⁷
        """
        return self.s7_unit

    def get_octonion_embedding(self) -> torch.Tensor:
        """Get full 8D octonion embedding for this colony.

        ADDED Dec 27, 2025 for coherency.

        Returns:
            8D octonion vector (e₀=0, e_{i+1}=1)
        """
        return self.e8_unit

    def get_octonion_state(self) -> Any:
        """Get OctonionState representation for this colony.

        Returns:
            OctonionState with this colony's canonical embedding
        """
        from kagami.core.unified_agents.octonion_state import OctonionState

        return OctonionState.from_colony_index(self.colony_idx)

    def normalize_to_s7(self, vector: torch.Tensor) -> torch.Tensor:
        """Normalize vector to S⁷ sphere (7D).

        Args:
            vector: Input vector (any dimension)

        Returns:
            Normalized vector same shape as input
        """
        return F.normalize(vector, dim=-1)

    def normalize_to_e8(self, vector: torch.Tensor) -> torch.Tensor:
        """Normalize vector to unit octonion (8D).

        Args:
            vector: Input 8D vector

        Returns:
            Unit octonion (8D, norm=1)
        """
        if vector.shape[-1] != 8:
            raise ValueError(f"Expected 8D vector, got {vector.shape[-1]}D")
        return F.normalize(vector, dim=-1)

    def execute(
        self,
        task: str,
        params: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        """Execute task with timing and history tracking.

        This is the primary entry point for agent execution. It wraps
        process_with_catastrophe() with:
        - Latency tracking
        - History recording
        - Metadata enrichment
        - Escalation checking

        Args:
            task: Task description
            params: Task parameters (unused currently)
            context: Execution context

        Returns:
            AgentResult with complete metadata
        """
        start_time = time.time()

        # Execute with catastrophe dynamics
        result = self.process_with_catastrophe(task, context)

        # Calculate latency
        result.latency = time.time() - start_time

        # Enrich metadata
        if result.metadata is None:
            result.metadata = {}
        result.metadata["colony"] = self.colony_name
        result.metadata["colony_idx"] = self.colony_idx
        result.metadata["catastrophe_type"] = getattr(self, "catastrophe_type", "unknown")

        # COHERENCY (Dec 27, 2025): Ensure e8_code is set[Any] for unified pipeline
        if result.e8_code is None:
            # Create e8_code from success state and colony identity
            e8_code = self.e8_unit.clone()
            # Modulate by success: positive real part for success, negative for failure
            real_part = 0.5 if result.success else -0.5
            e8_code[0] = real_part
            # Modulate colony component by success
            e8_code[self.colony_idx + 1] *= 1.0 if result.success else -0.5
            result.e8_code = F.normalize(e8_code, dim=-1)

        # Derive s7_embedding from e8_code for backward compatibility
        if result.s7_embedding is None and result.e8_code is not None:
            result.s7_embedding = result.e8_code[1:]  # e₁..e₇

        # Extract catastrophe state from metadata
        catastrophe_keys = [
            "activation",
            "fold_param_a",
            "cusp_param_a",
            "cusp_param_b",
            "ignition_occurred",
        ]
        result.catastrophe_state = {
            k: result.metadata.get(k) for k in catastrophe_keys if k in result.metadata
        }

        # Store e8_code in metadata for downstream extraction
        result.metadata["e8_code"] = result.e8_code
        result.metadata["s7_embedding"] = result.s7_embedding

        # Extract thoughts
        result.thoughts = result.metadata.get("thoughts", [])

        # Check escalation (add task to context for escalation logic)
        escalation_context = {**context, "task": task}
        if self.should_escalate(result, escalation_context):
            result.should_escalate = True
            # Generate escalation reason if not set[Any]
            if not result.escalation_reason:
                result.escalation_reason = (
                    f"{self.colony_name.capitalize()} suggests escalating to "
                    f"{result.escalation_target}"
                )

        # Record in history
        self._history.append(
            {
                "task": task,
                "result": result,
                "timestamp": start_time,
            }
        )

        return result

    def get_history(self) -> list[dict[str, Any]]:
        """Get execution history.

        Returns:
            List of execution records with task, result, timestamp
        """
        return self._history

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(colony={self.colony_name}, idx={self.colony_idx})"


__all__ = [
    "AgentResult",
    "BaseColonyAgent",
]
