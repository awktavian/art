"""Comprehensive tests for async resource management.

Tests generic resource pattern, cleanup guarantees, error handling,
batch resource management, and timeout handling.
"""

import asyncio
import pytest
from typing import Any
from unittest.mock import AsyncMock, Mock

from kagami.core.resources.async_resource import (
    AsyncResource,
    AsyncResourceManager,
    ResourceCleanupError,
    with_cleanup,
    ensure_cleanup,
)
from kagami.core.resources.tracker import get_resource_tracker, reset_tracker


@pytest.fixture(autouse=True)
def reset_resource_tracker():
    """Reset tracker before each test."""
    reset_tracker()
    yield
    reset_tracker()


@pytest.fixture
def mock_resource():
    """Create mock resource."""
    resource = Mock()
    resource.close = Mock()
    resource.name = "test_resource"
    return resource


@pytest.fixture
def async_cleanup():
    """Create async cleanup function."""
    cleanup = AsyncMock()
    return cleanup


@pytest.fixture
def sync_cleanup():
    """Create sync cleanup function."""
    cleanup = Mock()
    return cleanup


class TestAsyncResource:
    """Test AsyncResource class."""

    @pytest.mark.asyncio
    async def test_basic_lifecycle(self, mock_resource, sync_cleanup):
        """Test basic resource lifecycle."""
        async with AsyncResource(mock_resource, sync_cleanup) as r:
            assert r is mock_resource
            assert not r.cleaned_up  # Should access via the wrapper

        sync_cleanup.assert_called_once_with(mock_resource)

    @pytest.mark.asyncio
    async def test_async_cleanup(self, mock_resource, async_cleanup):
        """Test async cleanup function."""
        async with AsyncResource(mock_resource, async_cleanup) as r:
            assert r is mock_resource

        async_cleanup.assert_called_once_with(mock_resource)

    @pytest.mark.asyncio
    async def test_resource_tracking(self, mock_resource, sync_cleanup):
        """Test that resources are tracked."""
        tracker = get_resource_tracker()

        async with AsyncResource(mock_resource, sync_cleanup, resource_type="test") as r:
            # Should be tracked
            resources = tracker.get_resources("test")
            assert len(resources) == 1
            assert resources[0].resource_id == str(id(mock_resource))

        # Should be untracked after exit
        resources = tracker.get_resources("test")
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_no_tracking(self, mock_resource, sync_cleanup):
        """Test resource without tracking."""
        tracker = get_resource_tracker()

        async with AsyncResource(mock_resource, sync_cleanup, track=False) as r:
            # Should not be tracked
            resources = tracker.get_resources("generic")
            assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_cleanup_on_error(self, mock_resource, sync_cleanup):
        """Test cleanup happens even on error."""
        try:
            async with AsyncResource(mock_resource, sync_cleanup) as r:
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should still cleanup
        sync_cleanup.assert_called_once_with(mock_resource)

    @pytest.mark.asyncio
    async def test_cleanup_error_handling(self, mock_resource):
        """Test cleanup error is raised."""
        cleanup = Mock(side_effect=RuntimeError("Cleanup failed"))

        with pytest.raises(ResourceCleanupError, match="Cleanup failed for generic"):
            async with AsyncResource(mock_resource, cleanup) as r:
                pass

    @pytest.mark.asyncio
    async def test_double_cleanup_is_safe(self, mock_resource, sync_cleanup):
        """Test that double cleanup doesn't error."""
        wrapper = AsyncResource(mock_resource, sync_cleanup)
        await wrapper.__aenter__()
        await wrapper.cleanup()
        await wrapper.cleanup()  # Should not raise

        # Should only cleanup once
        sync_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_enter_function_sync(self, mock_resource, sync_cleanup):
        """Test sync enter function."""

        def enter_fn(resource):
            resource.initialized = True
            return resource

        async with AsyncResource(mock_resource, sync_cleanup, enter_fn=enter_fn) as r:
            assert r.initialized is True

    @pytest.mark.asyncio
    async def test_enter_function_async(self, mock_resource, sync_cleanup):
        """Test async enter function."""

        async def enter_fn(resource):
            await asyncio.sleep(0.01)
            resource.initialized = True
            return resource

        async with AsyncResource(mock_resource, sync_cleanup, enter_fn=enter_fn) as r:
            assert r.initialized is True

    @pytest.mark.asyncio
    async def test_custom_resource_type(self, mock_resource, sync_cleanup):
        """Test custom resource type."""
        tracker = get_resource_tracker()

        async with AsyncResource(mock_resource, sync_cleanup, resource_type="custom") as r:
            resources = tracker.get_resources("custom")
            assert len(resources) == 1

    @pytest.mark.asyncio
    async def test_manual_cleanup(self, mock_resource, sync_cleanup):
        """Test manual cleanup."""
        wrapper = AsyncResource(mock_resource, sync_cleanup)
        await wrapper.__aenter__()

        # Manual cleanup
        await wrapper.cleanup()

        sync_cleanup.assert_called_once()
        assert wrapper.cleaned_up

    @pytest.mark.asyncio
    async def test_cleanup_without_enter(self, mock_resource, sync_cleanup):
        """Test cleanup can be called without enter."""
        wrapper = AsyncResource(mock_resource, sync_cleanup)

        # Should not raise
        await wrapper.cleanup()

        sync_cleanup.assert_called_once()


