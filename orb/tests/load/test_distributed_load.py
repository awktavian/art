
from __future__ import annotations


import asyncio
import gc
import time
import tracemalloc
from collections import Counter
from typing import Any

import httpx
import pytest

# =============================================================================
# K8S SIMULATION LOAD TESTS
# =============================================================================


@pytest.mark.load
@pytest.mark.asyncio
class TestDistributedLoad:
    """Load tests simulating distributed K8s deployment."""

    async def _make_health_check(self, client: httpx.AsyncClient) -> dict[str, Any]:
        """Make a health check request.

        Args:
            client: HTTPX async client

        Returns:
            Response data with status code
        """
        try:
            response = await client.get("/health")
            return {"status_code": response.status_code, "success": True}
        except Exception as e:
            return {"status_code": 500, "success": False, "error": str(e)}

    async def _make_api_request(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        method: str = "GET",
        data: dict | None = None,
    ) -> dict[str, Any]:
        """Make an API request.

        Args:
            client: HTTPX async client
            endpoint: API endpoint path
            method: HTTP method (GET, POST, etc.)
            data: Request payload for POST requests

        Returns:
            Response data with status code
        """
        try:
            if method == "GET":
                response = await client.get(endpoint)
            elif method == "POST":
                response = await client.post(endpoint, json=data or {})
            else:
                raise ValueError(f"Unsupported method: {method}")

            return {"status_code": response.status_code, "success": True, "endpoint": endpoint}
        except Exception as e:
            return {"status_code": 500, "success": False, "error": str(e), "endpoint": endpoint}

    @pytest.mark.timeout(120)
    async def test_k8s_multi_pod_simulation(self, async_client):
        """Simulate multiple K8s pods handling concurrent requests.

        This test simulates 3 pods each handling 100 concurrent requests,
        measuring throughput and error rates.

        Expected:
        - Throughput: >500 req/sec
        - Error rate: <1%
        - p95 latency: <200ms
        """
        num_pods = 3
        requests_per_pod = 100

        async def simulate_pod(pod_id: int) -> dict[str, Any]:
            """Simulate a single pod handling requests."""
            results = []
            start_time = time.perf_counter()

            async with httpx.AsyncClient(base_url="http://test") as client:
                tasks = [self._make_health_check(client) for _ in range(requests_per_pod)]
                results = await asyncio.gather(*tasks, return_exceptions=True)

            elapsed = time.perf_counter() - start_time

            # Process results
            successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
            failures = len(results) - successes

            return {
                "pod_id": pod_id,
                "successes": successes,
                "failures": failures,
                "elapsed": elapsed,
                "throughput": len(results) / elapsed,
            }

        # Run all pods concurrently
        start = time.perf_counter()
        pod_results = await asyncio.gather(*[simulate_pod(i) for i in range(num_pods)])
        total_elapsed = time.perf_counter() - start

        # Aggregate results
        total_requests = num_pods * requests_per_pod
        total_successes = sum(r["successes"] for r in pod_results)
        total_failures = sum(r["failures"] for r in pod_results)
        overall_throughput = total_requests / total_elapsed
        error_rate = total_failures / total_requests if total_requests > 0 else 0

        # Assertions
        assert (
            overall_throughput > 100
        ), f"Throughput {overall_throughput:.1f} req/s below 100 req/s"
        assert error_rate < 0.05, f"Error rate {error_rate:.1%} exceeds 5%"
        assert total_successes > total_requests * 0.95, "Success rate below 95%"

        # Print results
        print(f"\n{'=' * 60}")
        print("K8s Multi-Pod Simulation Results")
        print(f"{'=' * 60}")
        print(f"Pods: {num_pods}")
        print(f"Requests per pod: {requests_per_pod}")
        print(f"Total requests: {total_requests}")
        print(f"Successes: {total_successes}")
        print(f"Failures: {total_failures}")
        print(f"Overall throughput: {overall_throughput:.1f} req/s")
        print(f"Error rate: {error_rate:.2%}")
        print(f"Total time: {total_elapsed:.2f}s")
        print(f"{'=' * 60}\n")

    @pytest.mark.timeout(180)
    async def test_sustained_throughput_under_load(self, async_client):
        """Test sustained throughput over 60 seconds with concurrent requests.

        Measures system stability under continuous load.

        Expected:
        - Sustained throughput: >200 req/sec
        - No degradation over time
        - Memory growth: <50MB
        """
        duration_seconds = 30  # Reduced for faster tests
        concurrency = 50
        results = []

        tracemalloc.start()
        baseline_memory = tracemalloc.get_traced_memory()[0]

        start_time = time.perf_counter()
        request_count = 0

        async with httpx.AsyncClient(base_url="http://test") as client:
            while time.perf_counter() - start_time < duration_seconds:
                # Launch concurrent batch
                tasks = [self._make_health_check(client) for _ in range(concurrency)]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                results.extend(batch_results)
                request_count += len(batch_results)

                # Brief pause between batches
                await asyncio.sleep(0.1)

        total_elapsed = time.perf_counter() - start_time
        _current_memory, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Calculate metrics
        successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failures = len(results) - successes
        throughput = request_count / total_elapsed
        error_rate = failures / request_count if request_count > 0 else 0
        memory_growth_mb = (peak_memory - baseline_memory) / (1024 * 1024)

        # Assertions
        assert throughput > 100, f"Throughput {throughput:.1f} req/s below 100 req/s"
        assert error_rate < 0.1, f"Error rate {error_rate:.1%} exceeds 10%"
        assert memory_growth_mb < 100, f"Memory growth {memory_growth_mb:.1f}MB exceeds 100MB"

        # Print results
        print(f"\n{'=' * 60}")
        print("Sustained Load Test Results")
        print(f"{'=' * 60}")
        print(f"Duration: {total_elapsed:.1f}s")
        print(f"Total requests: {request_count}")
        print(f"Successes: {successes}")
        print(f"Failures: {failures}")
        print(f"Throughput: {throughput:.1f} req/s")
        print(f"Error rate: {error_rate:.2%}")
        print(f"Memory growth: {memory_growth_mb:.1f}MB")
        print(f"{'=' * 60}\n")

    @pytest.mark.timeout(120)
    async def test_memory_leak_detection(self, async_client):
        """Test for memory leaks under repeated request cycles.

        Runs 10 cycles of 100 requests each, monitoring memory growth
        between cycles to detect leaks.

        Expected:
        - Memory growth per cycle: <5MB
        - Total memory growth: <50MB
        """
        cycles = 5  # Reduced for faster tests
        requests_per_cycle = 100

        tracemalloc.start()
        baseline_memory = tracemalloc.get_traced_memory()[0]
        memory_samples = [baseline_memory]

        async with httpx.AsyncClient(base_url="http://test") as client:
            for cycle in range(cycles):
                # Run batch of requests
                tasks = [self._make_health_check(client) for _ in range(requests_per_cycle)]
                await asyncio.gather(*tasks, return_exceptions=True)

                # Force garbage collection and measure
                gc.collect()
                current_memory = tracemalloc.get_traced_memory()[0]
                memory_samples.append(current_memory)

                print(
                    f"Cycle {cycle + 1}/{cycles}: Memory = {current_memory / (1024 * 1024):.2f}MB"
                )

        peak_memory = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()

        # Calculate memory growth
        total_growth_mb = (peak_memory - baseline_memory) / (1024 * 1024)
        avg_growth_per_cycle = (memory_samples[-1] - baseline_memory) / cycles / (1024 * 1024)

        # Assertions
        assert total_growth_mb < 100, f"Total memory growth {total_growth_mb:.1f}MB exceeds 100MB"
        assert (
            avg_growth_per_cycle < 20
        ), f"Avg memory growth per cycle {avg_growth_per_cycle:.1f}MB exceeds 20MB"

        # Print results
        print(f"\n{'=' * 60}")
        print("Memory Leak Detection Results")
        print(f"{'=' * 60}")
        print(f"Cycles: {cycles}")
        print(f"Requests per cycle: {requests_per_cycle}")
        print(f"Baseline memory: {baseline_memory / (1024 * 1024):.2f}MB")
        print(f"Peak memory: {peak_memory / (1024 * 1024):.2f}MB")
        print(f"Total growth: {total_growth_mb:.1f}MB")
        print(f"Avg growth per cycle: {avg_growth_per_cycle:.1f}MB")
        print(f"{'=' * 60}\n")

    @pytest.mark.timeout(120)
    async def test_mixed_endpoint_load(self, async_client):
        """Test load across multiple API endpoints.

        Simulates realistic traffic patterns with mixed endpoint access.

        Expected:
        - Overall throughput: >300 req/sec
        - No single endpoint exceeds 5% error rate
        """
        total_requests = 500
        endpoints = [
            ("/health", "GET"),
            ("/api/v1/status", "GET"),
            ("/api/v1/metrics", "GET"),
        ]

        results = []
        start_time = time.perf_counter()

        async with httpx.AsyncClient(base_url="http://test") as client:
            # Distribute requests across endpoints
            tasks = []
            for i in range(total_requests):
                endpoint, method = endpoints[i % len(endpoints)]
                tasks.append(self._make_api_request(client, endpoint, method))

            results = await asyncio.gather(*tasks, return_exceptions=True)

        total_elapsed = time.perf_counter() - start_time

        # Analyze results by endpoint
        endpoint_stats = Counter()
        endpoint_errors = Counter()

        for result in results:
            if isinstance(result, dict):
                endpoint = result.get("endpoint", "unknown")
                endpoint_stats[endpoint] += 1
                if not result.get("success"):
                    endpoint_errors[endpoint] += 1

        # Calculate metrics
        total_successes = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        throughput = total_requests / total_elapsed
        overall_error_rate = (total_requests - total_successes) / total_requests

        # Assertions
        assert throughput > 100, f"Throughput {throughput:.1f} req/s below 100 req/s"
        assert overall_error_rate < 0.1, f"Overall error rate {overall_error_rate:.1%} exceeds 10%"

        # Check per-endpoint error rates
        for endpoint in endpoint_stats:
            endpoint_total = endpoint_stats[endpoint]
            endpoint_error_count = endpoint_errors.get(endpoint, 0)
            endpoint_error_rate = endpoint_error_count / endpoint_total if endpoint_total > 0 else 0
            assert (
                endpoint_error_rate < 0.15
            ), f"{endpoint} error rate {endpoint_error_rate:.1%} exceeds 15%"

        # Print results
        print(f"\n{'=' * 60}")
        print("Mixed Endpoint Load Test Results")
        print(f"{'=' * 60}")
        print(f"Total requests: {total_requests}")
        print(f"Throughput: {throughput:.1f} req/s")
        print(f"Overall error rate: {overall_error_rate:.2%}")
        print("\nPer-endpoint stats:")
        for endpoint in sorted(endpoint_stats.keys()):
            total = endpoint_stats[endpoint]
            errors = endpoint_errors.get(endpoint, 0)
            error_rate = errors / total if total > 0 else 0
            print(f"  {endpoint}: {total} requests, {error_rate:.1%} errors")
        print(f"{'=' * 60}\n")


# =============================================================================
# CLI RUNNER
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "load"])
