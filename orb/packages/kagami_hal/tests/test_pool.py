"""Tests for VMPool (VM Pool Management).

Tests cover:
- Pool initialization and shutdown
- VM acquisition and release
- Automatic snapshot restoration
- Pool statistics
- Timeout handling
- Concurrent acquisition
- Pool configuration
- Global pool singleton

Created: December 31, 2025
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from kagami_hal.adapters.vm.pool import (
    PoolConfig,
    PooledVM,
    PoolStats,
    VMPool,
    get_vm_pool,
    shutdown_vm_pool,
)
from kagami_hal.adapters.vm.types import (
    OSType,
    VMConfig,
    VMTier,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def pool_config():
    """Create a default pool configuration."""
    return PoolConfig(
        max_vms=4,
        default_os=OSType.MACOS,
        default_tier=VMTier.SANDBOXED,
        auto_restore_snapshot="clean-state",
        acquire_timeout_seconds=10.0,
        warmup_count=0,
    )


@pytest.fixture
def pool(pool_config):
    """Create a VMPool instance."""
    return VMPool(pool_config)


@pytest.fixture
def mock_adapter():
    """Create a mock VM adapter."""
    adapter = MagicMock()
    adapter.initialize = AsyncMock(return_value=True)
    adapter.start = AsyncMock(return_value=True)
    adapter.stop = AsyncMock(return_value=True)
    adapter.shutdown = AsyncMock()
    adapter.list_snapshots = AsyncMock(return_value=["clean-state"])
    adapter.restore_snapshot = AsyncMock(return_value=True)
    return adapter


# =============================================================================
# PoolConfig Tests
# =============================================================================


class TestPoolConfig:
    """Tests for PoolConfig dataclass."""

    def test_default_config(self):
        """Test default pool configuration."""
        config = PoolConfig()

        assert config.max_vms == 4
        assert config.default_os == OSType.MACOS
        assert config.default_tier == VMTier.SANDBOXED
        assert config.auto_restore_snapshot == "clean-state"
        assert config.acquire_timeout_seconds == 300.0
        assert config.warmup_count == 0

    def test_custom_config(self):
        """Test custom pool configuration."""
        config = PoolConfig(
            max_vms=8,
            default_os=OSType.WINDOWS,
            default_tier=VMTier.MULTI_OS,
            auto_restore_snapshot="fresh",
            acquire_timeout_seconds=60.0,
            warmup_count=2,
        )

        assert config.max_vms == 8
        assert config.default_os == OSType.WINDOWS
        assert config.default_tier == VMTier.MULTI_OS
        assert config.auto_restore_snapshot == "fresh"
        assert config.warmup_count == 2


# =============================================================================
# PoolStats Tests
# =============================================================================


class TestPoolStats:
    """Tests for PoolStats dataclass."""

    def test_default_stats(self):
        """Test default pool statistics."""
        stats = PoolStats()

        assert stats.total_vms == 0
        assert stats.available_vms == 0
        assert stats.in_use_vms == 0
        assert stats.total_acquisitions == 0
        assert stats.total_releases == 0
        assert stats.failed_acquisitions == 0


# =============================================================================
# PooledVM Tests
# =============================================================================


class TestPooledVM:
    """Tests for PooledVM dataclass."""

    def test_pooled_vm_defaults(self, mock_adapter):
        """Test PooledVM default values."""
        config = VMConfig(name="test-vm")
        pooled_vm = PooledVM(adapter=mock_adapter, config=config)

        assert pooled_vm.adapter == mock_adapter
        assert pooled_vm.config == config
        assert pooled_vm.in_use is False
        assert pooled_vm.use_count == 0
        assert pooled_vm.last_used == 0.0
        assert pooled_vm.error_count == 0


# =============================================================================
# VMPool Initialization Tests
# =============================================================================


class TestVMPoolInit:
    """Tests for VMPool initialization."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        pool = VMPool()

        assert pool._config is not None
        assert pool._initialized is False
        assert len(pool._vms) == 0

    def test_init_custom_config(self, pool_config):
        """Test initialization with custom config."""
        pool = VMPool(pool_config)

        assert pool._config == pool_config
        assert pool._config.max_vms == 4

    @pytest.mark.asyncio
    async def test_initialize_success(self, pool):
        """Test successful pool initialization."""
        result = await pool.initialize()

        assert result is True
        assert pool._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, pool):
        """Test initialization is idempotent."""
        await pool.initialize()
        result = await pool.initialize()

        assert result is True

    @pytest.mark.asyncio
    async def test_initialize_with_warmup(self, mock_adapter):
        """Test initialization with pre-warmed VMs."""
        config = PoolConfig(warmup_count=2, default_tier=VMTier.HOST)
        pool = VMPool(config)

        # Mock _create_vm to return mock VMs
        async def mock_create_vm(os_type, tier, name=None):
            return PooledVM(
                adapter=mock_adapter,
                config=VMConfig(name=name or "test-vm"),
            )

        pool._create_vm = AsyncMock(side_effect=mock_create_vm)

        result = await pool.initialize()

        assert result is True
        assert len(pool._vms) == 2
        assert pool._stats.total_vms == 2
        assert pool._stats.available_vms == 2

    @pytest.mark.asyncio
    async def test_initialize_warmup_failure(self, mock_adapter):
        """Test initialization handles warmup failures gracefully."""
        config = PoolConfig(warmup_count=2)
        pool = VMPool(config)

        # First call succeeds, second fails
        call_count = 0

        async def mock_create_vm(os_type, tier, name=None):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("VM creation failed")
            return PooledVM(
                adapter=mock_adapter,
                config=VMConfig(name=name or "test-vm"),
            )

        pool._create_vm = AsyncMock(side_effect=mock_create_vm)

        result = await pool.initialize()

        # Should still initialize successfully with partial warmup
        assert result is True
        assert len(pool._vms) == 1


