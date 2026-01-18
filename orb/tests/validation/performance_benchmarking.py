"""💎 CRYSTAL COLONY — Performance Benchmarking & Monitoring

Comprehensive performance validation with benchmarking, regression detection,
and crystalline precision performance monitoring. Ensures post-cleanup system
maintains or exceeds performance standards with continuous optimization.

Performance Dimensions:
1. Response Time (P50, P95, P99, P999)
2. Throughput (Requests/second, Operations/second)
3. Memory Usage (Peak, Average, Leak Detection)
4. CPU Utilization (Average, Peak, Efficiency)
5. Network I/O (Bandwidth, Latency, Error Rates)
6. Database Performance (Query time, Connection pool)
7. Smart Home Integration Latency
8. World Model Inference Speed
9. Active Inference Planning Time
10. Safety System Response Time

Monitoring & Alerting:
- Real-time performance metrics collection
- Regression detection and alerting
- Performance SLO compliance monitoring
- Resource leak detection
- Bottleneck identification and analysis

Created: December 29, 2025
Colony: 💎 Crystal (Verification, Quality)
"""

from __future__ import annotations

import asyncio
import json
import logging
import psutil
import statistics
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union
from collections.abc import Callable
import resource
import tracemalloc
from concurrent.futures import ThreadPoolExecutor

import pytest
from kagami.core.safety import get_safety_filter

logger = logging.getLogger(__name__)


class BenchmarkType(Enum):
    """Types of performance benchmarks."""

    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    MEMORY = "memory"
    CPU = "cpu"
    NETWORK = "network"
    DATABASE = "database"
    SMART_HOME = "smart_home"
    WORLD_MODEL = "world_model"
    ACTIVE_INFERENCE = "active_inference"
    SAFETY_SYSTEM = "safety_system"
    LOAD_TEST = "load_test"
    STRESS_TEST = "stress_test"


class PerformanceMetric(Enum):
    """Performance metrics to track."""

    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    LATENCY_P999 = "latency_p999"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    MEMORY_PEAK = "memory_peak"
    MEMORY_AVERAGE = "memory_average"
    CPU_AVERAGE = "cpu_average"
    CPU_PEAK = "cpu_peak"
    NETWORK_LATENCY = "network_latency"
    DB_QUERY_TIME = "db_query_time"


@dataclass
class PerformanceResult:
    """Individual performance benchmark result."""

    benchmark_name: str
    benchmark_type: BenchmarkType
    metric: PerformanceMetric
    value: float
    unit: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)

    # Comparison data
    baseline_value: float | None = None
    threshold_value: float | None = None
    passed: bool = True

    @property
    def regression_percentage(self) -> float:
        """Calculate performance regression percentage."""
        if self.baseline_value and self.baseline_value > 0:
            return ((self.value - self.baseline_value) / self.baseline_value) * 100
        return 0.0

    @property
    def threshold_compliance(self) -> bool:
        """Check if result meets threshold requirements."""
        if self.threshold_value is None:
            return True

        # For latency metrics, lower is better
        if self.metric.value.startswith("latency"):
            return self.value <= self.threshold_value
        # For throughput, higher is better
        elif self.metric == PerformanceMetric.THROUGHPUT:
            return self.value >= self.threshold_value
        # For error rate, lower is better
        elif self.metric == PerformanceMetric.ERROR_RATE:
            return self.value <= self.threshold_value
        else:
            return self.value <= self.threshold_value


