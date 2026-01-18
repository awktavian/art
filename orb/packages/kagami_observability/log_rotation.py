"""Log rotation and compression for Kagami.

Provides configurable log rotation strategies:
- Time-based rotation (daily, hourly)
- Size-based rotation (max file size)
- Automatic compression of old logs (gzip)
- Retention policy (max backup count)

Created: December 27, 2025
"""

from __future__ import annotations

import gzip
import logging
import os
import shutil
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)


class CompressingTimedRotatingFileHandler(TimedRotatingFileHandler):
    """TimedRotatingFileHandler with automatic gzip compression.

    Rotates logs based on time interval and compresses old log files
    to save disk space. Supports all standard rotation intervals:
    - 'S': Seconds
    - 'M': Minutes
    - 'H': Hours
    - 'D': Days
    - 'midnight': Daily at midnight
    - 'W0'-'W6': Weekly on specific day (0=Monday)
    """

    def __init__(
        self,
        filename: str | Path,
        when: str = "midnight",
        interval: int = 1,
        backup_count: int = 7,
        encoding: str | None = "utf-8",
        delay: bool = False,
        utc: bool = False,
        at_time: any | None = None,  # type: ignore[valid-type]
        compress: bool = True,
    ) -> None:
        """Initialize rotating file handler with compression.

        Args:
            filename: Log file path
            when: Rotation interval ('midnight', 'H', 'D', etc.)
            interval: Rotation interval multiplier
            backup_count: Number of backup files to keep (0 = unlimited)
            encoding: File encoding
            delay: Defer file opening until first emit
            utc: Use UTC time for rotation
            at_time: Specific time for daily rotation (datetime.time)
            compress: Enable gzip compression of rotated files
        """
        super().__init__(
            filename=str(filename),
            when=when,
            interval=interval,
            backupCount=backup_count,
            encoding=encoding,
            delay=delay,
            utc=utc,
            atTime=at_time,
        )
        self.compress = compress

    def doRollover(self) -> None:
        """Perform log rotation and compress old file.

        Overrides parent doRollover to add compression step.
        """
        # Close current file
        if self.stream:
            self.stream.close()
            self.stream = None  # type: ignore[assignment]

        # Get the time that this sequence started at and make it a TimeTuple
        current_time = int(time.time())
        dst_now = time.localtime(current_time)[-1]
        t = self.rolloverAt - self.interval
        if self.utc:
            time_tuple = time.gmtime(t)
        else:
            time_tuple = time.localtime(t)
            dst_then = time_tuple[-1]
            if dst_now != dst_then:
                if dst_now:
                    addend = 3600
                else:
                    addend = -3600
                time_tuple = time.localtime(t + addend)

        # Build the rotated filename
        dfn = self.rotation_filename(
            f"{self.baseFilename}.{time.strftime(self.suffix, time_tuple)}"
        )

        # Rotate the file
        if os.path.exists(self.baseFilename):
            if os.path.exists(dfn):
                os.remove(dfn)
            self.rotate(self.baseFilename, dfn)

            # Compress the rotated file
            if self.compress:
                self._compress_file(dfn)

        # Delete old backup files
        if self.backupCount > 0:
            self._delete_old_backups()

        # Open new file
        if not self.delay:
            self.stream = self._open()

        # Update rollover time
        new_rollover_at = self.computeRollover(current_time)
        while new_rollover_at <= current_time:
            new_rollover_at = new_rollover_at + self.interval

        # If DST changes and midnight or weekly rollover, adjust
        if (self.when == "MIDNIGHT" or self.when.startswith("W")) and not self.utc:
            dst_at_rollover = time.localtime(new_rollover_at)[-1]
            if dst_now != dst_at_rollover:
                if not dst_now:
                    addend = -3600
                else:
                    addend = 3600
                new_rollover_at += addend

        self.rolloverAt = new_rollover_at

    def _compress_file(self, source: str) -> None:
        """Compress a log file using gzip.

        Args:
            source: Path to file to compress
        """
        try:
            compressed_path = f"{source}.gz"

            # Don't compress if already compressed
            if os.path.exists(compressed_path):
                logger.debug(f"Compressed file already exists: {compressed_path}")
                return

            # Compress the file
            with open(source, "rb") as f_in, gzip.open(compressed_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

            # Remove original
            os.remove(source)
            logger.info(f"Compressed log file: {source} -> {compressed_path}")

        except Exception as e:
            logger.error(f"Failed to compress log file {source}: {e}", exc_info=True)

    def _delete_old_backups(self) -> None:
        """Delete old backup files beyond backup_count."""
        try:
            dir_name, base_name = os.path.split(self.baseFilename)
            file_names = os.listdir(dir_name)

            # Find all rotated log files (including compressed)
            result = []
            prefix = base_name + "."
            plen = len(prefix)

            for file_name in file_names:
                if not file_name.startswith(prefix):
                    continue

                # Extract suffix (removing .gz if present)
                suffix = file_name[plen:]
                if suffix.endswith(".gz"):
                    suffix = suffix[:-3]

                # Check if suffix matches our pattern
                if self.extMatch.match(suffix):
                    result.append(os.path.join(dir_name, file_name))

            # Sort by modification time (oldest first)
            result.sort(key=lambda x: os.path.getmtime(x))

            # Delete oldest files beyond backup_count
            # Note: We count both compressed and uncompressed as separate files
            if len(result) > self.backupCount:
                for file_path in result[: len(result) - self.backupCount]:
                    try:
                        os.remove(file_path)
                        logger.debug(f"Deleted old log file: {file_path}")
                    except Exception as e:
                        logger.error(f"Failed to delete old log {file_path}: {e}")

        except Exception as e:
            logger.error(f"Failed to delete old backups: {e}", exc_info=True)


class SizeRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler with automatic gzip compression.

    Rotates logs based on file size and compresses old log files.
    """

    def __init__(
        self,
        filename: str | Path,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB default
        backup_count: int = 5,
        encoding: str | None = "utf-8",
        delay: bool = False,
        compress: bool = True,
    ) -> None:
        """Initialize size-based rotating file handler with compression.

        Args:
            filename: Log file path
            max_bytes: Max file size before rotation (bytes)
            backup_count: Number of backup files to keep
            encoding: File encoding
            delay: Defer file opening until first emit
            compress: Enable gzip compression of rotated files
        """
        super().__init__(
            filename=str(filename),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding,
            delay=delay,
        )
        self.compress = compress

    def doRollover(self) -> None:
        """Perform log rotation and compress old file."""
        if self.stream:
            self.stream.close()
            self.stream = None  # type: ignore[assignment]

        # Rotate files: log.N -> log.N+1
        for i in range(self.backupCount - 1, 0, -1):
            sfn = self.rotation_filename(f"{self.baseFilename}.{i}")
            dfn = self.rotation_filename(f"{self.baseFilename}.{i + 1}")

            # Handle both compressed and uncompressed files
            for ext in ["", ".gz"]:
                if os.path.exists(sfn + ext):
                    if os.path.exists(dfn + ext):
                        os.remove(dfn + ext)
                    os.rename(sfn + ext, dfn + ext)

        # Rotate current file to .1
        dfn = self.rotation_filename(f"{self.baseFilename}.1")
        if os.path.exists(dfn):
            os.remove(dfn)
        if os.path.exists(self.baseFilename):
            os.rename(self.baseFilename, dfn)

            # Compress the rotated file
            if self.compress:
                self._compress_file(dfn)

        # Open new file
        if not self.delay:
            self.stream = self._open()

    def _compress_file(self, source: str) -> None:
        """Compress a log file using gzip.

        Args:
            source: Path to file to compress
        """
        try:
            compressed_path = f"{source}.gz"

            with open(source, "rb") as f_in, gzip.open(compressed_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

            os.remove(source)
            logger.info(f"Compressed log file: {source} -> {compressed_path}")

        except Exception as e:
            logger.error(f"Failed to compress log file {source}: {e}", exc_info=True)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

RotationType = Literal["time", "size", "none"]


def create_rotating_file_handler(
    filename: str | Path,
    rotation_type: RotationType = "time",
    # Time-based rotation params
    when: str = "midnight",
    interval: int = 1,
    # Size-based rotation params
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    # Common params
    backup_count: int = 7,
    encoding: str = "utf-8",
    compress: bool = True,
) -> logging.Handler:
    """Create a rotating file handler with optional compression.

    Args:
        filename: Log file path
        rotation_type: Rotation strategy ('time', 'size', 'none')
        when: Time rotation interval ('midnight', 'H', 'D', etc.)
        interval: Time rotation interval multiplier
        max_bytes: Max file size for size-based rotation
        backup_count: Number of backup files to keep
        encoding: File encoding
        compress: Enable gzip compression

    Returns:
        Configured logging handler

    Example:
        >>> # Daily rotation at midnight, keep 7 days
        >>> handler = create_rotating_file_handler(
        ...     "/var/log/kagami/app.log",
        ...     rotation_type="time",
        ...     when="midnight",
        ...     backup_count=7,
        ... )

        >>> # Size-based rotation, 10MB chunks, keep 5 files
        >>> handler = create_rotating_file_handler(
        ...     "/var/log/kagami/app.log",
        ...     rotation_type="size",
        ...     max_bytes=10 * 1024 * 1024,
        ...     backup_count=5,
        ... )
    """
    # Ensure directory exists
    log_path = Path(filename)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if rotation_type == "time":
        handler = CompressingTimedRotatingFileHandler(
            filename=filename,
            when=when,
            interval=interval,
            backup_count=backup_count,
            encoding=encoding,
            compress=compress,
        )
    elif rotation_type == "size":
        handler = SizeRotatingFileHandler(  # type: ignore[assignment]
            filename=filename,
            max_bytes=max_bytes,
            backup_count=backup_count,
            encoding=encoding,
            compress=compress,
        )
    else:  # rotation_type == "none"
        handler = logging.FileHandler(  # type: ignore[assignment]
            filename=str(filename),
            encoding=encoding,
        )

    return handler


__all__ = [
    "CompressingTimedRotatingFileHandler",
    "RotationType",
    "SizeRotatingFileHandler",
    "create_rotating_file_handler",
]