# =============================================================================
# VMPool Shutdown Tests
# =============================================================================


class TestVMPoolShutdown:
    """Tests for VMPool shutdown."""

    @pytest.mark.asyncio
    async def test_shutdown(self, pool, mock_adapter):
        """Test pool shutdown."""
        await pool.initialize()

        # Add a VM to the pool
        pool._vms.append(PooledVM(adapter=mock_adapter, config=VMConfig(name="test-vm")))

        await pool.shutdown()

        assert pool._initialized is False
        assert len(pool._vms) == 0
        mock_adapter.stop.assert_called_once()
        mock_adapter.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_errors(self, pool, mock_adapter):
        """Test shutdown handles VM errors gracefully."""
        await pool.initialize()

        mock_adapter.stop = AsyncMock(side_effect=Exception("Stop error"))
        pool._vms.append(PooledVM(adapter=mock_adapter, config=VMConfig(name="test-vm")))

        # Should not raise
        await pool.shutdown()

        assert pool._initialized is False
        assert len(pool._vms) == 0


# =============================================================================
# VM Acquisition Tests
# =============================================================================


class TestVMAcquisition:
    """Tests for VM acquisition."""

    @pytest.mark.asyncio
    async def test_acquire_creates_new_vm(self, pool, mock_adapter):
        """Test acquiring a VM creates a new one when pool is empty."""
        await pool.initialize()

        async def mock_create_vm(os_type, tier, name=None):
            return PooledVM(
                adapter=mock_adapter,
                config=VMConfig(name=name or "test-vm", os_type=os_type, tier=tier),
            )

        pool._create_vm = AsyncMock(side_effect=mock_create_vm)

        async with pool.acquire() as vm:
            assert vm == mock_adapter
            assert pool._stats.in_use_vms == 1
            assert pool._stats.total_acquisitions == 1

    @pytest.mark.asyncio
    async def test_acquire_reuses_available_vm(self, pool, mock_adapter):
        """Test acquiring a VM reuses available VM."""
        await pool.initialize()

        # Add an available VM
        pooled_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="test-vm", os_type=OSType.MACOS, tier=VMTier.SANDBOXED),
        )
        pool._vms.append(pooled_vm)
        pool._stats.total_vms = 1
        pool._stats.available_vms = 1

        async with pool.acquire() as vm:
            assert vm == mock_adapter
            assert pool._stats.in_use_vms == 1
            assert pool._stats.available_vms == 0

    @pytest.mark.asyncio
    async def test_acquire_releases_on_exit(self, pool, mock_adapter):
        """Test VM is released when context exits."""
        await pool.initialize()

        async def mock_create_vm(os_type, tier, name=None):
            return PooledVM(
                adapter=mock_adapter,
                config=VMConfig(name=name or "test-vm"),
            )

        pool._create_vm = AsyncMock(side_effect=mock_create_vm)

        async with pool.acquire():
            assert pool._stats.in_use_vms == 1

        # After context exit
        assert pool._stats.in_use_vms == 0
        assert pool._stats.available_vms == 1
        assert pool._stats.total_releases == 1

    @pytest.mark.asyncio
    async def test_acquire_with_specific_os(self, pool, mock_adapter):
        """Test acquiring VM with specific OS type."""
        await pool.initialize()

        async def mock_create_vm(os_type, tier, name=None):
            return PooledVM(
                adapter=mock_adapter,
                config=VMConfig(name=name or "test-vm", os_type=os_type, tier=tier),
            )

        pool._create_vm = AsyncMock(side_effect=mock_create_vm)

        async with pool.acquire(os_type=OSType.WINDOWS):
            pass

        # Verify the VM was created with Windows OS
        call_args = pool._create_vm.call_args
        assert call_args[0][0] == OSType.WINDOWS

    @pytest.mark.asyncio
    async def test_acquire_with_specific_tier(self, pool, mock_adapter):
        """Test acquiring VM with specific tier."""
        await pool.initialize()

        async def mock_create_vm(os_type, tier, name=None):
            return PooledVM(
                adapter=mock_adapter,
                config=VMConfig(name=name or "test-vm", os_type=os_type, tier=tier),
            )

        pool._create_vm = AsyncMock(side_effect=mock_create_vm)

        async with pool.acquire(tier=VMTier.MULTI_OS):
            pass

        call_args = pool._create_vm.call_args
        assert call_args[0][1] == VMTier.MULTI_OS

    @pytest.mark.asyncio
    async def test_acquire_not_initialized_raises(self, pool):
        """Test acquiring from uninitialized pool raises error."""
        with pytest.raises(RuntimeError, match="not initialized"):
            async with pool.acquire():
                pass

    @pytest.mark.asyncio
    async def test_acquire_timeout(self, mock_adapter):
        """Test acquisition timeout."""
        config = PoolConfig(max_vms=1, acquire_timeout_seconds=0.1)
        pool = VMPool(config)
        await pool.initialize()

        # Add a VM that's in use
        pooled_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="test-vm"),
            in_use=True,
        )
        pool._vms.append(pooled_vm)
        pool._stats.total_vms = 1
        pool._stats.in_use_vms = 1

        with pytest.raises(TimeoutError, match="No VM available"):
            async with pool.acquire(timeout=0.1):
                pass

        assert pool._stats.failed_acquisitions == 1


