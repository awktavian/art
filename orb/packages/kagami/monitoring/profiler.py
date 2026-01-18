"""Real-time Performance Profiling System.

Provides continuous performance profiling with minimal overhead:
- CPU profiling with statistical sampling
- Memory allocation tracking
- I/O operation monitoring
- Function-level timing analysis
- Resource utilization tracking

Designed for production use with <1% performance impact.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import functools
import logging
import sys
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import psutil

logger = logging.getLogger(__name__)


@dataclass
class ProfileMetric:
    """A single profiling measurement."""

    name: str
    value: float
    timestamp: float
    context: dict[str, Any] = field(default_factory=dict)
    stack_trace: list[str] = field(default_factory=list)


@dataclass
class FunctionProfile:
    """Performance profile for a function."""

    name: str
    call_count: int = 0
    total_time: float = 0.0
    avg_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    memory_delta: int = 0
    recent_calls: deque[float] = field(default_factory=lambda: deque(maxlen=100))


class RealTimeProfiler:
    """Real-time performance profiler for production systems.

    Features:
    - Statistical CPU sampling
    - Memory allocation tracking
    - Function call profiling
    - Resource utilization monitoring
    - Hot path identification
    - Performance regression detection
    """

    def __init__(self, sample_interval: float = 0.1, max_samples: int = 10000):
        self.sample_interval = sample_interval
        self.max_samples = max_samples

        # Profiling data storage
        self._cpu_samples: deque[ProfileMetric] = deque(maxlen=max_samples)
        self._memory_samples: deque[ProfileMetric] = deque(maxlen=max_samples)
        self._io_samples: deque[ProfileMetric] = deque(maxlen=max_samples)
        self._function_profiles: dict[str, FunctionProfile] = {}

        # Sampling state
        self._sampling = False
        self._sample_thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Process info
        self._process = psutil.Process()
        self._start_time = time.time()

        # Hot path detection
        self._hot_paths: dict[str, int] = defaultdict(int)
        self._critical_functions = set()

        # Performance baselines
        self._baselines: dict[str, float] = {}
        self._regression_threshold = 0.2  # 20% performance degradation threshold

    def start(self) -> None:
        """Start real-time profiling."""
        if self._sampling:
            return

        self._sampling = True
        self._sample_thread = threading.Thread(target=self._sampling_loop, daemon=True)
        self._sample_thread.start()

        logger.info("📊 Real-time profiler started")

    def stop(self) -> None:
        """Stop profiling."""
        self._sampling = False

        if self._sample_thread:
            self._sample_thread.join(timeout=1.0)

        logger.info("📊 Real-time profiler stopped")

    def _sampling_loop(self) -> None:
        """Main sampling loop running in background thread."""
        while self._sampling:
            try:
                # Sample CPU usage
                cpu_percent = self._process.cpu_percent()
                self._record_sample(self._cpu_samples, "cpu_percent", cpu_percent)

                # Sample memory usage
                memory_info = self._process.memory_info()
                self._record_sample(self._memory_samples, "memory_rss", memory_info.rss)
                self._record_sample(self._memory_samples, "memory_vms", memory_info.vms)

                # Sample I/O stats
                try:
                    io_counters = self._process.io_counters()
                    self._record_sample(self._io_samples, "io_read_bytes", io_counters.read_bytes)
                    self._record_sample(self._io_samples, "io_write_bytes", io_counters.write_bytes)
                except (AttributeError, OSError):
                    # I/O counters not available on all platforms
                    pass

                # Sample call stack for hot path detection
                self._sample_call_stack()

                time.sleep(self.sample_interval)

            except Exception as e:
                logger.error(f"Profiler sampling error: {e}")
                time.sleep(1.0)

    def _record_sample(self, sample_queue: deque, name: str, value: float) -> None:
        """Record a performance sample."""
        with self._lock:
            sample_queue.append(ProfileMetric(name=name, value=value, timestamp=time.time()))

    def _sample_call_stack(self) -> None:
        """Sample current call stack for hot path detection."""
        try:
            # Get current frame
            frame = sys._getframe(1)
            stack_frames = []

            # Walk up the stack
            while frame and len(stack_frames) < 10:
                filename = frame.f_code.co_filename
                function = frame.f_code.co_name
                lineno = frame.f_lineno

                # Skip profiler frames
                if "profiler.py" not in filename:
                    stack_frames.append(f"{function}:{lineno}")

                frame = frame.f_back

            if stack_frames:
                path = " -> ".join(reversed(stack_frames))
                self._hot_paths[path] += 1

        except Exception:
            # Stack sampling is best-effort
            pass

    @contextmanager
    def profile_function(self, name: str) -> Generator[None, None, None]:
        """Context manager for profiling function execution."""
        start_time = time.time()
        start_memory = self._get_memory_usage()

        try:
            yield
        finally:
            end_time = time.time()
            end_memory = self._get_memory_usage()

            execution_time = end_time - start_time
            memory_delta = end_memory - start_memory

            self._record_function_call(name, execution_time, memory_delta)

    def _get_memory_usage(self) -> int:
        """Get current memory usage in bytes."""
        try:
            return self._process.memory_info().rss
        except Exception:
            return 0

    def _record_function_call(self, name: str, execution_time: float, memory_delta: int) -> None:
        """Record function call performance data."""
        with self._lock:
            if name not in self._function_profiles:
                self._function_profiles[name] = FunctionProfile(name=name)

            profile = self._function_profiles[name]
            profile.call_count += 1
            profile.total_time += execution_time
            profile.avg_time = profile.total_time / profile.call_count
            profile.min_time = min(profile.min_time, execution_time)
            profile.max_time = max(profile.max_time, execution_time)
            profile.memory_delta += memory_delta
            profile.recent_calls.append(execution_time)

            # Check for performance regressions
            self._check_regression(name, execution_time)

    def _check_regression(self, function_name: str, execution_time: float) -> None:
        """Check for performance regressions."""
        baseline = self._baselines.get(function_name)

        if baseline is None:
            # Set baseline after 10 calls
            profile = self._function_profiles.get(function_name)
            if profile and profile.call_count >= 10:
                self._baselines[function_name] = profile.avg_time
        else:
            # Check for regression
            if execution_time > baseline * (1 + self._regression_threshold):
                logger.warning(
                    f"🐌 Performance regression detected in {function_name}: "
                    f"{execution_time * 1000:.1f}ms vs baseline {baseline * 1000:.1f}ms"
                )

    def profile(self, func: Callable | None = None, *, name: str | None = None):
        """Decorator for profiling functions."""

        def decorator(f: Callable) -> Callable:
            profile_name = name or f"{f.__module__}.{f.__name__}"

            if asyncio.iscoroutinefunction(f):

                @functools.wraps(f)
                async def async_wrapper(*args, **kwargs):
                    with self.profile_function(profile_name):
                        return await f(*args, **kwargs)

                return async_wrapper
            else:

                @functools.wraps(f)
                def sync_wrapper(*args, **kwargs):
                    with self.profile_function(profile_name):
                        return f(*args, **kwargs)

                return sync_wrapper

        if func is None:
            return decorator
        else:
            return decorator(func)

    def mark_critical(self, function_name: str) -> None:
        """Mark a function as critical for monitoring."""
        self._critical_functions.add(function_name)

    def get_performance_summary(self) -> dict[str, Any]:
        """Get comprehensive performance summary."""
        with self._lock:
            uptime = time.time() - self._start_time

            # CPU stats
            cpu_samples = list(self._cpu_samples)
            cpu_usage = (
                sum(s.value for s in cpu_samples[-60:]) / min(len(cpu_samples), 60)
                if cpu_samples
                else 0
            )

            # Memory stats
            memory_samples = [s for s in self._memory_samples if s.name == "memory_rss"]
            current_memory = memory_samples[-1].value if memory_samples else 0
            peak_memory = max(s.value for s in memory_samples) if memory_samples else 0

            # Function stats
            function_stats = {}
            for name, profile in self._function_profiles.items():
                recent_avg = (
                    sum(profile.recent_calls) / len(profile.recent_calls)
                    if profile.recent_calls
                    else 0
                )
                function_stats[name] = {
                    "call_count": profile.call_count,
                    "avg_time_ms": profile.avg_time * 1000,
                    "recent_avg_ms": recent_avg * 1000,
                    "min_time_ms": profile.min_time * 1000,
                    "max_time_ms": profile.max_time * 1000,
                    "total_time_s": profile.total_time,
                    "memory_delta_mb": profile.memory_delta / (1024 * 1024),
                    "is_critical": name in self._critical_functions,
                }

            # Hot paths
            top_hot_paths = dict(
                sorted(self._hot_paths.items(), key=lambda x: x[1], reverse=True)[:10]
            )

            return {
                "uptime_seconds": uptime,
                "cpu": {"current_percent": cpu_usage, "samples": len(cpu_samples)},
                "memory": {
                    "current_mb": current_memory / (1024 * 1024),
                    "peak_mb": peak_memory / (1024 * 1024),
                    "samples": len(memory_samples),
                },
                "functions": function_stats,
                "hot_paths": top_hot_paths,
                "critical_functions": list(self._critical_functions),
                "sampling": {"interval": self.sample_interval, "active": self._sampling},
            }

    def get_critical_function_stats(self) -> dict[str, dict[str, Any]]:
        """Get performance stats for critical functions only."""
        with self._lock:
            stats = {}
            for name in self._critical_functions:
                if name in self._function_profiles:
                    profile = self._function_profiles[name]
                    recent_avg = (
                        sum(profile.recent_calls) / len(profile.recent_calls)
                        if profile.recent_calls
                        else 0
                    )

                    stats[name] = {
                        "avg_time_ms": profile.avg_time * 1000,
                        "recent_avg_ms": recent_avg * 1000,
                        "call_count": profile.call_count,
                        "p95_time_ms": self._calculate_percentile(profile.recent_calls, 0.95)
                        * 1000,
                        "p99_time_ms": self._calculate_percentile(profile.recent_calls, 0.99)
                        * 1000,
                    }

            return stats

    def _calculate_percentile(self, values: deque, percentile: float) -> float:
        """Calculate percentile from a deque of values."""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def export_flamegraph_data(self) -> dict[str, Any]:
        """Export data suitable for flame graph visualization."""
        with self._lock:
            # Convert hot paths to flame graph format
            flame_data = {"name": "root", "value": 0, "children": []}

            for path, count in self._hot_paths.items():
                parts = path.split(" -> ")
                current_node = flame_data

                for part in parts:
                    # Find or create child node
                    child = None
                    for c in current_node["children"]:
                        if c["name"] == part:
                            child = c
                            break

                    if not child:
                        child = {"name": part, "value": 0, "children": []}
                        current_node["children"].append(child)

                    child["value"] += count
                    current_node = child

            return flame_data

    def get_resource_utilization(self) -> dict[str, float]:
        """Get current resource utilization metrics."""
        try:
            cpu_percent = self._process.cpu_percent()
            memory_info = self._process.memory_info()
            memory_percent = self._process.memory_percent()

            # Get system-wide stats for context
            system_cpu = psutil.cpu_percent()
            system_memory = psutil.virtual_memory().percent

            return {
                "process_cpu_percent": cpu_percent,
                "process_memory_percent": memory_percent,
                "process_memory_mb": memory_info.rss / (1024 * 1024),
                "system_cpu_percent": system_cpu,
                "system_memory_percent": system_memory,
                "threads": self._process.num_threads(),
                "open_files": len(self._process.open_files()),
            }
        except Exception as e:
            logger.error(f"Error getting resource utilization: {e}")
            return {}

    def reset_baselines(self) -> None:
        """Reset performance baselines."""
        with self._lock:
            self._baselines.clear()
            logger.info("📊 Performance baselines reset")

    def set_regression_threshold(self, threshold: float) -> None:
        """Set performance regression detection threshold."""
        self._regression_threshold = threshold
        logger.info(f"📊 Regression threshold set to {threshold * 100:.1f}%")


# Global profiler instance
_global_profiler: RealTimeProfiler | None = None


def get_profiler() -> RealTimeProfiler:
    """Get the global profiler instance."""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = RealTimeProfiler()

    return _global_profiler


def profile(func: Callable | None = None, *, name: str | None = None):
    """Convenience decorator for profiling functions."""
    return get_profiler().profile(func, name=name)


def mark_critical(function_name: str) -> None:
    """Mark a function as critical for monitoring."""
    get_profiler().mark_critical(function_name)
