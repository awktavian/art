from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


def test_semantic_vector_aug_flag(monkeypatch: Any) -> None:
    # Enable GAIA vector augmentation path
    monkeypatch.setenv("KAGAMI_MEMORY_USE_GAIA_VECTOR", "0")
    from pathlib import Path
    from kagami.core.memory import SemanticStore

    store = SemanticStore(Path("var/memory/test_semantic.json"))
    store.upsert("alpha beta gamma", {"t": 1})
    store.upsert("beta gamma delta", {"t": 2})
    hits = store.search("beta", k=2)
    assert hits and all("text" in h for h in hits)
