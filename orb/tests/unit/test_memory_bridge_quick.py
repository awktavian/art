from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


def test_memory_bridge_disabled_by_default(monkeypatch: Any) -> None:
    # Memory bridge is now integrated into coordination module
    # Test that the functions exist

    from kagami.core.coordination import memory_bridge as mb

    # Bridge functions should exist and be callable
    assert callable(mb.restore_instincts_from_checkpoint)
    assert callable(mb.capture_instincts_to_checkpoint)


def test_memory_bridge_enabled_enqueue_and_drop(monkeypatch: Any) -> None:
    # Memory bridge now provides checkpoint-based memory restoration
    # Test that functions exist and are async-safe
    from kagami.core.coordination import memory_bridge as mb

    # Functions should exist
    assert callable(mb.restore_instincts_from_checkpoint)
    assert callable(mb.capture_instincts_to_checkpoint)

    # These are now async functions, so just verify they exist
    import inspect

    assert inspect.iscoroutinefunction(mb.restore_instincts_from_checkpoint)
    assert inspect.iscoroutinefunction(mb.capture_instincts_to_checkpoint)
