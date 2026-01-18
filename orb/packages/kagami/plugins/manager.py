"""Plugin Manager - Discovery, loading, and lifecycle management.

The Plugin Manager handles:
1. Plugin discovery via entry points and direct registration
2. Dependency resolution and loading order
3. Version compatibility checking
4. Plugin lifecycle (init, start, stop, cleanup)
5. Error handling (fail-fast on plugin errors)

Architecture:
    PluginManager
    ├── discover() - Find plugins via entry points
    ├── register() - Direct plugin registration
    ├── load() - Load plugin with dependencies
    ├── unload() - Unload plugin gracefully
    └── resolve_dependencies() - Topological sort

Entry Point Format:
    [kagami.plugins]
    my_plugin = my_package.plugin:MyPlugin

Created: December 28, 2025
"""

from __future__ import annotations

import importlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

try:
    from importlib.metadata import entry_points
except ImportError:
    from importlib_metadata import entry_points

from packaging.version import InvalidVersion, Version

from kagami.plugins.base import BasePlugin, PluginMetadata, PluginState

logger = logging.getLogger(__name__)


@dataclass
class PluginLoadResult:
    """Result of plugin loading operation."""

    plugin_id: str
    success: bool
    error: str | None = None
    skipped_reason: str | None = None
    dependencies_loaded: list[str] = field(default_factory=list[Any])


