"""Organism submodules - decomposed UnifiedOrganism components.

This package contains focused modules extracted from the unified_organism.py god class:

- base.py: Constants, lazy imports, shared utilities
- config.py: OrganismConfig and configuration management
- consciousness_manager.py: Consciousness integration manager
- perception.py: Sensory processing, observation encoding (PerceptionMixin)
- cognition.py: World model integration, symbiote, executive control (CognitionMixin)
- action.py: Action selection, policy execution, cost evaluation (ActionMixin)
- learning.py: Receipt learning, knowledge graph, adaptation (LearningMixin)
- lifecycle.py: Initialization, shutdown, health monitoring (LifecycleMixin)
- ambient.py: Ambient state integration, phase transitions (AmbientMixin)
"""

from kagami.core.unified_agents.organism.action import ActionMixin
from kagami.core.unified_agents.organism.ambient import AmbientMixin
from kagami.core.unified_agents.organism.base import (
    DEFAULT_MAX_POPULATION,
    GLOBAL_MAX_POPULATION,
    lazy_import_torch,
)
from kagami.core.unified_agents.organism.cognition import CognitionMixin
from kagami.core.unified_agents.organism.config import (
    OrganismConfig,
    create_organism_config,
    get_default_config,
    get_full_config,
    get_minimal_config,
    get_performance_config,
    get_safety_config,
    validate_organism_config,
)
from kagami.core.unified_agents.organism.consciousness_manager import ConsciousnessManager
from kagami.core.unified_agents.organism.learning import LearningMixin
from kagami.core.unified_agents.organism.lifecycle import LifecycleMixin
from kagami.core.unified_agents.organism.perception import PerceptionMixin

__all__ = [
    "DEFAULT_MAX_POPULATION",
    "GLOBAL_MAX_POPULATION",
    "ActionMixin",
    "AmbientMixin",
    "CognitionMixin",
    "ConsciousnessManager",
    "LearningMixin",
    "LifecycleMixin",
    "OrganismConfig",
    "PerceptionMixin",
    "create_organism_config",
    "get_default_config",
    "get_full_config",
    "get_minimal_config",
    "get_performance_config",
    "get_safety_config",
    "lazy_import_torch",
    "validate_organism_config",
]
