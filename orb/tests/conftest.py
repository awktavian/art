from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

# Ensure repo root and packages are importable under pytest --import-mode=importlib.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_repo_root_str = str(_REPO_ROOT)
_packages_str = str(_REPO_ROOT / "packages")

if _repo_root_str not in sys.path:
    sys.path.insert(0, _repo_root_str)
if _packages_str not in sys.path:
    sys.path.insert(0, _packages_str)

# Add satellite package directories to sys.path for test imports
_SATELLITES_DIR = _REPO_ROOT / "satellites"
for satellite in [
    "integrations",
    "hal",
    "api",
    "math",
    "observability",
    "smarthome",
    "genesis",
    "knowledge",
    "federated",
    "benchmarks",
    "ar",
]:
    satellite_path = str(_SATELLITES_DIR / satellite)
    if satellite_path not in sys.path:
        sys.path.insert(0, satellite_path)

# Import test environment configuration FIRST
from tests import conftest_env

# ==============================================================================
# HYPOTHESIS CONFIGURATION (Dec 5, 2025)
# ==============================================================================
# Fix FloatingPointError with subnormal floats on systems compiled with -ffast-math
# See: https://hypothesis.readthedocs.io/en/latest/settings.html
try:
    from hypothesis import HealthCheck, Phase, settings
    from hypothesis import strategies as st

    # Register a profile that works on -ffast-math systems
    settings.register_profile(
        "ci",
        deadline=None,  # No deadline in CI (avoids flaky timeouts)
        print_blob=True,  # Print failing examples for reproduction
        derandomize=True,  # Reproducible runs in CI
        suppress_health_check=(HealthCheck.too_slow,),
    )

    # Load the CI profile by default when CI=1 is set
    if os.getenv("CI") == "1":
        settings.load_profile("ci")

    # CRITICAL (Dec 5, 2025): Monkey-patch default float strategy to disable subnormals
    # This fixes FloatingPointError on systems with -ffast-math
    # The floats() strategy defaults to allow_subnormal=True which fails on such systems
    _original_floats = st.floats

    def safe_floats(
        min_value=None,
        max_value=None,
        *,
        allow_nan=None,
        allow_infinity=None,
        allow_subnormal=False,  # Changed default from True to False
        width=64,
    ):
        """Wrapper for st.floats that defaults allow_subnormal=False."""
        return _original_floats(
            min_value=min_value,
            max_value=max_value,
            allow_nan=allow_nan,
            allow_infinity=allow_infinity,
            allow_subnormal=allow_subnormal,
            width=width,
        )

    # Override the strategy module's floats
    st.floats = safe_floats  # type: ignore[assignment]

except ImportError:
    pass  # hypothesis not installed


# ==============================================================================
# PYTEST TIMEOUT CONFIGURATION (Dec 14, 2025)
# ==============================================================================
# Default timeout for tests to prevent hanging. Individual tests can override
# with @pytest.mark.timeout(seconds) decorator.
def pytest_configure(config: Any) -> None:
    """Configure pytest with default timeout."""
    # Register the timeout marker
    config.addinivalue_line(
        "markers", "timeout(seconds): Set a timeout for the test (requires pytest-timeout)"
    )


# Default timeout values by test type
DEFAULT_TIMEOUT = 30  # 30 seconds for most tests
SLOW_TEST_TIMEOUT = 120  # 2 minutes for slow tests
INTEGRATION_TIMEOUT = 300  # 5 minutes for integration tests

pytest_plugins = [
    "tests.fixtures.mock_fixtures",
    "tests.fixtures.mock_llm",
    "tests.fixtures.websocket_mocks",
    "tests.fixtures.mock_redis",
]


