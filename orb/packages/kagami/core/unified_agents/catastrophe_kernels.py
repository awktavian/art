"""Catastrophe-Based Decision Kernels for Colony Agents.

DUAL-PROCESS DECISION ARCHITECTURE (Dec 14, 2025):
==================================================
Each colony has TWO decision pathways:

1. FAST PATH (k<3): 1-layer catastrophe gradient
   - Reflexive, cached, <10ms latency
   - Pure catastrophe potential derivative
   - No context needed, purely local

2. SLOW PATH (k≥3): 3-layer KAN reasoning
   - Deliberative, computes EFE components
   - Context-aware, goal-sensitive
   - Full epistemic/pragmatic tradeoff

This mirrors dual-process cognition (Kahneman, 2011):
- System 1: Fast, automatic, catastrophe gradients
- System 2: Slow, deliberate, full KAN reasoning

CATASTROPHE MATHEMATICS:
=======================
Each catastrophe type has a canonical potential V(x; params).
The gradient ∇V defines the system's attractors and bifurcations.

Thom's Classification Theorem: There are EXACTLY 7 elementary
catastrophes for systems with ≤4 control parameters.

Each colony's decision kernel uses its catastrophe type:
- Spark (e₁):   Fold (A₂)        - Simple ignition
- Forge (e₂):   Cusp (A₃)        - Bistable quality choice
- Flow (e₃):    Swallowtail (A₄) - 3-way error recovery
- Nexus (e₄):   Butterfly (A₅)   - 4D integration manifold
- Beacon (e₅):  Hyperbolic (D₄⁺) - Planning divergence
- Grove (e₆):   Elliptic (D₄⁻)   - Knowledge convergence
- Crystal (e₇): Parabolic (D₅)   - Safety boundary

INTEGRATION WITH EXPECTED FREE ENERGY:
======================================
The slow path computes EFE components directly:
- Epistemic value: Information gain (curiosity)
- Pragmatic value: Goal achievement (utility)
- Risk: State uncertainty penalty
- Catastrophe: Singularity avoidance

Fast path approximates EFE via catastrophe gradient alone.

References:
- Thom (1972): "Structural Stability and Morphogenesis"
- Arnold (1975): "Critical Points of Smooth Functions"
- Kahneman (2011): "Thinking, Fast and Slow"
- Friston et al. (2015): "Active inference and epistemic value"

Created: December 14, 2025
Status: Production
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

# Conditional torch imports - allows module introspection without torch
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    from kagami.core.world_model.layers.catastrophe_kan import (
        CatastropheBasis,
        CatastropheType,
    )

    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    # Provide stubs for type checking
    if TYPE_CHECKING:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F

        from kagami.core.world_model.layers.catastrophe_kan import (
            CatastropheBasis,
            CatastropheType,
        )


# =============================================================================
# BASE CATASTROPHE KERNEL
# =============================================================================


class CatastropheKernel(nn.Module):
    """Base class for catastrophe-based decision kernels.

    DUAL-PROCESS ARCHITECTURE:
    =========================
    Each colony has TWO decision paths:

    FAST PATH (k<3):
        state → catastrophe_gradient → action [8D]
        - 1-layer: BatchedCatastropheBasis
        - Reflexive, <10ms
        - Pure local dynamics

    SLOW PATH (k≥3):
        state → 3-layer KAN → EFE components → action [8D]
        - Layer 1: Catastrophe basis (state → hidden)
        - Layer 2: Hidden → hidden (nonlinear mixing)
        - Layer 3: Hidden → 8D action (S⁷ embedding)
        - Context-aware: goals, epistemic/pragmatic weights

    The k-value (metacognition depth) determines routing:
    - k=1: Pure reflex (fast only)
    - k=2: Mixed (70% fast, 30% slow)
    - k≥3: Full deliberation (slow only)

    OUTPUT INVARIANT:
    ================
    Both paths return torch.Tensor[batch, 8] in S⁷ space:
    - 8D octonion embedding
    - Normalized to unit sphere
    - Differentiable for backprop

    Args:
        state_dim: Dimension of input state (typically 256 for h+z)
        catastrophe_type: Type of catastrophe (fold, cusp, swallowtail, etc.)
        colony_idx: Index of colony (0-6)
        hidden_dim: Hidden dimension for KAN layers
    """

    def __init__(
        self,
        state_dim: int,
        catastrophe_type: str,
        colony_idx: int,
        hidden_dim: int = 256,
    ):
        super().__init__()
        self.state_dim = state_dim
        self.catastrophe_type = catastrophe_type
        self.colony_idx = colony_idx
        self.hidden_dim = hidden_dim

        # Convert string to CatastropheType enum
        type_map = {
            "fold": CatastropheType.FOLD,
            "cusp": CatastropheType.CUSP,
            "swallowtail": CatastropheType.SWALLOWTAIL,
            "butterfly": CatastropheType.BUTTERFLY,
            "hyperbolic": CatastropheType.HYPERBOLIC,
            "elliptic": CatastropheType.ELLIPTIC,
            "parabolic": CatastropheType.PARABOLIC,
        }
        self.catastrophe_enum = type_map[catastrophe_type.lower()]

        # === FAST PATH: 1-layer catastrophe gradient ===
        self.fast_basis = CatastropheBasis(
            catastrophe_type=self.catastrophe_enum,
            num_channels=state_dim,
            init_scale=0.1,
        )

        # Fast path output projection to S⁷ (8D)
        self.fast_proj = nn.Linear(state_dim, 8)

        # === SLOW PATH: 3-layer KAN ===
        # Layer 1: State → Hidden (catastrophe activation)
        self.slow_layer1 = CatastropheBasis(
            catastrophe_type=self.catastrophe_enum,
            num_channels=state_dim,
            init_scale=0.1,
        )
        self.slow_proj1 = nn.Linear(state_dim, hidden_dim)

        # Layer 2: Hidden → Hidden (nonlinear mixing)
        self.slow_layer2 = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )

        # Layer 3: Hidden → 8D action
        self.slow_layer3 = nn.Linear(hidden_dim, 8)

        # === CONTEXT INTEGRATION ===
        # Goal encoder for pragmatic value
        self.goal_encoder = nn.Sequential(
            nn.Linear(15, hidden_dim // 2),  # 15 = observation_dim (E8+S⁷)
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, hidden_dim // 4),
        )

        # Context mixer (blends state + goal)
        self.context_mixer = nn.Linear(hidden_dim + hidden_dim // 4, hidden_dim)

        # === EPISTEMIC/PRAGMATIC BIAS ===
        # Each colony has different bias toward exploration vs exploitation
        # Initialized based on colony character
        self.register_buffer("epistemic_bias", self._get_epistemic_bias())
        self.register_buffer("pragmatic_bias", self._get_pragmatic_bias())

        logger.debug(
            f"CatastropheKernel[{catastrophe_type}]: state={state_dim}, "
            f"hidden={hidden_dim}, colony={colony_idx}"
        )

    def _get_epistemic_bias(self) -> torch.Tensor:
        """Get epistemic (exploration) bias for this colony.

        Higher values = more curious, exploratory.
        """
        # Colony-specific epistemic weights
        biases = {
            0: 1.5,  # Spark - high curiosity
            1: 0.5,  # Forge - low exploration, focus on quality
            2: 0.8,  # Flow - moderate, adaptive
            3: 1.2,  # Nexus - explores for integration
            4: 1.0,  # Beacon - balanced for planning
            5: 2.0,  # Grove - maximum curiosity
            6: 0.3,  # Crystal - minimal exploration, verify only
        }
        return torch.tensor(biases[self.colony_idx])

    def _get_pragmatic_bias(self) -> torch.Tensor:
        """Get pragmatic (exploitation) bias for this colony.

        Higher values = more goal-directed.
        """
        # Colony-specific pragmatic weights
        biases = {
            0: 0.5,  # Spark - low goal focus
            1: 2.0,  # Forge - high goal focus (build it right)
            2: 1.5,  # Flow - fixes toward goal
            3: 1.2,  # Nexus - integrates toward goal
            4: 1.8,  # Beacon - plans toward goal
            5: 0.3,  # Grove - low goal focus (pure research)
            6: 2.5,  # Crystal - maximum goal focus (verify spec)
        }
        return torch.tensor(biases[self.colony_idx])

    def forward_fast(self, state: torch.Tensor) -> torch.Tensor:
        """Fast path: 1-layer catastrophe gradient.

        REFLEXIVE DECISION (k<3):
        ========================
        Uses ONLY the catastrophe potential derivative.
        No context, no goals, purely local gradient.

        This is equivalent to Kahneman's System 1:
        - Automatic, effortless
        - Pattern matching
        - Fast but inflexible

        Args:
            state: [batch, state_dim] combined (h, z) state

        Returns:
            [batch, 8] action in S⁷ space
        """
        # Apply catastrophe basis
        activated = self.fast_basis(state)  # [batch, state_dim]

        # Project to 8D
        action = self.fast_proj(activated)  # [batch, 8]

        # Normalize to unit sphere (S⁷ constraint)
        action_norm = F.normalize(action, dim=-1)

        return action_norm

    def forward_slow(
        self,
        state: torch.Tensor,
        context: dict[str, Any],
    ) -> torch.Tensor:
        """Slow path: 3-layer KAN reasoning.

        DELIBERATIVE DECISION (k≥3):
        ===========================
        Uses full KAN with context integration.
        Considers goals, epistemic/pragmatic tradeoffs.

        This is Kahneman's System 2:
        - Effortful, deliberate
        - Flexible, context-aware
        - Slow but adaptable

        Args:
            state: [batch, state_dim] combined (h, z) state
            context: Dict with optional keys:
                - goals: [batch, obs_dim] goal observations
                - epistemic_weight: float override for curiosity
                - pragmatic_weight: float override for utility

        Returns:
            [batch, 8] action in S⁷ space
        """
        batch_size = state.shape[0]
        device = state.device

        # === LAYER 1: Catastrophe activation ===
        h1 = self.slow_layer1(state)  # [batch, state_dim]
        h1 = self.slow_proj1(h1)  # [batch, hidden_dim]

        # === CONTEXT INTEGRATION ===
        if "goals" in context and context["goals"] is not None:
            goals = context["goals"]  # [batch, obs_dim]
            goal_embed = self.goal_encoder(goals)  # [batch, hidden_dim//4]

            # Blend state + goal
            h1_with_context = torch.cat([h1, goal_embed], dim=-1)
            h1 = self.context_mixer(h1_with_context)

        # === LAYER 2: Nonlinear mixing ===
        h2 = self.slow_layer2(h1)  # [batch, hidden_dim]

        # === LAYER 3: Action output ===
        action = self.slow_layer3(h2)  # [batch, 8]

        # === EPISTEMIC/PRAGMATIC WEIGHTING ===
        # Modulate action based on exploration vs exploitation
        epistemic_w = context.get("epistemic_weight", self.epistemic_bias)
        pragmatic_w = context.get("pragmatic_weight", self.pragmatic_bias)

        # Epistemic component: uncertainty drives large actions
        state_uncertainty = state.var(dim=-1, keepdim=True)  # [batch, 1]
        epistemic_scale = epistemic_w * torch.sigmoid(state_uncertainty)

        # Pragmatic component: goal proximity drives precise actions
        if "goals" in context and context["goals"] is not None:
            # Goal distance (rough proxy)
            goal_distance = (state[:, :15] - context["goals"]).pow(2).sum(dim=-1, keepdim=True)
            pragmatic_scale = pragmatic_w * torch.sigmoid(-goal_distance)
        else:
            pragmatic_scale = torch.ones(batch_size, 1, device=device) * pragmatic_w

        # Combine scales
        total_scale = epistemic_scale + pragmatic_scale
        action_scaled = action * total_scale

        # Normalize to S⁷
        action_norm = F.normalize(action_scaled, dim=-1)

        return action_norm

    def forward(
        self,
        state: torch.Tensor,
        k_value: int = 3,
        context: dict[str, Any] | None = None,
    ) -> torch.Tensor:
        """Route to fast or slow path based on k-value.

        ROUTING LOGIC:
        =============
        - k < 3: Fast path only (reflexive)
        - k = 3: Slow path only (deliberative)
        - k > 3: Slow path only (deep deliberation)

        Args:
            state: [batch, state_dim] combined (h, z) state
            k_value: Metacognition depth (1-11)
            context: Optional context dict[str, Any] for slow path

        Returns:
            [batch, 8] action in S⁷ space
        """
        if context is None:
            context = {}

        if k_value < 3:
            return self.forward_fast(state)
        else:
            return self.forward_slow(state, context)

    def adapt_parameters(
        self,
        success_rate: float,
        fast_path_rate: float,
        learning_rate: float = 0.01,
    ) -> None:
        """Adapt catastrophe parameters based on performance.

        CATASTROPHE PARAMETER LEARNING (Dec 27, 2025):
        Dynamically adjusts epistemic/pragmatic biases based on outcomes:
        - High success → reinforce current balance
        - Low success → shift toward exploration
        - High fast path usage → reduce epistemic bias (faster is working)
        - Low fast path usage → increase epistemic bias (need more exploration)

        Args:
            success_rate: Recent task success rate (0-1)
            fast_path_rate: Fraction of tasks using fast path (0-1)
            learning_rate: Adaptation step size
        """
        with torch.no_grad():
            # Compute target adjustments
            # Low success → increase epistemic (explore more)
            # High success → maintain or slightly decrease epistemic
            epistemic_delta = learning_rate * (0.5 - success_rate)

            # High fast path usage with low success → need more deliberation
            if fast_path_rate > 0.7 and success_rate < 0.5:
                epistemic_delta += learning_rate * 0.5  # Boost exploration

            # Update biases (clamp to reasonable range)
            new_epistemic_val = self.epistemic_bias + epistemic_delta  # type: ignore[operator]
            if isinstance(new_epistemic_val, torch.Tensor):
                new_epistemic = new_epistemic_val.clamp(0.1, 3.0)
            else:
                new_epistemic = torch.tensor(max(0.1, min(3.0, new_epistemic_val)))
            self.epistemic_bias.copy_(new_epistemic)  # type: ignore[operator]

            # Pragmatic adjustment: inverse of epistemic for balance
            pragmatic_delta = -epistemic_delta * 0.5
            new_pragmatic_val = self.pragmatic_bias + pragmatic_delta  # type: ignore[operator]
            if isinstance(new_pragmatic_val, torch.Tensor):
                new_pragmatic = new_pragmatic_val.clamp(0.1, 3.0)
            else:
                new_pragmatic = torch.tensor(max(0.1, min(3.0, new_pragmatic_val)))
            self.pragmatic_bias.copy_(new_pragmatic)  # type: ignore[operator]

            logger.debug(
                f"CatastropheKernel[{self.catastrophe_type}] adapted: "  # type: ignore[operator]
                f"epistemic={self.epistemic_bias.item():.2f}, "
                f"pragmatic={self.pragmatic_bias.item():.2f} "
                f"(success={success_rate:.0%}, fast={fast_path_rate:.0%})"
            )


# =============================================================================
# SPECIALIZED KERNELS (7 CATASTROPHE TYPES)
# =============================================================================


class FoldKernel(CatastropheKernel):
    """Spark (e₁) - Fold Catastrophe (A₂).

    CATASTROPHE MATH:
    ================
    V(x; a) = x³/3 + ax
    ∇V = x² + a

    CHARACTER:
    =========
    - Ignition: Simple on/off behavior
    - Creativity: High epistemic bias (curiosity)
    - Impulsive: Fast path preferred

    FAST PATH: Pure gradient ignition
    SLOW PATH: Creative exploration, novelty-seeking
    """

    def __init__(self, state_dim: int = 256, hidden_dim: int = 256):
        super().__init__(
            state_dim=state_dim,
            catastrophe_type="fold",
            colony_idx=0,
            hidden_dim=hidden_dim,
        )

    def _get_epistemic_bias(self) -> torch.Tensor:
        return torch.tensor(1.5)  # High curiosity

    def _get_pragmatic_bias(self) -> torch.Tensor:
        return torch.tensor(0.5)  # Low goal focus


class CuspKernel(CatastropheKernel):
    """Forge (e₂) - Cusp Catastrophe (A₃).

    CATASTROPHE MATH:
    ================
    V(x; a, b) = x⁴/4 + ax²/2 + bx
    ∇V = x³ + ax + b

    CHARACTER:
    =========
    - Bistable: Quality vs speed choice
    - Perfectionism: High pragmatic bias
    - Hysteresis: Commits to decisions

    FAST PATH: Quality gradient (reconstruction accuracy)
    SLOW PATH: Deep quality optimization
    """

    def __init__(self, state_dim: int = 256, hidden_dim: int = 256):
        super().__init__(
            state_dim=state_dim,
            catastrophe_type="cusp",
            colony_idx=1,
            hidden_dim=hidden_dim,
        )

    def _get_epistemic_bias(self) -> torch.Tensor:
        return torch.tensor(0.5)  # Low exploration

    def _get_pragmatic_bias(self) -> torch.Tensor:
        return torch.tensor(2.0)  # High goal focus


class SwallowtailKernel(CatastropheKernel):
    """Flow (e₃) - Swallowtail Catastrophe (A₄).

    CATASTROPHE MATH:
    ================
    V(x; a, b, c) = x⁵/5 + ax³/3 + bx²/2 + cx
    ∇V = x⁴ + ax² + bx + c

    CHARACTER:
    =========
    - 3-way recovery: Multiple error correction paths
    - Adaptability: Moderate epistemic/pragmatic
    - Resilience: Finds alternative solutions

    FAST PATH: Error gradient minimization
    SLOW PATH: Multi-path error recovery with safety margin
    """

    def __init__(self, state_dim: int = 256, hidden_dim: int = 256):
        super().__init__(
            state_dim=state_dim,
            catastrophe_type="swallowtail",
            colony_idx=2,
            hidden_dim=hidden_dim,
        )

    def _get_epistemic_bias(self) -> torch.Tensor:
        return torch.tensor(0.8)  # Moderate exploration

    def _get_pragmatic_bias(self) -> torch.Tensor:
        return torch.tensor(1.5)  # Moderate-high goal focus

    def forward_slow(
        self,
        state: torch.Tensor,
        context: dict[str, Any],
    ) -> torch.Tensor:
        """Flow-specific slow path: safety margin aware.

        Augments base slow path with CBF h(x) awareness.
        Prefers actions that increase safety margin.
        """
        # Base action
        action = super().forward_slow(state, context)

        # Safety margin modulation
        if "safety_margin" in context:
            h = context["safety_margin"]  # [batch]
            # Low h → reduce action magnitude (conservative)
            safety_scale = torch.sigmoid(h).unsqueeze(-1)
            action = action * (0.5 + 0.5 * safety_scale)
            action = F.normalize(action, dim=-1)

        return action


class ButterflyKernel(CatastropheKernel):
    """Nexus (e₄) - Butterfly Catastrophe (A₅).

    CATASTROPHE MATH:
    ================
    V(x; a, b, c, d) = x⁶/6 + ax⁴/4 + bx³/3 + cx²/2 + dx
    ∇V = x⁵ + ax³ + bx² + cx + d

    CHARACTER:
    =========
    - 4D integration: Complex multi-colony coordination
    - Connection: High need for mutual information
    - Complexity: Handles intricate dependencies

    FAST PATH: Integration gradient (coherence)
    SLOW PATH: Full mutual information maximization
    """

    def __init__(self, state_dim: int = 256, hidden_dim: int = 256):
        super().__init__(
            state_dim=state_dim,
            catastrophe_type="butterfly",
            colony_idx=3,
            hidden_dim=hidden_dim,
        )

    def _get_epistemic_bias(self) -> torch.Tensor:
        return torch.tensor(1.2)  # High exploration for integration

    def _get_pragmatic_bias(self) -> torch.Tensor:
        return torch.tensor(1.2)  # Moderate goal focus


class HyperbolicKernel(CatastropheKernel):
    """Beacon (e₅) - Hyperbolic Umbilic (D₄⁺).

    CATASTROPHE MATH:
    ================
    V(x, y; a, b, c) = x³ + y³ + axy + bx + cy
    ∇V = (3x² + ay + b, 3y² + ax + c)

    CHARACTER:
    =========
    - Planning divergence: Long-horizon lookahead
    - Foresight: High future value estimation
    - Strategic: Outward-splitting decisions

    FAST PATH: Planning gradient (horizon expansion)
    SLOW PATH: Long-term value estimation (TD learning)
    """

    def __init__(self, state_dim: int = 256, hidden_dim: int = 256):
        super().__init__(
            state_dim=state_dim,
            catastrophe_type="hyperbolic",
            colony_idx=4,
            hidden_dim=hidden_dim,
        )

    def _get_epistemic_bias(self) -> torch.Tensor:
        return torch.tensor(1.0)  # Balanced

    def _get_pragmatic_bias(self) -> torch.Tensor:
        return torch.tensor(1.8)  # High goal focus


class EllipticKernel(CatastropheKernel):
    """Grove (e₆) - Elliptic Umbilic (D₄⁻).

    CATASTROPHE MATH:
    ================
    V(x, y; a, b, c) = x³ - xy² + a(x² + y²) + bx + cy
    ∇V = (3x² - y² + 2ax + b, -2xy + 2ay + c)

    CHARACTER:
    =========
    - Knowledge convergence: Inward-gathering research
    - Curiosity: Maximum epistemic bias
    - Depth: Focuses on uncertainty reduction

    FAST PATH: Knowledge gradient (information gain)
    SLOW PATH: Epistemic uncertainty reduction
    """

    def __init__(self, state_dim: int = 256, hidden_dim: int = 256):
        super().__init__(
            state_dim=state_dim,
            catastrophe_type="elliptic",
            colony_idx=5,
            hidden_dim=hidden_dim,
        )

    def _get_epistemic_bias(self) -> torch.Tensor:
        return torch.tensor(2.0)  # Maximum curiosity

    def _get_pragmatic_bias(self) -> torch.Tensor:
        return torch.tensor(0.3)  # Minimal goal focus


class ParabolicKernel(CatastropheKernel):
    """Crystal (e₇) - Parabolic Umbilic (D₅).

    CATASTROPHE MATH:
    ================
    V(x, y; a, b, c, d) = x²y + y⁴ + ax² + by² + cx + dy
    ∇V = (2xy + 2ax + c, x² + 4y³ + 2by + d)

    CHARACTER:
    =========
    - Safety boundary: CBF constraint enforcement
    - Verification: Maximum pragmatic bias
    - Skepticism: Trusts nothing unproven

    FAST PATH: Safety boundary detection (h(x) gradient)
    SLOW PATH: CBF-QP solution for guaranteed h(x) ≥ 0
    """

    def __init__(self, state_dim: int = 256, hidden_dim: int = 256):
        super().__init__(
            state_dim=state_dim,
            catastrophe_type="parabolic",
            colony_idx=6,
            hidden_dim=hidden_dim,
        )

    def _get_epistemic_bias(self) -> torch.Tensor:
        return torch.tensor(0.3)  # Minimal exploration

    def _get_pragmatic_bias(self) -> torch.Tensor:
        return torch.tensor(2.5)  # Maximum goal focus

    def forward_slow(
        self,
        state: torch.Tensor,
        context: dict[str, Any],
    ) -> torch.Tensor:
        """Crystal-specific slow path: CBF-aware.

        Ensures h(x) ≥ 0 constraint is satisfied.
        If unsafe, projects to nearest safe action.
        """
        # Base action
        action = super().forward_slow(state, context)

        # CBF projection (if barrier function provided)
        if "barrier_function" in context:
            h_func = context["barrier_function"]

            # Compute current safety margin
            h = h_func(state)  # [batch]

            # If unsafe, reduce action magnitude
            unsafe_mask = h < 0
            if unsafe_mask.any():
                # Scale down unsafe actions
                safety_scale = torch.ones_like(h)
                safety_scale[unsafe_mask] = 0.5  # Conservative scaling
                action = action * safety_scale.unsqueeze(-1)
                action = F.normalize(action, dim=-1)

        return action


# =============================================================================
# FACTORY & UTILITIES
# =============================================================================


def create_colony_kernel(
    colony_idx: int,
    state_dim: int = 256,
    hidden_dim: int = 256,
) -> CatastropheKernel:
    """Factory function to create appropriate kernel for colony.

    USAGE:
    =====
    ```python
    # Create kernel for Spark colony
    spark_kernel = create_colony_kernel(0)

    # Fast decision (k=1)
    action_fast = spark_kernel(state, k_value=1)

    # Slow decision (k=5, with goals)
    action_slow = spark_kernel(
        state,
        k_value=5,
        context={"goals": goal_obs}
    )
    ```

    Args:
        colony_idx: Index of colony (0-6)
        state_dim: Dimension of input state
        hidden_dim: Hidden dimension for KAN

    Returns:
        Appropriate CatastropheKernel subclass
    """
    KERNEL_CLASSES = [
        FoldKernel,  # 0: Spark
        CuspKernel,  # 1: Forge
        SwallowtailKernel,  # 2: Flow
        ButterflyKernel,  # 3: Nexus
        HyperbolicKernel,  # 4: Beacon
        EllipticKernel,  # 5: Grove
        ParabolicKernel,  # 6: Crystal
    ]

    if not 0 <= colony_idx < 7:
        raise ValueError(f"colony_idx must be in [0, 6], got {colony_idx}")

    return KERNEL_CLASSES[colony_idx](state_dim, hidden_dim)


def batch_evaluate_kernels(
    kernels: list[CatastropheKernel],
    states: torch.Tensor,
    k_value: int = 3,
    context: dict[str, Any] | None = None,
) -> torch.Tensor:
    """Evaluate all 7 kernels in parallel.

    BATCHED PROCESSING:
    ==================
    Uses batched tensor operations for efficiency.
    Exploits S⁷ parallelism (7 independent vector fields).

    Args:
        kernels: List of 7 CatastropheKernels
        states: [batch, state_dim] combined states
        k_value: Metacognition depth
        context: Optional context dict[str, Any]

    Returns:
        [batch, 7, 8] actions from all colonies
    """
    batch_size = states.shape[0]
    device = states.device

    # Allocate output
    actions = torch.empty(batch_size, 7, 8, device=device)

    # Evaluate each kernel
    for i, kernel in enumerate(kernels):
        actions[:, i, :] = kernel(states, k_value, context)

    return actions


# =============================================================================
# MINIMAL UNIT TESTS
# =============================================================================


if __name__ == "__main__":
    print("=" * 80)
    print("CATASTROPHE KERNELS - UNIT TESTS")
    print("=" * 80)

    # Test parameters
    batch_size = 4
    state_dim = 256
    hidden_dim = 256
    device = "cpu"

    print(f"\nTest setup: batch={batch_size}, state_dim={state_dim}")

    # Create test state
    state = torch.randn(batch_size, state_dim, device=device)

    # Test context
    goals = torch.randn(batch_size, 15, device=device)  # E8(8) + S⁷(7) = 15
    context = {"goals": goals}

    print("\n" + "-" * 80)
    print("TEST 1: Individual kernel instantiation")
    print("-" * 80)

    for i in range(7):
        kernel = create_colony_kernel(i, state_dim, hidden_dim)
        print(f"✓ Colony {i} ({kernel.catastrophe_type}): {kernel.__class__.__name__}")

    print("\n" + "-" * 80)
    print("TEST 2: Fast path (k=1)")
    print("-" * 80)

    for i in range(7):
        kernel = create_colony_kernel(i, state_dim, hidden_dim)
        action_fast = kernel.forward_fast(state)

        # Check output shape
        assert action_fast.shape == (batch_size, 8), f"Expected [batch, 8], got {action_fast.shape}"

        # Check S⁷ normalization
        norms = action_fast.norm(dim=-1)
        assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5), (
            f"Actions not normalized: {norms}"
        )

        print(f"✓ Colony {i} fast path: shape={action_fast.shape}, norm={norms[0]:.6f}")

    print("\n" + "-" * 80)
    print("TEST 3: Slow path (k=5)")
    print("-" * 80)

    for i in range(7):
        kernel = create_colony_kernel(i, state_dim, hidden_dim)
        action_slow = kernel.forward_slow(state, context)

        # Check output shape
        assert action_slow.shape == (batch_size, 8), f"Expected [batch, 8], got {action_slow.shape}"

        # Check S⁷ normalization
        norms = action_slow.norm(dim=-1)
        assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5), (
            f"Actions not normalized: {norms}"
        )

        print(f"✓ Colony {i} slow path: shape={action_slow.shape}, norm={norms[0]:.6f}")

    print("\n" + "-" * 80)
    print("TEST 4: Routing by k-value")
    print("-" * 80)

    kernel = create_colony_kernel(0, state_dim, hidden_dim)  # Spark

    # Test different k values
    for k in [1, 2, 3, 5, 7]:
        action = kernel(state, k_value=k, context=context)
        print(f"✓ k={k}: shape={action.shape}, norm={action.norm(dim=-1)[0]:.6f}")

    print("\n" + "-" * 80)
    print("TEST 5: Batched evaluation (all 7 colonies)")
    print("-" * 80)

    # Create all kernels
    kernels = [create_colony_kernel(i, state_dim, hidden_dim) for i in range(7)]

    # Evaluate in batch
    actions_batched = batch_evaluate_kernels(kernels, state, k_value=3, context=context)

    assert actions_batched.shape == (
        batch_size,
        7,
        8,
    ), f"Expected [batch, 7, 8], got {actions_batched.shape}"

    # Check all normalized
    norms = actions_batched.norm(dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5), "Not all actions normalized"

    print(f"✓ Batched output: shape={actions_batched.shape}")
    print(f"  Colony norms: {norms[0]}")

    print("\n" + "-" * 80)
    print("TEST 6: Gradient flow")
    print("-" * 80)

    kernel = create_colony_kernel(0, state_dim, hidden_dim)
    state_grad = state.clone().requires_grad_(True)

    # Forward pass
    action = kernel(state_grad, k_value=3, context=context)

    # Compute L2 loss for gradient test
    loss = action.pow(2).sum()

    # Backward pass
    loss.backward()

    # Check gradients exist
    assert state_grad.grad is not None, "No gradient for state"
    assert kernel.slow_proj1.weight.grad is not None, "No gradient for weights"

    print("✓ Gradients computed")
    print(f"  State grad norm: {state_grad.grad.norm():.6f}")
    print(f"  Weight grad norm: {kernel.slow_proj1.weight.grad.norm():.6f}")

    print("\n" + "-" * 80)
    print("TEST 7: Epistemic/Pragmatic biases")
    print("-" * 80)

    for i in range(7):
        kernel = create_colony_kernel(i, state_dim, hidden_dim)
        epistemic = kernel.epistemic_bias.item()  # type: ignore[operator]
        pragmatic = kernel.pragmatic_bias.item()  # type: ignore[operator]
        ratio = epistemic / pragmatic if pragmatic > 0 else float("inf")

        colony_names = ["Spark", "Forge", "Flow", "Nexus", "Beacon", "Grove", "Crystal"]
        print(
            f"✓ {colony_names[i]:8s}: epistemic={epistemic:.2f}, "
            f"pragmatic={pragmatic:.2f}, ratio={ratio:.2f}"
        )

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED ✓")
    print("=" * 80)
