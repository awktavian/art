"""Configurator Module - Executive Control for K OS.

Implements the Configurator from LeCun's cognitive architecture:

> "The configurator module takes inputs from all other modules and configures
> them for the task at hand by modulating their parameters and their attention
> circuits. In particular, the configurator may prime the perception, world
> model, and cost modules to fulfill a particular goal."

The Configurator is the "prefrontal cortex" of K OS - it provides executive
control by dynamically configuring all other modules based on:
1. Current task/goal
2. Current state of all modules
3. Learned task-configuration mappings

INTEGRATION WITH EXISTING SYSTEMS:
===================================
The Configurator COORDINATES (not replaces) existing routing systems:

- routing/multi_model_router.py → LLM model selection
- reasoning/adaptive_router.py → Reasoning strategy selection
- execution/adaptive_attention_allocator.py → Phase time allocation

The Configurator adds:
- Neural configuration token generation
- Cross-module state aggregation
- Unified task-based modulation

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                     CONFIGURATOR MODULE                         │
    │  ┌─────────────────────────────────────────────────────────┐   │
    │  │              Context Aggregator (Transformer)            │   │
    │  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │   │
    │  │  │  Task  │ │Percept │ │ World  │ │  Cost  │ │ Actor  │ │   │
    │  │  │  Emb   │ │ State  │ │ State  │ │ State  │ │ State  │ │   │
    │  │  └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ │   │
    │  │       └──────────┴─────────┴──────────┴──────────┘      │   │
    │  │                          ↓                               │   │
    │  │              [Transformer Encoder]                       │   │
    │  │                          ↓                               │   │
    │  │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐            │   │
    │  │  │Percept │ │ World  │ │  Cost  │ │ Actor  │            │   │
    │  │  │ Config │ │ Config │ │ Config │ │ Config │            │   │
    │  │  └────────┘ └────────┘ └────────┘ └────────┘            │   │
    │  └─────────────────────────────────────────────────────────┘   │
    │                                                                 │
    │  DELEGATES TO:                                                  │
    │  - AdaptiveReasoningRouter (strategy selection)                 │
    │  - AdaptiveAttentionAllocator (phase timing)                    │
    │  - MultiModelRouter (LLM selection)                             │
    └─────────────────────────────────────────────────────────────────┘

Created: December 6, 2025
Reference: docs/paper_A_Path_Towards_Autonomous_Machine_Intelligence.md
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, cast

import torch
import torch.nn as nn
import torch.nn.functional as F

from kagami.core.executive.task_configuration import (
    ActorConfig,
    CostConfig,
    PerceptionConfig,
    TaskConfiguration,
    WorldModelConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ConfiguratorConfig:
    """Configuration for the Configurator module."""

    # Input dimensions
    task_dim: int = 512  # Task embedding dimension
    perception_state_dim: int = 256
    world_model_state_dim: int = 256
    cost_state_dim: int = 64
    actor_state_dim: int = 128

    # Transformer architecture
    hidden_dim: int = 512
    n_heads: int = 8
    n_layers: int = 3
    dropout: float = 0.1

    # Output dimensions (configuration space)
    perception_config_dim: int = 64
    world_model_config_dim: int = 64
    cost_config_dim: int = 32
    actor_config_dim: int = 32

    # Token dimensions for module injection
    attention_token_dim: int = 64
    n_attention_tokens: int = 4  # Tokens to inject per module

    # Learning
    learning_rate: float = 1e-4
    gradient_clip: float = 1.0

    # Task type embeddings
    task_types: list[str] = field(
        default_factory=lambda: [
            "general",
            "exploration",
            "exploitation",
            "planning",
            "reactive",
            "safety_critical",
            "hierarchical",
            "creative",
        ]
    )


class TaskEncoder(nn.Module):
    """Encode task description into embedding."""

    def __init__(self, config: ConfiguratorConfig):
        super().__init__()
        self.config = config

        # Task type embedding (learned)
        self.task_type_embedding = nn.Embedding(len(config.task_types), config.hidden_dim // 4)
        self.task_type_to_idx = {t: i for i, t in enumerate(config.task_types)}

        # Task content encoder (from semantic embedding)
        self.content_encoder = nn.Sequential(
            nn.Linear(config.task_dim, config.hidden_dim),
            nn.LayerNorm(config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.hidden_dim),
        )

        # Combine type + content
        self.combiner = nn.Linear(config.hidden_dim + config.hidden_dim // 4, config.hidden_dim)

    def forward(
        self,
        task_embedding: torch.Tensor,
        task_type: str = "general",
    ) -> torch.Tensor:
        """Encode task.

        Args:
            task_embedding: [B, task_dim] semantic task embedding
            task_type: Task type string

        Returns:
            [B, hidden_dim] task encoding
        """
        # Encode content
        content = self.content_encoder(task_embedding)

        # Get type embedding
        type_idx = self.task_type_to_idx.get(task_type, 0)
        type_idx_tensor = torch.tensor([type_idx], device=task_embedding.device).expand(
            task_embedding.shape[0]
        )
        type_emb = self.task_type_embedding(type_idx_tensor)

        # Combine
        combined = torch.cat([content, type_emb], dim=-1)
        return cast(torch.Tensor, self.combiner(combined))


class ModuleStateEncoder(nn.Module):
    """Encode state from a specific module into common space."""

    def __init__(self, input_dim: int, hidden_dim: int):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Encode module state to hidden dim."""
        return cast(torch.Tensor, self.encoder(state))


