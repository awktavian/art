"""File handle management with automatic cleanup.

Provides safe file operations with guaranteed resource cleanup,
even in error conditions.
"""

import logging
from enum import Enum
from pathlib import Path
from typing import Any, Literal

import aiofiles

from kagami.core.resources.tracker import track_resource

logger = logging.getLogger(__name__)


class FileMode(str, Enum):
    """File access modes."""

    READ = "r"
    WRITE = "w"
    APPEND = "a"
    READ_BINARY = "rb"
    WRITE_BINARY = "wb"
    APPEND_BINARY = "ab"
    READ_WRITE = "r+"
    READ_WRITE_BINARY = "rb+"


class FileManager:
    """Managed file handle with automatic cleanup.

    Features:
    - Automatic resource cleanup via context manager
    - Resource leak tracking
    - Error handling with proper cleanup
    - Support for both sync and async file operations
    - Metrics collection

    Usage:
        # Async usage
        async with FileManager(path, FileMode.READ) as f:
            data = await f.read()

        # Auto-cleanup on error
        async with FileManager(path, FileMode.WRITE) as f:
            await f.write(data)
            # Cleanup happens even if exception raised

    Attributes:
        path: Path to file
        mode: File access mode
        encoding: File encoding (text modes only)
        handle: Underlying file handle
    """

    def __init__(
        self,
        path: str | Path,
        mode: FileMode | str = FileMode.READ,
        encoding: str = "utf-8",
        buffering: int = -1,
    ) -> None:
        """Initialize file manager.

        Args:
            path: Path to file
            mode: File access mode
            encoding: File encoding for text modes
            buffering: Buffer size (-1 for default)
        """
        self.path = Path(path)
        self.mode = FileMode(mode) if isinstance(mode, str) else mode
        self.encoding = encoding if "b" not in self.mode.value else None
        self.buffering = buffering
        self.handle: Any = None
        self._resource_id: str | None = None
        self._opened = False
        self._bytes_read = 0
        self._bytes_written = 0

    async def __aenter__(self) -> "FileManager":
        """Async context manager entry."""
        await self.open()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        """Async context manager exit with cleanup."""
        await self.close()
        return False

    async def open(self) -> None:
        """Open the file handle."""
        if self._opened:
            return

        try:
            # Create parent directories if writing
            if any(m in self.mode.value for m in ["w", "a"]):
                self.path.parent.mkdir(parents=True, exist_ok=True)

            # Open file
            if self.encoding:
                self.handle = await aiofiles.open(
                    self.path,
                    mode=self.mode.value,
                    encoding=self.encoding,
                    buffering=self.buffering,
                )
            else:
                self.handle = await aiofiles.open(
                    self.path,
                    mode=self.mode.value,
                    buffering=self.buffering,
                )

            self._opened = True

            # Track resource
            self._resource_id = track_resource(
                resource_type="file",
                resource_id=str(self.path),
                metadata={
                    "mode": self.mode.value,
                    "encoding": self.encoding,
                    "size": self.path.stat().st_size if self.path.exists() else 0,
                },
            )

            logger.debug(f"Opened file: {self.path} (mode={self.mode.value})")

        except Exception as e:
            logger.error(f"Failed to open file {self.path}: {e}")
            raise

    async def close(self) -> None:
        """Close the file handle with cleanup."""
        if not self._opened:
            return

        cleanup_error = None
        try:
            if self.handle:
                # Ensure data is flushed
                try:
                    await self.handle.flush()
                except Exception as e:
                    logger.warning(f"Failed to flush file {self.path}: {e}")

                # Close handle
                try:
                    await self.handle.close()
                except Exception as e:
                    cleanup_error = e
                    logger.error(f"Failed to close file {self.path}: {e}")
                finally:
                    self.handle = None

            # Log metrics
            if self._bytes_read > 0 or self._bytes_written > 0:
                logger.debug(
                    f"File {self.path}: read={self._bytes_read} bytes, "
                    f"written={self._bytes_written} bytes"
                )

        finally:
            self._opened = False

            # Untrack resource
            if self._resource_id:
                from kagami.core.resources.tracker import get_resource_tracker

                tracker = get_resource_tracker()
                tracker.untrack(self._resource_id)
                self._resource_id = None

            if cleanup_error:
                raise cleanup_error

    async def read(self, size: int = -1) -> str | bytes:
        """Read from file.

        Args:
            size: Number of bytes/chars to read (-1 for all)

        Returns:
            File contents
        """
        if not self._opened:
            raise RuntimeError("File not opened")

        data = await self.handle.read(size)
        self._bytes_read += len(data)
        return data

    async def readline(self) -> str | bytes:
        """Read a single line from file.

        Returns:
            Single line from file
        """
        if not self._opened:
            raise RuntimeError("File not opened")

        line = await self.handle.readline()
        self._bytes_read += len(line)
        return line

    async def readlines(self) -> list[str] | list[bytes]:
        """Read all lines from file.

        Returns:
            List of lines
        """
        if not self._opened:
            raise RuntimeError("File not opened")

        lines = await self.handle.readlines()
        self._bytes_read += sum(len(line) for line in lines)
        return lines

    async def write(self, data: str | bytes) -> int:
        """Write to file.

        Args:
            data: Data to write

        Returns:
            Number of bytes/chars written
        """
        if not self._opened:
            raise RuntimeError("File not opened")

        result = await self.handle.write(data)
        self._bytes_written += len(data)
        return result

    async def writelines(self, lines: list[str] | list[bytes]) -> None:
        """Write multiple lines to file.

        Args:
            lines: Lines to write
        """
        if not self._opened:
            raise RuntimeError("File not opened")

        await self.handle.writelines(lines)
        self._bytes_written += sum(len(line) for line in lines)

    async def flush(self) -> None:
        """Flush file buffer."""
        if not self._opened:
            raise RuntimeError("File not opened")

        await self.handle.flush()

    async def seek(self, offset: int, whence: int = 0) -> int:
        """Seek to position in file.

        Args:
            offset: Byte offset
            whence: Reference point (0=start, 1=current, 2=end)

        Returns:
            New absolute position
        """
        if not self._opened:
            raise RuntimeError("File not opened")

        return await self.handle.seek(offset, whence)

    async def tell(self) -> int:
        """Get current file position.

        Returns:
            Current byte offset
        """
        if not self._opened:
            raise RuntimeError("File not opened")

        return await self.handle.tell()

    @property
    def closed(self) -> bool:
        """Check if file is closed."""
        return not self._opened

    @property
    def name(self) -> str:
        """Get file name."""
        return str(self.path)

    def __repr__(self) -> str:
        """String representation."""
        status = "open" if self._opened else "closed"
        return f"FileManager({self.path}, mode={self.mode.value}, {status})"


