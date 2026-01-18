from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


from kagami.core.utils.safe_operations import (
    safe_add,
    safe_concat,
    safe_divide,
    safe_duration,
    safe_format_string,
    safe_increment,
    safe_max,
    safe_min,
    safe_multiply,
    safe_percentage,
    safe_subtract,
)


def test_safe_arithmetic() -> None:
    assert safe_divide(4, 2) == 2.0
    assert safe_divide(4, 0) == 0.0
    assert safe_multiply(3, 2) == 6.0
    assert safe_add(1, 2) == 3.0
    assert safe_subtract(5, 3) == 2.0
    assert safe_percentage(50, 200) == 25.0


def test_safe_string_ops() -> None:
    assert safe_concat("a", 1, None, separator="-") == "a-1"
    assert safe_format_string("Hello {name}", name=123) == "Hello 123"


def test_safe_increment_and_extrema_and_duration() -> None:
    assert safe_increment(1, 2) == 3
    assert safe_increment(1.5, 0.5) == 2.0
    assert safe_min(3, "x", 1.2) == 1.2
    assert safe_max(3, "x", 1.2) == 3.0
    assert safe_duration(5, 3) == 0.0
    assert safe_duration(3, 5) == 2.0
