"""Plugin Registry - Central registry of plugin capabilities.

The Plugin Registry tracks what capabilities are available across all loaded plugins:

1. Capability Discovery:
   - Query plugins by capability (e.g., "custom_colony", "safety_filter")
   - List all available capabilities
   - Find plugins providing specific capabilities

2. Metadata Storage:
   - Plugin metadata cache
   - Capability index
   - Dependency graph

3. Query Interface:
   - get_plugins_by_capability()
   - get_plugin_capabilities()
   - has_capability()

Created: December 28, 2025
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from kagami.plugins.base import BasePlugin, PluginMetadata

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Central registry of plugin capabilities.

    Example:
        ```python
        from kagami.plugins.registry import get_plugin_registry

        registry = get_plugin_registry()

        # Query plugins by capability
        colony_plugins = registry.get_plugins_by_capability("custom_colony")
        for plugin_id in colony_plugins:
            plugin = registry.get_plugin(plugin_id)
            print(f"Colony plugin: {plugin.get_metadata().name}")

        # Check if capability exists
        if registry.has_capability("safety_filter"):
            print("Custom safety filters available")

        # List all capabilities
        capabilities = registry.list_capabilities()
        print(f"Available capabilities: {capabilities}")
        ```
    """

    def __init__(self):
        """Initialize plugin registry."""
        self._plugins: dict[str, BasePlugin] = {}
        self._metadata: dict[str, PluginMetadata] = {}
        self._capability_index: dict[str, set[str]] = defaultdict(set[Any])

    def register(self, plugin: BasePlugin) -> None:
        """Register a plugin and index its capabilities.

        Args:
            plugin: Plugin instance to register
        """
        metadata = plugin.get_metadata()
        plugin_id = metadata.plugin_id

        # Store plugin and metadata
        self._plugins[plugin_id] = plugin
        self._metadata[plugin_id] = metadata

        # Index capabilities
        for capability in metadata.capabilities:
            self._capability_index[capability].add(plugin_id)

        logger.info(
            f"Registered plugin: {plugin_id} (capabilities: {', '.join(metadata.capabilities)})"
        )

    def unregister(self, plugin_id: str) -> bool:
        """Unregister a plugin.

        Args:
            plugin_id: Plugin identifier

        Returns:
            True if unregistered successfully
        """
        if plugin_id not in self._plugins:
            return False

        metadata = self._metadata[plugin_id]

        # Remove from capability index
        for capability in metadata.capabilities:
            self._capability_index[capability].discard(plugin_id)

        # Remove plugin and metadata
        del self._plugins[plugin_id]
        del self._metadata[plugin_id]

        logger.info(f"Unregistered plugin: {plugin_id}")
        return True

    def get_plugin(self, plugin_id: str) -> BasePlugin | None:
        """Get plugin by ID.

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

    def get_plugins_by_capability(self, capability: str) -> list[str]:
        """Get all plugins providing a capability.

        Args:
            capability: Capability name (e.g., "custom_colony")

        Returns:
            List of plugin IDs
        """
        return list(self._capability_index.get(capability, set()))

    def get_plugin_capabilities(self, plugin_id: str) -> list[str]:
        """Get capabilities provided by a plugin.

        Args:
            plugin_id: Plugin identifier

        Returns:
            List of capability names
        """
        metadata = self._metadata.get(plugin_id)
        if not metadata:
            return []
        return metadata.capabilities

    def has_capability(self, capability: str) -> bool:
        """Check if any plugin provides a capability.

        Args:
            capability: Capability name

        Returns:
            True if at least one plugin provides this capability
        """
        return len(self._capability_index.get(capability, set())) > 0

    def list_capabilities(self) -> list[str]:
        """List all available capabilities.

        Returns:
            List of capability names
        """
        return list(self._capability_index.keys())

    def list_plugins(self) -> list[str]:
        """List all registered plugins.

        Returns:
            List of plugin IDs
        """
        return list(self._plugins.keys())

    def get_stats(self) -> dict[str, Any]:
        """Get registry statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "total_plugins": len(self._plugins),
            "total_capabilities": len(self._capability_index),
            "capabilities": {
                capability: len(plugins) for capability, plugins in self._capability_index.items()
            },
        }

    def clear(self) -> None:
        """Clear all registrations (for testing)."""
        self._plugins.clear()
        self._metadata.clear()
        self._capability_index.clear()


# Singleton instance
_PLUGIN_REGISTRY: PluginRegistry | None = None


def get_plugin_registry() -> PluginRegistry:
    """Get global plugin registry instance."""
    global _PLUGIN_REGISTRY
    if _PLUGIN_REGISTRY is None:
        _PLUGIN_REGISTRY = PluginRegistry()
    return _PLUGIN_REGISTRY


def reset_plugin_registry() -> None:
    """Reset global plugin registry (for testing)."""
    global _PLUGIN_REGISTRY
    if _PLUGIN_REGISTRY is not None:
        _PLUGIN_REGISTRY.clear()
    _PLUGIN_REGISTRY = None


__all__ = [
    "PluginRegistry",
    "get_plugin_registry",
    "reset_plugin_registry",
]
