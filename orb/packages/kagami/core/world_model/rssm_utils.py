"""RSSM Utility Functions.

CREATED: December 19, 2025
PURPOSE: Helper functions for OrganismRSSM integration with KagamiWorldModel.

ARCHITECTURAL CHANGE:
OrganismRSSM now accepts S7 phase [B, 7] directly instead of full observations [B, 15].
This eliminates the redundant obs_encoder (~100k parameters) and provides a single
source of truth for observation encoding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import torch

if TYPE_CHECKING:
    from kagami.core.world_model.model_core import CoreState


def encode_for_rssm(core_state: CoreState) -> torch.Tensor:
    """Extract S7 phase from CoreState for OrganismRSSM input.

    CRITICAL INTEGRATION POINT:
    This function is the bridge between KagamiWorldModel's CoreState and
    OrganismRSSM's input format. It extracts the S7 phase (7D unit imaginary
    octonions) which represents the 7 colony activities.

    ARCHITECTURAL RATIONALE:
    - S7 is the natural representation space for 7 colonies (Fano plane structure)
    - Eliminates dual encoding: world model → S7 → RSSM (not world model → E8+S7 → obs_encoder → RSSM)
    - Saves ~100k parameters by removing redundant obs_encoder
    - Single source of truth: KagamiWorldModel owns observation encoding

    Args:
        core_state: CoreState from KagamiWorldModel encode() or forward()

    Returns:
        S7 phase tensor [B, 7] suitable for OrganismRSSM._step()

    Raises:
        ValueError: If core_state.s7_phase is None or has invalid shape

    Example:
        ```python
        from kagami.core.world_model import KagamiWorldModelFactory
        from kagami.core.world_model.colony_rssm import OrganismRSSM
        from kagami.core.world_model.rssm_utils import encode_for_rssm

        world_model = KagamiWorldModelFactory.create()
        rssm = OrganismRSSM()

        # Encode raw input to CoreState
        x = torch.randn(4, 8, 512)  # [B, S, D]
        core_state = world_model.encode(x)

        # Extract S7 for RSSM
        s7 = encode_for_rssm(core_state)  # [B, 7]

        # Step RSSM
        result = rssm.step_all(s7_phase=s7)
        ```
    """
    if core_state.s7_phase is None:
        raise ValueError(
            "CoreState.s7_phase is None. Ensure KagamiWorldModel encode() or forward() "
            "was called before extracting S7 for RSSM."
        )

    s7 = core_state.s7_phase

    # Validate shape
    if s7.dim() < 2:
        raise ValueError(
            f"CoreState.s7_phase must be at least 2D [B, 7], got shape {s7.shape}. "
            "Check that world model properly encodes S7 phase."
        )

    # Handle sequence dimension [B, S, 7] → take last timestep [B, 7]
    if s7.dim() == 3:
        s7 = s7[:, -1]  # [B, S, 7] → [B, 7]

    # Validate final shape
    if s7.shape[-1] != 7:
        raise ValueError(
            f"CoreState.s7_phase last dimension must be 7 (S7 phase), got {s7.shape[-1]}. "
            f"Full shape: {s7.shape}"
        )

    return s7


def decode_from_rssm(s7_phase: torch.Tensor) -> CoreState:
    """Create CoreState from RSSM's predicted S7 phase.

    INVERSE OPERATION: Convert OrganismRSSM output back to CoreState format.
    Useful for reconstruction loss and world model alignment.

    Args:
        s7_phase: Predicted S7 phase [B, 7] from OrganismRSSM.predict_obs()

    Returns:
        CoreState with s7_phase populated

    Example:
        ```python
        from kagami.core.world_model.colony_rssm import OrganismRSSM
        from kagami.core.world_model.rssm_utils import decode_from_rssm

        rssm = OrganismRSSM()
        rssm.initialize_all(batch_size=4)

        # Step RSSM
        result = rssm.step_all(s7_phase=torch.randn(4, 7))

        # Get predicted S7
        h = result["h_next"][:, 0]  # [B, 7, H] → [B, H] (first colony)
        z = result["z_next"][:, 0]  # [B, 7, Z] → [B, Z]
        s7_pred = rssm.predict_obs(h, z)  # [B, 7]

        # Convert back to CoreState
        core_state = decode_from_rssm(s7_pred)
        ```
    """
    from kagami.core.world_model.model_core import CoreState

    # Validate input
    if s7_phase.dim() != 2:
        raise ValueError(
            f"s7_phase must be 2D [B, 7], got shape {s7_phase.shape}. "
            "RSSM.predict_obs() should output [B, 7] S7 phase."
        )

    if s7_phase.shape[-1] != 7:
        raise ValueError(
            f"s7_phase last dimension must be 7 (S7 phase), got {s7_phase.shape[-1]}. "
            f"Full shape: {s7_phase.shape}"
        )

    # Create minimal CoreState with S7 phase
    return CoreState(
        s7_phase=s7_phase.unsqueeze(1),  # [B, 7] → [B, 1, 7] (add sequence dim)
        e8_code=None,  # Not available from RSSM alone
        shell_residual=None,  # Not available from RSSM alone
    )


__all__ = [
    "decode_from_rssm",
    "encode_for_rssm",
]