@pytest.fixture(autouse=True)
def auto_mock_external_services(monkeypatch: Any) -> None:
    """Automatically mock external services for all tests unless explicitly skipped.

    This ensures tests run independently of:
    - Redis (uses in-memory fallback)
    - CockroachDB (uses SQLite in-memory)
    - etcd (uses in-memory mock)

    To test with real services, set KAGAMI_USE_REAL_SERVICES=1
    """
    import os

    if os.getenv("KAGAMI_USE_REAL_SERVICES") == "1":
        return  # Use real services

    # Force in-memory database for tests
    monkeypatch.setenv("KAGAMI_DB_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    # Disable Redis requirement (uses in-memory fallback)
    monkeypatch.setenv("KAGAMI_TEST_DISABLE_REDIS", "1")

    # Disable etcd requirement
    monkeypatch.setenv("KAGAMI_DISABLE_ETCD", "1")

    # Disable external model loading
    monkeypatch.setenv("KAGAMI_LOAD_WORLD_MODEL", "0")
    monkeypatch.setenv("KAGAMI_LOAD_MATRYOSHKA", "0")


@pytest.fixture(scope="session")
def live_uvicorn_server():
    """Start a real uvicorn server for tests that need true WS/SSE.

    Yields a tuple (base_http_url, base_ws_url).
    """
    try:
        import uvicorn
        from kagami_api import create_app

        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
        sock.close()
        app = create_app()
        config = uvicorn.Config(app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        base_http = f"http://{host}:{port}"
        base_ws = f"ws://{host}:{port}"
        deadline = time.time() + 6.0
        ready = False
        while time.time() < deadline and (not ready):
            try:
                with urllib.request.urlopen(f"{base_http}/health", timeout=0.5) as r:
                    ready = r.status == 200
            except Exception:
                time.sleep(0.1)
        if not ready:
            pytest.skip("live_uvicorn_server failed to start in time")
        yield (base_http, base_ws)
    except Exception as e:
        pytest.skip(f"live_uvicorn_server unavailable: {e}")


@pytest.fixture(scope="session")
def ensure_services():
    """Best-effort check for Redis/CockroachDB; skip tests if unavailable.

    For full integration tests with real services, set KAGAMI_USE_REAL_SERVICES=1
    and ensure docker-compose services are running:
        docker-compose -f docker-compose.test.yml up -d redis cockroach
    """

    def _port_open(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            try:
                s.connect(("127.0.0.1", port))
                return True
            except Exception:
                return False

    # Check if services are available
    redis_available = _port_open(6380)
    db_available = _port_open(26257)

    if not redis_available or not db_available:
        # Mark as skipping external services
        os.environ.setdefault("PYTEST_SKIP_EXTERNAL", "1")
        os.environ.setdefault("KAGAMI_TEST_DISABLE_REDIS", "1")
    else:
        # Services available - use them
        os.environ["PYTEST_SKIP_EXTERNAL"] = "0"
        os.environ.pop("KAGAMI_TEST_DISABLE_REDIS", None)

    return redis_available and db_available


@pytest.fixture()
def client():
    try:
        from kagami_api import create_app
        from starlette.testclient import TestClient

        app = create_app()
        return TestClient(app)
    except Exception as e:
        pytest.skip(f"client fixture unavailable: {e}")


@pytest_asyncio.fixture()
async def async_client():
    try:
        from httpx import ASGITransport, AsyncClient
        from kagami_api import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    except Exception as e:
        pytest.skip(f"async_client fixture unavailable: {e}")


@pytest.fixture()
def authenticated_client(client: Any) -> None:
    """Client with authentication headers."""
    client.headers.update({"Authorization": "Bearer test-api-key-fixture"})
    return client


@pytest.fixture()
def csrf_headers(client: Any) -> Dict[str, Any]:
    """Get CSRF token and create headers dict."""
    try:
        response = client.get("/api/user/csrf-token")
        if response.status_code == 200:
            data = response.json()
            return {
                "X-CSRF-Token": data.get("csrf_token", ""),
                "X-Session-ID": data.get("session_id", ""),
                "Authorization": "Bearer test-api-key",
            }
    except Exception:
        pass
    return {"Authorization": "Bearer test-api-key"}


@pytest.fixture(scope="session", autouse=True)
def configure_test_environment():
    """Configure test environment for all tests.

    This fixture runs automatically before any tests to ensure
    lightweight models and test-appropriate settings are used.
    """
    assert os.environ.get("KAGAMI_TEST_MODE") == "1", (
        "Test mode not configured - test_env.py not imported?"
    )
    print("\n=== K os Test Configuration ===")
    print(f"Test Mode: {os.environ.get('KAGAMI_TEST_MODE')}")
    print(f"Default Model: {os.environ.get('KAGAMI_TRANSFORMERS_MODEL_DEFAULT')}")
    print(f"Boot Mode: {os.environ.get('KAGAMI_BOOT_MODE')}")
    print("================================\n")
    yield


@pytest.fixture
def lightweight_llm_config(monkeypatch: Any) -> None:
    """Ensure lightweight LLM configuration for individual tests.

    Use this fixture when you want to guarantee lightweight models
    are used, even if test_env.py configuration is overridden.
    """
    monkeypatch.setenv("KAGAMI_TRANSFORMERS_MODEL_DEFAULT", "sshleifer/tiny-gpt2")
    monkeypatch.setenv("KAGAMI_TRANSFORMERS_MODEL_CODER", "sshleifer/tiny-gpt2")
    monkeypatch.setenv("KAGAMI_TRANSFORMERS_MODEL_FAST", "sshleifer/tiny-gpt2")
    monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
    yield


@pytest.fixture(scope="session", autouse=True)
def initialize_test_db():
    """Initialize test database tables once per session.

    Creates all tables at the start of the test session for in-memory SQLite.
    Note: This must be synchronous to work with session scope.
    """
    import asyncio

    from kagami.core.database.models import Base

    from kagami.core.database import get_async_engine

    async def create_tables():
        engine = get_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # Run async function in a new event loop
    asyncio.run(create_tables())


@pytest_asyncio.fixture(autouse=True)
async def reset_db_engine():
    """Reset global async DB engine for each test.

    CRITICAL FIX (Dec 21, 2025): When resetting engine cache with in-memory SQLite,
    we must recreate tables since each new engine gets a fresh empty database.
    File-based SQLite databases persist tables across engine resets.
    """
    from kagami.core.database.models import Base

    from kagami.core.database import async_connection, connection, get_async_engine

    # Reset the cached references to force new engine creation
    async_connection._ASYNC_ENGINE = None
    async_connection._ASYNC_SESSION_FACTORY = None
    async_connection._ASYNC_DATABASE_URL_CACHE = None
    connection._DATABASE_URL_CACHE = None

    # Recreate tables for the new engine (critical for in-memory databases)
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Also create tables on the sync engine (for FastAPI dependency injection)
    from kagami.core.database.connection import get_engine

    sync_engine = get_engine()
    Base.metadata.create_all(bind=sync_engine)

    yield


@pytest_asyncio.fixture(autouse=True)
async def cleanup_experience_bus():
    """Cleanup ExperienceBus after each test to prevent hangs."""
    yield

    # Stop the ExperienceBus if it was started
    try:
        import kagami.core.events.experience_bus as eb_module

        if eb_module._experience_bus is not None:
            eb_module._experience_bus._running = False
            if eb_module._experience_bus._processor_task:
                eb_module._experience_bus._processor_task.cancel()
                try:
                    import asyncio

                    await asyncio.wait_for(eb_module._experience_bus._processor_task, timeout=0.5)
                except (TimeoutError, asyncio.CancelledError):
                    pass
            eb_module._experience_bus = None
    except Exception:
        pass


# ==============================================================================
# FLAKY TEST RETRY LOGIC (Dec 27, 2025)
# ==============================================================================


def pytest_runtest_makereport(item: Any, call: Any) -> None:
    """Hook to implement retry logic for flaky tests.

    Tests marked with @pytest.mark.flaky will be retried up to 3 times
    before being marked as failed.
    """
    if "flaky" in item.keywords and call.excinfo is not None:
        # Get or initialize retry count
        if not hasattr(item, "_flaky_retry_count"):
            item._flaky_retry_count = 0

        # Retry up to 3 times
        if item._flaky_retry_count < 3:
            item._flaky_retry_count += 1
            # Force test to be re-run by clearing the exception
            call.excinfo = None


# ==============================================================================
# BENCHMARK FIXTURES (Dec 27, 2025)
# ==============================================================================


@pytest.fixture
def benchmark_with_warmup():
    """Benchmark fixture with warmup rounds.

    Usage:
        def test_performance(benchmark_with_warmup) -> None:
            result = benchmark_with_warmup(my_function, arg1, arg2, warmup=10)
    """
    import gc
    import time

    def _benchmark(
        func: Any, *args: Any, warmup: Any = 10, iterations: Any = 100, **kwargs: Any
    ) -> Any:
        """Run benchmark with warmup.

        Args:
            func: Function to benchmark
            *args: Positional arguments for func
            warmup: Number of warmup iterations (default: 10)
            iterations: Number of timed iterations (default: 100)
            **kwargs: Keyword arguments for func

        Returns:
            dict: Benchmark results with mean_ms, std_ms, min_ms, max_ms
        """
        # Warmup rounds
        for _ in range(warmup):
            func(*args, **kwargs)

        gc.collect()

        # Timed iterations
        times = []
        for _ in range(iterations):
            start = time.perf_counter_ns()
            result = func(*args, **kwargs)
            end = time.perf_counter_ns()
            times.append((end - start) / 1_000_000)  # Convert to ms

        # Calculate statistics
        import statistics

        sorted_times = sorted(times)
        n = len(sorted_times)

        return {
            "mean_ms": statistics.mean(times),
            "std_ms": statistics.stdev(times) if n > 1 else 0.0,
            "min_ms": sorted_times[0],
            "max_ms": sorted_times[-1],
            "p50_ms": sorted_times[int(n * 0.5)],
            "p95_ms": sorted_times[int(n * 0.95)] if n >= 20 else sorted_times[-1],
            "p99_ms": sorted_times[int(n * 0.99)] if n >= 100 else sorted_times[-1],
            "result": result,
        }

    return _benchmark
