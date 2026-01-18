"""KagamiWorldModel encoding module.

Extracted from model_core.py as part of the world model refactoring (Dec 27, 2025).
Contains all encoding-related methods for converting observations into CoreState.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import torch
import torch.nn as nn

from .model_config import CoreState

logger = logging.getLogger(__name__)


class EncoderMixin:
    """Mixin providing encoding functionality for KagamiWorldModel.

    This mixin contains all methods related to encoding observations into
    the world model's internal representation (CoreState). It handles:
    - Raw tensor encoding via encode()
    - Text/dict[str, Any] observation encoding via encode_observation()
    - Unified perception API via observe()
    - Input dimension projection

    Methods are designed to be mixed into KagamiWorldModel and access
    its attributes via self.
    """

    def _project_to_bulk_dim(self, x: torch.Tensor) -> torch.Tensor:
        """Project input tensor to bulk_dim if necessary.

        Handles variable observation dimensions by creating/using cached
        projection layers. If input already matches bulk_dim, returns as-is.

        Args:
            x: [B, D] or [B, S, D] input tensor

        Returns:
            [B, bulk_dim] or [B, S, bulk_dim] projected tensor
        """
        input_dim = x.shape[-1]
        target_dim = int(self.config.bulk_dim)  # type: ignore[attr-defined]

        # No projection needed if dimensions match
        if input_dim == target_dim:
            return x

        # Create projection layer if not cached
        if input_dim not in self._input_projections:  # type: ignore[attr-defined]
            proj = nn.Linear(input_dim, target_dim, bias=False)
            # Initialize with Xavier uniform
            nn.init.xavier_uniform_(proj.weight)
            # Move to same device as model
            proj = proj.to(next(self.parameters()).device)  # type: ignore[attr-defined]
            # Register as submodule for proper state_dict tracking
            self.add_module(f"_input_proj_{input_dim}", proj)  # type: ignore[attr-defined]
            self._input_projections[input_dim] = proj  # type: ignore[attr-defined]
            logger.debug(f"Created input projection: {input_dim}D → {target_dim}D")

        # Apply projection
        return self._input_projections[input_dim](x)  # type: ignore[attr-defined]

    def encode(self, x: torch.Tensor) -> tuple[CoreState, dict[str, Any]]:
        """Encode with S7 extraction at all levels."""

        if x.dim() == 2:
            x = x.unsqueeze(1)

        # Project to bulk_dim if input dimension doesn't match
        x = self._project_to_bulk_dim(x)

        enc_result = self.unified_hourglass.encode(x, return_all=True)  # type: ignore[attr-defined]
        enc = enc_result if isinstance(enc_result, dict) else {}
        e8_code = enc.get("e8_quantized")
        s7_phase = enc.get("s7")
        shell_residual = enc.get("g2")

        # E8 trajectory cache lookup (Dec 24, 2025)
        cache_hit = False
        if self._trajectory_cache is not None and e8_code is not None:  # type: ignore[attr-defined]
            try:
                cached_pred = self._trajectory_cache.lookup(e8_code)  # type: ignore[attr-defined]
                if cached_pred is not None:
                    cache_hit = True
                    # Use cached prediction for downstream if available
                    enc["cache_hit"] = True
                    enc["cached_prediction"] = cached_pred
            except Exception as e:
                logger.debug(f"Cache lookup failed: {e}")

        e8_index = None
        if s7_phase is not None:
            e8_index = torch.full(
                s7_phase.shape[:-1], 112, device=s7_phase.device, dtype=torch.long
            )

        core_state = CoreState(
            e8_code=e8_code,
            s7_phase=s7_phase,
            shell_residual=shell_residual,
            e8_index=e8_index,
            lattice_stress=0.0,
            timestamp=time.time(),
        )

        fano_coherence = None
        if s7_phase is not None:
            fano_coherence = s7_phase.abs().mean(dim=-1).clamp(0.0, 1.0)

        metrics: dict[str, Any] = {
            "encoder_states": enc,
            "fano_coherence": fano_coherence,
        }

        # Extract S7 at all levels
        s7_metrics = self._extract_s7_at_all_levels(enc, core_state)  # type: ignore[attr-defined]
        metrics.update(s7_metrics)

        # Store in trajectory cache if not a hit (Dec 24, 2025)
        if self._trajectory_cache is not None and e8_code is not None and not cache_hit:  # type: ignore[attr-defined]
            try:
                # Store E8 trajectory with metadata for future lookups
                self._trajectory_cache.store(  # type: ignore[attr-defined]
                    e8_codes=e8_code,
                    prediction=s7_phase if s7_phase is not None else e8_code,
                    metadata={
                        "fano_coherence": float(fano_coherence.mean().item())
                        if fano_coherence is not None
                        else 0.0,
                        "timestamp": core_state.timestamp,
                    },
                )
            except Exception as e:
                logger.debug(f"Cache store failed: {e}")

        metrics["cache_hit"] = cache_hit

        return core_state, metrics

    def encode_observation(
        self,
        observation: str | torch.Tensor,
        mask: torch.Tensor | None = None,
    ) -> CoreState:
        """Encode observation (text or tensor) into world model representation.

        This method provides a unified interface for encoding observations from
        different modalities. For text inputs, it uses hash-based deterministic
        embeddings (consistent with training_orchestrator).

        Args:
            observation: Raw observation (text string or tensor [B, ...] or [D])
            mask: Optional mask [B] for batch encoding

        Returns:
            CoreState with embedding attribute set[Any]
        """
        # Convert observation to tensor based on type
        if isinstance(observation, str):
            # Hash-based deterministic embedding (matches training_orchestrator)
            dim = self.config.bulk_dim  # type: ignore[attr-defined]
            seed = (hash(observation) & 0xFFFFFFFF) or 0
            g = torch.Generator(device="cpu")
            g.manual_seed(seed)
            # Create [1, 1, D] tensor (batch=1, seq=1, dim=D)
            obs_tensor = torch.randn(1, 1, dim, generator=g)
            obs_tensor = obs_tensor.to(next(self.parameters()).device)  # type: ignore[attr-defined]
        elif isinstance(observation, dict):
            # Dec 21, 2025: Handle dict[str, Any] observations by hashing their string repr
            # Used by unified_organism when querying for routing hints
            import json

            dim = self.config.bulk_dim

            obs_str = json.dumps(observation, sort_keys=True, default=str)
            seed = (hash(obs_str) & 0xFFFFFFFF) or 0
            g = torch.Generator(device="cpu")
            g.manual_seed(seed)
            obs_tensor = torch.randn(1, 1, dim, generator=g)
            obs_tensor = obs_tensor.to(next(self.parameters()).device)

        else:
            obs_tensor = observation
            # Ensure 3D shape [B, S, D]
            if obs_tensor.dim() == 1:
                obs_tensor = obs_tensor.unsqueeze(0).unsqueeze(0)  # [D] -> [1, 1, D]
            elif obs_tensor.dim() == 2:
                obs_tensor = obs_tensor.unsqueeze(1)  # [B, D] -> [B, 1, D]

        # Apply mask if provided
        if mask is not None:
            obs_tensor = obs_tensor * mask.unsqueeze(-1).unsqueeze(-1)

        # Encode using existing method
        core_state, _ = self.encode(obs_tensor)

        # Add embedding attribute for compatibility with joint LLM training
        # Concatenate all available state components into a flat embedding
        embedding_parts: list[torch.Tensor] = []

        if core_state.e8_code is not None:
            embedding_parts.append(core_state.e8_code.flatten(start_dim=1))
        if core_state.s7_phase is not None:
            embedding_parts.append(core_state.s7_phase.flatten(start_dim=1))
        if core_state.shell_residual is not None:
            embedding_parts.append(core_state.shell_residual.flatten(start_dim=1))

        if embedding_parts:
            core_state.embedding = torch.cat(embedding_parts, dim=-1)
        else:
            # Fallback: create zero embedding
            device = next(self.parameters()).device  # type: ignore[attr-defined]
            core_state.embedding = torch.zeros(1, self.config.bulk_dim, device=device)  # type: ignore[attr-defined]

        return core_state

    async def observe(
        self,
        perception_state: torch.Tensor | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[CoreState, dict[str, Any]]:
        """Unified observation API: Perception → World Model → CoreState.

        This method provides the bridge between the perception module and
        the world model encoding, implementing the LeCun architecture flow:

            Observation → Perception → World Model → Routing

        From CLAUDE.md: "I observe" - This is the unified observation interface.

        Args:
            perception_state: [B, state_dim] output from PerceptionModule.perceive()
                             If None, uses hash-based encoding of context
            context: Additional context dict[str, Any] (used if perception_state is None)

        Returns:
            Tuple of (CoreState, metrics_dict) where CoreState contains:
            - e8_code: E8 lattice coordinates (8D)
            - s7_phase: Colony routing signal (7D)
            - shell_residual: G2 representation
            - mu_self: Strange loop fixed point
        """
        import torch as th

        # Handle perception state or context
        if perception_state is not None:
            # Direct perception input
            x = perception_state
        elif context is not None:
            # Hash-based encoding of context (fallback)
            import json

            context_str = json.dumps(context, sort_keys=True, default=str)
            core_state = self.encode_observation(context_str)
            return core_state, {"observation_type": "context_hash"}
        else:
            # Empty observation - return default state
            device = next(self.parameters()).device  # type: ignore[attr-defined]
            x = th.zeros(1, 1, self.config.bulk_dim, device=device)  # type: ignore[attr-defined]

        # Encode perception state through world model
        core_state, metrics = self.encode(x)

        # Add observation metadata
        metrics["observation_type"] = "perception" if perception_state is not None else "empty"
        metrics["observed_at"] = time.time()

        # Track strange loop convergence
        if core_state.mu_self is not None:
            metrics["mu_self_norm"] = float(core_state.mu_self.norm().item())

        return core_state, metrics
