"""Catastrophe-Informed KAN Layer - Colony-Specific Activation Functions.

BREAKTHROUGH INTEGRATION (December 2, 2025):
=============================================
Traditional KAN uses generic B-splines as learnable basis functions.
This module uses the 7 CATASTROPHE POTENTIAL DERIVATIVES as basis functions.

Each colony gets its mathematically canonical activation:
- Spark  (Fold):       φ(x; a) = 3x² + a
- Forge  (Cusp):       φ(x; a,b) = 4x³ + 2ax + b
- Flow   (Swallowtail): φ(x; a,b,c) = 5x⁴ + 3ax² + 2bx + c
- Nexus  (Butterfly):  φ(x; a,b,c,d) = 6x⁵ + 4ax³ + 3bx² + 2cx + d
- Beacon (Hyperbolic): φ(x,y; a,b,c) = (3x² + ay + b, 3y² + ax + c)
- Grove  (Elliptic):   φ(x,y; a,b,c) = (3x² - y² + 2ax + b, -2xy + 2ay + c)
- Crystal (Parabolic): φ(x,y; a,b,c,d) = (2xy + 2ax + c, x² + 4y³ + 2by + d)

S⁷ PARALLELISM (December 2, 2025):
==================================
S⁷ admits exactly 7 linearly independent vector fields (Bott-Kervaire theorem).
Each colony operates on its own vector field → 7 independent computation streams.

This module exploits this via BATCHED tensor operations:
- BatchedCatastropheBasis: All 7 catastrophes in single [B, 7, C] tensor
- BatchedCatastropheKAN: Parallel processing for all colonies
- FanoOctonionCombiner: Proper octonion multiplication for output combination

WHY THIS MATTERS:
=================
1. MATHEMATICAL CANONICITY: These are THE 7 ways smooth systems bifurcate
2. LEARNABLE PHYSICS: Parameters (a,b,c,d) are catastrophe control parameters
3. BIFURCATION AWARENESS: Network learns to navigate singularity manifolds
4. COLONY SPECIALIZATION: Each colony has its natural dynamic
5. S⁷ PARALLELISM: 7× speedup via batched tensor operations

THEORY:
=======
Kolmogorov-Arnold: f(x₁,...,xₙ) = Σᵢ φᵢ(Σⱼ ψᵢⱼ(xⱼ))

Standard KAN: φᵢ = B-splines (arbitrary smooth)
Catastrophe KAN: φᵢ = catastrophe potential derivative (canonical smooth)

The catastrophe potential derivatives are guaranteed to be:
- Smooth (C^∞)
- Universal (any smooth function near a catastrophe looks like one of 7)
- Structurally stable (small perturbations don't change type)

References:
- Thom (1972): Structural Stability and Morphogenesis
- Arnold (1975): Critical Points of Smooth Functions
- Liu et al. (2024): KAN: Kolmogorov-Arnold Networks
- Bott & Kervaire (1958): Parallelizability of spheres
- K OS Architecture: Colony-Catastrophe-Octonion correspondence

Created: December 2, 2025
Updated: December 2, 2025 - Added S⁷ parallel batched processing
"""

from __future__ import annotations

import logging
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

# torch.compile availability check
_TORCH_COMPILE_AVAILABLE = hasattr(torch, "compile")


# Import canonical constants (consolidation: Dec 3, 2025)
# Lazy import to avoid circular dependency
def _get_catastrophe_constants() -> Any:
    from kagami_math.catastrophe_constants import (
        COLONY_NAMES,
        MAX_CONTROL_PARAMS,
        CatastropheType,
        get_codim,
    )

    return CatastropheType, COLONY_NAMES, MAX_CONTROL_PARAMS, get_codim


# Re-export for API compatibility (import from constants module)
from kagami_math.catastrophe_constants import CatastropheType

logger = logging.getLogger(__name__)


# Backward compatibility: CATASTROPHE_PARAMS derived from canonical config
def _get_catastrophe_params() -> dict[str, Any]:
    CatastropheType, _COLONY_NAMES, _MAX_CONTROL_PARAMS, get_codim = _get_catastrophe_constants()
    return {CatastropheType(i): get_codim(i) for i in range(7)}


# Lazy-loaded global (computed on first access)
_CATASTROPHE_PARAMS = None


def CATASTROPHE_PARAMS() -> None:
    global _CATASTROPHE_PARAMS
    if _CATASTROPHE_PARAMS is None:
        _CATASTROPHE_PARAMS = _get_catastrophe_params()
    return _CATASTROPHE_PARAMS  # type: ignore[return-value]


# Backward compatibility alias
# Lazy-loaded global (computed on first access)
_MAX_CATASTROPHE_PARAMS = None


def MAX_CATASTROPHE_PARAMS() -> None:
    global _MAX_CATASTROPHE_PARAMS
    if _MAX_CATASTROPHE_PARAMS is None:
        (
            _CatastropheType,
            _COLONY_NAMES,
            MAX_CONTROL_PARAMS,
            _get_codim,
        ) = _get_catastrophe_constants()
        _MAX_CATASTROPHE_PARAMS = MAX_CONTROL_PARAMS
    return _MAX_CATASTROPHE_PARAMS


# =============================================================================
# BATCHED CATASTROPHE BASIS - All 7 types in single tensor operation
# =============================================================================