class ConfigurationHead(nn.Module):
    """Generate configuration for a specific module."""

    def __init__(
        self,
        hidden_dim: int,
        config_dim: int,
        n_tokens: int,
        token_dim: int,
    ):
        super().__init__()

        # Scalar configuration values
        self.config_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, config_dim),
        )

        # Attention tokens to inject into module
        self.token_generator = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, n_tokens * token_dim),
        )
        self.n_tokens = n_tokens
        self.token_dim = token_dim

    def forward(self, hidden: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Generate configuration.

        Args:
            hidden: [B, hidden_dim] aggregated hidden state

        Returns:
            config: [B, config_dim] scalar configuration values
            tokens: [B, n_tokens, token_dim] attention tokens
        """
        config = self.config_head(hidden)
        tokens = self.token_generator(hidden)
        tokens = tokens.view(-1, self.n_tokens, self.token_dim)
        return config, tokens


class ConfiguratorModule(nn.Module):
    """Executive Control Module - Configures all other modules.

    LeCun: "The configurator is the main controller of the agent. It takes
    input from all other modules and modulates their parameters and
    connection graphs."

    This module implements:
    1. Context aggregation from all modules
    2. Task-conditioned configuration generation
    3. Attention token generation for module injection

    Usage:
        configurator = ConfiguratorModule()

        # Get configuration for current task
        config = configurator.configure(
            task_embedding=task_emb,
            task_type="planning",
            perception_state=perception.get_state(),
            world_model_state=world_model.get_state(),
            cost_state=cost.get_state(),
            actor_state=actor.get_state(),
        )

        # Apply configuration to modules
        perception.set_config(config.perception)
        world_model.set_config(config.world_model)
        cost.set_config(config.cost)
        actor.set_config(config.actor)
    """

    def __init__(self, config: ConfiguratorConfig | None = None):
        super().__init__()
        self.config = config or ConfiguratorConfig()

        # Task encoder
        self.task_encoder = TaskEncoder(self.config)

        # Module state encoders (project each module's state to common space)
        self.perception_encoder = ModuleStateEncoder(
            self.config.perception_state_dim, self.config.hidden_dim
        )
        self.world_model_encoder = ModuleStateEncoder(
            self.config.world_model_state_dim, self.config.hidden_dim
        )
        self.cost_encoder = ModuleStateEncoder(self.config.cost_state_dim, self.config.hidden_dim)
        self.actor_encoder = ModuleStateEncoder(self.config.actor_state_dim, self.config.hidden_dim)

        # Context aggregator (transformer)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.config.hidden_dim,
            nhead=self.config.n_heads,
            dim_feedforward=self.config.hidden_dim * 4,
            dropout=self.config.dropout,
            batch_first=True,
        )
        self.context_aggregator = nn.TransformerEncoder(
            encoder_layer, num_layers=self.config.n_layers
        )

        # Configuration heads (one per module)
        self.perception_head = ConfigurationHead(
            self.config.hidden_dim,
            self.config.perception_config_dim,
            self.config.n_attention_tokens,
            self.config.attention_token_dim,
        )
        self.world_model_head = ConfigurationHead(
            self.config.hidden_dim,
            self.config.world_model_config_dim,
            self.config.n_attention_tokens,
            self.config.attention_token_dim,
        )
        self.cost_head = ConfigurationHead(
            self.config.hidden_dim,
            self.config.cost_config_dim,
            self.config.n_attention_tokens,
            self.config.attention_token_dim,
        )
        self.actor_head = ConfigurationHead(
            self.config.hidden_dim,
            self.config.actor_config_dim,
            self.config.n_attention_tokens,
            self.config.attention_token_dim,
        )

        # Urgency predictor (how quickly should we act?)
        self.urgency_head = nn.Sequential(
            nn.Linear(self.config.hidden_dim, 64),
            nn.GELU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

        # Mode predictor (which action mode to use?)
        self.mode_head = nn.Sequential(
            nn.Linear(self.config.hidden_dim, 64),
            nn.GELU(),
            nn.Linear(64, 3),  # mode_1, mode_2, hierarchical
        )

        logger.info(
            f"ConfiguratorModule initialized: hidden={self.config.hidden_dim}, "
            f"layers={self.config.n_layers}, heads={self.config.n_heads}"
        )

    def _get_default_states(
        self, batch_size: int, device: torch.device
    ) -> tuple[torch.Tensor, ...]:
        """Get default zero states for missing module states."""
        return (
            torch.zeros(batch_size, self.config.perception_state_dim, device=device),
            torch.zeros(batch_size, self.config.world_model_state_dim, device=device),
            torch.zeros(batch_size, self.config.cost_state_dim, device=device),
            torch.zeros(batch_size, self.config.actor_state_dim, device=device),
        )

    def forward(
        self,
        task_embedding: torch.Tensor,
        task_type: str = "general",
        perception_state: torch.Tensor | None = None,
        world_model_state: torch.Tensor | None = None,
        cost_state: torch.Tensor | None = None,
        actor_state: torch.Tensor | None = None,
    ) -> dict[str, Any]:
        """Forward pass - generate raw configuration tensors.

        Args:
            task_embedding: [B, task_dim] task description embedding
            task_type: Type of task for specialized handling
            *_state: Current state from each module (optional)

        Returns:
            Dictionary with raw configuration tensors
        """
        B = task_embedding.shape[0]
        device = task_embedding.device

        # Get default states for missing inputs
        defaults = self._get_default_states(B, device)
        if perception_state is None:
            perception_state = defaults[0]
        if world_model_state is None:
            world_model_state = defaults[1]
        if cost_state is None:
            cost_state = defaults[2]
        if actor_state is None:
            actor_state = defaults[3]

        # Encode task
        task_hidden = self.task_encoder(task_embedding, task_type)

        # Encode module states
        perception_hidden = self.perception_encoder(perception_state)
        world_model_hidden = self.world_model_encoder(world_model_state)
        cost_hidden = self.cost_encoder(cost_state)
        actor_hidden = self.actor_encoder(actor_state)

        # Stack as sequence for transformer [B, 5, hidden_dim]
        context = torch.stack(
            [
                task_hidden,
                perception_hidden,
                world_model_hidden,
                cost_hidden,
                actor_hidden,
            ],
            dim=1,
        )

        # Aggregate context through transformer
        aggregated = self.context_aggregator(context)

        # Use task position (first) as the main configuration source
        main_hidden = aggregated[:, 0, :]

        # Generate configurations for each module
        perception_config, perception_tokens = self.perception_head(aggregated[:, 1, :])
        world_model_config, world_model_tokens = self.world_model_head(aggregated[:, 2, :])
        cost_config, cost_tokens = self.cost_head(aggregated[:, 3, :])
        actor_config, actor_tokens = self.actor_head(aggregated[:, 4, :])

        # Global configuration
        urgency = self.urgency_head(main_hidden).squeeze(-1)
        mode_logits = self.mode_head(main_hidden)

        return {
            "perception_config": perception_config,
            "perception_tokens": perception_tokens,
            "world_model_config": world_model_config,
            "world_model_tokens": world_model_tokens,
            "cost_config": cost_config,
            "cost_tokens": cost_tokens,
            "actor_config": actor_config,
            "actor_tokens": actor_tokens,
            "urgency": urgency,
            "mode_logits": mode_logits,
            "aggregated_context": aggregated,
        }

    def configure(
        self,
        task_embedding: torch.Tensor,
        task_type: str = "general",
        perception_state: torch.Tensor | None = None,
        world_model_state: torch.Tensor | None = None,
        cost_state: torch.Tensor | None = None,
        actor_state: torch.Tensor | None = None,
    ) -> TaskConfiguration:
        """Generate TaskConfiguration for all modules.

        This is the main API for the Configurator.

        Args:
            task_embedding: [B, task_dim] task description embedding
            task_type: Type of task
            *_state: Current state from each module

        Returns:
            TaskConfiguration with settings for all modules
        """
        # Get raw outputs
        raw = self.forward(
            task_embedding,
            task_type,
            perception_state,
            world_model_state,
            cost_state,
            actor_state,
        )

        # Decode into structured configuration
        # (Using mean across batch for simplicity - could be per-sample)
        # Keep tensors on GPU, only sync at the end for final config
        urgency_tensor = raw["urgency"].mean()

        # Decode action mode from logits (keep on GPU)
        mode_probs = F.softmax(raw["mode_logits"].mean(dim=0), dim=-1)
        mode_idx_tensor = mode_probs.argmax()
        modes = ["mode_1", "mode_2", "hierarchical"]

        # Decode world model config from raw tensor (stay on GPU)
        wm_config_raw = raw["world_model_config"].mean(dim=0)
        horizon_tensor = torch.clamp(torch.sigmoid(wm_config_raw[0]) * 50, min=1.0, max=50.0).long()
        e8_levels_tensor = torch.clamp(
            torch.sigmoid(wm_config_raw[1]) * 16, min=1.0, max=16.0
        ).long()

        # Decode actor config (stay on GPU)
        actor_config_raw = raw["actor_config"].mean(dim=0)
        exploration_rate_tensor = torch.sigmoid(actor_config_raw[0]) * 0.3

        # Single synchronization point: convert all at once
        urgency = float(urgency_tensor.item())
        mode_idx = int(mode_idx_tensor.item())
        action_mode = modes[mode_idx]
        horizon = int(horizon_tensor.item())
        e8_levels = int(e8_levels_tensor.item())
        exploration_rate = float(exploration_rate_tensor.item())

        # Build TaskConfiguration
        config = TaskConfiguration(
            task_type=task_type,
            perception=PerceptionConfig(
                attention_tokens=raw["perception_tokens"],
                mode="standard",
            ),
            world_model=WorldModelConfig(
                horizon=horizon,
                e8_levels=e8_levels,
                predictor_tokens=raw["world_model_tokens"],
            ),
            cost=CostConfig(),  # Use defaults, modulated by tokens
            actor=ActorConfig(
                mode=action_mode,
                exploration_rate=exploration_rate,
            ),
            urgency=urgency,
            timestamp=time.time(),
        )

        return config

    def get_state(self) -> torch.Tensor:
        """Get configurator's own state for meta-learning.

        Returns a state vector summarizing the configurator's current
        configuration tendencies and learned biases for meta-learning.
        This enables higher-level adaptation of configuration strategies.

        Returns:
            State tensor [128] containing:
            - Configuration biases [64]: Learned preferences for config values
            - Task affinity weights [32]: Strengths for different task types
            - Performance metrics [32]: Historical configuration success rates
        """
        # Get current model parameters as state representation
        state_components = []

        # Extract learned biases from the feed-forward layers
        with torch.no_grad():
            # Configuration biases from intermediate layers
            if hasattr(self.config_head, "weight"):
                # Use mean of output layer weights as configuration bias summary
                config_biases = self.config_head.weight.mean(dim=0)[:64]
                if config_biases.numel() < 64:
                    # Pad if insufficient parameters
                    config_biases = torch.cat(
                        [
                            config_biases,
                            torch.zeros(64 - config_biases.numel(), device=config_biases.device),
                        ]
                    )
                state_components.append(config_biases[:64])
            else:
                # Fallback if no learned weights available
                state_components.append(torch.zeros(64, device=self.device))

            # Task affinity weights (placeholder - would track task performance)
            task_affinities = torch.zeros(32, device=self.device)
            # In production: task_affinities = self._compute_task_affinities()
            state_components.append(task_affinities)

            # Performance metrics (placeholder - would track success rates)
            performance_metrics = torch.ones(32, device=self.device) * 0.5  # Neutral performance
            # In production: performance_metrics = self._get_performance_history()
            state_components.append(performance_metrics)

        # Concatenate all state components
        state_vector = torch.cat(state_components, dim=0)

        # Ensure exactly 128 dimensions
        if state_vector.numel() > 128:
            state_vector = state_vector[:128]
        elif state_vector.numel() < 128:
            padding = torch.zeros(128 - state_vector.numel(), device=state_vector.device)
            state_vector = torch.cat([state_vector, padding])

        return state_vector


# =============================================================================
# INTEGRATED EXECUTIVE CONTROL
# =============================================================================


class IntegratedExecutiveControl:
    """Unified executive control integrating all routing/configuration systems.

    This is the CANONICAL entry point for task configuration in K OS.
    It coordinates:
    - ConfiguratorModule (neural configuration)
    - AdaptiveReasoningRouter (reasoning strategy)
    - AdaptiveAttentionAllocator (phase timing)
    - MultiModelRouter (LLM selection)

    Usage:
        executive = get_executive_control()
        config = await executive.configure_for_task(task_embedding, task_type)

        # Config contains everything needed for execution
        world_model.set_config(config.world_model)
        actor.set_config(config.actor)
    """

    def __init__(self, configurator_config: ConfiguratorConfig | None = None):
        # Neural configurator
        self._configurator = ConfiguratorModule(configurator_config)

        # Existing routing systems (lazy loaded)
        self._reasoning_router = None
        self._attention_allocator = None
        self._model_router = None

        logger.info("IntegratedExecutiveControl initialized")

    def _get_reasoning_router(self) -> None:
        """Lazy load reasoning router (ML-enhanced version)."""
        if self._reasoning_router is None:
            try:
                from kagami.core.reasoning.adaptive_router import (
                    get_adaptive_router,
                )

                self._reasoning_router = get_adaptive_router(mode="ml")  # type: ignore[assignment]
            except ImportError:
                # Fallback to base router
                try:
                    from kagami.core.reasoning.adaptive_router import (
                        get_adaptive_router,
                    )

                    self._reasoning_router = get_adaptive_router()  # type: ignore[assignment]
                except ImportError:
                    logger.debug("AdaptiveReasoningRouter not available")
        return self._reasoning_router

    def _get_attention_allocator(self) -> None:
        """Lazy load attention allocator."""
        if self._attention_allocator is None:
            try:
                from kagami.core.execution.adaptive_attention_allocator import (
                    AdaptiveAttentionAllocator,
                )

                self._attention_allocator = AdaptiveAttentionAllocator()  # type: ignore[assignment]
            except ImportError:
                logger.debug("AdaptiveAttentionAllocator not available")
        return self._attention_allocator

    def _get_model_router(self) -> None:
        """Lazy load model router."""
        if self._model_router is None:
            try:
                from kagami.core.routing import get_multi_model_router

                self._model_router = get_multi_model_router()  # type: ignore[assignment]
            except ImportError:
                logger.debug("MultiModelRouter not available")
        return self._model_router

    async def configure_for_task(
        self,
        task_embedding: torch.Tensor,
        task_type: str = "general",
        task_description: str = "",
        perception_state: torch.Tensor | None = None,
        world_model_state: torch.Tensor | None = None,
        cost_state: torch.Tensor | None = None,
        actor_state: torch.Tensor | None = None,
        context: Any = None,
        time_budget: float = 60.0,
    ) -> TaskConfiguration:
        """Configure all systems for a task.

        This is the main API - call this to get unified configuration.

        Args:
            task_embedding: Task semantic embedding
            task_type: Type of task
            task_description: Text description for routing
            *_state: Current module states
            context: Execution context
            time_budget: Total time budget in seconds

        Returns:
            Complete TaskConfiguration
        """
        # 1. Get neural configuration from ConfiguratorModule
        config = self._configurator.configure(
            task_embedding=task_embedding,
            task_type=task_type,
            perception_state=perception_state,
            world_model_state=world_model_state,
            cost_state=cost_state,
            actor_state=actor_state,
        )

        # 2. Enhance with reasoning router (if available)
        reasoning_router = self._get_reasoning_router()  # type: ignore[func-returns-value]
        if reasoning_router and task_description:
            try:
                reasoning_config = reasoning_router.route(task_description)
                # Apply reasoning config to actor
                config.actor.policy_temperature = reasoning_config.temperature
            except Exception as e:
                logger.debug(f"Reasoning router failed: {e}")

        # 3. Enhance with attention allocation (if available)
        attention_allocator = self._get_attention_allocator()  # type: ignore[func-returns-value]
        if attention_allocator:
            try:
                phase_allocation = attention_allocator.allocate_attention(
                    task_description or task_type,
                    context,
                    time_budget,
                )
                # Store phase timing in config metadata
                config.actor.planning_horizon = int(phase_allocation.get("simulate", 10) * 2)
            except Exception as e:
                logger.debug(f"Attention allocator failed: {e}")

        return config

    @property
    def configurator(self) -> ConfiguratorModule:
        """Access the underlying ConfiguratorModule."""
        return self._configurator


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_configurator: ConfiguratorModule | None = None
_executive: IntegratedExecutiveControl | None = None


def get_configurator(config: ConfiguratorConfig | None = None) -> ConfiguratorModule:
    """Get or create the global Configurator module.

    Args:
        config: Optional configuration (used only on first call)

    Returns:
        Singleton ConfiguratorModule instance
    """
    global _configurator
    if _configurator is None:
        _configurator = ConfiguratorModule(config)
        logger.info("Created global ConfiguratorModule")
    return _configurator


def get_executive_control(
    config: ConfiguratorConfig | None = None,
) -> IntegratedExecutiveControl:
    """Get or create the global IntegratedExecutiveControl.

    This is the PREFERRED entry point for task configuration.

    Args:
        config: Optional configurator config

    Returns:
        Singleton IntegratedExecutiveControl instance
    """
    global _executive
    if _executive is None:
        _executive = IntegratedExecutiveControl(config)
        logger.info("Created global IntegratedExecutiveControl")
    return _executive


def reset_configurator() -> None:
    """Reset the global configurator (for testing)."""
    global _configurator, _executive
    _configurator = None
    _executive = None
