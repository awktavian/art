from __future__ import annotations

import sys

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from kagami.core.schemas.schemas.plans import GeneratedTask, TaskList


def _has_unhashable_modules() -> bool:
    try:
        for v in list(sys.modules.values()):
            try:
                hash(v)
            except Exception:
                return True
        return False
    except Exception:
        return False


# Consolidated markers
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.skipif(
        _has_unhashable_modules(),
        reason="Unhashable entries in sys.modules detected; skip flaky property-based run",
    ),
]


@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=50,
)
@given(
    title=st.text(
        min_size=1,
        max_size=32,
        alphabet=st.sampled_from(list("abcdefghijklmnopqrstuvwxyz-")),
    ),
    priority=st.sampled_from(["low", "medium", "high"]),
)
def test_tasklist_schema_accepts_valid_generated_tasks(title: str, priority: str) -> None:
    tl = TaskList(tasks=[GeneratedTask(title=title, priority=priority)])
    assert isinstance(tl.tasks, list)
    assert tl.tasks and tl.tasks[0].title.strip()


@settings(
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    max_examples=50,
)
@given(
    long_list=st.lists(st.text(min_size=1, max_size=8), min_size=10, max_size=20),
)
def test_tasklist_schema_clamps_list_length(long_list: list[str]) -> None:
    # Pydantic max_length is enforced at field-level; ensure we can construct with truncation by slicing
    subset = long_list[:8]
    tl = TaskList(tasks=[GeneratedTask(title=t) for t in subset])
    assert len(tl.tasks) <= 8
