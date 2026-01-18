"""Shared thread pool for all async-to-sync operations.

Provides a global thread pool for running sync operations in async contexts.
This avoids the overhead of creating new ThreadPoolExecutors per request.

Updated December 29, 2025.
"""

import concurrent.futures
import os

_SHARED_POOL: concurrent.futures.ThreadPoolExecutor | None = None
_POOL_SIZE = int(os.getenv("SHARED_THREAD_POOL_SIZE", "10"))


def get_shared_thread_pool() -> concurrent.futures.ThreadPoolExecutor:
    """Get or create the shared thread pool.

    Returns:
        Shared ThreadPoolExecutor instance
    """
    global _SHARED_POOL
    if _SHARED_POOL is None:
        _SHARED_POOL = concurrent.futures.ThreadPoolExecutor(
            max_workers=_POOL_SIZE, thread_name_prefix="kagami_shared_"
        )
    return _SHARED_POOL


def shutdown_shared_pool(wait: bool = True) -> None:
    """Shutdown the shared thread pool.

    Call this during application shutdown.

    Args:
        wait: Wait for threads to complete
    """
    global _SHARED_POOL
    if _SHARED_POOL:
        _SHARED_POOL.shutdown(wait=wait)
        _SHARED_POOL = None


# NOTE: Legacy reference to composio_integration.py removed (Dec 29, 2025)
# The Composio service now uses its own executor pool in kagami/core/services/composio/__init__.py
import atexit

atexit.register(lambda: shutdown_shared_pool(wait=False))