# =============================================================================
# VM Release Tests
# =============================================================================


class TestVMRelease:
    """Tests for VM release."""

    @pytest.mark.asyncio
    async def test_release_restores_snapshot(self, pool, mock_adapter):
        """Test VM release restores snapshot."""
        await pool.initialize()

        pooled_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="test-vm"),
        )
        pool._vms.append(pooled_vm)
        pool._stats.total_vms = 1
        pool._stats.available_vms = 1

        async with pool.acquire():
            pass

        # Verify snapshot was restored
        mock_adapter.list_snapshots.assert_called()
        mock_adapter.restore_snapshot.assert_called_with("clean-state")

    @pytest.mark.asyncio
    async def test_release_snapshot_not_found(self, pool, mock_adapter):
        """Test release when snapshot doesn't exist."""
        await pool.initialize()

        mock_adapter.list_snapshots = AsyncMock(return_value=["other-snapshot"])

        pooled_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="test-vm"),
        )
        pool._vms.append(pooled_vm)
        pool._stats.total_vms = 1
        pool._stats.available_vms = 1

        async with pool.acquire():
            pass

        # Should not call restore since snapshot doesn't exist
        mock_adapter.restore_snapshot.assert_not_called()

    @pytest.mark.asyncio
    async def test_release_snapshot_error(self, pool, mock_adapter):
        """Test release handles snapshot restoration error."""
        await pool.initialize()

        mock_adapter.restore_snapshot = AsyncMock(side_effect=Exception("Restore error"))

        pooled_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="test-vm"),
        )
        pool._vms.append(pooled_vm)
        pool._stats.total_vms = 1
        pool._stats.available_vms = 1

        async with pool.acquire():
            pass

        # VM should still be released
        assert pool._stats.in_use_vms == 0
        assert pooled_vm.error_count == 1

    @pytest.mark.asyncio
    async def test_release_no_auto_restore(self, mock_adapter):
        """Test release without auto restore configured."""
        config = PoolConfig(auto_restore_snapshot="")
        pool = VMPool(config)
        await pool.initialize()

        pooled_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="test-vm"),
        )
        pool._vms.append(pooled_vm)
        pool._stats.total_vms = 1
        pool._stats.available_vms = 1

        async with pool.acquire():
            pass

        # Should not attempt to restore
        mock_adapter.restore_snapshot.assert_not_called()


