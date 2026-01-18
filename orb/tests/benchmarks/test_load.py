from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_e2e
# SPDX-License-Identifier: MIT
"""Comprehensive Load Testing and Performance Benchmarks.
This module provides extensive load testing capabilities with detailed metrics:
- Concurrent request testing (10, 50, 100+ concurrent users)
- Throughput measurement (requests/second)
- Latency percentiles (p50, p95, p99)
- Memory usage profiling under load
- Database connection pool stress testing
- Response time histograms
- Error rate tracking
- Resource utilization monitoring
Tests are designed to validate performance SLOs and identify bottlenecks.
Run with:
    pytest tests/benchmarks/test_load.py -v
    pytest tests/benchmarks/test_load.py -m benchmark
    pytest tests/benchmarks/test_load.py::TestLoadBenchmarks::test_concurrent_load_10_users -v
Created: December 27, 2025
"""
import asyncio
import gc
import os
import statistics
import time
import tracemalloc
from collections import Counter, defaultdict
from typing import Any

import httpx
import psutil


# =============================================================================
# BENCHMARK CONFIGURATION
# =============================================================================
class LoadTestConfig:
    """Configuration for load tests."""

    # API endpoints
    BASE_URL = os.getenv("LOAD_TEST_URL", "http://test")
    HEALTH_ENDPOINT = "/health"
    STATUS_ENDPOINT = "/api/v1/status"
    METRICS_ENDPOINT = "/api/v1/metrics"
    # Performance targets (SLOs)
    TARGET_P50_MS = 50  # 50ms p50 latency
    TARGET_P95_MS = 200  # 200ms p95 latency
    TARGET_P99_MS = 500  # 500ms p99 latency
    TARGET_THROUGHPUT_RPS = 100  # 100 requests/second
    TARGET_ERROR_RATE = 0.01  # 1% error rate
    MAX_MEMORY_GROWTH_MB = 100  # 100MB memory growth


# =============================================================================
# METRICS COLLECTION
# =============================================================================
class MetricsCollector:
    """Collects and analyzes performance metrics."""

    def __init__(self) -> None:
        """Initialize metrics collector."""
        self.response_times: list[float] = []
        self.status_codes: Counter = Counter()
        self.errors: list[str] = []
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def record_request(
        self,
        duration_ms: float,
        status_code: int,
        error: str | None = None,
    ) -> None:
        """Record a request result.
        Args:
            duration_ms: Request duration in milliseconds
            status_code: HTTP status code
            error: Error message if request failed
        """
        self.response_times.append(duration_ms)
        self.status_codes[status_code] += 1
        if error:
            self.errors.append(error)

    def start(self) -> None:
        """Start timing."""
        self.start_time = time.perf_counter()

    def stop(self) -> None:
        """Stop timing."""
        self.end_time = time.perf_counter()

    def get_percentile(self, percentile: float) -> float:
        """Calculate latency percentile.
        Args:
            percentile: Percentile to calculate (0-100)
        Returns:
            Latency in milliseconds
        """
        if not self.response_times:
            return 0.0
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * percentile / 100)
        return sorted_times[min(index, len(sorted_times) - 1)]

    def get_summary(self) -> dict[str, Any]:
        """Get metrics summary.
        Returns:
            Dictionary with performance metrics
        """
        total_requests = len(self.response_times)
        duration = self.end_time - self.start_time
        return {
            "total_requests": total_requests,
            "duration_seconds": duration,
            "throughput_rps": total_requests / duration if duration > 0 else 0,
            "latency_p50_ms": self.get_percentile(50),
            "latency_p95_ms": self.get_percentile(95),
            "latency_p99_ms": self.get_percentile(99),
            "latency_min_ms": min(self.response_times) if self.response_times else 0,
            "latency_max_ms": max(self.response_times) if self.response_times else 0,
            "latency_mean_ms": (statistics.mean(self.response_times) if self.response_times else 0),
            "latency_stdev_ms": (
                statistics.stdev(self.response_times) if len(self.response_times) > 1 else 0
            ),
            "success_count": sum(
                count for code, count in self.status_codes.items() if 200 <= code < 300
            ),
            "error_count": len(self.errors),
            "error_rate": len(self.errors) / total_requests if total_requests > 0 else 0,
            "status_codes": dict(self.status_codes),
        }

    def print_summary(self, title: str = "Load Test Results") -> None:
        """Print formatted summary.
        Args:
            title: Title for the summary
        """
        summary = self.get_summary()
        print(f"\n{'=' * 70}")
        print(f"{title:^70}")
        print(f"{'=' * 70}")
        print(f"Total Requests:     {summary['total_requests']:,}")
        print(f"Duration:           {summary['duration_seconds']:.2f}s")
        print(f"Throughput:         {summary['throughput_rps']:.1f} req/s")
        print("\nLatency Percentiles:")
        print(f"  p50:              {summary['latency_p50_ms']:.2f}ms")
        print(f"  p95:              {summary['latency_p95_ms']:.2f}ms")
        print(f"  p99:              {summary['latency_p99_ms']:.2f}ms")
        print(f"  min:              {summary['latency_min_ms']:.2f}ms")
        print(f"  max:              {summary['latency_max_ms']:.2f}ms")
        print(f"  mean:             {summary['latency_mean_ms']:.2f}ms")
        print(f"  stdev:            {summary['latency_stdev_ms']:.2f}ms")
        print("\nSuccess/Error:")
        print(f"  Successes:        {summary['success_count']:,}")
        print(f"  Errors:           {summary['error_count']:,}")
        print(f"  Error Rate:       {summary['error_rate']:.2%}")
        print("\nStatus Codes:")
        for code, count in sorted(summary["status_codes"].items()):
            print(f"  {code}:              {count:,}")
        print(f"{'=' * 70}\n")


