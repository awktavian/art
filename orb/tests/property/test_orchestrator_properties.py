"""Property-based tests for orchestrator using Hypothesis.

Tests invariants that should hold for ALL possible inputs.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


from hypothesis import given, settings
from hypothesis import strategies as st

from kagami.core.orchestrator.core import IntentOrchestrator
from kagami.core.orchestrator.utils import (
    _infer_app_from_action,
    _IntentEnvelope,
    _normalize_app_name,
)

# Strategies for generating test data
app_names = st.one_of(
    st.none(),
    st.text(min_size=1, max_size=50),
    st.sampled_from(
        ["Penny Finance", "Spark Analytics", "Luna Marketing", "plans", "files", "forge"]
    ),
)

actions = st.one_of(
    st.none(),
    st.text(min_size=1, max_size=100),
    st.sampled_from(
        ["plan.create", "upload", "search", "get_context", "generate.code", "unknown.action"]
    ),
)

metadata_dicts = st.dictionaries(
    keys=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N"))),
    values=st.one_of(
        st.text(max_size=50), st.integers(), st.booleans(), st.floats(allow_nan=False)
    ),
)


@given(app_names)
@settings(max_examples=100)
def test_normalize_app_name_idempotent(app_name: Any) -> None:
    """Property: normalizing twice yields same result as normalizing once."""
    result1 = _normalize_app_name(app_name)

    # Only test idempotency when first result is truthy (not None, not empty)
    if result1:
        result2 = _normalize_app_name(result1)
        assert result1 == result2, "Normalization should be idempotent for non-empty results"


@given(app_names)
@settings(max_examples=100)
def test_normalize_app_name_lowercase(app_name: Any) -> None:
    """Property: normalized names are always lowercase or None."""
    result = _normalize_app_name(app_name)

    if result is not None:
        assert result == result.lower(), "Normalized names should be lowercase"


@given(app_names)
@settings(max_examples=100)
def test_normalize_app_name_no_whitespace(app_name: Any) -> None:
    """Property: normalized names have no leading/trailing whitespace."""
    result = _normalize_app_name(app_name)

    if result is not None:
        assert result == result.strip(), "Normalized names should have no whitespace"


@given(actions)
@settings(max_examples=100, deadline=500)  # Allow 500ms for registry imports
def test_infer_app_from_action_deterministic(action: Any) -> None:
    """Property: same action always infers same app."""
    result1 = _infer_app_from_action(action)
    result2 = _infer_app_from_action(action)

    assert result1 == result2, "App inference should be deterministic"


@given(actions)
@settings(max_examples=100)
def test_infer_app_from_action_returns_valid_or_none(action: Any) -> None:
    """Property: inferred app is either a valid string or None."""
    result = _infer_app_from_action(action)

    assert result is None or isinstance(result, str), "Should return str or None"
    if result is not None:
        assert len(result) > 0, "Non-None result should be non-empty"


@given(st.text(max_size=50), st.text(max_size=50), metadata_dicts)
@settings(max_examples=50)
def test_intent_envelope_preserves_data(action: Any, app: Any, metadata: Any) -> None:
    """Property: IntentEnvelope preserves input data."""
    envelope = _IntentEnvelope(action=action, app=app, metadata=metadata, target=None)

    assert envelope.action == action
    assert envelope.app == app
    assert envelope.metadata == metadata
    assert envelope.target is None


@given(st.text(max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "P"))))
@settings(max_examples=50)
def test_normalize_never_raises(text: Any) -> None:
    """Property: normalize_app_name never raises exceptions."""
    try:
        result = _normalize_app_name(text)
        # Should always return None or str
        assert result is None or isinstance(result, str)
    except Exception as e:
        pytest.fail(f"normalize_app_name raised {type(e).__name__}: {e}")


@given(st.text(min_size=1, max_size=20), st.text(min_size=1, max_size=20))
@settings(max_examples=50)
def test_normalize_canonical_apps_consistent(prefix: Any, suffix: Any) -> None:
    """Property: canonical app names always normalize consistently."""
    # Test that well-known apps always map to same result
    canonical = {
        "penny": "penny",
        "spark": "spark",
        "luna": "luna",
        "echo": "echo",
        "harmony": "harmony",
        "plans": "plans",
        "files": "files",
        "forge": "forge",
    }

    for original, expected in canonical.items():
        # Test exact match
        assert _normalize_app_name(original) == expected

        # Test case insensitivity
        assert _normalize_app_name(original.upper()) == expected
        assert _normalize_app_name(original.title()) == expected


@given(st.text(min_size=1, max_size=100))
@settings(max_examples=50)
def test_infer_app_never_returns_empty_string(action: Any) -> None:
    """Property: infer_app_from_action never returns empty string."""
    result = _infer_app_from_action(action)

    assert result != "", "Should never return empty string (None or valid app)"


@given(
    st.sampled_from(["plan", "plans", "plan.create", "create_plan", "generate_tasks"]),
)
@settings(deadline=500)
def test_infer_app_plans_actions(action: Any) -> None:
    """Property: plan-related actions infer to 'planner' app (registry) or 'plans' (fallback)."""
    result = _infer_app_from_action(action)

    # Registry returns 'planner', orchestrator fallback returns 'plans'
    assert result in ["plans", "planner"], f"Action '{action}' should infer to plans/planner"


@given(
    st.sampled_from(["upload", "search", "get_context", "find_related", "scan"]),
)
@settings(deadline=500)
def test_infer_app_files_actions(action: Any) -> None:
    """Property: file-related actions infer to 'research' app (registry) or 'files' (fallback)."""
    result = _infer_app_from_action(action)

    # Registry returns 'research', orchestrator fallback returns 'files'
    assert result in ["files", "research"], f"Action '{action}' should infer to files/research"
