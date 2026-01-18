from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
from datetime import timedelta
from kagami_api.security.token_manager import TokenManager


def test_get_token_info_fields(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "secret")
    tm = TokenManager()
    tok = tm.create_access_token({"sub": "u1"}, expires_delta=timedelta(minutes=1))
    info = tm.get_token_info(tok)
    assert info and "subject" in info and info["subject"] == "u1"
    assert "expires_at" in info
    assert "issued_at" in info
    assert info.get("token_type") == "access"
