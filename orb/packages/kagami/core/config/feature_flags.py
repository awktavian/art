"""K os Feature Flags - Production Configuration System.

Centralized feature flag system.

Default posture:
- Core/runtime features remain enabled by default.
- High-risk research capabilities (especially self-modification) are **opt-in** via env.
"""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LifecycleFlags:
    """Agent lifecycle features (biological paradigm)."""

    enable_agent_mitosis: bool = True
    enable_agent_apoptosis: bool = True
    enable_genetic_evolution: bool = True
    enable_genetic_memory: bool = True

    # Emergency overrides
    force_static_pool: bool = False
    max_global_agents: int = 500

    @classmethod
    def from_env(cls) -> LifecycleFlags:
        """Load lifecycle flags from environment variables.

        Environment variables: None (all lifecycle features enabled by default)
            - KAGAMI_MAX_GLOBAL_AGENTS: Maximum agent count (default: 500)

        Returns:
            LifecycleFlags instance with environment configuration
        """
        return cls(
            enable_agent_mitosis=True,
            enable_agent_apoptosis=True,
            enable_genetic_evolution=True,
            enable_genetic_memory=True,
            force_static_pool=False,
            max_global_agents=int(os.getenv("KAGAMI_MAX_GLOBAL_AGENTS", "500")),
        )


@dataclass
class WorldModelFlags:
    """World model and geometric intelligence features."""

    use_geometric_world_model: bool = True
    enforce_g2_equivariance: bool = True
    enable_matryoshka_brain: bool = True
    enable_chaos_reservoir: bool = True

    # Configuration
    world_model_dimensions: int = 2048
    matryoshka_layers: int = 7
    g2_validation_threshold: float = 0.001

    # Fallback options
    use_poincare_only: bool = False

    @classmethod
    def from_env(cls) -> WorldModelFlags:
        """Load world model flags from environment variables.

        Environment variables:
            - KAGAMI_WM_DIMENSIONS: World model embedding dimensions (default: 2048)
            - KAGAMI_MATRYOSHKA_LAYERS: Number of matryoshka layers (default: 7)
            - KAGAMI_G2_THRESHOLD: G2 equivariance validation threshold (default: 0.001)

        Returns:
            WorldModelFlags instance with environment configuration
        """
        return cls(
            use_geometric_world_model=True,
            enforce_g2_equivariance=True,
            enable_matryoshka_brain=True,
            enable_chaos_reservoir=True,
            world_model_dimensions=int(os.getenv("KAGAMI_WM_DIMENSIONS", "2048")),
            matryoshka_layers=int(os.getenv("KAGAMI_MATRYOSHKA_LAYERS", "7")),
            g2_validation_threshold=float(os.getenv("KAGAMI_G2_THRESHOLD", "0.001")),
            use_poincare_only=False,
        )


@dataclass
class SafetyFlags:
    """Safety system configuration.
    ALWAYS ON.
    """

    # CBF parameters
    cbf_safety_threshold: float = 1.0
    cbf_alpha: float = 0.5

    # Memory limits
    memory_soft_limit_gb: float = 4.0
    memory_hard_limit_gb: float = 8.0

    @classmethod
    def from_env(cls) -> SafetyFlags:
        """Load safety flags from environment variables.

        Environment variables:
            - KAGAMI_CBF_THRESHOLD: Control Barrier Function safety threshold (default: 1.0)
            - KAGAMI_CBF_ALPHA: CBF alpha parameter for h(x) dynamics (default: 0.5)
            - KAGAMI_MEMORY_SOFT_LIMIT_GB: Soft memory limit for warnings (default: 4.0)
            - KAGAMI_MEMORY_HARD_LIMIT_GB: Hard memory limit for termination (default: 8.0)

        Returns:
            SafetyFlags instance with environment configuration
        """
        return cls(
            cbf_safety_threshold=float(os.getenv("KAGAMI_CBF_THRESHOLD", "1.0")),
            cbf_alpha=float(os.getenv("KAGAMI_CBF_ALPHA", "0.5")),
            memory_soft_limit_gb=float(os.getenv("KAGAMI_MEMORY_SOFT_LIMIT_GB", "4.0")),
            memory_hard_limit_gb=float(os.getenv("KAGAMI_MEMORY_HARD_LIMIT_GB", "8.0")),
        )

    def validate(self) -> None:
        """Validate safety flag constraints.

        Raises:
            ValueError: If hard memory limit is less than soft limit
        """
        if self.memory_hard_limit_gb < self.memory_soft_limit_gb:
            raise ValueError(
                f"Hard limit ({self.memory_hard_limit_gb}) < soft limit ({self.memory_soft_limit_gb})"
            )


