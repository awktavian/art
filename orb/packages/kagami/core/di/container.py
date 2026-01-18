"""Lightweight Dependency Injection Container Implementation.

Provides a thread-safe registry that maps service keys to provider callables.
This enables late binding of infrastructure components (e.g., API event
broadcasters, database connections) without import cycles between layers.

Design Decisions:
    - Global singleton registries (_providers, _singletons)
    - Thread-safe with RLock (reentrant for nested calls)
    - Keys normalized to strings for consistent lookup
    - Type keys use fully qualified names (module.ClassName)
    - Singleton pattern with lazy instantiation

Registry Structure:
    _providers: key → (provider_callable, is_singleton)
    _singletons: key → instance (only for singleton services)

Thread Safety:
    All registry operations acquire _lock before modifying state.
    RLock allows recursive locking (same thread can re-acquire).

Performance:
    - O(1) lookups via dict
    - Lock contention minimized (short critical sections)
    - Singletons cached after first resolution

Example:
    >>> register_service("logger", lambda: Logger(), singleton=True)
    >>> logger = resolve_service("logger")  # Creates once
    >>> logger2 = resolve_service("logger")  # Returns cached
    >>> logger is logger2  # True
"""

from __future__ import annotations

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import threading  # Thread-safe registry access
from collections.abc import Callable, Hashable  # Type annotations
from typing import Any  # Generic type hint

# =============================================================================
# TYPE ALIASES
# =============================================================================
# Provider is a factory callable that creates service instances.
# Takes no arguments, returns the service instance.
Provider = Callable[[], Any]

# =============================================================================
# GLOBAL REGISTRIES
# =============================================================================
# These are module-level singletons shared across the application.
# All access must be protected by _lock for thread safety.

# RLock allows recursive locking (same thread can re-acquire)
_lock = threading.RLock()

# Maps normalized key → (provider_callable, is_singleton_bool)
_providers: dict[str, tuple[Provider, bool]] = {}

# Cache for singleton instances (only created once)
_singletons: dict[str, Any] = {}


def _normalize_key(key: str | Hashable | type) -> str:
    """Normalize service key to a consistent string format.

    Handles string keys (passed through), type keys (converted to
    fully qualified name), and other hashable keys.

    Args:
        key: String, type, or other hashable key.

    Returns:
        Normalized string key for registry lookup.

    Raises:
        TypeError: If key cannot be normalized.

    Example:
        >>> _normalize_key("my_service")
        'my_service'
        >>> _normalize_key(MyClass)
        'mymodule.MyClass'
    """
    # String keys are used directly
    if isinstance(key, str):
        return key
    # Type keys use fully qualified name (module.ClassName)
    try:
        module = getattr(key, "__module__", None)
        qualname = getattr(key, "__qualname__", None)
        if module and qualname:
            return f"{module}.{qualname}"
    except Exception as exc:  # pragma: no cover - defensive
        raise TypeError(f"Unsupported service key {key!r}") from exc
    raise TypeError(f"Unsupported service key {key!r}") from None


# =============================================================================
# REGISTRATION FUNCTIONS
# =============================================================================


def register_service(
    key: str | Hashable | type,
    provider: Provider,
    *,
    singleton: bool = True,
    replace: bool = False,
) -> None:
    """Register a provider callable for the given service key.

    The provider is a factory function that creates service instances.
    By default, services are singletons (created once, cached).

    Args:
        key: Service identifier (string, type, or hashable).
        provider: Callable that creates the service (no arguments).
        singleton: If True, cache instance after first creation.
        replace: If True, allow replacing existing registration.

    Raises:
        ValueError: If key already registered and replace=False.

    Example:
        >>> register_service("db", lambda: Database(), singleton=True)
        >>> register_service(Logger, lambda: Logger(), singleton=True)
    """
    norm_key = _normalize_key(key)
    with _lock:
        # Check for duplicate registration
        if not replace and norm_key in _providers:
            raise ValueError(f"Service '{norm_key}' already registered")
        # Store provider and singleton flag
        _providers[norm_key] = (provider, singleton)
        # Clear cached singleton if replacing
        if replace:
            _singletons.pop(norm_key, None)


