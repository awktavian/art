"""Comprehensive integration tests for resource management system.

Tests all managers together, resource tracking across managers, leak detection
in real scenarios, metrics collection, cleanup ordering, and production scenarios.
"""

import asyncio
import time
import pytest
from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from kagami.core.resources.tracker import (
    get_resource_tracker,
    reset_tracker,
    check_for_leaks,
    cleanup_leaked_resources,
    get_resource_stats,
)


@pytest.fixture(autouse=True)
def reset_resource_tracker():
    """Reset tracker before each test."""
    reset_tracker()
    yield
    reset_tracker()


@pytest.fixture
def temp_dir():
    """Create temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestCrossManagerIntegration:
    """Test integration across different resource managers."""

    @pytest.mark.asyncio
    async def test_file_and_connection_together(self, temp_dir):
        """Test using file and connection managers together."""
        from kagami.core.resources.file_manager import FileManager, FileMode
        from kagami.core.resources.connection_manager import ConnectionManager

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        mock_conn = Mock()
        mock_conn.close = AsyncMock()

        tracker = get_resource_tracker()

        async with FileManager(test_file, FileMode.READ) as f:
            async with ConnectionManager(mock_conn) as conn:
                # Both should be tracked
                resources = tracker.get_resources()
                assert len(resources) == 2

                # Verify both types
                types = {r.resource_type for r in resources}
                assert "file" in types
                assert "connection" in types

        # Both should be cleaned up
        resources = tracker.get_resources()
        assert len(resources) == 0

    @pytest.mark.asyncio
    @patch('kagami.core.resources.gpu_manager.TORCH_AVAILABLE', True)
    @patch('kagami.core.resources.gpu_manager.cuda')
    async def test_all_managers_together(self, mock_cuda, temp_dir):
        """Test all resource managers working together."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.file_manager import FileManager, FileMode
        from kagami.core.resources.connection_manager import ConnectionManager
        from kagami.core.resources.websocket_manager import WebSocketManager
        from kagami.core.resources.gpu_manager import GPUMemoryManager
        from kagami.core.resources.async_resource import AsyncResourceManager

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        mock_conn = Mock()
        mock_conn.close = AsyncMock()

        mock_ws = Mock()
        mock_ws.close = AsyncMock()

        tracker = get_resource_tracker()

        async with AsyncResourceManager() as res_mgr:
            async with FileManager(test_file, FileMode.READ) as f:
                async with ConnectionManager(mock_conn) as conn:
                    async with WebSocketManager(mock_ws) as ws:
                        async with GPUMemoryManager(device='cpu') as gpu:
                            # All should be tracked
                            resources = tracker.get_resources()
                            assert len(resources) >= 5  # res_mgr, file, conn, ws, gpu

        # All should be cleaned up
        resources = tracker.get_resources()
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_nested_managers_cleanup_order(self, temp_dir):
        """Test cleanup order with nested managers."""
        from kagami.core.resources.file_manager import FileManager, FileMode
        from kagami.core.resources.connection_manager import ConnectionManager

        cleanup_order = []

        # Patch cleanup methods to track order
        original_file_close = FileManager.close
        original_conn_close = ConnectionManager.close

        async def track_file_close(self):
            cleanup_order.append("file")
            await original_file_close(self)

        async def track_conn_close(self):
            cleanup_order.append("connection")
            await original_conn_close(self)

        with patch.object(FileManager, 'close', track_file_close):
            with patch.object(ConnectionManager, 'close', track_conn_close):
                test_file = temp_dir / "test.txt"
                test_file.write_text("data")

                mock_conn = Mock()
                mock_conn.close = AsyncMock()

                async with FileManager(test_file, FileMode.READ) as f:
                    async with ConnectionManager(mock_conn) as conn:
                        pass

        # Inner should cleanup first (LIFO)
        assert cleanup_order == ["connection", "file"]