class PluginManager:
    """Central plugin manager for discovery, loading, and lifecycle.

    Example:
        ```python
        manager = PluginManager()

        # Discover plugins from entry points
        discovered = manager.discover()
        print(f"Found {len(discovered)} plugins")

        # Load all discovered plugins
        results = manager.load_all()
        for result in results:
            if result.success:
                print(f"Loaded: {result.plugin_id}")

        # Access loaded plugins
        plugin = manager.get_plugin("my_plugin")
        if plugin:
            print(f"Plugin version: {plugin.metadata.version}")

        # Unload all plugins
        manager.unload_all()
        ```
    """

    def __init__(self, kagami_version: str = "0.1.0"):
        """Initialize plugin manager.

        Args:
            kagami_version: Current Kagami version for compatibility checks
        """
        self.kagami_version = kagami_version
        self._plugins: dict[str, BasePlugin] = {}
        self._metadata: dict[str, PluginMetadata] = {}
        self._dependency_graph: dict[str, set[str]] = defaultdict(set[Any])

    def discover(self, group: str = "kagami.plugins") -> list[PluginMetadata]:
        """Discover plugins via entry points.

        Args:
            group: Entry point group name

        Returns:
            List of discovered plugin metadata
        """
        discovered = []

        try:
            eps = entry_points()
            # Handle both dict[str, Any]-style (Python 3.9) and SelectableGroups (Python 3.10+)
            if hasattr(eps, "select"):
                plugin_entries = eps.select(group=group)
            else:
                plugin_entries = eps.get(group, [])

            for ep in plugin_entries:
                try:
                    # Load plugin class
                    plugin_class = ep.load()

                    # Validate it's a BasePlugin subclass
                    if not issubclass(plugin_class, BasePlugin):
                        logger.warning(
                            f"Entry point {ep.name} does not point to BasePlugin subclass"
                        )
                        continue

                    # Get metadata from class
                    metadata = plugin_class.get_metadata()
                    self._metadata[metadata.plugin_id] = metadata
                    discovered.append(metadata)

                    logger.info(f"Discovered plugin: {metadata.plugin_id} v{metadata.version}")

                except Exception as e:
                    logger.error(f"Failed to load entry point {ep.name}: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Failed to discover plugins: {e}", exc_info=True)

        return discovered

    def register(self, plugin: BasePlugin) -> None:
        """Register a plugin directly (without entry points).

        Args:
            plugin: Plugin instance to register
        """
        metadata = plugin.get_metadata()
        self._metadata[metadata.plugin_id] = metadata
        self._plugins[metadata.plugin_id] = plugin
        plugin._state = PluginState.REGISTERED

        logger.info(f"Registered plugin: {metadata.plugin_id} v{metadata.version}")

    def load(self, plugin_id: str, force: bool = False) -> PluginLoadResult:
        """Load a plugin with dependency resolution.

        Args:
            plugin_id: Plugin identifier
            force: Force load even if already loaded

        Returns:
            Plugin load result
        """
        # Check if already loaded
        if plugin_id in self._plugins and not force:
            plugin = self._plugins[plugin_id]
            if plugin._state in (PluginState.INITIALIZED, PluginState.STARTED):
                return PluginLoadResult(
                    plugin_id=plugin_id,
                    success=True,
                    skipped_reason="already_loaded",
                )

        # Get metadata
        metadata = self._metadata.get(plugin_id)
        if not metadata:
            return PluginLoadResult(
                plugin_id=plugin_id,
                success=False,
                error="Plugin not discovered or registered",
            )

        # Check Kagami version compatibility
        if not self._check_compatibility(metadata):
            return PluginLoadResult(
                plugin_id=plugin_id,
                success=False,
                error=f"Incompatible with Kagami {self.kagami_version} "
                f"(requires {metadata.kagami_version_min}-{metadata.kagami_version_max})",
            )

        # Load dependencies first
        dependencies_loaded = []
        for dep_id in metadata.dependencies:
            dep_result = self.load(dep_id)
            if not dep_result.success:
                return PluginLoadResult(
                    plugin_id=plugin_id,
                    success=False,
                    error=f"Failed to load dependency: {dep_id} ({dep_result.error})",
                )
            dependencies_loaded.append(dep_id)

        # Instantiate plugin if not registered
        if plugin_id not in self._plugins:
            try:
                # Dynamically import and instantiate
                module_path, class_name = metadata.entry_point.rsplit(":", 1)
                module = importlib.import_module(module_path)
                plugin_class = getattr(module, class_name)
                plugin = plugin_class()
                self._plugins[plugin_id] = plugin

            except Exception as e:
                return PluginLoadResult(
                    plugin_id=plugin_id,
                    success=False,
                    error=f"Failed to instantiate plugin: {e}",
                )

        # Initialize plugin
        plugin = self._plugins[plugin_id]
        try:
            plugin.on_init()
            plugin._state = PluginState.INITIALIZED

            logger.info(f"Loaded plugin: {plugin_id} v{metadata.version}")

            return PluginLoadResult(
                plugin_id=plugin_id,
                success=True,
                dependencies_loaded=dependencies_loaded,
            )

        except Exception as e:
            logger.error(f"Failed to initialize plugin {plugin_id}: {e}", exc_info=True)
            plugin._state = PluginState.ERROR
            return PluginLoadResult(
                plugin_id=plugin_id,
                success=False,
                error=f"Initialization failed: {e}",
            )

    def load_all(self, order: list[str] | None = None) -> list[PluginLoadResult]:
        """Load all discovered plugins.

        Args:
            order: Optional load order (defaults to dependency-resolved order)

        Returns:
            List of load results
        """
        if order is None:
            # Resolve dependencies and create load order
            order = self.resolve_dependencies()

        results = []
        for plugin_id in order:
            result = self.load(plugin_id)
            results.append(result)

        return results

    def unload(self, plugin_id: str) -> bool:
        """Unload a plugin gracefully.

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if unloaded successfully
        """
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            logger.warning(f"Plugin {plugin_id} not loaded")
            return False

        try:
            # Stop if started
            if plugin._state == PluginState.STARTED:
                plugin.on_stop()

            # Cleanup
            plugin.on_cleanup()
            plugin._state = PluginState.UNLOADED

            logger.info(f"Unloaded plugin: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_id}: {e}", exc_info=True)
            plugin._state = PluginState.ERROR
            return False

    def unload_all(self) -> None:
        """Unload all plugins in reverse dependency order."""
        # Get reverse load order
        order = list(reversed(self.resolve_dependencies()))

        for plugin_id in order:
            self.unload(plugin_id)

    def start(self, plugin_id: str) -> bool:
        """Start a plugin.

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if started successfully
        """
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            logger.warning(f"Plugin {plugin_id} not loaded")
            return False

        if plugin._state != PluginState.INITIALIZED:
            logger.warning(f"Plugin {plugin_id} not initialized (state: {plugin._state})")
            return False

        try:
            plugin.on_start()
            plugin._state = PluginState.STARTED
            logger.info(f"Started plugin: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start plugin {plugin_id}: {e}", exc_info=True)
            plugin._state = PluginState.ERROR
            return False

    def stop(self, plugin_id: str) -> bool:
        """Stop a plugin.

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if stopped successfully
        """
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            logger.warning(f"Plugin {plugin_id} not loaded")
            return False

        if plugin._state != PluginState.STARTED:
            logger.warning(f"Plugin {plugin_id} not started (state: {plugin._state})")
            return False

        try:
            plugin.on_stop()
            plugin._state = PluginState.INITIALIZED
            logger.info(f"Stopped plugin: {plugin_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to stop plugin {plugin_id}: {e}", exc_info=True)
            plugin._state = PluginState.ERROR
            return False

    def get_plugin(self, plugin_id: str) -> BasePlugin | None:
        """Get loaded plugin by ID.

        Args:
            plugin_id: Plugin identifier

        Returns:
            Plugin instance or None
        """
        return self._plugins.get(plugin_id)

    def get_metadata(self, plugin_id: str) -> PluginMetadata | None:
        """Get plugin metadata.

        Args:
            plugin_id: Plugin identifier

        Returns:
            Plugin metadata or None
        """
        return self._metadata.get(plugin_id)

    def list_plugins(self) -> list[tuple[str, PluginState]]:
        """List all plugins and their states.

        Returns:
            List of (plugin_id, state) tuples
        """
        result = []
        for plugin_id, plugin in self._plugins.items():
            result.append((plugin_id, plugin._state))
        return result

    def resolve_dependencies(self) -> list[str]:
        """Resolve plugin load order using topological sort.

        Returns:
            Ordered list[Any] of plugin IDs (dependencies first)

        Raises:
            ValueError: If circular dependencies detected
        """
        # Build dependency graph
        graph: dict[str, set[str]] = defaultdict(set[Any])
        for plugin_id, metadata in self._metadata.items():
            graph[plugin_id] = set(metadata.dependencies)

        # Topological sort (Kahn's algorithm)
        in_degree = dict.fromkeys(graph, 0)
        for deps in graph.values():
            for dep in deps:
                in_degree[dep] = in_degree.get(dep, 0) + 1

        queue = [plugin_id for plugin_id, degree in in_degree.items() if degree == 0]
        order = []

        while queue:
            plugin_id = queue.pop(0)
            order.append(plugin_id)

            for neighbor in graph[plugin_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(order) != len(graph):
            raise ValueError("Circular dependency detected in plugins")

        return order

    def check_health(self, plugin_id: str) -> dict[str, Any]:
        """Check plugin health.

        Args:
            plugin_id: Plugin identifier

        Returns:
            Health check result
        """
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return {
                "plugin_id": plugin_id,
                "healthy": False,
                "error": "Plugin not loaded",
            }

        try:
            health = plugin.health_check()
            return {
                "plugin_id": plugin_id,
                "state": plugin._state.value,
                "healthy": health.healthy,
                "status": health.status,
                "details": health.details,
            }

        except Exception as e:
            return {
                "plugin_id": plugin_id,
                "healthy": False,
                "error": str(e),
            }

    def _check_compatibility(self, metadata: PluginMetadata) -> bool:
        """Check if plugin is compatible with current Kagami version.

        Args:
            metadata: Plugin metadata

        Returns:
            True if compatible
        """
        try:
            current = Version(self.kagami_version)
            min_version = Version(metadata.kagami_version_min)
            max_version = Version(metadata.kagami_version_max)

            return min_version <= current <= max_version

        except InvalidVersion:
            logger.warning(f"Invalid version format: {self.kagami_version}")
            return False


# Singleton instance
_PLUGIN_MANAGER: PluginManager | None = None


def get_plugin_manager() -> PluginManager:
    """Get global plugin manager instance."""
    global _PLUGIN_MANAGER
    if _PLUGIN_MANAGER is None:
        _PLUGIN_MANAGER = PluginManager()
    return _PLUGIN_MANAGER


def reset_plugin_manager() -> None:
    """Reset global plugin manager (for testing)."""
    global _PLUGIN_MANAGER
    if _PLUGIN_MANAGER is not None:
        _PLUGIN_MANAGER.unload_all()
    _PLUGIN_MANAGER = None


__all__ = [
    "PluginLoadResult",
    "PluginManager",
    "get_plugin_manager",
    "reset_plugin_manager",
]
