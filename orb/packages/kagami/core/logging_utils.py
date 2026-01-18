"""Logging utilities for worker-aware logging.

Problem:
========
PyTorch DataLoader spawns multiple worker processes for parallel data loading.
Each worker re-imports all modules, causing initialization logs to appear 16x
(once per worker + main process).

Solution:
=========
1. `is_main_process()` - Detect if running in main process vs worker
2. `log_once()` - Log only once per process lifetime
3. `main_process_only()` - Decorator to skip function in workers
4. `worker_init_fn()` - Centralized worker initialization

Usage:
======
```python
from kagami.core.logging_utils import is_main_process, log_once

# Only log from main process
if is_main_process():
    logger.info("This only appears once")

# Log once per process (useful for per-worker init)
log_once(logger, "info", "Initialized X", key="init_x")
```
"""

from __future__ import annotations

import functools
import logging
import os
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Track logged messages to avoid duplicates
_LOGGED_MESSAGES: set[str] = set()

# Environment variable set in workers to suppress init logs
_WORKER_ENV_VAR = "KAGAMI_DATALOADER_WORKER"


def is_main_process() -> bool:
    """Check if running in main process (not a DataLoader worker).

    Returns:
        True if main process, False if DataLoader worker.
    """
    # Check environment variable (most reliable)
    if os.environ.get(_WORKER_ENV_VAR):
        return False

    # Check PyTorch worker info
    try:
        from torch.utils.data import get_worker_info

        info = get_worker_info()
        if info is not None:
            return False
    except Exception:
        pass

    return True


def is_worker_process() -> bool:
    """Check if running in a DataLoader worker process."""
    return not is_main_process()


def get_worker_id() -> int | None:
    """Get the worker ID if in a worker, else None."""
    try:
        from torch.utils.data import get_worker_info

        info = get_worker_info()
        if info is not None:
            return info.id
    except Exception:
        pass
    return None


def log_once(
    log: logging.Logger,
    level: str,
    message: str,
    *args: Any,
    key: str | None = None,
    **kwargs: Any,
) -> bool:
    """Log a message only once per process lifetime.

    Args:
        log: Logger instance
        level: Log level ("debug", "info", "warning", "error")
        message: Log message (can contain % formatting)
        *args: Args for % formatting
        key: Unique key for deduplication (defaults to message)
        **kwargs: Additional kwargs for logger

    Returns:
        True if message was logged, False if already logged.
    """
    key = key or message
    if key in _LOGGED_MESSAGES:
        return False

    _LOGGED_MESSAGES.add(key)
    getattr(log, level)(message, *args, **kwargs)
    return True


def main_process_only(func: Callable) -> Callable:
    """Decorator to only execute function in main process.

    Usage:
        @main_process_only
        def log_initialization():
            logger.info("Initializing...")
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if is_main_process():
            return func(*args, **kwargs)
        return None

    return wrapper


def worker_init_fn(worker_id: int) -> None:
    """Standard worker initialization function for DataLoader.

    Sets up the worker environment:
    1. Marks process as worker (suppresses init logs)
    2. Seeds random state
    3. Configures logging level

    Usage:
        DataLoader(dataset, num_workers=16, worker_init_fn=worker_init_fn)
    """
    import random

    import numpy as np

    # Mark as worker process
    os.environ[_WORKER_ENV_VAR] = str(worker_id)

    # Seed random state for reproducibility
    seed = int(os.environ.get("KAGAMI_SEED", "42")) + worker_id * 1000
    random.seed(seed)
    np.random.seed(seed)

    try:
        import torch

        torch.manual_seed(seed)
    except ImportError:
        pass

    # Suppress DEBUG/INFO logs in workers (only show WARNING+)
    logging.getLogger().setLevel(logging.WARNING)

    # But keep kagami loggers at INFO for important messages
    kagami_logger = logging.getLogger("kagami")
    kagami_logger.setLevel(logging.INFO)


def configure_worker_logging() -> None:
    """Configure logging for the current process based on worker status.

    Call this at the start of any module that has initialization logs.
    """
    if is_worker_process():
        # Suppress most logs in workers
        logging.getLogger().setLevel(logging.WARNING)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def info_main_only(log: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
    """Log INFO only from main process."""
    if is_main_process():
        log.info(message, *args, **kwargs)


def debug_in_worker(log: logging.Logger, message: str, *args: Any, **kwargs: Any) -> None:
    """Log as INFO in main, DEBUG in workers."""
    if is_main_process():
        log.info(message, *args, **kwargs)
    else:
        log.debug(message, *args, **kwargs)