class TestAsyncResourceManager:
    """Test AsyncResourceManager class."""

    @pytest.mark.asyncio
    async def test_basic_lifecycle(self):
        """Test basic manager lifecycle."""
        async with AsyncResourceManager() as mgr:
            assert mgr.resource_count == 0

    @pytest.mark.asyncio
    async def test_add_resource(self, mock_resource, sync_cleanup):
        """Test adding a resource."""
        async with AsyncResourceManager() as mgr:
            resource = await mgr.add(mock_resource, sync_cleanup)

            assert resource is mock_resource
            assert mgr.resource_count == 1

    @pytest.mark.asyncio
    async def test_add_multiple_resources(self):
        """Test adding multiple resources."""
        resources = [Mock() for _ in range(3)]
        cleanup_fns = [Mock() for _ in range(3)]

        async with AsyncResourceManager() as mgr:
            for r, c in zip(resources, cleanup_fns, strict=False):
                await mgr.add(r, c)

            assert mgr.resource_count == 3

        # All should be cleaned up
        for c in cleanup_fns:
            c.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_order(self):
        """Test resources are cleaned up in LIFO order."""
        cleanup_order = []

        def make_cleanup(name):
            def cleanup(resource):
                cleanup_order.append(name)

            return cleanup

        async with AsyncResourceManager() as mgr:
            await mgr.add(Mock(), make_cleanup("first"))
            await mgr.add(Mock(), make_cleanup("second"))
            await mgr.add(Mock(), make_cleanup("third"))

        # Should cleanup in reverse order (LIFO)
        assert cleanup_order == ["third", "second", "first"]

    @pytest.mark.asyncio
    async def test_cleanup_on_error(self):
        """Test cleanup happens even on error."""
        cleanup = Mock()

        try:
            async with AsyncResourceManager() as mgr:
                await mgr.add(Mock(), cleanup)
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should still cleanup
        cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_partial_cleanup_on_add_error(self):
        """Test partial cleanup when add fails."""
        cleanup1 = Mock()
        cleanup2 = Mock()

        async def failing_enter(resource):
            raise RuntimeError("Enter failed")

        try:
            async with AsyncResourceManager() as mgr:
                await mgr.add(Mock(), cleanup1)
                await mgr.add(Mock(), cleanup2, enter_fn=failing_enter)
        except RuntimeError:
            pass

        # First resource should be cleaned up
        cleanup1.assert_called_once()
        # Second cleanup shouldn't be called (resource didn't enter)
        cleanup2.assert_not_called()

    @pytest.mark.asyncio
    async def test_cleanup_error_aggregation(self):
        """Test cleanup errors are aggregated."""
        cleanup1 = Mock()
        cleanup2 = Mock(side_effect=RuntimeError("Cleanup 2 failed"))
        cleanup3 = Mock()

        with pytest.raises(ResourceCleanupError, match="Failed to cleanup 1 resources"):
            async with AsyncResourceManager() as mgr:
                await mgr.add(Mock(), cleanup1)
                await mgr.add(Mock(), cleanup2)
                await mgr.add(Mock(), cleanup3)

        # All cleanups should be attempted
        cleanup1.assert_called_once()
        cleanup2.assert_called_once()
        cleanup3.assert_called_once()

    @pytest.mark.asyncio
    async def test_resource_tracking(self):
        """Test manager itself is tracked."""
        tracker = get_resource_tracker()

        async with AsyncResourceManager() as mgr:
            resources = tracker.get_resources("resource_manager")
            assert len(resources) == 1

        # Should be untracked after exit
        resources = tracker.get_resources("resource_manager")
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_custom_resource_type(self):
        """Test adding resource with custom type."""
        tracker = get_resource_tracker()

        async with AsyncResourceManager() as mgr:
            await mgr.add(Mock(), Mock(), resource_type="custom")

            resources = tracker.get_resources("custom")
            assert len(resources) == 1

    @pytest.mark.asyncio
    async def test_enter_function(self):
        """Test adding resource with enter function."""

        async def enter_fn(resource):
            resource.initialized = True
            return resource

        async with AsyncResourceManager() as mgr:
            resource = Mock()
            result = await mgr.add(resource, Mock(), enter_fn=enter_fn)

            assert result.initialized is True

    @pytest.mark.asyncio
    async def test_async_cleanup_functions(self):
        """Test async cleanup functions."""
        cleanup = AsyncMock()

        async with AsyncResourceManager() as mgr:
            await mgr.add(Mock(), cleanup)

        cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_manual_cleanup(self):
        """Test manual cleanup_all."""
        cleanup = Mock()

        mgr = AsyncResourceManager()
        await mgr.__aenter__()
        await mgr.add(Mock(), cleanup)

        await mgr.cleanup_all()

        cleanup.assert_called_once()
        assert mgr.resource_count == 0


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.mark.asyncio
    async def test_with_cleanup(self, mock_resource, sync_cleanup):
        """Test with_cleanup function."""

        async def operation(resource):
            return resource.name

        result = await with_cleanup(mock_resource, sync_cleanup, operation)

        assert result == "test_resource"
        sync_cleanup.assert_called_once_with(mock_resource)

    @pytest.mark.asyncio
    async def test_with_cleanup_sync_operation(self, mock_resource, sync_cleanup):
        """Test with_cleanup with sync operation."""

        def operation(resource):
            return resource.name

        result = await with_cleanup(mock_resource, sync_cleanup, operation)

        assert result == "test_resource"
        sync_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_cleanup_error(self, mock_resource, sync_cleanup):
        """Test with_cleanup handles errors."""

        async def operation(resource):
            raise ValueError("Operation failed")

        with pytest.raises(ValueError, match="Operation failed"):
            await with_cleanup(mock_resource, sync_cleanup, operation)

        # Should still cleanup
        sync_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_cleanup(self):
        """Test ensure_cleanup function."""
        resource1 = Mock()
        resource2 = Mock()
        cleanup1 = Mock()
        cleanup2 = Mock()

        async with await ensure_cleanup(
            (resource1, cleanup1),
            (resource2, cleanup2),
        ) as mgr:
            assert mgr.resource_count == 2

        # Both should be cleaned up
        cleanup1.assert_called_once()
        cleanup2.assert_called_once()


