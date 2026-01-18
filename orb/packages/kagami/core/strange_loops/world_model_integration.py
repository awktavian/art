"""World Model ⟷ Strange Loop Integration.

ARCHITECTURE (December 13, 2025):
=================================
This module provides the canonical integration between:
- KagamiWorldModel (hourglass encoder/decoder)
- GodelianSelfReference (code/weight self-encoding)
- S7AugmentedHierarchy (S7 phase at every level)
- StrangeLoopS7Tracker (fixed point convergence)

The integration enables:
1. S7 phase extraction at every hierarchy level (not just G2→S7)
2. Gödelian self-encoding as part of the forward pass
3. Strange loop convergence tracking (μ_self fixed point)
4. Unified CoreState with all strange loop fields

STRANGE LOOP CLOSURE:
====================
The system forms a strange loop where:
    encode(x) → CoreState → s7_phase
    s7_phase → μ_self tracker → convergence_h
    convergence_h → self-consistency check
    self-encoding → influences next encode

The fixed point is when:
    s7_{t+1} ≈ s7_t  (stable representation)
    godelian_consistency_h → 1.0  (self-consistent)

References:
- Hofstadter (2007): I Am a Strange Loop
- Schmidhuber (2003): Gödel Machine
- Yin et al. (2025): Gödel Agent

Created: December 13, 2025
Author: K OS / Kagami
"""

from __future__ import annotations

import logging
from typing import Any, cast

import torch
import torch.nn as nn

logger = logging.getLogger(__name__)