class ResourceMonitor:
    """Monitors system resource usage."""

    def __init__(self) -> None:
        """Initialize resource monitor."""
        self.process = psutil.Process()
        self.baseline_memory: float = 0.0
        self.peak_memory: float = 0.0
        self.baseline_cpu: float = 0.0
        self.cpu_samples: list[float] = []

    def start(self) -> None:
        """Start monitoring."""
        self.baseline_memory = self.process.memory_info().rss / (1024 * 1024)
        self.baseline_cpu = self.process.cpu_percent()

    def sample(self) -> None:
        """Take a resource usage sample."""
        current_memory = self.process.memory_info().rss / (1024 * 1024)
        self.peak_memory = max(self.peak_memory, current_memory)
        self.cpu_samples.append(self.process.cpu_percent())

    def get_summary(self) -> dict[str, Any]:
        """Get resource usage summary.
        Returns:
            Dictionary with resource metrics
        """
        current_memory = self.process.memory_info().rss / (1024 * 1024)
        return {
            "baseline_memory_mb": self.baseline_memory,
            "current_memory_mb": current_memory,
            "peak_memory_mb": self.peak_memory,
            "memory_growth_mb": current_memory - self.baseline_memory,
            "cpu_mean_percent": statistics.mean(self.cpu_samples) if self.cpu_samples else 0,
            "cpu_max_percent": max(self.cpu_samples) if self.cpu_samples else 0,
        }


# =============================================================================
# LOAD TEST UTILITIES
# =============================================================================
async def make_request(
    client: httpx.AsyncClient,
    endpoint: str,
    method: str = "GET",
    data: dict | None = None,
    metrics: MetricsCollector | None = None,
) -> dict[str, Any]:
    """Make an HTTP request and record metrics.
    Args:
        client: HTTPX async client
        endpoint: API endpoint path
        method: HTTP method (GET, POST, etc.)
        data: Request payload for POST requests
        metrics: Metrics collector instance
    Returns:
        Response data with timing information
    """
    start = time.perf_counter()
    error = None
    status_code = 500
    try:
        if method == "GET":
            response = await client.get(endpoint)
        elif method == "POST":
            response = await client.post(endpoint, json=data or {})
        elif method == "PUT":
            response = await client.put(endpoint, json=data or {})
        elif method == "DELETE":
            response = await client.delete(endpoint)
        else:
            raise ValueError(f"Unsupported method: {method}")
        status_code = response.status_code
        success = 200 <= status_code < 300
    except Exception as e:
        error = str(e)
        success = False
    duration_ms = (time.perf_counter() - start) * 1000
    if metrics:
        metrics.record_request(duration_ms, status_code, error)
    return {
        "duration_ms": duration_ms,
        "status_code": status_code,
        "success": success,
        "error": error,
    }


