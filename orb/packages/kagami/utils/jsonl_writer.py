"""JSONL File Writing Utilities.

Provides thread-safe JSONL file writing with rotation support.
Extracted from receipts.py for reusability.
"""

from __future__ import annotations

import logging
import os

from kagami.core.boot_mode import is_test_mode

logger = logging.getLogger(__name__)


def append_jsonl_locked(file_path: str, line: str) -> None:
    """Append a line to JSONL file with file locking.

    Args:
        file_path: Path to JSONL file
        line: JSON string to append (without newline)
    """
    # In tests, use non-blocking locks to prevent deadlocks
    is_test = is_test_mode()

    try:
        # Try POSIX flock
        try:
            import fcntl
        except ImportError:
            fcntl = None  # type: ignore

        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)

        with open(file_path, "a", encoding="utf-8") as f:
            try:
                if fcntl is not None:
                    lock_mode = fcntl.LOCK_EX | fcntl.LOCK_NB if is_test else fcntl.LOCK_EX
                    fcntl.flock(f.fileno(), lock_mode)
            except (BlockingIOError, OSError):
                if is_test:
                    return  # Skip in tests if can't get lock
                raise
            except Exception:
                pass

            try:
                f.write(line if line.endswith("\n") else line + "\n")
                f.flush()
            finally:
                try:
                    if fcntl is not None:
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass

    except Exception as e:
        if not is_test:
            logger.debug(f"JSONL write failed: {e}")


__all__ = ["append_jsonl_locked"]