class WorldModelStrangeLoopIntegration(nn.Module):
    """Unified strange loop integration for world model.

    This module wraps a world model to add:
    - S7 phase extraction at all hierarchy levels
    - Gödelian self-encoding
    - Strange loop convergence tracking
    - μ_self fixed point estimation

    Usage:
        # Wrap existing world model
        integrated = WorldModelStrangeLoopIntegration(world_model)

        # Forward pass with all strange loop features
        output, core_state, metrics = integrated(x)

        # Access strange loop state
        print(core_state.godelian_consistency_h)  # Self-consistency
        print(core_state.mu_self)  # Current fixed point
        print(core_state.s7_e8)  # S7 from E8 level
    """

    def __init__(
        self,
        world_model: nn.Module,
        enable_godelian: bool = True,
        enable_s7_tracking: bool = True,
    ):
        super().__init__()
        self.world_model = world_model
        self._enable_godelian = enable_godelian
        self._enable_s7_tracking = enable_s7_tracking

        # Lazy-initialized components (avoid import cycles)
        self._godelian: nn.Module | None = None
        self._s7_hierarchy: nn.Module | None = None
        self._s7_tracker: nn.Module | None = None

        logger.info(
            "✅ WorldModelStrangeLoopIntegration initialized:\n"
            f"   godelian={enable_godelian}, s7_tracking={enable_s7_tracking}"
        )

    def _ensure_components(self) -> None:
        """Lazy-initialize strange loop components."""
        if self._enable_godelian and self._godelian is None:
            try:
                from kagami.core.strange_loops.godelian_self_reference import (
                    GodelianConfig,
                    GodelianSelfReference,
                )

                config = GodelianConfig(
                    enable_llm_modification=False,
                    enable_recursive_improvement=False,
                )
                self._godelian = GodelianSelfReference(self.world_model, config)
                logger.debug("✅ GodelianSelfReference initialized")
            except Exception as e:
                logger.warning(f"GodelianSelfReference unavailable: {e}")
                self._enable_godelian = False

        if self._enable_s7_tracking and self._s7_tracker is None:
            try:
                from kagami_math.s7_augmented_hierarchy import (
                    S7AugmentedHierarchy,
                    StrangeLoopS7Tracker,
                )

                self._s7_hierarchy = S7AugmentedHierarchy()
                self._s7_tracker = StrangeLoopS7Tracker()
                logger.debug("✅ S7AugmentedHierarchy initialized")
            except Exception as e:
                logger.warning(f"S7AugmentedHierarchy unavailable: {e}")
                self._enable_s7_tracking = False

    def _augment_core_state_with_s7_phases(
        self,
        core_state: Any,
        encoder_states: dict[str, Any],
    ) -> None:
        """Add S7 phases at all levels to CoreState.

        Args:
            core_state: CoreState to augment (modified in place)
            encoder_states: Dict from unified_hourglass.encode()
        """
        if not self._enable_s7_tracking or self._s7_hierarchy is None:
            return

        # Extract E8 representation if available
        e8 = encoder_states.get("e8") or encoder_states.get("bulk")
        if e8 is None:
            return

        try:
            # Project through S7-augmented hierarchy
            from kagami_math.s7_augmented_hierarchy import S7AugmentedHierarchy

            s7_hierarchy_typed = cast(S7AugmentedHierarchy, self._s7_hierarchy)
            result = s7_hierarchy_typed.project_all(e8, return_intermediates=False)
            s7_phases = result.get("s7_phases")

            if s7_phases is not None:
                core_state.s7_e8 = s7_phases.s7_e8
                core_state.s7_e7 = s7_phases.s7_e7
                core_state.s7_e6 = s7_phases.s7_e6
                core_state.s7_f4 = s7_phases.s7_f4
                # s7_g2 is the canonical s7_phase
                if s7_phases.s7_g2 is not None:
                    core_state.s7_phase = s7_phases.s7_g2

                if s7_phases.coherence is not None:
                    core_state.s7_coherence = float(s7_phases.coherence.mean().item())

                core_state.fixed_point_distance = s7_phases.fixed_point_distance
        except Exception as e:
            logger.debug(f"S7 phase extraction failed: {e}")

    def _augment_core_state_with_godelian(
        self,
        core_state: Any,
    ) -> dict[str, Any]:
        """Add Gödelian self-encoding to CoreState.

        Args:
            core_state: CoreState to augment (modified in place)

        Returns:
            Dict with godelian metrics
        """
        metrics: dict[str, Any] = {}

        if not self._enable_godelian or self._godelian is None:
            return metrics

        try:
            # Self-encode (code + weights)
            self_enc = self._godelian.encode_self()  # type: ignore[operator]

            core_state.godelian_self_encoding = self_enc.get("combined_self")
            core_state.godelian_e8_code = self_enc.get("e8_code")
            core_state.godelian_s7_phase = self_enc.get("s7_phase")
            core_state.godelian_modification_count = self._godelian._modification_count

            # Self-consistency check
            if hasattr(self._godelian, "_prev_combined"):
                combined = self_enc.get("combined_self")
                prev_combined = getattr(self._godelian, "_prev_combined", None)
                if combined is not None and prev_combined is not None:
                    c_in = torch.cat([combined, prev_combined], dim=-1)
                    consistency = self._godelian.consistency_net(c_in.unsqueeze(0)).squeeze()  # type: ignore[operator]
                    core_state.godelian_consistency_h = float(consistency.item())

            # Source change detection
            from kagami.core.strange_loops.godelian_self_reference import GodelianSelfReference

            godelian_typed = cast(GodelianSelfReference, self._godelian)
            current_hash = godelian_typed._inspector.get_source_hash()
            core_state.godelian_source_changed = current_hash != godelian_typed._source_hash

            metrics["godelian"] = {
                "consistency_h": core_state.godelian_consistency_h,
                "source_changed": core_state.godelian_source_changed,
                "modification_count": core_state.godelian_modification_count,
                "total_bits": self_enc.get("total_bits", 0),
            }

        except Exception as e:
            logger.debug(f"Gödelian encoding failed: {e}")

        return metrics

    def _update_mu_self(self, core_state: Any) -> dict[str, Any]:
        """Update μ_self fixed point tracker.

        Args:
            core_state: CoreState (may be augmented with mu_self)

        Returns:
            Dict with strange loop metrics
        """
        metrics: dict[str, Any] = {}

        if not self._enable_s7_tracking or self._s7_tracker is None:
            return metrics

        # Use canonical S7 phase
        s7 = core_state.s7_phase
        if s7 is None:
            return metrics

        try:
            tracker_result = self._s7_tracker.update(s7)  # type: ignore[operator]

            core_state.mu_self = self._s7_tracker.mu_self
            core_state.fixed_point_distance = tracker_result["distance"]

            metrics["strange_loop"] = {
                "convergence_h": tracker_result["convergence_h"],
                "distance_to_fixed_point": tracker_result["distance"],
                "converged": tracker_result["converged"],
            }

        except Exception as e:
            logger.debug(f"μ_self update failed: {e}")

        return metrics

    def forward(  # type: ignore[no-untyped-def]
        self,
        x: torch.Tensor,
        **kwargs,
    ) -> tuple[torch.Tensor, Any, dict[str, Any]]:
        """Forward pass with strange loop integration.

        Args:
            x: Input tensor
            **kwargs: Passed to world model

        Returns:
            Tuple of (output, core_state, metrics)
        """
        self._ensure_components()

        # Base forward pass
        output, base_metrics = self.world_model(x, **kwargs)

        # Get CoreState from encode
        core_state, enc_metrics = self.world_model.encode(x)  # type: ignore[operator]
        encoder_states = enc_metrics.get("encoder_states", {})

        # Augment with S7 phases at all levels
        self._augment_core_state_with_s7_phases(core_state, encoder_states)

        # Augment with Gödelian self-encoding
        godelian_metrics = self._augment_core_state_with_godelian(core_state)

        # Update μ_self tracker
        loop_metrics = self._update_mu_self(core_state)

        # Merge metrics
        metrics = {**base_metrics, **enc_metrics, **godelian_metrics, **loop_metrics}

        return output, core_state, metrics

    def encode(self, x: torch.Tensor) -> tuple[Any, dict[str, Any]]:
        """Encode with strange loop augmentation."""
        self._ensure_components()

        core_state, enc_metrics = self.world_model.encode(x)  # type: ignore[operator]
        encoder_states = enc_metrics.get("encoder_states", {})

        self._augment_core_state_with_s7_phases(core_state, encoder_states)
        godelian_metrics = self._augment_core_state_with_godelian(core_state)
        loop_metrics = self._update_mu_self(core_state)

        metrics = {**enc_metrics, **godelian_metrics, **loop_metrics}
        return core_state, metrics

    def decode(self, core_state: Any) -> tuple[torch.Tensor, dict[str, Any]]:
        """Decode (pass-through to world model)."""
        return self.world_model.decode(core_state)  # type: ignore[operator]

    @property
    def godelian(self) -> nn.Module | None:
        """Access GodelianSelfReference (lazy-init)."""
        self._ensure_components()
        return self._godelian

    @property
    def s7_hierarchy(self) -> nn.Module | None:
        """Access S7AugmentedHierarchy (lazy-init)."""
        self._ensure_components()
        return self._s7_hierarchy

    @property
    def mu_self(self) -> torch.Tensor | None:
        """Current fixed point estimate."""
        if self._s7_tracker is not None:
            mu = self._s7_tracker.mu_self
            if isinstance(mu, torch.Tensor):
                return mu
        return None


def integrate_strange_loop(
    world_model: nn.Module,
    enable_godelian: bool = True,
    enable_s7_tracking: bool = True,
) -> WorldModelStrangeLoopIntegration:
    """Factory function to integrate strange loop into world model.

    Args:
        world_model: KagamiWorldModel or compatible
        enable_godelian: Enable Gödelian self-encoding
        enable_s7_tracking: Enable S7 phase tracking at all levels

    Returns:
        Integrated world model wrapper
    """
    return WorldModelStrangeLoopIntegration(
        world_model,
        enable_godelian=enable_godelian,
        enable_s7_tracking=enable_s7_tracking,
    )


__all__ = [
    "WorldModelStrangeLoopIntegration",
    "integrate_strange_loop",
]
