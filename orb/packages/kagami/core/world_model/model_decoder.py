"""KagamiWorldModel decoding module.

Extracted from model_core.py as part of the world model refactoring (Dec 27, 2025).
Contains all decoding-related methods for converting CoreState back to observations.
"""

from __future__ import annotations

from typing import Any

import torch

from .model_config import CoreState


class DecoderMixin:
    """Mixin providing decoding functionality for KagamiWorldModel.

    This mixin contains all methods related to decoding the world model's
    internal representation (CoreState) back into observation space. It handles:
    - CoreState to tensor reconstruction via decode()

    Methods are designed to be mixed into KagamiWorldModel and access
    its attributes via self.
    """

    def decode(self, core_state: CoreState) -> tuple[torch.Tensor, dict[str, Any]]:
        """Decode CoreState back to observation space.

        Args:
            core_state: World model internal state containing e8_code

        Returns:
            Tuple of (reconstructed_tensor, metrics_dict)

        Raises:
            ValueError: If core_state.e8_code is None
        """
        if core_state.e8_code is None:
            raise ValueError("CoreState.e8_code is required for decode")

        dec_result = self.unified_hourglass.decode(core_state.e8_code, return_all=True)  # type: ignore[attr-defined]
        if isinstance(dec_result, dict):
            dec = dec_result
            reconstructed = dec.get("bulk", torch.tensor([]))
        else:
            dec = {}
            reconstructed = dec_result if isinstance(dec_result, torch.Tensor) else torch.tensor([])
        return reconstructed, {"decoder_states": dec, "e8": dec.get("e8_vq")}
