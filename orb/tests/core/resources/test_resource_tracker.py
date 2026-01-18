"""Tests for resource tracker."""

import pytest
import asyncio
import time

from kagami.core.resources.tracker import (
    ResourceTracker,
    get_resource_tracker,
    track_resource,
    untrack_resource,
    check_for_leaks,
    cleanup_leaked_resources,
    get_resource_stats,
    reset_tracker,
)


@pytest.fixture
def tracker():
    """Create a fresh tracker."""
    reset_tracker()
    tracker = get_resource_tracker()
    tracker.clear()
    return tracker


class TestResourceTracker:
    """Test ResourceTracker class."""

    def test_track_resource(self, tracker):
        """Test tracking a resource."""
        resource_id = tracker.track("file", "/tmp/test.txt", {"mode": "r"})

        assert resource_id == "/tmp/test.txt"
        assert len(tracker.get_resources()) == 1

        resource = tracker.get_resources()[0]
        assert resource.resource_type == "file"
        assert resource.resource_id == "/tmp/test.txt"
        assert resource.metadata["mode"] == "r"

    def test_untrack_resource(self, tracker):
        """Test untracking a resource."""
        tracker.track("file", "/tmp/test.txt")
        assert len(tracker.get_resources()) == 1

        result = tracker.untrack("/tmp/test.txt")
        assert result is True
        assert len(tracker.get_resources()) == 0

        # Untracking again should return False
        result = tracker.untrack("/tmp/test.txt")
        assert result is False

    def test_get_stats(self, tracker):
        """Test getting statistics."""
        tracker.track("file", "file1.txt")
        tracker.track("connection", "conn1")
        tracker.track("connection", "conn2")

        stats = tracker.get_stats()
        assert stats["total_tracked"] == 3
        assert stats["total_created"] == 3
        assert stats["total_cleaned"] == 0
        assert stats["by_type"]["file"] == 1
        assert stats["by_type"]["connection"] == 2

        tracker.untrack("file1.txt")

        stats = tracker.get_stats()
        assert stats["total_tracked"] == 2
        assert stats["total_cleaned"] == 1

    def test_detect_leaks_by_age(self, tracker):
        """Test leak detection by age threshold."""
        # Track resources
        tracker.track("file", "old_file.txt")
        time.sleep(0.1)
        tracker.track("file", "new_file.txt")

        # No leaks with high threshold
        leaks = tracker.detect_leaks(threshold=1.0)
        assert len(leaks) == 0

        # Both should leak with low threshold
        leaks = tracker.detect_leaks(threshold=0.05)
        assert len(leaks) == 2

    def test_detect_leaks_by_type(self, tracker):
        """Test leak detection filtered by type."""
        tracker.track("file", "file1.txt")
        tracker.track("connection", "conn1")

        # Only file leaks
        leaks = tracker.detect_leaks(threshold=0.0, resource_type="file")
        assert len(leaks) == 1
        assert leaks[0].resource_type == "file"

        # Only connection leaks
        leaks = tracker.detect_leaks(threshold=0.0, resource_type="connection")
        assert len(leaks) == 1
        assert leaks[0].resource_type == "connection"

    def test_get_resources_by_type(self, tracker):
        """Test getting resources filtered by type."""
        tracker.track("file", "file1.txt")
        tracker.track("file", "file2.txt")
        tracker.track("connection", "conn1")

        files = tracker.get_resources("file")
        assert len(files) == 2

        connections = tracker.get_resources("connection")
        assert len(connections) == 1

    @pytest.mark.asyncio
    async def test_cleanup_all(self, tracker):
        """Test cleaning up all resources."""
        # Track resources
        tracker.track("test", "res1")
        tracker.track("test", "res2")
        tracker.track("test", "res3")

        # Register cleanup callback
        cleaned = []
        def cleanup_fn(resource):
            cleaned.append(resource.resource_id)

        tracker.register_cleanup_callback("test", cleanup_fn)

        # Force cleanup
        count = await tracker.cleanup_all(force=True)
        assert count == 3
        assert len(cleaned) == 3
        assert len(tracker.get_resources()) == 0

    @pytest.mark.asyncio
    async def test_cleanup_only_old_resources(self, tracker):
        """Test cleanup only cleans old resources."""
        # Track old resource
        tracker.track("test", "old")
        time.sleep(0.1)

        # Track new resource
        tracker.track("test", "new")

        # Cleanup with threshold
        tracker.set_leak_threshold(0.05)

        cleaned = []
        def cleanup_fn(resource):
            cleaned.append(resource.resource_id)

        tracker.register_cleanup_callback("test", cleanup_fn)

        # Should only clean old resource
        count = await tracker.cleanup_all(force=False)
        assert count == 1
        assert "old" in cleaned
        assert "new" not in cleaned

    def test_convenience_functions(self, tracker):
        """Test convenience functions."""
        # Track
        resource_id = track_resource("file", "/tmp/test.txt", {"mode": "r"})
        assert resource_id == "/tmp/test.txt"

        # Get stats
        stats = get_resource_stats()
        assert stats["total_tracked"] == 1

        # Untrack
        result = untrack_resource("/tmp/test.txt")
        assert result is True

        stats = get_resource_stats()
        assert stats["total_tracked"] == 0

    @pytest.mark.asyncio
    async def test_check_for_leaks(self, tracker):
        """Test check_for_leaks function."""
        tracker.track("file", "file1.txt")
        tracker.track("file", "file2.txt")

        # Check for leaks
        leaks = await check_for_leaks(threshold=0.0, log=False)
        assert len(leaks) == 2

    @pytest.mark.asyncio
    async def test_cleanup_leaked_resources(self, tracker):
        """Test cleanup_leaked_resources function."""
        tracker.track("test", "res1")
        tracker.track("test", "res2")

        cleaned = []
        def cleanup_fn(resource):
            cleaned.append(resource.resource_id)

        tracker.register_cleanup_callback("test", cleanup_fn)

        count = await cleanup_leaked_resources(force=True)
        assert count == 2
        assert len(cleaned) == 2

    def test_clear(self, tracker):
        """Test clearing all resources."""
        tracker.track("file", "file1.txt")
        tracker.track("file", "file2.txt")

        tracker.clear()

        assert len(tracker.get_resources()) == 0
        stats = tracker.get_stats()
        assert stats["total_created"] == 0
        assert stats["total_cleaned"] == 0