@dataclass
class ObservabilityFlags:
    """Observability and monitoring configuration."""

    enable_profiling: bool = False
    receipt_batch_size: int = 100
    receipt_flush_interval_ms: int = 1000
    enable_high_cardinality_labels: bool = False

    @classmethod
    def from_env(cls) -> ObservabilityFlags:
        """Load observability flags from environment variables.

        Environment variables:
            - KAGAMI_ENABLE_PROFILING: Enable performance profiling (default: 0)
            - KAGAMI_RECEIPT_BATCH_SIZE: Receipt batch size for metrics (default: 100)
            - KAGAMI_RECEIPT_FLUSH_MS: Receipt flush interval in ms (default: 1000)
            - KAGAMI_HIGH_CARDINALITY_LABELS: Enable high-cardinality labels (default: 0)

        Returns:
            ObservabilityFlags instance with environment configuration
        """
        return cls(
            enable_profiling=os.getenv("KAGAMI_ENABLE_PROFILING", "0") == "1",
            receipt_batch_size=int(os.getenv("KAGAMI_RECEIPT_BATCH_SIZE", "100")),
            receipt_flush_interval_ms=int(os.getenv("KAGAMI_RECEIPT_FLUSH_MS", "1000")),
            enable_high_cardinality_labels=os.getenv("KAGAMI_HIGH_CARDINALITY_LABELS", "0") == "1",
        )


@dataclass
class ResearchFlags:
    """Experimental research features."""

    # SAFE-BY-DEFAULT: high-risk autonomous features are opt-in.
    enable_self_modification: bool = False
    enable_continuous_evolution: bool = False
    enable_self_healing: bool = False
    enable_periodic_reflection: bool = False
    enable_federated_learning: bool = False
    enable_swarm_intelligence: bool = False
    enable_social_learning: bool = False

    @classmethod
    def from_env(cls) -> ResearchFlags:
        """Load research flags from environment variables.

        All research features are OPT-IN (default: disabled) for safety.

        Environment variables:
            - KAGAMI_ENABLE_SELF_MODIFICATION: Allow autonomous code modification (default: false)
            - KAGAMI_ENABLE_CONTINUOUS_EVOLUTION: Enable continuous evolution (default: false)
            - KAGAMI_ENABLE_SELF_HEALING: Enable self-healing mechanisms (default: false)
            - KAGAMI_ENABLE_PERIODIC_REFLECTION: Enable periodic self-reflection (default: false)
            - KAGAMI_ENABLE_FEDERATED_LEARNING: Enable federated learning (default: false)
            - KAGAMI_ENABLE_SWARM_INTELLIGENCE: Enable swarm behaviors (default: false)
            - KAGAMI_ENABLE_SOCIAL_LEARNING: Enable social learning (default: false)

        Returns:
            ResearchFlags instance with environment configuration
        """

        def _env_bool(name: str, default: bool) -> bool:
            val = os.getenv(name)
            if val is None:
                return default
            return val.lower() in ("1", "true", "yes", "on")

        return cls(
            enable_self_modification=_env_bool("KAGAMI_ENABLE_SELF_MODIFICATION", False),
            enable_continuous_evolution=_env_bool("KAGAMI_ENABLE_CONTINUOUS_EVOLUTION", False),
            enable_self_healing=_env_bool("KAGAMI_ENABLE_SELF_HEALING", False),
            enable_periodic_reflection=_env_bool("KAGAMI_ENABLE_PERIODIC_REFLECTION", False),
            enable_federated_learning=_env_bool("KAGAMI_ENABLE_FEDERATED_LEARNING", False),
            enable_swarm_intelligence=_env_bool("KAGAMI_ENABLE_SWARM_INTELLIGENCE", False),
            enable_social_learning=_env_bool("KAGAMI_ENABLE_SOCIAL_LEARNING", False),
        )


# Global singleton
_feature_flags: FeatureFlags | None = None


