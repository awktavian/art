"""Distributed checkpoint locking using etcd.

Prevents multiple instances from saving checkpoints simultaneously,
which can cause corruption or race conditions.

Uses KagamiConsensus distributed lock infrastructure (Dec 16, 2025).
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def checkpoint_lock(
    checkpoint_name: str = "system_checkpoint",
    timeout: float = 60.0,
) -> AsyncGenerator[bool, None]:
    """Acquire distributed lock for checkpoint operations.

    Args:
        checkpoint_name: Name of checkpoint operation
        timeout: Max time to wait for lock (default 60s). Set to 0 for fail-fast.

    Yields:
        True if lock acquired successfully
        False if lock acquisition timed out (allows graceful skip)

    Example:
        async with checkpoint_lock("model_checkpoint", timeout=0) as acquired:
            if acquired:
                save_checkpoint("model.pt")
    """
    try:
        from kagami.core.consensus.distributed_lock import distributed_lock

        # Use distributed lock with reasonable timeout
        async with distributed_lock(
            resource=f"checkpoint:{checkpoint_name}",
            ttl=300,  # 5 minute TTL for checkpoint operations
            timeout=timeout,
            auto_renew=True,  # Auto-renew for long checkpoints
        ):
            logger.info(f"🔒 Acquired checkpoint lock: {checkpoint_name}")
            yield True
            logger.info(f"🔓 Released checkpoint lock: {checkpoint_name}")

    except TimeoutError:
        logger.warning(
            f"⏱️  Could not acquire checkpoint lock for '{checkpoint_name}' - "
            "another instance is checkpointing. Skipping this cycle."
        )
        yield False

    except Exception as e:
        logger.error(f"Checkpoint lock error: {e}")
        # Fail-safe: allow checkpoint (single instance assumption)
        logger.warning(
            f"Proceeding with checkpoint '{checkpoint_name}' without lock "
            "(etcd unavailable - assuming single instance)"
        )
        yield True


__all__ = ["checkpoint_lock"]
