"""Tests for file manager."""

import pytest
from pathlib import Path
import tempfile
import asyncio

from kagami.core.resources import FileManager, FileMode
from kagami.core.resources.file_manager import (
    read_file,
    write_file,
    append_file,
    read_binary,
    write_binary,
)
from kagami.core.resources.tracker import get_resource_tracker, reset_tracker


@pytest.fixture
def temp_dir():
    """Create temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(autouse=True)
def reset_resource_tracker():
    """Reset tracker before each test."""
    reset_tracker()
    yield
    reset_tracker()


class TestFileManager:
    """Test FileManager class."""

    @pytest.mark.asyncio
    async def test_read_file(self, temp_dir):
        """Test reading a file."""
        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello, World!")

        # Read file
        async with FileManager(test_file, FileMode.READ) as f:
            content = await f.read()
            assert content == "Hello, World!"

    @pytest.mark.asyncio
    async def test_write_file(self, temp_dir):
        """Test writing a file."""
        test_file = temp_dir / "test.txt"

        # Write file
        async with FileManager(test_file, FileMode.WRITE) as f:
            await f.write("Test content")

        # Verify
        assert test_file.read_text() == "Test content"

    @pytest.mark.asyncio
    async def test_append_file(self, temp_dir):
        """Test appending to a file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Line 1\n")

        # Append
        async with FileManager(test_file, FileMode.APPEND) as f:
            await f.write("Line 2\n")

        # Verify
        assert test_file.read_text() == "Line 1\nLine 2\n"

    @pytest.mark.asyncio
    async def test_binary_read_write(self, temp_dir):
        """Test binary file operations."""
        test_file = temp_dir / "test.bin"
        test_data = b"\x00\x01\x02\x03\x04"

        # Write binary
        async with FileManager(test_file, FileMode.WRITE_BINARY) as f:
            await f.write(test_data)

        # Read binary
        async with FileManager(test_file, FileMode.READ_BINARY) as f:
            content = await f.read()
            assert content == test_data

    @pytest.mark.asyncio
    async def test_readline(self, temp_dir):
        """Test reading lines."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\n")

        async with FileManager(test_file, FileMode.READ) as f:
            line1 = await f.readline()
            line2 = await f.readline()
            assert line1 == "Line 1\n"
            assert line2 == "Line 2\n"

    @pytest.mark.asyncio
    async def test_readlines(self, temp_dir):
        """Test reading all lines."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\n")

        async with FileManager(test_file, FileMode.READ) as f:
            lines = await f.readlines()
            assert len(lines) == 3
            assert lines[0] == "Line 1\n"
            assert lines[2] == "Line 3\n"

    @pytest.mark.asyncio
    async def test_cleanup_on_error(self, temp_dir):
        """Test that file is cleaned up on error."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test")

        tracker = get_resource_tracker()
        initial_count = len(tracker.get_resources("file"))

        try:
            async with FileManager(test_file, FileMode.READ) as f:
                await f.read()
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify cleanup happened
        final_count = len(tracker.get_resources("file"))
        assert final_count == initial_count

    @pytest.mark.asyncio
    async def test_resource_tracking(self, temp_dir):
        """Test that resources are tracked."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Test")

        tracker = get_resource_tracker()

        async with FileManager(test_file, FileMode.READ) as f:
            # Should be tracked
            resources = tracker.get_resources("file")
            assert len(resources) > 0

        # Should be untracked
        resources = tracker.get_resources("file")
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_convenience_read_file(self, temp_dir):
        """Test convenience read function."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello")

        content = await read_file(test_file)
        assert content == "Hello"

    @pytest.mark.asyncio
    async def test_convenience_write_file(self, temp_dir):
        """Test convenience write function."""
        test_file = temp_dir / "test.txt"

        await write_file(test_file, "Hello")
        assert test_file.read_text() == "Hello"

    @pytest.mark.asyncio
    async def test_convenience_append_file(self, temp_dir):
        """Test convenience append function."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("Hello")

        await append_file(test_file, " World")
        assert test_file.read_text() == "Hello World"

    @pytest.mark.asyncio
    async def test_convenience_binary(self, temp_dir):
        """Test convenience binary functions."""
        test_file = temp_dir / "test.bin"
        test_data = b"\x00\x01\x02"

        await write_binary(test_file, test_data)
        content = await read_binary(test_file)
        assert content == test_data

    @pytest.mark.asyncio
    async def test_create_parent_directories(self, temp_dir):
        """Test that parent directories are created."""
        test_file = temp_dir / "subdir" / "nested" / "test.txt"

        async with FileManager(test_file, FileMode.WRITE) as f:
            await f.write("Test")

        assert test_file.exists()
        assert test_file.read_text() == "Test"

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, temp_dir):
        """Test that bytes read/written are tracked."""
        test_file = temp_dir / "test.txt"

        async with FileManager(test_file, FileMode.WRITE) as f:
            await f.write("Hello World")
            assert f._bytes_written == 11

        async with FileManager(test_file, FileMode.READ) as f:
            await f.read()
            assert f._bytes_read == 11