# =============================================================================
# Pool Statistics Integration Tests
# =============================================================================


class TestPoolStatsIntegration:
    """Integration tests for pool statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self, pool, mock_adapter):
        """Test getting pool statistics."""
        await pool.initialize()

        pooled_vm1 = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="vm1"),
            in_use=False,
        )
        pooled_vm2 = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="vm2"),
            in_use=True,
        )
        pool._vms.extend([pooled_vm1, pooled_vm2])

        stats = await pool.get_stats()

        assert stats.total_vms == 2
        assert stats.available_vms == 1
        assert stats.in_use_vms == 1

    def test_stats_property(self, pool):
        """Test stats property returns current stats."""
        stats = pool.stats

        assert isinstance(stats, PoolStats)


# =============================================================================
# Concurrent Acquisition Tests
# =============================================================================


class TestConcurrentAcquisition:
    """Tests for concurrent VM acquisition."""

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self, mock_adapter):
        """Test acquiring multiple VMs concurrently."""
        config = PoolConfig(max_vms=4)
        pool = VMPool(config)
        await pool.initialize()

        async def mock_create_vm(os_type, tier, name=None):
            return PooledVM(
                adapter=mock_adapter,
                config=VMConfig(name=name or "test-vm"),
            )

        pool._create_vm = AsyncMock(side_effect=mock_create_vm)

        acquired_vms = []

        async def acquire_task():
            async with pool.acquire() as vm:
                acquired_vms.append(vm)
                await asyncio.sleep(0.01)  # Brief hold

        # Acquire 3 VMs concurrently
        await asyncio.gather(
            acquire_task(),
            acquire_task(),
            acquire_task(),
        )

        assert len(acquired_vms) == 3
        assert pool._stats.total_acquisitions == 3
        assert pool._stats.total_releases == 3

    @pytest.mark.asyncio
    async def test_acquire_waits_for_available(self, mock_adapter):
        """Test acquisition waits for VM to become available."""
        config = PoolConfig(max_vms=1, acquire_timeout_seconds=5.0)
        pool = VMPool(config)
        await pool.initialize()

        async def mock_create_vm(os_type, tier, name=None):
            return PooledVM(
                adapter=mock_adapter,
                config=VMConfig(name=name or "test-vm"),
            )

        pool._create_vm = AsyncMock(side_effect=mock_create_vm)

        results = []

        async def first_task():
            async with pool.acquire():
                results.append("first_acquired")
                await asyncio.sleep(0.1)
            results.append("first_released")

        async def second_task():
            await asyncio.sleep(0.05)  # Ensure first task acquires first
            async with pool.acquire():
                results.append("second_acquired")

        await asyncio.gather(first_task(), second_task())

        # Second task should wait for first to release
        assert results == ["first_acquired", "first_released", "second_acquired"]


# =============================================================================
# VM Selection Tests
# =============================================================================


class TestVMSelection:
    """Tests for VM selection logic."""

    @pytest.mark.asyncio
    async def test_find_available_vm_by_os(self, pool, mock_adapter):
        """Test finding VM by OS type."""
        await pool.initialize()

        mac_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="mac-vm", os_type=OSType.MACOS, tier=VMTier.SANDBOXED),
            in_use=False,
        )
        win_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="win-vm", os_type=OSType.WINDOWS, tier=VMTier.MULTI_OS),
            in_use=False,
        )
        pool._vms.extend([mac_vm, win_vm])

        found = await pool._find_available_vm(os_type=OSType.WINDOWS)

        assert found == win_vm

    @pytest.mark.asyncio
    async def test_find_available_vm_by_tier(self, pool, mock_adapter):
        """Test finding VM by tier."""
        await pool.initialize()

        tier1_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="host-vm", os_type=OSType.MACOS, tier=VMTier.HOST),
            in_use=False,
        )
        tier2_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="sandbox-vm", os_type=OSType.MACOS, tier=VMTier.SANDBOXED),
            in_use=False,
        )
        pool._vms.extend([tier1_vm, tier2_vm])

        found = await pool._find_available_vm(tier=VMTier.SANDBOXED)

        assert found == tier2_vm

    @pytest.mark.asyncio
    async def test_find_available_vm_skips_in_use(self, pool, mock_adapter):
        """Test finding VM skips in-use VMs."""
        await pool.initialize()

        in_use_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="in-use-vm", os_type=OSType.MACOS, tier=VMTier.SANDBOXED),
            in_use=True,
        )
        available_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="available-vm", os_type=OSType.MACOS, tier=VMTier.SANDBOXED),
            in_use=False,
        )
        pool._vms.extend([in_use_vm, available_vm])

        found = await pool._find_available_vm()

        assert found == available_vm

    @pytest.mark.asyncio
    async def test_find_available_vm_none_match(self, pool, mock_adapter):
        """Test finding VM when none match criteria."""
        await pool.initialize()

        mac_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="mac-vm", os_type=OSType.MACOS, tier=VMTier.SANDBOXED),
            in_use=False,
        )
        pool._vms.append(mac_vm)

        found = await pool._find_available_vm(os_type=OSType.WINDOWS)

        assert found is None


# =============================================================================
# Global Pool Singleton Tests
# =============================================================================


class TestGlobalPool:
    """Tests for global pool singleton functions."""

    @pytest.mark.asyncio
    async def test_get_vm_pool_creates_singleton(self):
        """Test get_vm_pool creates singleton."""
        # Clean up any existing pool
        await shutdown_vm_pool()

        pool1 = await get_vm_pool()
        pool2 = await get_vm_pool()

        assert pool1 is pool2
        assert pool1._initialized is True

        # Clean up
        await shutdown_vm_pool()

    @pytest.mark.asyncio
    async def test_get_vm_pool_with_config(self):
        """Test get_vm_pool uses config on first call."""
        await shutdown_vm_pool()

        config = PoolConfig(max_vms=8)
        pool = await get_vm_pool(config)

        assert pool._config.max_vms == 8

        # Clean up
        await shutdown_vm_pool()

    @pytest.mark.asyncio
    async def test_shutdown_vm_pool(self):
        """Test shutdown_vm_pool clears singleton."""
        await shutdown_vm_pool()

        pool1 = await get_vm_pool()
        await shutdown_vm_pool()

        # Should create a new pool
        pool2 = await get_vm_pool()

        assert pool1 is not pool2

        # Clean up
        await shutdown_vm_pool()


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_acquire_updates_use_count(self, pool, mock_adapter):
        """Test acquisition updates use count."""
        await pool.initialize()

        pooled_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="test-vm", os_type=OSType.MACOS, tier=VMTier.SANDBOXED),
        )
        pool._vms.append(pooled_vm)
        pool._stats.total_vms = 1
        pool._stats.available_vms = 1

        async with pool.acquire():
            assert pooled_vm.use_count == 1

        async with pool.acquire():
            assert pooled_vm.use_count == 2

    @pytest.mark.asyncio
    async def test_acquire_updates_last_used(self, pool, mock_adapter):
        """Test acquisition updates last_used timestamp."""
        await pool.initialize()

        pooled_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="test-vm", os_type=OSType.MACOS, tier=VMTier.SANDBOXED),
        )
        pool._vms.append(pooled_vm)
        pool._stats.total_vms = 1
        pool._stats.available_vms = 1

        initial_last_used = pooled_vm.last_used

        async with pool.acquire():
            assert pooled_vm.last_used > initial_last_used

    @pytest.mark.asyncio
    async def test_vm_creation_failure(self, pool):
        """Test handling of VM creation failure."""
        await pool.initialize()

        pool._create_vm = AsyncMock(side_effect=RuntimeError("VM creation failed"))

        with pytest.raises(RuntimeError, match="VM creation failed"):
            async with pool.acquire():
                pass

    @pytest.mark.asyncio
    async def test_release_signals_waiting_acquirers(self, mock_adapter):
        """Test that release signals waiting acquirers."""
        config = PoolConfig(max_vms=1, acquire_timeout_seconds=5.0)
        pool = VMPool(config)
        await pool.initialize()

        pooled_vm = PooledVM(
            adapter=mock_adapter,
            config=VMConfig(name="test-vm", os_type=OSType.MACOS, tier=VMTier.SANDBOXED),
            in_use=True,
        )
        pool._vms.append(pooled_vm)
        pool._stats.total_vms = 1
        pool._stats.in_use_vms = 1

        acquire_event = asyncio.Event()

        async def waiting_task():
            async with pool.acquire():
                acquire_event.set()

        # Start waiting task
        task = asyncio.create_task(waiting_task())

        # Give it a moment to start waiting
        await asyncio.sleep(0.05)

        # Release the VM
        await pool._release_vm(pooled_vm)

        # Wait for acquisition to complete
        await asyncio.wait_for(acquire_event.wait(), timeout=1.0)

        await task
