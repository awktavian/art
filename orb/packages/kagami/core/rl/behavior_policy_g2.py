from __future__ import annotations

"""BehaviorPolicyG2: Learned behavior policy on G2-constrained action space.

Produces small step actions parameterized by a 14D tangent vector (xi14)
intended to represent a step along the Lie algebra of G2. The actual world
model integrates actions as semantic hints; we encode the G2 step compactly in
the action dict[str, Any] and rely on PXO/JEPA to condition predictions accordingly.

Design goals:
- Fast K=1 action emission per decision (no candidate sampling loop)
- Safety gates: h(x) >= 0 via CBF context; temporal r-gate: dt >= 0
- Lightweight learning hook (no-op for now; compatible signature)

Interfaces with UnifiedRLLoop by exposing a similar method signature to Actor:
  sample_actions(state, k=1, exploration_noise=..., temperature=..., context=...)
and an update(trajectory, returns, advantages) stub to remain compatible with
training loops.
"""
import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class BehaviorPolicyG2:
    """G2-constrained behavior policy.

    Emits a single action per call, shaped by context and safety gates.
    """

    def __init__(
        self,
        *,
        init_std: float = 0.5,
        min_std: float = 0.1,
        entropy_coef: float = 0.01,
    ) -> None:
        self._rng = np.random.RandomState(42)
        self._std = float(init_std)
        self._min_std = float(min_std)
        self._entropy_coef = float(entropy_coef)

        # Lazy manifold load
        self._manifold = None
        try:
            from kagami.core.matryoshka_fiber_bundle import (
                get_matryoshka_bundle,
            )

            self._manifold = get_matryoshka_bundle()
        except Exception as e:  # pragma: no cover - optional dependency
            logger.debug(f"MatryoshkaFiberBundle unavailable: {e}")

        # Safety control barrier (unified WildGuard + OptimalCBF pipeline)
        # Dec 6, 2025: Using unified safety API
        self._cbf_available = False
        try:
            from kagami.core.safety.cbf_integration import check_cbf_sync

            self._check_cbf_sync = check_cbf_sync
            self._cbf_available = True
        except Exception as e:  # pragma: no cover - optional dependency
            logger.debug(f"CBF unavailable: {e}")

    async def sample_actions(
        self,
        state: Any,
        k: int = 1,
        exploration_noise: float = 0.2,
        temperature: float = 1.0,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Emit one G2 action (K=1 fast path).

        Args:
            state: Current world-model state (typically 384D embedding)
            k: Number of actions requested (ignored; returns 1 for speed)
            exploration_noise: Extra stochasticity added to xi14
            temperature: Not used (reserved)
            context: Additional fields for safety extraction and metadata
        """
        context = context or {}

        # Compute manifold radius r if possible (temporal gate)
        r_now = 0.0
        if self._manifold is not None and hasattr(state, "embedding"):
            try:
                emb = np.array(state.embedding, dtype=np.float32)
                z = self._manifold.embed_to_manifold(emb)  # type: ignore[arg-type]

                r_now = float(np.linalg.norm(z))
            except Exception:
                r_now = 0.0

        # Sample xi14 (Lie algebra step) with gaussian noise
        base_std = max(self._min_std, self._std)
        extra = float(max(0.0, exploration_noise))
        std = base_std * (1.0 + 0.5 * extra)
        xi14 = self._rng.randn(14).astype(np.float32) * std

        # Temporal increment (r-gate): ensure non-negative dt
        dt = float(max(0.05, 0.1 * (1.0 + extra)))

        # Safety gate via unified pipeline (WildGuard + OptimalCBF)
        if self._cbf_available:
            try:
                result = self._check_cbf_sync(
                    operation="g2_step",
                    action="sample_actions",
                    source="behavior_policy_g2",
                    content=str(context.get("content", "")),
                )
                h_value = result.h_x
                context["h_value"] = h_value
                if not result.safe or h_value < 0.0:  # type: ignore[operator]
                    # Reduce step and slow down when unsafe
                    xi14 *= 0.0  # freeze structural change
                    dt = 0.05
            except Exception:
                pass

        action = {
            "action": "g2_step",
            "g2_xi14": xi14.tolist(),
            "dt": dt,
            "r_now": r_now,
            "_policy": "BehaviorPolicyG2",
        }
        return [action]

    async def update(
        self,
        trajectory: list[Any],
        returns: list[float],
        advantages: list[float] | None = None,
    ) -> float:
        """Compatibility stub for training.

        A full Gaussian policy gradient update would require storing sampled
        actions/log-probs. For now, return 0.0 so learning loops remain stable.
        """
        # Optional entropy annealing heuristic
        try:
            if advantages is not None and len(advantages) > 0:
                mean_adv = float(np.mean(advantages))
                # Anneal std down when advantages positive (policy improving)
                if mean_adv > 0.0:
                    self._std = max(self._min_std, self._std * (1.0 - 0.01))
        except Exception:
            pass
        return 0.0


_policy_singleton: BehaviorPolicyG2 | None = None


def get_behavior_policy_g2() -> BehaviorPolicyG2:
    global _policy_singleton
    if _policy_singleton is None:
        _policy_singleton = BehaviorPolicyG2()
    return _policy_singleton


__all__ = ["BehaviorPolicyG2", "get_behavior_policy_g2"]
