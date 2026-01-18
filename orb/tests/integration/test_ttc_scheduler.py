from __future__ import annotations


from typing import Any


def test_budget_monotonicity() -> None:
    from kagami.core.reasoning.compute_budget import budget_for

    b_low = budget_for("balanced", risk=0.1, complexity=0.1)
    b_high = budget_for("balanced", risk=0.9, complexity=0.9)

    assert b_high.sc_samples >= b_low.sc_samples
    assert b_high.think_tokens >= b_low.think_tokens
    assert b_high.rollout_K >= b_low.rollout_K
    assert b_high.rollout_H >= b_low.rollout_H


def test_ttc_mode_env_default_and_override(monkeypatch: Any) -> None:
    from kagami.core.reasoning.compute_budget import get_default_mode

    monkeypatch.delenv("KAGAMI_TTC_MODE", raising=False)
    assert get_default_mode() == "balanced"

    monkeypatch.setenv("KAGAMI_TTC_MODE", "thorough")
    assert get_default_mode() == "thorough"