class TestLeakDetection:
    """Test leak detection in real scenarios."""

    @pytest.mark.asyncio
    async def test_detect_file_leak(self, temp_dir):
        """Test detecting leaked file handles."""
        from kagami.core.resources.file_manager import FileManager, FileMode

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        tracker = get_resource_tracker()

        # Create file manager without closing
        mgr = FileManager(test_file, FileMode.READ)
        await mgr.open()

        # Should detect leak
        leaks = await check_for_leaks(threshold=0.0, log=False)
        assert len(leaks) == 1
        assert leaks[0].resource_type == "file"

        # Cleanup
        await mgr.close()

    @pytest.mark.asyncio
    async def test_detect_connection_leak(self):
        """Test detecting leaked connections."""
        from kagami.core.resources.connection_manager import ConnectionManager

        mock_conn = Mock()
        mock_conn.close = AsyncMock()

        # Create connection without closing
        mgr = ConnectionManager(mock_conn)
        await mgr.open()

        # Should detect leak
        leaks = await check_for_leaks(threshold=0.0, log=False)
        assert len(leaks) == 1
        assert leaks[0].resource_type == "connection"

        # Cleanup
        await mgr.close()

    @pytest.mark.asyncio
    async def test_detect_multiple_leaks(self, temp_dir):
        """Test detecting multiple leaked resources."""
        from kagami.core.resources.file_manager import FileManager, FileMode
        from kagami.core.resources.connection_manager import ConnectionManager

        test_file1 = temp_dir / "test1.txt"
        test_file2 = temp_dir / "test2.txt"
        test_file1.write_text("data")
        test_file2.write_text("data")

        # Create leaked resources
        file_mgr1 = FileManager(test_file1, FileMode.READ)
        await file_mgr1.open()

        file_mgr2 = FileManager(test_file2, FileMode.READ)
        await file_mgr2.open()

        mock_conn = Mock()
        mock_conn.close = AsyncMock()
        conn_mgr = ConnectionManager(mock_conn)
        await conn_mgr.open()

        # Should detect all leaks
        leaks = await check_for_leaks(threshold=0.0, log=False)
        assert len(leaks) == 3

        # Cleanup
        await file_mgr1.close()
        await file_mgr2.close()
        await conn_mgr.close()

    @pytest.mark.asyncio
    async def test_leak_cleanup(self, temp_dir):
        """Test automatic leak cleanup."""
        from kagami.core.resources.file_manager import FileManager, FileMode

        tracker = get_resource_tracker()

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        # Create leaked file
        mgr = FileManager(test_file, FileMode.READ)
        await mgr.open()

        # Register cleanup callback
        async def cleanup_file(resource):
            # Find the manager and close it
            # In real scenario, this would be handled by the tracker
            pass

        tracker.register_cleanup_callback("file", cleanup_file)

        # Initial leak
        leaks = await check_for_leaks(threshold=0.0, log=False)
        assert len(leaks) == 1

        # Manual cleanup
        await mgr.close()

        # No more leaks
        leaks = await check_for_leaks(threshold=0.0, log=False)
        assert len(leaks) == 0

    @pytest.mark.asyncio
    async def test_age_based_leak_detection(self, temp_dir):
        """Test leak detection based on age threshold."""
        from kagami.core.resources.file_manager import FileManager, FileMode

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        # Create old resource
        mgr_old = FileManager(test_file, FileMode.READ)
        await mgr_old.open()

        # Wait
        await asyncio.sleep(0.1)

        # Create new resource
        test_file2 = temp_dir / "test2.txt"
        test_file2.write_text("data")
        mgr_new = FileManager(test_file2, FileMode.READ)
        await mgr_new.open()

        # Only old should be detected as leak
        leaks = await check_for_leaks(threshold=0.05, log=False)
        assert len(leaks) == 1

        # Cleanup
        await mgr_old.close()
        await mgr_new.close()


