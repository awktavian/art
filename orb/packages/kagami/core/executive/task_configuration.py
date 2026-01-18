"""Task Configuration - Structured configuration for all modules.

LeCun: "The configurator primes the perception system to extract the relevant
information from the percept for the task at hand."

Each configuration dataclass specifies how to modulate a specific module.
These are OUTPUT by the ConfiguratorModule and INPUT to each target module.

Created: December 6, 2025
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch


@dataclass
class PerceptionConfig:
    """Configuration for the perception module.

    Controls what aspects of the input to attend to.

    LeCun: "For tasks that require a rapid detection of simple motifs, the
    configurator may modulate the weights of low-level layers."
    """

    # Extra tokens to inject into perception transformer
    attention_tokens: torch.Tensor | None = None  # [N_tokens, D]

    # Spatial attention mask (where to look)
    spatial_attention: torch.Tensor | None = None  # [H, W] or None for full

    # Feature extraction mode
    mode: str = "standard"  # "fine", "coarse", "object", "standard"

    # Modality weights (which senses to prioritize)
    modality_weights: dict[str, float] = field(
        default_factory=lambda: {
            "vision": 1.0,
            "audio": 1.0,
            "language": 1.0,
            "proprioception": 1.0,
        }
    )

    # Temporal context (how many past frames to consider)
    temporal_context: int = 8


@dataclass
class WorldModelConfig:
    """Configuration for the world model.

    Controls prediction horizon, abstraction level, and uncertainty handling.

    LeCun: "What aspects of the world state is relevant depends on the task
    at hand. The configurator configures the world model to handle the
    situation at hand."
    """

    # Prediction horizon (how far ahead to predict)
    horizon: int = 10  # Number of steps

    # Abstraction level (which E8 levels to use)
    # 0 = most detailed (all levels), higher = more abstract
    abstraction_level: int = 0

    # Number of E8 residual levels for this task
    e8_levels: int = 4  # 1-16

    # Uncertainty mode
    uncertainty_mode: str = "stochastic"  # "deterministic", "stochastic", "ensemble"

    # Latent variable configuration
    latent_samples: int = 1  # Number of latent samples for prediction

    # Extra transformer tokens for world model
    predictor_tokens: torch.Tensor | None = None


@dataclass
class CostConfig:
    """Configuration for the cost module.

    Controls the weighting of intrinsic costs and trainable critic.

    LeCun: "A simple way to make the cost configurable is by modulating the
    weights of a linear combination of elementary cost sub-modules."
    """

    # Intrinsic Cost (IC) weights - IMMUTABLE drives
    ic_weights: dict[str, float] = field(
        default_factory=lambda: {
            "curiosity": 0.1,  # Exploration drive
            "empowerment": 0.1,  # Control maximization
            "homeostasis": 0.2,  # Stability maintenance
            "safety": 0.3,  # CBF constraint (HIGH - safety critical)
            "energy": 0.1,  # Energy conservation
            "social": 0.1,  # Social interaction
            "novelty": 0.1,  # Novelty seeking
        }
    )

    # Trainable Critic (TC) weights - LEARNED costs
    tc_weights: dict[str, float] = field(
        default_factory=lambda: {
            "task_progress": 0.4,  # Progress toward goal
            "subgoal": 0.3,  # Current subgoal achievement
            "efficiency": 0.2,  # Action efficiency
            "quality": 0.1,  # Output quality
        }
    )

    # Active subgoal (if any)
    subgoal: torch.Tensor | None = None
    subgoal_weight: float = 1.0

    # Discount factor for future costs
    discount: float = 0.99

    # Risk sensitivity (0 = risk neutral, >0 = risk averse)
    risk_sensitivity: float = 0.1


@dataclass
class ActorConfig:
    """Configuration for the actor module.

    Controls action selection mode and exploration.

    LeCun: "The actor may comprise two components: (1) a policy module that
    directly produces an action (Mode-1), and (2) the action optimizer for
    model-predictive control (Mode-2)."
    """

    # Action mode
    mode: str = "mode_2"  # "mode_1", "mode_2", "hierarchical"

    # Mode-1 (reactive) configuration
    policy_temperature: float = 1.0  # Softmax temperature
    use_compiled_skill: bool = False  # Use pre-compiled skill if available
    compiled_skill_id: str | None = None

    # Mode-2 (planning) configuration
    planning_horizon: int = 10
    planning_iterations: int = 5
    mpc_samples: int = 100

    # Hierarchical configuration
    hierarchy_levels: int = 2  # Number of abstraction levels
    high_level_horizon: int = 50
    low_level_horizon: int = 10

    # Exploration
    exploration_rate: float = 0.1  # ε for ε-greedy
    exploration_noise: float = 0.1  # Noise scale for continuous

    # Action constraints
    max_action_norm: float = 1.0
    action_smoothing: float = 0.1  # Temporal smoothing


@dataclass
class TaskConfiguration:
    """Complete configuration for all modules.

    This is the OUTPUT of the ConfiguratorModule.
    Each component module receives its relevant config.
    """

    # Task identification
    task_id: str = ""
    task_type: str = "general"  # "planning", "reactive", "exploration", etc.

    # Per-module configurations
    perception: PerceptionConfig = field(default_factory=PerceptionConfig)
    world_model: WorldModelConfig = field(default_factory=WorldModelConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    actor: ActorConfig = field(default_factory=ActorConfig)

    # Global settings
    urgency: float = 0.5  # 0 = relaxed, 1 = urgent (affects all modules)
    precision_mode: bool = False  # High precision vs fast approximate

    # Metadata
    timestamp: float = 0.0
    source: str = "configurator"  # Where this config came from

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "perception": {
                "mode": self.perception.mode,
                "temporal_context": self.perception.temporal_context,
                "modality_weights": self.perception.modality_weights,
            },
            "world_model": {
                "horizon": self.world_model.horizon,
                "abstraction_level": self.world_model.abstraction_level,
                "e8_levels": self.world_model.e8_levels,
                "uncertainty_mode": self.world_model.uncertainty_mode,
            },
            "cost": {
                "ic_weights": self.cost.ic_weights,
                "tc_weights": self.cost.tc_weights,
                "discount": self.cost.discount,
            },
            "actor": {
                "mode": self.actor.mode,
                "exploration_rate": self.actor.exploration_rate,
                "planning_horizon": self.actor.planning_horizon,
            },
            "urgency": self.urgency,
            "precision_mode": self.precision_mode,
        }

    @classmethod
    def for_exploration(cls) -> TaskConfiguration:
        """Create configuration optimized for exploration."""
        config = cls(task_type="exploration")
        config.cost.ic_weights["curiosity"] = 0.4
        config.cost.ic_weights["novelty"] = 0.3
        config.actor.exploration_rate = 0.3
        config.actor.mode = "mode_2"  # Need planning for exploration
        config.world_model.latent_samples = 3  # Sample multiple futures
        return config

    @classmethod
    def for_exploitation(cls) -> TaskConfiguration:
        """Create configuration optimized for exploitation."""
        config = cls(task_type="exploitation")
        config.cost.tc_weights["task_progress"] = 0.6
        config.actor.exploration_rate = 0.05
        config.actor.mode = "mode_1"  # Fast reactive
        config.actor.use_compiled_skill = True
        return config

    @classmethod
    def for_safety_critical(cls) -> TaskConfiguration:
        """Create configuration for safety-critical tasks."""
        config = cls(task_type="safety_critical")
        config.cost.ic_weights["safety"] = 0.6
        config.cost.risk_sensitivity = 0.5
        config.actor.mode = "mode_2"  # Always plan
        config.actor.planning_iterations = 10
        config.world_model.uncertainty_mode = "ensemble"
        config.precision_mode = True
        return config

    @classmethod
    def for_hierarchical_planning(cls) -> TaskConfiguration:
        """Create configuration for hierarchical planning tasks."""
        config = cls(task_type="hierarchical")
        config.actor.mode = "hierarchical"
        config.actor.hierarchy_levels = 3
        config.world_model.horizon = 100
        config.world_model.abstraction_level = 2
        return config
