
from __future__ import annotations


from kagami.core.reasoning.narrator import is_complex, narrate


def test_is_complex_heuristics() -> None:
    assert is_complex({"multi_step": True}) is True
    assert is_complex({"cross_files": True}) is True
    assert is_complex({"uncertainty": True}) is True
    assert is_complex({}) is False


def test_narrate_outputs_plan() -> None:
    plan = narrate("Implement feature X")
    assert plan.goal == "Implement feature X"
    assert plan.steps and plan.evidence and plan.done_criteria