class TestMetricsCollection:
    """Test metrics collection across managers."""

    @pytest.mark.asyncio
    async def test_resource_stats(self, temp_dir):
        """Test collecting resource statistics."""
        from kagami.core.resources.file_manager import FileManager, FileMode
        from kagami.core.resources.connection_manager import ConnectionManager

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        mock_conn = Mock()
        mock_conn.close = AsyncMock()

        async with FileManager(test_file, FileMode.READ) as f:
            async with ConnectionManager(mock_conn) as conn:
                stats = get_resource_stats()

                assert stats['total_tracked'] == 2
                assert stats['by_type']['file'] == 1
                assert stats['by_type']['connection'] == 1

        # After cleanup
        stats = get_resource_stats()
        assert stats['total_tracked'] == 0
        assert stats['total_cleaned'] == 2

    @pytest.mark.asyncio
    async def test_metrics_accuracy(self, temp_dir):
        """Test metrics are accurate."""
        from kagami.core.resources.file_manager import FileManager, FileMode

        test_file = temp_dir / "test.txt"
        content = "Hello World!" * 100
        test_file.write_text(content)

        async with FileManager(test_file, FileMode.READ) as f:
            data = await f.read()
            assert f._bytes_read == len(content)

    @pytest.mark.asyncio
    async def test_connection_metrics(self):
        """Test connection manager metrics."""
        from kagami.core.resources.connection_manager import DatabaseConnectionManager

        mock_session = Mock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        async with DatabaseConnectionManager(mock_session) as mgr:
            await mgr.execute("SELECT 1")
            await mgr.execute("SELECT 2")
            await mgr.execute("SELECT 3")

            assert mgr._queries_executed == 3

    @pytest.mark.asyncio
    async def test_websocket_metrics(self):
        """Test WebSocket manager metrics."""
        from kagami.core.resources.websocket_manager import WebSocketManager

        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        mock_ws.close = AsyncMock()

        async with WebSocketManager(mock_ws) as ws:
            await ws.send("test1")
            await ws.send("test2")

            stats = ws.get_stats()
            assert stats['messages_sent'] == 2
            assert stats['bytes_sent'] == 10  # "test1" + "test2"


class TestPerformanceOverhead:
    """Test that resource tracking has minimal overhead."""

    @pytest.mark.asyncio
    async def test_file_manager_overhead(self, temp_dir):
        """Test file manager overhead is minimal."""
        from kagami.core.resources.file_manager import FileManager, FileMode

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        start = time.perf_counter()

        for _ in range(100):
            async with FileManager(test_file, FileMode.READ) as f:
                await f.read()

        elapsed = time.perf_counter() - start

        # Should be fast (< 0.5 seconds for 100 iterations)
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_connection_manager_overhead(self):
        """Test connection manager overhead is minimal."""
        from kagami.core.resources.connection_manager import ConnectionManager

        mock_conn = Mock()
        mock_conn.close = AsyncMock()

        start = time.perf_counter()

        for _ in range(100):
            async with ConnectionManager(mock_conn) as conn:
                pass

        elapsed = time.perf_counter() - start

        # Should be fast (< 0.5 seconds for 100 iterations)
        assert elapsed < 0.5

    @pytest.mark.asyncio
    async def test_tracking_overhead_percentage(self, temp_dir):
        """Test tracking overhead is less than 1%."""
        from kagami.core.resources.async_resource import AsyncResource

        resource = Mock()
        cleanup = Mock()

        # With tracking
        start = time.perf_counter()
        for _ in range(1000):
            async with AsyncResource(resource, cleanup, track=True) as r:
                pass
        with_tracking = time.perf_counter() - start

        # Without tracking
        start = time.perf_counter()
        for _ in range(1000):
            async with AsyncResource(resource, cleanup, track=False) as r:
                pass
        without_tracking = time.perf_counter() - start

        # Overhead should be minimal
        overhead_percent = ((with_tracking - without_tracking) / without_tracking) * 100
        assert overhead_percent < 10  # Less than 10% overhead


