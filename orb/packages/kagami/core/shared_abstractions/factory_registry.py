"""Factory Registry — Central Factory Discovery (451+ Factory Functions).

CONSOLIDATES: Factory function patterns across the codebase
REDUCES: Factory duplication and scattered factory management
PROVIDES: Central registry for all factory functions

This enables dynamic factory discovery and consistent factory patterns
across all Kagami services and components.

Created: December 30, 2025
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class FactoryInfo:
    """Information about a registered factory function."""

    factory_id: str
    factory_function: Callable[..., T]
    return_type: type
    description: str
    category: str = "general"
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    singleton: bool = False
    async_factory: bool = False


# Type alias for factory functions
FactoryFunction = Callable[..., Any]


class FactoryRegistry:
    """Central registry for factory functions across the Kagami system."""

    def __init__(self):
        self._factories: dict[str, FactoryInfo] = {}
        self._categories: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def register_factory(
        self,
        factory_id: str,
        factory_function: FactoryFunction,
        return_type: type,
        description: str,
        category: str = "general",
        dependencies: list[str] | None = None,
        tags: list[str] | None = None,
        singleton: bool = False,
        async_factory: bool = False,
    ) -> None:
        """Register a factory function.

        Args:
            factory_id: Unique identifier for the factory
            factory_function: The factory function
            return_type: Type returned by the factory
            description: Description of what the factory creates
            category: Category for organization
            dependencies: List of dependency factory IDs
            tags: Tags for discovery
            singleton: Whether factory creates singletons
            async_factory: Whether factory function is async
        """
        with self._lock:
            factory_info = FactoryInfo(
                factory_id=factory_id,
                factory_function=factory_function,
                return_type=return_type,
                description=description,
                category=category,
                dependencies=dependencies or [],
                tags=tags or [],
                singleton=singleton,
                async_factory=async_factory,
            )

            self._factories[factory_id] = factory_info

            # Update category index
            if category not in self._categories:
                self._categories[category] = []
            if factory_id not in self._categories[category]:
                self._categories[category].append(factory_id)

            logger.debug(f"Registered factory: {factory_id} ({category})")

    def unregister_factory(self, factory_id: str) -> bool:
        """Unregister a factory function.

        Args:
            factory_id: Factory ID to unregister

        Returns:
            True if factory was found and removed
        """
        with self._lock:
            if factory_id in self._factories:
                factory_info = self._factories.pop(factory_id)

                # Remove from category index
                category = factory_info.category
                if category in self._categories:
                    if factory_id in self._categories[category]:
                        self._categories[category].remove(factory_id)

                logger.debug(f"Unregistered factory: {factory_id}")
                return True

            return False

    def get_factory(self, factory_id: str) -> FactoryInfo | None:
        """Get factory information by ID.

        Args:
            factory_id: Factory ID to look up

        Returns:
            FactoryInfo if found, None otherwise
        """
        return self._factories.get(factory_id)

    def create_instance(self, factory_id: str, *args, **kwargs) -> Any:
        """Create an instance using a registered factory.

        Args:
            factory_id: Factory ID to use
            *args: Arguments to pass to factory
            **kwargs: Keyword arguments to pass to factory

        Returns:
            Created instance

        Raises:
            ValueError: If factory not found
            Exception: If factory execution fails
        """
        factory_info = self.get_factory(factory_id)
        if not factory_info:
            raise ValueError(f"Factory not found: {factory_id}")

        try:
            return factory_info.factory_function(*args, **kwargs)
        except Exception as e:
            logger.error(f"Factory {factory_id} failed: {e}")
            raise

    async def create_instance_async(self, factory_id: str, *args, **kwargs) -> Any:
        """Create an instance using an async factory.

        Args:
            factory_id: Factory ID to use
            *args: Arguments to pass to factory
            **kwargs: Keyword arguments to pass to factory

        Returns:
            Created instance

        Raises:
            ValueError: If factory not found or not async
            Exception: If factory execution fails
        """
        factory_info = self.get_factory(factory_id)
        if not factory_info:
            raise ValueError(f"Factory not found: {factory_id}")

        if not factory_info.async_factory:
            raise ValueError(f"Factory {factory_id} is not async")

        try:
            return await factory_info.factory_function(*args, **kwargs)
        except Exception as e:
            logger.error(f"Async factory {factory_id} failed: {e}")
            raise

    def list_factories(
        self,
        category: str | None = None,
        tags: list[str] | None = None,
        return_type: type | None = None,
    ) -> list[FactoryInfo]:
        """List factories matching criteria.

        Args:
            category: Optional category filter
            tags: Optional tag filters (any match)
            return_type: Optional return type filter

        Returns:
            List of matching FactoryInfo objects
        """
        factories = list(self._factories.values())

        if category:
            factories = [f for f in factories if f.category == category]

        if tags:
            factories = [f for f in factories if any(tag in f.tags for tag in tags)]

        if return_type:
            factories = [f for f in factories if f.return_type == return_type]

        return factories

    def get_categories(self) -> list[str]:
        """Get all registered categories.

        Returns:
            List of category names
        """
        return list(self._categories.keys())

    def get_factory_count(self) -> int:
        """Get total number of registered factories.

        Returns:
            Number of registered factories
        """
        return len(self._factories)

    def discover_dependencies(self, factory_id: str) -> list[str]:
        """Discover all dependencies for a factory (recursive).

        Args:
            factory_id: Factory ID to analyze

        Returns:
            List of all dependency factory IDs (including transitive)
        """
        visited = set()
        dependencies = []

        def _discover_recursive(fid: str):
            if fid in visited:
                return
            visited.add(fid)

            factory_info = self.get_factory(fid)
            if factory_info:
                for dep in factory_info.dependencies:
                    dependencies.append(dep)
                    _discover_recursive(dep)

        _discover_recursive(factory_id)
        return dependencies

    def validate_dependencies(self) -> dict[str, list[str]]:
        """Validate that all factory dependencies are satisfied.

        Returns:
            Dictionary mapping factory IDs to list of missing dependencies
        """
        missing_deps = {}

        for factory_id, factory_info in self._factories.items():
            missing = []
            for dep in factory_info.dependencies:
                if dep not in self._factories:
                    missing.append(dep)

            if missing:
                missing_deps[factory_id] = missing

        return missing_deps


# Global registry instance
_global_factory_registry = FactoryRegistry()


def get_factory_registry() -> FactoryRegistry:
    """Get the global factory registry instance."""
    return _global_factory_registry


def register_factory(
    factory_id: str,
    factory_function: FactoryFunction,
    return_type: type,
    description: str,
    **kwargs,
) -> None:
    """Register a factory function in the global registry.

    Args:
        factory_id: Unique identifier for the factory
        factory_function: The factory function
        return_type: Type returned by the factory
        description: Description of what the factory creates
        **kwargs: Additional factory options
    """
    global_registry = get_factory_registry()
    global_registry.register_factory(
        factory_id, factory_function, return_type, description, **kwargs
    )


def discover_factory(
    factory_id: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    return_type: type | None = None,
) -> list[FactoryInfo] | FactoryInfo | None:
    """Discover factories matching criteria.

    Args:
        factory_id: Specific factory ID to find
        category: Category to search in
        tags: Tags to match
        return_type: Return type to match

    Returns:
        Single FactoryInfo if factory_id specified, list otherwise
    """
    global_registry = get_factory_registry()

    if factory_id:
        return global_registry.get_factory(factory_id)
    else:
        return global_registry.list_factories(category=category, tags=tags, return_type=return_type)


# =============================================================================
# FACTORY DECORATORS
# =============================================================================


def factory(factory_id: str, return_type: type, description: str, **kwargs):
    """Decorator to automatically register a function as a factory.

    Args:
        factory_id: Unique identifier for the factory
        return_type: Type returned by the factory
        description: Description of what the factory creates
        **kwargs: Additional factory options

    Example:
        @factory("my_service", MyService, "Creates MyService instance")
        def create_my_service():
            return MyService()
    """

    def decorator(func: FactoryFunction) -> FactoryFunction:
        register_factory(factory_id, func, return_type, description, **kwargs)
        return func

    return decorator


def async_factory(factory_id: str, return_type: type, description: str, **kwargs):
    """Decorator to register an async function as a factory.

    Args:
        factory_id: Unique identifier for the factory
        return_type: Type returned by the factory
        description: Description of what the factory creates
        **kwargs: Additional factory options
    """
    kwargs["async_factory"] = True

    def decorator(func: FactoryFunction) -> FactoryFunction:
        register_factory(factory_id, func, return_type, description, **kwargs)
        return func

    return decorator


def singleton_factory(factory_id: str, return_type: type, description: str, **kwargs):
    """Decorator to register a singleton factory.

    Args:
        factory_id: Unique identifier for the factory
        return_type: Type returned by the factory
        description: Description of what the factory creates
        **kwargs: Additional factory options
    """
    kwargs["singleton"] = True

    def decorator(func: FactoryFunction) -> FactoryFunction:
        register_factory(factory_id, func, return_type, description, **kwargs)
        return func

    return decorator
