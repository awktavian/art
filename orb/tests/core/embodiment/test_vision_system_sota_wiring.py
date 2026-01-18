"""VisionSystem SOTA wiring tests.

These are lightweight and do NOT load any real SOTA weights. We inject a dummy
UnifiedVisionModule to verify the plumbing and fallback behavior.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration

from types import SimpleNamespace

import numpy as np


@pytest.mark.asyncio
async def test_vision_system_uses_sota_hooks_when_forced(monkeypatch: Any) -> None:
    from kagami.core.embodiment.vision_system import VisionSystem

    class DummyVision:
        def __init__(self) -> None:
            self.encode_calls = 0
            self.detect_calls = 0
            self.caption_calls = 0

        async def encode(self, _pil: Any) -> str:
            self.encode_calls += 1
            return "DUMMY_FEATURES"

        async def detect(self, _pil: Any) -> List[Any]:
            self.detect_calls += 1
            # Match UnifiedVisionModule DetectedObject shape (normalized bbox)
            return [SimpleNamespace(label="person", confidence=0.9, bbox=[0.0, 0.0, 1.0, 1.0])]

        async def caption(self, _pil: Any, detailed: bool = False) -> str:
            del detailed
            self.caption_calls += 1
            return "A person in the scene."

    vs = VisionSystem()
    dummy = DummyVision()

    # Force SOTA path without relying on environment (pytest sets PYTEST_CURRENT_TEST).
    monkeypatch.setattr(vs, "_should_use_sota", lambda: True)
    monkeypatch.setattr(vs, "_get_sota_vision", lambda: dummy)

    img = np.zeros((64, 64, 3), dtype=np.uint8)
    perception = await vs.perceive(img)

    assert perception.features == "DUMMY_FEATURES"
    assert perception.scene_description == "A person in the scene."
    assert len(perception.objects) == 1
    assert perception.objects[0].label == "person"

    assert dummy.encode_calls == 1
    assert dummy.detect_calls == 1
    assert dummy.caption_calls == 1
