
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration


"""Perception SOTA wiring smoke tests.

These tests ensure the SOTA vision stack is reachable via the canonical
`kagami.core.multimodal.perception` namespace without triggering heavy model loads.
"""


def test_perception_exports_sota_vision_symbols():
    import kagami.core.multimodal.perception as perception

    assert perception.UnifiedVisionModule is not None
    assert perception.DINOv2Encoder is not None
    assert perception.get_optimal_device is not None
