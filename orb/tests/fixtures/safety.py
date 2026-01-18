"""Safety-related test fixtures for Kagami test suite.

Provides standardized fixtures for testing safety mechanisms:
- CBF (Control Barrier Function) testing utilities
- Safety violation simulation
- Honesty validation testing
- Markov blanket testing

Usage:
    def test_cbf_enforcement(cbf_validator):
        with cbf_validator.expect_violation():
            # Code that should trigger CBF violation
            pass
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from kagami.core.exceptions import CBFViolation, HonestyViolation, MarkovBlanketViolation


class CBFTestValidator:
    """Helper for testing CBF enforcement."""

    def __init__(self) -> None:
        self.violations: list[CBFViolation] = []

    @contextmanager
    def expect_violation(
        self, barrier_name: str | None = None, h_value: float | None = None
    ) -> Generator[None, None, None]:
        """Context manager that expects a CBF violation.

        Args:
            barrier_name: Expected barrier name (optional)
            h_value: Expected barrier value (optional)
        """
        try:
            yield
            # If we get here, no exception was raised
            raise AssertionError("Expected CBF violation was not raised")
        except CBFViolation as e:
            self.violations.append(e)
            if barrier_name is not None and e.barrier_name != barrier_name:
                raise AssertionError(f"Expected barrier '{barrier_name}', got '{e.barrier_name}'")
            if h_value is not None and abs(e.h_value - h_value) > 1e-6:
                raise AssertionError(f"Expected h={h_value}, got h={e.h_value}")

    def assert_no_violations(self) -> None:
        """Assert that no CBF violations occurred."""
        if self.violations:
            raise AssertionError(f"Unexpected CBF violations: {self.violations}")

    def clear_violations(self) -> None:
        """Clear recorded violations."""
        self.violations.clear()


@pytest.fixture
def cbf_validator() -> CBFTestValidator:
    """Provide a CBF test validator."""
    return CBFTestValidator()


@pytest.fixture
def mock_cbf_enforcer() -> MagicMock:
    """Provide a mocked CBF enforcer for testing."""
    mock = MagicMock()
    mock.check_barrier = MagicMock(return_value=0.5)  # Safe by default
    mock.enforce_barrier = MagicMock()
    return mock


class HonestyTestValidator:
    """Helper for testing honesty enforcement."""

    def __init__(self) -> None:
        self.violations: list[HonestyViolation] = []

    @contextmanager
    def expect_honesty_violation(self, claim: str | None = None) -> Generator[None, None, None]:
        """Context manager that expects a honesty violation."""
        try:
            yield
            raise AssertionError("Expected honesty violation was not raised")
        except HonestyViolation as e:
            self.violations.append(e)
            if claim is not None and e.claim != claim:
                raise AssertionError(f"Expected claim '{claim}', got '{e.claim}'") from e


@pytest.fixture
def honesty_validator() -> HonestyTestValidator:
    """Provide a honesty test validator."""
    return HonestyTestValidator()


class MarkovBlanketTestValidator:
    """Helper for testing Markov blanket enforcement."""

    def __init__(self) -> None:
        self.violations: list[MarkovBlanketViolation] = []

    @contextmanager
    def expect_boundary_violation(self, colony: str | None = None) -> Generator[None, None, None]:
        """Context manager that expects a boundary violation."""
        try:
            yield
            raise AssertionError("Expected Markov blanket violation was not raised")
        except MarkovBlanketViolation as e:
            self.violations.append(e)
            if colony is not None and e.colony != colony:
                raise AssertionError(f"Expected colony '{colony}', got '{e.colony}'") from e


@pytest.fixture
def markov_blanket_validator() -> MarkovBlanketTestValidator:
    """Provide a Markov blanket test validator."""
    return MarkovBlanketTestValidator()


@pytest.fixture
def safety_disabled() -> Generator[None, None, None]:
    """Temporarily disable safety checks for testing."""
    with patch("kagami.core.safety.cbf_decorators.SAFETY_ENABLED", False):
        yield


@pytest.fixture
def safety_strict() -> Generator[None, None, None]:
    """Enable strict safety mode for testing."""
    with patch("kagami.core.safety.cbf_decorators.STRICT_MODE", True):
        yield


__all__ = [
    "CBFTestValidator",
    "HonestyTestValidator",
    "MarkovBlanketTestValidator",
    "cbf_validator",
    "mock_cbf_enforcer",
    "honesty_validator",
    "markov_blanket_validator",
    "safety_disabled",
    "safety_strict",
]