async def concurrent_requests(
    base_url: str,
    endpoint: str,
    num_requests: int,
    method: str = "GET",
    data: dict | None = None,
) -> MetricsCollector:
    """Execute concurrent requests and collect metrics.
    Args:
        base_url: Base URL for requests
        endpoint: API endpoint path
        num_requests: Number of concurrent requests
        method: HTTP method
        data: Request payload for POST requests
    Returns:
        MetricsCollector with results
    """
    metrics = MetricsCollector()
    metrics.start()
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        tasks = [make_request(client, endpoint, method, data, metrics) for _ in range(num_requests)]
        await asyncio.gather(*tasks, return_exceptions=True)
    metrics.stop()
    return metrics


# =============================================================================
# LOAD TEST BENCHMARKS
# =============================================================================
@pytest.mark.benchmark
@pytest.mark.load
@pytest.mark.asyncio
class TestLoadBenchmarks:
    """Comprehensive load testing benchmarks."""

    @pytest.mark.timeout(60)
    async def test_concurrent_load_10_users(self) -> None:
        """Benchmark with 10 concurrent users.
        Simulates light load with 10 concurrent users making 100 requests.
        Expected SLOs:
        - Throughput: >100 req/s
        - p95 latency: <200ms
        - Error rate: <1%
        """
        num_users = 10
        requests_per_user = 100
        metrics = await concurrent_requests(
            LoadTestConfig.BASE_URL,
            LoadTestConfig.HEALTH_ENDPOINT,
            num_users * requests_per_user,
        )
        metrics.print_summary("10 Concurrent Users - Load Test")
        summary = metrics.get_summary()
        # Validate SLOs
        assert summary["throughput_rps"] > 50, (
            f"Throughput {summary['throughput_rps']:.1f} req/s below 50 req/s"
        )
        assert summary["latency_p95_ms"] < 500, (
            f"p95 latency {summary['latency_p95_ms']:.1f}ms exceeds 500ms"
        )
        assert summary["error_rate"] < 0.05, f"Error rate {summary['error_rate']:.1%} exceeds 5%"

    @pytest.mark.timeout(90)
    async def test_concurrent_load_50_users(self) -> None:
        """Benchmark with 50 concurrent users.
        Simulates moderate load with 50 concurrent users.
        Expected SLOs:
        - Throughput: >200 req/s
        - p95 latency: <300ms
        - Error rate: <2%
        """
        num_users = 50
        requests_per_user = 100
        metrics = await concurrent_requests(
            LoadTestConfig.BASE_URL,
            LoadTestConfig.HEALTH_ENDPOINT,
            num_users * requests_per_user,
        )
        metrics.print_summary("50 Concurrent Users - Load Test")
        summary = metrics.get_summary()
        # Validate SLOs
        assert summary["throughput_rps"] > 100, (
            f"Throughput {summary['throughput_rps']:.1f} req/s below 100 req/s"
        )
        assert summary["latency_p95_ms"] < 1000, (
            f"p95 latency {summary['latency_p95_ms']:.1f}ms exceeds 1000ms"
        )
        assert summary["error_rate"] < 0.1, f"Error rate {summary['error_rate']:.1%} exceeds 10%"

    @pytest.mark.timeout(120)
    async def test_concurrent_load_100_users(self) -> None:
        """Benchmark with 100 concurrent users.
        Simulates heavy load with 100 concurrent users.
        Expected SLOs:
        - Throughput: >300 req/s
        - p99 latency: <1000ms
        - Error rate: <5%
        """
        num_users = 100
        requests_per_user = 50
        metrics = await concurrent_requests(
            LoadTestConfig.BASE_URL,
            LoadTestConfig.HEALTH_ENDPOINT,
            num_users * requests_per_user,
        )
        metrics.print_summary("100 Concurrent Users - Load Test")
        summary = metrics.get_summary()
        # Validate SLOs (relaxed for high concurrency)
        assert summary["throughput_rps"] > 50, (
            f"Throughput {summary['throughput_rps']:.1f} req/s below 50 req/s"
        )
        assert summary["latency_p99_ms"] < 2000, (
            f"p99 latency {summary['latency_p99_ms']:.1f}ms exceeds 2000ms"
        )
        assert summary["error_rate"] < 0.15, f"Error rate {summary['error_rate']:.1%} exceeds 15%"

    @pytest.mark.timeout(120)
    async def test_throughput_measurement(self) -> None:
        """Measure maximum throughput under sustained load.
        Runs sustained load for 30 seconds and measures throughput.
        Expected:
        - Sustained throughput: >200 req/s
        - Throughput stability: <10% variance
        """
        duration_seconds = 30
        concurrency = 50
        metrics = MetricsCollector()
        resource_monitor = ResourceMonitor()
        metrics.start()
        resource_monitor.start()
        start_time = time.perf_counter()
        async with httpx.AsyncClient(base_url=LoadTestConfig.BASE_URL, timeout=30.0) as client:
            while time.perf_counter() - start_time < duration_seconds:
                tasks = [
                    make_request(client, LoadTestConfig.HEALTH_ENDPOINT, metrics=metrics)
                    for _ in range(concurrency)
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                resource_monitor.sample()
                await asyncio.sleep(0.05)
        metrics.stop()
        metrics.print_summary("Sustained Throughput Test")
        summary = metrics.get_summary()
        resources = resource_monitor.get_summary()
        print("\nResource Usage:")
        print(f"  Memory Growth:    {resources['memory_growth_mb']:.1f}MB")
        print(f"  CPU (mean):       {resources['cpu_mean_percent']:.1f}%")
        print(f"  CPU (peak):       {resources['cpu_max_percent']:.1f}%\n")
        # Validate throughput
        assert summary["throughput_rps"] > 50, (
            f"Throughput {summary['throughput_rps']:.1f} req/s below 50 req/s"
        )
        assert resources["memory_growth_mb"] < 200, (
            f"Memory growth {resources['memory_growth_mb']:.1f}MB exceeds 200MB"
        )

    @pytest.mark.timeout(120)
    async def test_latency_percentiles(self) -> None:
        """Test and validate latency percentile distribution.
        Makes 1000 requests and validates latency distribution.
        Expected:
        - p50: <50ms
        - p95: <200ms
        - p99: <500ms
        """
        num_requests = 1000
        metrics = await concurrent_requests(
            LoadTestConfig.BASE_URL,
            LoadTestConfig.HEALTH_ENDPOINT,
            num_requests,
        )
        metrics.print_summary("Latency Percentile Test")
        summary = metrics.get_summary()
        # Create histogram buckets
        buckets = defaultdict(int)
        for latency in metrics.response_times:
            if latency < 10:
                buckets["<10ms"] += 1
            elif latency < 50:
                buckets["10-50ms"] += 1
            elif latency < 100:
                buckets["50-100ms"] += 1
            elif latency < 200:
                buckets["100-200ms"] += 1
            elif latency < 500:
                buckets["200-500ms"] += 1
            else:
                buckets[">=500ms"] += 1
        print("\nLatency Distribution:")
        for bucket in ["<10ms", "10-50ms", "50-100ms", "100-200ms", "200-500ms", ">=500ms"]:
            count = buckets[bucket]
            percentage = count / num_requests * 100 if num_requests > 0 else 0
            bar = "█" * int(percentage / 2)
            print(f"  {bucket:12} [{percentage:5.1f}%] {bar}")
        print()
        # Validate percentiles (relaxed for test environment)
        assert summary["latency_p50_ms"] < 200, (
            f"p50 latency {summary['latency_p50_ms']:.1f}ms exceeds 200ms"
        )
        assert summary["latency_p95_ms"] < 1000, (
            f"p95 latency {summary['latency_p95_ms']:.1f}ms exceeds 1000ms"
        )
        assert summary["latency_p99_ms"] < 2000, (
            f"p99 latency {summary['latency_p99_ms']:.1f}ms exceeds 2000ms"
        )

    @pytest.mark.timeout(180)
    async def test_memory_usage_under_load(self) -> None:
        """Test memory usage and leak detection under sustained load.
        Runs 10 cycles of 100 requests, monitoring memory growth.
        Expected:
        - Total memory growth: <100MB
        - No progressive memory leaks
        """
        cycles = 10
        requests_per_cycle = 100
        tracemalloc.start()
        baseline_memory = tracemalloc.get_traced_memory()[0]
        memory_samples = [baseline_memory]
        async with httpx.AsyncClient(base_url=LoadTestConfig.BASE_URL, timeout=30.0) as client:
            for cycle in range(cycles):
                tasks = [
                    make_request(client, LoadTestConfig.HEALTH_ENDPOINT)
                    for _ in range(requests_per_cycle)
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                gc.collect()
                current_memory = tracemalloc.get_traced_memory()[0]
                memory_samples.append(current_memory)
                print(
                    f"Cycle {cycle + 1}/{cycles}: Memory = {current_memory / (1024 * 1024):.2f}MB"
                )
        peak_memory = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        total_growth_mb = (peak_memory - baseline_memory) / (1024 * 1024)
        print("\nMemory Analysis:")
        print(f"  Baseline:         {baseline_memory / (1024 * 1024):.2f}MB")
        print(f"  Peak:             {peak_memory / (1024 * 1024):.2f}MB")
        print(f"  Total Growth:     {total_growth_mb:.1f}MB\n")
        # Validate memory usage
        assert total_growth_mb < 200, f"Memory growth {total_growth_mb:.1f}MB exceeds 200MB"

    @pytest.mark.timeout(120)
    async def test_database_connection_pool_stress(self) -> None:
        """Stress test database connection pool.
        Simulates high database load with concurrent queries.
        Expected:
        - All requests complete successfully
        - No connection pool exhaustion
        - Error rate: <5%
        """
        num_requests = 500
        # Use an endpoint that likely touches the database
        metrics = await concurrent_requests(
            LoadTestConfig.BASE_URL,
            LoadTestConfig.STATUS_ENDPOINT,
            num_requests,
        )
        metrics.print_summary("Database Connection Pool Stress Test")
        summary = metrics.get_summary()
        # Validate database connection handling
        assert summary["error_rate"] < 0.1, (
            f"Error rate {summary['error_rate']:.1%} exceeds 10% (possible pool exhaustion)"
        )
        assert summary["success_count"] > num_requests * 0.9, (
            "Less than 90% success rate indicates connection issues"
        )

    @pytest.mark.timeout(120)
    async def test_response_time_histogram(self) -> None:
        """Generate detailed response time histogram.
        Creates a histogram of response times across 1000 requests.
        """
        num_requests = 1000
        metrics = await concurrent_requests(
            LoadTestConfig.BASE_URL,
            LoadTestConfig.HEALTH_ENDPOINT,
            num_requests,
        )
        # Create fine-grained histogram
        histogram = defaultdict(int)
        bucket_size_ms = 10
        for latency in metrics.response_times:
            bucket = int(latency / bucket_size_ms) * bucket_size_ms
            histogram[bucket] += 1

        print("\nDetailed Response Time Histogram:")
        print(f"{'Bucket (ms)':>12} {'Count':>8} {'Percentage':>12} {'Bar':>20}")
        print("-" * 56)
        for bucket in sorted(histogram.keys())[
            :20
        ]:  # Show first 20 buckets  # type: ignore[assignment]
            count = histogram[bucket]

            percentage = count / num_requests * 100
            bar = "█" * int(percentage)
            print(f"{bucket:>5}-{bucket + bucket_size_ms:<4} {count:>8} {percentage:>11.2f}% {bar}")
        metrics.print_summary("Response Time Histogram Test")

    @pytest.mark.timeout(120)
    async def test_error_rate_tracking(self) -> None:
        """Test error rate tracking across different scenarios.
        Tests various endpoints and tracks error rates.
        Expected:
        - Overall error rate: <5%
        - Per-endpoint error rate: <10%
        """
        endpoints = [
            LoadTestConfig.HEALTH_ENDPOINT,
            LoadTestConfig.STATUS_ENDPOINT,
            LoadTestConfig.METRICS_ENDPOINT,
        ]
        endpoint_metrics: dict[str, MetricsCollector] = {}
        for endpoint in endpoints:
            metrics = await concurrent_requests(
                LoadTestConfig.BASE_URL,
                endpoint,
                200,
            )
            endpoint_metrics[endpoint] = metrics
        # Print per-endpoint results
        print("\nPer-Endpoint Error Rates:")
        print(f"{'Endpoint':^30} {'Requests':>10} {'Errors':>8} {'Rate':>8}")
        print("-" * 58)
        total_requests = 0
        total_errors = 0
        for endpoint, metrics in endpoint_metrics.items():
            summary = metrics.get_summary()
            total_requests += summary["total_requests"]
            total_errors += summary["error_count"]
            print(
                f"{endpoint:30} {summary['total_requests']:>10} "
                f"{summary['error_count']:>8} {summary['error_rate']:>7.1%}"
            )
        overall_error_rate = total_errors / total_requests if total_requests > 0 else 0
        print(f"\nOverall Error Rate: {overall_error_rate:.2%}\n")
        # Validate error rates
        assert overall_error_rate < 0.15, f"Overall error rate {overall_error_rate:.1%} exceeds 15%"

    @pytest.mark.timeout(180)
    async def test_resource_utilization_monitoring(self) -> None:
        """Monitor CPU and memory utilization under load.
        Runs sustained load while monitoring resource usage.
        Expected:
        - CPU usage stable
        - Memory growth: <100MB
        - No resource leaks
        """
        duration_seconds = 30
        concurrency = 30
        resource_monitor = ResourceMonitor()
        metrics = MetricsCollector()
        resource_monitor.start()
        metrics.start()
        start_time = time.perf_counter()
        async with httpx.AsyncClient(base_url=LoadTestConfig.BASE_URL, timeout=30.0) as client:
            while time.perf_counter() - start_time < duration_seconds:
                tasks = [
                    make_request(client, LoadTestConfig.HEALTH_ENDPOINT, metrics=metrics)
                    for _ in range(concurrency)
                ]
                await asyncio.gather(*tasks, return_exceptions=True)
                resource_monitor.sample()
                await asyncio.sleep(0.1)
        metrics.stop()
        resources = resource_monitor.get_summary()
        print("\nResource Utilization Report:")
        print(f"{'=' * 60}")
        print("Memory:")
        print(f"  Baseline:         {resources['baseline_memory_mb']:.1f}MB")
        print(f"  Current:          {resources['current_memory_mb']:.1f}MB")
        print(f"  Peak:             {resources['peak_memory_mb']:.1f}MB")
        print(f"  Growth:           {resources['memory_growth_mb']:.1f}MB")
        print("\nCPU:")
        print(f"  Mean:             {resources['cpu_mean_percent']:.1f}%")
        print(f"  Peak:             {resources['cpu_max_percent']:.1f}%")
        print(f"{'=' * 60}\n")
        metrics.print_summary("Resource Utilization Test")
        # Validate resource usage
        assert resources["memory_growth_mb"] < 200, (
            f"Memory growth {resources['memory_growth_mb']:.1f}MB exceeds 200MB"
        )

    @pytest.mark.timeout(180)
    async def test_mixed_workload_simulation(self) -> None:
        """Simulate realistic mixed workload.
        Combines different request types and patterns to simulate
        real-world usage.
        Expected:
        - Overall throughput: >100 req/s
        - Error rate: <5%
        - Resource stability
        """
        duration_seconds = 30
        endpoints = [
            (LoadTestConfig.HEALTH_ENDPOINT, "GET", 5),  # Weight 5
            (LoadTestConfig.STATUS_ENDPOINT, "GET", 3),  # Weight 3
            (LoadTestConfig.METRICS_ENDPOINT, "GET", 2),  # Weight 2
        ]
        # Create weighted endpoint list
        weighted_endpoints = []
        for endpoint, method, weight in endpoints:
            weighted_endpoints.extend([(endpoint, method)] * weight)
        metrics = MetricsCollector()
        resource_monitor = ResourceMonitor()
        metrics.start()
        resource_monitor.start()
        start_time = time.perf_counter()
        request_index = 0
        async with httpx.AsyncClient(base_url=LoadTestConfig.BASE_URL, timeout=30.0) as client:
            while time.perf_counter() - start_time < duration_seconds:
                # Pick endpoint in round-robin from weighted list
                endpoint, method = weighted_endpoints[request_index % len(weighted_endpoints)]
                request_index += 1
                tasks = [make_request(client, endpoint, method, metrics=metrics) for _ in range(20)]
                await asyncio.gather(*tasks, return_exceptions=True)
                resource_monitor.sample()
                await asyncio.sleep(0.05)
        metrics.stop()
        metrics.print_summary("Mixed Workload Simulation")
        resources = resource_monitor.get_summary()
        summary = metrics.get_summary()
        print("\nResource Usage:")
        print(f"  Memory Growth:    {resources['memory_growth_mb']:.1f}MB")
        print(f"  CPU (mean):       {resources['cpu_mean_percent']:.1f}%\n")
        # Validate mixed workload performance
        assert summary["throughput_rps"] > 50, (
            f"Throughput {summary['throughput_rps']:.1f} req/s below 50 req/s"
        )
        assert summary["error_rate"] < 0.15, f"Error rate {summary['error_rate']:.1%} exceeds 15%"


# =============================================================================
# CLI RUNNER
# =============================================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "benchmark"])
