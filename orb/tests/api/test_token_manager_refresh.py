from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
from datetime import timedelta
from kagami_api.security.token_manager import TokenManager


def test_refresh_token_and_optional_rotate(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "secret")
    tm = TokenManager()
    refresh = tm.create_refresh_token({"sub": "u1"}, expires_delta=timedelta(minutes=5))
    # No rotate
    out = tm.refresh_access_token(refresh)
    assert out and out.get("access_token")
    # Rotate
    monkeypatch.setenv("ROTATE_REFRESH_TOKENS", "true")
    out2 = tm.refresh_access_token(refresh)
    assert out2 and out2.get("access_token")
    assert out2.get("refresh_token")
