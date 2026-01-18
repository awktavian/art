"""Performance Optimization Monitoring Dashboard.

Provides real-time monitoring and metrics for all optimization systems:
- Cache performance
- Batch processing throughput
- LLM request efficiency
- Database query performance
- Progressive rendering stats

Colony: Nexus (e₄) - Integration
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Aggregate performance metrics."""

    # Cache metrics
    cache_hit_rate: float = 0.0
    cache_memory_mb: float = 0.0
    cache_avg_latency_ms: float = 0.0

    # Batch processing metrics
    batch_throughput: float = 0.0
    batch_queue_size: int = 0
    batch_avg_time_ms: float = 0.0

    # LLM metrics
    llm_dedup_rate: float = 0.0
    llm_batch_size: float = 0.0
    llm_cache_hit_rate: float = 0.0

    # Database metrics
    db_slow_queries: int = 0
    db_avg_latency_ms: float = 0.0
    db_query_count: int = 0

    # Progressive rendering metrics
    render_active_count: int = 0
    render_avg_completion_time: float = 0.0
    render_avg_quality: str = "unknown"

    # Overall metrics
    total_requests: int = 0
    avg_response_time_ms: float = 0.0
    error_rate: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "cache": {
                "hit_rate": self.cache_hit_rate,
                "memory_mb": self.cache_memory_mb,
                "avg_latency_ms": self.cache_avg_latency_ms,
            },
            "batch_processing": {
                "throughput": self.batch_throughput,
                "queue_size": self.batch_queue_size,
                "avg_time_ms": self.batch_avg_time_ms,
            },
            "llm": {
                "dedup_rate": self.llm_dedup_rate,
                "batch_size": self.llm_batch_size,
                "cache_hit_rate": self.llm_cache_hit_rate,
            },
            "database": {
                "slow_queries": self.db_slow_queries,
                "avg_latency_ms": self.db_avg_latency_ms,
                "query_count": self.db_query_count,
            },
            "progressive_rendering": {
                "active_count": self.render_active_count,
                "avg_completion_time": self.render_avg_completion_time,
                "avg_quality": self.render_avg_quality,
            },
            "overall": {
                "total_requests": self.total_requests,
                "avg_response_time_ms": self.avg_response_time_ms,
                "error_rate": self.error_rate,
            },
            "timestamp": self.timestamp,
        }


