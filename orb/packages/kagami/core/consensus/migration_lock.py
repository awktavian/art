"""Distributed migration locking for database schema changes.

Ensures only one instance runs Alembic migrations at a time,
preventing concurrent schema changes that could corrupt the database.

Uses KagamiConsensus distributed lock infrastructure (Dec 16, 2025).
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def migration_lock(migration_name: str = "alembic") -> Generator[bool, None, None]:
    """Acquire distributed lock for database migrations.

    Args:
        migration_name: Name of migration operation

    Yields:
        True if lock acquired (always yields for compatibility)

    Raises:
        RuntimeError: If used from async context or if lock acquisition fails
        TimeoutError: If lock cannot be acquired within timeout

    Example:
        with migration_lock("schema_upgrade"):
            # Run alembic upgrade
            alembic.command.upgrade(config, "head")
    """
    try:
        from kagami.core.consensus.distributed_lock import distributed_lock

        # Verify we're not in an async context
        try:
            asyncio.get_running_loop()
            raise RuntimeError("migration_lock cannot be used from within an async context")
        except RuntimeError:
            pass

        # Create new event loop for sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Use distributed lock with long timeout for migrations
        async def acquire_and_wait() -> AsyncGenerator[bool, None]:
            async with distributed_lock(
                resource=f"migration:{migration_name}",
                ttl=600,  # 10 minute TTL for migrations
                timeout=300.0,  # Wait up to 5 minutes for lock
                auto_renew=True,  # Auto-renew for long migrations
            ):
                logger.info(f"🔒 Acquired migration lock: {migration_name}")
                # Hold lock while migration runs
                yield True
                logger.info(f"🔓 Released migration lock: {migration_name}")

        # Run async context manager in sync context
        lock_gen = acquire_and_wait()
        try:
            lock = loop.run_until_complete(lock_gen.__anext__())
        except StopAsyncIteration as e:
            raise RuntimeError("Migration lock generator finished without yielding") from e

        try:
            yield lock
        finally:
            # Resume generator to release lock
            try:
                loop.run_until_complete(lock_gen.__anext__())
            except StopAsyncIteration:
                pass  # Expected exit
            except Exception as e:
                logger.error(f"Error releasing migration lock: {e}")
            finally:
                loop.close()

    except TimeoutError:
        logger.error(
            f"⏱️  Could not acquire migration lock for '{migration_name}' - "
            "another instance is running migrations. Aborting to prevent corruption."
        )
        raise RuntimeError(
            f"Migration lock timeout - another instance is running '{migration_name}'"
        ) from None

    except Exception as e:
        logger.error(f"Migration lock error: {e}")
        # FAIL-CLOSED for migrations - do NOT proceed without lock
        raise RuntimeError(
            f"Cannot run migration without distributed lock: {e}. "
            "etcd is required for safe multi-instance deployments."
        ) from e


__all__ = ["migration_lock"]
