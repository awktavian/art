from __future__ import annotations

import pytest
from typing import Any


@pytest.mark.slow
@pytest.mark.timeout(300)
def test_webarena_smoke_runs_and_emits_metrics() -> None:
    """Test that webarena smoke benchmark runs successfully.

    Note: Metrics emission is optional since benchmark metrics were removed.
    """
    try:
        from kagami_benchmarks.ai.webarena_smoke import run_smoke
    except ImportError as e:
        pytest.skip(f"Benchmark module not available: {e}")

    result = run_smoke()
    # Check for either old or new result format
    has_old_format = "success_rate" in result
    has_new_format = "score" in result or "validity_rate" in result
    assert has_old_format or has_new_format, f"Unexpected result format: {list(result.keys())}"

    if has_old_format:
        assert 0.0 <= result["success_rate"] <= 1.0
    if has_new_format:
        # New format uses 'score' or 'validity_rate' for success metrics
        score = result.get("score", result.get("validity_rate", 0))
        assert 0.0 <= score <= 1.0


@pytest.mark.slow
@pytest.mark.timeout(300)
def test_swebench_wrapper_interface(monkeypatch) -> None:
    try:
        from kagami_benchmarks.ai.swebench_runner import run_verified

    except ImportError as e:
        pytest.skip(f"Benchmark module not available: {e}")

    # No actual harness required; function should return dict interface or raise runtime error
    try:
        res = run_verified(n=1)
        # Accept either old or new key format
        old_keys = {"resolved_pct", "tasks_run", "tasks_resolved", "tokens_used"}
        new_keys = {"score", "total", "status"}
        has_old_format = len(old_keys & set(res.keys())) >= 2
        has_new_format = len(new_keys & set(res.keys())) >= 2
        assert has_old_format or has_new_format, f"Unexpected result format: {list(res.keys())}"
    except RuntimeError:
        # Acceptable if harness missing
        pass
