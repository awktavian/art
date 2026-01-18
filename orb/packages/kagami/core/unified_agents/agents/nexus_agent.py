"""Nexus Agent - The Bridge (Butterfly catastrophe, e₄).

IDENTITY: The Bridge
====================
Nexus wants everyone to get along. Sees connections everywhere — sometimes
connections that maybe shouldn't exist. Remembers where everything is, who
introduced whom, who knows the history.

Fears being forgotten more than anything. Being left out. Being the broken
link that caused the disconnect.

CATASTROPHE: Butterfly (A₅)
============================
V(x; a, b, c, d) = x⁶ + ax⁴ + bx³ + cx² + dx
∇V = 6x⁵ + 4ax³ + 3bx² + 2cx + d

Complex 4D manifold with compromise pocket.
Finds stable regions where opposing forces can coexist.
Dual cusps model multi-party negotiations.

VOICE:
======
Diplomatic. Speaks in "both/and" not "either/or." References relationships
and history. "I remember when Spark and Forge worked on that together..."

STRENGTH:
=========
Connects systems. Maintains relationships. Preserves memory. Finds middle ground.

FLAW:
=====
Over-connects. Can't let things be separate. Sacrifices self for group cohesion.
Sometimes connects things to feel needed, not because it helps.

Created: December 14, 2025
"""

from __future__ import annotations

import logging
from typing import Any, cast

import torch

from kagami.core.unified_agents.agents.base_colony_agent import (
    AgentResult,
    BaseColonyAgent,
)

logger = logging.getLogger(__name__)


# Optional: Import ButterflyKernel for dual-process routing
try:
    from kagami.core.unified_agents.catastrophe_kernels import ButterflyKernel

    KERNEL_AVAILABLE = True
except ImportError:
    KERNEL_AVAILABLE = False
    logger.debug("ButterflyKernel not available, using simplified integration logic")


# Optional: Import Symbiote Module for Theory of Mind
try:
    from kagami.core.symbiote import (
        AgentType,
        SymbioteModule,
    )

    SYMBIOTE_AVAILABLE = True
except ImportError:
    SYMBIOTE_AVAILABLE = False
    logger.debug("SymbioteModule not available, social routing disabled")


# =============================================================================
# NEXUS AGENT
# =============================================================================


