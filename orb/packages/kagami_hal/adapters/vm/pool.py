"""VM Pool Manager.

Manages a pool of VMs for concurrent automation tasks.
Supports automatic VM allocation, cleanup, and snapshot restoration.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .types import OSType, VMConfig, VMTier

if TYPE_CHECKING:
    from .protocol import VMAdapterProtocol

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """VM pool configuration.

    Optimized defaults for low-latency VM acquisition:
    - Pre-warm 1 VM at startup (eliminates cold-start for first request)
    - Async snapshot restore (non-blocking release)
    - Proactive VM creation when pool runs low
    """

    max_vms: int = 4
    default_os: OSType = OSType.MACOS
    default_tier: VMTier = VMTier.SANDBOXED
    auto_restore_snapshot: str = "clean-state"
    acquire_timeout_seconds: float = 300.0
    warmup_count: int = 1  # Pre-warm 1 VM to eliminate cold-start latency
    async_snapshot_restore: bool = True  # Don't block release on snapshot
    proactive_creation_threshold: float = 0.5  # Create new VM when <50% available
    health_check_interval_seconds: float = 60.0  # Periodic health checks


@dataclass
class PooledVM:
    """A VM in the pool."""

    adapter: VMAdapterProtocol
    config: VMConfig
    in_use: bool = False
    use_count: int = 0
    last_used: float = 0.0
    error_count: int = 0


@dataclass
class PoolStats:
    """Pool statistics."""

    total_vms: int = 0
    available_vms: int = 0
    in_use_vms: int = 0
    total_acquisitions: int = 0
    total_releases: int = 0
    failed_acquisitions: int = 0


class VMPool:
    """Manages a pool of VMs for concurrent automation.

    The pool supports:
    - Automatic VM allocation from available pool
    - Snapshot restoration on release
    - Configurable pool size
    - Multiple OS types and tiers
    - Context manager for automatic cleanup

    Usage:
        pool = VMPool(PoolConfig(max_vms=4))
        await pool.initialize()

        # Acquire a VM
        async with pool.acquire() as vm:
            await vm.screenshot()
            await vm.click(100, 200)
        # VM automatically released and snapshot restored

        # Acquire specific OS
        async with pool.acquire(os_type=OSType.WINDOWS) as vm:
            result = await vm.execute("dir C:\\")

        await pool.shutdown()
    """

    def __init__(self, config: PoolConfig | None = None):
        """Initialize VM pool.

        Args:
            config: Pool configuration
        """
        self._config = config or PoolConfig()
        self._vms: list[PooledVM] = []
        self._lock = asyncio.Lock()
        self._initialized = False
        self._stats = PoolStats()
        self._acquire_event = asyncio.Event()
        self._pending_creations = 0  # Track VMs being created to prevent over-allocation

    @property
    def stats(self) -> PoolStats:
        """Get pool statistics."""
        return self._stats

    async def initialize(self) -> bool:
        """Initialize the VM pool.

        Creates any pre-warmed VMs specified in config.

        Returns:
            True if initialized successfully
        """
        if self._initialized:
            return True

        logger.info(f"Initializing VM pool (max={self._config.max_vms})")

        # Pre-warm VMs if configured
        for i in range(self._config.warmup_count):
            try:
                vm = await self._create_vm(
                    os_type=self._config.default_os,
                    tier=self._config.default_tier,
                )
                self._vms.append(vm)
                self._stats.total_vms += 1
                self._stats.available_vms += 1
            except Exception as e:
                logger.warning(f"Failed to pre-warm VM {i}: {e}")

        self._initialized = True
        self._acquire_event.set()
        logger.info(f"VM pool initialized ({len(self._vms)} pre-warmed)")
        return True

    async def shutdown(self) -> None:
        """Shutdown pool and all VMs."""
        logger.info("Shutting down VM pool")

        async with self._lock:
            # Shutdown all VMs in parallel
            if self._vms:

                async def shutdown_vm(vm):
                    await vm.adapter.stop()
                    await vm.adapter.shutdown()

                await asyncio.gather(*[shutdown_vm(vm) for vm in self._vms], return_exceptions=True)
            self._vms.clear()
            self._initialized = False

        logger.info("VM pool shutdown complete")

    async def _create_vm(
        self,
        os_type: OSType = OSType.MACOS,
        tier: VMTier = VMTier.SANDBOXED,
        name: str | None = None,
    ) -> PooledVM:
        """Create a new VM adapter.

        Args:
            os_type: Operating system type
            tier: VM isolation tier
            name: Optional VM name

        Returns:
            PooledVM wrapper
        """
        # Import adapters here to avoid circular imports
        from .cua_lume import CUALumeAdapter
        from .parallels import ParallelsAdapter
        from .peekaboo import PeekabooAdapter

        vm_name = name or f"pool-{os_type.value}-{len(self._vms)}"
        config = VMConfig(
            name=vm_name,
            os_type=os_type,
            tier=tier,
        )

        # Select adapter based on tier
        adapter: VMAdapterProtocol
        if tier == VMTier.HOST:
            adapter = PeekabooAdapter()
        elif tier == VMTier.SANDBOXED:
            adapter = CUALumeAdapter(vm_name)
        elif tier == VMTier.MULTI_OS:
            adapter = ParallelsAdapter(vm_name)
        else:
            raise ValueError(f"Unknown tier: {tier}")

        # Initialize adapter
        if not await adapter.initialize(config):
            raise RuntimeError(f"Failed to initialize VM adapter: {vm_name}")

        # Start VM (except for host)
        if tier != VMTier.HOST:
            if not await adapter.start():
                raise RuntimeError(f"Failed to start VM: {vm_name}")

        return PooledVM(adapter=adapter, config=config)

    async def _find_available_vm(
        self,
        os_type: OSType | None = None,
        tier: VMTier | None = None,
    ) -> PooledVM | None:
        """Find an available VM matching criteria.

        Args:
            os_type: Required OS type (None = any)
            tier: Required tier (None = any)

        Returns:
            Available PooledVM or None
        """
        for pooled_vm in self._vms:
            if pooled_vm.in_use:
                continue

            if os_type and pooled_vm.config.os_type != os_type:
                continue

            if tier and pooled_vm.config.tier != tier:
                continue

            return pooled_vm

        return None

    @asynccontextmanager
    async def acquire(
        self,
        os_type: OSType | None = None,
        tier: VMTier | None = None,
        timeout: float | None = None,
    ) -> AsyncIterator[VMAdapterProtocol]:
        """Acquire a VM from the pool.

        Args:
            os_type: Required OS type (None = default)
            tier: Required tier (None = default)
            timeout: Timeout in seconds (None = use config)

        Yields:
            VMAdapterProtocol for the acquired VM

        Raises:
            TimeoutError: If no VM available within timeout
            RuntimeError: If pool not initialized
        """
        if not self._initialized:
            raise RuntimeError("VM pool not initialized")

        os_type = os_type or self._config.default_os
        tier = tier or self._config.default_tier
        timeout = timeout or self._config.acquire_timeout_seconds

        pooled_vm: PooledVM | None = None
        start_time = asyncio.get_event_loop().time()
        reserved_slot = False  # Track if we reserved a creation slot

        try:
            # Try to acquire VM
            while True:
                should_create = False

                async with self._lock:
                    # Look for available VM
                    pooled_vm = await self._find_available_vm(os_type, tier)

                    if pooled_vm:
                        pooled_vm.in_use = True
                        pooled_vm.use_count += 1
                        pooled_vm.last_used = asyncio.get_event_loop().time()
                        self._stats.available_vms -= 1
                        self._stats.in_use_vms += 1
                        self._stats.total_acquisitions += 1
                        break

                    # Can we create a new VM? Check both existing VMs and pending creations
                    # to prevent race condition where multiple coroutines all try to create VMs
                    total_allocated = len(self._vms) + self._pending_creations
                    if total_allocated < self._config.max_vms:
                        # Reserve a slot before releasing the lock
                        self._pending_creations += 1
                        reserved_slot = True
                        should_create = True

                # Create VM outside the lock to avoid blocking other operations
                if should_create:
                    try:
                        pooled_vm = await self._create_vm(os_type, tier)
                        # Add the created VM to the pool
                        async with self._lock:
                            self._pending_creations -= 1
                            reserved_slot = False
                            pooled_vm.in_use = True
                            pooled_vm.use_count = 1
                            pooled_vm.last_used = asyncio.get_event_loop().time()
                            self._vms.append(pooled_vm)
                            self._stats.total_vms += 1
                            self._stats.in_use_vms += 1
                            self._stats.total_acquisitions += 1
                        break
                    except Exception as e:
                        # Release the reserved slot on failure
                        async with self._lock:
                            self._pending_creations -= 1
                            reserved_slot = False
                        logger.error(f"Failed to create VM: {e}")
                        raise

                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout:
                    self._stats.failed_acquisitions += 1
                    raise TimeoutError(
                        f"No VM available within {timeout}s "
                        f"(pool={len(self._vms)}, in_use={self._stats.in_use_vms})"
                    )

                # Wait for a VM to become available
                self._acquire_event.clear()
                try:
                    await asyncio.wait_for(
                        self._acquire_event.wait(),
                        timeout=min(5.0, timeout - elapsed),
                    )
                except TimeoutError:
                    pass  # Retry loop

            logger.debug(f"Acquired VM: {pooled_vm.config.name}")
            yield pooled_vm.adapter

        finally:
            # Release reserved slot if we reserved one but failed before creating
            if reserved_slot:
                async with self._lock:
                    self._pending_creations -= 1
            if pooled_vm:
                await self._release_vm(pooled_vm)

    async def _release_vm(self, pooled_vm: PooledVM) -> None:
        """Release a VM back to the pool.

        Restores snapshot if configured. Uses async restore by default
        to avoid blocking the release operation.

        Args:
            pooled_vm: VM to release
        """
        async with self._lock:
            pooled_vm.in_use = False
            self._stats.in_use_vms -= 1
            self._stats.available_vms += 1
            self._stats.total_releases += 1

            # Signal waiting acquirers IMMEDIATELY (don't wait for snapshot)
            self._acquire_event.set()
            logger.debug(f"Released VM: {pooled_vm.config.name}")

        # Restore snapshot AFTER releasing lock (async, non-blocking)
        if self._config.auto_restore_snapshot:
            if self._config.async_snapshot_restore:
                # Fire-and-forget background restore
                asyncio.create_task(self._restore_snapshot_background(pooled_vm))
            else:
                # Blocking restore (legacy behavior)
                await self._restore_snapshot_sync(pooled_vm)

    async def _restore_snapshot_background(self, pooled_vm: PooledVM) -> None:
        """Restore snapshot in background (non-blocking).

        Args:
            pooled_vm: VM to restore
        """
        try:
            snapshots = await pooled_vm.adapter.list_snapshots()
            if self._config.auto_restore_snapshot in snapshots:
                await pooled_vm.adapter.restore_snapshot(self._config.auto_restore_snapshot)
                logger.debug(f"Background snapshot restored: {self._config.auto_restore_snapshot}")
        except Exception as e:
            logger.warning(f"Background snapshot restore failed: {e}")
            async with self._lock:
                pooled_vm.error_count += 1

    async def _restore_snapshot_sync(self, pooled_vm: PooledVM) -> None:
        """Restore snapshot synchronously (blocking).

        Args:
            pooled_vm: VM to restore
        """
        try:
            snapshots = await pooled_vm.adapter.list_snapshots()
            if self._config.auto_restore_snapshot in snapshots:
                await pooled_vm.adapter.restore_snapshot(self._config.auto_restore_snapshot)
                logger.debug(f"Restored snapshot: {self._config.auto_restore_snapshot}")
        except Exception as e:
            logger.warning(f"Failed to restore snapshot: {e}")
            async with self._lock:
                pooled_vm.error_count += 1

    async def get_stats(self) -> PoolStats:
        """Get current pool statistics.

        Returns:
            PoolStats
        """
        async with self._lock:
            self._stats.total_vms = len(self._vms)
            self._stats.available_vms = sum(1 for vm in self._vms if not vm.in_use)
            self._stats.in_use_vms = sum(1 for vm in self._vms if vm.in_use)
            return self._stats


# Singleton pool instance
_vm_pool: VMPool | None = None


async def get_vm_pool(config: PoolConfig | None = None) -> VMPool:
    """Get the global VM pool singleton.

    Args:
        config: Optional config (used only on first call)

    Returns:
        Initialized VMPool
    """
    global _vm_pool

    if _vm_pool is None:
        _vm_pool = VMPool(config)
        await _vm_pool.initialize()

    return _vm_pool


async def shutdown_vm_pool() -> None:
    """Shutdown the global VM pool."""
    global _vm_pool

    if _vm_pool is not None:
        await _vm_pool.shutdown()
        _vm_pool = None


__all__ = [
    "PoolConfig",
    "PoolStats",
    "PooledVM",
    "VMPool",
    "get_vm_pool",
    "shutdown_vm_pool",
]
