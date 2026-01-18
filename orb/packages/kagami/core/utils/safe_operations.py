from __future__ import annotations

from typing import Any


def _to_float(x: Any) -> float:
    """Convert value to float, returning 0.0 on failure.

    Args:
        x: Value to convert (int, float, str, etc.)

    Returns:
        Float representation of x, or 0.0 if conversion fails
    """
    try:
        return float(x)
    except Exception:
        return 0.0


def safe_divide(a: Any, b: Any) -> float:
    """Divide two values with division-by-zero protection.

    Converts inputs to float and returns 0.0 if denominator is zero.

    Args:
        a: Numerator (any type convertible to float)
        b: Denominator (any type convertible to float)

    Returns:
        a / b, or 0.0 if b is zero or unconvertible

    Examples:
        >>> safe_divide(10, 2)
        5.0
        >>> safe_divide(10, 0)
        0.0
        >>> safe_divide("10", "invalid")
        0.0
    """
    num = _to_float(a)
    den = _to_float(b)
    if den == 0.0:
        return 0.0
    return num / den


def safe_multiply(a: Any, b: Any) -> float:
    """Multiply two values with automatic type conversion.

    Args:
        a: First operand (any type convertible to float)
        b: Second operand (any type convertible to float)

    Returns:
        a * b as float, or 0.0 if either operand fails conversion
    """
    return _to_float(a) * _to_float(b)


def safe_add(a: Any, b: Any) -> float:
    """Add two values with automatic type conversion.

    Args:
        a: First operand (any type convertible to float)
        b: Second operand (any type convertible to float)

    Returns:
        a + b as float, or 0.0 if either operand fails conversion
    """
    return _to_float(a) + _to_float(b)


def safe_subtract(a: Any, b: Any) -> float:
    """Subtract two values with automatic type conversion.

    Args:
        a: Minuend (any type convertible to float)
        b: Subtrahend (any type convertible to float)

    Returns:
        a - b as float, or 0.0 if either operand fails conversion
    """
    return _to_float(a) - _to_float(b)


def safe_percentage(part: Any, whole: Any) -> float:
    """Calculate percentage with division-by-zero protection.

    Args:
        part: Part value (numerator)
        whole: Whole value (denominator)

    Returns:
        (part / whole) * 100, or 0.0 if whole is zero

    Examples:
        >>> safe_percentage(25, 100)
        25.0
        >>> safe_percentage(1, 3)
        33.333333333333336
        >>> safe_percentage(10, 0)
        0.0
    """
    return safe_divide(_to_float(part) * 100.0, _to_float(whole))


def safe_concat(*args: Any, separator: str = "") -> str:
    """Concatenate values to string, skipping None and empty values.

    Args:
        *args: Values to concatenate
        separator: String to insert between values (default: "")

    Returns:
        Concatenated string with non-empty values joined by separator

    Examples:
        >>> safe_concat("hello", "world", separator=" ")
        "hello world"
        >>> safe_concat("foo", None, "bar", separator="-")
        "foo-bar"
        >>> safe_concat(1, 2, 3)
        "123"
    """
    parts: list[str] = []
    for a in args:
        if a is None:
            continue
        parts.append(str(a))
    return separator.join([p for p in parts if p != ""])


def safe_format_string(template: str, **kwargs: Any) -> str:
    """Format string with kwargs, returning template unchanged on error.

    Converts all kwargs to strings before formatting. Never raises exceptions.

    Args:
        template: Format string with {placeholders}
        **kwargs: Values to substitute into template

    Returns:
        Formatted string, or original template if formatting fails

    Examples:
        >>> safe_format_string("Hello {name}!", name="World")
        "Hello World!"
        >>> safe_format_string("Value: {x}", x=42)
        "Value: 42"
        >>> safe_format_string("Bad {x}", y=10)
        "Bad {x}"
    """
    try:
        safe_kwargs = {k: str(v) for k, v in kwargs.items()}
        return template.format(**safe_kwargs)
    except Exception:
        return template


def safe_increment(value: Any, delta: Any) -> float | int:
    """Increment value by delta, preserving int type when possible.

    Args:
        value: Initial value
        delta: Amount to add

    Returns:
        value + delta as int if both inputs are int, otherwise as float

    Examples:
        >>> safe_increment(10, 5)
        15
        >>> safe_increment(10.0, 5)
        15.0
        >>> safe_increment("10", "5")
        15.0
    """
    if isinstance(value, int) and isinstance(delta, int):
        return value + delta
    return _to_float(value) + _to_float(delta)


def safe_min(*values: Any) -> float:
    """Find minimum value, ignoring unconvertible values.

    Filters out values that can't be converted to float.

    Args:
        *values: Values to compare

    Returns:
        Minimum of convertible values, or 0.0 if none convertible

    Examples:
        >>> safe_min(5, 2, 8, 1)
        1.0
        >>> safe_min("invalid", None, {})
        0.0
        >>> safe_min(10, "5", None)
        5.0
    """
    # Only consider values that can be converted to float; ignore others
    floats = []
    for v in values:
        try:
            floats.append(float(v))
        except Exception:
            continue
    return min(floats) if floats else 0.0


def safe_max(*values: Any) -> float:
    """Find maximum value, ignoring unconvertible values.

    Filters out values that can't be converted to float.

    Args:
        *values: Values to compare

    Returns:
        Maximum of convertible values, or 0.0 if none convertible

    Examples:
        >>> safe_max(5, 2, 8, 1)
        8.0
        >>> safe_max("invalid", None, {})
        0.0
        >>> safe_max(10, "15", None)
        15.0
    """
    # Only consider values that can be converted to float; ignore others
    floats = []
    for v in values:
        try:
            floats.append(float(v))
        except Exception:
            continue
    return max(floats) if floats else 0.0


def safe_duration(start: Any, end: Any) -> float:
    """Calculate duration between start and end times, clamped to non-negative.

    Args:
        start: Start time/timestamp (any type convertible to float)
        end: End time/timestamp (any type convertible to float)

    Returns:
        max(0.0, end - start) to ensure non-negative duration

    Examples:
        >>> safe_duration(10.0, 15.0)
        5.0
        >>> safe_duration(15.0, 10.0)
        0.0
        >>> safe_duration("invalid", "100")
        100.0
    """
    s = _to_float(start)
    e = _to_float(end)
    return max(0.0, e - s)


__all__ = [
    "safe_add",
    "safe_concat",
    "safe_divide",
    "safe_duration",
    "safe_format_string",
    "safe_increment",
    "safe_max",
    "safe_min",
    "safe_multiply",
    "safe_percentage",
    "safe_subtract",
]
