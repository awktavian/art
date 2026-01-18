from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import torch

from kagami.core.embodiment.control.mpc_controller import create_mpc_controller
from kagami.core.embodiment.control.trust_region import get_trust_region
from kagami.core.embodiment.motor_decoder import DISCRETE_ACTIONS
from kagami.core.embodiment.predictive_coding import create_predictive_coding_operators
from kagami.core.embodiment.sensorimotor_world_model import SensorimotorWorldModel
from kagami.core.reasoning.grounded_reasoner import create_grounded_reasoner
from kagami.core.world_model.kagami_world_model import (
    KagamiWorldModel as create_matryoshka_v2,
)


@dataclass
class UnifiedLoopConfig:
    # EXCEPTIONAL HIERARCHY DIMENSIONS from centralized config
    # Aligned to G₂ ⊂ F₄ ⊂ E₆ ⊂ E₇ ⊂ E₈
    dimensions: Sequence[int] | None = None  # Set in __post_init__
    device: str = "cpu"
    horizon: int = 5
    enable_mpc: bool = True
    enable_grounding: bool = True
    enable_trust_region: bool = True

    def __post_init__(self) -> None:
        """Initialize dimensions from centralized config if not set[Any]."""
        if self.dimensions is None:
            from kagami_math.dimensions import get_exceptional_dimensions_without_bulk

            object.__setattr__(self, "dimensions", get_exceptional_dimensions_without_bulk())


class UnifiedLoop:
    """Convenience wrapper bundling the core embodied reasoning components."""

    def __init__(  # type: ignore[no-untyped-def]
        self,
        *,
        sensorimotor,
        predictive_coding,
        mpc=None,
        reasoner=None,
        trust_region=None,
        device: str = "cpu",
    ) -> None:
        self.sensorimotor = sensorimotor
        self.predictive_coding = predictive_coding
        self.mpc = mpc
        self.reasoner = reasoner
        self.trust_region = trust_region
        self.device = device
        self.receipts: list[dict[str, Any]] = []

    @torch.no_grad()
    def tick(self, observations: Mapping[str, Any], task: str | None = None) -> dict[str, Any]:
        """Run a full perception → action cycle.

        Args:
            observations: Dictionary with optional keys `vision_emb`, `language_emb`,
                and `video_frames`.
            task: Optional description of the current task.
        """
        vision_emb = observations.get("vision_emb")
        language_emb = observations.get("language_emb")
        video_frames = observations.get("video_frames")

        if vision_emb is not None and not isinstance(vision_emb, torch.Tensor):
            vision_emb = torch.tensor(vision_emb, device=self.device, dtype=torch.float32)
        if language_emb is not None and not isinstance(language_emb, torch.Tensor):
            language_emb = torch.tensor(language_emb, device=self.device, dtype=torch.float32)
        if video_frames is not None and not isinstance(video_frames, torch.Tensor):
            video_frames = torch.tensor(video_frames, device=self.device, dtype=torch.float32)

        prediction = self.sensorimotor.predict(
            vision_emb=vision_emb,
            language_emb=language_emb,
            video_frames=video_frames,
        )

        discrete = self.sensorimotor.decoder.decode_discrete_action(
            prediction["discrete_actions"],
            prediction.get("discrete_action_labels") or DISCRETE_ACTIONS,
        )

        latent_state = torch.cat(
            [prediction["predicted_z"], prediction["predicted_o"]], dim=-1
        ).detach()

        receipt = {
            "correlation_id": str(uuid.uuid4()),
            "status": "accepted",
            "task": task,
            "action": discrete["action"],
            "confidence": float(discrete["confidence"]),
        }
        self.receipts.append(receipt)

        return {
            "action": discrete["action"],
            "action_confidence": float(discrete["confidence"]),
            "latent_state": latent_state.cpu(),
            "receipt": receipt,
        }


def create_unified_loop(  # type: ignore[no-untyped-def]
    dimensions: Sequence[int] | None = None,
    *,
    device: str = "cpu",
    horizon: int = 5,
    enable_mpc: bool = True,
    enable_grounding: bool = True,
    enable_trust_region: bool = True,
    **_,
) -> UnifiedLoop:
    """High-level factory used by integration tests."""

    # Use exceptional hierarchy dimensions from centralized config by default
    if dimensions is None:
        from kagami_math.dimensions import get_exceptional_dimensions_without_bulk

        dims = list(get_exceptional_dimensions_without_bulk())
    else:
        dims = list(dimensions)

    sensorimotor = SensorimotorWorldModel(
        matryoshka_dims=dims,
        device=device,
        compile_model=False,
        enable_rssm=False,
        training_bypass=True,
    )
    predictive_coding = create_predictive_coding_operators(device=device)

    mpc = None
    if enable_mpc:
        # Use factory to create model, handling legacy kwargs if needed
        try:
            brain = create_matryoshka_v2(dimensions=dims, device=device)  # type: ignore[call-arg]
        except TypeError:
            # OptimizedWorldModel init might differ from factory or legacy wrapper
            brain = create_matryoshka_v2(dimensions=dims)  # type: ignore[call-arg]
            # Brain is nn.Module, so move to device
            brain.to(device)

        mpc = create_mpc_controller(brain, horizon=horizon, num_samples=16, device=device)

    reasoner = create_grounded_reasoner(device=device) if enable_grounding else None
    trust_region = get_trust_region() if enable_trust_region else None

    return UnifiedLoop(
        sensorimotor=sensorimotor,
        predictive_coding=predictive_coding,
        mpc=mpc,
        reasoner=reasoner,
        trust_region=trust_region,
        device=device,
    )


__all__ = ["UnifiedLoop", "UnifiedLoopConfig", "create_unified_loop"]
