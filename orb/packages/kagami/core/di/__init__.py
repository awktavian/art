"""Dependency Injection Container for Kagami.

Provides a lightweight dependency injection (DI) system that enables
late binding of services without circular imports. This is critical
for large codebases where infrastructure components (databases, APIs,
event systems) need to be swapped or mocked for testing.

Why Dependency Injection?
    - Decouples components from their dependencies
    - Enables testing with mock implementations
    - Avoids circular import issues in large codebases
    - Supports singleton and factory patterns
    - Makes dependencies explicit and configurable

Core Concepts:
    - **Service Key**: String or type identifying a service
    - **Provider**: Callable that creates service instances
    - **Singleton**: Instance reused across all resolutions
    - **Factory**: New instance created on each resolution

Components:
    - register_service: Register a provider callable
    - register_instance: Register a pre-built singleton
    - resolve_service: Get service instance (creates if needed)
    - try_resolve: Get service or None if not registered
    - has_service: Check if service is registered
    - unregister_service: Remove a service registration
    - reset_container: Clear all (for tests)
    - ServiceContainer: Class-based facade for all operations

Thread Safety:
    All operations are thread-safe using RLock (reentrant).
    Safe to use from multiple threads concurrently.

Example:
    >>> from kagami.core.di import register_service, resolve_service
    >>>
    >>> # Register a singleton service
    >>> register_service("database", lambda: Database(), singleton=True)
    >>>
    >>> # Resolve anywhere in the codebase
    >>> db = resolve_service("database")
    >>>
    >>> # Register with type key
    >>> from kagami.core.protocols import EventBroadcaster
    >>> register_service(EventBroadcaster, lambda: MyBroadcaster())
    >>> broadcaster = resolve_service(EventBroadcaster)

See Also:
    - kagami.core.di.container: Implementation details
    - docs/architecture.md: System architecture
"""

from kagami.core.di.container import (
    ServiceContainer,
    has_service,
    register_instance,
    register_service,
    reset_container,
    resolve_service,
    try_resolve,
    unregister_service,
)

# =============================================================================
# PUBLIC API
# =============================================================================
# All DI container functions and classes.

__all__ = [
    # Class-based facade (for backwards compatibility)
    "ServiceContainer",
    # Query functions
    "has_service",
    # Registration functions
    "register_instance",
    "register_service",
    # Management functions
    "reset_container",
    # Resolution functions
    "resolve_service",
    "try_resolve",
    "unregister_service",
]
