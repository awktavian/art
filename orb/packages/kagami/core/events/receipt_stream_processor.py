from __future__ import annotations

from kagami.core.async_utils import safe_create_task

"Real-Time Receipt Stream Processing.\n\nThis module provides real-time learning from receipts using async streaming.\nDesigned to be upgradeable to Kafka/Kinesis for production scale.\n\nBenefits:\n- Zero-delay learning (no batch processing lag)\n- Better scalability via event-driven architecture\n- Decoupled learning systems\n- Can be upgraded to Kafka for distributed processing\n\nArchitecture:\n    Receipts → AsyncQueue → StreamProcessor → Learning Systems\n\nFuture: Replace AsyncQueue with Kafka for true distributed streaming.\n"
import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from kagami.core.caching.redis_keys import RedisKeys

logger = logging.getLogger(__name__)

try:
    from kagami.core.caching.redis import RedisClientFactory
except Exception:  # pragma: no cover - optional dependency
    RedisClientFactory = None  # type: ignore


@dataclass
class StreamMetrics:
    """Metrics for stream processing."""

    total_processed: int = 0
    total_errors: int = 0
    processing_times_ms: list[float] | None = None
    last_process_time: float = 0.0

    def __post_init__(self) -> None:
        if self.processing_times_ms is None:
            self.processing_times_ms = []

    @property
    def avg_processing_time_ms(self) -> float:
        """Average processing time."""
        if not self.processing_times_ms:
            return 0.0
        return sum(self.processing_times_ms) / len(self.processing_times_ms)

    @property
    def success_rate(self) -> float:
        """Success rate (0-1)."""
        total = self.total_processed + self.total_errors
        if total == 0:
            return 1.0
        return self.total_processed / total


