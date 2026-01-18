"""Test environment detection utilities.

Provides centralized test environment detection for K os.

NOTE: Prefer kagami.core.boot_mode.is_test_mode() for new code.
This module provides backward compatibility and additional test detection utilities.

USAGE GUIDELINES:
-----------------

PREFERRED: Use KAGAMI_BOOT_MODE=test (set by conftest.py)
✅ Check: from kagami.core.boot_mode import is_test_mode

VALID use cases (infrastructure-level decisions):
✅ Database connection configuration (SQLite vs Postgres)
✅ File locking mode selection (blocking vs non-blocking)
✅ Redis fallback behavior (fail-closed vs in-memory)
✅ Log level adjustments (reduce test noise)
✅ Metrics collection (disable expensive metrics in tests)

INVALID use cases (business logic shortcuts):
❌ Skipping business logic entirely
❌ Suppressing validation errors
❌ Bypassing security checks
❌ Returning mock data instead of real implementation
❌ Disabling receipts/observability requirements

PREFERRED ALTERNATIVE:
Use dependency injection and pytest fixtures instead of environment detection
whenever possible. Tests should exercise the same code paths as production,
just with different configuration.

Example (GOOD):
    @pytest.fixture
    def security_config():
        return SecurityConfig(environment="test", redis_available=True)

    def test_with_config(security_config):
        middleware = SecurityMiddleware(security_config)
        # Tests actual production code with test config

Example (BAD):
    def process_data(data):
        if is_test_environment():
            return {"mock": "data"}  # Skips actual logic!
        # ... actual processing ...
"""

import os

from kagami.core.boot_mode import is_test_mode as _boot_is_test_mode


def is_test_environment() -> bool:
    """Detect if running in a test environment.

    Checks KAGAMI_BOOT_MODE first (preferred), then falls back to other signals.

    Returns:
        True if running under test conditions, False otherwise.

    Note:
        Use sparingly. Prefer dependency injection over environment detection.
        See module docstring for usage guidelines.
    """
    # PRIMARY: Check KAGAMI_BOOT_MODE (set by conftest.py)
    if _boot_is_test_mode():
        return True

    # FALLBACK: rely on explicit CI / pytest env markers
    return bool(
        os.getenv("CI") == "true"
        or os.getenv("PYTEST_CURRENT_TEST")
        or os.getenv("PYTEST_XDIST_WORKER")
    )


def is_ci_environment() -> bool:
    """Detect if running in CI/CD pipeline.

    Returns:
        True if running in CI (GitHub Actions, CircleCI, etc.)
    """
    return bool(
        os.getenv("CI") == "true"
        or os.getenv("GITHUB_ACTIONS") == "true"
        or os.getenv("CIRCLECI") == "true"
    )


def get_test_worker_id() -> str | None:
    """Get pytest-xdist worker ID if running in parallel.

    Useful for creating isolated resources per test worker
    (e.g., separate memory directories, database instances).

    Returns:
        Worker ID (e.g., "gw0", "gw1") or None if not using xdist

    Example:
        worker_id = get_test_worker_id()
        if worker_id:
            db_path = f"/tmp/test_db_{worker_id}.sqlite"
        else:
            db_path = f"/tmp/test_db_{os.getpid()}.sqlite"
    """
    return os.getenv("PYTEST_XDIST_WORKER")


__all__ = [
    "get_test_worker_id",
    "is_ci_environment",
    "is_test_environment",
]