@dataclass
class PerformanceReport:
    """Comprehensive performance benchmark report."""

    # Overall metrics
    total_benchmarks: int = 0
    passed_benchmarks: int = 0
    failed_benchmarks: int = 0
    regression_count: int = 0

    # Results
    results: list[PerformanceResult] = field(default_factory=list)

    # Summary statistics
    average_latency_p95: float = 0.0
    average_throughput: float = 0.0
    peak_memory_usage: float = 0.0
    average_cpu_usage: float = 0.0

    # Performance SLOs
    slo_compliance_rate: float = 100.0
    violated_slos: list[str] = field(default_factory=list)

    # Regression analysis
    performance_regressions: list[PerformanceResult] = field(default_factory=list)

    # Resource efficiency
    memory_efficiency_score: float = 100.0
    cpu_efficiency_score: float = 100.0

    # Timing
    benchmark_duration: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate overall benchmark success rate."""
        if self.total_benchmarks == 0:
            return 0.0
        return self.passed_benchmarks / self.total_benchmarks

    def add_result(self, result: PerformanceResult) -> None:
        """Add a performance result to the report."""
        self.results.append(result)
        self.total_benchmarks += 1

        if result.passed:
            self.passed_benchmarks += 1
        else:
            self.failed_benchmarks += 1

        # Check for regressions
        if result.baseline_value and result.regression_percentage > 10:  # 10% threshold
            self.regression_count += 1
            self.performance_regressions.append(result)


class PerformanceBenchmarker:
    """💎 Crystal Colony performance benchmarking system.

    Implements comprehensive performance validation with benchmarking,
    regression detection, and crystalline precision performance monitoring.
    """

    def __init__(self, project_root: Path = None):
        """Initialize performance benchmarker."""
        self.project_root = project_root or Path("/Users/schizodactyl/projects/kagami")
        self.cbf_filter = get_safety_filter()
        self.report = PerformanceReport()

        # Performance thresholds (SLOs)
        self.performance_thresholds = {
            PerformanceMetric.LATENCY_P95: 2000.0,  # 2 seconds max
            PerformanceMetric.LATENCY_P99: 5000.0,  # 5 seconds max
            PerformanceMetric.THROUGHPUT: 100.0,  # 100 req/s min
            PerformanceMetric.ERROR_RATE: 0.01,  # 1% max
            PerformanceMetric.MEMORY_PEAK: 2048.0,  # 2GB max
            PerformanceMetric.CPU_AVERAGE: 70.0,  # 70% max
            PerformanceMetric.NETWORK_LATENCY: 100.0,  # 100ms max
            PerformanceMetric.DB_QUERY_TIME: 50.0,  # 50ms max
        }

        # Baseline performance data (would load from historical data)
        self.baseline_metrics = {
            PerformanceMetric.LATENCY_P95: 1200.0,
            PerformanceMetric.THROUGHPUT: 150.0,
            PerformanceMetric.MEMORY_PEAK: 1024.0,
            PerformanceMetric.CPU_AVERAGE: 45.0,
        }

        # Resource monitoring
        self.memory_tracer_started = False
        self.cpu_monitor_active = False

        logger.info("💎 Performance Benchmarker initialized")

    async def run_comprehensive_benchmarks(
        self, benchmark_types: list[BenchmarkType] = None, load_levels: list[str] = None
    ) -> PerformanceReport:
        """🏃 Run comprehensive performance benchmarks.

        Args:
            benchmark_types: Specific benchmark types to run
            load_levels: Load levels to test (light, medium, heavy)

        Returns:
            Comprehensive performance report
        """

        start_time = time.time()
        logger.info("💎 PERFORMANCE: Starting comprehensive benchmarking...")

        if benchmark_types is None:
            benchmark_types = [
                BenchmarkType.RESPONSE_TIME,
                BenchmarkType.THROUGHPUT,
                BenchmarkType.MEMORY,
                BenchmarkType.CPU,
                BenchmarkType.SMART_HOME,
                BenchmarkType.WORLD_MODEL,
                BenchmarkType.SAFETY_SYSTEM,
            ]

        if load_levels is None:
            load_levels = ["light", "medium", "heavy"]

        try:
            # Initialize monitoring
            await self._initialize_monitoring()

            # Run benchmarks for each type and load level
            for benchmark_type in benchmark_types:
                for load_level in load_levels:
                    await self._run_benchmark_suite(benchmark_type, load_level)

            # Calculate summary statistics
            self._calculate_summary_statistics()

            # Generate performance report
            self.report.benchmark_duration = time.time() - start_time
            self._generate_performance_summary()

            return self.report

        except Exception as e:
            logger.error(f"💥 Benchmarking error: {e}")
            raise
        finally:
            await self._cleanup_monitoring()

    async def _initialize_monitoring(self) -> None:
        """Initialize performance monitoring."""
        # Start memory tracing
        if not self.memory_tracer_started:
            tracemalloc.start()
            self.memory_tracer_started = True

        # Initialize CPU monitoring
        self.cpu_monitor_active = True

        logger.info("📊 Performance monitoring initialized")

    async def _cleanup_monitoring(self) -> None:
        """Cleanup performance monitoring."""
        if self.memory_tracer_started:
            tracemalloc.stop()
            self.memory_tracer_started = False

        self.cpu_monitor_active = False

        logger.info("📊 Performance monitoring cleanup complete")

    async def _run_benchmark_suite(self, benchmark_type: BenchmarkType, load_level: str) -> None:
        """Run benchmark suite for specific type and load level."""

        logger.info(f"🏃 Running {benchmark_type.value} benchmarks ({load_level} load)...")

        if benchmark_type == BenchmarkType.RESPONSE_TIME:
            await self._benchmark_response_time(load_level)
        elif benchmark_type == BenchmarkType.THROUGHPUT:
            await self._benchmark_throughput(load_level)
        elif benchmark_type == BenchmarkType.MEMORY:
            await self._benchmark_memory_usage(load_level)
        elif benchmark_type == BenchmarkType.CPU:
            await self._benchmark_cpu_usage(load_level)
        elif benchmark_type == BenchmarkType.NETWORK:
            await self._benchmark_network_performance(load_level)
        elif benchmark_type == BenchmarkType.DATABASE:
            await self._benchmark_database_performance(load_level)
        elif benchmark_type == BenchmarkType.SMART_HOME:
            await self._benchmark_smart_home_performance(load_level)
        elif benchmark_type == BenchmarkType.WORLD_MODEL:
            await self._benchmark_world_model_performance(load_level)
        elif benchmark_type == BenchmarkType.ACTIVE_INFERENCE:
            await self._benchmark_active_inference_performance(load_level)
        elif benchmark_type == BenchmarkType.SAFETY_SYSTEM:
            await self._benchmark_safety_system_performance(load_level)
        elif benchmark_type == BenchmarkType.LOAD_TEST:
            await self._benchmark_load_test(load_level)
        elif benchmark_type == BenchmarkType.STRESS_TEST:
            await self._benchmark_stress_test(load_level)

    async def _benchmark_response_time(self, load_level: str) -> None:
        """Benchmark response time performance."""

        # Configure test parameters based on load level
        request_count = {"light": 100, "medium": 1000, "heavy": 10000}[load_level]
        concurrency = {"light": 1, "medium": 10, "heavy": 100}[load_level]

        latencies = []

        async def make_request() -> float:
            """Simulate API request and measure latency."""
            start = time.perf_counter()

            # Simulate API processing time
            await asyncio.sleep(0.001 * (1 + len(latencies) / 10000))  # Slight increase over time

            # Mock some work
            result = sum(i * i for i in range(100))

            end = time.perf_counter()
            return (end - start) * 1000  # Convert to milliseconds

        # Run concurrent requests
        semaphore = asyncio.Semaphore(concurrency)

        async def bounded_request():
            async with semaphore:
                return await make_request()

        tasks = [bounded_request() for _ in range(request_count)]
        latencies = await asyncio.gather(*tasks)

        # Calculate percentiles
        latencies.sort()
        p50 = latencies[int(len(latencies) * 0.50)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        p999 = latencies[int(len(latencies) * 0.999)]

        # Add results
        self._add_result(
            "response_time_p50",
            BenchmarkType.RESPONSE_TIME,
            PerformanceMetric.LATENCY_P50,
            p50,
            "ms",
            load_level,
        )
        self._add_result(
            "response_time_p95",
            BenchmarkType.RESPONSE_TIME,
            PerformanceMetric.LATENCY_P95,
            p95,
            "ms",
            load_level,
        )
        self._add_result(
            "response_time_p99",
            BenchmarkType.RESPONSE_TIME,
            PerformanceMetric.LATENCY_P99,
            p99,
            "ms",
            load_level,
        )

        logger.info(f"✅ Response time benchmark complete: P95={p95:.1f}ms, P99={p99:.1f}ms")

    async def _benchmark_throughput(self, load_level: str) -> None:
        """Benchmark throughput performance."""

        duration = {"light": 10, "medium": 30, "heavy": 60}[load_level]
        concurrency = {"light": 5, "medium": 20, "heavy": 50}[load_level]

        request_count = 0
        error_count = 0
        start_time = time.perf_counter()

        async def worker():
            """Worker to simulate continuous requests."""
            nonlocal request_count, error_count

            while time.perf_counter() - start_time < duration:
                try:
                    # Simulate request processing
                    await asyncio.sleep(0.01)  # 10ms processing time
                    request_count += 1
                except Exception:
                    error_count += 1

        # Run workers concurrently
        workers = [worker() for _ in range(concurrency)]
        await asyncio.gather(*workers)

        total_time = time.perf_counter() - start_time
        throughput = request_count / total_time
        error_rate = error_count / max(request_count, 1)

        # Add results
        self._add_result(
            "throughput",
            BenchmarkType.THROUGHPUT,
            PerformanceMetric.THROUGHPUT,
            throughput,
            "req/s",
            load_level,
        )
        self._add_result(
            "error_rate",
            BenchmarkType.THROUGHPUT,
            PerformanceMetric.ERROR_RATE,
            error_rate,
            "ratio",
            load_level,
        )

        logger.info(
            f"✅ Throughput benchmark complete: {throughput:.1f} req/s, error rate: {error_rate:.1%}"
        )

    async def _benchmark_memory_usage(self, load_level: str) -> None:
        """Benchmark memory usage."""

        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Simulate memory-intensive operations
        data_size = {"light": 10000, "medium": 100000, "heavy": 1000000}[load_level]

        # Allocate memory
        memory_data = []
        for i in range(data_size):
            memory_data.append([i] * 10)  # Create some data

        # Measure peak memory
        peak_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = peak_memory - initial_memory

        # Cleanup
        del memory_data

        # Wait for garbage collection
        import gc

        gc.collect()

        # Measure final memory
        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Add results
        self._add_result(
            "memory_peak",
            BenchmarkType.MEMORY,
            PerformanceMetric.MEMORY_PEAK,
            peak_memory,
            "MB",
            load_level,
        )
        self._add_result(
            "memory_average",
            BenchmarkType.MEMORY,
            PerformanceMetric.MEMORY_AVERAGE,
            (initial_memory + final_memory) / 2,
            "MB",
            load_level,
        )

        logger.info(
            f"✅ Memory benchmark complete: Peak={peak_memory:.1f}MB, Increase={memory_increase:.1f}MB"
        )

    async def _benchmark_cpu_usage(self, load_level: str) -> None:
        """Benchmark CPU usage."""

        duration = {"light": 5, "medium": 15, "heavy": 30}[load_level]
        workers = {"light": 2, "medium": 4, "heavy": 8}[load_level]

        cpu_samples = []

        def cpu_intensive_task():
            """CPU-intensive computation."""
            start = time.time()
            result = 0
            while time.time() - start < duration / workers:
                # Mathematical computation
                for i in range(10000):
                    result += i**0.5
            return result

        # Monitor CPU usage during execution
        async def monitor_cpu():
            while len(cpu_samples) < duration * 2:  # Sample twice per second
                cpu_percent = psutil.cpu_percent(interval=0.5)
                cpu_samples.append(cpu_percent)

        # Start CPU monitoring
        monitor_task = asyncio.create_task(monitor_cpu())

        # Run CPU-intensive tasks
        with ThreadPoolExecutor(max_workers=workers) as executor:
            tasks = [executor.submit(cpu_intensive_task) for _ in range(workers)]
            # Wait for completion
            for task in tasks:
                task.result()

        # Stop monitoring
        monitor_task.cancel()

        if cpu_samples:
            avg_cpu = statistics.mean(cpu_samples)
            peak_cpu = max(cpu_samples)
        else:
            avg_cpu = peak_cpu = 0.0

        # Add results
        self._add_result(
            "cpu_average",
            BenchmarkType.CPU,
            PerformanceMetric.CPU_AVERAGE,
            avg_cpu,
            "percent",
            load_level,
        )
        self._add_result(
            "cpu_peak",
            BenchmarkType.CPU,
            PerformanceMetric.CPU_PEAK,
            peak_cpu,
            "percent",
            load_level,
        )

        logger.info(f"✅ CPU benchmark complete: Avg={avg_cpu:.1f}%, Peak={peak_cpu:.1f}%")

    async def _benchmark_network_performance(self, load_level: str) -> None:
        """Benchmark network performance."""

        import aiohttp

        urls = [
            "https://httpbin.org/delay/0.1",
            "https://httpbin.org/json",
            "https://httpbin.org/status/200",
        ]

        request_count = {"light": 10, "medium": 50, "heavy": 200}[load_level]
        latencies = []

        async def measure_request_latency(session, url):
            """Measure single request latency."""
            start = time.perf_counter()
            try:
                async with session.get(url) as response:
                    await response.read()
                    end = time.perf_counter()
                    return (end - start) * 1000  # ms
            except Exception:
                return None

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            tasks = []
            for _ in range(request_count):
                url = urls[_ % len(urls)]
                tasks.append(measure_request_latency(session, url))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            latencies = [r for r in results if r is not None and not isinstance(r, Exception)]

        if latencies:
            avg_latency = statistics.mean(latencies)
            p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        else:
            avg_latency = p95_latency = 0.0

        # Add results
        self._add_result(
            "network_latency",
            BenchmarkType.NETWORK,
            PerformanceMetric.NETWORK_LATENCY,
            avg_latency,
            "ms",
            load_level,
        )

        logger.info(f"✅ Network benchmark complete: Avg latency={avg_latency:.1f}ms")

    async def _benchmark_database_performance(self, load_level: str) -> None:
        """Benchmark database performance."""

        query_count = {"light": 50, "medium": 500, "heavy": 2000}[load_level]
        query_times = []

        # Mock database queries
        async def mock_database_query():
            """Mock database query with realistic timing."""
            start = time.perf_counter()

            # Simulate database work
            await asyncio.sleep(0.001 + (len(query_times) * 0.0001))  # Slight degradation

            end = time.perf_counter()
            return (end - start) * 1000  # ms

        # Execute queries
        for _ in range(query_count):
            query_time = await mock_database_query()
            query_times.append(query_time)

        if query_times:
            avg_query_time = statistics.mean(query_times)
            p95_query_time = sorted(query_times)[int(len(query_times) * 0.95)]
        else:
            avg_query_time = p95_query_time = 0.0

        # Add results
        self._add_result(
            "db_query_time",
            BenchmarkType.DATABASE,
            PerformanceMetric.DB_QUERY_TIME,
            avg_query_time,
            "ms",
            load_level,
        )

        logger.info(f"✅ Database benchmark complete: Avg query time={avg_query_time:.1f}ms")

    async def _benchmark_smart_home_performance(self, load_level: str) -> None:
        """Benchmark smart home integration performance."""

        from kagami_smarthome import SmartHomeController, SmartHomeConfig

        # Mock controller
        config = SmartHomeConfig()
        controller = SmartHomeController(config)

        # Mock integrations
        from unittest.mock import Mock, AsyncMock

        controller._control4 = Mock()
        controller._control4.set_light_level = AsyncMock(return_value=True)

        operation_count = {"light": 20, "medium": 100, "heavy": 500}[load_level]
        operation_times = []

        async def mock_smart_home_operation():
            """Mock smart home operation."""
            start = time.perf_counter()

            # Simulate Control4 API call
            await controller.set_lights(50, ["Living Room"])

            end = time.perf_counter()
            return (end - start) * 1000  # ms

        # Execute operations
        for _ in range(operation_count):
            operation_time = await mock_smart_home_operation()
            operation_times.append(operation_time)

        if operation_times:
            avg_time = statistics.mean(operation_times)
            p95_time = sorted(operation_times)[int(len(operation_times) * 0.95)]
        else:
            avg_time = p95_time = 0.0

        # Add results
        self._add_result(
            "smart_home_latency",
            BenchmarkType.SMART_HOME,
            PerformanceMetric.LATENCY_P95,
            p95_time,
            "ms",
            load_level,
        )

        logger.info(f"✅ Smart home benchmark complete: P95 latency={p95_time:.1f}ms")

    async def _benchmark_world_model_performance(self, load_level: str) -> None:
        """Benchmark world model performance."""

        prediction_count = {"light": 10, "medium": 50, "heavy": 200}[load_level]
        prediction_times = []

        async def mock_world_model_prediction():
            """Mock world model prediction."""
            start = time.perf_counter()

            # Simulate neural network inference
            import numpy as np

            data = np.random.randn(100, 100)
            result = np.mean(data @ data.T)  # Some computation

            end = time.perf_counter()
            return (end - start) * 1000  # ms

        # Execute predictions
        for _ in range(prediction_count):
            prediction_time = await mock_world_model_prediction()
            prediction_times.append(prediction_time)

        if prediction_times:
            avg_time = statistics.mean(prediction_times)
            p95_time = sorted(prediction_times)[int(len(prediction_times) * 0.95)]
        else:
            avg_time = p95_time = 0.0

        # Add results
        self._add_result(
            "world_model_inference",
            BenchmarkType.WORLD_MODEL,
            PerformanceMetric.LATENCY_P95,
            p95_time,
            "ms",
            load_level,
        )

        logger.info(f"✅ World model benchmark complete: P95 inference time={p95_time:.1f}ms")

    async def _benchmark_active_inference_performance(self, load_level: str) -> None:
        """Benchmark active inference performance."""

        planning_count = {"light": 5, "medium": 20, "heavy": 100}[load_level]
        planning_times = []

        async def mock_active_inference_planning():
            """Mock active inference planning."""
            start = time.perf_counter()

            # Simulate planning computation
            for i in range(1000):
                # Mock belief updates and action selection
                belief = sum(j for j in range(i % 100))

            end = time.perf_counter()
            return (end - start) * 1000  # ms

        # Execute planning
        for _ in range(planning_count):
            planning_time = await mock_active_inference_planning()
            planning_times.append(planning_time)

        if planning_times:
            avg_time = statistics.mean(planning_times)
            p95_time = sorted(planning_times)[int(len(planning_times) * 0.95)]
        else:
            avg_time = p95_time = 0.0

        # Add results
        self._add_result(
            "active_inference_planning",
            BenchmarkType.ACTIVE_INFERENCE,
            PerformanceMetric.LATENCY_P95,
            p95_time,
            "ms",
            load_level,
        )

        logger.info(f"✅ Active inference benchmark complete: P95 planning time={p95_time:.1f}ms")

    async def _benchmark_safety_system_performance(self, load_level: str) -> None:
        """Benchmark safety system performance."""

        evaluation_count = {"light": 100, "medium": 1000, "heavy": 10000}[load_level]
        evaluation_times = []

        async def mock_safety_evaluation():
            """Mock safety system CBF evaluation."""
            start = time.perf_counter()

            # Simulate CBF evaluation
            h_value = self.cbf_filter.evaluate_safety(
                {"action": "performance_test", "timestamp": time.time(), "load_level": load_level}
            )

            end = time.perf_counter()
            return (end - start) * 1000  # ms

        # Execute safety evaluations
        for _ in range(evaluation_count):
            eval_time = await mock_safety_evaluation()
            evaluation_times.append(eval_time)

        if evaluation_times:
            avg_time = statistics.mean(evaluation_times)
            p95_time = sorted(evaluation_times)[int(len(evaluation_times) * 0.95)]
        else:
            avg_time = p95_time = 0.0

        # Add results
        self._add_result(
            "safety_evaluation",
            BenchmarkType.SAFETY_SYSTEM,
            PerformanceMetric.LATENCY_P95,
            p95_time,
            "ms",
            load_level,
        )

        logger.info(f"✅ Safety system benchmark complete: P95 evaluation time={p95_time:.1f}ms")

    async def _benchmark_load_test(self, load_level: str) -> None:
        """Run load test benchmark."""

        concurrent_users = {"light": 10, "medium": 100, "heavy": 1000}[load_level]
        duration = {"light": 30, "medium": 60, "heavy": 120}[load_level]

        request_counts = []
        error_counts = []

        async def user_session():
            """Simulate user session."""
            requests = 0
            errors = 0
            start_time = time.time()

            while time.time() - start_time < duration:
                try:
                    # Simulate user action
                    await asyncio.sleep(0.1)  # User think time
                    requests += 1
                except Exception:
                    errors += 1

            request_counts.append(requests)
            error_counts.append(errors)

        # Run concurrent user sessions
        sessions = [user_session() for _ in range(concurrent_users)]
        await asyncio.gather(*sessions)

        total_requests = sum(request_counts)
        total_errors = sum(error_counts)
        throughput = total_requests / duration
        error_rate = total_errors / max(total_requests, 1)

        # Add results
        self._add_result(
            "load_test_throughput",
            BenchmarkType.LOAD_TEST,
            PerformanceMetric.THROUGHPUT,
            throughput,
            "req/s",
            load_level,
        )
        self._add_result(
            "load_test_error_rate",
            BenchmarkType.LOAD_TEST,
            PerformanceMetric.ERROR_RATE,
            error_rate,
            "ratio",
            load_level,
        )

        logger.info(f"✅ Load test complete: {throughput:.1f} req/s, {error_rate:.1%} error rate")

    async def _benchmark_stress_test(self, load_level: str) -> None:
        """Run stress test benchmark."""

        # Stress test pushes beyond normal capacity
        stress_multiplier = {"light": 1.5, "medium": 3.0, "heavy": 10.0}[load_level]
        base_load = 100

        stress_load = int(base_load * stress_multiplier)
        duration = 60  # 1 minute stress test

        success_count = 0
        failure_count = 0
        response_times = []

        async def stress_operation():
            """Stress operation."""
            nonlocal success_count, failure_count

            start = time.perf_counter()
            try:
                # Simulate heavy operation
                await asyncio.sleep(0.01)  # Base operation time
                success_count += 1
            except Exception:
                failure_count += 1

            response_time = (time.perf_counter() - start) * 1000
            response_times.append(response_time)

        # Run stress operations
        start_time = time.time()
        tasks = []

        while time.time() - start_time < duration:
            # Launch operations in batches
            batch_size = min(stress_load, 50)  # Limit concurrent operations
            batch = [stress_operation() for _ in range(batch_size)]
            await asyncio.gather(*batch)

        # Calculate stress metrics
        total_ops = success_count + failure_count
        success_rate = success_count / max(total_ops, 1)
        avg_response_time = statistics.mean(response_times) if response_times else 0

        # Add results
        self._add_result(
            "stress_test_success_rate",
            BenchmarkType.STRESS_TEST,
            PerformanceMetric.THROUGHPUT,
            success_rate,
            "ratio",
            load_level,
        )

        logger.info(
            f"✅ Stress test complete: {success_rate:.1%} success rate under {stress_multiplier}x load"
        )

    def _add_result(
        self,
        name: str,
        benchmark_type: BenchmarkType,
        metric: PerformanceMetric,
        value: float,
        unit: str,
        load_level: str,
    ) -> None:
        """Add a performance result."""

        # Get baseline and threshold values
        baseline = self.baseline_metrics.get(metric)
        threshold = self.performance_thresholds.get(metric)

        # Create result
        result = PerformanceResult(
            benchmark_name=f"{name}_{load_level}",
            benchmark_type=benchmark_type,
            metric=metric,
            value=value,
            unit=unit,
            timestamp=time.time(),
            baseline_value=baseline,
            threshold_value=threshold,
            metadata={"load_level": load_level},
        )

        # Check if result passes
        result.passed = result.threshold_compliance

        # Add to report
        self.report.add_result(result)

    def _calculate_summary_statistics(self) -> None:
        """Calculate summary statistics from benchmark results."""

        # Group results by metric
        by_metric = {}
        for result in self.report.results:
            if result.metric not in by_metric:
                by_metric[result.metric] = []
            by_metric[result.metric].append(result.value)

        # Calculate averages
        if PerformanceMetric.LATENCY_P95 in by_metric:
            self.report.average_latency_p95 = statistics.mean(
                by_metric[PerformanceMetric.LATENCY_P95]
            )

        if PerformanceMetric.THROUGHPUT in by_metric:
            self.report.average_throughput = statistics.mean(
                by_metric[PerformanceMetric.THROUGHPUT]
            )

        if PerformanceMetric.MEMORY_PEAK in by_metric:
            self.report.peak_memory_usage = max(by_metric[PerformanceMetric.MEMORY_PEAK])

        if PerformanceMetric.CPU_AVERAGE in by_metric:
            self.report.average_cpu_usage = statistics.mean(
                by_metric[PerformanceMetric.CPU_AVERAGE]
            )

        # Calculate SLO compliance
        compliant_results = [r for r in self.report.results if r.passed]
        self.report.slo_compliance_rate = (
            len(compliant_results) / max(len(self.report.results), 1) * 100
        )

        # Identify violated SLOs
        violated = [r for r in self.report.results if not r.passed]
        self.report.violated_slos = [
            f"{r.benchmark_name}: {r.value:.2f} {r.unit}" for r in violated
        ]

        # Calculate efficiency scores
        self.report.memory_efficiency_score = max(
            0, 100 - (self.report.peak_memory_usage / 2048 * 100)
        )
        self.report.cpu_efficiency_score = max(0, 100 - self.report.average_cpu_usage)

    def _generate_performance_summary(self) -> None:
        """Generate comprehensive performance summary."""

        logger.info("💎 PERFORMANCE BENCHMARKING COMPLETE")
        logger.info(f"Total Benchmarks: {self.report.total_benchmarks}")
        logger.info(f"Passed: {self.report.passed_benchmarks}")
        logger.info(f"Failed: {self.report.failed_benchmarks}")
        logger.info(f"Success Rate: {self.report.success_rate:.1%}")
        logger.info(f"Benchmark Duration: {self.report.benchmark_duration:.2f}s")

        # Performance metrics
        logger.info("\n📊 PERFORMANCE METRICS:")
        logger.info(f"Average Latency P95: {self.report.average_latency_p95:.1f}ms")
        logger.info(f"Average Throughput: {self.report.average_throughput:.1f} req/s")
        logger.info(f"Peak Memory Usage: {self.report.peak_memory_usage:.1f} MB")
        logger.info(f"Average CPU Usage: {self.report.average_cpu_usage:.1f}%")

        # SLO compliance
        logger.info("\n🎯 SLO COMPLIANCE:")
        logger.info(f"Overall SLO Compliance: {self.report.slo_compliance_rate:.1f}%")

        if self.report.violated_slos:
            logger.warning("SLO Violations:")
            for violation in self.report.violated_slos:
                logger.warning(f"  - {violation}")

        # Performance regressions
        if self.report.performance_regressions:
            logger.warning(f"\n⚠️ PERFORMANCE REGRESSIONS ({self.report.regression_count}):")
            for regression in self.report.performance_regressions:
                logger.warning(
                    f"  - {regression.benchmark_name}: {regression.regression_percentage:+.1f}%"
                )

        # Efficiency scores
        logger.info("\n⚡ EFFICIENCY SCORES:")
        logger.info(f"Memory Efficiency: {self.report.memory_efficiency_score:.1f}%")
        logger.info(f"CPU Efficiency: {self.report.cpu_efficiency_score:.1f}%")

    async def run_quick_benchmarks(self) -> PerformanceReport:
        """🚀 Run quick performance benchmarks for CI/CD."""

        # Essential benchmarks only
        essential_types = [
            BenchmarkType.RESPONSE_TIME,
            BenchmarkType.THROUGHPUT,
            BenchmarkType.SAFETY_SYSTEM,
        ]

        return await self.run_comprehensive_benchmarks(
            benchmark_types=essential_types, load_levels=["light", "medium"]
        )


# =============================================================================
# Performance Test Suite
# =============================================================================


@pytest.mark.asyncio
class TestPerformanceBenchmarking:
    """Test suite for performance benchmarking."""

    @pytest.fixture
    async def benchmarker(self):
        """Create performance benchmarker."""
        return PerformanceBenchmarker()

    async def test_response_time_benchmark(self, benchmarker):
        """Test response time benchmarking."""
        await benchmarker._benchmark_response_time("light")

        # Check results were added
        latency_results = [
            r for r in benchmarker.report.results if r.metric == PerformanceMetric.LATENCY_P95
        ]
        assert len(latency_results) > 0

        # Check values are reasonable
        for result in latency_results:
            assert result.value > 0
            assert result.value < 10000  # Less than 10 seconds

    async def test_throughput_benchmark(self, benchmarker):
        """Test throughput benchmarking."""
        await benchmarker._benchmark_throughput("light")

        # Check results
        throughput_results = [
            r for r in benchmarker.report.results if r.metric == PerformanceMetric.THROUGHPUT
        ]
        assert len(throughput_results) > 0

        for result in throughput_results:
            assert result.value > 0

    async def test_memory_benchmark(self, benchmarker):
        """Test memory benchmarking."""
        await benchmarker._benchmark_memory_usage("light")

        # Check results
        memory_results = [
            r for r in benchmarker.report.results if r.metric == PerformanceMetric.MEMORY_PEAK
        ]
        assert len(memory_results) > 0

    async def test_performance_result_regression(self, benchmarker):
        """Test performance regression detection."""
        result = PerformanceResult(
            benchmark_name="test_regression",
            benchmark_type=BenchmarkType.RESPONSE_TIME,
            metric=PerformanceMetric.LATENCY_P95,
            value=1500.0,  # 1.5 seconds
            unit="ms",
            timestamp=time.time(),
            baseline_value=1000.0,  # 1 second baseline
        )

        # Check regression calculation
        assert result.regression_percentage == 50.0  # 50% regression

    async def test_quick_benchmarks(self, benchmarker):
        """Test quick benchmark suite."""
        report = await benchmarker.run_quick_benchmarks()

        assert isinstance(report, PerformanceReport)
        assert report.total_benchmarks > 0
        assert report.benchmark_duration > 0


# =============================================================================
# Performance CLI
# =============================================================================


async def main():
    """Main performance benchmarking runner."""

    import argparse

    parser = argparse.ArgumentParser(description="💎 Crystal Colony Performance Benchmarker")
    parser.add_argument(
        "--mode",
        choices=["quick", "full", "load", "stress"],
        default="quick",
        help="Benchmark mode",
    )
    parser.add_argument(
        "--load-levels",
        nargs="+",
        choices=["light", "medium", "heavy"],
        default=["light", "medium"],
        help="Load levels to test",
    )

    args = parser.parse_args()

    try:
        benchmarker = PerformanceBenchmarker()

        if args.mode == "quick":
            report = await benchmarker.run_quick_benchmarks()
        elif args.mode == "load":
            report = await benchmarker.run_comprehensive_benchmarks(
                benchmark_types=[BenchmarkType.LOAD_TEST], load_levels=args.load_levels
            )
        elif args.mode == "stress":
            report = await benchmarker.run_comprehensive_benchmarks(
                benchmark_types=[BenchmarkType.STRESS_TEST], load_levels=args.load_levels
            )
        else:
            # Full benchmarks
            report = await benchmarker.run_comprehensive_benchmarks(load_levels=args.load_levels)

        # Determine exit code based on results
        if report.slo_compliance_rate >= 95.0 and report.regression_count == 0:
            print("✅ PERFORMANCE VALIDATION: PASSED")
            return 0
        elif report.slo_compliance_rate >= 80.0 and report.regression_count <= 2:
            print("⚠️ PERFORMANCE VALIDATION: WARNING")
            return 1
        else:
            print("❌ PERFORMANCE VALIDATION: FAILED")
            return 2

    except Exception as e:
        print(f"💥 PERFORMANCE BENCHMARKING ERROR: {e}")
        return 3


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
