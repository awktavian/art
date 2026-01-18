"""Plugin Hooks - Extension points for plugin integration.

Hooks provide integration points for plugins to extend Kagami's behavior:

1. Colony Hooks:
   - pre_action: Before colony processes task
   - post_action: After colony completes task
   - colony_registration: When custom colony is registered

2. Safety Hooks:
   - pre_safety_check: Before CBF safety evaluation
   - post_safety_check: After CBF safety evaluation
   - safety_filter: Custom safety filter implementation

3. Forge Hooks:
   - pre_generation: Before Forge generates content
   - post_generation: After Forge generates content
   - module_registration: When custom module is registered

4. Receipt Hooks:
   - pre_emission: Before receipt is emitted
   - post_emission: After receipt is emitted
   - receipt_processing: Custom receipt processor

Architecture:
    HookRegistry
    ├── register_hook() - Register hook handler
    ├── unregister_hook() - Remove hook handler
    ├── call_hook() - Execute all handlers for a hook
    └── clear_hooks() - Remove all handlers

Created: December 28, 2025
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HookType(Enum):
    """Hook types for plugin extension points."""

    # Colony hooks
    PRE_ACTION = "colony.pre_action"
    POST_ACTION = "colony.post_action"
    COLONY_REGISTRATION = "colony.registration"

    # Safety hooks
    PRE_SAFETY_CHECK = "safety.pre_check"
    POST_SAFETY_CHECK = "safety.post_check"
    SAFETY_FILTER = "safety.filter"

    # Forge hooks
    PRE_GENERATION = "forge.pre_generation"
    POST_GENERATION = "forge.post_generation"
    MODULE_REGISTRATION = "forge.module_registration"

    # Receipt hooks
    PRE_EMISSION = "receipt.pre_emission"
    POST_EMISSION = "receipt.post_emission"
    RECEIPT_PROCESSING = "receipt.processing"

    # World model hooks
    PRE_PREDICTION = "world_model.pre_prediction"
    POST_PREDICTION = "world_model.post_prediction"

    # Routing hooks
    PRE_ROUTING = "routing.pre_routing"
    POST_ROUTING = "routing.post_routing"


@dataclass
class HookContext:
    """Context passed to hook handlers."""

    hook_type: HookType
    data: dict[str, Any]
    plugin_id: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        """Get data value with default."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set data value."""
        self.data[key] = value


# Hook handler type: (context) -> modified_context or None
HookHandler = Callable[[HookContext], HookContext | None]


class HookRegistry:
    """Central registry for plugin hooks.

    Example:
        ```python
        from kagami.plugins.hooks import get_hook_registry, HookType, HookContext

        registry = get_hook_registry()

        # Register a hook handler
        def my_pre_action_handler(ctx: HookContext) -> HookContext:
            print(f"Task: {ctx.get('task')}")
            ctx.set('custom_data', 'my_value')
            return ctx

        registry.register_hook(
            HookType.PRE_ACTION,
            my_pre_action_handler,
            plugin_id="my_plugin"
        )

        # Call hooks (done by Kagami internally)
        context = HookContext(
            hook_type=HookType.PRE_ACTION,
            data={'task': 'build feature'}
        )
        result = registry.call_hook(HookType.PRE_ACTION, context)
        print(result.get('custom_data'))  # 'my_value'
        ```
    """

    def __init__(self):
        """Initialize hook registry."""
        self._handlers: dict[HookType, list[tuple[str | None, HookHandler]]] = defaultdict(
            list[Any]
        )

    def register_hook(
        self,
        hook_type: HookType,
        handler: HookHandler,
        plugin_id: str | None = None,
        priority: int = 100,
    ) -> None:
        """Register a hook handler.

        Args:
            hook_type: Type of hook
            handler: Handler function
            plugin_id: Optional plugin identifier
            priority: Handler priority (lower = earlier, default 100)
        """
        # Insert handler sorted by priority
        handlers = self._handlers[hook_type]
        handlers.append((plugin_id, handler))
        # Sort by priority (not implemented yet, all handlers execute in registration order)

        logger.debug(
            f"Registered hook handler: {hook_type.value} "
            f"(plugin: {plugin_id or 'core'}, priority: {priority})"
        )

    def unregister_hook(
        self,
        hook_type: HookType,
        plugin_id: str,
    ) -> int:
        """Unregister all handlers for a plugin.

        Args:
            hook_type: Type of hook
            plugin_id: Plugin identifier

        Returns:
            Number of handlers removed
        """
        handlers = self._handlers[hook_type]
        original_count = len(handlers)

        # Remove handlers matching plugin_id
        self._handlers[hook_type] = [
            (pid, handler) for pid, handler in handlers if pid != plugin_id
        ]

        removed = original_count - len(self._handlers[hook_type])
        if removed > 0:
            logger.debug(
                f"Unregistered {removed} handlers for {hook_type.value} (plugin: {plugin_id})"
            )

        return removed

    def call_hook(
        self,
        hook_type: HookType,
        context: HookContext,
    ) -> HookContext:
        """Call all handlers for a hook.

        Handlers are called in registration order. Each handler receives the
        context from the previous handler (allowing modification).

        If a handler returns None, the hook chain continues with the original context.
        If a handler raises an exception, it's logged but doesn't stop the chain.

        Args:
            hook_type: Type of hook
            context: Hook context

        Returns:
            Modified context after all handlers
        """
        handlers = self._handlers.get(hook_type, [])
        if not handlers:
            return context

        current_context = context

        for plugin_id, handler in handlers:
            try:
                result = handler(current_context)
                if result is not None:
                    current_context = result

            except Exception as e:
                logger.error(
                    f"Hook handler failed: {hook_type.value} "
                    f"(plugin: {plugin_id or 'unknown'}): {e}",
                    exc_info=True,
                )
                # Continue with other handlers

        return current_context

    def clear_hooks(self, hook_type: HookType | None = None) -> None:
        """Clear all handlers for a hook type (or all hooks).

        Args:
            hook_type: Optional hook type (clears all if None)
        """
        if hook_type is None:
            self._handlers.clear()
            logger.debug("Cleared all hook handlers")
        else:
            self._handlers[hook_type] = []
            logger.debug(f"Cleared handlers for {hook_type.value}")

    def list_hooks(self, hook_type: HookType | None = None) -> dict[str, list[str | None]]:
        """List registered hooks.

        Args:
            hook_type: Optional hook type filter

        Returns:
            Dict mapping hook type names to list[Any] of plugin IDs
        """
        if hook_type is None:
            # All hooks
            result = {}
            for htype, handlers in self._handlers.items():
                result[htype.value] = [plugin_id for plugin_id, _ in handlers]
            return result
        else:
            # Specific hook
            handlers = self._handlers.get(hook_type, [])
            return {hook_type.value: [plugin_id for plugin_id, _ in handlers]}


