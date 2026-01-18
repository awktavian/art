"""Base Plugin - Abstract base class for all Kagami plugins.

All plugins must inherit from BasePlugin and implement:
1. get_metadata() - Plugin identification and metadata
2. on_init() - Initialization hook
3. on_start() - Start hook (optional)
4. on_stop() - Stop hook (optional)
5. on_cleanup() - Cleanup hook
6. health_check() - Health monitoring

Plugin Lifecycle:
    DISCOVERED → REGISTERED → INITIALIZED → STARTED → STOPPED → UNLOADED
                                     ↓
                                   ERROR

Created: December 28, 2025
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginState(Enum):
    """Plugin lifecycle state."""

    DISCOVERED = "discovered"  # Found via entry point
    REGISTERED = "registered"  # Registered with manager
    INITIALIZED = "initialized"  # on_init() completed
    STARTED = "started"  # on_start() completed
    STOPPED = "stopped"  # on_stop() completed
    UNLOADED = "unloaded"  # on_cleanup() completed
    ERROR = "error"  # Error during lifecycle


@dataclass
class PluginMetadata:
    """Plugin metadata for discovery and compatibility."""

    plugin_id: str  # Unique identifier (e.g., "my_org.custom_colony")
    name: str  # Human-readable name
    version: str  # Semantic version (e.g., "1.0.0")
    description: str  # Brief description
    author: str  # Plugin author
    entry_point: str  # Import path (e.g., "my_package.plugin:MyPlugin")

    # Dependencies
    dependencies: list[str] = field(default_factory=list[Any])  # Plugin IDs

    # Compatibility
    kagami_version_min: str = "0.1.0"
    kagami_version_max: str = "999.0.0"

    # Capabilities
    capabilities: list[str] = field(default_factory=list[Any])

    # Additional metadata
    license: str = "MIT"
    homepage: str = ""
    tags: list[str] = field(default_factory=list[Any])


@dataclass
class HealthCheckResult:
    """Result of plugin health check."""

    healthy: bool
    status: str = "ok"  # ok, degraded, error
    details: dict[str, Any] = field(default_factory=dict[str, Any])


class BasePlugin(ABC):
    """Abstract base class for all Kagami plugins.

    Plugins extend Kagami's functionality by:
    - Adding custom colonies
    - Implementing custom safety filters
    - Creating custom Forge modules
    - Adding receipt processors
    - Extending the world model

    Example:
        ```python
        from kagami.plugins import BasePlugin, PluginMetadata

        class MyPlugin(BasePlugin):
            @classmethod
            def get_metadata(cls) -> PluginMetadata:
                return PluginMetadata(
                    plugin_id="my_org.my_plugin",
                    name="My Plugin",
                    version="1.0.0",
                    description="Custom colony for specialized tasks",
                    author="My Organization",
                    entry_point="my_package.plugin:MyPlugin",
                )

            def on_init(self) -> None:
                self.config = self.get_config()
                print(f"Initialized with config: {self.config}")

            def on_start(self) -> None:
                print("Plugin started")

            def on_stop(self) -> None:
                print("Plugin stopped")

            def on_cleanup(self) -> None:
                print("Plugin cleaned up")

            def health_check(self) -> HealthCheckResult:
                return HealthCheckResult(healthy=True, status="ok")
        ```
    """

    def __init__(self) -> None:
        """Initialize plugin base."""
        self._state = PluginState.DISCOVERED
        self._config: dict[str, Any] = {}

    @classmethod
    @abstractmethod
    def get_metadata(cls) -> PluginMetadata:
        """Get plugin metadata.

        Returns:
            Plugin metadata with identification and compatibility info
        """

    @abstractmethod
    def on_init(self) -> None:
        """Initialize plugin.

        Called once when plugin is loaded. Use this to:
        - Initialize internal state
        - Validate configuration
        - Setup resources (connections, caches, etc.)

        Raises:
            Exception: If initialization fails
        """

    def on_start(self) -> None:  # noqa: B027
        """Start plugin.

        Called when plugin should begin active operation. Use this to:
        - Start background tasks
        - Open connections
        - Begin processing

        Optional: Default implementation does nothing.
        """
        pass

    def on_stop(self) -> None:  # noqa: B027
        """Stop plugin.

        Called when plugin should stop active operation. Use this to:
        - Stop background tasks
        - Pause processing
        - Preserve state

        Optional: Default implementation does nothing.
        """
        pass

    @abstractmethod
    def on_cleanup(self) -> None:
        """Cleanup plugin resources.

        Called when plugin is unloaded. Use this to:
        - Close connections
        - Release resources
        - Persist state if needed

        Raises:
            Exception: If cleanup fails
        """

    def health_check(self) -> HealthCheckResult:
        """Check plugin health.

        Returns:
            Health check result

        Optional: Default returns healthy.
        """
        return HealthCheckResult(
            healthy=True,
            status="ok",
            details={"state": self._state.value},
        )

    def get_config(self) -> dict[str, Any]:
        """Get plugin configuration.

        Configuration is provided by the plugin manager at load time.

        Returns:
            Plugin configuration dictionary
        """
        return self._config

    def set_config(self, config: dict[str, Any]) -> None:
        """Set plugin configuration.

        Args:
            config: Configuration dictionary
        """
        self._config = config

    @property
    def state(self) -> PluginState:
        """Get current plugin state.

        Returns:
            Current lifecycle state
        """
        return self._state


__all__ = [
    "BasePlugin",
    "HealthCheckResult",
    "PluginMetadata",
    "PluginState",
]
