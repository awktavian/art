"""Model cache configuration schema.

Provides centralized configuration for the model cache system with support for:
- YAML configuration files
- Environment variable overrides
- XDG Base Directory specification compliance
- Hugging Face integration

Environment Variables:
    KAGAMI_MODEL_CACHE_DIR: Override cache directory
    KAGAMI_MODEL_CACHE_MAX_SIZE_GB: Override maximum cache size
    KAGAMI_MODEL_CACHE_MAX_MODELS: Override maximum model count
    KAGAMI_MODEL_CACHE_ENABLED: Disable caching if "0"
    KAGAMI_MODEL_CACHE_WARM: Enable/disable warm cache
    MODEL_CACHE_PATH: Legacy cache directory (lower priority)
    HF_HOME: Hugging Face cache directory
    XDG_CACHE_HOME: XDG base cache directory

Example YAML:
    model_cache:
      cache_dir: ${XDG_CACHE_HOME:-~/.cache}/kagami/models
      max_size_gb: 100.0
      max_models: 10
      eviction_policy: lru
      ttl_hours: 168
      warm_cache:
        enabled: true
        models:
          - model_id: "Qwen/Qwen3-14B"
            priority: high
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


@dataclass
class WarmCacheModel:
    """Configuration for a model to warm-load on startup.

    Attributes:
        model_id: Hugging Face model identifier or local path
        priority: Loading priority (high loads first)
        config: Model-specific configuration (device, dtype, etc.)
    """

    model_id: str
    priority: Literal["high", "medium", "low"] = "medium"
    config: dict[str, Any] = field(default_factory=dict[str, Any])

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.model_id:
            raise ValueError("model_id cannot be empty")
        if self.priority not in ("high", "medium", "low"):
            raise ValueError(f"Invalid priority: {self.priority}")


@dataclass
class WarmCacheConfig:
    """Configuration for warm cache on startup.

    Attributes:
        enabled: Whether to enable warm cache
        models: List of models to pre-load
    """

    enabled: bool = True
    models: list[WarmCacheModel] = field(default_factory=list[Any])

    def __post_init__(self) -> None:
        """Validate configuration."""
        # Ensure models are WarmCacheModel instances
        self.models = [
            m if isinstance(m, WarmCacheModel) else WarmCacheModel(**m) for m in self.models
        ]


@dataclass
class MetricsConfig:
    """Configuration for cache metrics and monitoring.

    Attributes:
        enabled: Whether to enable metrics collection
        prometheus_namespace: Namespace for Prometheus metrics
    """

    enabled: bool = True
    prometheus_namespace: str = "kagami_model_cache"

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not self.prometheus_namespace:
            raise ValueError("prometheus_namespace cannot be empty")


@dataclass
class ModelCacheConfig:
    """Configuration for model cache system.

    Attributes:
        cache_dir: Directory for model cache storage
        max_size_gb: Maximum cache size in gigabytes
        max_models: Maximum number of models to keep
        eviction_policy: Cache eviction strategy
        ttl_hours: Time-to-live for cached models in hours
        hf_cache_dir: Hugging Face cache directory
        scan_hf_on_startup: Scan HF cache for existing models on startup
        warm_cache: Warm cache configuration
        metrics: Metrics configuration
        verify_checksums: Verify model checksums on load
        atomic_writes: Use atomic writes for cache files
    """

    cache_dir: Path
    max_size_gb: float = 100.0
    max_models: int = 10
    eviction_policy: Literal["lru", "lfu", "fifo"] = "lru"
    ttl_hours: int = 168  # 1 week
    hf_cache_dir: Path = field(
        default_factory=lambda: Path.home() / ".cache" / "huggingface" / "hub"
    )
    scan_hf_on_startup: bool = True
    warm_cache: WarmCacheConfig = field(default_factory=WarmCacheConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    verify_checksums: bool = True
    atomic_writes: bool = True

    def __post_init__(self) -> None:
        """Validate and normalize configuration.

        Note: mypy reports some lines as unreachable, but they are reachable
        when deserializing from YAML/dict[str, Any] where types may not match field annotations.
        """
        # Ensure paths are Path objects
        if not isinstance(self.cache_dir, Path):
            self.cache_dir = Path(self.cache_dir)  # type: ignore
        if not isinstance(self.hf_cache_dir, Path):
            self.hf_cache_dir = Path(self.hf_cache_dir)  # type: ignore

        # Expand user paths
        self.cache_dir = self.cache_dir.expanduser()
        self.hf_cache_dir = self.hf_cache_dir.expanduser()

        # Validate numeric ranges
        if self.max_size_gb <= 0:
            raise ValueError(f"max_size_gb must be positive, got {self.max_size_gb}")
        if self.max_models <= 0:
            raise ValueError(f"max_models must be positive, got {self.max_models}")
        if self.ttl_hours <= 0:
            raise ValueError(f"ttl_hours must be positive, got {self.ttl_hours}")

        # Validate eviction policy
        if self.eviction_policy not in ("lru", "lfu", "fifo"):
            raise ValueError(f"Invalid eviction_policy: {self.eviction_policy}")

        # Ensure nested configs are correct types
        # Note: These checks are runtime safeguards for dict[str, Any]-based initialization
        # from external sources (e.g., YAML/JSON deserialization)
        if isinstance(self.warm_cache, dict):
            self.warm_cache = WarmCacheConfig(**self.warm_cache)

        elif not isinstance(self.warm_cache, WarmCacheConfig):
            raise TypeError(
                f"warm_cache must be WarmCacheConfig or dict[str, Any], got {type(self.warm_cache)}"
            )

        if isinstance(self.metrics, dict):
            self.metrics = MetricsConfig(**self.metrics)

        elif not isinstance(self.metrics, MetricsConfig):
            raise TypeError(
                f"metrics must be MetricsConfig or dict[str, Any], got {type(self.metrics)}"
            )

        # Create cache directory if it doesn't exist
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Model cache directory: {self.cache_dir}")
        except Exception as e:
            logger.warning(f"Failed to create cache directory {self.cache_dir}: {e}")

    @classmethod
    def from_env(cls) -> "ModelCacheConfig":
        """Load configuration from environment variables with defaults.

        Environment variable precedence:
        1. KAGAMI_MODEL_CACHE_* (new, preferred)
        2. MODEL_CACHE_PATH (legacy)
        3. XDG_CACHE_HOME (standard)
        4. HF_HOME (Hugging Face)

        Returns:
            ModelCacheConfig instance with environment-based configuration
        """
        # Determine cache directory with priority:
        # 1. KAGAMI_MODEL_CACHE_DIR
        # 2. MODEL_CACHE_PATH (legacy, deprecated)
        # 3. XDG_CACHE_HOME/kagami/models
        # 4. ~/.cache/kagami/models
        cache_dir_str = os.getenv("KAGAMI_MODEL_CACHE_DIR")
        if not cache_dir_str:
            legacy_path = os.getenv("MODEL_CACHE_PATH")
            if legacy_path:
                import warnings

                warnings.warn(
                    "MODEL_CACHE_PATH is deprecated. Use KAGAMI_MODEL_CACHE_DIR instead.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                cache_dir_str = legacy_path
        if not cache_dir_str:
            xdg_cache = os.getenv("XDG_CACHE_HOME")
            if xdg_cache:
                cache_dir_str = f"{xdg_cache}/kagami/models"
            else:
                cache_dir_str = "~/.cache/kagami/models"

        # Expand environment variables in path
        cache_dir_str = os.path.expandvars(cache_dir_str)
        cache_dir = Path(cache_dir_str).expanduser()

        # Determine HF cache directory
        hf_home = os.getenv("HF_HOME")
        if hf_home:
            hf_cache_dir = Path(hf_home) / "hub"
        else:
            hf_cache_dir = Path.home() / ".cache" / "huggingface" / "hub"

        # Parse numeric settings
        try:
            max_size_gb = float(os.getenv("KAGAMI_MODEL_CACHE_MAX_SIZE_GB", "100.0"))
        except ValueError:
            logger.warning("Invalid KAGAMI_MODEL_CACHE_MAX_SIZE_GB, using default 100.0")
            max_size_gb = 100.0

        try:
            max_models = int(os.getenv("KAGAMI_MODEL_CACHE_MAX_MODELS", "10"))
        except ValueError:
            logger.warning("Invalid KAGAMI_MODEL_CACHE_MAX_MODELS, using default 10")
            max_models = 10

        # Parse boolean settings
        warm_cache_enabled = os.getenv("KAGAMI_MODEL_CACHE_WARM", "true").lower() in (
            "true",
            "1",
            "yes",
            "on",
        )

        scan_hf_on_startup = os.getenv("KAGAMI_MODEL_CACHE_SCAN_HF", "true").lower() in (
            "true",
            "1",
            "yes",
            "on",
        )

        metrics_enabled = os.getenv("KAGAMI_MODEL_CACHE_METRICS", "true").lower() in (
            "true",
            "1",
            "yes",
            "on",
        )

        verify_checksums = os.getenv("KAGAMI_MODEL_CACHE_VERIFY_CHECKSUMS", "true").lower() in (
            "true",
            "1",
            "yes",
            "on",
        )

        atomic_writes = os.getenv("KAGAMI_MODEL_CACHE_ATOMIC_WRITES", "true").lower() in (
            "true",
            "1",
            "yes",
            "on",
        )

        # Create configuration
        return cls(
            cache_dir=cache_dir,
            max_size_gb=max_size_gb,
            max_models=max_models,
            eviction_policy="lru",  # Default, can be overridden by YAML
            ttl_hours=168,  # 1 week
            hf_cache_dir=hf_cache_dir,
            scan_hf_on_startup=scan_hf_on_startup,
            warm_cache=WarmCacheConfig(enabled=warm_cache_enabled),
            metrics=MetricsConfig(enabled=metrics_enabled),
            verify_checksums=verify_checksums,
            atomic_writes=atomic_writes,
        )

    @classmethod
    def from_yaml(cls, path: Path) -> "ModelCacheConfig":
        """Load configuration from YAML file.

        Environment variables in the YAML file are expanded using the format:
        ${VAR_NAME} or ${VAR_NAME:-default_value}

        Args:
            path: Path to YAML configuration file

        Returns:
            ModelCacheConfig instance from YAML

        Raises:
            FileNotFoundError: If YAML file doesn't exist
            ValueError: If YAML is invalid
        """
        import re

        try:
            import yaml
        except ImportError as e:
            raise ImportError(
                "PyYAML is required for YAML configuration. Install with: pip install pyyaml"
            ) from e

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        # Read YAML file
        with open(path) as f:
            content = f.read()

        # Expand environment variables in format ${VAR} or ${VAR:-default}
        def expand_env_var(match: re.Match[str]) -> str:
            var_name = match.group(1)
            default_value = ""

            # Handle ${VAR:-default} syntax
            if ":-" in var_name:
                var_name, default_value = var_name.split(":-", 1)

            return os.getenv(var_name, default_value)

        content = re.sub(r"\$\{([^}]+)\}", expand_env_var, content)

        # Parse YAML
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {path}: {e}") from e

        if not data:
            raise ValueError(f"Empty YAML file: {path}")

        # Extract model_cache section if present
        if "model_cache" in data:
            config_data = data["model_cache"]
        else:
            config_data = data

        # Convert paths to Path objects
        if "cache_dir" in config_data:
            config_data["cache_dir"] = Path(config_data["cache_dir"]).expanduser()
        else:
            # Use environment-based default
            config_data["cache_dir"] = cls.from_env().cache_dir

        if "hf_cache_dir" in config_data:
            config_data["hf_cache_dir"] = Path(config_data["hf_cache_dir"]).expanduser()

        # Parse nested configurations
        if "warm_cache" in config_data:
            warm_data = config_data["warm_cache"]
            if "models" in warm_data:
                warm_data["models"] = [
                    WarmCacheModel(**m) if isinstance(m, dict) else m for m in warm_data["models"]
                ]
            config_data["warm_cache"] = WarmCacheConfig(**warm_data)

        if "metrics" in config_data:
            config_data["metrics"] = MetricsConfig(**config_data["metrics"])

        try:
            return cls(**config_data)
        except TypeError as e:
            raise ValueError(f"Invalid configuration in {path}: {e}") from e

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary for serialization.

        Returns:
            Dictionary representation of configuration
        """
        return {
            "cache_dir": str(self.cache_dir),
            "max_size_gb": self.max_size_gb,
            "max_models": self.max_models,
            "eviction_policy": self.eviction_policy,
            "ttl_hours": self.ttl_hours,
            "hf_cache_dir": str(self.hf_cache_dir),
            "scan_hf_on_startup": self.scan_hf_on_startup,
            "warm_cache": {
                "enabled": self.warm_cache.enabled,
                "models": [
                    {
                        "model_id": m.model_id,
                        "priority": m.priority,
                        "config": m.config,
                    }
                    for m in self.warm_cache.models
                ],
            },
            "metrics": {
                "enabled": self.metrics.enabled,
                "prometheus_namespace": self.metrics.prometheus_namespace,
            },
            "verify_checksums": self.verify_checksums,
            "atomic_writes": self.atomic_writes,
        }


def get_default_config() -> ModelCacheConfig:
    """Get default model cache configuration.

    Loads configuration with this priority:
    1. config/model_cache.yaml (if exists)
    2. Environment variables
    3. Built-in defaults

    Returns:
        Default ModelCacheConfig instance
    """
    # Check if caching is explicitly disabled
    if os.getenv("KAGAMI_MODEL_CACHE_ENABLED", "1").lower() in ("0", "false", "no", "off"):
        logger.info("Model cache disabled via KAGAMI_MODEL_CACHE_ENABLED")
        # Return minimal config with caching effectively disabled
        return ModelCacheConfig(
            cache_dir=Path("/tmp/kagami_models_disabled"),
            max_size_gb=0.1,
            max_models=1,
        )

    # Try to load from YAML config
    from kagami.core.utils.paths import get_project_root

    try:
        project_root = get_project_root()
        config_path = project_root / "config" / "model_cache.yaml"
        if config_path.exists():
            logger.info(f"Loading model cache config from {config_path}")
            return ModelCacheConfig.from_yaml(config_path)
    except Exception as e:
        logger.warning(f"Failed to load model cache config from YAML: {e}")

    # Fall back to environment variables
    logger.info("Using environment-based model cache config")
    return ModelCacheConfig.from_env()
