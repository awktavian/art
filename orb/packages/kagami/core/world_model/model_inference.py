"""KagamiWorldModel inference module (Dec 27, 2025).

Provides inference methods for KagamiWorldModel:
- forward(): Main forward pass with S7 extraction
- _compute_h_jepa_predictions(): Multi-horizon E8 predictions

RESTORED (Dec 27, 2025):
========================
During refactoring, these methods were accidentally left empty.
Restored from git history to fix forward pass.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class InferenceMixin:
    """Inference methods: forward(), H-JEPA predictions.

    This mixin expects the class to have:
    - unified_hourglass: SemanticResidualE8
    - organism_rssm: OrganismRSSM
    - h_jepa_predictor, h_jepa_target: H-JEPA networks
    - fano_attention: Optional Fano attention module
    - _sequence_ib: SequenceInformationBottleneck
    - _project_to_bulk_dim(): Project input to bulk dimension
    - _extract_s7_at_all_levels(): Extract S7 phase at all levels
    - s7_to_fano, fano_to_s7: Projection layers
    - config.use_amp: Whether to use GPU AMP autocast
    - _amp_dtype: Cached torch dtype for AMP (float16 or bfloat16)
    """

    # Declare attributes that will be provided by the main class
    unified_hourglass: Any
    organism_rssm: Any
    h_jepa_predictor: Any
    h_jepa_target: Any
    h_jepa_ema_tau: float
    fano_attention: Any
    _sequence_ib: Any
    s7_to_fano: Any
    fano_to_s7: Any
    training: bool
    config: Any
    _amp_dtype: Any

    def forward(
        self, x: torch.Tensor, *, action: torch.Tensor | None = None, **_: Any
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Forward pass with S7 extraction at all hierarchy levels.

        Supports GPU AMP autocast when config.use_amp=True. The forward pass
        is wrapped with torch.amp.autocast for mixed precision training.

        Args:
            x: [B, D] or [B, S, D] input tensor
            action: optional action tensor (accepted for compatibility)

        Returns:
            (reconstructed, metrics)
        """
        # GPU AMP autocast for mixed precision training (Jan 4, 2026)
        # FIX (Jan 4, 2026): Detect device type dynamically for TPU/GPU compatibility
        use_amp = getattr(self.config, "use_amp", False)
        if use_amp and self.training and self._amp_dtype is not None:
            # Get device type from input tensor for correct autocast context
            device_type = x.device.type
            # XLA (TPU) uses "xla" device type but torch.amp.autocast only supports "cuda"/"cpu"
            # For TPU, XLA handles mixed precision natively, so skip autocast
            if device_type == "cuda":
                with torch.amp.autocast(device_type="cuda", dtype=self._amp_dtype):
                    return self._forward_impl(x, action=action)
            else:
                # For TPU (xla), MPS, or CPU - no autocast wrapper needed
                # TPU uses bfloat16 natively via model dtype conversion in model_core.py
                return self._forward_impl(x, action=action)
        else:
            return self._forward_impl(x, action=action)

    def _forward_impl(
        self, x: torch.Tensor, *, action: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, dict[str, Any]]:
        """Internal forward implementation (called by forward with optional AMP wrapping).

        Args:
            x: [B, D] or [B, S, D] input tensor
            action: optional action tensor (accepted for compatibility)

        Returns:
            (reconstructed, metrics)
        """
        from kagami.core.world_model.model_config import CoreState

        if x.dim() == 2:
            x_in = x.unsqueeze(1)
            squeeze_seq = True
        else:
            x_in = x
            squeeze_seq = False

        # Project to bulk_dim if input dimension doesn't match
        x_in = self._project_to_bulk_dim(x_in)  # type: ignore[attr-defined]

        # Hourglass reconstruction + encoder states
        hg = self.unified_hourglass(x_in, return_all=True)
        reconstructed = hg["reconstructed"] if isinstance(hg, dict) else torch.tensor([])
        enc = hg.get("encoder_states", {}) if isinstance(hg, dict) else {}

        # NaN/Inf stability check
        if not torch.isfinite(reconstructed).all():
            logger.warning(
                "NaN/Inf detected in forward pass reconstruction. "
                "Input finite: %s, Reconstruction finite: %s",
                torch.isfinite(x_in).all().item(),
                torch.isfinite(reconstructed).all().item(),
            )
            reconstructed = torch.where(
                torch.isfinite(reconstructed), reconstructed, torch.zeros_like(reconstructed)
            )

        # Build CoreState from encoder intermediates
        e8_code = enc.get("e8_quantized")
        s7_phase = enc.get("s7")
        shell_residual = enc.get("g2")

        # E8 index for geometric loss weighting
        e8_index = None
        if s7_phase is not None:
            e8_index = torch.full(
                s7_phase.shape[:-1],
                112,
                device=s7_phase.device,
                dtype=torch.long,
            )

        core_state = CoreState(
            e8_code=e8_code,
            s7_phase=s7_phase,
            shell_residual=shell_residual,
            e8_index=e8_index,
            lattice_stress=0.0,
            timestamp=time.time(),
        )

        # Fano coherence proxy (bounded [0, 1])
        fano_coherence = None
        if s7_phase is not None:
            fano_coherence = s7_phase.abs().mean(dim=-1).clamp(0.0, 1.0)

        metrics: dict[str, Any] = {
            "core_state": core_state,
            "encoder_states": enc,
            "num_levels": hg.get("num_levels"),
            "bits_used": hg.get("bits_used"),
            "fano_coherence": fano_coherence,
        }

        # S7 at all levels + strange loop
        s7_metrics = self._extract_s7_at_all_levels(enc, core_state)  # type: ignore[attr-defined]
        metrics.update(s7_metrics)

        # Fano attention for cross-colony communication
        if self.fano_attention is not None and core_state.s7_phase is not None:
            s7_phase = core_state.s7_phase
            B, S, _D = s7_phase.shape

            s7_flat = s7_phase.reshape(B * S, 7)
            s7_proj = self.s7_to_fano(s7_flat)

            s7_input = s7_proj.unsqueeze(1).expand(B * S, 7, 32)
            s7_attended = self.fano_attention(s7_input)
            s7_attended = s7_attended.mean(dim=1)
            s7_attended = self.fano_to_s7(s7_attended)
            s7_attended = s7_attended.reshape(B, S, 7)

            core_state.s7_phase = s7_attended
            metrics["fano_attention_applied"] = True

        # Organism RSSM dynamics
        if core_state.e8_code is not None and core_state.s7_phase is not None:
            e8_for_rssm = core_state.e8_code
            s7_for_rssm = core_state.s7_phase
            try:
                rssm_out = self.organism_rssm(
                    e8_code=e8_for_rssm, s7_phase=s7_for_rssm, sample=self.training
                )
                # FIX (Dec 28, 2025): Use kl_balanced (with free_bits) - NO FALLBACK
                # kl_balanced has DreamerV3 free_bits applied, raw kl does not
                rssm_kl = rssm_out["kl_balanced"]
                if isinstance(rssm_kl, torch.Tensor) and rssm_kl.numel() > 1:
                    rssm_kl = rssm_kl.mean()
                metrics["rssm_kl_divergence"] = rssm_kl
                # Also log raw KL for diagnostics
                metrics["rssm_kl_raw"] = rssm_out["kl"].mean()
                metrics["rssm_organism_actions"] = rssm_out["organism_actions"]
                metrics["rssm_colony_actions"] = rssm_out["colony_actions"]
            except Exception as e:
                logger.debug("RSSM forward failed: %s", e)

        # H-JEPA multi-horizon prediction
        if e8_code is not None:
            h_jepa_metrics = self._compute_h_jepa_predictions(e8_code)
            metrics.update(h_jepa_metrics)

        # Sequence-IB on nucleus sequence
        nucleus_seq = enc.get("nucleus_sequence")
        if nucleus_seq is None:
            codes = enc.get("e8_indices")
            if isinstance(codes, list) and codes:
                try:
                    nucleus_seq = self.unified_hourglass.residual_e8.decode_sequence(codes)
                except Exception:
                    nucleus_seq = None

        if nucleus_seq is not None:
            try:
                seqib_out = self._sequence_ib(
                    nucleus_seq, num_levels=int(enc.get("num_levels") or 0) or None
                )
                metrics["seq_ib_reconstruction_loss"] = seqib_out.get("reconstruction_loss")
                metrics["seq_ib_kl_loss"] = seqib_out.get("kl_loss")
                metrics["z_latent"] = seqib_out.get("z")
            except Exception as e:
                logger.debug("Sequence-IB forward failed: %s", e)

        if action is not None:
            metrics["action_provided"] = True

        if squeeze_seq:
            reconstructed = reconstructed.squeeze(1)

        return reconstructed, metrics

    def _compute_h_jepa_predictions(
        self,
        e8_code: torch.Tensor,
    ) -> dict[str, Any]:
        """Compute H-JEPA multi-horizon predictions.

        Args:
            e8_code: [B, S, 8] E8 latent codes

        Returns:
            Dict with predictions at each horizon (horizon_1, horizon_2, horizon_4, horizon_8)
        """
        metrics: dict[str, Any] = {}

        if self.h_jepa_predictor is None or self.h_jepa_target is None:
            return metrics

        # H-JEPA predictor expects [B, 8] input, outputs [B, 32] = 4 horizons × 8D
        # If e8_code is [B, S, 8], we take the last timestep for prediction
        if e8_code.dim() == 3:
            e8_input = e8_code[:, -1, :]  # [B, 8]
        else:
            e8_input = e8_code  # [B, 8]

        # Multi-horizon keys matching test expectations
        horizon_steps = [1, 2, 4, 8]

        try:
            # Get predictions from predictor network: [B, 32] = 4 × 8D
            pred_output = self.h_jepa_predictor(e8_input)  # [B, 32]

            # Get targets from target network (with stop gradient)
            with torch.no_grad():
                target_output = self.h_jepa_target(e8_input)  # [B, 32]

            # Split into 4 horizons of 8D each
            B = pred_output.shape[0]
            pred_split = pred_output.view(B, 4, 8)  # [B, 4, 8]
            target_split = target_output.view(B, 4, 8)  # [B, 4, 8]

            # Build prediction dicts with proper horizon_* keys
            pred_dict = {}
            target_dict = {}
            for i, h in enumerate(horizon_steps):
                pred_dict[f"horizon_{h}"] = pred_split[:, i, :]  # [B, 8]
                target_dict[f"horizon_{h}"] = target_split[:, i, :]  # [B, 8]

            metrics["h_jepa_predictions"] = pred_dict
            metrics["h_jepa_target_predictions"] = target_dict

        except Exception as e:
            logger.debug("H-JEPA prediction failed: %s", e)

        return metrics

    def update_h_jepa_target(self, decay: float | None = None, *, tau: float | None = None) -> None:
        """Update H-JEPA target network with EMA.

        Args:
            decay: Optional EMA decay override. If None, uses self.h_jepa_ema_tau.
                   (Dec 30, 2025): Added to support curriculum-scheduled decay.
            tau: Alias for decay (for test compatibility). If provided, overrides decay.
        """
        if self.h_jepa_predictor is None or self.h_jepa_target is None:
            return

        # Use tau (alias) if provided, else decay, else default
        ema_tau = tau if tau is not None else (decay if decay is not None else self.h_jepa_ema_tau)

        with torch.no_grad():
            for pred_param, target_param in zip(
                self.h_jepa_predictor.parameters(),
                self.h_jepa_target.parameters(),
                strict=True,
            ):
                target_param.data.mul_(ema_tau).add_(pred_param.data, alpha=1.0 - ema_tau)
