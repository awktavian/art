"""Configuration module - unified entry point.

CONSOLIDATED: December 31, 2025
All configuration is now in unified_config.py. This module re-exports everything
for backward compatibility. Direct imports from unified_config.py are preferred.

USAGE:
======
# Legacy style (for backward compatibility)
from kagami.core.config import get_config, get_bool_config, get_int_config

# Modern style (recommended)
from kagami.core.config import get_kagami_config

config = get_kagami_config()  # Uses environment + defaults
config = get_kagami_config(profile="large")  # Named preset

# Runtime config management
from kagami.core.config import RuntimeConfigManager, get_config_manager

manager = get_config_manager()
manager.load_from_file("config.yaml", watch_for_changes=True)

MIGRATION NOTES:
================
- config_root.py is deprecated (use unified_config.py)
- comprehensive_config.py is deprecated (use unified_config.py)
- ComprehensiveConfigManager is now aliased to RuntimeConfigManager
- All exports are from unified_config.py (single source of truth)

CREATED: December 16, 2025
CONSOLIDATED: December 31, 2025
"""

from pathlib import Path

# Location configuration (portable deployment support)
from kagami.core.config.location_config import (
    DEFAULT_LOCATION,
    HomeLocation,
    get_home_coordinates,
    get_home_latitude,
    get_home_location,
    get_home_longitude,
    reset_home_location,
    set_home_location,
    validate_location_consistency,
)

# Import everything from unified_config (SINGLE SOURCE OF TRUTH)
# Shared configurations (CONSOLIDATED: Jan 11, 2026)
from kagami.core.config.shared import (
    BasePoolConfig,
    CircuitBreakerConfig,
)
from kagami.core.config.unified_config import (
    # Enums
    ActivationType,
    AdaptiveConfig,
    CBFDynamicsConfig,
    ClassKConfig,
    ClassKType,
    ComprehensiveConfigManager,
    Config,
    ConfigFormat,
    ConfigSchema,
    ConfigSource,
    ConfigValue,
    ConfigWatcher,
    DynamicsType,
    E8BottleneckConfig,
    # Environment configuration (migrated from config_root.py)
    EnvironmentConfig,
    HofstadterLoopConfig,
    # Pydantic V2 configuration models
    KagamiConfig,
    MatryoshkaWeightStrategy,
    RSSMConfig,
    # Runtime config management (migrated from comprehensive_config.py)
    RuntimeConfigManager,
    SafetyConfig,
    SymbioteConfig,
    TrainingConfig,
    WorldModelConfig,
    apply_env_overrides,
    config,
    get_bool_config,
    get_config,
    get_config_manager,
    get_database_url,
    get_int_config,
    # Factory functions
    get_kagami_config,
    get_model_cache_path,
    get_redis_url,
    get_str_config,
    is_production,
    load_config_file,
    load_env_config,
    reset_config_manager,
    settings,
)

__all__ = [
    # Location configuration
    "DEFAULT_LOCATION",
    # Enums
    "ActivationType",
    "AdaptiveConfig",
    # Shared configurations (CONSOLIDATED: Jan 11, 2026)
    "BasePoolConfig",
    "CBFDynamicsConfig",
    "CircuitBreakerConfig",
    "ClassKConfig",
    "ClassKType",
    "ComprehensiveConfigManager",  # Alias for backward compatibility
    "Config",  # Alias for backward compatibility
    "ConfigFormat",
    "ConfigSchema",
    "ConfigSource",
    "ConfigValue",
    "ConfigWatcher",
    "DynamicsType",
    "E8BottleneckConfig",
    # Environment configuration (migrated from config_root.py)
    "EnvironmentConfig",
    "HofstadterLoopConfig",
    "HomeLocation",
    # Pydantic V2 configuration models
    "KagamiConfig",
    "MatryoshkaWeightStrategy",
    "RSSMConfig",
    # Runtime config management (migrated from comprehensive_config.py)
    "RuntimeConfigManager",
    "SafetyConfig",
    "SymbioteConfig",
    "TrainingConfig",
    "WorldModelConfig",
    "apply_env_overrides",
    "config",  # Global singleton proxy
    "get_bool_config",
    "get_config",
    "get_config_manager",
    "get_database_url",
    "get_home_coordinates",
    "get_home_latitude",
    "get_home_location",
    "get_home_longitude",
    "get_int_config",
    # Factory functions
    "get_kagami_config",
    "get_model_cache_path",
    "get_redis_url",
    "get_str_config",
    "is_production",
    "load_config_file",
    "load_env_config",
    "reset_config_manager",
    "reset_home_location",
    "set_home_location",
    "settings",  # Settings view
    "validate_location_consistency",
]


# Initialize Config singleton on import (loads environment)
_config = Config()
