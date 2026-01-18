"""Distributed locking using etcd leases and transactions.

Provides consensus-aware distributed locks for coordinating across instances:
- Migration locks: Serialize database schema changes
- Checkpoint locks: Prevent concurrent checkpoint writes
- General resource locks: Coordinate access to shared resources

Uses etcd3 leases with automatic renewal and CBF-compliant timeout handling.

Created: December 16, 2025 (migration from deprecated swarm.distributed_locks)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import etcd3

logger = logging.getLogger(__name__)


class DistributedLock:
    """Distributed lock using etcd lease and transaction primitives.

    Thread-safe, async-compatible lock that uses etcd leases for:
    - Automatic expiry (TTL)
    - Renewal during long-held locks (auto_renew=True)
    - Atomic acquire via compare-and-set[Any] transaction

    Example:
        async with distributed_lock("migration:alembic", ttl=600):
            # Run migration - lock auto-renewed
            await run_alembic_upgrade()
    """

    def __init__(
        self,
        resource: str,
        ttl: int = 30,
        auto_renew: bool = False,
        timeout: float = 10.0,
    ):
        """Initialize distributed lock.

        Args:
            resource: Resource identifier (e.g., "migration:schema_v1")
            ttl: Lease time-to-live in seconds
            auto_renew: Auto-renew lease while held (for long operations)
            timeout: Max time to wait for lock acquisition (seconds)
        """
        self.resource = resource
        self.ttl = ttl
        self.auto_renew = auto_renew
        self.timeout = timeout

        self._client: etcd3.Etcd3Client | None = None
        self._lease: etcd3.Lease | None = None
        self._lease_id: int | None = None
        self._acquired = False
        self._renew_task: asyncio.Task | None = None

        # Lock key in etcd
        self._lock_key = f"/locks/{resource}"

    async def acquire(self, blocking: bool = True, timeout: float | None = None) -> bool:
        """Acquire the distributed lock.

        Args:
            blocking: If True, wait up to timeout for lock. If False, fail immediately.
            timeout: Override default timeout (seconds)

        Returns:
            True if lock acquired, False if timeout (only in blocking mode)

        Raises:
            TimeoutError: If blocking=True and timeout exceeded
            RuntimeError: If lock already acquired or etcd unavailable
        """
        if self._acquired:
            raise RuntimeError("Lock already acquired")

        # Get etcd client
        from kagami.core.consensus.etcd_client import get_etcd_client

        try:
            self._client = get_etcd_client()
        except Exception as e:
            raise RuntimeError(f"Cannot acquire lock: etcd unavailable - {e}") from e

        # Create lease
        try:
            self._lease = self._client.lease(ttl=self.ttl)
            self._lease_id = self._lease.id
        except Exception as e:
            raise RuntimeError(f"Failed to create etcd lease: {e}") from e

        # Attempt to acquire lock via transaction
        effective_timeout = timeout if timeout is not None else self.timeout
        start_time = time.time()

        while True:
            try:
                # Transaction: if key doesn't exist, create it with our lease
                success = self._client.transaction(
                    compare=[
                        self._client.transactions.version(self._lock_key) == 0  # Key doesn't exist
                    ],
                    success=[
                        self._client.transactions.put(
                            self._lock_key,
                            f"locked-{self._lease_id}".encode(),
                            lease=self._lease,
                        )
                    ],
                    failure=[],
                )

                if success:
                    self._acquired = True
                    logger.info(
                        f"🔒 Acquired distributed lock: {self.resource} (lease={self._lease_id})"
                    )

                    # Start auto-renewal task if requested
                    if self.auto_renew:
                        self._renew_task = asyncio.create_task(self._renewal_loop())

                    return True

                # Lock held by another instance
                if not blocking:
                    # Non-blocking mode: fail immediately
                    await self._cleanup_lease()
                    return False

                # Check timeout
                elapsed = time.time() - start_time
                if elapsed >= effective_timeout:
                    await self._cleanup_lease()
                    raise TimeoutError(
                        f"Failed to acquire lock '{self.resource}' within {effective_timeout}s"
                    )

                # Wait and retry
                await asyncio.sleep(0.5)

            except Exception as e:
                await self._cleanup_lease()
                raise RuntimeError(f"Error acquiring lock: {e}") from e

    async def release(self) -> None:
        """Release the distributed lock.

        Raises:
            RuntimeError: If lock not acquired or already released
        """
        if not self._acquired:
            raise RuntimeError("Cannot release lock that is not acquired")

        try:
            # Stop renewal task
            if self._renew_task is not None:
                self._renew_task.cancel()
                try:
                    await self._renew_task
                except asyncio.CancelledError:
                    pass
                self._renew_task = None

            # Delete lock key
            if self._client is not None:
                try:
                    self._client.delete(self._lock_key)
                except Exception as e:
                    logger.warning(f"Error deleting lock key: {e}")

            # Revoke lease
            await self._cleanup_lease()

            self._acquired = False
            logger.info(f"🔓 Released distributed lock: {self.resource}")

        except Exception as e:
            logger.error(f"Error releasing lock: {e}")
            raise

    async def _renewal_loop(self) -> None:
        """Background task to auto-renew lease."""
        try:
            # Renew at 1/3 of TTL interval
            renew_interval = self.ttl / 3.0

            while self._acquired:
                await asyncio.sleep(renew_interval)

                if self._lease is not None and self._acquired:
                    try:
                        self._lease.refresh()
                        logger.debug(f"Renewed lease for lock '{self.resource}'")
                    except Exception as e:
                        logger.error(f"Failed to renew lease for lock '{self.resource}': {e}")
                        # Don't raise - let the lease expire naturally
                        break

        except asyncio.CancelledError:
            # Expected during shutdown
            pass

    async def _cleanup_lease(self) -> None:
        """Revoke lease and cleanup."""
        if self._lease is not None:
            try:
                self._lease.revoke()
            except Exception as e:
                logger.debug(f"Error revoking lease (non-critical): {e}")
            self._lease = None
            self._lease_id = None

    @property
    def locked(self) -> bool:
        """Check if lock is currently held."""
        return self._acquired

    async def __aenter__(self) -> DistributedLock:
        """Async context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:  # type: ignore[no-untyped-def]
        """Async context manager exit."""
        await self.release()
        return False


@asynccontextmanager
async def distributed_lock(
    resource: str,
    ttl: int = 30,
    timeout: float = 10.0,
    auto_renew: bool = False,
) -> AsyncGenerator[DistributedLock, None]:
    """Async context manager for distributed locks.

    Args:
        resource: Resource identifier (e.g., "migration:alembic")
        ttl: Lease TTL in seconds
        timeout: Max wait time for lock acquisition
        auto_renew: Auto-renew lease for long operations

    Yields:
        DistributedLock instance (already acquired)

    Example:
        async with distributed_lock("checkpoint:model", ttl=300):
            save_checkpoint("model.pt")
    """
    lock = DistributedLock(
        resource=resource,
        ttl=ttl,
        auto_renew=auto_renew,
        timeout=timeout,
    )

    try:
        await lock.acquire()
        yield lock
    finally:
        if lock.locked:
            await lock.release()


__all__ = ["DistributedLock", "distributed_lock"]
