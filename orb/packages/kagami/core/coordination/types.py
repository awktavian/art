"""Shared types for consensus coordination.

CREATED: December 15, 2025
PURPOSE: Break circular dependency between kagami_consensus.py and consensus_safety.py

This module contains types used by both consensus protocol and safety verification.
"""

# Standard library imports
import time
from dataclasses import (
    dataclass,
    field,
)
from enum import Enum


class ColonyID(Enum):
    """Colony identifiers (0-6)."""

    SPARK = 0
    FORGE = 1
    FLOW = 2
    NEXUS = 3
    BEACON = 4
    GROVE = 5
    CRYSTAL = 6


# =============================================================================
# COORDINATION PROPOSALS
# =============================================================================


@dataclass
class CoordinationProposal:
    """A colony's proposed routing decision."""

    proposer: ColonyID
    target_colonies: list[ColonyID]
    task_decomposition: dict[ColonyID, str] = field(default_factory=dict)
    confidence: float = 0.8  # [0, 1]
    fano_justification: str = ""  # Which Fano lines justify this routing
    cbf_margin: float = 0.5  # Safety margin h(x)
    timestamp: float = field(default_factory=time.time)


__all__ = [
    "ColonyID",
    "CoordinationProposal",
]