# Singleton instance
_HOOK_REGISTRY: HookRegistry | None = None


def get_hook_registry() -> HookRegistry:
    """Get global hook registry instance."""
    global _HOOK_REGISTRY
    if _HOOK_REGISTRY is None:
        _HOOK_REGISTRY = HookRegistry()
    return _HOOK_REGISTRY


def reset_hook_registry() -> None:
    """Reset global hook registry (for testing)."""
    global _HOOK_REGISTRY
    if _HOOK_REGISTRY is not None:
        _HOOK_REGISTRY.clear_hooks()
    _HOOK_REGISTRY = None


# Convenience functions for common hook operations


def register_colony_hook(
    hook_type: HookType,
    handler: HookHandler,
    plugin_id: str | None = None,
) -> None:
    """Register a colony hook.

    Args:
        hook_type: Colony hook type
        handler: Hook handler
        plugin_id: Optional plugin ID
    """
    if hook_type not in (
        HookType.PRE_ACTION,
        HookType.POST_ACTION,
        HookType.COLONY_REGISTRATION,
    ):
        raise ValueError(f"Not a colony hook: {hook_type}")

    registry = get_hook_registry()
    registry.register_hook(hook_type, handler, plugin_id)


def register_safety_hook(
    hook_type: HookType,
    handler: HookHandler,
    plugin_id: str | None = None,
) -> None:
    """Register a safety hook.

    Args:
        hook_type: Safety hook type
        handler: Hook handler
        plugin_id: Optional plugin ID
    """
    if hook_type not in (
        HookType.PRE_SAFETY_CHECK,
        HookType.POST_SAFETY_CHECK,
        HookType.SAFETY_FILTER,
    ):
        raise ValueError(f"Not a safety hook: {hook_type}")

    registry = get_hook_registry()
    registry.register_hook(hook_type, handler, plugin_id)


def register_forge_hook(
    hook_type: HookType,
    handler: HookHandler,
    plugin_id: str | None = None,
) -> None:
    """Register a forge hook.

    Args:
        hook_type: Forge hook type
        handler: Hook handler
        plugin_id: Optional plugin ID
    """
    if hook_type not in (
        HookType.PRE_GENERATION,
        HookType.POST_GENERATION,
        HookType.MODULE_REGISTRATION,
    ):
        raise ValueError(f"Not a forge hook: {hook_type}")

    registry = get_hook_registry()
    registry.register_hook(hook_type, handler, plugin_id)


def register_receipt_hook(
    hook_type: HookType,
    handler: HookHandler,
    plugin_id: str | None = None,
) -> None:
    """Register a receipt hook.

    Args:
        hook_type: Receipt hook type
        handler: Hook handler
        plugin_id: Optional plugin ID
    """
    if hook_type not in (
        HookType.PRE_EMISSION,
        HookType.POST_EMISSION,
        HookType.RECEIPT_PROCESSING,
    ):
        raise ValueError(f"Not a receipt hook: {hook_type}")

    registry = get_hook_registry()
    registry.register_hook(hook_type, handler, plugin_id)


__all__ = [
    "HookContext",
    "HookHandler",
    "HookRegistry",
    "HookType",
    "get_hook_registry",
    "register_colony_hook",
    "register_forge_hook",
    "register_receipt_hook",
    "register_safety_hook",
    "reset_hook_registry",
]
