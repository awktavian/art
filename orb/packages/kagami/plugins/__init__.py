"""Kagami Plugin System - Extensibility framework for Kagami.

The plugin system provides a comprehensive architecture for extending Kagami's
functionality through plugins.

Core Components:
- PluginManager: Discovery, loading, and lifecycle management
- BasePlugin: Abstract base class for all plugins
- HookRegistry: Extension points for plugin integration
- PluginRegistry: Capability discovery and metadata storage

Plugin Types:
1. Colony Plugins: Custom agent colonies
2. Safety Plugins: Custom safety filters
3. Forge Plugins: Custom content generation modules
4. Receipt Plugins: Custom receipt processors

Quick Start:
    ```python
    from kagami.plugins import (
        get_plugin_manager,
        BasePlugin,
        PluginMetadata,
    )

    # Create a plugin
    class MyPlugin(BasePlugin):
        @classmethod
        def get_metadata(cls):
            return PluginMetadata(
                plugin_id="my_org.my_plugin",
                name="My Plugin",
                version="1.0.0",
                description="My custom plugin",
                author="My Organization",
                entry_point="my_package:MyPlugin",
            )

        def on_init(self):
            print("Plugin initialized")

        def on_cleanup(self):
            print("Plugin cleaned up")

    # Load plugin
    manager = get_plugin_manager()
    manager.register(MyPlugin())
    manager.load("my_org.my_plugin")
    ```

Entry Points:
    Plugins can be discovered automatically via entry points:

    ```toml
    [project.entry-points."kagami.plugins"]
    my_plugin = "my_package.plugin:MyPlugin"
    ```

Examples:
    See `kagami/plugins/examples/` for complete examples:
    - custom_colony: Custom agent colony
    - custom_safety: Custom safety filter
    - custom_forge: Custom Forge module

Created: December 28, 2025
"""

from kagami.plugins.base import (
    BasePlugin,
    HealthCheckResult,
    PluginMetadata,
    PluginState,
)
from kagami.plugins.hooks import (
    HookContext,
    HookHandler,
    HookRegistry,
    HookType,
    get_hook_registry,
    register_colony_hook,
    register_forge_hook,
    register_receipt_hook,
    register_safety_hook,
    reset_hook_registry,
)
from kagami.plugins.manager import (
    PluginLoadResult,
    PluginManager,
    get_plugin_manager,
    reset_plugin_manager,
)
from kagami.plugins.registry import (
    PluginRegistry,
    get_plugin_registry,
    reset_plugin_registry,
)

__version__ = "1.0.0"

__all__ = [
    # Base
    "BasePlugin",
    "HealthCheckResult",
    "HookContext",
    "HookHandler",
    "HookRegistry",
    # Hooks
    "HookType",
    "PluginLoadResult",
    # Manager
    "PluginManager",
    "PluginMetadata",
    # Registry
    "PluginRegistry",
    "PluginState",
    "get_hook_registry",
    "get_plugin_manager",
    "get_plugin_registry",
    "register_colony_hook",
    "register_forge_hook",
    "register_receipt_hook",
    "register_safety_hook",
    "reset_hook_registry",
    # Reset functions
    "reset_plugin_manager",
    "reset_plugin_registry",
]
