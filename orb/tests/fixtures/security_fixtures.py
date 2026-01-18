"""Security Test Fixtures.

Provides test utilities for bypassing security in tests.
Extracted from production security.py module for cleaner separation.
"""

from __future__ import annotations

import os
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from fastapi import Request


@pytest.fixture
def test_api_key() -> str:
    """Provide standard test API key.

    Returns:
        Test API key string
    """
    return "test_api_key"


@pytest.fixture
def test_api_key_alternate() -> str:
    """Provide alternate test API key.

    Returns:
        Alternate test API key
    """
    return "test-api-key-for-testing-only"


@pytest.fixture
def bypass_security(monkeypatch: MonkeyPatch, test_api_key: str) -> None:
    """Monkeypatch security to accept test API key.

    Args:
        monkeypatch: Pytest monkeypatch fixture
        test_api_key: Test API key
    """
    from kagami_api.security import Principal

    def mock_verify_api_key(api_key: str | None) -> bool:
        """Mock API key verification."""
        return api_key in {test_api_key, "test-api-key-for-testing-only", "dev-api-key"}

    def mock_require_auth(request: Request, credentials: Any = None) -> Principal:
        """Mock authentication."""
        return Principal(sub="test_user", roles=["api_user", "admin"])

    monkeypatch.setattr(
        "kagami_api.security.SecurityFramework.validate_api_key", mock_verify_api_key
    )
    monkeypatch.setattr("kagami_api.security.require_auth", mock_require_auth)


@pytest.fixture
def test_principal() -> Any:
    """Create test principal for authenticated requests.

    Returns:
        Principal with test user
    """
    from kagami_api.security import Principal

    return Principal(sub="test_user", roles=["api_user", "admin"])


def is_test_environment() -> bool:
    """Check if running in test environment.

    Returns:
        True if in test environment
    """
    return bool(os.getenv("PYTEST_CURRENT_TEST") or os.getenv("KAGAMI_TEST_MODE"))


def should_bypass_auth(path: str) -> bool:
    """Check if path is eligible for test auth bypass.

    Only allows bypass in test mode AND non-production.

    Args:
        path: Request path

    Returns:
        True if bypass allowed
    """
    if not is_test_environment():
        return False

    # Never bypass in production
    env = (os.getenv("ENVIRONMENT") or "development").lower()
    if env == "production":
        return False

    # Allowed paths for bypass
    prefixes = (
        "/api/command",
        "/api/plans",
        "/api/rooms",
        "/api/worldgraph",
        "/api/tools",
        "/api/forge",
        "/api/world",
    )

    return any(path.startswith(pref) for pref in prefixes)


__all__ = [
    "bypass_security",
    "is_test_environment",
    "should_bypass_auth",
    "test_api_key",
    "test_api_key_alternate",
    "test_principal",
]
