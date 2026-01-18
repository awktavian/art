"""Sparse Octonion Activation

Activate only relevant imaginary units per modality:
- vision → i₁ (primary visual direction)
- audio → i₂ (auditory)
- language → i₃ (semantic)
- etc.

Benefits:
- Computational efficiency (skip inactive units)
- Interpretability (each unit has semantic meaning)
- Regularization (sparsity encourages structured representations)
"""

import logging

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class SparseOctonionActivation(nn.Module):
    """Sparse activation over octonion imaginary units.

    Strategy:
    - Learn which imaginary units are active for each input
    - Apply soft gating (sigmoid) or hard gating (top-k)
    - Preserve unit norm on S⁷
    """

    def __init__(self, mode: str = "soft", top_k: int = 4, learn_gates: bool = True) -> None:
        super().__init__()
        self.mode = mode
        self.top_k = top_k
        if learn_gates:
            self.gate_net = nn.Sequential(
                nn.Linear(8, 16),
                nn.Tanh(),
                nn.Linear(16, 7),
                nn.Sigmoid() if mode == "soft" else nn.Identity(),
            ).to(torch.float32)
        else:
            self.gate_net = None  # type: ignore[assignment]
        logger.info(f"✅ Sparse octonion: mode={mode}, top_k={top_k}")

    def forward(
        self, o: torch.Tensor, modality_hints: dict[str, float] | None = None
    ) -> torch.Tensor:
        """Apply sparse activation.

        Args:
            o: [B, 8] octonions
            modality_hints: Optional dict[str, Any] mapping modality to activation strength

        Returns:
            o_sparse: [B, 8] with sparse imaginary components
        """
        B = o.shape[0]
        original_dtype = o.dtype
        gate_dtype = original_dtype
        if self.gate_net is not None:
            try:
                gate_dtype = next(self.gate_net.parameters()).dtype
            except StopIteration:
                gate_dtype = original_dtype
        if original_dtype in (torch.float16, torch.bfloat16):
            gate_dtype = torch.float32 if gate_dtype == original_dtype else gate_dtype
        needs_cast = original_dtype != gate_dtype
        o_work = o.to(dtype=gate_dtype) if needs_cast else o
        real = o_work[:, 0:1]
        imag = o_work[:, 1:]
        if self.gate_net is not None:
            gates = self.gate_net(o_work)
        elif modality_hints is not None:
            modality_to_unit = {
                "vision": 0,
                "audio": 1,
                "language": 2,
                "touch": 3,
                "proprioception": 4,
                "interoception": 5,
                "meta": 6,
            }
            gates = torch.zeros(B, 7, device=o_work.device, dtype=o_work.dtype)
            for mod, strength in modality_hints.items():
                if mod in modality_to_unit:
                    gates[:, modality_to_unit[mod]] = strength
        else:
            gates = torch.ones(B, 7, device=o_work.device, dtype=o_work.dtype)
        if self.mode == "soft":
            imag_gated = imag * gates
        elif self.mode == "hard":
            _, top_indices = torch.topk(gates, k=min(self.top_k, 7), dim=-1)
            mask = torch.zeros_like(gates)
            mask.scatter_(1, top_indices, 1.0)
            imag_gated = imag * mask
        else:
            imag_gated = imag
        o_sparse = torch.cat([real, imag_gated], dim=-1)
        o_sparse = o_sparse / (o_sparse.norm(dim=-1, keepdim=True) + 1e-15)
        if needs_cast and original_dtype == torch.float16:
            o_sparse = o_sparse.to(original_dtype)
        final_norm = o_sparse.float().norm(dim=-1, keepdim=True)
        final_norm = final_norm.clamp_min(1e-12).to(o_sparse.dtype)
        o_sparse = o_sparse / final_norm
        return o_sparse

    def get_activation_stats(self, o: torch.Tensor) -> dict[str, float]:
        """Compute sparsity statistics."""
        with torch.no_grad():
            original_dtype = o.dtype
            gate_dtype = original_dtype
            if self.gate_net is not None:
                try:
                    gate_dtype = next(self.gate_net.parameters()).dtype
                except StopIteration:
                    gate_dtype = original_dtype
            if original_dtype in (torch.float16, torch.bfloat16):
                gate_dtype = torch.float32 if gate_dtype == original_dtype else gate_dtype
            o_work = o.to(dtype=gate_dtype) if original_dtype != gate_dtype else o
            imag = o_work[:, 1:]
            if self.gate_net is not None:
                gates = self.gate_net(o_work)
            else:
                gates = torch.ones_like(imag)
            return {
                "mean_active_units": (gates > 0.5).float().sum(dim=-1).mean().item(),
                "sparsity": 1.0 - gates.mean().item(),
                "max_activation": gates.max().item(),
                "min_activation": gates.min().item(),
            }
