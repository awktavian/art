"""Colony RSSM - Unified Entry Point.

Provides OrganismRSSM: a 7-colony recurrent state space model with
Fano plane attention and Hofstadter strange loops.

Components:
- rssm_components.py: Core components and utilities
- rssm_core.py: Main OrganismRSSM class
"""

from __future__ import annotations

from kagami.core.config.unified_config import HofstadterLoopConfig

# Import all public components from split modules
from kagami.core.config.unified_config import RSSMConfig as ColonyRSSMConfig

from .rssm_components import (
    HofstadterStrangeLoop,
    SparseFanoAttention,
    get_fano_plane_connectivity,
    validate_colony_connectivity,
    # NOTE: BatchedOrganismCore and GodelAgent removed from exports (Dec 27, 2025).
    # These were created but never used in production code paths.
    # For tests that need direct access, import from rssm_components:
    #   from kagami.core.world_model.rssm_components import BatchedOrganismCore, GodelAgent
)
from .rssm_core import OrganismRSSM, create_rssm_world_model, get_organism_rssm, reset_organism_rssm
from .rssm_state import ColonyState, create_colony_states

# Main exports
__all__ = [
    "ColonyRSSMConfig",
    "ColonyState",
    "HofstadterLoopConfig",
    "HofstadterStrangeLoop",
    # Core classes
    "OrganismRSSM",
    # Component classes
    "SparseFanoAttention",
    "create_colony_states",
    "create_rssm_world_model",
    # Utility functions
    "get_fano_plane_connectivity",
    # Factory functions
    "get_organism_rssm",
    "reset_organism_rssm",
    "validate_colony_connectivity",
]

# Version information
__version__ = "2.0.0"  # Bumped due to major refactoring
__description__ = "Colony Recurrent State Space Model with Fano plane attention"