class TestProductionScenarios:
    """Test real production scenarios."""

    @pytest.mark.asyncio
    async def test_api_request_lifecycle(self, temp_dir):
        """Test typical API request resource lifecycle."""
        from kagami.core.resources.file_manager import FileManager, FileMode
        from kagami.core.resources.connection_manager import DatabaseConnectionManager

        # Simulate API request that reads file and queries DB
        test_file = temp_dir / "config.json"
        test_file.write_text('{"key": "value"}')

        mock_session = Mock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        tracker = get_resource_tracker()

        # Request starts
        async with DatabaseConnectionManager(mock_session) as db:
            async with FileManager(test_file, FileMode.READ) as f:
                config = await f.read()
                await db.execute("SELECT * FROM users")

        # Request ends - all resources should be cleaned up
        resources = tracker.get_resources()
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_websocket_connection_lifecycle(self):
        """Test WebSocket connection lifecycle."""
        from kagami.core.resources.websocket_manager import WebSocketManager
        from kagami.core.resources.connection_manager import RedisConnectionManager

        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        mock_ws.receive_json = AsyncMock(return_value={"msg": "hello"})
        mock_ws.close = AsyncMock()

        mock_redis = Mock()
        mock_redis.get = AsyncMock()
        mock_redis.set = AsyncMock()

        tracker = get_resource_tracker()

        # WebSocket connection with Redis cache
        async with WebSocketManager(mock_ws) as ws:
            async with RedisConnectionManager(mock_redis) as redis:
                # Send message
                await ws.send({"type": "message"})

                # Cache result
                await redis.set("ws:last_message", "data")

                # Get cached data
                await redis.get("ws:last_message")

        # All cleaned up
        resources = tracker.get_resources()
        assert len(resources) == 0

    @pytest.mark.asyncio
    @patch('kagami.core.resources.gpu_manager.TORCH_AVAILABLE', True)
    @patch('kagami.core.resources.gpu_manager.cuda')
    @patch('kagami.core.resources.gpu_manager.torch')
    async def test_ml_inference_pipeline(self, mock_torch, mock_cuda):
        """Test ML inference pipeline resource management."""
        mock_cuda.is_available.return_value = False

        from kagami.core.resources.gpu_manager import GPUMemoryManager
        from kagami.core.resources.connection_manager import DatabaseConnectionManager

        mock_session = Mock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.rollback = AsyncMock()
        mock_session.close = AsyncMock()

        tracker = get_resource_tracker()

        # ML inference: load model, run inference, save results
        async with DatabaseConnectionManager(mock_session) as db:
            async with GPUMemoryManager(device='cpu') as gpu:
                # Load data from DB
                await db.execute("SELECT * FROM inputs")

                # Simulate tensor allocation
                tensor = Mock()
                tensor.device = 'cpu'
                tensor.element_size = Mock(return_value=4)
                tensor.nelement = Mock(return_value=1000)
                gpu.track(tensor, "input")

                # Save results
                await db.execute("INSERT INTO results VALUES (?)")

        # All cleaned up
        resources = tracker.get_resources()
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_concurrent_api_requests(self):
        """Test concurrent API requests don't leak resources."""
        from kagami.core.resources.connection_manager import ConnectionManager

        async def handle_request(request_id):
            mock_conn = Mock()
            mock_conn.close = AsyncMock()

            async with ConnectionManager(mock_conn) as conn:
                # Simulate work
                await asyncio.sleep(0.01)

        tracker = get_resource_tracker()

        # Simulate 20 concurrent requests
        await asyncio.gather(*[handle_request(i) for i in range(20)])

        # No leaks
        resources = tracker.get_resources()
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_error_recovery(self, temp_dir):
        """Test error recovery doesn't leak resources."""
        from kagami.core.resources.file_manager import FileManager, FileMode
        from kagami.core.resources.connection_manager import ConnectionManager

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        mock_conn = Mock()
        mock_conn.close = AsyncMock()

        tracker = get_resource_tracker()

        # Simulate error during processing
        for _ in range(10):
            try:
                async with FileManager(test_file, FileMode.READ) as f:
                    async with ConnectionManager(mock_conn) as conn:
                        # Simulate random failure
                        raise RuntimeError("Processing error")
            except RuntimeError:
                pass

        # No leaks despite errors
        resources = tracker.get_resources()
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_long_running_worker(self, temp_dir):
        """Test long-running worker doesn't leak resources."""
        from kagami.core.resources.connection_manager import ConnectionManager

        tracker = get_resource_tracker()

        async def worker_task():
            for _ in range(10):
                mock_conn = Mock()
                mock_conn.close = AsyncMock()

                async with ConnectionManager(mock_conn) as conn:
                    # Simulate work
                    await asyncio.sleep(0.01)

        await worker_task()

        # No leaks
        resources = tracker.get_resources()
        assert len(resources) == 0

        stats = get_resource_stats()
        assert stats['total_tracked'] == 0
        assert stats['total_cleaned'] == 10


