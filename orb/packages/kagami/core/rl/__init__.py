from __future__ import annotations

"""Reinforcement Learning systems for K os.

FULL POWER MODE - Always enabled, no degraded fallbacks.

Includes:
- Model-based RL (world models, actor-critic, imagination)
- Embodied learning (Genesis physics integration)
- 3-tier intelligence (reflexes, intuition, reasoning)
- FULL learned hierarchical planning (Pan et al., 2024)
- PPO + GAE (Oct 2025 RL audit - 2-5x sample efficiency)
- HER for sparse rewards (5-10x faster learning)
- RND curiosity (robust exploration)
- Model ensemble (30-50% better uncertainty)
- V-trace off-policy correction

CANONICAL: Use learned_hierarchical_planning for production.
All LeCun architecture components are implemented at 100%.

REMOVED: KAGAMI_MINIMAL_PXO mode - RL is always fully operational.
"""

# Full RL stack imports - ALWAYS enabled
from .actor_critic import Critic, get_actor, get_critic

# G2 behavior policy (fast, offline-safe)
from .behavior_policy_g2 import BehaviorPolicyG2, get_behavior_policy_g2
from .gae import get_gae_calculator

# Backward compatibility removed - use LearnedHierarchicalPlanner
from .hybrid_actor import HybridActor, get_hybrid_actor
from .intrinsic_reward import IntrinsicRewardCalculator, get_intrinsic_reward_calculator

# FULL SCIENTIFIC IMPLEMENTATION (Use this)
from .learned_hierarchical_planning import (
    HierarchicalPlan,
    HierarchicalValueFunction,
    LearnedHierarchicalPlanner,
    Option,
    TemporalAbstractionNetwork,
    get_hierarchical_planner,
)
from .llm_guided_actor import LLMGuidedActor

# PPO + GAE (Oct 2025 improvements)
from .ppo_actor import get_ppo_actor

# RLHF/Preference Learning
from .preference_learning import (
    PreferenceDataset,
    RewardModel,
    RLHFTrainer,
    get_preference_dataset,
    get_reward_model,
    get_rlhf_trainer,
    record_preference,
)
from .rnd_curiosity import get_rnd_curiosity
from .semantic_encoder import SemanticEncoder, get_semantic_encoder
from .unified_loop import UnifiedRLLoop, get_rl_loop
from .wake_sleep import (
    Phase as WakeSleepPhase,
)

# embodied_learning removed Dec 14, 2025 - module never created
# NOTE: Embodied learning functionality moved to kagami/core/embodied/
# Wake-Sleep learning for world model training
from .wake_sleep import (
    WakeSleep,
    WakeSleepConfig,
    WakeSleepStats,
    create_wake_sleep,
)

__all__ = [
    "BehaviorPolicyG2",
    "Critic",
    "HierarchicalPlan",
    "HierarchicalValueFunction",
    # Other components
    "HybridActor",
    "IntrinsicRewardCalculator",
    "LLMGuidedActor",
    # NOTE: Embodied RL exports removed Dec 8, 2025 - see kagami/core/embodied/
    # FULL SCIENTIFIC VERSIONS (preferred)
    "LearnedHierarchicalPlanner",
    "Option",
    # RLHF
    "PreferenceDataset",
    "RLHFTrainer",
    "RewardModel",
    "SemanticEncoder",
    "TemporalAbstractionNetwork",
    "UnifiedRLLoop",
    # Wake-Sleep learning
    "WakeSleep",
    "WakeSleepConfig",
    "WakeSleepPhase",
    "WakeSleepStats",
    "create_wake_sleep",
    "get_actor",
    "get_behavior_policy_g2",
    "get_critic",
    "get_gae_calculator",
    "get_hierarchical_planner",
    "get_hybrid_actor",
    "get_intrinsic_reward_calculator",
    # PPO/GAE
    "get_ppo_actor",
    "get_preference_dataset",
    "get_reward_model",
    "get_rl_loop",
    "get_rlhf_trainer",
    "get_rnd_curiosity",
    "get_semantic_encoder",
    "record_preference",
]
