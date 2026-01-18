"""Unit tests for kagami.core.security.safe_eval."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import math

from kagami.core.security.safe_eval import safe_eval


def test_safe_eval_literal_expression() -> None:
    assert safe_eval("1 + 2", {}) == 3


def test_safe_eval_allowed_name() -> None:
    allowed = {"x": 4}
    assert safe_eval("x * 2", allowed) == 8


def test_safe_eval_allowed_function_call() -> None:
    allowed = {"double": lambda value: value * 2}
    assert safe_eval("double(21)", allowed) == 42


def test_safe_eval_supports_slicing() -> None:
    allowed = {"arr": [1, 2, 3, 4]}
    assert safe_eval("arr[1:3]", allowed) == [2, 3]


def test_safe_eval_blocks_unknown_name() -> None:
    with pytest.raises(ValueError):
        safe_eval("unknown + 1", {})


def test_safe_eval_blocks_attribute_access() -> None:
    with pytest.raises(ValueError):
        safe_eval("foo.__class__", {"foo": 1})


def test_safe_eval_handles_bool_and_compare() -> None:
    allowed = {"x": 10}
    assert safe_eval("x > 5 and x < 20", allowed) is True


def test_safe_eval_literal_fallback_dict() -> None:
    assert safe_eval("{'a': 1, 'b': 2}", {}) == {"a": 1, "b": 2}


def test_safe_eval_math_constant() -> None:
    result = safe_eval("pi * 2", {"pi": math.pi})
    assert pytest.approx(result, rel=1e-6) == math.pi * 2