async def read_file(path: str | Path, encoding: str = "utf-8") -> str:
    """Convenience function to read entire file.

    Args:
        path: Path to file
        encoding: File encoding

    Returns:
        File contents
    """
    async with FileManager(path, FileMode.READ, encoding=encoding) as f:
        return await f.read()


async def write_file(path: str | Path, data: str, encoding: str = "utf-8") -> None:
    """Convenience function to write entire file.

    Args:
        path: Path to file
        data: Data to write
        encoding: File encoding
    """
    async with FileManager(path, FileMode.WRITE, encoding=encoding) as f:
        await f.write(data)


async def append_file(path: str | Path, data: str, encoding: str = "utf-8") -> None:
    """Convenience function to append to file.

    Args:
        path: Path to file
        data: Data to append
        encoding: File encoding
    """
    async with FileManager(path, FileMode.APPEND, encoding=encoding) as f:
        await f.write(data)


async def read_binary(path: str | Path) -> bytes:
    """Convenience function to read binary file.

    Args:
        path: Path to file

    Returns:
        File contents as bytes
    """
    async with FileManager(path, FileMode.READ_BINARY) as f:
        return await f.read()


async def write_binary(path: str | Path, data: bytes) -> None:
    """Convenience function to write binary file.

    Args:
        path: Path to file
        data: Data to write
    """
    async with FileManager(path, FileMode.WRITE_BINARY) as f:
        await f.write(data)
