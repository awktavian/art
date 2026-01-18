"""Comprehensive resource management framework for Kagami.

Provides production-ready resource lifecycle management with:
- Automatic cleanup on shutdown (priority-ordered)
- Leak detection and monitoring
- Context managers for scoped resource use
- Decorator for auto-registering class instances

Quick Start:
    # Global manager singleton
    from kagami.core.resource_management import get_resource_manager, CleanupPriority

    manager = get_resource_manager()
    manager.register_resource(connection, "db", priority=CleanupPriority.HIGH)

    # Context manager (auto-cleanup)
    from kagami.core.resource_management import resource_context

    with resource_context(connection, "conn") as conn:
        conn.execute(...)

    # Decorator (auto-register instances)
    from kagami.core.resource_management import managed_resource

    @managed_resource("handler")
    class FileHandler:
        def close(self): ...

Key Components:
    - ResourceManager: Central registry and cleanup coordinator
    - CleanupPriority: CRITICAL → HIGH → MEDIUM → LOW ordering
    - ResourceState: Lifecycle states (ACTIVE, CLEANUP_PENDING, etc.)
    - LeakDetector: Background monitoring for memory leaks
    - resource_context / async_resource_context: Scoped cleanup
"""

from .comprehensive_cleanup import (
    AsyncResourceProtocol,
    CleanupPriority,
    LeakDetector,
    ResourceLeak,
    ResourceManager,
    ResourceMetrics,
    ResourceProtocol,
    ResourceState,
    ResourceTracker,
    async_resource_context,
    cleanup_temp_files,
    disable_leak_detection,
    enable_leak_detection,
    force_garbage_collection,
    get_resource_manager,
    managed_resource,
    resource_context,
)

__all__ = [
    "AsyncResourceProtocol",
    "CleanupPriority",
    "LeakDetector",
    "ResourceLeak",
    "ResourceManager",
    "ResourceMetrics",
    "ResourceProtocol",
    "ResourceState",
    "ResourceTracker",
    "async_resource_context",
    "cleanup_temp_files",
    "disable_leak_detection",
    "enable_leak_detection",
    "force_garbage_collection",
    "get_resource_manager",
    "managed_resource",
    "resource_context",
]