class OptimizationMonitor:
    """Monitors all optimization systems."""

    def __init__(self, update_interval: int = 10):
        """Initialize monitor.

        Args:
            update_interval: Metrics update interval in seconds
        """
        self.update_interval = update_interval
        self._running = False
        self._monitor_task: asyncio.Task | None = None
        self._metrics_history: list[PerformanceMetrics] = []
        self._max_history = 100

    async def start(self) -> None:
        """Start monitoring."""
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Optimization monitor started")

    async def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("Optimization monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                metrics = await self.collect_metrics()
                self._metrics_history.append(metrics)

                # Trim history
                if len(self._metrics_history) > self._max_history:
                    self._metrics_history.pop(0)

                # Log summary
                await self._log_metrics(metrics)

                await asyncio.sleep(self.update_interval)

            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(self.update_interval)

    async def collect_metrics(self) -> PerformanceMetrics:
        """Collect metrics from all optimization systems."""
        metrics = PerformanceMetrics()

        # Collect cache metrics
        try:
            from kagami.core.caching.redis_cache import get_global_cache

            cache = await get_global_cache()
            cache_stats = await cache.get_stats()
            metrics.cache_hit_rate = cache_stats.get("hit_rate", 0.0)
            metrics.cache_memory_mb = cache_stats.get("memory_used_mb", 0.0)
            metrics.cache_avg_latency_ms = cache_stats.get("avg_get_time_ms", 0.0)
        except Exception as e:
            logger.debug(f"Failed to collect cache metrics: {e}")

        # Collect batch processing metrics
        try:
            from kagami.forge.modules.generation.batch_processor import (
                get_gaussian_processor,
            )

            processor = await get_gaussian_processor()
            batch_stats = await processor.get_stats()
            metrics.batch_throughput = batch_stats.get("avg_throughput", 0.0)
            metrics.batch_queue_size = batch_stats.get("queue_size", 0)
        except Exception as e:
            logger.debug(f"Failed to collect batch metrics: {e}")

        # Collect LLM metrics
        try:
            from kagami.core.services.llm.request_batcher import get_global_batcher

            batcher = await get_global_batcher()
            llm_stats = await batcher.get_stats()

            # Get stats for all models
            all_stats = llm_stats if isinstance(llm_stats, dict) else {}
            if all_stats:
                # Aggregate across models
                total_requests = sum(s.get("total_requests", 0) for s in all_stats.values())
                total_deduped = sum(s.get("deduplicated", 0) for s in all_stats.values())
                metrics.llm_dedup_rate = (
                    total_deduped / total_requests if total_requests > 0 else 0.0
                )
        except Exception as e:
            logger.debug(f"Failed to collect LLM metrics: {e}")

        # Collect database metrics
        try:
            from kagami.core.database.query_optimizer import get_global_profiler

            profiler = get_global_profiler()
            db_stats = await profiler.get_stats()
            metrics.db_slow_queries = db_stats.get("slow_queries", 0)
            metrics.db_avg_latency_ms = db_stats.get("avg_time_ms", 0.0)
            metrics.db_query_count = db_stats.get("total_queries", 0)
        except Exception as e:
            logger.debug(f"Failed to collect database metrics: {e}")

        # Collect progressive rendering metrics
        try:
            from kagami.forge.progressive_renderer import get_global_renderer

            renderer = get_global_renderer()
            active_renders = await renderer.get_active_renders()
            metrics.render_active_count = len(active_renders)
        except Exception as e:
            logger.debug(f"Failed to collect rendering metrics: {e}")

        return metrics

    async def _log_metrics(self, metrics: PerformanceMetrics) -> None:
        """Log metrics summary."""
        logger.info("=" * 80)
        logger.info("OPTIMIZATION METRICS SUMMARY")
        logger.info("=" * 80)
        logger.info(
            f"Cache:     Hit rate {metrics.cache_hit_rate:.1%}, "
            f"Memory {metrics.cache_memory_mb:.1f} MB"
        )
        logger.info(
            f"Batch:     Throughput {metrics.batch_throughput:.2f} items/s, "
            f"Queue {metrics.batch_queue_size}"
        )
        logger.info(
            f"LLM:       Dedup rate {metrics.llm_dedup_rate:.1%}, "
            f"Cache hit {metrics.llm_cache_hit_rate:.1%}"
        )
        logger.info(
            f"Database:  Slow queries {metrics.db_slow_queries}, "
            f"Avg latency {metrics.db_avg_latency_ms:.2f}ms"
        )
        logger.info(f"Rendering: Active renders {metrics.render_active_count}")
        logger.info("=" * 80)

    async def get_current_metrics(self) -> dict[str, Any]:
        """Get current metrics."""
        if self._metrics_history:
            return self._metrics_history[-1].to_dict()
        return PerformanceMetrics().to_dict()

    async def get_metrics_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get metrics history.

        Args:
            limit: Maximum number of historical metrics to return

        Returns:
            List of metrics dictionaries
        """
        return [m.to_dict() for m in self._metrics_history[-limit:]]

    async def get_performance_report(self) -> dict[str, Any]:
        """Generate comprehensive performance report."""
        if not self._metrics_history:
            return {"error": "No metrics collected yet"}

        recent = self._metrics_history[-10:]  # Last 10 data points

        report = {
            "time_range": {
                "start": recent[0].timestamp,
                "end": recent[-1].timestamp,
                "duration_seconds": recent[-1].timestamp - recent[0].timestamp,
            },
            "cache": {
                "avg_hit_rate": sum(m.cache_hit_rate for m in recent) / len(recent),
                "avg_memory_mb": sum(m.cache_memory_mb for m in recent) / len(recent),
                "max_memory_mb": max(m.cache_memory_mb for m in recent),
            },
            "batch_processing": {
                "avg_throughput": sum(m.batch_throughput for m in recent) / len(recent),
                "max_queue_size": max(m.batch_queue_size for m in recent),
                "avg_queue_size": sum(m.batch_queue_size for m in recent) / len(recent),
            },
            "llm": {
                "avg_dedup_rate": sum(m.llm_dedup_rate for m in recent) / len(recent),
                "avg_cache_hit_rate": sum(m.llm_cache_hit_rate for m in recent) / len(recent),
            },
            "database": {
                "total_slow_queries": sum(m.db_slow_queries for m in recent),
                "avg_latency_ms": sum(m.db_avg_latency_ms for m in recent) / len(recent),
                "total_queries": sum(m.db_query_count for m in recent),
            },
            "recommendations": await self._generate_recommendations(recent),
        }

        return report

    async def _generate_recommendations(
        self, recent_metrics: list[PerformanceMetrics]
    ) -> list[str]:
        """Generate optimization recommendations based on metrics."""
        recommendations = []

        avg_cache_hit_rate = sum(m.cache_hit_rate for m in recent_metrics) / len(recent_metrics)
        if avg_cache_hit_rate < 0.5:
            recommendations.append(
                "Cache hit rate is low (<50%). Consider increasing cache TTL or "
                "enabling more aggressive caching."
            )

        avg_dedup_rate = sum(m.llm_dedup_rate for m in recent_metrics) / len(recent_metrics)
        if avg_dedup_rate < 0.2:
            recommendations.append(
                "LLM deduplication rate is low (<20%). Consider increasing deduplication cache TTL."
            )

        max_queue_size = max(m.batch_queue_size for m in recent_metrics)
        if max_queue_size > 50:
            recommendations.append(
                f"Batch queue is large ({max_queue_size}). Consider increasing "
                "max_batch_size or parallel workers."
            )

        total_slow_queries = sum(m.db_slow_queries for m in recent_metrics)
        if total_slow_queries > 10:
            recommendations.append(
                f"Multiple slow queries detected ({total_slow_queries}). "
                "Review database indexes and query optimization."
            )

        avg_throughput = sum(m.batch_throughput for m in recent_metrics) / len(recent_metrics)
        if avg_throughput < 1.0 and avg_throughput > 0:
            recommendations.append(
                "Batch processing throughput is low (<1 item/s). Consider "
                "reducing per-item complexity or increasing parallelism."
            )

        if not recommendations:
            recommendations.append(
                "All metrics are within acceptable ranges. System is performing well!"
            )

        return recommendations


# Global monitor instance
_global_monitor: OptimizationMonitor | None = None


async def get_global_monitor() -> OptimizationMonitor:
    """Get or create global optimization monitor."""
    global _global_monitor

    if _global_monitor is None:
        _global_monitor = OptimizationMonitor()
        await _global_monitor.start()

    return _global_monitor


# Convenience function for getting metrics


async def get_optimization_metrics() -> dict[str, Any]:
    """Get current optimization metrics.

    Returns:
        Dictionary with current metrics

    Example:
        metrics = await get_optimization_metrics()
        print(f"Cache hit rate: {metrics['cache']['hit_rate']:.1%}")
    """
    monitor = await get_global_monitor()
    return await monitor.get_current_metrics()


async def get_performance_report() -> dict[str, Any]:
    """Get comprehensive performance report.

    Returns:
        Dictionary with performance report and recommendations

    Example:
        report = await get_performance_report()
        for rec in report['recommendations']:
            print(rec)
    """
    monitor = await get_global_monitor()
    return await monitor.get_performance_report()
