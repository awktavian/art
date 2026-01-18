from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami_observability.metrics import REGISTRY


def test_ws_control_latency_histogram_exists() -> None:
    names = set(getattr(REGISTRY, "_names_to_collectors", {}).keys())
    assert "kagami_ws_message_latency_seconds" in names
