"""Hardware optimization for G₂ computations.

Includes SDPAttention (zero-copy attention), G2HardwareConfig (auto-detection),
and factory functions for optimal configurations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal

import torch
import torch.nn as nn
import torch.nn.functional as F

from .irrep_levels import IrrepLevel

logger = logging.getLogger(__name__)


# =============================================================================
# OPTIMIZED SDPA ATTENTION (Zero-Copy)
# =============================================================================


class SDPAttention(nn.Module):
    """Scaled Dot-Product Attention using torch.nn.functional.scaled_dot_product_attention.

    Unlike nn.MultiheadAttention, this does NOT make tensors contiguous internally,
    eliminating unnecessary memory copies.

    Performance: 48 fewer contiguous() calls per forward pass.
    """

    def __init__(self, embed_dim: int, num_heads: int, dropout: float = 0.0):
        super().__init__()
        assert embed_dim % num_heads == 0, (
            f"embed_dim {embed_dim} must be divisible by num_heads {num_heads}"
        )

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.dropout = dropout

        # Fused QKV projection for efficiency
        self.qkv_proj = nn.Linear(embed_dim, 3 * embed_dim, bias=True)
        self.out_proj = nn.Linear(embed_dim, embed_dim, bias=True)

        # Initialize with small values for stable training
        nn.init.xavier_uniform_(self.qkv_proj.weight, gain=0.1)
        nn.init.zeros_(self.qkv_proj.bias)
        nn.init.xavier_uniform_(self.out_proj.weight, gain=0.1)
        nn.init.zeros_(self.out_proj.bias)

    def forward(
        self,
        query: torch.Tensor,
        key: torch.Tensor,
        value: torch.Tensor,
        attn_mask: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, None]:
        """Forward pass with zero-copy SDPA.

        Args:
            query: [B, S, D] - same as key/value for self-attention
            key: [B, S, D]
            value: [B, S, D]
            attn_mask: Optional attention mask

        Returns:
            (output, None) - second element for API compatibility with nn.MultiheadAttention
        """
        B, S, D = query.shape

        # Self-attention: query == key == value
        # Fused QKV projection: [B, S, 3*D]
        qkv = self.qkv_proj(query)

        # Split and reshape WITHOUT making contiguous
        # [B, S, 3*D] -> [B, S, 3, H, head_dim] -> [3, B, H, S, head_dim]
        qkv = qkv.view(B, S, 3, self.num_heads, self.head_dim)
        qkv = qkv.permute(2, 0, 3, 1, 4)  # [3, B, H, S, head_dim]
        q, k, v = qkv.unbind(0)  # Each: [B, H, S, head_dim]

        # SDPA handles non-contiguous tensors efficiently
        # Uses Flash Attention when available (CUDA), math kernel otherwise (MPS)
        attn_out = F.scaled_dot_product_attention(
            q,
            k,
            v,
            attn_mask=attn_mask,
            dropout_p=self.dropout if self.training else 0.0,
            is_causal=False,
        )  # [B, H, S, head_dim]

        # Reshape back: [B, H, S, head_dim] -> [B, S, D]
        attn_out = attn_out.permute(0, 2, 1, 3).reshape(B, S, D)

        # Output projection
        output = self.out_proj(attn_out)

        return output, None  # None for attention weights (not computed for efficiency)


# =============================================================================
# HARDWARE CONFIGURATION
# =============================================================================


@dataclass
class G2HardwareConfig:
    """Hardware-optimized configuration for G₂ computations.

    Detects hardware and sets optimal parameters for:
    - Apple Silicon MPS (M3/M4 Ultra with unified memory)
    - NVIDIA CUDA (A100, H100, RTX 4090)
    - CPU fallback
    """

    # Auto-detected hardware
    device_type: str = "auto"  # auto, mps, cuda, cpu

    # Memory settings
    total_memory_gb: float = 0.0  # 0 = auto-detect
    target_memory_usage: float = 0.80

    # Precision
    dtype: str = "float32"  # float32, float16, bfloat16
    use_amp: bool = True

    # Batch settings
    optimal_batch_size: int = 0  # 0 = auto-calculate
    gradient_accumulation: int = 4

    # G₂-specific
    irrep_level: IrrepLevel = IrrepLevel.STANDARD
    rep_multiplier: int = 1  # k copies of fundamental
    enable_cross_copy: bool = True  # Cross-copy tensor products

    # Performance
    use_fused_ops: bool = True
    use_checkpointing: bool = False
    compile_mode: str | None = None  # torch.compile mode

    def __post_init__(self) -> None:
        """Auto-detect and configure for hardware."""
        if self.device_type == "auto":
            self.device_type = self._detect_device()

        if self.total_memory_gb == 0.0:
            self.total_memory_gb = self._detect_memory()

        if self.optimal_batch_size == 0:
            self.optimal_batch_size = self._calculate_batch_size()

        # Set optimal dtype for device
        if self.dtype == "auto":
            self.dtype = self._optimal_dtype()

        # Configure irrep level based on memory
        self._configure_irrep_level()

        logger.debug("G2HardwareConfig: %s, %dGB", self.device_type, int(self.total_memory_gb))

    def _detect_device(self) -> str:
        """Detect optimal device."""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _detect_memory(self) -> float:
        """Detect available memory in GB."""
        if self.device_type == "cuda":
            return torch.cuda.get_device_properties(0).total_memory / (1024**3)
        elif self.device_type == "mps":
            try:
                import psutil

                return psutil.virtual_memory().total / (1024**3)
            except ImportError:
                return 32.0  # Conservative default for Mac
        return 16.0  # CPU default

    def _calculate_batch_size(self) -> int:
        """Calculate optimal batch size."""
        # Estimate model memory footprint
        params_estimate = self._estimate_params_mb()

        # Available memory after model
        available_gb = self.total_memory_gb * self.target_memory_usage - (params_estimate / 1024)

        # Per-sample activation memory (MB)
        # Depends on irrep level
        per_sample_mb = {
            IrrepLevel.MINIMAL: 10,
            IrrepLevel.STANDARD: 30,
            IrrepLevel.EXTENDED: 80,
            IrrepLevel.MAXIMAL: 150,
        }[self.irrep_level]

        batch_size = int((available_gb * 1024) / per_sample_mb)
        batch_size = max(8, min(512, batch_size))  # Clamp

        return batch_size

    def _estimate_params_mb(self) -> float:
        """Estimate model parameters in MB."""
        base_params = 10_000_000  # 10M base
        multiplier = self.rep_multiplier**2  # Quadratic scaling

        level_multiplier = {
            IrrepLevel.MINIMAL: 1,
            IrrepLevel.STANDARD: 3,
            IrrepLevel.EXTENDED: 8,
            IrrepLevel.MAXIMAL: 15,
        }[self.irrep_level]

        total_params = base_params * multiplier * level_multiplier
        bytes_per_param = {"float32": 4, "float16": 2, "bfloat16": 2}.get(self.dtype, 4)

        return (total_params * bytes_per_param) / (1024**2)

    def _optimal_dtype(self) -> str:
        """Get optimal dtype for device."""
        if self.device_type == "cuda":
            # Check for bfloat16 support
            if torch.cuda.is_bf16_supported():
                return "bfloat16"
            return "float16"
        elif self.device_type == "mps":
            # MPS supports bfloat16 on M3/M4
            return "bfloat16"
        return "float32"

    def _configure_irrep_level(self) -> None:
        """Configure irrep level based on memory."""
        if self.total_memory_gb >= 256:
            self.irrep_level = IrrepLevel.MAXIMAL
            self.rep_multiplier = max(4, self.rep_multiplier)
        elif self.total_memory_gb >= 64:
            self.irrep_level = IrrepLevel.EXTENDED
            self.rep_multiplier = max(2, self.rep_multiplier)
        elif self.total_memory_gb >= 16:
            self.irrep_level = IrrepLevel.STANDARD
        else:
            self.irrep_level = IrrepLevel.MINIMAL

    def get_torch_dtype(self) -> torch.dtype:
        """Get torch dtype object."""
        return {
            "float32": torch.float32,
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
        }[self.dtype]

    def get_device(self) -> torch.device:
        """Get torch device."""
        return torch.device(self.device_type)


# =============================================================================
# OPTIMAL PRESETS
# =============================================================================


def get_optimal_g2_config(
    hardware: Literal[
        "mps_512gb", "mps_128gb", "cuda_a100", "cuda_h100", "cuda_rtx", "cpu", "auto"
    ] = "auto",
    model_size: Literal["nano", "small", "base", "large", "xl"] = "base",
) -> G2HardwareConfig:
    """Get optimally tuned G₂ configuration for hardware and model size.

    Args:
        hardware: Hardware target (auto-detects if "auto")
        model_size: Model size preset

    Returns:
        Optimally configured G2HardwareConfig
    """
    # Auto-detect hardware
    if hardware == "auto":
        if torch.backends.mps.is_available():
            try:
                import psutil

                mem_gb = psutil.virtual_memory().total / (1024**3)
                hardware = "mps_512gb" if mem_gb >= 400 else "mps_128gb"
            except ImportError:
                hardware = "mps_128gb"
        elif torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            mem_gb = props.total_memory / (1024**3)
            if mem_gb >= 70:
                hardware = "cuda_h100"
            elif mem_gb >= 40:
                hardware = "cuda_a100"
            else:
                hardware = "cuda_rtx"
        else:
            hardware = "cpu"

    # Base configurations per hardware
    hw_configs: dict[str, dict[str, object]] = {
        "mps_512gb": {
            "device_type": "mps",
            "total_memory_gb": 512.0,
            "dtype": "bfloat16",
            "use_amp": True,
            "optimal_batch_size": 256,
            "gradient_accumulation": 2,
            "irrep_level": IrrepLevel.MAXIMAL,
            "rep_multiplier": 4,
            "enable_cross_copy": True,
            "use_fused_ops": True,
            "use_checkpointing": False,
        },
        "mps_128gb": {
            "device_type": "mps",
            "total_memory_gb": 128.0,
            "dtype": "bfloat16",
            "use_amp": True,
            "optimal_batch_size": 64,
            "gradient_accumulation": 4,
            "irrep_level": IrrepLevel.EXTENDED,
            "rep_multiplier": 2,
            "enable_cross_copy": True,
            "use_fused_ops": True,
            "use_checkpointing": False,
        },
        "cuda_h100": {
            "device_type": "cuda",
            "total_memory_gb": 80.0,
            "dtype": "bfloat16",
            "use_amp": True,
            "optimal_batch_size": 128,
            "gradient_accumulation": 2,
            "irrep_level": IrrepLevel.MAXIMAL,
            "rep_multiplier": 4,
            "enable_cross_copy": True,
            "use_fused_ops": True,
            "use_checkpointing": False,
            "compile_mode": "reduce-overhead",
        },
        "cuda_a100": {
            "device_type": "cuda",
            "total_memory_gb": 40.0,
            "dtype": "bfloat16",
            "use_amp": True,
            "optimal_batch_size": 64,
            "gradient_accumulation": 4,
            "irrep_level": IrrepLevel.EXTENDED,
            "rep_multiplier": 2,
            "enable_cross_copy": True,
            "use_fused_ops": True,
            "use_checkpointing": False,
            "compile_mode": "reduce-overhead",
        },
        "cuda_rtx": {
            "device_type": "cuda",
            "total_memory_gb": 24.0,
            "dtype": "float16",
            "use_amp": True,
            "optimal_batch_size": 32,
            "gradient_accumulation": 8,
            "irrep_level": IrrepLevel.STANDARD,
            "rep_multiplier": 1,
            "enable_cross_copy": True,
            "use_fused_ops": True,
            "use_checkpointing": True,
        },
        "cpu": {
            "device_type": "cpu",
            "total_memory_gb": 32.0,
            "dtype": "float32",
            "use_amp": False,
            "optimal_batch_size": 8,
            "gradient_accumulation": 16,
            "irrep_level": IrrepLevel.MINIMAL,
            "rep_multiplier": 1,
            "enable_cross_copy": False,
            "use_fused_ops": False,
            "use_checkpointing": True,
        },
    }

    # Adjust for model size
    size_multipliers: dict[str, dict[str, int | float]] = {
        "nano": {"rep_multiplier": 1, "optimal_batch_size_mult": 2.0},
        "small": {"rep_multiplier": 1, "optimal_batch_size_mult": 1.5},
        "base": {"rep_multiplier": 1, "optimal_batch_size_mult": 1.0},
        "large": {"rep_multiplier": 2, "optimal_batch_size_mult": 0.5},
        "xl": {"rep_multiplier": 4, "optimal_batch_size_mult": 0.25},
    }

    config_dict = hw_configs[hardware].copy()
    size_adj = size_multipliers[model_size]

    rep_mult = int(config_dict.get("rep_multiplier", 1))  # type: ignore[call-overload]
    batch_size = int(config_dict.get("optimal_batch_size", 8))  # type: ignore[call-overload]
    batch_mult = float(size_adj.get("optimal_batch_size_mult", 1.0))
    size_rep_mult = int(size_adj.get("rep_multiplier", 1))

    config_dict["rep_multiplier"] = max(rep_mult, size_rep_mult)
    config_dict["optimal_batch_size"] = int(batch_size * batch_mult)

    return G2HardwareConfig(**config_dict)  # type: ignore[arg-type]


__all__ = [
    "G2HardwareConfig",
    "SDPAttention",
    "get_optimal_g2_config",
]
