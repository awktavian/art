"""Boot action registry and protocol.

Provides a unified interface for boot actions with dependency injection
and configuration-driven boot sequence.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from fastapi import FastAPI

BootCallable = Callable[["FastAPI"], Awaitable[None]]


class BootAction(Protocol):
    """Protocol for boot actions.

    All boot actions follow this interface for consistent execution
    and configuration-driven orchestration.
    """

    async def execute(self, app: FastAPI) -> None:
        """Execute the boot action.

        Args:
            app: FastAPI application instance to configure.

        Raises:
            RuntimeError: If action execution fails.
        """
        ...

    @property
    def name(self) -> str:
        """Action name for logging and configuration."""
        ...

    @property
    def dependencies(self) -> tuple[str, ...]:
        """Names of actions that must complete before this one."""
        ...


class ActionRegistry:
    """Registry for boot actions with dependency resolution."""

    def __init__(self) -> None:
        self._actions: dict[str, BootCallable] = {}
        self._dependencies: dict[str, tuple[str, ...]] = {}

    def register(
        self,
        name: str,
        action: BootCallable,
        dependencies: tuple[str, ...] = (),
    ) -> None:
        """Register a boot action.

        Args:
            name: Unique action name.
            action: Async callable that accepts FastAPI app.
            dependencies: Names of prerequisite actions.

        Raises:
            ValueError: If action name is already registered.
        """
        if name in self._actions:
            raise ValueError(f"Action '{name}' already registered")
        self._actions[name] = action
        self._dependencies[name] = dependencies

    def get(self, name: str) -> BootCallable:
        """Get registered action by name.

        Args:
            name: Action name.

        Returns:
            Registered action callable.

        Raises:
            KeyError: If action not registered.
        """
        return self._actions[name]

    def get_dependencies(self, name: str) -> tuple[str, ...]:
        """Get action dependencies.

        Args:
            name: Action name.

        Returns:
            Tuple of prerequisite action names.

        Raises:
            KeyError: If action not registered.
        """
        return self._dependencies[name]

    def list_actions(self) -> list[str]:
        """List all registered action names."""
        return list(self._actions.keys())


# Global registry instance
_registry = ActionRegistry()


def register_action(
    name: str,
    dependencies: tuple[str, ...] = (),
) -> Callable[[BootCallable], BootCallable]:
    """Decorator to register boot actions.

    Usage:
        @register_action("database", dependencies=("enforce_full_operation",))
        async def startup_database(app: FastAPI) -> None:
            ...

    Args:
        name: Unique action name.
        dependencies: Names of prerequisite actions.

    Returns:
        Decorator function.
    """

    def decorator(func: BootCallable) -> BootCallable:
        _registry.register(name, func, dependencies)
        return func

    return decorator


def get_registry() -> ActionRegistry:
    """Get the global action registry."""
    return _registry


# Re-export all actions for backwards compatibility
from kagami.boot.actions.init import (
    _env_int,
    _should_enable_loader,
    enforce_full_operation_check,
    shutdown_e8_bus,
    shutdown_etcd,
    startup_cbf_system,
    startup_database,
    startup_e8_bus,
    startup_etcd,
    startup_feature_flags,
    startup_redis,
)
from kagami.boot.actions.registration import (
    startup_ambient_os,
    startup_hal,
    startup_socketio,
)
from kagami.boot.actions.shutdown import shutdown_all

# 🔥 FORGE COLONY: Smart home organism integration
from kagami.boot.actions.smarthome import (
    shutdown_smart_home_organism_bridge,
    startup_smart_home_organism_bridge,
)
from kagami.boot.actions.wiring import (
    coordinate_background_tasks,
    startup_background_tasks,
    startup_brain,
    startup_learning_systems,
    startup_llm_service,
    startup_orchestrator,
    startup_safety,
)

__all__ = [
    "ActionRegistry",
    # Registry
    "BootAction",
    "BootCallable",
    # Helpers
    "_env_int",
    "_should_enable_loader",
    "coordinate_background_tasks",
    # Initialization
    "enforce_full_operation_check",
    "get_registry",
    "register_action",
    # Shutdown
    "shutdown_all",
    "shutdown_e8_bus",
    "shutdown_etcd",
    "shutdown_smart_home_organism_bridge",
    "startup_ambient_os",
    "startup_background_tasks",
    "startup_brain",
    "startup_cbf_system",
    "startup_database",
    "startup_e8_bus",
    "startup_etcd",
    "startup_feature_flags",
    # Registration
    "startup_hal",
    "startup_learning_systems",
    "startup_llm_service",
    # Wiring
    "startup_orchestrator",
    "startup_redis",
    "startup_safety",
    # 🔥 FORGE COLONY: Smart home organism integration
    "startup_smart_home_organism_bridge",
    "startup_socketio",
]
