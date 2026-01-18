"""Full Operation enforcement for API startup.

Validates that all mandatory components are available before the API becomes ready.

OPTIMIZED (Dec 30, 2025): Run checks in parallel using asyncio.gather.
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Thread pool for blocking I/O operations
_executor = ThreadPoolExecutor(max_workers=3)


def _check_redis() -> tuple[bool, str | None]:
    """Check Redis connectivity (blocking)."""
    try:
        from kagami.core.caching.redis import RedisClientFactory

        redis = RedisClientFactory.get_client()
        redis.ping()
        return True, None
    except Exception as e:
        return False, f"Redis: {e}"


def _check_database() -> tuple[bool, str | None]:
    """Check database connectivity (blocking)."""
    try:
        from kagami.core.database.connection import get_engine
        from sqlalchemy import text

        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, f"Database: {e}"


def _check_metrics() -> tuple[bool, str | None]:
    """Check metrics registry (fast)."""
    try:
        from kagami_observability.metrics import REGISTRY

        assert REGISTRY is not None
        return True, None
    except Exception as e:
        return False, f"Metrics: {e}"


async def enforce_full_operation() -> bool:
    """Enforce Full Operation mode - all components mandatory.

    OPTIMIZED (Dec 30, 2025): Run Redis and Database checks in parallel
    using ThreadPoolExecutor for blocking I/O operations.

    Returns:
        True if all components operational, False otherwise

    Raises:
        RuntimeError: In production if any component is unavailable
    """
    _env = (os.getenv("ENVIRONMENT") or "development").lower()
    _local_mode = os.getenv("KAGAMI_LOCAL_MODE", "").lower() in ("1", "true", "yes", "on")
    _full_op = (
        os.getenv("KAGAMI_FULL_OPERATION") or ("1" if _env == "production" else "0")
    ).lower() in ("1", "true", "yes", "on")

    # Local mode always skips full operation checks
    if _local_mode:
        logger.info("Local mode enabled - skipping Full Operation checks")
        return True

    if not _full_op:
        logger.info("Full Operation mode disabled - allowing degraded operation")
        return True

    logger.info("Full Operation enforcement: checking mandatory components...")

    # Run all checks in parallel using ThreadPoolExecutor for blocking I/O
    loop = asyncio.get_event_loop()

    # Schedule all checks concurrently
    redis_task = loop.run_in_executor(_executor, _check_redis)
    db_task = loop.run_in_executor(_executor, _check_database)
    metrics_task = loop.run_in_executor(_executor, _check_metrics)

    # Wait for all checks to complete
    results = await asyncio.gather(redis_task, db_task, metrics_task, return_exceptions=True)

    failures = []
    check_names = ["Redis", "Database", "Metrics"]

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            failures.append(f"{check_names[i]}: {result}")
            logger.error(f"✗ {check_names[i]} check failed: {result}")
        else:
            success, error = result
            if success:
                logger.info(f"✓ {check_names[i]} operational")
            else:
                failures.append(error or f"{check_names[i]}: unknown error")
                logger.error(f"✗ {error}")

    if failures:
        msg = f"Full Operation FAILED - missing components: {', '.join(failures)}"
        logger.error(msg)
        if _env == "production":
            raise RuntimeError(msg) from None
        return False

    logger.info("✅ Full Operation achieved - all mandatory components operational")
    return True
