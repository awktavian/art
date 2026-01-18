"""Singleton Pattern Consolidation — Centralized Singleton Registry.

CONSOLIDATES: 20+ manual singleton patterns identified across the codebase
REDUCES: Thread-safety issues, code duplication, inconsistent initialization
PROVIDES: Unified singleton management with proper async support

Singletons register at module import time. Example usage:
    from kagami.core.tasks.background_task_manager import get_task_manager
    from kagami.core.services.enhanced_embedding_service import get_enhanced_embedding_service

This consolidation provides:
- Thread-safe initialization via SingletonRegistry
- Async-safe singleton support (with automatic initialize() call)
- Consistent reset capability for testing
- Proper memory management
- Centralized status/debugging via list_singletons()
- Decorator-based registration via singleton_factory / async_singleton_factory

Created: December 30, 2025
Updated: January 12, 2026 - Cleaned up deprecated code, kept essential registry
"""

from __future__ import annotations

import threading
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from kagami.core.utils.singleton import AsyncSingleton, get_or_create

T = TypeVar("T")

# =============================================================================
# GLOBAL SINGLETON REGISTRY
# =============================================================================


class SingletonRegistry:
    """Central registry for all singleton instances.

    Provides unified management, reset capability, and debugging support.
    """

    def __init__(self):
        self._instances: dict[str, Any] = {}
        self._async_instances: dict[str, AsyncSingleton[Any]] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._lock = threading.Lock()

    def register_sync(self, key: str, factory: Callable[[], T]) -> Callable[[], T]:
        """Register a synchronous singleton factory.

        Args:
            key: Unique key for the singleton
            factory: Factory function to create the instance

        Returns:
            Function to get the singleton instance
        """
        with self._lock:
            self._factories[key] = factory

        def get_instance() -> T:
            return get_or_create(key, factory, self._instances, self._lock)

        return get_instance

    def register_async(self, key: str, factory: Callable[[], T]) -> Callable[[], Awaitable[T]]:
        """Register an async singleton factory.

        Args:
            key: Unique key for the singleton
            factory: Factory function to create the instance

        Returns:
            Async function to get the singleton instance
        """
        with self._lock:
            self._factories[key] = factory
            if key not in self._async_instances:
                self._async_instances[key] = AsyncSingleton(factory)

        async def get_instance() -> T:
            return await self._async_instances[key].get()

        return get_instance

    def get_instance(self, key: str) -> Any | None:
        """Get a singleton instance by key (if it exists).

        Args:
            key: Singleton key

        Returns:
            Instance if it exists, None otherwise
        """
        # Check sync instances first
        if key in self._instances:
            return self._instances[key]

        # Check async instances
        if key in self._async_instances:
            async_singleton = self._async_instances[key]
            if async_singleton._instance is not None:
                return async_singleton._instance

        return None

    def reset(self, key: str | None = None) -> None:
        """Reset singleton instances.

        Args:
            key: Specific key to reset, or None to reset all
        """
        with self._lock:
            if key is None:
                # Reset all
                self._instances.clear()
                for async_singleton in self._async_instances.values():
                    async_singleton.reset()
            else:
                # Reset specific
                self._instances.pop(key, None)
                if key in self._async_instances:
                    self._async_instances[key].reset()

    def list_singletons(self) -> dict[str, dict[str, Any]]:
        """List all registered singletons with their status.

        Returns:
            Dictionary with singleton info
        """
        info = {}

        with self._lock:
            for key in self._factories:
                sync_instance = self._instances.get(key)
                async_instance = None
                if key in self._async_instances:
                    async_instance = self._async_instances[key]._instance

                info[key] = {
                    "sync_initialized": sync_instance is not None,
                    "async_initialized": async_instance is not None,
                    "factory": self._factories[key].__name__ if key in self._factories else None,
                }

        return info


# Global registry instance
_singleton_registry = SingletonRegistry()


# =============================================================================
# REGISTRY ACCESS
# =============================================================================


def get_singleton_registry() -> SingletonRegistry:
    """Get the global singleton registry for advanced operations."""
    return _singleton_registry


def reset_all_singletons() -> None:
    """Reset all singletons (primarily for testing)."""
    _singleton_registry.reset()


def get_singleton_status() -> dict[str, Any]:
    """Get status of all registered singletons."""
    return _singleton_registry.list_singletons()


# =============================================================================
# DECORATOR FUNCTIONS FOR EASY REGISTRATION
# =============================================================================


def singleton_factory(
    singleton_key: str, return_type: type, description: str, category: str = "general"
):
    """Decorator to register a function as a singleton factory.

    Args:
        singleton_key: Unique key for the singleton
        return_type: Type that the factory returns
        description: Description of the singleton
        category: Category for organization

    Example:
        @singleton_factory("my_service", MyService, "Service singleton")
        def get_my_service() -> MyService:
            return MyService()
    """

    def decorator(func: Callable[[], Any]) -> Callable[[], Any]:
        # Register with singleton registry
        return _singleton_registry.register_sync(singleton_key, func)

    return decorator


def async_singleton_factory(
    singleton_key: str, return_type: type, description: str, category: str = "general"
):
    """Decorator to register an async function as a singleton factory.

    Args:
        singleton_key: Unique key for the singleton
        return_type: Type that the factory returns
        description: Description of the singleton
        category: Category for organization
    """

    def decorator(func: Callable[[], Awaitable[Any]]) -> Callable[[], Awaitable[Any]]:
        # Register with async singleton registry
        return _singleton_registry.register_async(singleton_key, func)

    return decorator
