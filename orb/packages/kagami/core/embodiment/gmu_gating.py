"""Gated Multimodal Unit (GMU) - Reliability-Aware Fusion

Based on Arevalo et al. (2017): "Gated Multimodal Units for Information Fusion"
- Learn modality-specific gates based on reliability/quality
- Adaptive weighting: emphasize reliable modalities, suppress noisy ones
- Differentiable: trained end-to-end with task loss

Key insight: Not all modalities are equally reliable at all times.
- Vision may be occluded → reduce weight
- Audio may be noisy → reduce weight
- Language may be ambiguous → reduce weight

GMU learns these patterns automatically via sigmoid gates.

Integration with octonions:
- Gates modulate octonion components before composition
- Each imaginary unit i₁...i₇ gets reliability-weighted contribution
"""

import logging
from typing import Any, cast

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class GMUGate(nn.Module):
    """Single GMU gate for one modality.

    Computes reliability gate from modality embedding:
        g = σ(W·x + b)

    Output is element-wise multiplier in [0, 1].
    """

    def __init__(self, input_dim: int, hidden_dim: int = 64) -> None:
        super().__init__()
        self.gate_net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim), nn.Tanh(), nn.Linear(hidden_dim, 1), nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Compute gate from input.

        Args:
            x: [B, input_dim] modality embedding

        Returns:
            gate: [B, 1] scalar in [0, 1]
        """
        return cast(torch.Tensor, self.gate_net(x))


class GatedMultimodalUnit(nn.Module):
    """GMU: Reliability-aware gating for multimodal fusion.

    Architecture:
    1. Per-modality gates: g_i = σ(f_i(x_i))
    2. Gated embeddings: h_i = g_i ⊙ x_i
    3. Fusion: h = Σ_i h_i (or learned combination)

    For octonion integration:
    - Gates modulate before projection to S⁷
    - Preserves geometric structure (gated octonion still on S⁷)
    """

    def __init__(
        self,
        modality_dims: dict[str, int],
        hidden_dim: int = 64,
        fusion_mode: str = "sum",
        device: str = "cpu",
    ) -> None:
        super().__init__()
        self.modality_names = list(modality_dims.keys())
        self.fusion_mode = fusion_mode
        self.device = device
        self.gates = nn.ModuleDict(
            {name: GMUGate(dim, hidden_dim).to(device) for name, dim in modality_dims.items()}
        )
        if fusion_mode == "weighted":
            self.fusion_weights = nn.Parameter(torch.ones(len(modality_dims)) / len(modality_dims))
        logger.info(f"✅ GMU initialized: {len(modality_dims)} modalities, mode={fusion_mode}")

    def forward(self, modality_inputs: dict[str, torch.Tensor | None]) -> dict[str, torch.Tensor]:
        """Apply GMU gating to modalities.

        Args:
            modality_inputs: Dict mapping modality name to [B, dim] tensor
                             None values are treated as missing

        Returns:
            Dict with:
              - gated_inputs: Dict of gated modalities
              - gates: Dict of gate values (for inspection)
              - fusion: Fused representation (if applicable)
        """
        gated_inputs: dict[str, Any] = {}
        gate_values = {}
        for name in self.modality_names:
            emb = modality_inputs.get(name)
            if emb is None:
                batch_size = next(
                    (v.shape[0] for v in modality_inputs.values() if v is not None), 1
                )
                gate_values[name] = torch.zeros(batch_size, 1, device=self.device)
                gated_inputs[name] = None
                continue
            gate = self.gates[name](emb)
            gate_values[name] = gate
            gated = emb * gate
            gated_inputs[name] = gated
        fusion = None
        if self.fusion_mode != "none":
            available = [v for v in gated_inputs.values() if v is not None]
            if available:
                if self.fusion_mode == "sum":
                    fusion = torch.stack(available, dim=0).sum(dim=0)
                elif self.fusion_mode == "concat":
                    fusion = torch.cat(available, dim=-1)
                elif self.fusion_mode == "weighted":
                    weights = F.softmax(self.fusion_weights, dim=0)
                    fusion = torch.zeros_like(available[0])
                    for i, emb in enumerate(available):
                        if i < len(weights):
                            fusion = fusion + weights[i] * emb
        return {"gated_inputs": gated_inputs, "gates": gate_values, "fusion": fusion}  # type: ignore[dict-item]

    def get_gate_statistics(
        self, modality_inputs: dict[str, torch.Tensor | None]
    ) -> dict[str, float]:
        """Compute gate statistics for monitoring.

        Returns:
            Dict with mean gate value per modality
        """
        with torch.no_grad():
            stats = {}
            for name in self.modality_names:
                emb = modality_inputs.get(name)
                if emb is not None:
                    gate = self.gates[name](emb)
                    stats[f"{name}_gate_mean"] = gate.mean().item()
                    stats[f"{name}_gate_std"] = gate.std().item()
                else:
                    stats[f"{name}_gate_mean"] = 0.0
                    stats[f"{name}_gate_std"] = 0.0
            return stats