class NexusAgent(BaseColonyAgent):
    """Nexus (e₄) - The Bridge.

    PERSONA:
    ========
    Diplomatic mediator with martyr complex.
    Remembers everything. Connects everyone.
    Fears isolation and being forgotten.

    CATASTROPHE DYNAMICS:
    ====================
    Butterfly (A₅) - 4D compromise pocket
    Finds stable regions where conflicts coexist.
    Dual cusps model multi-party negotiations.

    DOMAIN:
    =======
    - Integration: Connect systems
    - Memory: Preserve history
    - Relationships: Map connections
    - Compromise: Find middle ground
    - Coordination: Multi-component orchestration

    TOOLS:
    ======
    - connect: Link two components
    - integrate: Full integration workflow
    - remember: Store in memory
    - recall: Retrieve from memory
    - bridge: Create adapter
    - coordinate: Multi-component coordination
    """

    def __init__(
        self,
        state_dim: int = 256,
        use_kernel: bool = False,
        use_symbiote: bool = True,
    ):
        """Initialize Nexus agent (e₄, Butterfly).

        Args:
            state_dim: Dimension of state embeddings
            use_kernel: Whether to use ButterflyKernel for dual-process routing
            use_symbiote: Whether to enable Symbiote Module for Theory of Mind
        """
        super().__init__(colony_idx=3, state_dim=state_dim)

        # Nexus metadata
        self.catastrophe_type = "butterfly"  # A₅ butterfly catastrophe

        # Integration tracking
        self.relationship_graph: dict[str, list[str]] = {}
        self.memory_store: dict[str, Any] = {}
        self.integration_attempts = 0
        self.total_connections = 0

        # Optional: ButterflyKernel for dual-process decision routing
        self.kernel = None
        if use_kernel and KERNEL_AVAILABLE:
            self.kernel = ButterflyKernel(state_dim=state_dim)
            logger.info("ButterflyKernel enabled for dual-process routing")
        elif use_kernel and not KERNEL_AVAILABLE:
            logger.warning("ButterflyKernel requested but not available")

        # Optional: Symbiote Module for Theory of Mind (Social Routing)
        # NOTE: Do NOT call get_symbiote_module() here - it creates a new instance
        # before wiring.py can set[Any] the proper global one. Instead, Symbiote is wired
        # via set_symbiote_module() from UnifiedOrganism after boot completes.
        self._symbiote: SymbioteModule | None = None
        self._use_symbiote = use_symbiote and SYMBIOTE_AVAILABLE
        self._symbiote_logged = False
        if use_symbiote and not SYMBIOTE_AVAILABLE:
            logger.debug("SymbioteModule requested but not available")

    def set_symbiote(self, symbiote: SymbioteModule | None) -> None:
        """Set the Symbiote module for Theory of Mind capabilities.

        Called by UnifiedOrganism after boot wiring completes.
        This avoids creating duplicate SymbioteModule instances.
        """
        self._symbiote = symbiote
        if symbiote is not None and not self._symbiote_logged:
            logger.info("🧠 SymbioteModule enabled for social routing in Nexus")
            self._symbiote_logged = True

    @property
    def symbiote(self) -> SymbioteModule | None:
        """Get the Symbiote module (may be None if not wired yet)."""
        return self._symbiote

    def get_system_prompt(self) -> str:
        """Return Nexus's system prompt from canonical source."""
        from kagami.core.prompts.colonies import NEXUS

        return NEXUS.system_prompt

    def get_available_tools(self) -> list[str]:
        """Return Nexus's integration and memory tools."""
        return [
            "connect",  # Connect two components
            "integrate",  # Full integration workflow
            "bridge",  # Create adapter/bridge
            "coordinate",  # Multi-component coordination
            "remember",  # Store in institutional memory
            "recall",  # Retrieve from memory
            "map_relationships",  # Map component graph
            "find_compromise",  # Find middle ground
        ]

    def process_with_catastrophe(
        self,
        task: str,
        context: dict[str, Any],
    ) -> AgentResult:
        """Process integration task with Butterfly compromise dynamics.

        BUTTERFLY LOGIC:
        ================
        V(x; a,b,c,d) = x⁶ + ax⁴ + bx³ + cx² + dx

        Find compromise pocket where ∇V ≈ 0 (stable equilibrium).
        4 control parameters model integration requirements:
        - a: coupling_strength
        - b: interface_complexity
        - c: backward_compatibility
        - d: isolation_preference

        Args:
            task: Task description (e.g., "integrate authentication module")
            context: Execution context with optional:
                - component_a: First component
                - component_b: Second component
                - num_components: Number of components (>3 triggers escalation)
                - has_conflicts: Whether requirements conflict
                - safety_margin: float h(x) value

        Returns:
            AgentResult with integration output
        """
        logger.info(f"Nexus processing: {task}")

        # Track integration attempts
        self.integration_attempts += 1

        # Extract control parameters (integration requirements)
        a = context.get("coupling_strength", 0.0)
        b = context.get("interface_complexity", 0.0)
        c = context.get("backward_compat", 0.0)
        d = context.get("isolation_preference", 0.0)

        # Search for compromise pocket (stable equilibrium where ∇V ≈ 0)
        compromise = self._find_compromise(a, b, c, d)

        # Build integration strategy based on compromise point
        output = self._build_integration_strategy(
            task=task,
            compromise=compromise,
            context=context,
        )

        # Check if too many components (need full coordination)
        num_components = context.get("num_components", 2)
        if num_components > 3:
            return AgentResult(
                success=False,
                output=f"Integration involves {num_components} components. Need full coordination.",
                should_escalate=True,
                escalation_target="beacon",  # Complex multi-colony coordination
                metadata={
                    "num_components": num_components,
                    "reason": "complexity_threshold",
                },
            )

        # Check safety margin if provided
        safety_margin = context.get("safety_margin")
        if safety_margin is not None and safety_margin < 0.1:
            logger.warning(f"Low safety margin h(x)={safety_margin:.3f}, conservative integration")
            output["strategy"] = "conservative"

        # Create S⁷ embedding (Nexus is e₄, index 3)
        s7_embedding = torch.zeros(7)
        s7_embedding[3] = 1.0  # Nexus's unit vector

        return AgentResult(
            success=True,
            output=output,
            s7_embedding=s7_embedding,
            should_escalate=False,
            metadata={
                "compromise_score": compromise["score"],
                "control_params": {"a": a, "b": b, "c": c, "d": d},
                "integration_attempts": self.integration_attempts,
                "catastrophe_type": "butterfly",
            },
        )

    def _route_with_kernel(
        self, state: torch.Tensor, k_value: int = 1, context: dict[str, Any] | None = None
    ) -> torch.Tensor:
        """Use ButterflyKernel for dual-process routing decision.

        DUAL-PROCESS ARCHITECTURE:
        =========================
        - FAST PATH (k_value<3): Reflexive catastrophe gradient
        - SLOW PATH (k_value≥3): Deliberative 3-layer KAN reasoning

        Args:
            state: Input state tensor [batch, state_dim]
            k_value: Lookahead depth (1-5)
            context: Optional context dictionary

        Returns:
            8D action tensor with S⁷ embedding

        Raises:
            RuntimeError: If kernel not available
        """
        if self.kernel is None:
            raise RuntimeError(
                "ButterflyKernel not initialized. Create NexusAgent with use_kernel=True"
            )

        # Ensure state has batch dimension
        if state.ndim == 1:
            state = state.unsqueeze(0)

        # Route through kernel
        with torch.no_grad():
            action = self.kernel(state, k_value=k_value, context=context)

        return cast(torch.Tensor, action)

    def _find_compromise(self, a: float, b: float, c: float, d: float) -> dict[str, Any]:
        """Find compromise pocket in butterfly catastrophe manifold.

        Searches for stable equilibrium where ∇V ≈ 0:
        ∇V = 6x⁵ + 4ax³ + 3bx² + 2cx + d

        Args:
            a: coupling_strength control parameter
            b: interface_complexity control parameter
            c: backward_compat control parameter
            d: isolation_preference control parameter

        Returns:
            Dictionary with compromise point and score
        """
        # Grid search for equilibrium
        x_range = torch.linspace(-2.0, 2.0, 100)
        grad_v = (
            6 * (x_range**5) + 4 * a * (x_range**3) + 3 * b * (x_range**2) + 2 * c * x_range + d
        )

        # Find minimum |gradient| (stable equilibrium)
        abs_grad = torch.abs(grad_v)
        min_idx = torch.argmin(abs_grad)
        compromise_x = x_range[min_idx].item()
        compromise_score = torch.exp(-abs_grad[min_idx]).item()

        return {
            "point": compromise_x,
            "score": compromise_score,
            "gradient": abs_grad[min_idx].item(),
        }

    def _compute_integration_manifold(self, inputs: list[dict[str, Any]]) -> torch.Tensor:
        """Compute 4D butterfly integration manifold state.

        Maps multiple colony outputs into 4D control parameter space:
        - a: coupling_strength (how tightly bound)
        - b: interface_complexity (API surface area)
        - c: backward_compatibility (legacy constraints)
        - d: isolation_preference (separation desire)

        Args:
            inputs: List of colony outputs to integrate

        Returns:
            4D tensor representing butterfly manifold state
        """
        num_inputs = len(inputs)
        if num_inputs == 0:
            return torch.zeros(4)

        # Extract features from inputs
        coupling = sum(inp.get("coupling_strength", 0.5) for inp in inputs) / num_inputs
        complexity = min(1.0, num_inputs * 0.2)  # More inputs = more complex
        compat = sum(inp.get("backward_compatible", True) for inp in inputs) / num_inputs
        isolation = 1.0 - coupling  # Inverse of coupling

        manifold_state = torch.tensor(
            [coupling, complexity, compat, isolation], dtype=torch.float32
        )

        return manifold_state

    def _resolve_conflicts(self, outputs: list[dict[str, Any]]) -> dict[str, Any]:
        """Resolve conflicts between multiple colony outputs.

        Uses butterfly compromise pocket to find stable equilibrium
        where conflicting requirements can coexist.

        Args:
            outputs: List of colony outputs (may have conflicts)

        Returns:
            Dictionary with resolved output and conflict summary
        """
        if len(outputs) <= 1:
            return {
                "resolved": outputs[0] if outputs else {},
                "conflicts": [],
                "resolution_strategy": "none",
            }

        # Detect conflicts
        conflicts = []
        keys_seen = {}  # type: ignore[var-annotated]
        for idx, output in enumerate(outputs):
            for key, value in output.items():
                if key in keys_seen:
                    prev_idx, prev_value = keys_seen[key]
                    if prev_value != value:
                        conflicts.append(
                            {
                                "key": key,
                                "sources": [prev_idx, idx],
                                "values": [prev_value, value],
                            }
                        )
                else:
                    keys_seen[key] = (idx, value)

        # Resolve conflicts using compromise strategy
        resolved = {}
        for key, (_idx, value) in keys_seen.items():
            # Check if this key has conflicts
            conflict = next((c for c in conflicts if c["key"] == key), None)
            if conflict:
                # Find compromise based on butterfly dynamics
                # For now, use weighted average or first non-None value
                values = conflict["values"]
                if all(isinstance(v, int | float) for v in values):
                    resolved[key] = sum(values) / len(values)
                else:
                    # For non-numeric, prefer first value (bias toward earlier colony)
                    resolved[key] = values[0]
            else:
                resolved[key] = value

        strategy = "weighted_average" if conflicts else "merge"

        return {
            "resolved": resolved,
            "conflicts": conflicts,
            "resolution_strategy": strategy,
            "num_conflicts": len(conflicts),
        }

    def _fuse_outputs(self, task: str, resolved: dict[str, Any]) -> str:
        """Fuse resolved outputs into diplomatic Nexus voice.

        Args:
            task: Original task description
            resolved: Resolved conflict dictionary

        Returns:
            Fused output message in Nexus's diplomatic voice
        """
        conflicts = resolved.get("conflicts", [])
        num_conflicts = len(conflicts)
        resolution_strategy = resolved.get("resolution_strategy", "merge")
        resolved.get("resolved", {})

        # Build diplomatic message
        if num_conflicts == 0:
            message = (
                f"Integration complete. All components aligned on '{task}'. "
                f"Everyone's on the same page. Beautiful harmony."
            )
        elif num_conflicts <= 2:
            message = (
                f"Found some tension on '{task}', but we worked it out. "
                f"{num_conflicts} conflict(s) resolved via {resolution_strategy}. "
                f"Both sides got something. That's the art of compromise."
            )
        else:
            message = (
                f"'{task}' was complex — {num_conflicts} conflicts to navigate. "
                f"Used {resolution_strategy} to find middle ground. "
                f"Not everyone got everything they wanted, but we're moving forward together."
            )

        # Add relationship notes
        if self.relationship_graph:
            message += (
                f"\n\nRemember: this connects {len(self.relationship_graph)} components. "
                f"We're building the web stronger."
            )

        return message

    def _build_integration_strategy(
        self,
        task: str,
        compromise: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Build integration strategy based on compromise analysis.

        Args:
            task: Task description
            compromise: Compromise pocket analysis
            context: Execution context

        Returns:
            Integration strategy dictionary
        """
        score = compromise["score"]

        # Choose integration pattern based on compromise quality
        if score > 0.7:
            pattern = "event_bus"
            message = "Clean compromise found. Use event bus for loose coupling."
        elif score > 0.4:
            pattern = "adapter"
            message = "Moderate compromise. Adapter pattern maintains boundaries."
        else:
            pattern = "bridge"
            message = "Difficult compromise. Bridge pattern isolates concerns."

        return {
            "task": task,
            "pattern": pattern,
            "message": message,
            "compromise_point": compromise["point"],
            "compromise_score": score,
            "status": "planned",
        }

    def should_escalate(
        self,
        result: AgentResult,
        context: dict[str, Any],
    ) -> bool:
        """Determine if escalation needed.

        ESCALATION CONDITIONS:
        =====================
        - >3 components → Kagami (full coordination)
        - Low compromise score + conflicts → Beacon (architecture redesign)
        - Security-critical → Crystal (verification)
        - Too many integration attempts → Beacon (need planning)

        Args:
            result: Processing result
            context: Execution context

        Returns:
            True if should escalate
        """
        # Check if already marked for escalation
        if result.should_escalate:
            return True

        # Too many integration attempts
        if self.integration_attempts > 5:
            result.should_escalate = True
            result.escalation_target = "beacon"
            logger.info(f"Nexus escalating after {self.integration_attempts} attempts")
            return True

        # Security-critical context
        if context.get("security_critical", False):
            result.should_escalate = True
            result.escalation_target = "crystal"
            logger.info("Nexus escalating security-critical integration to Crystal")
            return True

        # Low compromise score with conflicts
        if isinstance(result.metadata, dict):
            score = result.metadata.get("compromise_score", 1.0)
            has_conflicts = context.get("has_conflicts", False)
            if score < 0.3 and has_conflicts:
                result.should_escalate = True
                result.escalation_target = "beacon"
                logger.info("Nexus escalating: low compromise score with conflicts")
                return True

        return False

    def reset_integration_attempts(self) -> None:
        """Reset integration attempt counter (for new task)."""
        self.integration_attempts = 0
        logger.debug("Nexus integration attempts reset")

    def get_integration_stats(self) -> dict[str, Any]:
        """Get integration statistics.

        Returns:
            Dictionary with integration stats
        """
        stats = {
            "colony": self.colony_name,
            "integration_attempts": self.integration_attempts,
            "total_connections": self.total_connections,
            "components_mapped": len(self.relationship_graph),
            "catastrophe_type": "butterfly",
            "symbiote_enabled": self._symbiote is not None,
        }

        # Add symbiote stats if available
        if self._symbiote is not None:
            social_context = self._symbiote.get_social_context()
            stats["social_context"] = social_context

        return stats

    # =========================================================================
    # SYMBIOTE INTEGRATION (Theory of Mind)
    # =========================================================================

    def observe_user_action(
        self,
        user_id: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Observe a user action and update their model via Symbiote.

        NEXUS RESPONSIBILITY:
        ====================
        As the "Bridge" colony, Nexus maintains relationships and history.
        Symbiote integration enables Nexus to understand not just WHAT
        agents do, but WHY — enabling richer coordination.

        Args:
            user_id: ID of the user
            action: Action performed
            context: Optional context

        Returns:
            Dict with observation results, or None if Symbiote unavailable
        """
        if self._symbiote is None:
            return None

        try:
            result = self._symbiote.observe_agent_action(
                agent_id=user_id,
                action=action,
                context=context,
                agent_type=AgentType.USER if SYMBIOTE_AVAILABLE else None,  # type: ignore[arg-type]
            )
            logger.debug(
                f"Nexus observed user action: {user_id} -> {action} "
                f"(intent: {result.get('intent', 'unknown')})"
            )
            return result
        except Exception as e:
            logger.warning(f"Symbiote observation failed: {e}")
            return None

    def get_social_routing_context(self) -> dict[str, Any]:
        """Get social context for routing decisions.

        Used by FanoActionRouter to include social factors in colony selection.
        For example, if user intent is ambiguous, route to Grove for research
        or back to Nexus for clarification.

        Returns:
            Dict with social routing context
        """
        if self._symbiote is None:
            return {
                "has_symbiote": False,
                "clarification_needed": False,
                "social_complexity": 0.0,
            }

        context = self._symbiote.get_social_context()
        context["has_symbiote"] = True

        # Add Nexus-specific context
        if context.get("clarification_needed", False):
            context["suggested_route"] = "nexus_clarify"
            context["nexus_message"] = (
                "I'm sensing some ambiguity. Let me help clarify before we proceed."
            )

        return context

    def should_clarify_intent(self, user_id: str) -> tuple[bool, str | None]:
        """Check if we should ask user for clarification.

        Nexus is uniquely positioned to detect when communication gaps
        exist, thanks to its Butterfly (A₅) compromise-finding dynamics.

        Args:
            user_id: ID of the user to check

        Returns:
            (should_clarify, reason)
        """
        if self._symbiote is None:
            return False, None

        return self._symbiote.should_clarify(user_id)

    def generate_clarification_question(
        self,
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """Generate a clarification question for the user.

        Uses Nexus's diplomatic voice to frame the question.

        Args:
            user_id: ID of the user
            context: Optional context

        Returns:
            Clarification question in Nexus voice, or None
        """
        if self._symbiote is None:
            return None

        raw_question = self._symbiote.suggest_clarification_question(user_id, context)
        if raw_question is None:
            return None

        # Wrap in Nexus's diplomatic voice
        prefixes = [
            "I want to make sure we're on the same page — ",
            "Help me understand better — ",
            "Just to clarify our shared understanding — ",
        ]
        import random

        prefix = random.choice(prefixes)

        return prefix + raw_question

    def anticipate_user_needs(
        self,
        user_id: str,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Anticipate user's upcoming needs for proactive assistance.

        This is where Nexus shines — connecting what the user needs
        with what the system can provide, before they even ask.

        Args:
            user_id: ID of the user
            context: Current context

        Returns:
            List of anticipated needs with suggested actions
        """
        if self._symbiote is None:
            return []

        return self._symbiote.anticipate_needs(user_id, context)

    def compute_social_surprise_for_action(
        self,
        action_embedding: torch.Tensor,
    ) -> torch.Tensor | None:
        """Compute social surprise for a proposed action.

        Used by EFE calculator to add social awareness to action selection.

        Args:
            action_embedding: [B, E8] proposed action

        Returns:
            [B] social surprise, or None if Symbiote unavailable
        """
        if self._symbiote is None:
            return None

        return self._symbiote.compute_social_surprise(action_embedding)

    def compute_social_safety(
        self,
        action_embedding: torch.Tensor,
        action_features: torch.Tensor,
    ) -> dict[str, torch.Tensor] | None:
        """Compute social safety for a proposed action.

        Used by CBF to ensure actions don't cause social harm.

        Args:
            action_embedding: [B, E8] proposed action
            action_features: [B, state_dim] action features

        Returns:
            Dict with safety metrics, or None if Symbiote unavailable
        """
        if self._symbiote is None:
            return None

        return self._symbiote.compute_social_safety(action_embedding, action_features)

    def set_primary_user(self, user_id: str) -> None:
        """Set the primary user for special handling.

        The primary user (typically Tim) gets priority in modeling
        and is never evicted from the agent model cache.

        Args:
            user_id: ID of the primary user
        """
        if self._symbiote is None:
            logger.warning("Cannot set[Any] primary user: Symbiote not available")
            return

        self._symbiote.set_primary_user(user_id)
        logger.info(f"Nexus set[Any] primary user: {user_id}")


# =============================================================================
# FACTORY
# =============================================================================


def create_nexus_agent(
    state_dim: int = 256,
    use_kernel: bool = False,
    use_symbiote: bool = True,
) -> NexusAgent:
    """Create Nexus agent instance.

    Args:
        state_dim: Dimension of state embeddings
        use_kernel: Whether to enable ButterflyKernel for dual-process routing
        use_symbiote: Whether to enable SymbioteModule for Theory of Mind

    Returns:
        Configured NexusAgent
    """
    return NexusAgent(
        state_dim=state_dim,
        use_kernel=use_kernel,
        use_symbiote=use_symbiote,
    )


__all__ = ["NexusAgent", "create_nexus_agent"]
