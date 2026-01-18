"""Dead Letter Queue (DLQ) recovery for failed receipt writes."""

from __future__ import annotations

import asyncio
import json
import logging

from kagami.core.caching.redis_keys import RedisKeys

logger = logging.getLogger(__name__)

DLQ_KEY = RedisKeys.dlq()
RECOVERY_INTERVAL_SECONDS = 60


async def process_dlq_loop() -> None:
    """Background loop to recover receipts from DLQ.

    Runs every 60 seconds, attempts to re-persist failed receipts to CockroachDB.

    Architecture:
    - Processes DLQ items in FIFO order (rpop from Redis list[Any])
    - Retries each receipt 3 times with exponential backoff
    - Re-queues failed receipts at front of DLQ (lpush)
    - Stops processing batch on first failure to avoid infinite loops

    Usage:
        asyncio.create_task(process_dlq_loop())
    """
    from kagami.core.caching.redis.factory import RedisClientFactory
    from kagami.core.receipts.persistence_helpers import _persist_receipt_db_with_retry_async

    redis_client = RedisClientFactory.get_client(purpose="default", async_mode=False)

    while True:
        try:
            await asyncio.sleep(RECOVERY_INTERVAL_SECONDS)

            # Process all DLQ items (batch)
            processed = 0
            while True:
                receipt_json = redis_client.rpop(DLQ_KEY)
                if not receipt_json:
                    break  # DLQ empty

                try:
                    receipt = json.loads(receipt_json)
                    success = await _persist_receipt_db_with_retry_async(receipt, max_retries=3)
                    if success:
                        processed += 1
                        logger.info(f"Recovered receipt from DLQ: {receipt.get('correlation_id')}")
                    else:
                        # Re-queue at front (FIFO)
                        redis_client.lpush(DLQ_KEY, receipt_json)
                        logger.warning(
                            f"DLQ recovery failed for receipt {receipt.get('correlation_id')}, "
                            "re-queued"
                        )
                        break  # Stop processing to avoid infinite loop
                except json.JSONDecodeError as e:
                    logger.error(f"DLQ recovery: invalid JSON in DLQ item: {e}")
                    # Discard invalid JSON
                    continue
                except Exception as e:
                    logger.error(f"DLQ recovery failed for receipt: {e}")
                    # Re-queue at front (FIFO)
                    redis_client.lpush(DLQ_KEY, receipt_json)
                    break  # Stop processing to avoid infinite loop

            if processed > 0:
                logger.info(f"DLQ recovery processed {processed} receipts")

        except Exception as e:
            logger.error(f"DLQ recovery loop error: {e}")
            await asyncio.sleep(10)  # Brief backoff on error


def start_dlq_recovery_background() -> asyncio.Task[None]:
    """Start DLQ recovery as background task.

    Returns:
        Asyncio task handle for monitoring/cancellation

    Example:
        task = start_dlq_recovery_background()
        # ... run application ...
        task.cancel()
    """
    try:
        task = asyncio.create_task(process_dlq_loop())
        logger.info("DLQ recovery background task started")
        return task
    except RuntimeError as e:
        logger.warning(f"Failed to start DLQ recovery (no event loop?): {e}")
        raise
