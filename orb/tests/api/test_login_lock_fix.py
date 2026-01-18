"""Unit tests for login distributed lock race condition fix.

This test validates that the login endpoint properly handles distributed lock
acquisition failures in production mode.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from kagami_api.routes.user.auth import login
from kagami.core.schemas.schemas.validation import LoginRequest


@pytest.fixture(autouse=True)
def disable_cbf_checks():
    """Disable CBF checks for these tests."""
    with patch("kagami.core.safety.cbf_decorators.enforce_tier1", lambda x: lambda f: f):
        yield


@pytest.fixture
def mock_env_production(monkeypatch: Any) -> None:
    """Set environment to production mode."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("KAGAMI_FULL_OPERATION", "1")


@pytest.fixture
def mock_env_development(monkeypatch: Any) -> None:
    """Set environment to development mode."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("KAGAMI_FULL_OPERATION", "0")


@pytest.fixture
def mock_login_tracker():
    """Mock login tracker with Redis client."""
    tracker = MagicMock()
    tracker.redis_client = AsyncMock()
    tracker._use_redis = True
    tracker.max_attempts = 5
    tracker.lockout_minutes = 15
    return tracker


@pytest.mark.asyncio
@pytest.mark.slow
async def test_lock_acquisition_timeout_production(
    mock_env_production: Any, mock_login_tracker: Any
) -> None:
    """Test that lock acquisition timeout fails hard in production."""

    # Configure mock to timeout
    async def timeout_set(*args: Any, **kwargs) -> Any:
        await asyncio.sleep(10)  # Will timeout

    mock_login_tracker.redis_client.set = timeout_set
    request = LoginRequest(username="testuser", password="testpass", grant_type="password")
    with patch("kagami_api.routes.user.auth.SecurityFramework"):
        with patch("kagami_api.routes.user.auth.get_user_store"):
            with patch(
                "kagami_api.routes.user.auth.get_login_tracker",
                return_value=mock_login_tracker,
            ):
                # Should raise 503 in production on timeout
                with pytest.raises(HTTPException) as exc_info:
                    await login(request)  # type: ignore[arg-type]
                assert exc_info.value.status_code == 503
                assert "temporarily unavailable" in exc_info.value.detail.lower()
                assert exc_info.value.headers.get("Retry-After") == "10"  # type: ignore[union-attr]


@pytest.mark.asyncio
@pytest.mark.slow
async def test_lock_acquisition_timeout_development(
    mock_env_development: Any, mock_login_tracker: Any
) -> None:
    """Test that lock acquisition timeout allows degraded operation in development."""

    # Configure mock to timeout
    async def timeout_set(*args: Any, **kwargs) -> Any:
        await asyncio.sleep(10)  # Will timeout

    mock_login_tracker.redis_client.set = timeout_set
    mock_login_tracker.is_locked = AsyncMock(return_value=(False, None))
    mock_user_store = MagicMock()
    mock_user_store.get_user.return_value = None
    request = LoginRequest(username="testuser", password="testpass", grant_type="password")
    with patch("kagami_api.routes.user.auth.SecurityFramework"):
        with patch("kagami_api.routes.user.auth.get_user_store", return_value=mock_user_store):
            with patch(
                "kagami_api.routes.user.auth.get_login_tracker",
                return_value=mock_login_tracker,
            ):
                # Should continue in development mode (eventually failing on invalid user)
                with pytest.raises(HTTPException) as exc_info:
                    await login(request)  # type: ignore[arg-type]
                # Should fail on invalid credentials, not lock timeout
                assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_redis_unavailable_production(
    mock_env_production: Any, mock_login_tracker: Any
) -> None:
    """Test that missing Redis fails hard in production."""
    # Simulate Redis unavailable
    mock_login_tracker.redis_client = None
    mock_login_tracker._use_redis = False
    request = LoginRequest(username="testuser", password="testpass", grant_type="password")
    with patch("kagami_api.routes.user.auth.SecurityFramework"):
        with patch("kagami_api.routes.user.auth.get_user_store"):
            with patch(
                "kagami_api.routes.user.auth.get_login_tracker",
                return_value=mock_login_tracker,
            ):
                # Should raise 503 in production when Redis unavailable
                with pytest.raises(HTTPException) as exc_info:
                    await login(request)  # type: ignore[arg-type]
                assert exc_info.value.status_code == 503
                assert "temporarily unavailable" in exc_info.value.detail.lower()
                assert exc_info.value.headers.get("Retry-After") == "30"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_redis_unavailable_development(
    mock_env_development: Any, mock_login_tracker: Any
) -> None:
    """Test that missing Redis allows degraded operation in development."""
    # Simulate Redis unavailable
    mock_login_tracker.redis_client = None
    mock_login_tracker._use_redis = False
    mock_login_tracker.is_locked = AsyncMock(return_value=(False, None))
    mock_user_store = MagicMock()
    mock_user_store.get_user.return_value = None
    request = LoginRequest(username="testuser", password="testpass", grant_type="password")
    with patch("kagami_api.routes.user.auth.SecurityFramework"):
        with patch("kagami_api.routes.user.auth.get_user_store", return_value=mock_user_store):
            with patch(
                "kagami_api.routes.user.auth.get_login_tracker",
                return_value=mock_login_tracker,
            ):
                # Should continue in development mode (eventually failing on invalid user)
                with pytest.raises(HTTPException) as exc_info:
                    await login(request)  # type: ignore[arg-type]
                # Should fail on invalid credentials, not Redis unavailability
                assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_lock_contention(mock_env_production: Any, mock_login_tracker: Any) -> None:
    """Test that lock contention returns 429."""
    # Simulate lock already held by another request
    mock_login_tracker.redis_client.set = AsyncMock(return_value=False)
    request = LoginRequest(username="testuser", password="testpass", grant_type="password")
    with patch("kagami_api.routes.user.auth.SecurityFramework"):
        with patch("kagami_api.routes.user.auth.get_user_store"):
            with patch(
                "kagami_api.routes.user.auth.get_login_tracker",
                return_value=mock_login_tracker,
            ):
                # Should raise 429 when lock already held
                with pytest.raises(HTTPException) as exc_info:
                    await login(request)  # type: ignore[arg-type]
                assert exc_info.value.status_code == 429
                assert "in progress" in exc_info.value.detail.lower()
                assert "Retry-After" in exc_info.value.headers  # type: ignore[operator]


@pytest.mark.asyncio
@pytest.mark.slow
async def test_lock_release_timeout(mock_env_production: Any, mock_login_tracker: Any) -> None:
    """Test that lock release timeout is handled gracefully."""
    # Simulate successful lock acquisition
    mock_login_tracker.redis_client.set = AsyncMock(return_value=True)
    mock_login_tracker.is_locked = AsyncMock(return_value=(False, None))

    # Simulate lock release timeout
    async def timeout_delete(*args: Any, **kwargs) -> None:
        await asyncio.sleep(10)  # Will timeout

    mock_login_tracker.redis_client.delete = timeout_delete
    mock_user_store = MagicMock()
    mock_user_store.get_user.return_value = None
    request = LoginRequest(username="testuser", password="testpass", grant_type="password")
    with patch("kagami_api.routes.user.auth.SecurityFramework"):
        with patch("kagami_api.routes.user.auth.get_user_store", return_value=mock_user_store):
            with patch(
                "kagami_api.routes.user.auth.get_login_tracker",
                return_value=mock_login_tracker,
            ):
                # Should handle lock release timeout gracefully
                with pytest.raises(HTTPException) as exc_info:
                    await login(request)  # type: ignore[arg-type]
                # Should fail on invalid credentials, lock release error logged
                assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_heartbeat_cancellation(mock_env_production: Any, mock_login_tracker: Any) -> None:
    """Test that heartbeat task is properly cancelled."""
    # Simulate successful lock acquisition
    mock_login_tracker.redis_client.set = AsyncMock(return_value=True)
    mock_login_tracker.redis_client.delete = AsyncMock(return_value=True)
    mock_login_tracker.redis_client.expire = AsyncMock(return_value=True)
    mock_login_tracker.is_locked = AsyncMock(return_value=(False, None))
    mock_user_store = MagicMock()
    mock_user_store.get_user.return_value = None
    request = LoginRequest(username="testuser", password="testpass", grant_type="password")
    with patch("kagami_api.routes.user.auth.SecurityFramework"):
        with patch("kagami_api.routes.user.auth.get_user_store", return_value=mock_user_store):
            with patch(
                "kagami_api.routes.user.auth.get_login_tracker",
                return_value=mock_login_tracker,
            ):
                # Should handle heartbeat cancellation gracefully
                with pytest.raises(HTTPException) as exc_info:
                    await login(request)  # type: ignore[arg-type]
                # Should fail on invalid credentials
                assert exc_info.value.status_code == 401
                # Lock should be released
                mock_login_tracker.redis_client.delete.assert_called()


@pytest.mark.asyncio
async def test_successful_login_with_lock(
    mock_env_production: Any, mock_login_tracker: Any
) -> None:
    """Test successful login with proper lock acquisition and release."""
    # Simulate successful lock acquisition
    mock_login_tracker.redis_client.set = AsyncMock(return_value=True)
    mock_login_tracker.redis_client.delete = AsyncMock(return_value=True)
    mock_login_tracker.is_locked = AsyncMock(return_value=(False, None))
    mock_login_tracker.clear_attempts = AsyncMock()
    mock_user_store = MagicMock()
    mock_user_store.get_user.return_value = {
        "username": "testuser",
        "roles": ["user"],
        "id": "test-id",
    }
    mock_user_store.authenticate_user.return_value = True
    mock_security = MagicMock()
    mock_security.create_access_token.return_value = "access_token"
    mock_security.create_refresh_token.return_value = "refresh_token"
    request = LoginRequest(username="testuser", password="testpass", grant_type="password")
    with patch("kagami_api.routes.user.auth.SecurityFramework", return_value=mock_security):
        with patch("kagami_api.routes.user.auth.get_user_store", return_value=mock_user_store):
            with patch(
                "kagami_api.routes.user.auth.get_login_tracker",
                return_value=mock_login_tracker,
            ):
                with patch("kagami_api.routes.user.auth.audit_login_success"):
                    # Should succeed and release lock
                    response = await login(request)  # type: ignore[arg-type]
                    assert response.access_token == "access_token"
                    assert response.refresh_token == "refresh_token"
                    # Lock should be acquired and released
                    mock_login_tracker.redis_client.set.assert_called_once()
                    mock_login_tracker.redis_client.delete.assert_called_once()
                    mock_login_tracker.clear_attempts.assert_called_once()
