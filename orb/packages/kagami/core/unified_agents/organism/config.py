"""Organism Configuration Module - Configuration management for unified organism.

Responsibilities:
- Organism configuration data class
- Default configuration creation
- Configuration validation
- Feature toggles and optimization settings
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class OrganismConfig:
    """Configuration for UnifiedOrganism.

    Controls all aspects of organism behavior, from consciousness integration
    to colony coordination and execution strategies.
    """

    # Consciousness Integration (Ultimate Goal)
    consciousness_enabled: bool = True
    consciousness_checkpoint_path: str | None = None
    consciousness_auto_save: bool = True
    consciousness_save_interval: int = 300  # seconds

    # Colony Configuration
    colony_count: int = 7  # 7 elementary catastrophes
    colony_max_workers: int = 4
    colony_timeout: float = 30.0

    # E8 Action Reduction
    e8_enabled: bool = True
    e8_action_count: int = 240  # E8 lattice roots
    e8_fano_plane_enabled: bool = True

    # Homeostasis
    homeostasis_enabled: bool = True
    homeostasis_interval: float = 10.0  # seconds
    homeostasis_auto_tune: bool = True

    # Safety Integration
    safety_cbf_enabled: bool = True
    safety_strict_mode: bool = False
    safety_emergency_halt: bool = True

    # Executive Control (LeCun Integration)
    executive_enabled: bool = True
    executive_planning_depth: int = 3
    executive_cost_weighting: float = 1.0

    # Autonomous Goal Engine
    autonomous_goals_enabled: bool = False  # Disabled by default
    autonomous_goal_persistence: bool = True
    autonomous_goal_checkpoint: str | None = None

    # Social Symbiote
    symbiote_enabled: bool = False  # Disabled by default
    symbiote_theory_of_mind: bool = True
    symbiote_interaction_history: int = 100

    # Perception Integration
    perception_enabled: bool = False  # Disabled by default
    perception_multimodal: bool = True
    perception_memory_size: int = 1000

    # Ambient Integration
    ambient_enabled: bool = False  # Disabled by default
    ambient_auto_update: bool = True
    ambient_state_persistence: bool = True

    # World Model Integration
    world_model_enabled: bool = True
    world_model_context_size: int = 2048
    world_model_memory_buffer: int = 10000

    # Knowledge Graph Integration
    knowledge_graph_enabled: bool = True
    knowledge_graph_auto_update: bool = True
    knowledge_graph_max_entities: int = 100000

    # Performance Optimization
    lazy_loading: bool = True
    torch_compile_enabled: bool = False  # Disabled by default
    mixed_precision: bool = False  # Disabled by default
    memory_optimization: bool = True

    # Debugging and Monitoring
    debug_mode: bool = False
    metrics_enabled: bool = True
    profiling_enabled: bool = False
    log_level: str = "INFO"

    # Advanced Features
    catastrophe_algebra: bool = True  # Thom's catastrophes
    fano_plane_routing: bool = True  # Projective geometry
    e8_lattice_embedding: bool = True  # Exceptional geometry
    receipt_learning: bool = True  # Self-improvement

    def __post_init__(self):
        """Validate and adjust configuration after initialization."""
        # Validate colony count
        if self.colony_count < 1:
            logger.warning("Colony count must be at least 1, setting to 7")
            self.colony_count = 7
        elif self.colony_count > 7:
            logger.warning("Colony count > 7 not fully supported, setting to 7")
            self.colony_count = 7

        # Validate E8 action count
        if self.e8_action_count != 240:
            logger.warning("E8 lattice has exactly 240 roots, correcting")
            self.e8_action_count = 240

        # Adjust performance settings based on capabilities
        if self.torch_compile_enabled:
            try:
                import torch

                if not hasattr(torch, "compile"):
                    logger.warning("torch.compile not available, disabling")
                    self.torch_compile_enabled = False
            except ImportError:
                logger.warning("PyTorch not available, disabling torch.compile")
                self.torch_compile_enabled = False

        # Memory optimization recommendations
        if self.memory_optimization:
            if self.world_model_memory_buffer > 50000:
                logger.info("Large memory buffer detected, consider reducing for optimization")
            if self.knowledge_graph_max_entities > 500000:
                logger.info("Large knowledge graph size, consider reducing for optimization")

        # Safety configuration validation
        if self.safety_strict_mode and not self.safety_cbf_enabled:
            logger.warning("Strict safety mode requires CBF, enabling CBF")
            self.safety_cbf_enabled = True

        # Log configuration summary
        if self.debug_mode:
            self._log_config_summary()

    def _log_config_summary(self) -> None:
        """Log configuration summary for debugging."""
        enabled_features = []

        if self.consciousness_enabled:
            enabled_features.append("consciousness")
        if self.e8_enabled:
            enabled_features.append("e8-action-reduction")
        if self.homeostasis_enabled:
            enabled_features.append("homeostasis")
        if self.safety_cbf_enabled:
            enabled_features.append("cbf-safety")
        if self.executive_enabled:
            enabled_features.append("executive-control")
        if self.autonomous_goals_enabled:
            enabled_features.append("autonomous-goals")
        if self.symbiote_enabled:
            enabled_features.append("social-symbiote")
        if self.perception_enabled:
            enabled_features.append("perception")
        if self.ambient_enabled:
            enabled_features.append("ambient-integration")
        if self.world_model_enabled:
            enabled_features.append("world-model")
        if self.knowledge_graph_enabled:
            enabled_features.append("knowledge-graph")

        logger.info(f"Organism features enabled: {', '.join(enabled_features)}")
        logger.info(
            f"Colony configuration: {self.colony_count} colonies, {self.colony_max_workers} max workers"
        )

    def get_feature_status(self) -> dict[str, bool]:
        """Get status of all major features."""
        return {
            "consciousness": self.consciousness_enabled,
            "e8_reduction": self.e8_enabled,
            "homeostasis": self.homeostasis_enabled,
            "safety_cbf": self.safety_cbf_enabled,
            "executive_control": self.executive_enabled,
            "autonomous_goals": self.autonomous_goals_enabled,
            "social_symbiote": self.symbiote_enabled,
            "perception": self.perception_enabled,
            "ambient": self.ambient_enabled,
            "world_model": self.world_model_enabled,
            "knowledge_graph": self.knowledge_graph_enabled,
            "catastrophe_algebra": self.catastrophe_algebra,
            "fano_plane_routing": self.fano_plane_routing,
            "e8_lattice_embedding": self.e8_lattice_embedding,
            "receipt_learning": self.receipt_learning,
        }

    def enable_all_features(self) -> None:
        """Enable all available features (for testing or full functionality)."""
        self.consciousness_enabled = True
        self.e8_enabled = True
        self.homeostasis_enabled = True
        self.safety_cbf_enabled = True
        self.executive_enabled = True
        self.autonomous_goals_enabled = True
        self.symbiote_enabled = True
        self.perception_enabled = True
        self.ambient_enabled = True
        self.world_model_enabled = True
        self.knowledge_graph_enabled = True
        self.catastrophe_algebra = True
        self.fano_plane_routing = True
        self.e8_lattice_embedding = True
        self.receipt_learning = True

        logger.info("All organism features enabled")

    def enable_minimal_features(self) -> None:
        """Enable only minimal features (for basic functionality)."""
        self.consciousness_enabled = False
        self.e8_enabled = True  # Core functionality
        self.homeostasis_enabled = True  # Core functionality
        self.safety_cbf_enabled = True  # Safety is critical
        self.executive_enabled = True  # Core functionality
        self.autonomous_goals_enabled = False
        self.symbiote_enabled = False
        self.perception_enabled = False
        self.ambient_enabled = False
        self.world_model_enabled = False
        self.knowledge_graph_enabled = False
        self.catastrophe_algebra = True  # Core mathematical framework
        self.fano_plane_routing = True  # Core routing
        self.e8_lattice_embedding = True  # Core geometry
        self.receipt_learning = False

        logger.info("Minimal organism features enabled")

    def optimize_for_performance(self) -> None:
        """Optimize configuration for maximum performance."""
        self.lazy_loading = True
        self.memory_optimization = True
        self.torch_compile_enabled = True
        self.mixed_precision = True

        # Reduce memory-intensive features
        self.world_model_context_size = min(1024, self.world_model_context_size)
        self.world_model_memory_buffer = min(5000, self.world_model_memory_buffer)
        self.knowledge_graph_max_entities = min(50000, self.knowledge_graph_max_entities)

        # Disable debugging features
        self.debug_mode = False
        self.profiling_enabled = False
        self.log_level = "WARNING"

        logger.info("Configuration optimized for performance")

    def optimize_for_safety(self) -> None:
        """Optimize configuration for maximum safety."""
        self.safety_cbf_enabled = True
        self.safety_strict_mode = True
        self.safety_emergency_halt = True

        # Enable comprehensive monitoring
        self.homeostasis_enabled = True
        self.homeostasis_auto_tune = True
        self.metrics_enabled = True

        # Conservative timeouts
        self.colony_timeout = min(10.0, self.colony_timeout)
        self.homeostasis_interval = min(5.0, self.homeostasis_interval)

        # Enable debugging for safety analysis
        self.debug_mode = True
        self.log_level = "DEBUG"

        logger.info("Configuration optimized for safety")


def create_organism_config(preset: str | None = None, **overrides: Any) -> OrganismConfig:
    """Create organism configuration with optional preset and overrides."""
    config = OrganismConfig()

    # Apply preset
    if preset == "minimal":
        config.enable_minimal_features()
    elif preset == "full":
        config.enable_all_features()
    elif preset == "performance":
        config.optimize_for_performance()
    elif preset == "safety":
        config.optimize_for_safety()
    elif preset is not None:
        logger.warning(f"Unknown preset '{preset}', using default configuration")

    # Apply overrides
    for key, value in overrides.items():
        if hasattr(config, key):
            setattr(config, key, value)
        else:
            logger.warning(f"Unknown configuration key: {key}")

    return config


def validate_organism_config(config: OrganismConfig) -> list[str]:
    """Validate organism configuration and return list of issues."""
    issues = []

    # Check critical dependencies
    if config.consciousness_enabled and not config.world_model_enabled:
        issues.append("Consciousness requires world model integration")

    if config.autonomous_goals_enabled and not config.executive_enabled:
        issues.append("Autonomous goals require executive control")

    if config.symbiote_enabled and not config.perception_enabled:
        issues.append("Social symbiote requires perception integration")

    if config.safety_strict_mode and not config.safety_cbf_enabled:
        issues.append("Strict safety mode requires CBF safety")

    # Check resource constraints
    if config.colony_count * config.colony_max_workers > 50:
        issues.append("High worker count may cause resource exhaustion")

    if config.world_model_memory_buffer > 100000:
        issues.append("Large world model buffer may cause memory issues")

    if config.knowledge_graph_max_entities > 1000000:
        issues.append("Large knowledge graph may cause performance issues")

    # Check timeout settings
    if config.colony_timeout < 1.0:
        issues.append("Colony timeout too short, may cause premature failures")

    if config.homeostasis_interval < 1.0:
        issues.append("Homeostasis interval too short, may cause excessive overhead")

    # Check feature compatibility
    if config.e8_lattice_embedding and not config.e8_enabled:
        issues.append("E8 lattice embedding requires E8 action reduction")

    if config.fano_plane_routing and not config.e8_fano_plane_enabled:
        issues.append("Fano plane routing requires E8 fano plane support")

    return issues


def get_default_config() -> OrganismConfig:
    """Get default organism configuration."""
    return OrganismConfig()


def get_minimal_config() -> OrganismConfig:
    """Get minimal organism configuration."""
    return create_organism_config(preset="minimal")


def get_full_config() -> OrganismConfig:
    """Get full-featured organism configuration."""
    return create_organism_config(preset="full")


def get_performance_config() -> OrganismConfig:
    """Get performance-optimized organism configuration."""
    return create_organism_config(preset="performance")


def get_safety_config() -> OrganismConfig:
    """Get safety-optimized organism configuration."""
    return create_organism_config(preset="safety")
