"""K OS Infrastructure Package.

Core infrastructure components for process and thread management.

This package consolidates infrastructure utilities:
- singleton_cleanup_mixin.py: Singleton pattern with cleanup
- background_task_manager.py: Background task management
- background_processor.py: Background job processing
- graceful_shutdown.py: Graceful shutdown handling
- shared_thread_pool.py: Shared thread pool management
- connection_pool.py: Generic connection pooling (Dec 22, 2025)
- process_isolation.py: Process isolation utilities
"""

from kagami.core.infra.connection_pool import (
    ConnectionPool,
    PoolConfig,
    PooledConnection,
)
from kagami.core.infra.graceful_shutdown import (
    GracefulShutdownCoordinator,
)
from kagami.core.infra.shared_thread_pool import (
    get_shared_thread_pool,
    shutdown_shared_pool,
)
from kagami.core.infra.singleton_cleanup_mixin import SingletonCleanupMixin

# BackgroundTaskManager moved to tasks layer to fix layer violation
# Re-export for backward compatibility
from kagami.core.tasks.background_task_manager import BackgroundTaskManager

__all__ = [
    # Background tasks
    "BackgroundTaskManager",
    # Connection pool
    "ConnectionPool",
    # Shutdown
    "GracefulShutdownCoordinator",
    "PoolConfig",
    "PooledConnection",
    # Singleton
    "SingletonCleanupMixin",
    # Thread pool
    "get_shared_thread_pool",
    "shutdown_shared_pool",
]
