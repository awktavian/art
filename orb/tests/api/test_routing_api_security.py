"""Integration tests for routing API security fix.

CREATED: December 15, 2025
PURPOSE: Verify API key forgery vulnerability is fixed at API level

Test Coverage:
1. Forged API keys are rejected (CRITICAL)
2. Valid API keys are accepted
3. Expired keys are rejected
4. Revoked keys are rejected
5. Tier-based authorization works correctly
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
from datetime import datetime, timedelta
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from kagami_api.routing_api import router as routing_router
from kagami_api.security import get_api_key_manager
from kagami.core.database.models import APIKey as DBAPIKey
from kagami.core.database.models import User as DBUser


@pytest.fixture
def app():
    """Create FastAPI test app."""
    app = FastAPI()
    app.include_router(routing_router)
    return app


@pytest.fixture
def client(app: Any) -> Any:
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session(tmp_path: Any) -> Any:
    """Create test database session."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from kagami.core.database.base import Base

    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_user(db_session: Any) -> Any:
    """Create test user."""
    user = DBUser(
        username="testuser",
        email="test@example.com",
        tenant_id="test-tenant",
        hashed_password="fake_hash",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def valid_pro_key(db_session: Any, test_user: Any) -> Any:
    """Create valid pro API key."""
    api_key_manager = get_api_key_manager()
    plaintext_key, _key_id = api_key_manager.create_api_key(
        db_session, str(test_user.id), tier="pro", name="Test Pro Key"
    )
    return plaintext_key


@pytest.fixture
def valid_free_key(db_session: Any, test_user: Any) -> Any:
    """Create valid free API key."""
    api_key_manager = get_api_key_manager()
    plaintext_key, _key_id = api_key_manager.create_api_key(
        db_session, str(test_user.id), tier="free", name="Test Free Key"
    )
    return plaintext_key


# =============================================================================
# TESTS: FORGED KEY REJECTION (CRITICAL)
# =============================================================================
def test_forged_pro_key_rejected(client: Any, db_session: Any) -> Any:
    """CRITICAL: Forged pro keys must be rejected."""
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        # Try various forged keys
        forged_keys = [
            "sk_pro_",
            "sk_pro_forged",
            "sk_pro_" + "a" * 64,
            "sk_pro_" + "f" * 64,
        ]
        for forged_key in forged_keys:
            response = client.post(
                "/v1/route",
                headers={"X-API-Key": forged_key},
                json={
                    "task": "test task",
                    "context": {},
                },
            )
            assert response.status_code == 401, f"Forged key accepted: {forged_key}"
            assert "Invalid or expired API key" in response.text


def test_forged_free_key_rejected(client: Any, db_session: Any) -> None:
    """CRITICAL: Forged free keys must be rejected."""
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        forged_keys = [
            "sk_free_",
            "sk_free_fake",
            "sk_free_" + "b" * 64,
        ]
        for forged_key in forged_keys:
            response = client.post(
                "/v1/route",
                headers={"X-API-Key": forged_key},
                json={
                    "task": "test task",
                    "context": {},
                },
            )
            assert response.status_code == 401, f"Forged key accepted: {forged_key}"


# =============================================================================
# TESTS: VALID KEY ACCEPTANCE
# =============================================================================
def test_valid_pro_key_accepted(client: Any, db_session: Any, valid_pro_key: Any) -> None:
    """Test that valid pro keys are accepted."""
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        response = client.post(
            "/v1/route",
            headers={"X-API-Key": valid_pro_key},
            json={
                "task": "test task",
                "context": {},
                "complexity": 0.5,
            },
        )
        # Should succeed (200) or fail for other reasons, but NOT 401
        assert response.status_code != 401


def test_valid_free_key_accepted(client: Any, db_session: Any, valid_free_key: Any) -> None:
    """Test that valid free keys are accepted for simple tasks."""
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        response = client.post(
            "/v1/route",
            headers={"X-API-Key": valid_free_key},
            json={
                "task": "simple task",
                "context": {},
                "complexity": 0.2,  # Below 0.3 threshold
            },
        )
        # Should succeed (200) or fail for other reasons, but NOT 401
        assert response.status_code != 401


# =============================================================================
# TESTS: EXPIRED KEY REJECTION
# =============================================================================
def test_expired_key_rejected(client: Any, db_session: Any, test_user: Any) -> None:
    """SECURITY: Expired keys must be rejected."""
    api_key_manager = get_api_key_manager()
    plaintext_key, key_id = api_key_manager.create_api_key(
        db_session, str(test_user.id), tier="pro", expires_in_days=0
    )
    # Set expiration to past
    db_key = db_session.get(DBAPIKey, key_id)
    db_key.expires_at = datetime.utcnow() - timedelta(days=1)
    db_session.commit()
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        response = client.post(
            "/v1/route",
            headers={"X-API-Key": plaintext_key},
            json={
                "task": "test task",
                "context": {},
            },
        )
        assert response.status_code == 401
        assert "Invalid or expired API key" in response.text


# =============================================================================
# TESTS: REVOKED KEY REJECTION
# =============================================================================
def test_revoked_key_rejected(client: Any, db_session: Any, test_user: Any) -> None:
    """SECURITY: Revoked keys must be rejected."""
    api_key_manager = get_api_key_manager()
    plaintext_key, key_id = api_key_manager.create_api_key(
        db_session, str(test_user.id), tier="pro"
    )
    # Revoke the key
    api_key_manager.revoke_api_key(db_session, key_id, str(test_user.id))
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        response = client.post(
            "/v1/route",
            headers={"X-API-Key": plaintext_key},
            json={
                "task": "test task",
                "context": {},
            },
        )
        assert response.status_code == 401
        assert "Invalid or expired API key" in response.text


# =============================================================================
# TESTS: TIER-BASED AUTHORIZATION
# =============================================================================
def test_free_tier_blocked_from_complex_tasks(
    client: Any, db_session: Any, valid_free_key: Any
) -> None:
    """Test that free tier is blocked from complex tasks."""
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        response = client.post(
            "/v1/route",
            headers={"X-API-Key": valid_free_key},
            json={
                "task": "complex task requiring multiple agents",
                "context": {},
                "complexity": 0.8,  # Above 0.3 threshold
            },
        )
        assert response.status_code == 403
        assert "Pro tier" in response.text


def test_pro_tier_allowed_complex_tasks(client: Any, db_session: Any, valid_pro_key: Any) -> None:
    """Test that pro tier can access complex tasks."""
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        response = client.post(
            "/v1/route",
            headers={"X-API-Key": valid_pro_key},
            json={
                "task": "complex task requiring multiple agents",
                "context": {},
                "complexity": 0.8,
            },
        )
        # Should succeed (200) or fail for other reasons, but NOT 403
        assert response.status_code != 403


# =============================================================================
# TESTS: MISSING/INVALID HEADERS
# =============================================================================
def test_missing_api_key_header(client: Any) -> None:
    """Test request with missing API key."""
    response = client.post(
        "/v1/route",
        json={
            "task": "test task",
            "context": {},
        },
    )
    assert response.status_code == 401
    assert "API key required" in response.text


def test_empty_api_key_header(client: Any) -> None:
    """Test request with empty API key."""
    response = client.post(
        "/v1/route",
        headers={"X-API-Key": ""},
        json={
            "task": "test task",
            "context": {},
        },
    )
    assert response.status_code == 401


# =============================================================================
# TESTS: VULNERABILITY REGRESSION
# =============================================================================
def test_old_vulnerability_is_fixed(client: Any, db_session: Any) -> None:
    """CRITICAL: Verify the original vulnerability is completely fixed.
    Old vulnerable code:
        if api_key.startswith("sk_pro_"):
            return {"tier": "pro", "key": api_key}  # Accepts ANY string!
    This test verifies that prefix-only validation is completely removed.
    """
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        # All these should be rejected (database lookup required)
        test_cases = [
            ("sk_pro_", "Empty suffix"),
            ("sk_pro_attack", "Short suffix"),
            ("sk_pro_" + "a" * 64, "Full length forged"),
            ("sk_pro_" + "f" * 64, "Another forged"),
            ("sk_free_attack", "Free tier forged"),
            ("sk_ent_attack", "Enterprise tier forged"),
        ]
        for forged_key, description in test_cases:
            response = client.post(
                "/v1/route",
                headers={"X-API-Key": forged_key},
                json={
                    "task": "test task",
                    "context": {},
                },
            )
            assert response.status_code == 401, (
                f"SECURITY BUG: {description} accepted. "
                f"Key: {forged_key}. "
                f"Response: {response.status_code} {response.text}"
            )


# =============================================================================
# TESTS: WEBSOCKET SECURITY
# =============================================================================
def test_websocket_forged_key_rejected(client: Any, db_session: Any) -> None:
    """SECURITY: WebSocket endpoint must also validate API keys properly."""
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        # WebSocket with forged key should be rejected
        # Expect WebSocketDisconnect or similar connection error
        with pytest.raises(
            (RuntimeError, OSError, Exception)
        ):  # TestClient raises various errors for WS failures
            with client.websocket_connect("/v1/stream?api_key=sk_pro_forged"):
                pass


def test_websocket_valid_pro_key_accepted(client: Any, db_session: Any, valid_pro_key: Any) -> None:
    """Test that WebSocket accepts valid pro keys."""
    with patch("kagami_api.routing_api.get_db", return_value=iter([db_session])):
        # This might fail for other reasons, but shouldn't fail auth
        try:
            with client.websocket_connect(f"/v1/stream?api_key={valid_pro_key}") as ws:
                pass  # Connection should be accepted
        except Exception as e:
            # If it fails, it shouldn't be an auth error
            assert "Pro tier required" not in str(e)
            assert "Invalid API key" not in str(e)
