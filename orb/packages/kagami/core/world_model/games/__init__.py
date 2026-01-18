"""Game World Model Module (Consolidated).

MIGRATED: January 5, 2026
From: packages/kagami_games/kagami_games/world_model/
To: packages/kagami/core/world_model/games/

Integrates Kagami's OrganismRSSM for game dynamics prediction,
enabling imagination-based planning and sample-efficient learning.

Key Components:
- GameWorldModel: RSSM wrapper for game frame sequences
- GameFrameEncoder: CNN encoder for game observations
- ImaginationPlanner: MCTS-style planning on latent space
"""

from .frame_encoder import GameFrameDecoder, GameFrameEncoder
from .game_world_model import (
    GameWorldModel,
    GameWorldModelConfig,
    GameWorldModelState,
)
from .imagination import (
    ImaginationPlanner,
    MCTSNode,
    PlanningConfig,
    SimpleImagination,
)

__all__ = [
    "GameFrameDecoder",
    "GameFrameEncoder",
    "GameWorldModel",
    "GameWorldModelConfig",
    "GameWorldModelState",
    "ImaginationPlanner",
    "MCTSNode",
    "PlanningConfig",
    "SimpleImagination",
]