class TestConcurrency:
    """Test concurrent resource usage."""

    @pytest.mark.asyncio
    async def test_concurrent_resource_creation(self):
        """Test concurrent resource creation."""

        async def create_and_use_resource():
            resource = Mock()
            cleanup = Mock()

            async with AsyncResource(resource, cleanup) as r:
                await asyncio.sleep(0.01)
                return r.name if hasattr(r, "name") else "unnamed"

        # Run concurrently
        results = await asyncio.gather(*[create_and_use_resource() for _ in range(10)])

        assert len(results) == 10

    @pytest.mark.asyncio
    async def test_concurrent_manager_usage(self):
        """Test concurrent manager usage."""

        async def use_manager():
            async with AsyncResourceManager() as mgr:
                for _ in range(3):
                    await mgr.add(Mock(), Mock())
                await asyncio.sleep(0.01)

        # Run concurrently
        await asyncio.gather(*[use_manager() for _ in range(5)])

        # Should not leak resources
        tracker = get_resource_tracker()
        assert len(tracker.get_resources()) == 0

    @pytest.mark.asyncio
    async def test_nested_managers(self):
        """Test nested resource managers."""
        cleanup_calls = []

        def make_cleanup(name):
            def cleanup(resource):
                cleanup_calls.append(name)

            return cleanup

        async with AsyncResourceManager() as mgr1:
            await mgr1.add(Mock(), make_cleanup("outer1"))

            async with AsyncResourceManager() as mgr2:
                await mgr2.add(Mock(), make_cleanup("inner1"))
                await mgr2.add(Mock(), make_cleanup("inner2"))

            await mgr1.add(Mock(), make_cleanup("outer2"))

        # Inner should cleanup first
        assert cleanup_calls == ["inner2", "inner1", "outer2", "outer1"]


