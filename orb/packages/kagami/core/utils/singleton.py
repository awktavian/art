"""Singleton utilities for consistent single-instance patterns.

This module provides reusable singleton patterns to replace 30+ manual
implementations scattered across the codebase.

CONSOLIDATION (December 25, 2025):
==================================
Replaces manual singleton patterns like:
    _INSTANCE: ClassName | None = None
    def get_instance() -> ClassName:
        global _INSTANCE
        if _INSTANCE is None:
            _INSTANCE = ClassName()
        return _INSTANCE

Usage:
======
    from kagami.core.utils.singleton import singleton, SingletonMeta, get_or_create

    # Option 1: Decorator
    @singleton
    class MyService:
        def __init__(self):
            pass

    instance = MyService()  # Always returns same instance

    # Option 2: Metaclass
    class MyService(metaclass=SingletonMeta):
        pass

    # Option 3: Factory function
    _cache: dict[str, MyService] = {}
    def get_my_service() -> MyService:
        return get_or_create("my_service", MyService, _cache)
"""

from __future__ import annotations

import asyncio
import functools
import threading
from collections.abc import Callable
from typing import Any, Generic, TypeVar

T = TypeVar("T")


# =============================================================================
# SINGLETON DECORATOR
# =============================================================================


def singleton(cls: type[T]) -> type[T]:
    """Decorator to make a class a singleton.

    Thread-safe implementation using double-checked locking.

    Example:
        @singleton
        class DatabaseConnection:
            def __init__(self):
                self.connect()

        # All calls return same instance
        conn1 = DatabaseConnection()
        conn2 = DatabaseConnection()
        assert conn1 is conn2
    """
    _instance: T | None = None
    _lock = threading.Lock()
    _original_init = cls.__init__

    @functools.wraps(cls.__init__)
    def __init__(self: T, *args: Any, **kwargs: Any) -> None:
        # Only initialize once
        pass

    def __new__(cls_inner: type[T], *args: Any, **kwargs: Any) -> T:
        nonlocal _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = object.__new__(cls_inner)
                    _original_init(_instance, *args, **kwargs)
        return _instance

    cls.__new__ = __new__  # type: ignore
    cls.__init__ = __init__  # type: ignore
    return cls


# =============================================================================
# SINGLETON METACLASS
# =============================================================================


class SingletonMeta(type):
    """Metaclass for singleton pattern.

    Thread-safe implementation.

    Example:
        class ConfigManager(metaclass=SingletonMeta):
            def __init__(self):
                self.config = {}

        # All instantiations return same instance
        config1 = ConfigManager()
        config2 = ConfigManager()
        assert config1 is config2
    """

    _instances: dict[type, Any] = {}
    _lock = threading.Lock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]

    @classmethod
    def reset(mcs, cls: type) -> None:
        """Reset a singleton instance (for testing)."""
        with mcs._lock:
            mcs._instances.pop(cls, None)


# =============================================================================
# FACTORY FUNCTION HELPER
# =============================================================================


def get_or_create(
    key: str,
    factory: Callable[[], T],
    cache: dict[str, T],
    lock: threading.Lock | None = None,
) -> T:
    """Get or create a singleton instance using a cache dict[str, Any].

    Thread-safe helper for manual singleton management.

    Example:
        _services: dict[str, MyService] = {}
        _lock = threading.Lock()

        def get_my_service() -> MyService:
            return get_or_create("default", MyService, _services, _lock)

    Args:
        key: Cache key for the instance
        factory: Callable that creates the instance
        cache: Dictionary to store instances
        lock: Optional lock for thread safety

    Returns:
        The singleton instance
    """
    if key in cache:
        return cache[key]

    if lock is None:
        lock = threading.Lock()

    with lock:
        if key not in cache:
            cache[key] = factory()
        return cache[key]


# =============================================================================
# ASYNC SINGLETON WITH LAZY INITIALIZATION
# =============================================================================


class AsyncSingleton(Generic[T]):
    """Async-safe singleton with lazy initialization.

    Use this for services that need async initialization.

    Example:
        class DatabaseService:
            async def initialize(self):
                self.pool = await create_pool()

        _db = AsyncSingleton(DatabaseService)

        async def get_db() -> DatabaseService:
            return await _db.get()
    """

    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._instance: T | None = None
        self._lock = asyncio.Lock()
        self._initialized = False

    async def get(self) -> T:
        """Get the singleton instance, creating if needed."""
        if self._instance is not None and self._initialized:
            return self._instance

        async with self._lock:
            if self._instance is None:
                self._instance = self._factory()

            # Call initialize() if it exists and hasn't been called
            if not self._initialized:
                if hasattr(self._instance, "initialize"):
                    init_method = self._instance.initialize
                    if asyncio.iscoroutinefunction(init_method):
                        await init_method()
                    else:
                        init_method()
                self._initialized = True

            return self._instance

    def reset(self) -> None:
        """Reset the singleton (for testing)."""
        self._instance = None
        self._initialized = False


# =============================================================================
# LAZY SINGLETON DESCRIPTOR
# =============================================================================


class LazySingleton(Generic[T]):
    """Descriptor for lazy singleton initialization.

    Use as a class attribute for lazy initialization.

    Example:
        class App:
            config = LazySingleton(lambda: ConfigManager())
            database = LazySingleton(lambda: DatabasePool())

        app = App()
        app.config  # Creates ConfigManager on first access
    """

    def __init__(self, factory: Callable[[], T]) -> None:
        self._factory = factory
        self._instance: T | None = None
        self._lock = threading.Lock()

    def __get__(self, obj: Any, objtype: type | None = None) -> T:
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    self._instance = self._factory()
        return self._instance

    def reset(self) -> None:
        """Reset the singleton (for testing)."""
        with self._lock:
            self._instance = None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "AsyncSingleton",
    "LazySingleton",
    "SingletonMeta",
    "get_or_create",
    "singleton",
]