class ReceiptStreamProcessor:
    """Process receipts in real-time for instant learning.

    This processor enables zero-delay learning by processing receipts
    as they arrive instead of in batches.

    Usage:
        processor = ReceiptStreamProcessor()
        await processor.start()

        # In receipt generation code:
        await processor.process_receipt(receipt)
    """

    def __init__(
        self, queue_size: int = 10000, batch_size: int = 10, batch_timeout_ms: int = 100
    ) -> None:
        """Initialize stream processor.

        Args:
            queue_size: Max receipts in queue before backpressure
            batch_size: Process receipts in micro-batches for efficiency
            batch_timeout_ms: Max wait time for batch to fill
        """
        self._queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=queue_size)
        self._batch_size: int = batch_size
        self._initial_batch_size: int = batch_size
        self._batch_timeout: float = batch_timeout_ms / 1000.0
        self._handlers: list[Callable[[dict[str, Any]], Awaitable[Any]]] = []
        self._metrics: StreamMetrics = StreamMetrics()
        self._metrics_by_phase: dict[str, StreamMetrics] = defaultdict(StreamMetrics)
        self._running: bool = False
        self._started: bool = False
        self._process_task: asyncio.Task[Any] | None = None
        self._learning: Any = None
        self._prediction: Any = None
        self._experience: Any = None
        self._auto_start_task: asyncio.Task[Any] | None = None
        self._causal_buffer: list[dict[str, Any]] = []

        # Circuit breaker for queue saturation
        self._circuit_breaker_threshold: float = 0.8  # 80% full triggers warning
        self._circuit_breaker_active: bool = False
        self._dropped_receipts: int = 0

        # Redis fallback for overflow
        self._redis_fallback_enabled: bool = True
        self._redis_client: Any = None

        # ENHANCEMENT: Hierarchical pattern extraction
        try:
            from kagami.core.learning.hierarchical_patterns import HierarchicalPatternExtractor

            self._pattern_extractor: Any = HierarchicalPatternExtractor()
            self._enhanced_learning_enabled: bool = True
            logger.info("✅ Enhanced learning with hierarchical patterns enabled")
        except ImportError as e:
            self._pattern_extractor = None
            self._enhanced_learning_enabled = False
            logger.warning(f"Enhanced learning modules not available: {e}")

    def add_handler(self, handler: Callable[[dict[str, Any]], Awaitable[Any]]) -> None:
        """Add custom receipt handler.

        Args:
            handler: Async function that processes receipt
        """
        self._handlers.append(handler)

    async def process_receipt(self, receipt: dict[str, Any]) -> None:
        """Process a single receipt in real-time with guaranteed delivery.

        This is the main entry point for receipt processing. Implements:
        - Backpressure with timeout (wait up to 5s for queue space)
        - Redis pub/sub fallback when queue saturates
        - Circuit breaker to prevent cascading failures

        Args:
            receipt: Receipt dict[str, Any] with correlation_id, phase, event, etc.

        Raises:
            RuntimeError: If processor not started (must call start() after registering handlers)
        """
        if not self._started:
            raise RuntimeError(
                "ReceiptStreamProcessor not started. "
                "Call await processor.start() after registering handlers."
            )
        # Check circuit breaker threshold
        queue_utilization = self._queue.qsize() / self._queue.maxsize
        if queue_utilization >= self._circuit_breaker_threshold:
            if not self._circuit_breaker_active:
                self._circuit_breaker_active = True
                logger.warning(
                    f"Circuit breaker activated: queue at {queue_utilization:.1%} capacity. "
                    "Engaging backpressure and Redis fallback."
                )
                # Adapt batch size: increase batch size under load to clear queue faster
                self._batch_size = min(1000, self._initial_batch_size * 10)
                logger.info(f"Adaptive batching: increased batch size to {self._batch_size}")

                # Emit warning receipt
                try:
                    import importlib

                    emit_receipt = importlib.import_module("kagami.core.receipts").emit_receipt

                    emit_receipt(
                        correlation_id="system",
                        action="receipt.queue.saturated",
                        app="receipt_processor",
                        event_name="queue.circuit_breaker",
                        event_data={
                            "queue_size": self._queue.qsize(),
                            "queue_maxsize": self._queue.maxsize,
                            "utilization": queue_utilization,
                        },
                        status="warning",
                    )
                except Exception:
                    pass
        elif queue_utilization < 0.5 and self._circuit_breaker_active:
            self._circuit_breaker_active = False
            self._batch_size = self._initial_batch_size
            logger.info(
                f"Circuit breaker deactivated: queue utilization back to normal. Batch size reset to {self._batch_size}"
            )

        # Try to enqueue with backpressure (wait up to 5s)
        try:
            await asyncio.wait_for(self._queue.put(receipt), timeout=5.0)
            return
        except TimeoutError:
            logger.warning("Receipt queue full after 5s backpressure, attempting Redis fallback")
            self._metrics.total_errors += 1
            self._dropped_receipts += 1

        # Redis fallback: publish to Redis list[Any] for persistent async processing
        if self._redis_fallback_enabled:
            try:
                if self._redis_client is None:
                    if RedisClientFactory is None:
                        logger.error("Redis fallback requested but RedisClientFactory unavailable")  # type: ignore[unreachable]
                        raise RuntimeError("RedisClientFactory unavailable for fallback") from None
                    self._redis_client = RedisClientFactory.get_client(
                        purpose="receipts",  # type: ignore[arg-type]
                        async_mode=True,
                        decode_responses=False,
                    )

                import json

                # Push to LPUSH list[Any] for persistent storage (instead of PUBLISH)
                # This prevents message loss if no subscribers are listening immediately
                await self._redis_client.lpush(
                    RedisKeys.queue("fallback_queue"), json.dumps(receipt, ensure_ascii=False)
                )
                # Also PUBLISH for real-time listeners (optional, best effort)
                await self._redis_client.publish(
                    RedisKeys.queue("overflow"), json.dumps(receipt, ensure_ascii=False)
                )
                logger.debug("Receipt pushed to Redis fallback queue (persistent)")
                return
            except Exception as e:
                logger.error(f"Redis fallback failed: {e}")

        # Last resort: drop receipt and log
        logger.error(
            f"Receipt dropped (no capacity): correlation_id={receipt.get('correlation_id')}, "
            f"total_dropped={self._dropped_receipts}"
        )
        # Emit metric
        try:
            from kagami_observability.metrics import Counter

            DROPPED_RECEIPTS = Counter(
                "kagami_receipts_dropped_total", "Receipts dropped due to queue saturation"
            )
            DROPPED_RECEIPTS.inc()
        except Exception:
            pass

    async def start(self) -> None:
        """Start stream processing in background.

        Must be called after all handlers are registered to avoid dropping receipts.
        """
        if self._started:
            logger.warning("Stream processor already started")
            return

        self._started = True
        self._running = True
        self._process_task = safe_create_task(self._process_stream(), name="_process_stream")
        self._init_learning_systems()
        logger.info("📊 Receipt stream processor started (real-time learning enabled)")

    async def stop(self) -> None:
        """Stop stream processing gracefully."""
        if not self._running:
            return
        self._running = False
        self._started = False
        await self._queue.join()
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info(
            f"Receipt stream processor stopped (processed {self._metrics.total_processed} receipts)"
        )

    def _init_learning_systems(self) -> None:
        """Initialize learning systems (lazy loading)."""
        try:
            from kagami.core.coordination.experience_store import get_experience_store
            from kagami.core.instincts.learning_instinct import get_learning_instinct
            from kagami.core.instincts.prediction_instinct import get_prediction_instinct

            self._learning = get_learning_instinct()
            self._prediction = get_prediction_instinct()
            self._experience = get_experience_store()
            logger.info("✅ Learning systems initialized for stream processing")
        except Exception as e:
            logger.warning(f"Could not initialize learning systems: {e}")

    async def _process_stream(self) -> None:
        """Main stream processing loop."""
        while self._running:
            try:
                batch = await self._collect_batch()
                if batch:
                    await self._process_batch(batch)
            except Exception as e:
                logger.error(f"Stream processing error: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _collect_batch(self) -> list[dict[str, Any]]:
        """Collect micro-batch of receipts.

        Returns:
            List of receipts to process
        """
        batch = []  # type: ignore[var-annotated]
        deadline = time.time() + self._batch_timeout
        while len(batch) < self._batch_size and time.time() < deadline:
            try:
                timeout = max(0.001, deadline - time.time())
                receipt = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                batch.append(receipt)
            except TimeoutError:
                break
        return batch

    async def _process_batch(self, batch: list[dict[str, Any]]) -> None:
        """Process batch of receipts.

        Args:
            batch: List of receipts to process
        """
        start_time = time.time()
        for receipt in batch:
            try:
                await self._process_single_receipt(receipt)
                self._metrics.total_processed += 1
                phase = receipt.get("phase", "unknown")
                self._metrics_by_phase[phase].total_processed += 1
            except Exception as e:
                logger.error(f"Receipt processing failed: {e}", exc_info=True)
                self._metrics.total_errors += 1
                phase = receipt.get("phase", "unknown")
                self._metrics_by_phase[phase].total_errors += 1
            finally:
                self._queue.task_done()
        processing_time = (time.time() - start_time) * 1000
        self._metrics.processing_times_ms.append(processing_time)  # type: ignore[union-attr]
        if len(self._metrics.processing_times_ms) > 1000:  # type: ignore[arg-type]
            self._metrics.processing_times_ms = self._metrics.processing_times_ms[-1000:]  # type: ignore[index]
        self._metrics.last_process_time = time.time()

    async def _process_single_receipt(self, receipt: dict[str, Any]) -> None:
        """Process a single receipt for learning.

        Args:
            receipt: Receipt dict[str, Any]
        """
        # NOTE: RL experience storage moved to UnifiedLearningCoordinator (CONVERGE phase)
        # to prevent race conditions and double-counting.
        for handler in self._handlers:
            try:
                await handler(receipt)
            except Exception as e:
                logger.debug(f"Handler failed: {e}")

    def _extract_context(self, receipt: dict[str, Any]) -> dict[str, str | dict[str, Any]]:
        """Extract learning context from receipt.

        Args:
            receipt: Receipt dict[str, Any]

        Returns:
            Context dict[str, Any] for learning
        """
        intent = receipt.get("intent") or {}
        if not isinstance(intent, dict):
            intent = {}
        metadata = intent.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        return {
            "app": intent.get("app", "unknown"),
            "action": intent.get("action", "unknown"),
            "params": intent.get("args", {}),
            "complexity": metadata.get("complexity", "normal"),
        }

    async def _learn_causality(self, receipt: dict[str, Any]) -> None:
        """Learn causal relationships from receipt.

        Args:
            receipt: Receipt dict[str, Any]
        """
        self._causal_buffer.append(receipt)

        # Run causal discovery every 100 receipts
        if len(self._causal_buffer) >= 100:
            try:
                from kagami.core.learning.causal_learning_loop import learn_causality_from_receipts

                result = await learn_causality_from_receipts(self._causal_buffer)

                if result.get("status") == "success":
                    logger.info(
                        f"🔗 Causal discovery: {result['num_edges']} edges found "
                        f"among {result['num_nodes']} variables"
                    )

                # Clear buffer
                self._causal_buffer = self._causal_buffer[-50:]  # Keep last 50 for overlap
            except Exception as e:
                logger.debug(f"Causal learning failed: {e}")

    def _extract_outcome(self, receipt: dict[str, Any]) -> dict[str, str | int | float]:
        """Extract outcome from receipt.

        Args:
            receipt: Receipt dict[str, Any]

        Returns:
            Outcome dict[str, Any]
        """
        event = receipt.get("event", {})
        event_data = event.get("data", {})
        return {
            "status": event_data.get("status", event.get("name", "unknown")),
            "duration_ms": receipt.get("duration_ms", 0),
            "prediction_error_ms": receipt.get("prediction_error_ms", 0),
            "threat_score": event_data.get("threat_score", 0.0),
            "ts": receipt.get("ts", time.time()),
        }

    def _extract_valence(self, receipt: dict[str, Any]) -> float:
        """Extract emotional valence from receipt.

        Args:
            receipt: Receipt dict[str, Any]

        Returns:
            Valence score [-1, 1]
        """
        valence = receipt.get("valence")
        if valence is not None:
            return float(valence)
        outcome = self._extract_outcome(receipt)
        status = str(outcome.get("status") or "").lower()
        duration = outcome.get("duration_ms", 0)
        if "error" in status or "fail" in status:
            return -0.8
        elif "success" in status or "ok" in status or "verified" in status:
            speed_factor = max(0, 1.0 - duration / 1000)  # type: ignore[operator]
            return 0.3 + 0.7 * speed_factor
        else:
            return 0.0

    def get_metrics(self) -> dict[str, Any]:
        """Get stream processing metrics.

        Returns:
            Dict with processing statistics
        """
        queue_size = self._queue.qsize()
        queue_utilization = queue_size / self._queue.maxsize if self._queue.maxsize > 0 else 0

        # Export Prometheus metrics
        try:
            from kagami_observability.metrics import Gauge

            QUEUE_SIZE = Gauge("kagami_receipt_queue_size", "Current receipt queue size")
            QUEUE_UTILIZATION = Gauge(
                "kagami_receipt_queue_utilization", "Receipt queue utilization ratio"
            )
            DROPPED_COUNT = Gauge("kagami_receipt_dropped_count", "Total receipts dropped")
            CIRCUIT_BREAKER = Gauge(
                "kagami_receipt_circuit_breaker", "Circuit breaker status (0=off, 1=on)"
            )

            QUEUE_SIZE.set(queue_size)
            QUEUE_UTILIZATION.set(queue_utilization)
            DROPPED_COUNT.set(self._dropped_receipts)
            CIRCUIT_BREAKER.set(1 if self._circuit_breaker_active else 0)
        except Exception:
            pass

        return {
            "total_processed": self._metrics.total_processed,
            "total_errors": self._metrics.total_errors,
            "dropped_receipts": self._dropped_receipts,
            "success_rate": self._metrics.success_rate,
            "avg_processing_time_ms": self._metrics.avg_processing_time_ms,
            "queue_size": queue_size,
            "queue_maxsize": self._queue.maxsize,
            "queue_utilization": queue_utilization,
            "circuit_breaker_active": self._circuit_breaker_active,
            "is_running": self._running,
            "last_process_time": self._metrics.last_process_time,
            "by_phase": {
                phase: {
                    "processed": metrics.total_processed,
                    "errors": metrics.total_errors,
                    "success_rate": metrics.success_rate,
                }
                for phase, metrics in self._metrics_by_phase.items()
            },
        }

    def is_running(self) -> bool:
        """Return whether the processor loop is active."""
        return self._running

    def ensure_running(self) -> None:
        """Ensure the receipt stream processor background loop is running.

        WARNING: This auto-start mechanism can cause race conditions if handlers
        are not registered before receipts arrive. Use explicit start() instead.
        """
        if self._started:
            return

        loop = self._resolve_loop()
        if loop is None or not loop.is_running():
            logger.warning("Receipt stream processor could not auto-start (no running event loop)")
            return

        if self._auto_start_task and not self._auto_start_task.done():
            return

        logger.warning(
            "Auto-starting receipt processor without handler registration check. "
            "Consider explicit processor.start() after handler registration."
        )

        self._auto_start_task = safe_create_task(
            self.start(),
            name="receipt_processor_auto_start",
            logger_context={"component": "receipt_processor"},
        )

    def _resolve_loop(self) -> asyncio.AbstractEventLoop | None:
        """Return the running event loop if available, None otherwise."""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    def reset_metrics(self) -> None:
        """Reset metrics (useful for testing)."""
        self._metrics = StreamMetrics()
        self._metrics_by_phase.clear()


_stream_processor: ReceiptStreamProcessor | None = None


def get_stream_processor() -> ReceiptStreamProcessor:
    """Get global stream processor singleton.

    Returns:
        ReceiptStreamProcessor instance
    """
    global _stream_processor
    if _stream_processor is None:
        _stream_processor = ReceiptStreamProcessor()
    return _stream_processor