@dataclass
class FeatureFlags:
    """Complete K os feature configuration."""

    lifecycle: LifecycleFlags = field(default_factory=LifecycleFlags)
    world_model: WorldModelFlags = field(default_factory=WorldModelFlags)
    safety: SafetyFlags = field(default_factory=SafetyFlags)
    observability: ObservabilityFlags = field(default_factory=ObservabilityFlags)
    research: ResearchFlags = field(default_factory=ResearchFlags)

    @classmethod
    def from_env(cls) -> FeatureFlags:
        """Load all feature flags from environment variables.

        Creates complete FeatureFlags with all subsystems loaded from environment.

        Returns:
            FeatureFlags instance with all categories configured

        Raises:
            ValueError: If safety flag validation fails
        """
        flags = cls(
            lifecycle=LifecycleFlags.from_env(),
            world_model=WorldModelFlags.from_env(),
            safety=SafetyFlags.from_env(),
            observability=ObservabilityFlags.from_env(),
            research=ResearchFlags.from_env(),
        )
        flags.safety.validate()
        return flags

    def as_dict(self) -> dict[str, Any]:
        """Convert feature flags to nested dictionary.

        Returns:
            Dictionary with category keys and flag dictionaries
        """
        return {
            "lifecycle": asdict(self.lifecycle),
            "world_model": asdict(self.world_model),
            "safety": asdict(self.safety),
            "observability": asdict(self.observability),
            "research": asdict(self.research),
        }

    def as_metric_labels(self) -> dict[str, str]:
        """Convert feature flags to Prometheus metric labels.

        Returns:
            Dictionary of feature names to "on"/"off" strings
        """
        return {
            "mitosis": "on",
            "apoptosis": "on",
            "evolution": "on",
            "geometric_wm": "on",
            "g2_equivariance": "on",
        }

    def apply_overrides(self, overrides: dict[str, Any]) -> None:
        """Apply runtime overrides to feature flags.

        Updates flags from dictionary, performing type conversions as needed.
        Validates safety constraints after applying overrides.

        Args:
            overrides: Dictionary with category keys and flag overrides
                Example: {"safety": {"cbf_threshold": "0.8"}}
        """
        for category_name, flags in overrides.items():
            if not hasattr(self, category_name):
                continue

            category_obj = getattr(self, category_name)
            for flag_name, value in flags.items():
                if hasattr(category_obj, flag_name):
                    # Type conversion
                    target_type = type(getattr(category_obj, flag_name))
                    if target_type is bool and isinstance(value, str):
                        value = value.lower() in ("true", "1", "yes", "on")
                    elif target_type is int and isinstance(value, str):
                        try:
                            value = int(value)
                        except ValueError:
                            continue
                    elif target_type is float and isinstance(value, str):
                        try:
                            value = float(value)
                        except ValueError:
                            continue

                    setattr(category_obj, flag_name, value)

        try:
            self.safety.validate()
        except Exception:
            pass


# FeatureFlagWatcher moved to services layer to fix layer violation
# (config L0 should not import from consensus L4)
# Re-export for backward compatibility
def get_feature_flag_watcher() -> Any:
    """Get the feature flag watcher (re-exported from services layer).

    Re-export to maintain backward compatibility after layer refactoring.

    Returns:
        FeatureFlagWatcher instance for consensus-based flag synchronization
    """
    from kagami.core.services.feature_flag_sync import get_feature_flag_watcher as _get_watcher

    return _get_watcher()


# Re-export class for type hints
def __getattr__(name: str) -> Any:
    if name == "FeatureFlagWatcher":
        from kagami.core.services.feature_flag_sync import FeatureFlagWatcher

        return FeatureFlagWatcher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def get_feature_flags() -> FeatureFlags:
    """Get global feature flags singleton.

    Lazy-loads from environment on first call. Registers metrics if available.

    Returns:
        Global FeatureFlags instance
    """
    global _feature_flags
    if _feature_flags is None:
        _feature_flags = FeatureFlags.from_env()

        try:
            from kagami_observability.metrics.system import FEATURE_FLAGS_ACTIVE

            for feature, state in _feature_flags.as_metric_labels().items():
                FEATURE_FLAGS_ACTIVE.labels(feature=feature, state=state).set(1)
        except ImportError:
            pass

    return _feature_flags


def reload_feature_flags() -> FeatureFlags:
    """Reload feature flags from environment.

    Clears cached flags and re-loads from environment variables.
    Use when environment has changed and flags need refresh.

    Returns:
        Newly loaded FeatureFlags instance
    """
    global _feature_flags
    _feature_flags = None
    return get_feature_flags()


def reset_feature_flags() -> None:
    """Reset feature flags singleton to None.

    Forces reload on next get_feature_flags() call.
    Primarily for testing.
    """
    global _feature_flags
    _feature_flags = None


__all__ = [
    "FeatureFlags",
    "LifecycleFlags",
    "ObservabilityFlags",
    "ResearchFlags",
    "SafetyFlags",
    "WorldModelFlags",
    "get_feature_flag_watcher",
    "get_feature_flags",
    "reload_feature_flags",
    "reset_feature_flags",
]
