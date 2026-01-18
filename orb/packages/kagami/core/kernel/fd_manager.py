"""File Descriptor Manager for K os Kernel.

Provides POSIX-style file descriptor management for syscalls.

Created: November 15, 2025
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FileMode(str, Enum):
    """File open modes."""

    READ = "r"
    WRITE = "w"
    APPEND = "a"
    READ_WRITE = "r+"


@dataclass
class FileDescriptor:
    """File descriptor metadata."""

    fd: int
    path: Path
    mode: FileMode
    position: int = 0
    file_handle: Any = None


class FileDescriptorManager:
    """Manages file descriptors for kernel syscalls.

    Provides POSIX-style file operations with async support.
    """

    def __init__(self) -> None:
        self._descriptors: dict[int, FileDescriptor] = {}
        self._next_fd = 1000  # Start at 1000 to avoid conflicts with system FDs
        self._lock = asyncio.Lock()

    async def open_file(self, path: str, mode: str = "r") -> int:
        """Open file and return file descriptor.

        Args:
            path: File path
            mode: Open mode (r, w, a, r+)

        Returns:
            File descriptor number

        Raises:
            FileNotFoundError: If file doesn't exist (in read mode)
            PermissionError: If access denied
        """
        async with self._lock:
            path_obj = Path(path).resolve()

            # Validate mode
            try:
                file_mode = FileMode(mode)
            except ValueError:
                raise ValueError(f"Invalid file mode: {mode}") from None

            # Check file exists for read modes
            if file_mode in (FileMode.READ, FileMode.READ_WRITE):
                if not path_obj.exists():
                    raise FileNotFoundError(f"File not found: {path}") from None

            # Open file handle
            try:
                handle: Any
                if file_mode == FileMode.READ:
                    handle = open(path_obj, "rb")
                elif file_mode == FileMode.WRITE:
                    handle = open(path_obj, "wb")
                elif file_mode == FileMode.APPEND:
                    handle = open(path_obj, "ab")
                elif file_mode == FileMode.READ_WRITE:
                    handle = open(path_obj, "r+b")
                else:
                    raise ValueError(f"Unsupported mode: {file_mode}")

            except PermissionError:
                raise PermissionError(f"Access denied: {path}") from None

            # Allocate file descriptor
            fd = self._next_fd
            self._next_fd += 1

            descriptor = FileDescriptor(
                fd=fd,
                path=path_obj,
                mode=file_mode,
                file_handle=handle,
            )

            self._descriptors[fd] = descriptor

            logger.debug(f"Opened {path} as FD {fd} (mode={mode})")

            return fd

    async def read_file(self, fd: int, size: int = -1) -> bytes:
        """Read from file descriptor.

        Args:
            fd: File descriptor
            size: Bytes to read (-1 = all)

        Returns:
            Bytes read

        Raises:
            ValueError: If FD not found or not readable
        """
        async with self._lock:
            if fd not in self._descriptors:
                raise ValueError(f"Invalid file descriptor: {fd}")

            descriptor = self._descriptors[fd]

            if descriptor.mode not in (FileMode.READ, FileMode.READ_WRITE):
                raise ValueError(f"File descriptor {fd} not open for reading")

            if not descriptor.file_handle:
                raise ValueError(f"File descriptor {fd} has no handle")

            # Read from handle
            try:
                if size == -1:
                    data = descriptor.file_handle.read()
                else:
                    data = descriptor.file_handle.read(size)

                descriptor.position = descriptor.file_handle.tell()

                return bytes(data)

            except Exception as e:
                raise RuntimeError(f"Read failed on FD {fd}: {e}") from None

    async def write_file(self, fd: int, data: bytes) -> int:
        """Write to file descriptor.

        Args:
            fd: File descriptor
            data: Bytes to write

        Returns:
            Bytes written

        Raises:
            ValueError: If FD not found or not writable
        """
        async with self._lock:
            if fd not in self._descriptors:
                raise ValueError(f"Invalid file descriptor: {fd}")

            descriptor = self._descriptors[fd]

            if descriptor.mode not in (FileMode.WRITE, FileMode.APPEND, FileMode.READ_WRITE):
                raise ValueError(f"File descriptor {fd} not open for writing")

            if not descriptor.file_handle:
                raise ValueError(f"File descriptor {fd} has no handle")

            # Write to handle
            try:
                bytes_written = descriptor.file_handle.write(data)
                descriptor.position = descriptor.file_handle.tell()

                return int(bytes_written)

            except Exception as e:
                raise RuntimeError(f"Write failed on FD {fd}: {e}") from None

    async def close_file(self, fd: int) -> bool:
        """Close file descriptor.

        Args:
            fd: File descriptor

        Returns:
            True if closed, False if not found
        """
        async with self._lock:
            if fd not in self._descriptors:
                return False

            descriptor = self._descriptors[fd]

            # Close file handle
            if descriptor.file_handle:
                try:
                    descriptor.file_handle.close()
                except Exception as e:
                    logger.warning(f"Error closing FD {fd}: {e}")

            # Remove from registry
            del self._descriptors[fd]

            logger.debug(f"Closed FD {fd}")

            return True

    async def list_descriptors(self) -> list[dict[str, Any]]:
        """List all open file descriptors.

        Returns:
            List of FD info
        """
        async with self._lock:
            descriptors = []

            for descriptor in self._descriptors.values():
                descriptors.append(
                    {
                        "fd": descriptor.fd,
                        "path": str(descriptor.path),
                        "mode": descriptor.mode.value,
                        "position": descriptor.position,
                    }
                )

            return descriptors

    def get_stats(self) -> dict[str, Any]:
        """Get FD manager statistics.

        Returns:
            Stats dict[str, Any]
        """
        return {
            "open_descriptors": len(self._descriptors),
            "next_fd": self._next_fd,
        }


# Global singleton
_fd_manager: FileDescriptorManager | None = None


def get_fd_manager() -> FileDescriptorManager:
    """Get global file descriptor manager.

    Returns:
        FileDescriptorManager singleton
    """
    global _fd_manager

    if _fd_manager is None:
        _fd_manager = FileDescriptorManager()

    return _fd_manager


__all__ = [
    "FileDescriptor",
    "FileDescriptorManager",
    "FileMode",
    "get_fd_manager",
]
