from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
from kagami_api.security import SecurityFramework


def test_validate_api_key_accepts_test_key(monkeypatch: Any) -> None:
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")
    assert SecurityFramework.validate_api_key("test_api_key") is True


def test_validate_api_key_rejects_wrong_key(monkeypatch: Any) -> None:
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    # Ensure configured key is not equal to the test value
    monkeypatch.setenv("KAGAMI_API_KEY", "kagami_abc123")
    assert SecurityFramework.validate_api_key("not_the_key") is False