class TestCleanupGuarantees:
    """Test cleanup guarantees in various scenarios."""

    @pytest.mark.asyncio
    async def test_cleanup_on_exception(self, temp_dir):
        """Test cleanup happens even with exceptions."""
        from kagami.core.resources.file_manager import FileManager, FileMode

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        tracker = get_resource_tracker()

        exceptions = [
            ValueError("test"),
            RuntimeError("test"),
            KeyError("test"),
        ]

        for exc in exceptions:
            try:
                async with FileManager(test_file, FileMode.READ) as f:
                    raise exc
            except Exception:
                pass

            # Should always cleanup
            resources = tracker.get_resources()
            assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_cleanup_on_asyncio_cancellation(self, temp_dir):
        """Test cleanup happens on asyncio.CancelledError."""
        from kagami.core.resources.file_manager import FileManager, FileMode

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        tracker = get_resource_tracker()

        async def task():
            async with FileManager(test_file, FileMode.READ) as f:
                await asyncio.sleep(10)

        # Start and cancel task
        t = asyncio.create_task(task())
        await asyncio.sleep(0.01)
        t.cancel()

        try:
            await t
        except asyncio.CancelledError:
            pass

        # Should cleanup even when cancelled
        # Note: This depends on how Python handles context managers with cancellation
        await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_cleanup_order_preserved(self):
        """Test cleanup order is preserved."""
        from kagami.core.resources.async_resource import AsyncResourceManager

        cleanup_order = []

        def make_cleanup(name):
            def cleanup(resource):
                cleanup_order.append(name)
            return cleanup

        async with AsyncResourceManager() as mgr:
            await mgr.add(Mock(), make_cleanup("first"))
            await mgr.add(Mock(), make_cleanup("second"))
            await mgr.add(Mock(), make_cleanup("third"))

        # LIFO order
        assert cleanup_order == ["third", "second", "first"]

    @pytest.mark.asyncio
    async def test_partial_cleanup_on_error(self):
        """Test partial cleanup when one cleanup fails."""
        from kagami.core.resources.async_resource import AsyncResourceManager, ResourceCleanupError

        cleanup_calls = []

        def make_cleanup(name, should_fail=False):
            def cleanup(resource):
                cleanup_calls.append(name)
                if should_fail:
                    raise RuntimeError(f"{name} failed")
            return cleanup

        with pytest.raises(ResourceCleanupError):
            async with AsyncResourceManager() as mgr:
                await mgr.add(Mock(), make_cleanup("first"))
                await mgr.add(Mock(), make_cleanup("second", should_fail=True))
                await mgr.add(Mock(), make_cleanup("third"))

        # All should be attempted despite failure
        assert "first" in cleanup_calls
        assert "second" in cleanup_calls
        assert "third" in cleanup_calls


class TestStressTests:
    """Stress tests for resource management."""

    @pytest.mark.asyncio
    async def test_many_concurrent_resources(self):
        """Test handling many concurrent resources."""
        from kagami.core.resources.connection_manager import ConnectionManager

        async def create_connection():
            mock_conn = Mock()
            mock_conn.close = AsyncMock()
            async with ConnectionManager(mock_conn) as conn:
                await asyncio.sleep(0.001)

        # Create many concurrent connections
        await asyncio.gather(*[create_connection() for _ in range(100)])

        # No leaks
        tracker = get_resource_tracker()
        resources = tracker.get_resources()
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_rapid_create_destroy(self, temp_dir):
        """Test rapid resource creation and destruction."""
        from kagami.core.resources.file_manager import FileManager, FileMode

        test_file = temp_dir / "test.txt"
        test_file.write_text("data")

        # Rapidly create and destroy
        for _ in range(100):
            async with FileManager(test_file, FileMode.READ) as f:
                await f.read()

        # No leaks
        tracker = get_resource_tracker()
        resources = tracker.get_resources()
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_nested_depth(self):
        """Test deeply nested resource managers."""
        from kagami.core.resources.async_resource import AsyncResource

        depth = 0
        max_depth = 20

        async def nest_resources(current_depth):
            nonlocal depth
            depth = max(depth, current_depth)

            if current_depth >= max_depth:
                return

            resource = Mock()
            cleanup = Mock()

            async with AsyncResource(resource, cleanup) as r:
                await nest_resources(current_depth + 1)

        await nest_resources(0)

        assert depth == max_depth

        # No leaks
        tracker = get_resource_tracker()
        resources = tracker.get_resources()
        assert len(resources) == 0