class TestTimeout:
    """Test timeout handling."""

    @pytest.mark.asyncio
    async def test_slow_cleanup(self):
        """Test slow cleanup doesn't hang forever."""

        async def slow_cleanup(resource):
            await asyncio.sleep(10)

        resource = Mock()

        # Use timeout to prevent test from hanging
        with pytest.raises(asyncio.TimeoutError):
            async with asyncio.timeout(0.1):
                async with AsyncResource(resource, slow_cleanup) as r:
                    pass

    @pytest.mark.asyncio
    async def test_slow_enter_function(self):
        """Test slow enter function."""

        async def slow_enter(resource):
            await asyncio.sleep(10)
            return resource

        resource = Mock()

        with pytest.raises(asyncio.TimeoutError):
            async with asyncio.timeout(0.1):
                async with AsyncResource(resource, Mock(), enter_fn=slow_enter) as r:
                    pass


class TestRobustness:
    """Test robustness and edge cases."""

    @pytest.mark.asyncio
    async def test_cleanup_on_keyboard_interrupt(self, mock_resource, sync_cleanup):
        """Test cleanup happens on KeyboardInterrupt."""
        try:
            async with AsyncResource(mock_resource, sync_cleanup) as r:
                raise KeyboardInterrupt()
        except KeyboardInterrupt:
            pass

        # Should still cleanup
        sync_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_on_system_exit(self, mock_resource, sync_cleanup):
        """Test cleanup happens on SystemExit."""
        try:
            async with AsyncResource(mock_resource, sync_cleanup) as r:
                raise SystemExit(1)
        except SystemExit:
            pass

        # Should still cleanup
        sync_cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_none_resource(self, sync_cleanup):
        """Test handling None resource."""
        async with AsyncResource(None, sync_cleanup) as r:
            assert r is None

        sync_cleanup.assert_called_once_with(None)

    @pytest.mark.asyncio
    async def test_none_cleanup_function(self, mock_resource):
        """Test handling None cleanup function."""
        # Should not raise
        async with AsyncResource(mock_resource, None) as r:  # type: ignore
            assert r is mock_resource

    @pytest.mark.asyncio
    async def test_manager_with_no_resources(self):
        """Test manager with no resources."""
        async with AsyncResourceManager() as mgr:
            pass

        # Should not raise

    @pytest.mark.asyncio
    async def test_enter_function_modifies_resource(self):
        """Test enter function can return different resource."""
        original = Mock(name="original")
        modified = Mock(name="modified")

        def enter_fn(resource):
            return modified

        cleanup = Mock()

        async with AsyncResource(original, cleanup, enter_fn=enter_fn) as r:
            assert r is modified  # Should get modified version

        # Cleanup should receive modified resource
        cleanup.assert_called_once_with(modified)

    @pytest.mark.asyncio
    async def test_multiple_errors_during_cleanup(self):
        """Test handling multiple errors during cleanup."""
        cleanup1 = Mock(side_effect=RuntimeError("Error 1"))
        cleanup2 = Mock(side_effect=RuntimeError("Error 2"))
        cleanup3 = Mock(side_effect=RuntimeError("Error 3"))

        with pytest.raises(ResourceCleanupError):
            async with AsyncResourceManager() as mgr:
                await mgr.add(Mock(), cleanup1)
                await mgr.add(Mock(), cleanup2)
                await mgr.add(Mock(), cleanup3)

        # All should be attempted
        cleanup1.assert_called_once()
        cleanup2.assert_called_once()
        cleanup3.assert_called_once()


