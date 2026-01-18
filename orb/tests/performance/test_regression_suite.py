"""Performance regression tests to ensure system performance doesn't degrade."""

import pytest
import time
import gc
from typing import Any

# Performance benchmarking
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

pytestmark = [
    pytest.mark.performance,
    pytest.mark.timeout(30),  # Performance tests should complete quickly
]


class TestPerformanceRegression:
    """Test suite for performance regression detection."""

    def test_config_import_performance(self):
        """Test that config import is fast."""
        start_time = time.time()

        try:
            from kagami.core.config import get_config

            import_time = time.time() - start_time

            # Config import should be very fast (< 100ms)
            assert import_time < 0.1, f"Config import took {import_time:.3f}s, expected < 0.1s"

        except ImportError:
            pytest.skip("Config module not available")

    def test_database_connection_performance(self):
        """Test that database connection setup is reasonably fast."""
        start_time = time.time()

        try:
            from kagami.core.database.connection import resolve_database_url

            url = resolve_database_url()
            connection_time = time.time() - start_time

            # URL resolution should be fast (< 50ms)
            assert connection_time < 0.05, f"DB URL resolution took {connection_time:.3f}s"
            assert url is not None

        except ImportError:
            pytest.skip("Database module not available")

    @pytest.mark.skipif(not PSUTIL_AVAILABLE, reason="psutil not available")
    def test_memory_usage_baseline(self):
        """Test that basic operations don't consume excessive memory."""
        gc.collect()  # Clean up before measurement
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        try:
            # Perform some basic operations
            from kagami.core.config import get_config, get_bool_config, get_int_config

            for i in range(100):
                get_config(f"test_key_{i}", "default")
                get_bool_config(f"bool_key_{i}", False)
                get_int_config(f"int_key_{i}", 0)

            gc.collect()
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            # Memory increase should be reasonable (< 10MB for basic operations)
            assert memory_increase < 10, f"Memory increased by {memory_increase:.2f}MB"

        except ImportError:
            pytest.skip("Required modules not available")

    def test_repeated_operations_performance(self):
        """Test that repeated operations maintain consistent performance."""
        try:
            from kagami.core.config import get_config

            # Measure performance of repeated operations
            times = []
            for _i in range(10):
                start = time.time()
                for j in range(100):
                    get_config(f"perf_test_{j}", "default")
                elapsed = time.time() - start
                times.append(elapsed)

            # Performance should be consistent (max time < 2x min time)
            min_time = min(times)
            max_time = max(times)
            ratio = max_time / min_time if min_time > 0 else float("inf")

            assert ratio < 2.0, f"Performance variance too high: {ratio:.2f}x"

        except ImportError:
            pytest.skip("Config module not available")


class TestScalabilityRegression:
    """Test that system scales appropriately."""

    @pytest.mark.parametrize("num_keys", [10, 50, 100])
    def test_config_scaling(self, num_keys):
        """Test that config performance scales linearly."""
        try:
            from kagami.core.config import get_config

            start_time = time.time()
            for i in range(num_keys):
                get_config(f"scale_test_{i}", f"default_{i}")
            elapsed = time.time() - start_time

            # Should scale linearly (allow some overhead)
            expected_max = num_keys * 0.001  # 1ms per operation
            assert elapsed < expected_max, (
                f"Scaling test failed: {elapsed:.3f}s for {num_keys} operations"
            )

        except ImportError:
            pytest.skip("Config module not available")


class TestAsyncPerformance:
    """Test async operation performance."""

    @pytest.mark.asyncio
    async def test_async_import_performance(self):
        """Test that async imports are fast."""
        start_time = time.time()

        try:
            from kagami.core.database.async_connection import get_async_engine

            import_time = time.time() - start_time

            # Async import should be fast
            assert import_time < 0.1, f"Async import took {import_time:.3f}s"

        except ImportError:
            pytest.skip("Async database not available")


class TestRegressionBenchmarks:
    """Benchmark tests to detect performance regressions."""

    def test_baseline_import_benchmark(self):
        """Establish baseline for import performance."""
        import_times = {}

        modules_to_test = [
            "kagami.core.config",
            "kagami.core.database.connection",
        ]

        for module in modules_to_test:
            start = time.time()
            try:
                __import__(module)
                elapsed = time.time() - start
                import_times[module] = elapsed
            except ImportError:
                import_times[module] = None

        # Log performance for regression tracking
        for module, elapsed in import_times.items():
            if elapsed is not None:
                print(f"BENCHMARK: {module} import: {elapsed:.3f}s")
                # Fail if any import takes more than 200ms
                assert elapsed < 0.2, f"{module} import too slow: {elapsed:.3f}s"

    def test_function_call_overhead(self):
        """Test function call overhead doesn't regress."""
        try:
            from kagami.core.config import get_config

            # Measure function call overhead
            num_calls = 1000
            start = time.time()
            for _i in range(num_calls):
                get_config("overhead_test", "default")
            elapsed = time.time() - start

            avg_time = elapsed / num_calls
            # Each call should be very fast (< 1ms)
            assert avg_time < 0.001, f"Function call overhead too high: {avg_time:.6f}s per call"

        except ImportError:
            pytest.skip("Config module not available")