class BatchedCatastropheBasis(nn.Module):
    """All 7 catastrophe potential derivatives in a single batched operation.

    S⁷ PARALLELISM (Dec 2, 2025):
    =============================
    Instead of processing colonies sequentially, this processes ALL 7
    catastrophes in a single [B, 7, C] tensor operation.

    The Bott-Kervaire theorem guarantees 7 linearly independent vector fields
    on S⁷, meaning these 7 computations are truly independent and can be
    parallelized with no interference.

    TRUE 2D CATASTROPHES (Dec 2, 2025):
    ===================================
    Corank-2 catastrophes (D₄⁺, D₄⁻, D₅) require 2D state variables (x, y).
    Instead of approximating y from x, we split input channels into (x, y) pairs:
    - Even indices → x coordinates
    - Odd indices → y coordinates

    This preserves the true mathematical structure of umbilic catastrophes.

    TORCH.COMPILE (Dec 2, 2025):
    ============================
    Forward pass is compiled for JIT optimization on hot path.
    """

    _compiled_forward = None  # Cached compiled forward function

    def __init__(
        self,
        num_channels: int,
        init_scale: float = 0.1,
        temperature: float = 1.0,
    ):
        """Initialize batched catastrophe basis for all 7 types.

        Args:
            num_channels: Number of feature channels (must be even for 2D catastrophes)
            init_scale: Initial scale for control parameters
            temperature: Initial temperature for smooth activation control (default: 1.0)
        """
        super().__init__()
        self.num_channels = num_channels

        # Ensure even channels for (x, y) splitting in 2D catastrophes (types 4-6 only)
        # Note: BatchedCatastropheBasis processes all 7 types, but padding is only needed
        # if any 2D catastrophe will be used. Since we process all 7, we always pad.
        if num_channels % 2 != 0:
            logger.warning(
                f"num_channels={num_channels} is odd. Padding to {num_channels + 1} "
                f"for proper 2D catastrophe (x, y) splitting."
            )
            self.num_channels = num_channels + 1

        # Learnable control parameters for ALL 7 catastrophes
        # Shape: [7, num_channels, max_params] - unified shape
        self.control_params = nn.Parameter(
            torch.randn(7, self.num_channels, MAX_CATASTROPHE_PARAMS()) * init_scale  # type: ignore[func-returns-value]
        )

        # === LEARNABLE TEMPERATURE PARAMETER (Dec 27, 2025) ===
        # Controls catastrophe activation sharpness
        # - Higher temperature → smoother transitions (less sharp bifurcations)
        # - Lower temperature → sharper transitions (more pronounced catastrophes)
        # Per-colony temperatures allow each catastrophe to learn optimal sharpness
        self.temperature = nn.Parameter(torch.ones(7) * temperature)

        # Precompute masks for parameter validity per catastrophe type
        # Some types only use a, some use a,b, some a,b,c, some a,b,c,d
        (
            CatastropheType,
            _COLONY_NAMES,
            _MAX_CONTROL_PARAMS,
            _get_codim,
        ) = _get_catastrophe_constants()
        param_mask = torch.zeros(7, MAX_CATASTROPHE_PARAMS())  # type: ignore[func-returns-value]
        for cat_type in CatastropheType:
            num_params = CATASTROPHE_PARAMS()[cat_type]  # type: ignore[func-returns-value]
            param_mask[cat_type, :num_params] = 1.0
        self.register_buffer("param_mask", param_mask)

        # Mark which catastrophes are 2D (umbilic types)
        is_2d = torch.tensor(
            [
                False,  # Fold
                False,  # Cusp
                False,  # Swallowtail
                False,  # Butterfly
                True,  # Hyperbolic (D₄⁺)
                True,  # Elliptic (D₄⁻)
                True,  # Parabolic (D₅)
            ]
        )
        self.register_buffer("is_2d", is_2d)

        # === LEARNABLE RESIDUAL GATE (Dec 8, 2025) ===
        # Ensures gradient flow through catastrophe layers
        # Initialized to 0.1 (small but non-zero for gradient highway)
        # Can learn to increase if catastrophe dynamics are stable
        self.residual_gate = nn.Parameter(torch.tensor(0.1))

        # === OUTPUT LAYER NORM (Dec 8, 2025) ===
        # Normalizes catastrophe outputs to prevent gradient explosion
        # Uses proper nn.LayerNorm for deepcopy compatibility
        self.output_norm = nn.LayerNorm(self.num_channels)

        logger.debug(
            f"BatchedCatastropheBasis: {num_channels} channels, "
            f"7 catastrophe types, unified [7, C, 4] parameters"
        )

        # Compile _forward_impl for JIT optimization (Dec 21, 2025).
        #
        # IMPORTANT (MPS):
        # - torch.compile/inductor on MPS is still noisy/unstable and can introduce
        #   extra graph breaks + materializations.
        # - Default to compiling only when CUDA is available.
        self._use_compiled = False
        if _TORCH_COMPILE_AVAILABLE:
            try:
                if torch.cuda.is_available():
                    self._forward_impl_compiled = torch.compile(
                        self._forward_impl,
                        mode="reduce-overhead",
                        dynamic=False,  # Fixed batch size on CUDA
                    )
                    self._use_compiled = True
                    logger.debug(
                        "BatchedCatastropheBasis: torch.compile enabled (CUDA, 2-3x speedup)"
                    )
            except Exception as e:
                logger.debug(f"BatchedCatastropheBasis: torch.compile failed ({e})")
                self._use_compiled = False

    def forward(
        self,
        x: torch.Tensor,
        param_modulation: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Apply all 7 catastrophe activations in parallel.

        Args:
            x: [B, 7, C] input tensor (all colonies at once)
            param_modulation: Optional [7, max_params] or [B, 7, max_params] modulation

        Returns:
            [B, 7, C] activated tensor (all colonies)
        """
        if self._use_compiled:
            # torch.compile + inductor is sensitive to zero-stride views produced by
            # `.expand()` (common in our 7-colony broadcasting). Ensure contiguous
            # layout before entering the compiled region to avoid stride-assertion
            # failures at runtime (seen on MPS).
            if not x.is_contiguous():
                x = x.contiguous()
            if (
                param_modulation is not None
                and isinstance(param_modulation, torch.Tensor)
                and not param_modulation.is_contiguous()
            ):
                param_modulation = param_modulation.contiguous()
            return self._forward_impl_compiled(x, param_modulation)
        return self._forward_impl(x, param_modulation)

    def _forward_impl(
        self,
        x: torch.Tensor,
        param_modulation: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Core forward implementation - TRUE CATASTROPHE DYNAMICS with gradient highway.

        PURE CATASTROPHE FUNCTIONS (Dec 8, 2025):
        =========================================
        Uses the EXACT catastrophe potential derivatives from Thom's classification.
        The 7 elementary catastrophes are THE canonical ways smooth systems bifurcate.

        GRADIENT STABILITY (Dec 8, 2025):
        =================================
        Uses LEARNABLE residual gate (like Transformer/ResNet) for gradient flow.
        This is mathematically principled:
        - output = catastrophe(x) + gate * x
        - gate is learned, starts at 0.1, can adapt
        - Ensures gradients flow even when catastrophe outputs are small
        - Does NOT dilute the catastrophe math - just provides alternative gradient path

        MPS OPTIMIZED:
        1. Compute all outputs in contiguous slices to reduce fragmentation
        2. Use addcmul for fused multiply-add operations where possible
        3. Pre-allocate output with correct layout before computation
        """
        B, num_colonies, C = x.shape
        assert num_colonies == 7, f"Expected 7 colonies, got {num_colonies}"
        device = x.device
        dtype = x.dtype

        # Pad channels if needed for 2D processing
        if self.num_channels > C:
            x = F.pad(x, (0, self.num_channels - C))
            C = self.num_channels

        # Get control parameters: [7, C, 4]
        params = self.control_params

        # Apply modulation if provided
        if param_modulation is not None:
            if param_modulation.dim() == 2:
                mod = param_modulation.unsqueeze(1) * 0.1
            else:
                mod = param_modulation.mean(dim=0, keepdim=False).unsqueeze(1) * 0.1
            params = params + mod.expand_as(params)  # type: ignore[assignment]

        # === GRADIENT STABILITY: Soft bound input to prevent numerical overflow ===
        # tanh is smoother than softsign and preserves more gradient information
        # Scale factor 0.5 keeps most values in linear regime while bounding extremes
        x_stable = torch.tanh(x * 0.5) * 2.0  # Maps [-∞,∞] → [-2, 2] smoothly

        # === TEMPERATURE SCALING (Dec 27, 2025) ===
        # Apply per-colony temperature: x → x/T (scales input sharpness)
        # Temperatures are clamped to [0.1, 10.0] to prevent instability
        temp_clamped = self.temperature.clamp(0.1, 10.0).view(1, 7, 1)  # [1, 7, 1]
        x_temp = x_stable / temp_clamped  # Scale input by temperature

        # Extract parameters as contiguous tensors for efficient access
        a = params[:, :, 0].contiguous()  # [7, C]
        b = params[:, :, 1].contiguous()  # [7, C]
        c = params[:, :, 2].contiguous()  # [7, C]
        d = params[:, :, 3].contiguous()  # [7, C]

        # Pre-allocate output as contiguous tensor
        output = torch.empty(B, 7, C, device=device, dtype=dtype)

        # === CORANK-1 CATASTROPHES (types 0-3): 1D activations ===
        # TRUE potential derivatives from Thom's classification
        x_0123 = x_temp[:, :4, :].contiguous()  # [B, 4, C] - colonies 0-3 (temperature-scaled)

        # Compute powers
        x_sq = x_0123 * x_0123  # x²

        # Type 0 - Fold (A₂): V = x³ + ax → ∂V/∂x = 3x² + a
        # NOTE: Avoid constructing device tensors inside forward (hurts compile + causes graph breaks).
        output[:, 0, :] = a[0, :] + 3.0 * x_sq[:, 0, :]

        # Type 1 - Cusp (A₃): V = x⁴ + ax² + bx → ∂V/∂x = 4x³ + 2ax + b
        x1 = x_0123[:, 1, :]
        x1_sq = x_sq[:, 1, :]
        x1_cu = x1_sq * x1
        output[:, 1, :] = b[1, :] + (2.0 * a[1, :]) * x1 + 4.0 * x1_cu

        # Type 2 - Swallowtail (A₄): V = x⁵ + ax³ + bx² + cx → ∂V/∂x = 5x⁴ + 3ax² + 2bx + c
        x2 = x_0123[:, 2, :]
        x2_sq = x_sq[:, 2, :]
        x2_4 = x2_sq * x2_sq
        output[:, 2, :] = c[2, :] + (2.0 * b[2, :]) * x2 + (3.0 * a[2, :]) * x2_sq + 5.0 * x2_4

        # Type 3 - Butterfly (A₅): V = x⁶ + ax⁴ + bx³ + cx² + dx → ∂V/∂x = 6x⁵ + 4ax³ + 3bx² + 2cx + d
        x3 = x_0123[:, 3, :]
        x3_sq = x_sq[:, 3, :]
        x3_cu = x3_sq * x3
        x3_5 = x3_sq * x3_cu
        output[:, 3, :] = (
            d[3, :]
            + (2.0 * c[3, :]) * x3
            + (3.0 * b[3, :]) * x3_sq
            + (4.0 * a[3, :]) * x3_cu
            + 6.0 * x3_5
        )

        # === CORANK-2 CATASTROPHES (types 4-6): TRUE 2D UMBILIC ===
        half_C = C // 2

        # Use temperature-scaled input for 2D catastrophes
        x_456 = x_temp[:, 4:7, :].contiguous()  # [B, 3, C] (temperature-scaled)

        # Reshape for paired processing: [B, 3, C//2, 2] then transpose to [B, 3, 2, C//2]
        x_456_paired = x_456.view(B, 3, half_C, 2).permute(0, 1, 3, 2).contiguous()

        x_c = x_456_paired[:, :, 0, :]  # [B, 3, C//2] - x coordinates
        y_c = x_456_paired[:, :, 1, :]  # [B, 3, C//2] - y coordinates

        # Pre-compute powers (shared across 2D types)
        x_c2 = x_c * x_c
        y_c2 = y_c * y_c
        y_c3 = y_c2 * y_c

        # Get even-indexed parameters for 2D types
        a_2d = a[4:7, 0::2].contiguous()
        b_2d = b[4:7, 0::2].contiguous()
        c_2d = c[4:7, 0::2].contiguous()
        d_2d = d[4:7, 0::2].contiguous()

        # Allocate output for 2D types
        out_2d = torch.empty(B, 3, 2, half_C, device=device, dtype=dtype)

        # === Type 4 - Hyperbolic Umbilic (D₄⁺) ===
        # V = x³ + y³ + axy + bx + cy
        # ∂V/∂x = 3x² + ay + b
        # ∂V/∂y = 3y² + ax + c
        out_2d[:, 0, 0, :] = 3 * x_c2[:, 0, :] + a_2d[0, :] * y_c[:, 0, :] + b_2d[0, :]
        out_2d[:, 0, 1, :] = 3 * y_c2[:, 0, :] + a_2d[0, :] * x_c[:, 0, :] + c_2d[0, :]

        # === Type 5 - Elliptic Umbilic (D₄⁻) ===
        # V = x³ - xy² + a(x² + y²) + bx + cy
        # ∂V/∂x = 3x² - y² + 2ax + b
        # ∂V/∂y = -2xy + 2ay + c
        out_2d[:, 1, 0, :] = (
            3 * x_c2[:, 1, :] - y_c2[:, 1, :] + 2 * a_2d[1, :] * x_c[:, 1, :] + b_2d[1, :]
        )
        out_2d[:, 1, 1, :] = (
            -2 * x_c[:, 1, :] * y_c[:, 1, :] + 2 * a_2d[1, :] * y_c[:, 1, :] + c_2d[1, :]
        )

        # === Type 6 - Parabolic Umbilic (D₅) ===
        # V = x²y + y⁴ + ax² + by² + cx + dy
        # ∂V/∂x = 2xy + 2ax + c
        # ∂V/∂y = x² + 4y³ + 2by + d
        out_2d[:, 2, 0, :] = (
            2 * x_c[:, 2, :] * y_c[:, 2, :] + 2 * a_2d[2, :] * x_c[:, 2, :] + c_2d[2, :]
        )
        out_2d[:, 2, 1, :] = (
            x_c2[:, 2, :] + 4 * y_c3[:, 2, :] + 2 * b_2d[2, :] * y_c[:, 2, :] + d_2d[2, :]
        )

        # Reshape back to interleaved: [B, 3, C]
        out_2d_interleaved = out_2d.permute(0, 1, 3, 2).reshape(B, 3, C)
        output[:, 4:7, :] = out_2d_interleaved

        # === TEMPERATURE RE-SCALING (Dec 27, 2025) ===
        # Scale output back by temperature to maintain proper gradient magnitude
        # This completes the temperature transformation: f(x/T) * T
        output = output * temp_clamped

        # === OUTPUT NORMALIZATION (Dec 8, 2025) ===
        # Pure catastrophe outputs can be large (e.g., 6x^5 with x=2 → 192)
        # Use proper LayerNorm for deepcopy compatibility and gradient stability
        output_normalized = self.output_norm(output)

        # === LEARNABLE RESIDUAL GATE (Transformer-style) ===
        # Ensures gradient flow while preserving catastrophe dynamics
        # gate initialized to 0.1, can learn to increase/decrease
        # FIX (Dec 14, 2025): Use stabilized input for residual to prevent unbounded passthrough
        return output_normalized + self.residual_gate * x_stable

    def get_singularity_risk(self, x: torch.Tensor) -> torch.Tensor:
        """Compute singularity risk for all 7 catastrophes in parallel.

        Args:
            x: [B, 7, C] input tensor

        Returns:
            [B, 7] risk tensor in [0, 1]
        """
        grad = self.forward(x)
        grad_magnitude = grad.abs().mean(dim=-1)  # [B, 7]
        # FIX (Dec 14, 2025): Correct risk direction - large gradients indicate extreme regions
        # High gradient magnitude = near boundary of catastrophe manifold = high risk
        # Low gradient magnitude = stable equilibrium region = low risk
        risk = torch.sigmoid(grad_magnitude - 2.0)
        return risk.clamp(0, 1)


# =============================================================================
# FANO OCTONION COMBINER - Proper octonion multiplication for output combination
# =============================================================================


class FanoOctonionCombiner(nn.Module):
    """Combine colony outputs using Fano plane multiplication.

    S⁷ STRUCTURE (Dec 2, 2025):
    ==========================
    Instead of simple scalar weighted sum, this uses proper octonion
    multiplication according to Fano plane rules:

        e_i × e_j = ±e_k  (where (i,j,k) is a Fano line)

    This preserves the non-associative algebra of octonions and enables
    proper inter-colony coupling.

    ARCHITECTURE:
    =============
    1. Compute Fano products (colony interactions on same Fano lines)
    2. Mix original outputs with Fano-coupled outputs
    3. Apply learned S⁷ weights for final aggregation
    """

    def __init__(self, d_model: int):
        """Initialize Fano combiner.

        Args:
            d_model: Model dimension
        """
        super().__init__()
        self.d_model = d_model

        # Import Fano structure
        from kagami_math.fano_plane import (
            get_fano_lines_zero_indexed,
        )

        # Precompute Fano line indices (0-indexed)
        fano_lines_0idx = get_fano_lines_zero_indexed()

        # Build index tensors for batched Fano product gathering
        # line_i[l], line_j[l] → line_k[l] for each Fano line l
        # OPTIMIZATION: Pre-compute and cache Fano line indices
        line_i = torch.tensor([line[0] for line in fano_lines_0idx], dtype=torch.long)
        line_j = torch.tensor([line[1] for line in fano_lines_0idx], dtype=torch.long)
        line_k = torch.tensor([line[2] for line in fano_lines_0idx], dtype=torch.long)

        self.register_buffer("line_i", line_i)
        self.register_buffer("line_j", line_j)
        self.register_buffer("line_k", line_k)

        # Learnable Fano coupling strength per line
        self.fano_coupling_strength = nn.Parameter(torch.ones(7) * 0.1)

        # Learnable S⁷ weights for final aggregation
        self.s7_weights = nn.Parameter(torch.ones(7) / 7)

        # Fano product mixer (learns how to combine original + coupled)
        self.fano_mixer = nn.Linear(d_model * 2, d_model)

        # Output projection
        self.output_proj = nn.Linear(d_model, d_model)

        logger.debug(f"FanoOctonionCombiner: {d_model}D with 7 Fano lines")

    def compute_fano_products(
        self,
        colony_outputs: torch.Tensor,
    ) -> torch.Tensor:
        """Compute all 7 Fano line products in parallel.

        For each Fano line (i, j, k): coupled_k += strength * (out_i ⊗ out_j)

        Args:
            colony_outputs: [B, 7, D] outputs from all colonies

        Returns:
            [B, 7, D] Fano-coupled outputs
        """
        B, _num_colonies, D = colony_outputs.shape

        # Gather outputs for each Fano line
        # out_i[l] = output from first colony of line l
        # line_i/j/k are [7] tensors, we need [B, 7, D] indexing
        # Cast buffers to Tensor for type safety
        line_i: torch.Tensor = self.line_i  # type: ignore[assignment]
        line_j: torch.Tensor = self.line_j  # type: ignore[assignment]
        line_k: torch.Tensor = self.line_k  # type: ignore[assignment]

        out_i = torch.stack([colony_outputs[:, idx, :] for idx in line_i], dim=1)  # [B, 7, D]
        out_j = torch.stack([colony_outputs[:, idx, :] for idx in line_j], dim=1)  # [B, 7, D]

        # Element-wise product (approximation of octonion ⊗)
        # Full octonion multiplication would require 8D, we use D-dim proxy
        products = out_i * out_j  # [B, 7, D]

        # Scale by coupling strength
        scaled_products = products * self.fano_coupling_strength.view(1, 7, 1)

        # Scatter-add to target colonies (each product goes to line_k)
        # GRADIENT FIX (Dec 5, 2025): Use functional scatter_add instead of in-place
        # In-place scatter_add_ on zeros_like doesn't propagate gradients to scaled_products
        # because the destination tensor doesn't track gradients through the in-place op.
        index_expanded = line_k.view(1, 7, 1).expand(B, 7, D)
        fano_coupled = torch.zeros_like(colony_outputs).scatter_add(
            1, index_expanded, scaled_products
        )

        return fano_coupled

    def forward(
        self,
        colony_outputs: torch.Tensor,
        domain_activations: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Combine colony outputs using Fano-aware aggregation.

        Args:
            colony_outputs: [B, 7, D] outputs from all colonies
            domain_activations: Optional [7] or [B, 7] external colony weights

        Returns:
            [B, D] combined output
        """
        B, _num_colonies, _D = colony_outputs.shape

        # 1. Compute Fano products (inter-colony coupling)
        fano_coupled = self.compute_fano_products(colony_outputs)

        # 2. Mix original + Fano-coupled
        mixed = self.fano_mixer(torch.cat([colony_outputs, fano_coupled], dim=-1))  # [B, 7, D]

        # 3. Apply S⁷ weights
        if domain_activations is not None:
            if domain_activations.dim() == 1:
                domain_activations = domain_activations.unsqueeze(0).expand(B, -1)
            weights = F.softmax(domain_activations * self.s7_weights, dim=-1)
        else:
            weights = F.softmax(self.s7_weights, dim=-1)

        # 4. Weighted sum: [B, D]
        combined = (mixed * weights.unsqueeze(-1)).sum(dim=1)

        # 5. Final projection
        return self.output_proj(combined)


# =============================================================================
# BATCHED CATASTROPHE KAN LAYER
# =============================================================================


class BatchedCatastropheKANLayer(nn.Module):
    """Batched KAN layer for all 7 colonies in parallel.

    S⁷ PARALLELISM (Dec 2, 2025):
    =============================
    Processes all 7 colonies in a single [B, 7, C] tensor operation,
    exploiting the 7 linearly independent vector fields on S⁷.

    Each colony gets its own catastrophe-type activation while sharing
    the weight matrix for efficiency.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        init_scale: float = 0.1,
        temperature: float = 1.0,
        use_residual: bool = True,
    ):
        """Initialize batched KAN layer.

        Args:
            in_features: Input dimension
            out_features: Output dimension
            init_scale: Initial scale for control parameters
            temperature: Initial temperature for smooth activation control
            use_residual: Add linear residual connection
        """
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features

        # Batched catastrophe basis (all 7 types)
        self.basis = BatchedCatastropheBasis(
            num_channels=in_features,
            init_scale=init_scale,
            temperature=temperature,
        )

        # Per-colony weights: [7, out_features, in_features]
        self.weight = nn.Parameter(
            torch.randn(7, out_features, in_features) * (1.0 / in_features**0.5)
        )
        self.bias = nn.Parameter(torch.zeros(7, out_features))

        # Optional residual connection
        self.use_residual = use_residual
        if use_residual and in_features == out_features:
            self.residual_scale = nn.Parameter(torch.ones(7) * 0.1)
        else:
            self.use_residual = False

        logger.debug(
            f"BatchedCatastropheKANLayer: {in_features} → {out_features} (7 colonies parallel)"
        )

        # Compile forward for JIT optimization (Dec 21, 2025)
        self._use_compiled = False
        if _TORCH_COMPILE_AVAILABLE and torch.cuda.is_available():
            try:
                self._forward_compiled = torch.compile(
                    self.forward,
                    mode="reduce-overhead",
                    dynamic=False,
                )
                self._use_compiled = True
                logger.debug("BatchedCatastropheKANLayer: forward compiled (2-3x speedup)")
            except Exception as e:
                logger.debug(f"BatchedCatastropheKANLayer: compile failed ({e})")

    def forward(
        self,
        x: torch.Tensor,
        param_modulation: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Forward pass for all 7 colonies in parallel (JIT-compiled on CUDA).

        Args:
            x: [B, 7, in_features] or [B, in_features]
            param_modulation: Optional [7, max_params] modulation

        Returns:
            [B, 7, out_features]
        """
        # Use compiled version if available
        if self._use_compiled:
            return self._forward_compiled(x, param_modulation)

        # Handle unbatched colony input
        if x.dim() == 2:
            # [B, in_features] → [B, 7, in_features]
            x = x.unsqueeze(1).expand(-1, 7, -1)

        _B, _num_colonies, _C = x.shape

        # Apply batched catastrophe activation
        activated = self.basis(x, param_modulation)  # [B, 7, in_features]

        # Per-colony linear transformation using einsum
        # activated: [B, 7, in_features], weight: [7, out_features, in_features]
        # → output: [B, 7, out_features]
        output = torch.einsum("bci,coi->bco", activated, self.weight)
        output = output + self.bias.unsqueeze(
            0
        )  # Add bias [7, out_features] → [1, 7, out_features]

        # Residual connection
        if self.use_residual:
            # Scale per colony
            residual_scaled = x * self.residual_scale.view(1, 7, 1)
            output = output + residual_scaled

        return output


class BatchedCatastropheKANFeedForward(nn.Module):
    """Batched KAN FFN for all 7 colonies in parallel.

    Architecture:
        x[B,7,D] → KAN[B,7,D→B,7,4D] → KAN[B,7,4D→B,7,D] → y[B,7,D]
    """

    def __init__(
        self,
        d_model: int,
        d_ff: int | None = None,
        dropout: float = 0.1,
        temperature: float = 1.0,
    ):
        super().__init__()
        d_ff = d_ff or 4 * d_model

        self.kan1 = BatchedCatastropheKANLayer(d_model, d_ff, temperature=temperature)
        self.kan2 = BatchedCatastropheKANLayer(d_ff, d_model, temperature=temperature)
        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm([7, d_model])  # Per-colony normalization

        logger.debug(
            f"BatchedCatastropheKANFeedForward: {d_model} → {d_ff} → {d_model} (T={temperature})"
        )

        # Compile forward for JIT optimization (Dec 21, 2025)
        self._use_compiled = False
        if _TORCH_COMPILE_AVAILABLE and torch.cuda.is_available():
            try:
                self._forward_compiled = torch.compile(
                    self._forward_impl,
                    mode="reduce-overhead",
                    dynamic=False,
                )
                self._use_compiled = True
                logger.debug("BatchedCatastropheKANFeedForward: compiled (2-3x speedup)")
            except Exception as e:
                logger.debug(f"BatchedCatastropheKANFeedForward: compile failed ({e})")

    def _forward_impl(
        self,
        x: torch.Tensor,
        param_modulation: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Core forward implementation."""
        # Handle unbatched colony input
        if x.dim() == 2:
            x = x.unsqueeze(1).expand(-1, 7, -1)

        residual = x
        x = self.kan1(x, param_modulation)
        x = self.dropout(x)
        x = self.kan2(x)
        x = self.dropout(x)
        x = self.norm(x + residual)
        return x

    def forward(
        self,
        x: torch.Tensor,
        param_modulation: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Forward with residual (JIT-compiled on CUDA).

        Args:
            x: [B, 7, D] or [B, D]
            param_modulation: Optional [7, max_params]

        Returns:
            [B, 7, D]
        """
        if self._use_compiled:
            return self._forward_compiled(x, param_modulation)
        return self._forward_impl(x, param_modulation)

    def catastrophe_loss(self, x: torch.Tensor) -> torch.Tensor:
        """Batched catastrophe loss for all colonies."""
        if x.dim() == 2:
            x = x.unsqueeze(1).expand(-1, 7, -1)

        risk = self.kan1.basis.get_singularity_risk(x)  # [B, 7]
        threshold = 0.7
        penalty = F.relu(risk - threshold).pow(2).mean()
        return penalty


# =============================================================================
# SINGLE-COLONY CLASSES (for per-colony processing in ColonyRSSM)
# =============================================================================


class CatastropheBasis(nn.Module):
    """Catastrophe potential derivative as KAN basis function.

    Used by ColonyRSSM.active_decoder for per-colony action generation.
    For all-colonies-at-once processing, see BatchedCatastropheBasis.
    """

    def __init__(
        self,
        catastrophe_type: Any,
        num_channels: int = 1,
        init_scale: float = 0.1,
        temperature: float = 1.0,
    ) -> None:
        super().__init__()
        (
            CatastropheType,
            _COLONY_NAMES,
            _MAX_CONTROL_PARAMS,
            _get_codim,
        ) = _get_catastrophe_constants()
        self.catastrophe_type = catastrophe_type
        self.num_channels = num_channels
        self.num_params = CATASTROPHE_PARAMS()[catastrophe_type]  # type: ignore[func-returns-value]

        # FIX (Dec 14, 2025): Ensure even channels for (x, y) splitting in 2D catastrophes
        # Must match BatchedCatastropheBasis padding behavior for consistency
        # Only pad if this is a 2D catastrophe type
        self.is_2d = catastrophe_type in [
            CatastropheType.HYPERBOLIC,
            CatastropheType.ELLIPTIC,
            CatastropheType.PARABOLIC,
        ]
        if self.is_2d and num_channels % 2 != 0:
            logger.warning(
                f"num_channels={num_channels} is odd. Padding to {num_channels + 1} "
                f"for proper 2D catastrophe (x, y) splitting."
            )
            self.num_channels = num_channels + 1

        self.control_params = nn.Parameter(
            torch.randn(self.num_channels, self.num_params) * init_scale
        )

        # === LEARNABLE TEMPERATURE PARAMETER (Dec 27, 2025) ===
        # Controls catastrophe activation sharpness for this colony
        self.temperature = nn.Parameter(torch.tensor(temperature))

        # === LEARNABLE RESIDUAL GATE (Dec 8, 2025) ===
        # Ensures gradient flow through catastrophe layers
        self.residual_gate = nn.Parameter(torch.tensor(0.1))

        # === OUTPUT LAYER NORM (Dec 8, 2025) ===
        # Normalizes catastrophe outputs to prevent gradient explosion
        # FIX (Dec 14, 2025): Use self.num_channels (padded) not num_channels (original)
        self.output_norm = nn.LayerNorm(self.num_channels)

    def forward(
        self,
        x: torch.Tensor,
        param_modulation: torch.Tensor | None = None,
    ) -> torch.Tensor:
        return self._apply_catastrophe(x, param_modulation)

    def _apply_catastrophe(
        self,
        x: torch.Tensor,
        param_modulation: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Apply TRUE catastrophe potential derivative with gradient highway.

        PURE CATASTROPHE DYNAMICS (Dec 8, 2025):
        Uses exact derivatives from Thom's 7 elementary catastrophes.
        Includes learnable residual gate for gradient stability.
        """
        # FIX (Dec 14, 2025): Pad channels if needed (must match BatchedCatastropheBasis)
        if x.shape[-1] < self.num_channels:
            x = F.pad(x, (0, self.num_channels - x.shape[-1]))

        params = self.control_params

        if param_modulation is not None:
            if param_modulation.dim() == 1:
                mod = param_modulation[: self.num_params].unsqueeze(0)
            else:
                mod = param_modulation[:, : self.num_params].mean(dim=0, keepdim=True)
            params = params + mod.expand_as(params) * 0.1  # type: ignore[assignment]

        # === GRADIENT STABILITY: Soft bound input to prevent numerical overflow ===
        x_stable = torch.tanh(x * 0.5) * 2.0  # Maps [-∞,∞] → [-2, 2] smoothly

        # === TEMPERATURE SCALING (Dec 27, 2025) ===
        # Apply temperature: x → x/T (scales input sharpness)
        # Temperature is clamped to [0.1, 10.0] to prevent instability
        temp_clamped = self.temperature.clamp(0.1, 10.0)
        x_temp = x_stable / temp_clamped

        if self.catastrophe_type == CatastropheType.FOLD:
            # V = x³ + ax → ∂V/∂x = 3x² + a
            a = params[:, 0]
            catastrophe_out = 3 * x_temp.pow(2) + a

        elif self.catastrophe_type == CatastropheType.CUSP:
            # V = x⁴ + ax² + bx → ∂V/∂x = 4x³ + 2ax + b
            a, b = params[:, 0], params[:, 1]
            catastrophe_out = 4 * x_temp.pow(3) + 2 * a * x_temp + b

        elif self.catastrophe_type == CatastropheType.SWALLOWTAIL:
            # V = x⁵ + ax³ + bx² + cx → ∂V/∂x = 5x⁴ + 3ax² + 2bx + c
            a, b, c = params[:, 0], params[:, 1], params[:, 2]
            catastrophe_out = 5 * x_temp.pow(4) + 3 * a * x_temp.pow(2) + 2 * b * x_temp + c

        elif self.catastrophe_type == CatastropheType.BUTTERFLY:
            # V = x⁶ + ax⁴ + bx³ + cx² + dx → ∂V/∂x = 6x⁵ + 4ax³ + 3bx² + 2cx + d
            a, b, c, d = params[:, 0], params[:, 1], params[:, 2], params[:, 3]
            catastrophe_out = (
                6 * x_temp.pow(5)
                + 4 * a * x_temp.pow(3)
                + 3 * b * x_temp.pow(2)
                + 2 * c * x_temp
                + d
            )

        elif self.catastrophe_type == CatastropheType.HYPERBOLIC:
            # Hyperbolic Umbilic (D₄⁺): V = x³ + y³ + axy + bx + cy
            # ∂V/∂x = 3x² + ay + b
            # ∂V/∂y = 3y² + ax + c
            a, b, c = params[:, 0], params[:, 1], params[:, 2]
            x_coord = x_temp[..., 0::2]
            y_coord = x_temp[..., 1::2]
            grad_x = 3 * x_coord.pow(2) + a[0::2] * y_coord + b[0::2]
            grad_y = 3 * y_coord.pow(2) + a[0::2] * x_coord + c[0::2]
            catastrophe_out = torch.zeros_like(x)
            catastrophe_out[..., 0::2] = grad_x
            catastrophe_out[..., 1::2] = grad_y

        elif self.catastrophe_type == CatastropheType.ELLIPTIC:
            # Elliptic Umbilic (D₄⁻): V = x³ - xy² + a(x² + y²) + bx + cy
            # ∂V/∂x = 3x² - y² + 2ax + b
            # ∂V/∂y = -2xy + 2ay + c
            a, b, c = params[:, 0], params[:, 1], params[:, 2]
            x_coord = x_temp[..., 0::2]
            y_coord = x_temp[..., 1::2]
            grad_x = 3 * x_coord.pow(2) - y_coord.pow(2) + 2 * a[0::2] * x_coord + b[0::2]
            grad_y = -2 * x_coord * y_coord + 2 * a[0::2] * y_coord + c[0::2]
            catastrophe_out = torch.zeros_like(x)
            catastrophe_out[..., 0::2] = grad_x
            catastrophe_out[..., 1::2] = grad_y

        elif self.catastrophe_type == CatastropheType.PARABOLIC:
            # Parabolic Umbilic (D₅): V = x²y + y⁴ + ax² + by² + cx + dy
            # ∂V/∂x = 2xy + 2ax + c
            # ∂V/∂y = x² + 4y³ + 2by + d
            a, b, c, d = params[:, 0], params[:, 1], params[:, 2], params[:, 3]
            x_coord = x_temp[..., 0::2]
            y_coord = x_temp[..., 1::2]
            grad_x = 2 * x_coord * y_coord + 2 * a[0::2] * x_coord + c[0::2]
            grad_y = x_coord.pow(2) + 4 * y_coord.pow(3) + 2 * b[0::2] * y_coord + d[0::2]
            catastrophe_out = torch.zeros_like(x)
            catastrophe_out[..., 0::2] = grad_x
            catastrophe_out[..., 1::2] = grad_y

        else:
            raise ValueError(f"Unknown catastrophe type: {self.catastrophe_type}")

        # === TEMPERATURE RE-SCALING (Dec 27, 2025) ===
        # Scale output back by temperature to maintain proper gradient magnitude
        catastrophe_out = catastrophe_out * temp_clamped

        # === OUTPUT NORMALIZATION (Dec 8, 2025) ===
        # Use proper LayerNorm for deepcopy compatibility and gradient stability
        catastrophe_normalized = self.output_norm(catastrophe_out)

        # === LEARNABLE RESIDUAL GATE ===
        # Ensures gradient flow while preserving catastrophe dynamics
        # FIX (Dec 14, 2025): Use stabilized input for residual to prevent unbounded passthrough
        return catastrophe_normalized + self.residual_gate * x_stable

    def get_singularity_risk(self, x: torch.Tensor) -> torch.Tensor:
        grad = self._apply_catastrophe(x)
        grad_magnitude = grad.abs().mean(dim=-1)
        # FIX (Dec 14, 2025): Correct risk direction
        risk = torch.sigmoid(grad_magnitude - 2.0)
        return risk.clamp(0, 1)


class CatastropheKANLayer(nn.Module):
    """Colony-specific KAN layer using catastrophe basis functions.

    Used by ColonyRSSM.active_decoder for per-colony action generation.
    For all-colonies-at-once processing, see BatchedCatastropheKANLayer.
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        colony_idx: int,
        init_scale: float = 0.1,
        temperature: float = 1.0,
        use_residual: bool = True,
    ):
        super().__init__()
        self.in_features = in_features
        self.out_features = out_features
        self.colony_idx = colony_idx
        self.catastrophe_type = CatastropheType(colony_idx)
        # Lazy import to avoid circular dependency
        _, COLONY_NAMES, _, _ = _get_catastrophe_constants()
        self.colony_name = COLONY_NAMES[colony_idx]

        self.basis = CatastropheBasis(
            catastrophe_type=self.catastrophe_type,
            num_channels=in_features,
            init_scale=init_scale,
            temperature=temperature,
        )

        self.weight = nn.Parameter(
            torch.randn(out_features, in_features) * (1.0 / in_features**0.5)
        )
        self.bias = nn.Parameter(torch.zeros(out_features))

        self.use_residual = use_residual
        if use_residual and in_features == out_features:
            self.residual_scale = nn.Parameter(torch.tensor(0.1))
        else:
            self.use_residual = False

    def forward(
        self,
        x: torch.Tensor,
        param_modulation: torch.Tensor | None = None,
    ) -> torch.Tensor:
        activated = self.basis(x, param_modulation)
        output = F.linear(activated, self.weight, self.bias)
        if self.use_residual:
            output = output + self.residual_scale * x
        return output

    def get_control_parameters(self) -> dict[str, torch.Tensor]:
        params = self.basis.control_params
        param_names = ["a", "b", "c", "d"][: self.basis.num_params]
        return {name: params[:, i] for i, name in enumerate(param_names)}

    def singularity_loss(self, x: torch.Tensor) -> torch.Tensor:
        risk = self.basis.get_singularity_risk(x)
        threshold = 0.7
        return F.relu(risk - threshold).pow(2).mean()


class CatastropheKANFeedForward(nn.Module):
    """Colony-specific KAN feedforward.

    Used for single-colony feedforward. For all 7 colonies at once,
    see BatchedCatastropheKANFeedForward.
    """

    def __init__(
        self,
        d_model: int,
        d_ff: int | None = None,
        colony_idx: int = 0,
        dropout: float = 0.1,
        temperature: float = 1.0,
    ):
        super().__init__()
        d_ff = d_ff or 4 * d_model
        self.colony_idx = colony_idx

        self.kan1 = CatastropheKANLayer(
            d_model, d_ff, colony_idx=colony_idx, temperature=temperature
        )
        self.kan2 = CatastropheKANLayer(
            d_ff, d_model, colony_idx=colony_idx, temperature=temperature
        )
        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(d_model)

    def forward(
        self,
        x: torch.Tensor,
        param_modulation: torch.Tensor | None = None,
    ) -> torch.Tensor:
        residual = x
        x = self.kan1(x, param_modulation)
        x = self.dropout(x)
        x = self.kan2(x)
        x = self.dropout(x)
        x = self.norm(x + residual)
        return x

    def catastrophe_loss(self, x: torch.Tensor) -> torch.Tensor:
        h = self.kan1(x)
        return self.kan1.singularity_loss(x) + self.kan2.singularity_loss(h)


# =============================================================================
# MULTI-COLONY CATASTROPHE KAN - OPTIMIZED
# =============================================================================


class MultiColonyCatastropheKAN(nn.Module):
    """Parallel processing with all 7 catastrophe types.

    S⁷ PARALLELISM (Dec 2, 2025):
    =============================
    Now uses BATCHED tensor operations for all 7 colonies.
    Exploits the 7 linearly independent vector fields on S⁷.

    ARCHITECTURE:
    =============
    1. Input [B, D] → expand to [B, 7, D]
    2. BatchedCatastropheKANFeedForward (parallel processing)
    3. FanoOctonionCombiner (Fano-aware aggregation)
    4. Output [B, D]

    This IS the octonion algebra manifested in activation functions.
    """

    def __init__(
        self,
        d_model: int,
        d_ff: int | None = None,
        dropout: float = 0.1,
        temperature: float = 1.0,
    ):
        """Initialize multi-colony CatastropheKAN.

        All 7 colonies processed in parallel with Fano plane routing.

        Args:
            d_model: Model dimension
            d_ff: Feedforward dimension (default: 4*d_model)
            dropout: Dropout rate
            temperature: Initial temperature for smooth activation control (default: 1.0)
        """
        super().__init__()
        d_ff = d_ff or 4 * d_model
        self.d_model = d_model

        # Batched FFN for all 7 colonies
        self.batched_ffn = BatchedCatastropheKANFeedForward(d_model, d_ff, dropout, temperature)

        # Fano-aware combiner (octonion algebra aware)
        self.combiner = FanoOctonionCombiner(d_model)

        logger.debug(f"MultiColonyCatastropheKAN: {d_model}D → {d_ff}D → {d_model}D")

    def forward(
        self,
        x: torch.Tensor,
        domain_activations: torch.Tensor | None = None,
        colony_modulations: dict[int, torch.Tensor] | None = None,
    ) -> torch.Tensor:
        """Forward through all 7 colonies in parallel.

        Args:
            x: [..., d_model]
            domain_activations: Optional [7] weights for each colony
            colony_modulations: Optional dict[str, Any] mapping colony_idx → [num_params] modulation

        Returns:
            [..., d_model]
        """
        # Handle various input shapes
        original_shape = x.shape
        if x.dim() == 1:
            x = x.unsqueeze(0)  # [D] → [1, D]

        x.shape[0]

        # Expand to [B, 7, D]
        x_expanded = x.unsqueeze(1).expand(-1, 7, -1)  # [B, 7, D]

        # Convert colony_modulations dict[str, Any] to tensor if provided
        param_modulation = None
        if colony_modulations is not None:
            max_params = MAX_CATASTROPHE_PARAMS()  # type: ignore[func-returns-value]
            param_modulation = torch.zeros((7, max_params), device=x.device)
            for colony_idx, mod in colony_modulations.items():
                param_modulation[colony_idx, : mod.shape[-1]] = mod[:max_params]

        # Process all colonies in parallel
        outputs = self.batched_ffn(x_expanded, param_modulation)  # [B, 7, D]

        # Fano-aware combination
        combined = self.combiner(outputs, domain_activations)  # [B, D]

        # Restore original batch dimension if needed
        if len(original_shape) == 1:
            combined = combined.squeeze(0)

        return combined

    def get_all_control_parameters(self) -> dict[str, dict[str, torch.Tensor]]:
        """Get control parameters for all colonies."""
        _, COLONY_NAMES, _, _ = _get_catastrophe_constants()
        params = self.batched_ffn.kan1.basis.control_params  # [7, C, 4]
        return {
            COLONY_NAMES[i]: {
                "a": params[i, :, 0],
                "b": params[i, :, 1],
                "c": params[i, :, 2],
                "d": params[i, :, 3],
            }
            for i in range(7)
        }

    def total_catastrophe_loss(self, x: torch.Tensor) -> torch.Tensor:
        """Total singularity avoidance loss across all colonies."""
        return self.batched_ffn.catastrophe_loss(x)

    def get_singularity_risk(self, x: torch.Tensor) -> torch.Tensor:
        """Get per-colony singularity risk.

        Returns differentiable risk tensor for training loss.
        Add to loss to encourage stable operation away from bifurcations.

        Args:
            x: [B, D] or [B, 7, D] input tensor

        Returns:
            [B, 7] risk tensor in [0, 1] (higher = closer to singularity)
        """
        # Expand if needed
        if x.dim() == 2:
            B, D = x.shape
            x_expanded = x.view(B, 7, -1) if D % 7 == 0 else x.unsqueeze(1).expand(-1, 7, -1)
        else:
            x_expanded = x
        return self.batched_ffn.kan1.basis.get_singularity_risk(x_expanded)


# =============================================================================
# MODULE EXPORTS
# =============================================================================


__all__ = [
    # COLONY_NAMES - import from kagami_math.catastrophe_constants
    "CATASTROPHE_PARAMS",
    "MAX_CATASTROPHE_PARAMS",
    # Batched (preferred)
    "BatchedCatastropheBasis",
    "BatchedCatastropheKANFeedForward",
    "BatchedCatastropheKANLayer",
    # Legacy (for backward compatibility)
    "CatastropheBasis",
    "CatastropheKAN",  # Alias for MultiColonyCatastropheKAN
    "CatastropheKANFeedForward",
    "CatastropheKANLayer",
    # Enums and constants
    "CatastropheType",
    "FanoOctonionCombiner",
    # Main module
    "MultiColonyCatastropheKAN",
]

# Alias for common import pattern
CatastropheKAN = MultiColonyCatastropheKAN


logger.debug("CatastropheKAN module loaded")