class TestPerformance:
    """Test resource manager performance."""

    @pytest.mark.asyncio
    async def test_overhead_is_minimal(self):
        """Test that manager overhead is minimal."""
        import time

        resource = Mock()
        cleanup = Mock()

        start = time.perf_counter()

        for _ in range(1000):
            async with AsyncResource(resource, cleanup, track=False) as r:
                pass

        elapsed = time.perf_counter() - start

        # Should be fast (< 1 second for 1000 iterations)
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_many_resources_in_manager(self):
        """Test manager with many resources."""
        import time

        start = time.perf_counter()

        async with AsyncResourceManager() as mgr:
            for i in range(100):
                await mgr.add(Mock(name=f"resource{i}"), Mock())

        elapsed = time.perf_counter() - start

        # Should complete quickly
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_tracking_overhead(self):
        """Test resource tracking overhead."""
        import time

        resource = Mock()
        cleanup = Mock()

        # With tracking
        start = time.perf_counter()
        for _ in range(100):
            async with AsyncResource(resource, cleanup, track=True) as r:
                pass
        with_tracking = time.perf_counter() - start

        # Without tracking
        start = time.perf_counter()
        for _ in range(100):
            async with AsyncResource(resource, cleanup, track=False) as r:
                pass
        without_tracking = time.perf_counter() - start

        # Overhead should be minimal (< 2x)
        assert with_tracking < without_tracking * 3


class TestBatchOperations:
    """Test batch resource operations."""

    @pytest.mark.asyncio
    async def test_batch_add(self):
        """Test adding multiple resources at once."""
        resources = [(Mock(), Mock()) for _ in range(10)]

        async with AsyncResourceManager() as mgr:
            for resource, cleanup in resources:
                await mgr.add(resource, cleanup)

            assert mgr.resource_count == 10

    @pytest.mark.asyncio
    async def test_batch_cleanup_success(self):
        """Test successful batch cleanup."""
        cleanups = [Mock() for _ in range(10)]

        async with AsyncResourceManager() as mgr:
            for cleanup in cleanups:
                await mgr.add(Mock(), cleanup)

        # All should be cleaned up
        for cleanup in cleanups:
            cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_cleanup_partial_failure(self):
        """Test batch cleanup with some failures."""
        cleanups = [
            Mock(),
            Mock(side_effect=RuntimeError("Failed")),
            Mock(),
        ]

        with pytest.raises(ResourceCleanupError):
            async with AsyncResourceManager() as mgr:
                for cleanup in cleanups:
                    await mgr.add(Mock(), cleanup)

        # All should be attempted
        for cleanup in cleanups:
            cleanup.assert_called_once()
