"""Executive Control Module - Configurator Architecture.

Implements LeCun's Configurator concept from "A Path Towards Autonomous Machine Intelligence":

> "The configurator module takes inputs from all other modules and configures them
> for the task at hand by modulating their parameters and their attention circuits."

The Configurator is the EXECUTIVE CONTROL center of K OS. It:
1. Receives context from all modules (perception, world model, cost, actor)
2. Outputs configuration tokens that modulate each module's behavior
3. Enables task-specific adaptation without retraining

Architecture:
    TaskEmbedding + ModuleStates → Transformer → ConfigurationTokens
                                                        ↓
                    ┌──────────────┬──────────────┬──────────────┐
                    ↓              ↓              ↓              ↓
               Perception    WorldModel        Cost          Actor

Key insight: Configuration tokens act as "extra inputs" to transformer-based
modules, dynamically routing attention and modulating function.

Created: December 6, 2025
Reference: docs/LECUN_INTEGRATION_COMPLETE.md
"""

from __future__ import annotations

from kagami.core.executive.configurator import (
    ConfiguratorConfig,
    ConfiguratorModule,
    IntegratedExecutiveControl,
    get_configurator,
    get_executive_control,
    reset_configurator,
)
from kagami.core.executive.task_configuration import (
    ActorConfig,
    CostConfig,
    PerceptionConfig,
    TaskConfiguration,
    WorldModelConfig,
)

__all__ = [
    "ActorConfig",
    "ConfiguratorConfig",
    # Core classes
    "ConfiguratorModule",
    "CostConfig",
    "IntegratedExecutiveControl",
    "PerceptionConfig",
    # Configuration dataclasses
    "TaskConfiguration",
    "WorldModelConfig",
    # Singleton accessors (PREFERRED: get_executive_control)
    "get_configurator",
    "get_executive_control",
    "reset_configurator",
]