def register_instance(key: str | Hashable | type, instance: Any, *, replace: bool = True) -> None:
    """Register a pre-built singleton instance.

    Use when you already have an instance and don't need lazy creation.
    The instance is stored directly in the singleton cache.

    Args:
        key: Service identifier (string, type, or hashable).
        instance: Pre-built service instance.
        replace: If True, replace existing registration (default True).

    Example:
        >>> config = Config.from_file("config.yaml")
        >>> register_instance("config", config)
    """
    norm_key = _normalize_key(key)
    with _lock:
        # Create a provider that returns the instance (for API consistency)
        _providers[norm_key] = (lambda: instance, True)
        # Store directly in singleton cache
        if replace or norm_key not in _singletons:
            _singletons[norm_key] = instance


# =============================================================================
# RESOLUTION FUNCTIONS
# =============================================================================


def resolve_service(key: str | Hashable | type) -> Any:
    """Resolve (and instantiate if needed) a service.

    For singleton services, creates instance on first call and caches.
    For factory services, creates new instance on each call.

    Args:
        key: Service identifier (string, type, or hashable).

    Returns:
        Service instance.

    Raises:
        LookupError: If service key is not registered.

    Example:
        >>> db = resolve_service("database")
        >>> db.connect()
    """
    norm_key = _normalize_key(key)
    with _lock:
        # Look up provider entry
        provider_entry = _providers.get(norm_key)
        if not provider_entry:
            raise LookupError(f"Service '{norm_key}' is not registered")

        provider, singleton = provider_entry
        if singleton:
            # Return cached instance or create and cache
            if norm_key not in _singletons:
                _singletons[norm_key] = provider()
            return _singletons[norm_key]
        # Factory: create new instance each time
        return provider()


def try_resolve(key: str | Hashable | type) -> Any | None:
    """Resolve a service if registered; return None otherwise.

    Safe version of resolve_service that doesn't raise exceptions.
    Useful for optional dependencies.

    Args:
        key: Service identifier (string, type, or hashable).

    Returns:
        Service instance or None if not registered.

    Example:
        >>> cache = try_resolve("cache")  # Returns None if not configured
        >>> if cache:
        ...     cache.set("key", "value")
    """
    try:
        return resolve_service(key)
    except LookupError:
        return None


# =============================================================================
# QUERY AND MANAGEMENT FUNCTIONS
# =============================================================================


def has_service(key: str | Hashable | type) -> bool:
    """Check if a service is registered.

    Args:
        key: Service identifier to check.

    Returns:
        True if service is registered, False otherwise.
    """
    norm_key = _normalize_key(key)
    with _lock:
        return norm_key in _providers


def unregister_service(key: str | Hashable | type) -> None:
    """Remove a service registration.

    Clears both the provider and any cached singleton instance.

    Args:
        key: Service identifier to unregister.
    """
    norm_key = _normalize_key(key)
    with _lock:
        _providers.pop(norm_key, None)
        _singletons.pop(norm_key, None)


def reset_container() -> None:
    """Clear all registered services (test use only).

    Removes all providers and cached singletons.
    Call this in test teardown to ensure clean state.

    WARNING: Do not call in production code!
    """
    with _lock:
        _providers.clear()
        _singletons.clear()


# =============================================================================
# SERVICE CONTAINER CLASS
# =============================================================================
# Class-based facade for backwards compatibility with legacy DI API.
# All methods are static and delegate to module-level functions.


class ServiceContainer:
    """Class-based facade for the DI container.

    Provides a backwards-compatible interface mirroring legacy DI API.
    All methods are static and delegate to module-level functions.

    This allows both styles:
        # Functional style
        register_service("db", lambda: DB())
        db = resolve_service("db")

        # Class-based style
        ServiceContainer.register("db", lambda: DB())
        db = ServiceContainer.resolve("db")

    Attributes:
        register: Alias for register_service.
        register_instance: Alias for register_instance.
        resolve: Alias for resolve_service.
        try_resolve: Alias for try_resolve.
        has: Alias for has_service.
        unregister: Alias for unregister_service.
        reset: Alias for reset_container.
    """

    register = staticmethod(register_service)
    register_instance = staticmethod(register_instance)
    resolve = staticmethod(resolve_service)
    try_resolve = staticmethod(try_resolve)
    has = staticmethod(has_service)
    unregister = staticmethod(unregister_service)
    reset = staticmethod(reset_container)


# =============================================================================
# PUBLIC API
# =============================================================================
# All DI container functions and classes.

__all__ = [
    # Class-based facade
    "ServiceContainer",
    # Query and management functions
    "has_service",
    # Registration functions
    "register_instance",
    "register_service",
    "reset_container",
    # Resolution functions
    "resolve_service",
    "try_resolve",
    "unregister_service",
]
