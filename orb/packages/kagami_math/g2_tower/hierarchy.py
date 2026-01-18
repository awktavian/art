"""Scalable G₂ Hierarchy combining all optimizations.

Integrates:
1. G2IrrepTower for tensor product expansion
2. G2CrossCopyInteraction for rep_multiplier scaling
3. Hardware-optimized configuration
4. Modern deep learning techniques (Pre-LayerNorm, Stochastic Depth, GLU)
"""

from __future__ import annotations

import logging
from typing import Literal

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami_math.g2_forms import G2PhiPsi

from .cross_copy import G2CrossCopyInteraction
from .hardware import G2HardwareConfig, get_optimal_g2_config
from .tower import G2IrrepTower

logger = logging.getLogger(__name__)


class ScalableG2Hierarchy(nn.Module):
    """Scalable G₂-equivariant hierarchy combining all optimizations.

    ENHANCED (Dec 2, 2025) with modern deep learning techniques:
    1. G2IrrepTower for tensor product expansion (7⊗7 → 1⊕7⊕14⊕27)
    2. G2CrossCopyInteraction for rep_multiplier scaling
    3. Hardware-optimized configuration
    4. Pre-LayerNorm (better gradient flow, used in GPT-2+)
    5. Stochastic depth / DropPath (from DeiT/Swin)
    6. SiLU activation (used in Mamba, Gated Linear Units)
    7. Residual scaling (like DreamerV3/Mamba-2)

    Use this as a drop-in replacement for the G₂ layers in the
    UnifiedEquivariantHourglass.
    """

    def __init__(
        self,
        input_dim: int = 7,
        output_dim: int = 7,
        config: G2HardwareConfig | None = None,
        num_layers: int = 3,
        drop_path_rate: float = 0.1,  # Stochastic depth
        use_gated: bool = True,  # Gated Linear Unit style
    ):
        """Initialize scalable G₂ hierarchy.

        Args:
            input_dim: Input dimension (should be 7 or 7*k)
            output_dim: Output dimension (typically same as input)
            config: Hardware configuration
            num_layers: Number of processing layers
            drop_path_rate: Stochastic depth drop rate (0 = no drop)
            use_gated: Use Gated Linear Unit (GLU) style residuals
        """
        super().__init__()

        self.config = config or G2HardwareConfig()
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.num_layers = num_layers
        self.drop_path_rate = drop_path_rate
        self.use_gated = use_gated

        # Determine rep_multiplier from input dim
        self.rep_multiplier = max(1, input_dim // 7)

        # === PRE-LAYERNORM (applied BEFORE each layer) ===
        self.pre_norms = nn.ModuleList([nn.LayerNorm(input_dim) for _ in range(num_layers)])

        # === IRREP TOWER (stacked residual blocks) ===
        self.irrep_towers = nn.ModuleList(
            [
                G2IrrepTower(
                    config=self.config,
                    target_dim=input_dim,
                    num_layers=2,
                )
                for _ in range(num_layers)
            ]
        )

        # === GATED LINEAR UNIT (GLU) for each layer ===
        # GLU: output = x * sigmoid(gate)
        # This helps control gradient flow and learning dynamics
        if use_gated:
            self.gates: nn.ModuleList | None = nn.ModuleList(
                [
                    nn.Sequential(
                        nn.Linear(input_dim, input_dim),
                        nn.Sigmoid(),
                    )
                    for _ in range(num_layers)
                ]
            )
        else:
            self.gates = None

        # === STOCHASTIC DEPTH (DropPath) ===
        # Linearly increasing drop rate per layer (DeiT style)
        if drop_path_rate > 0:
            drop_rates = [
                drop_path_rate * i / (num_layers - 1) if num_layers > 1 else 0
                for i in range(num_layers)
            ]
        else:
            drop_rates = [0.0] * num_layers
        self.drop_path_rates = drop_rates

        # === RESIDUAL SCALING (learnable, like Mamba-2) ===
        # Initialized small to stabilize early training
        self.residual_scales = nn.ParameterList(
            [nn.Parameter(torch.tensor(0.1)) for _ in range(num_layers)]
        )

        # === CROSS-COPY INTERACTIONS (if k > 1) ===
        self.cross_copy: nn.ModuleList | None
        if self.rep_multiplier > 1 and self.config.enable_cross_copy:
            self.cross_copy = nn.ModuleList(
                [
                    G2CrossCopyInteraction(
                        rep_multiplier=self.rep_multiplier,
                        hidden_dim=64,
                        use_attention=True,
                    )
                    for _ in range(num_layers)
                ]
            )
        else:
            self.cross_copy = None

        # G₂ structures - registered submodule so it moves with .to()
        self._g2_struct = G2PhiPsi(device=torch.device("cpu"))

        # === FINAL LAYERNORM ===
        self.final_norm = nn.LayerNorm(input_dim)

        # Output projection if dimensions differ
        self.output_proj: nn.Linear | None
        if output_dim != input_dim:
            self.output_proj = nn.Linear(input_dim, output_dim)
        else:
            self.output_proj = None

        # Log configuration
        total_params = sum(p.numel() for p in self.parameters())
        logger.debug(
            f"ScalableG2Hierarchy: rep_mult={self.rep_multiplier}, params={total_params:,}"
        )

    def _drop_path(self, x: torch.Tensor, drop_prob: float) -> torch.Tensor:
        """Apply stochastic depth (DropPath) during training.

        Args:
            x: Input tensor
            drop_prob: Drop probability

        Returns:
            x with stochastic depth applied
        """
        if drop_prob == 0.0 or not self.training:
            return x

        keep_prob = 1 - drop_prob
        shape = (x.shape[0],) + (1,) * (x.ndim - 1)
        random_tensor = keep_prob + torch.rand(shape, dtype=x.dtype, device=x.device)
        random_tensor.floor_()  # Binarize
        output = x.div(keep_prob) * random_tensor
        return output

    def forward(
        self,
        x: torch.Tensor,
        return_intermediates: bool = False,
    ) -> torch.Tensor | dict[str, torch.Tensor]:
        """Process input through scalable G₂ hierarchy.

        ARCHITECTURE (Dec 2, 2025):
        - Pre-LayerNorm for each layer
        - Irrep Tower processes 7D copies
        - Optional Gated Linear Unit
        - Stochastic Depth (DropPath)
        - Learnable residual scaling
        - Cross-copy interactions (if k > 1)
        - Final LayerNorm

        Args:
            x: [..., input_dim] input
            return_intermediates: Return all layer outputs

        Returns:
            [..., output_dim] output or dict with intermediates
        """
        intermediates: dict[str, torch.Tensor] | None = (
            {"input": x} if return_intermediates else None
        )

        h = x

        for i in range(self.num_layers):
            # Store residual
            residual = h

            # === PRE-LAYERNORM (better gradient flow) ===
            h_normed = self.pre_norms[i](h)

            # === IRREP TOWER PROCESSING ===
            # Process each 7D copy through irrep tower
            copies = list(h_normed.split(7, dim=-1))
            tower_outputs = []

            for _j, copy in enumerate(copies):
                tower_out = self.irrep_towers[i](copy)
                # Project back to 7D
                tower_out_7d = (
                    tower_out[..., :7]
                    if tower_out.shape[-1] >= 7
                    else F.pad(tower_out, (0, 7 - tower_out.shape[-1]))
                )
                tower_outputs.append(tower_out_7d)

            h = torch.cat(tower_outputs, dim=-1)

            # === CROSS-COPY INTERACTION ===
            if self.cross_copy is not None:
                h = self.cross_copy[i](h)

            # === GATED LINEAR UNIT (optional) ===
            if self.gates is not None:
                gate = self.gates[i](residual)
                h = h * gate

            # === STOCHASTIC DEPTH (DropPath) ===
            h = self._drop_path(h, self.drop_path_rates[i])

            # === RESIDUAL WITH LEARNABLE SCALING ===
            scale = self.residual_scales[i]
            h = residual + h * scale

            if return_intermediates and intermediates is not None:
                intermediates[f"layer_{i}"] = h

        # === FINAL LAYERNORM ===
        h = self.final_norm(h)

        # Output projection
        if self.output_proj is not None:
            h = self.output_proj(h)

        if return_intermediates and intermediates is not None:
            intermediates["output"] = h
            return intermediates

        return h  # type: ignore[no-any-return]


def create_optimal_g2_hierarchy(
    input_dim: int = 7,
    output_dim: int = 7,
    hardware: Literal[
        "mps_512gb", "mps_128gb", "cuda_a100", "cuda_h100", "cuda_rtx", "cpu", "auto"
    ] = "auto",
    model_size: Literal["nano", "small", "base", "large", "xl"] = "base",
) -> ScalableG2Hierarchy:
    """Create optimally configured G₂ hierarchy.

    Args:
        input_dim: Input dimension
        output_dim: Output dimension
        hardware: Hardware target
        model_size: Model size preset

    Returns:
        Configured ScalableG2Hierarchy
    """
    config = get_optimal_g2_config(hardware, model_size)

    # Adjust input_dim based on rep_multiplier if needed
    if input_dim == 7 and config.rep_multiplier > 1:
        input_dim = 7 * config.rep_multiplier
        output_dim = 7 * config.rep_multiplier if output_dim == 7 else output_dim

    return ScalableG2Hierarchy(
        input_dim=input_dim,
        output_dim=output_dim,
        config=config,
        num_layers=3,
    )


__all__ = [
    "ScalableG2Hierarchy",
    "create_optimal_g2_hierarchy",
]
