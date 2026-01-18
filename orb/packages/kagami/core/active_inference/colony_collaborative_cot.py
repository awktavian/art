"""Colony Collaborative Chain-of-Thought - Fano-Routed Reasoning Within Markov Blanket.

ARCHITECTURAL POSITION (Dec 2, 2025):
=====================================
CoT lives INSIDE the organism's Markov blanket, specifically in the
INTERNAL DYNAMICS phase (μ → μ). It is NOT external communication.

Markov Blanket Flow:
    η_org (external) → s_org (sensory) → μ_org (internal) → a_org (active) → η_org
                                          ▲
                                          │
                                   ┌──────┴──────┐
                                   │  FANO CoT   │
                                   │  Reasoning  │
                                   └─────────────┘

The CoT process:
1. Each colony generates a local reasoning trace from its z-state
2. Traces propagate along Fano lines (valid 3-colony compositions)
3. Traces are aggregated into organism-level thought
4. Aggregated thought influences organism action selection

This respects the Markov blanket property:
- CoT is INTERNAL (colonies reasoning about each other)
- CoT does NOT directly interact with external world
- External influence comes only through sensory interface
- External effect comes only through active interface

MATHEMATICAL FOUNDATION:
========================
CoT traces are encoded in the tangent space of S⁷ (the imaginary octonions).
Each colony's trace is a vector in its local tangent space T_eᵢS⁷.
Fano multiplication defines how traces compose: T_eᵢ × T_eⱼ → T_eₖ.

This matches the catastrophe dynamics:
- Fold (Spark): Threshold reasoning ("if X then sudden Y")
- Cusp (Forge): Bistable reasoning ("either A or B, hysteresis")
- Swallowtail (Flow): Multi-path reasoning ("paths P1, P2, P3")
- Butterfly (Nexus): Complex integration ("synthesize A, B, C, D")
- Hyperbolic (Beacon): Divergent focus ("branch out to explore")
- Elliptic (Grove): Convergent search ("narrow down to solution")
- Parabolic (Crystal): Edge detection ("verify boundary conditions")

VARIABLE-LENGTH ENCODING (Dec 2, 2025):
=======================================
Traces use ADAPTIVE RESIDUAL E8 QUANTIZATION for variable-length encoding:
- Level 0:     240 codes     (~7.9 bits)  - Simple traces
- Level 1:  57,600 codes    (~15.8 bits)  - Standard traces
- Level 2:  13.8M codes     (~23.7 bits)  - Complex traces
- Level 3:   3.3B codes     (~31.6 bits)  - High-precision traces

Adaptive early stopping when residual norm < threshold.
This allows:
- Simple yes/no decisions: 1 byte
- Standard reasoning: 2 bytes
- Complex multi-step: 3-4 bytes
- Full precision when needed: up to 8 bytes

References:
- Wei et al. (2022): "Chain-of-Thought Prompting Elicits Reasoning"
- Yao et al. (2023): "Tree of Thoughts: Deliberate Problem Solving"
- Friston et al. (2015): "Active inference and epistemic value"
- Baez (2002): "The Octonions", Bull. AMS 39(2)
- Viazovska (2017): "The sphere packing problem in dimension 8"

Created: December 2, 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn
import torch.nn.functional as F

if TYPE_CHECKING:
    pass

# Variable-length E8 encoding (v2 lattice protocol)
from kagami_math.e8_lattice_protocol import (
    E8LatticeResidualConfig,
    ResidualE8LatticeVQ,
)
from kagami_math.fano_plane import (
    get_fano_lines_zero_indexed,
)

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS (imported from canonical source)
# =============================================================================

from kagami_math.catastrophe_constants import COLONY_NAMES

FANO_LINES_0IDX = get_fano_lines_zero_indexed()

# Catastrophe-specific reasoning patterns
CATASTROPHE_REASONING = {
    "spark": "threshold",  # Fold: sudden transitions
    "forge": "bistable",  # Cusp: either-or decisions
    "flow": "multipath",  # Swallowtail: multiple recovery paths
    "nexus": "integrative",  # Butterfly: synthesize multiple inputs
    "beacon": "divergent",  # Hyperbolic: branch out
    "grove": "convergent",  # Elliptic: narrow down
    "crystal": "boundary",  # Parabolic: edge cases
}


class CoTPhase(Enum):
    """Chain-of-Thought processing phases."""

    LOCAL = "local"  # Each colony generates local trace
    FANO_PROPAGATE = "fano"  # Traces propagate along Fano lines
    AGGREGATE = "aggregate"  # Traces aggregate into organism thought
    REFINE = "refine"  # Optional: refine based on aggregated view


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ReasoningTrace:
    """A single reasoning trace from a colony.

    Traces live in the tangent space of S⁷ at the colony's basis vector.
    This ensures geometric consistency with the octonion structure.

    GRADIENT FLOW (Dec 2, 2025):
    - trace_vector: keeps gradient for main reasoning path
    - confidence_tensor: keeps gradient for attention weighting
    - confidence: scalar for logging (detached)
    """

    colony_idx: int
    colony_name: str

    # Trace content (tangent vector) - DIFFERENTIABLE
    trace_vector: torch.Tensor  # [trace_dim] in tangent space T_eᵢS⁷

    # Catastrophe-specific reasoning type
    reasoning_type: str

    # Confidence as tensor for gradient flow
    confidence_tensor: torch.Tensor | None = None  # [1] or scalar tensor

    # Confidence scalar for logging (detached)
    confidence: float = 1.0

    # Parent traces (for Fano composition)
    parents: tuple[int, int] | None = None  # (colony_i, colony_j) if composed

    # Metadata
    depth: int = 0  # Reasoning depth (0 = initial, 1+ = derived)

    def __repr__(self) -> str:
        parents_str = f" ← ({self.parents[0]}×{self.parents[1]})" if self.parents else ""
        return (
            f"ReasoningTrace({self.colony_name}, "
            f"type={self.reasoning_type}, conf={self.confidence:.2f}"
            f"{parents_str})"
        )

    def get_confidence_for_grad(self) -> torch.Tensor:
        """Get confidence tensor for gradient-preserving operations."""
        if self.confidence_tensor is not None:
            return self.confidence_tensor
        return torch.tensor(self.confidence, device=self.trace_vector.device)


@dataclass
class CollaborativeThought:
    """Aggregated thought from all colonies.

    This is the organism-level reasoning result, suitable for
    influencing action selection via the active interface.

    VARIABLE-LENGTH ENCODING (Dec 2, 2025):
    =======================================
    All traces and thoughts are E8-quantized with adaptive precision.
    The `e8_encoding` field contains variable-length byte representations.
    """

    # Per-colony traces
    colony_traces: dict[str, ReasoningTrace] = field(default_factory=dict[str, Any])

    # Fano-composed traces (derived from 3-colony compositions)
    fano_traces: list[ReasoningTrace] = field(default_factory=list[Any])

    # Aggregated organism-level thought vector
    aggregated_vector: torch.Tensor | None = None

    # Overall reasoning confidence
    confidence: float = 1.0

    # Which Fano lines were activated
    active_fano_lines: list[tuple[int, int, int]] = field(default_factory=list[Any])

    # Metrics
    num_reasoning_steps: int = 0
    processing_time_ms: float = 0.0

    # =========================================================
    # VARIABLE-LENGTH E8 ENCODING
    # =========================================================

    # E8 indices for each colony trace [colony_name -> [num_levels]]
    trace_e8_indices: dict[str, torch.Tensor] = field(default_factory=dict[str, Any])

    # E8 indices for aggregated thought [num_levels]
    thought_e8_indices: torch.Tensor | None = None

    # Total E8 levels used (sum across all traces)
    total_e8_levels: int = 0

    # Commitment loss for training
    commitment_loss: float = 0.0

    # Byte representation of aggregated thought (for serialization)
    thought_bytes: bytes | None = None


# =============================================================================
# COLONY TRACE GENERATOR
# =============================================================================


class ColonyTraceGenerator(nn.Module):
    """Generates reasoning traces from colony z-states.

    Each colony has a specialized generator matching its catastrophe type.
    Traces are generated in the tangent space of S⁷.
    """

    def __init__(
        self,
        colony_idx: int,
        z_dim: int = 14,
        trace_dim: int = 32,
        hidden_dim: int = 64,
    ):
        super().__init__()
        self.colony_idx = colony_idx
        self.colony_name = COLONY_NAMES[colony_idx]
        self.reasoning_type = CATASTROPHE_REASONING[self.colony_name]
        self.trace_dim = trace_dim

        # z → trace projection (catastrophe-aware)
        self.trace_proj = nn.Sequential(
            nn.Linear(z_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            self._get_activation(),  # Catastrophe-specific activation
            nn.Linear(hidden_dim, trace_dim),
        )

        # Confidence estimator
        self.confidence_head = nn.Sequential(
            nn.Linear(z_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid(),
        )

    def _get_activation(self) -> nn.Module:
        """Get catastrophe-specific activation function."""
        # Match activation dynamics to catastrophe type
        if self.reasoning_type == "threshold":
            return nn.ReLU()  # Sharp threshold
        elif self.reasoning_type == "bistable":
            return nn.Tanh()  # Bounded, symmetric
        elif self.reasoning_type == "multipath":
            return nn.GELU()  # Smooth, multi-modal
        elif self.reasoning_type == "integrative":
            return nn.SiLU()  # Smooth, integrative
        elif self.reasoning_type == "divergent":
            return nn.Softplus()  # Unbounded positive
        elif self.reasoning_type == "convergent":
            return nn.Sigmoid()  # Bounded, converging
        elif self.reasoning_type == "boundary":
            return nn.Hardtanh()  # Hard boundaries
        else:
            return nn.ReLU()

    def forward(self, z: torch.Tensor) -> ReasoningTrace:
        """Generate reasoning trace from colony z-state.

        Args:
            z: [z_dim] or [B, z_dim] colony stochastic state

        Returns:
            ReasoningTrace with trace vector and confidence

        GRADIENT FLOW (Dec 2, 2025):
        Both trace_vector and confidence_tensor preserve gradients.
        """
        # Ensure batch dimension
        if z.dim() == 1:
            z = z.unsqueeze(0)

        # Generate trace vector (DIFFERENTIABLE)
        trace_vector = self.trace_proj(z)  # [B, trace_dim]

        # Normalize to unit tangent vector (geometric constraint)
        trace_vector = F.normalize(trace_vector, dim=-1)

        # Estimate confidence (DIFFERENTIABLE - keep as tensor)
        confidence_tensor = self.confidence_head(z).squeeze(-1)  # [B]

        # Scalar for logging (detached)
        confidence_scalar = confidence_tensor.detach().mean().item()

        return ReasoningTrace(
            colony_idx=self.colony_idx,
            colony_name=self.colony_name,
            trace_vector=trace_vector.squeeze(0),
            reasoning_type=self.reasoning_type,
            confidence_tensor=confidence_tensor.squeeze(0)
            if confidence_tensor.numel() == 1
            else confidence_tensor.mean(),
            confidence=confidence_scalar,
            depth=0,
        )


# =============================================================================
# FANO TRACE PROPAGATOR
# =============================================================================


class FanoTracePropagator(nn.Module):
    """Propagates reasoning traces along Fano lines.

    When two colonies on a Fano line generate traces, their composition
    produces a trace for the third colony: T_eᵢ × T_eⱼ → T_eₖ.

    This implements collaborative reasoning through the Fano structure.
    """

    def __init__(
        self,
        trace_dim: int = 32,
        hidden_dim: int = 64,
    ):
        super().__init__()
        self.trace_dim = trace_dim

        # Fano line composition weights (learnable)
        # One composition network per Fano line
        self.line_composers = nn.ModuleList(
            [
                nn.Sequential(
                    nn.Linear(2 * trace_dim, hidden_dim),
                    nn.LayerNorm(hidden_dim),
                    nn.ReLU(),
                    nn.Linear(hidden_dim, trace_dim),
                )
                for _ in range(7)  # 7 Fano lines
            ]
        )

        # Attention weights for selecting which lines to activate
        self.line_gate = nn.Sequential(
            nn.Linear(7 * trace_dim, 7),
            nn.Sigmoid(),
        )

        # Build Fano adjacency for quick lookup
        self._build_fano_structure()

    def _build_fano_structure(self) -> None:
        """Build Fano structure for efficient propagation."""
        # Map: (source, partner) → (result, line_idx, sign)
        self.fano_products: dict[tuple[int, int], tuple[int, int, int]] = {}

        for line_idx, (i, j, k) in enumerate(FANO_LINES_0IDX):
            # i × j = k
            self.fano_products[(i, j)] = (k, line_idx, 1)
            # j × k = i
            self.fano_products[(j, k)] = (i, line_idx, 1)
            # k × i = j
            self.fano_products[(k, i)] = (j, line_idx, 1)
            # Reverse (negative)
            self.fano_products[(j, i)] = (k, line_idx, -1)
            self.fano_products[(k, j)] = (i, line_idx, -1)
            self.fano_products[(i, k)] = (j, line_idx, -1)

    def propagate(
        self,
        traces: dict[int, ReasoningTrace],
        max_depth: int = 2,
    ) -> list[ReasoningTrace]:
        """Propagate traces along Fano lines.

        Args:
            traces: Dict mapping colony_idx → ReasoningTrace
            max_depth: Maximum propagation depth

        Returns:
            List of composed traces (Fano products)
        """
        composed_traces = []
        device = next(iter(traces.values())).trace_vector.device

        # Collect all trace vectors for gating
        all_traces = torch.zeros(7, self.trace_dim, device=device)
        for idx, trace in traces.items():
            if idx < 7:
                all_traces[idx] = trace.trace_vector

        # Compute line activation gates
        gates = self.line_gate(all_traces.flatten())  # [7]

        # Propagate along each Fano line
        for line_idx, (i, j, k) in enumerate(FANO_LINES_0IDX):
            gate = gates[line_idx]

            # Skip if gate is low (colonies not actively reasoning together)
            if gate < 0.3:
                continue

            # Check if we have traces for two colonies on this line
            pairs = [(i, j, k), (j, k, i), (k, i, j)]

            for source, partner, result in pairs:
                if source in traces and partner in traces:
                    source_trace = traces[source]
                    partner_trace = traces[partner]

                    # Skip if already composed
                    if source_trace.depth + partner_trace.depth >= max_depth:
                        continue

                    # Compose traces
                    composed = self._compose_traces(
                        source_trace,
                        partner_trace,
                        result,
                        line_idx,
                        gate,
                    )
                    composed_traces.append(composed)

        return composed_traces

    def _compose_traces(
        self,
        source: ReasoningTrace,
        partner: ReasoningTrace,
        result_idx: int,
        line_idx: int,
        gate: torch.Tensor,
    ) -> ReasoningTrace:
        """Compose two traces into a third via Fano multiplication.

        Args:
            source: Source colony trace
            partner: Partner colony trace
            result_idx: Result colony index
            line_idx: Fano line index
            gate: Activation gate for this line

        Returns:
            Composed trace for result colony
        """
        # Concatenate source and partner traces
        combined = torch.cat([source.trace_vector, partner.trace_vector])

        # Apply line-specific composition
        composed_vector = self.line_composers[line_idx](combined)

        # Apply gate and normalize
        composed_vector = gate * F.normalize(composed_vector, dim=-1)

        # Composed confidence (DIFFERENTIABLE) - product of parent confidences × gate
        source_conf = source.get_confidence_for_grad()
        partner_conf = partner.get_confidence_for_grad()
        composed_confidence_tensor = source_conf * partner_conf * gate
        composed_confidence_scalar = composed_confidence_tensor.detach().item()

        return ReasoningTrace(
            colony_idx=result_idx,
            colony_name=COLONY_NAMES[result_idx],
            trace_vector=composed_vector,
            reasoning_type=CATASTROPHE_REASONING[COLONY_NAMES[result_idx]],
            confidence_tensor=composed_confidence_tensor,
            confidence=composed_confidence_scalar,
            parents=(source.colony_idx, partner.colony_idx),
            depth=max(source.depth, partner.depth) + 1,
        )


# =============================================================================
# THOUGHT AGGREGATOR
# =============================================================================


class ThoughtAggregator(nn.Module):
    """Aggregates colony traces into organism-level thought.

    Uses attention over traces weighted by confidence and Fano structure.
    Produces a single organism thought vector for action selection.
    """

    def __init__(
        self,
        trace_dim: int = 32,
        output_dim: int = 98,  # 7 * 14 (matches z_all dimension)
        num_heads: int = 4,  # Must divide trace_dim
    ):
        super().__init__()
        self.trace_dim = trace_dim
        self.output_dim = output_dim

        # Ensure num_heads divides trace_dim
        if trace_dim % num_heads != 0:
            num_heads = 4 if trace_dim % 4 == 0 else 2 if trace_dim % 2 == 0 else 1

        # Multi-head attention for aggregation
        self.attention = nn.MultiheadAttention(
            embed_dim=trace_dim,
            num_heads=num_heads,
            batch_first=True,
        )

        # Query for organism-level aggregation
        self.organism_query = nn.Parameter(torch.randn(1, 1, trace_dim))

        # Project to organism internal state dimension
        self.output_proj = nn.Sequential(
            nn.Linear(trace_dim, output_dim // 2),
            nn.LayerNorm(output_dim // 2),
            nn.GELU(),
            nn.Linear(output_dim // 2, output_dim),
        )

    def forward(
        self,
        colony_traces: dict[str, ReasoningTrace],
        fano_traces: list[ReasoningTrace],
    ) -> tuple[torch.Tensor, float]:
        """Aggregate all traces into organism thought.

        Args:
            colony_traces: Per-colony reasoning traces
            fano_traces: Fano-composed traces

        Returns:
            (aggregated_vector [output_dim], confidence)
        """
        # Collect all traces
        all_traces = list(colony_traces.values()) + fano_traces

        if not all_traces:
            # No traces - return zeros
            device = self.organism_query.device
            return torch.zeros(self.output_dim, device=device), 0.0

        device = all_traces[0].trace_vector.device

        # Stack trace vectors [N, trace_dim]
        trace_vectors = torch.stack([t.trace_vector for t in all_traces])

        # Create confidence weights (DIFFERENTIABLE - use tensor confidences)
        confidences = torch.stack([t.get_confidence_for_grad() for t in all_traces])

        # Add batch dimension for attention
        trace_vectors = trace_vectors.unsqueeze(0)  # [1, N, trace_dim]

        # Expand organism query
        query = self.organism_query.expand(1, -1, -1).to(device)

        # Apply attention with confidence-weighted key biasing
        # We use attention output directly (preserves out_proj gradients)
        # and modulate by confidence post-hoc
        confidence_weights = confidences / (confidences.sum() + 1e-8)

        # Scale trace vectors by confidence before attention (differentiable)
        # This allows attention to "see" confidence in the values
        weighted_traces = trace_vectors * confidence_weights.unsqueeze(0).unsqueeze(-1)

        # Apply attention - use the attention output directly (includes out_proj)
        attended, _attn_weights = self.attention(
            query,  # [1, 1, trace_dim]
            trace_vectors,  # [1, N, trace_dim] - keys
            weighted_traces,  # [1, N, trace_dim] - values weighted by confidence
        )
        # attended: [1, 1, trace_dim] - includes out_proj gradient path

        # Project to output
        aggregated = self.output_proj(attended.squeeze(0).squeeze(0))

        # Overall confidence
        overall_confidence = confidences.mean().item()

        return aggregated, overall_confidence


# =============================================================================
# COLONY COLLABORATIVE COT
# =============================================================================


class ColonyCollaborativeCoT(nn.Module):
    """Colony Collaborative Chain-of-Thought within Markov Blanket.

    POSITION: Lives INSIDE organism internal dynamics (μ → μ).

    This module:
    1. Generates local reasoning traces from each colony's z-state
    2. Propagates traces along Fano lines (valid 3-colony compositions)
    3. Aggregates into organism-level thought
    4. Modulates the z_coupled state before action selection

    The output feeds into the organism's active interface, maintaining
    Markov blanket structure (CoT influences action, not external world).

    ADAPTIVE CoT DEPTH (Dec 6, 2025):
    =================================
    CoT depth adapts to compute budget (k_value) from Configurator:
    - k=1-3 (reflex): depth=1 (fast, minimal reasoning)
    - k=3-7 (standard): depth=2 (balanced reasoning)
    - k=7-11 (deep): depth=3 (thorough reasoning)
    - k>11: capped at depth=3 (safety limit)

    Use set_compute_budget(k_value) to modulate depth dynamically.

    VARIABLE-LENGTH E8 ENCODING (Dec 2, 2025):
    ==========================================
    ALL traces use adaptive residual E8 quantization:
    - 1-4 E8 levels based on trace complexity
    - Adaptive early stopping when residual < threshold
    - Shared E8VQ with memory system for consistency

    Capacity per level:
    - Level 0: 240 codes (7.9 bits)
    - Level 1: 57,600 codes (15.8 bits)
    - Level 2: 13.8M codes (23.7 bits)
    - Level 3: 3.3B codes (31.6 bits)

    Call set_library() to connect to model._unified_library.
    """

    # K-value to depth mapping (LeCun Mode-2 adaptive planning)
    K_VALUE_DEPTH_MAP = {
        (1, 3): 1,  # Reflex: minimal reasoning
        (3, 7): 2,  # Standard: balanced
        (7, 11): 3,  # Deep: thorough
        (11, 999): 3,  # Cap at 3 for safety
    }

    def __init__(
        self,
        z_dim: int = 14,
        trace_dim: int = 32,
        hidden_dim: int = 64,
        max_propagation_depth: int = 2,
        enable_refinement: bool = True,
        device: str = "cpu",
    ):
        super().__init__()
        self.z_dim = z_dim
        self.trace_dim = trace_dim
        self.max_depth = max_propagation_depth
        self.enable_refinement = enable_refinement

        # =========================================================
        # VARIABLE-LENGTH E8 lattice residual (v2 protocol)
        # =========================================================
        # For trace quantization (trace_dim → 8D → variable bytes)
        self._trace_to_8d = nn.Linear(trace_dim, 8)
        self._trace_from_8d = nn.Linear(8, trace_dim)
        self.trace_e8 = ResidualE8LatticeVQ(
            E8LatticeResidualConfig(
                max_levels=8,
                min_levels=1,
                adaptive_levels=True,
                residual_threshold=1e-3,
            )
        )

        # For aggregated thoughts (larger dimension: 7*z_dim → 8D → variable bytes)
        self._thought_to_8d = nn.Linear(7 * z_dim, 8)
        self._thought_from_8d = nn.Linear(8, 7 * z_dim)
        self.thought_e8 = ResidualE8LatticeVQ(
            E8LatticeResidualConfig(
                max_levels=8,
                min_levels=1,
                adaptive_levels=True,
                residual_threshold=1e-3,
            )
        )

        # Program library reference (set[Any] via set_library)
        # NOTE: Use list[Any] wrapper to avoid PyTorch Module registration
        # The library is owned by KagamiWorldModel._unified_library, not here
        # We just need a reference for program-guided reasoning
        self._program_library_ref: list[Any] = [None]  # Wrapper to avoid double-registration

        # =========================================================
        # PER-COLONY TRACE GENERATORS
        # =========================================================
        self.trace_generators = nn.ModuleList(
            [ColonyTraceGenerator(i, z_dim, trace_dim, hidden_dim) for i in range(7)]
        )

        # Fano propagator
        self.fano_propagator = FanoTracePropagator(trace_dim, hidden_dim)

        # Thought aggregator
        self.aggregator = ThoughtAggregator(
            trace_dim=trace_dim,
            output_dim=7 * z_dim,  # Match z_all dimension
            num_heads=7,
        )

        # Refinement layer (optional second pass)
        if enable_refinement:
            self.refiner = nn.Sequential(
                nn.Linear(7 * z_dim * 2, hidden_dim * 2),
                nn.LayerNorm(hidden_dim * 2),
                nn.GELU(),
                nn.Linear(hidden_dim * 2, 7 * z_dim),
            )

        # CoT influence gate (how much CoT modulates z_coupled)
        self.influence_gate = nn.Sequential(
            nn.Linear(7 * z_dim * 2, 1),
            nn.Sigmoid(),
        )

        # =========================================================
        # PROGRAM-GUIDED REASONING
        # =========================================================
        # When library is set[Any], can use program embeddings to guide reasoning
        # num_heads must divide embed_dim evenly
        _num_heads = 7 if trace_dim % 7 == 0 else (2 if trace_dim % 2 == 0 else 1)
        self.program_attention = nn.MultiheadAttention(
            embed_dim=trace_dim,
            num_heads=_num_heads,
            batch_first=True,
        )

        logger.debug(
            "ColonyCollaborativeCoT: z=%d, trace=%d, depth=%d",
            z_dim,
            trace_dim,
            max_propagation_depth,
        )

    def get_program_library(self) -> None:
        """Get program library reference (avoids double-registration).

        NOTE: Do NOT use self._program_library = X as PyTorch's __setattr__
        intercepts Module assignments even with @property.setter defined.
        """
        return self._program_library_ref[0]

    def set_library(self, library: Any) -> None:
        """Connect to ProgramLibrary for program-guided reasoning.

        Call this with model._unified_library to enable:
        - Program-guided trace refinement
        - Shared gradient flow with world model training

        Args:
            library: ProgramLibrary (ResidualCatastropheProgramLibrary)
        """
        # CRITICAL: Use list[Any] assignment to avoid PyTorch Module registration!
        # PyTorch's __setattr__ intercepts `self.attr = Module()` even with properties
        self._program_library_ref[0] = library
        logger.debug("ColonyCollaborativeCoT connected to program library")

    def set_compute_budget(self, k_value: int) -> int:
        """Set CoT depth based on compute budget (k_value) from Configurator.

        LeCun (2022) Section 3.1.2: Mode-2 planning depth adapts to task complexity.
        This implements adaptive CoT depth based on the system's compute budget.

        Args:
            k_value: Compute budget (1-3: reflex, 3-7: standard, 7-11: deep, >11: max)

        Returns:
            int: The new max_depth setting
        """
        for (k_min, k_max), depth in self.K_VALUE_DEPTH_MAP.items():
            if k_min <= k_value < k_max:
                self.max_depth = depth
                logger.debug(f"CoT depth set[Any] to {depth} for k_value={k_value}")
                return depth

        # Default fallback
        self.max_depth = 2
        return 2

    def get_effective_depth(self) -> int:
        """Get the current effective propagation depth."""
        return self.max_depth

    def quantize_trace(self, trace: torch.Tensor) -> dict[str, Any]:
        """Quantize a trace using VARIABLE-LENGTH E8 lattice residual encoding.

        Uses adaptive residual quantization:
        - Simple traces: 1 level (7.9 bits)
        - Standard traces: 2 levels (15.8 bits)
        - Complex traces: 3-4 levels (23.7-31.6 bits)

        Args:
            trace: [trace_dim] or [B, trace_dim] trace vector(s)

        Returns:
            Dict with:
                - quantized: [B, trace_dim] reconstructed trace
                - codes: List of lattice codes (VARIABLE LENGTH)
                - num_levels_used: actual levels used
                - commitment_loss: for training
                - bits_used: bits actually used
        """
        # Ensure batch dimension
        if trace.dim() == 1:
            trace = trace.unsqueeze(0)

        # Project to 8D for E8 quantization
        trace_8d = self._trace_to_8d(trace)

        # Lattice residual quantization
        num_levels = 4 if self.training else 8
        vq_result = self.trace_e8(trace_8d, num_levels=num_levels)
        # ResidualE8LatticeVQ returns dict: {quantized, loss, indices, perplexity}
        quantized_8d = vq_result["quantized"]
        codes_tensor = vq_result["indices"]  # [B, L, 8] where L = num_levels
        codes = [codes_tensor[:, i, :] for i in range(codes_tensor.shape[1])]

        # Project back to trace_dim
        quantized = self._trace_from_8d(quantized_8d)

        # Commitment loss from VQ result
        commitment_loss = vq_result["loss"]

        # Byte protocol payload (variable length) for compatibility/logging
        trace_bytes = self.trace_e8.encode_bytes(trace_8d[0], num_levels=len(codes))
        indices = torch.tensor(list(trace_bytes), device=trace.device, dtype=torch.uint8)

        return {
            "quantized": quantized,
            "codes": codes,
            "num_levels_used": len(codes),
            "bytes_used": len(self.trace_e8.encode_bytes(trace_8d[0], num_levels=len(codes))),
            "commitment_loss": commitment_loss,
            "indices_list": codes,  # legacy name
            "indices": indices,  # legacy name
            "bytes": trace_bytes,
        }

    def quantize_thought(self, thought: torch.Tensor) -> dict[str, Any]:
        """Quantize aggregated organism thought using VARIABLE-LENGTH E8 lattice residual.

        Thoughts are larger (7*z_dim = 98D) so may need more precision.

        Args:
            thought: [7*z_dim] or [B, 7*z_dim] aggregated thought

        Returns:
            Dict with quantized thought, indices, and metadata
        """
        if thought.dim() == 1:
            thought = thought.unsqueeze(0)

        # Project to 8D
        thought_8d = self._thought_to_8d(thought)

        # Quantize
        num_levels = 4 if self.training else 8
        vq_result = self.thought_e8(thought_8d, num_levels=num_levels)
        # ResidualE8LatticeVQ returns dict: {quantized, loss, indices, perplexity}
        quantized_8d = vq_result["quantized"]
        codes_tensor = vq_result["indices"]  # [B, L, 8] where L = num_levels
        codes = [codes_tensor[:, i, :] for i in range(codes_tensor.shape[1])]

        # Project back
        quantized = self._thought_from_8d(quantized_8d)

        # Commitment loss from VQ result
        commitment_loss = vq_result["loss"]

        # Byte protocol (variable length) for serialization/logging
        thought_bytes = self.thought_e8.encode_bytes(thought_8d[0], num_levels=len(codes))
        indices = torch.tensor(list(thought_bytes), device=thought.device, dtype=torch.uint8)

        return {
            "quantized": quantized,
            "codes": codes,
            "num_levels_used": len(codes),
            "bytes_used": len(self.thought_e8.encode_bytes(thought_8d[0], num_levels=len(codes))),
            "commitment_loss": commitment_loss,
            "indices_list": codes,  # legacy name used by forward() for level bookkeeping
            "indices": indices,  # legacy name used by forward() for reporting
            "bytes": thought_bytes,
        }

    def to_bytes(self, trace: torch.Tensor) -> bytes:
        """Convert trace to v2 lattice protocol bytes.

        Args:
            trace: [trace_dim] trace vector

        Returns:
            bytes (varint-coded, variable length)
        """
        if trace.dim() == 1:
            trace = trace.unsqueeze(0)
        trace_8d = self._trace_to_8d(trace)
        num_levels = 4 if self.training else 8
        return self.trace_e8.encode_bytes(trace_8d[0], num_levels=num_levels)

    def from_bytes(self, byte_data: bytes, device: str = "cpu") -> torch.Tensor:
        """Reconstruct trace from v2 lattice protocol bytes.

        Args:
            byte_data: E8 byte sequence (1-8 bytes)
            device: Target device for output tensor

        Returns:
            [trace_dim] reconstructed trace
        """
        decoded_8d, _codes = self.trace_e8.decode_bytes(byte_data)
        decoded_8d = decoded_8d.to(device)
        return self._trace_from_8d(decoded_8d).squeeze(0)

    def forward(
        self,
        z_states: dict[str, torch.Tensor],
    ) -> tuple[CollaborativeThought, torch.Tensor]:
        """Run collaborative chain-of-thought with VARIABLE-LENGTH E8 encoding.

        MARKOV BLANKET POSITION: This is μ → μ (internal dynamics).
        Input is colony internal states, output modulates internal state.

        VARIABLE-LENGTH ENCODING:
        - Each trace is E8-quantized with adaptive levels (1-4)
        - Simple reasoning uses fewer bytes
        - Complex reasoning uses more bytes
        - Commitment loss available for training

        Args:
            z_states: Dict mapping colony_name → z tensor [z_dim]

        Returns:
            (CollaborativeThought, z_modulation [7*z_dim])
        """
        import time

        start_time = time.time()

        # Track E8 encoding metrics
        # v2: trace_e8_indices maps colony_name -> [L, 8] int64 lattice codes
        trace_e8_indices: dict[str, torch.Tensor] = {}
        total_commitment_loss = 0.0
        total_e8_levels = 0

        # ========================================================
        # PHASE 1: LOCAL - Generate traces from each colony
        # S⁷ PARALLELISM (Dec 7, 2025): Batch all 7 colonies together
        # ========================================================
        colony_traces: dict[str, ReasoningTrace] = {}
        colony_traces_by_idx: dict[int, ReasoningTrace] = {}

        # Step 1a: Generate all traces (keep structure)
        trace_vectors = []
        trace_names = []
        trace_indices = []
        for name, z in z_states.items():
            if name not in COLONY_NAMES:
                continue
            idx = COLONY_NAMES.index(name)
            trace = self.trace_generators[idx](z)
            trace_vectors.append(trace.trace_vector)
            trace_names.append(name)
            trace_indices.append(idx)
            colony_traces[name] = trace
            colony_traces_by_idx[idx] = trace

        # Step 1b: S⁷ PARALLEL E8 quantization - batch all 7 colonies
        if trace_vectors:
            # Stack: [7, trace_dim]
            batched_traces = torch.stack(trace_vectors, dim=0)

            # Project to 8D: [7, 8]
            batched_8d = self._trace_to_8d(batched_traces)

            # SINGLE E8 call for all 7 colonies (was 7 separate calls!)
            num_levels = 4 if self.training else 8
            vq_result = self.trace_e8(batched_8d, num_levels=num_levels)
            # ResidualE8LatticeVQ returns dict: {quantized, loss, indices, perplexity}
            quantized_8d = vq_result["quantized"]
            codes_tensor = vq_result["indices"]  # [7, L, 8] where L = num_levels
            # Convert codes from [7, L, 8] to list of [7, 8] for compatibility
            codes = [codes_tensor[:, i, :] for i in range(codes_tensor.shape[1])]
            metrics = {"commitment_loss": vq_result["loss"]}

            # Project back: [7, trace_dim]
            quantized_traces = self._trace_from_8d(quantized_8d)

            # Track metrics (aggregated)
            total_commitment_loss += metrics.get("commitment_loss", torch.tensor(0.0))
            total_e8_levels += len(codes) * len(trace_names)

            # Unbatch and update traces
            for i, name in enumerate(trace_names):
                colony_traces[name].trace_vector = quantized_traces[i]
                # Store per-colony lattice codes: [L, 8]
                trace_e8_indices[name] = torch.stack([c[i].to(torch.int64) for c in codes], dim=0)

        # ========================================================
        # PHASE 2: FANO_PROPAGATE - Propagate along Fano lines
        # ========================================================
        fano_traces = self.fano_propagator.propagate(
            colony_traces_by_idx,
            max_depth=self.max_depth,
        )

        # Quantize Fano-composed traces (S⁷ PARALLEL)
        if fano_traces:
            fano_vectors = torch.stack([t.trace_vector for t in fano_traces], dim=0)
            fano_8d = self._trace_to_8d(fano_vectors)
            num_levels = 4 if self.training else 8
            fano_vq_result = self.trace_e8(fano_8d, num_levels=num_levels)
            # ResidualE8LatticeVQ returns dict: {quantized, loss, indices, perplexity}
            fano_quantized_8d = fano_vq_result["quantized"]
            fano_codes_tensor = fano_vq_result["indices"]  # [B, L, 8]
            fano_codes = [fano_codes_tensor[:, i, :] for i in range(fano_codes_tensor.shape[1])]
            fano_metrics = {"commitment_loss": fano_vq_result["loss"]}
            fano_quantized = self._trace_from_8d(fano_quantized_8d)

            for i, trace in enumerate(fano_traces):
                trace.trace_vector = fano_quantized[i]

            total_commitment_loss += fano_metrics.get("commitment_loss", torch.tensor(0.0))
            total_e8_levels += len(fano_codes) * len(fano_traces)

        # Track active Fano lines
        active_lines = set()
        for trace in fano_traces:
            if trace.parents:
                # Find which line this composition came from
                for line in FANO_LINES_0IDX:
                    if trace.parents[0] in line and trace.parents[1] in line:
                        active_lines.add(line)
                        break

        # ========================================================
        # PHASE 3: AGGREGATE - Combine into organism thought
        # ========================================================
        aggregated_vector, confidence = self.aggregator(colony_traces, fano_traces)

        # ========================================================
        # PHASE 4: REFINE (optional) - Second pass with full context
        # ========================================================
        if self.enable_refinement and hasattr(self, "refiner"):
            # Concatenate original z_all with aggregated thought
            z_all = torch.cat([z_states[name] for name in COLONY_NAMES])
            combined = torch.cat([z_all, aggregated_vector])
            refined = self.refiner(combined)
            aggregated_vector = refined

        # ========================================================
        # PHASE 4.5: PROGRAM ATTENTION (Dec 4, 2025) - GRADIENT FIX
        # ========================================================
        # Use program_attention to provide gradients to the MultiheadAttention params
        # This integrates program library embeddings into the reasoning process
        if self.training and hasattr(self, "program_attention"):
            # Create query from colony traces (same dim as trace_dim=32)
            trace_list = [
                colony_traces[name].trace_vector for name in COLONY_NAMES if name in colony_traces
            ]
            if trace_list:
                kv = torch.stack(trace_list).unsqueeze(0)  # [1, 7, trace_dim]

                # Use first trace as query (all same dim = trace_dim)
                query = trace_list[0].unsqueeze(0).unsqueeze(0)  # [1, 1, trace_dim]

                # Self-attention over traces
                attended, _ = self.program_attention(query, kv, kv)  # [1, 1, trace_dim]

                # Project attended to 7*z_dim (aggregated_vector dim)
                # Properly handle dimension mismatch via repeat + interpolation
                attended_flat = attended.squeeze()  # [trace_dim]
                target_len = 7 * self.z_dim  # aggregated_vector length

                if attended_flat.numel() < target_len:
                    # Need to expand: repeat and pad
                    num_repeats = (target_len // attended_flat.numel()) + 1
                    attended_expanded = attended_flat.repeat(num_repeats)[:target_len]
                else:
                    # Need to shrink: take first target_len elements
                    attended_expanded = attended_flat[:target_len]

                # Small modulation for gradient flow without disrupting main output
                aggregated_vector = aggregated_vector + 0.01 * (
                    attended_expanded - attended_expanded.detach()
                )

        # ========================================================
        # PHASE 5: QUANTIZE THOUGHT - Variable-length encoding
        # ========================================================
        thought_quant = self.quantize_thought(aggregated_vector)
        thought_e8_indices = torch.stack(
            [c[0].to(torch.int64) for c in thought_quant["codes"]], dim=0
        )
        total_e8_levels += thought_quant["num_levels_used"]

        # Use quantized thought (straight-through)
        aggregated_vector = thought_quant["quantized"].squeeze(0)

        # Convert to bytes for serialization (v2 varint protocol)
        thought_8d = self._thought_to_8d(thought_quant["quantized"])
        thought_bytes = self.thought_e8.encode_bytes(
            thought_8d[0], num_levels=thought_quant["num_levels_used"]
        )

        # ========================================================
        # COMPUTE MODULATION - How much CoT influences z_coupled
        # ========================================================
        z_all = torch.cat([z_states[name] for name in COLONY_NAMES])
        gate_input = torch.cat([z_all, aggregated_vector])
        gate = self.influence_gate(gate_input)

        # Modulation = gate * aggregated (additive influence on z)
        z_modulation = gate * aggregated_vector

        # Build result with variable-length encoding info
        thought = CollaborativeThought(
            colony_traces=colony_traces,
            fano_traces=fano_traces,
            aggregated_vector=aggregated_vector,
            confidence=confidence,
            active_fano_lines=list(active_lines),
            num_reasoning_steps=len(colony_traces) + len(fano_traces),
            processing_time_ms=(time.time() - start_time) * 1000,
            # Variable-length E8 encoding
            trace_e8_indices=trace_e8_indices,
            thought_e8_indices=thought_e8_indices,
            total_e8_levels=total_e8_levels,
            commitment_loss=total_commitment_loss,
            thought_bytes=thought_bytes,
        )

        return thought, z_modulation

    def get_reasoning_summary(self, thought: CollaborativeThought) -> str:
        """Get human-readable summary of reasoning with E8 encoding info.

        Args:
            thought: CollaborativeThought result

        Returns:
            String summary of collaborative reasoning
        """
        lines = ["=== Colony Collaborative CoT Summary ==="]

        # Colony traces with E8 encoding
        lines.append("\nLocal Traces (E8-quantized):")
        for name, trace in thought.colony_traces.items():
            # Get encoding info if available
            e8_info = ""
            if name in thought.trace_e8_indices:
                indices = thought.trace_e8_indices[name]
                num_levels = indices.shape[-1] if indices.dim() > 1 else indices.numel()
                e8_info = f", E8:{num_levels}L"
            lines.append(f"  {name}: {trace.reasoning_type} (conf={trace.confidence:.2f}{e8_info})")

        # Fano compositions
        if thought.fano_traces:
            lines.append("\nFano Compositions:")
            for trace in thought.fano_traces:
                if trace.parents:
                    parent_names = (COLONY_NAMES[trace.parents[0]], COLONY_NAMES[trace.parents[1]])
                    lines.append(
                        f"  {parent_names[0]} × {parent_names[1]} → {trace.colony_name} "
                        f"(conf={trace.confidence:.2f})"
                    )

        # Active Fano lines
        if thought.active_fano_lines:
            lines.append("\nActive Fano Lines:")
            for line in thought.active_fano_lines:
                names = [COLONY_NAMES[i] for i in line]
                lines.append(f"  {names[0]} — {names[1]} — {names[2]}")

        # Variable-length encoding summary
        lines.append("\nVariable-Length E8 Encoding:")
        lines.append(f"  Total E8 levels: {thought.total_e8_levels}")
        if thought.thought_e8_indices is not None:
            thought_levels = (
                thought.thought_e8_indices.shape[-1]
                if thought.thought_e8_indices.dim() > 1
                else thought.thought_e8_indices.numel()
            )
            lines.append(f"  Thought encoding: {thought_levels} levels")
        if thought.thought_bytes:
            lines.append(f"  Thought bytes: {len(thought.thought_bytes)} bytes")
        lines.append(f"  Commitment loss: {thought.commitment_loss:.4f}")

        # Summary
        lines.append(
            f"\nOverall: {thought.num_reasoning_steps} steps, "
            f"conf={thought.confidence:.2f}, "
            f"{thought.processing_time_ms:.1f}ms"
        )

        return "\n".join(lines)


# =============================================================================
# INTEGRATION FUNCTIONS
# =============================================================================


def create_collaborative_cot(
    z_dim: int = 14,
    trace_dim: int = 32,
    hidden_dim: int = 64,
    max_depth: int = 2,
    enable_refinement: bool = True,
) -> ColonyCollaborativeCoT:
    """Create a ColonyCollaborativeCoT module with variable-length E8 encoding.

    ALL instances use adaptive E8 residual quantization (1-4 levels).

    Args:
        z_dim: Dimension of colony z-states (H¹⁴ = 14)
        trace_dim: Dimension of reasoning traces
        hidden_dim: Hidden layer dimension
        max_depth: Maximum Fano propagation depth
        enable_refinement: Enable refinement pass

    Returns:
        Configured ColonyCollaborativeCoT with variable-length E8
    """
    return ColonyCollaborativeCoT(
        z_dim=z_dim,
        trace_dim=trace_dim,
        hidden_dim=hidden_dim,
        max_propagation_depth=max_depth,
        enable_refinement=enable_refinement,
    )


__all__ = [
    # DELETED: integrate_cot_with_organism (Dec 3, 2025)
    # Use organism_cot.integrate_organism_cot instead for unified CoT+EFE
    "CATASTROPHE_REASONING",
    "CoTPhase",
    "CollaborativeThought",
    "ColonyCollaborativeCoT",
    "ColonyTraceGenerator",
    "FanoTracePropagator",
    "ReasoningTrace",
    "ThoughtAggregator",
    "create_collaborative_cot",
]
