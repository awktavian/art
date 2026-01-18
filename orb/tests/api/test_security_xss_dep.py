from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


def test_bleach_required_in_production(monkeypatch: Any) -> None:
    # Ensure production config passes core validation
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("KAGAMI_API_KEY", "x" * 40)
    import sys

    saved = sys.modules.pop("bleach", None)
    try:
        # Force subsequent imports of bleach to fail
        sys.modules["bleach"] = None  # type: ignore[assignment]
        from kagami_api import security_middleware as sm

        with pytest.raises(RuntimeError):
            sm.SecurityMiddleware(app=None, enable_csrf=True, enable_xss_protection=True)
    finally:
        if saved is not None:
            sys.modules["bleach"] = saved
        else:
            sys.modules.pop("bleach", None)
