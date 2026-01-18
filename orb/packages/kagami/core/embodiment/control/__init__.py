"""Embodiment Control Module.

MPC controller, trust region, and safety cost functions for embodied control.

Consolidated from kagami.core.control (December 2025).
"""

from kagami.core.embodiment.control.mpc_controller import (
    MPCController,
    create_mpc_controller,
)
from kagami.core.embodiment.control.safety_cost import SafetyCost  # type: ignore[attr-defined]
from kagami.core.embodiment.control.trust_region import (  # type: ignore[attr-defined]
    TrustRegion,
    get_trust_region,
)

__all__ = [
    "MPCController",
    "SafetyCost",
    "TrustRegion",
    "create_mpc_controller",
    "get_trust_region",
]
