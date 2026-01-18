"""Receipt streaming logic."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import time as _time
from typing import Any

from kagami.core.async_utils import safe_create_task
from kagami.core.caching.redis_keys import RedisKeys
from kagami.core.receipts.ingestor import _RECEIPTS

logger = logging.getLogger(__name__)


def _load_stream_processor() -> Any:
    """Lazy load stream processor."""
    try:
        module = importlib.import_module("kagami.core.streaming.receipt_stream_processor")
        getter = getattr(module, "get_stream_processor", None)
        return getter() if callable(getter) else None
    except Exception as exc:
        logger.debug(f"Stream processor unavailable: {exc}")
        return None


def fanout_receipt_to_stream_processor(receipt: dict[str, Any]) -> None:
    """Deliver receipts into the real-time learning loop."""
    if os.getenv("KAGAMI_STREAM_PROCESSING_ENABLED", "1") != "1":
        return

    processor = _load_stream_processor()
    if processor is None:
        logger.debug("Receipt stream processor not available; skipping learning loop.")
        return

    try:
        if hasattr(processor, "ensure_running"):
            processor.ensure_running()

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("Receipt fanout skipped (event loop not running)")
            return

        safe_create_task(
            processor.process_receipt(receipt),
            name="receipt_learning_loop",
            logger_context={"correlation_id": receipt.get("correlation_id", "unknown")},
        )
    except RuntimeError:
        logger.warning("Receipt fanout skipped (no event loop available)")
    except Exception as exc:
        logger.debug(f"Stream processing failed: {exc}")


async def stream_receipts() -> None:
    """Stream receipts via Server-Sent Events (SSE)."""
    try:
        from sse_starlette.sse import EventSourceResponse

        use_sse_starlette = True
    except ImportError:
        from fastapi.responses import (
            StreamingResponse as EventSourceResponse,  # type: ignore[assignment]
        )

        use_sse_starlette = False

    async def event_generator() -> None:  # type: ignore[misc]
        try:
            if use_sse_starlette:
                yield {
                    "event": "connected",
                    "data": json.dumps({"status": "streaming", "timestamp": _time.time()}),
                }
            else:
                yield f"event: connected\ndata: {json.dumps({'status': 'streaming', 'timestamp': _time.time()})}\n\n"

            processor = _load_stream_processor()
            if processor is None:
                logger.warning(
                    "Receipt stream processor unavailable, streaming from in-memory cache"
                )
                start_time = _time.time()
                while (_time.time() - start_time) < 300:
                    receipts = list(_RECEIPTS.values())[-10:]
                    for receipt in receipts:
                        if use_sse_starlette:
                            yield {
                                "event": "receipt",
                                "data": json.dumps(receipt),
                            }
                        else:
                            yield f"event: receipt\ndata: {json.dumps(receipt)}\n\n"
                    await asyncio.sleep(1.0)
            else:
                try:
                    from kagami.core.caching.redis import RedisClientFactory

                    redis = RedisClientFactory.get_client()
                    pubsub = redis.pubsub()
                    pubsub.subscribe(RedisKeys.stream("receipts"))
                    logger.info("📡 Subscribed to receipt event stream via Redis pub/sub")
                except Exception as e:
                    logger.warning(f"Redis pub/sub unavailable, using polling: {e}")

                start_time = _time.time()
                last_seen = set()
                while (_time.time() - start_time) < 300:
                    receipts = list(_RECEIPTS.values())
                    for receipt in receipts:
                        receipt_id = receipt.get("correlation_id", "")
                        if receipt_id and receipt_id not in last_seen:
                            last_seen.add(receipt_id)
                            if use_sse_starlette:
                                yield {
                                    "event": "receipt",
                                    "data": json.dumps(receipt),
                                }
                            else:
                                yield f"event: receipt\ndata: {json.dumps(receipt)}\n\n"
                    await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Receipt stream error: {e}")
            if use_sse_starlette:
                yield {"event": "error", "data": json.dumps({"error": str(e)})}
            else:
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    if use_sse_starlette:
        return EventSourceResponse(event_generator())  # type: ignore[return-value, func-returns-value]
    else:
        return EventSourceResponse(event_generator(), media_type="text/event-stream")  # type: ignore[return-value, func-returns-value]
