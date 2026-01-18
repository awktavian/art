"""Tests for optional imports utility module.

Tests the clear error message pattern for optional dependencies.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from kagami.core.utils.optional_imports import (
    MissingOptionalDependency,
    has_package,
    require_package,
)


def test_require_package_with_available_module() -> None:
    """Test require_package when module is available."""
    import sys

    # sys is always available
    result = require_package(
        sys, package_name="sys", feature_name="System Module", install_cmd="builtin"
    )
    assert result is sys


def test_require_package_with_missing_module() -> None:
    """Test require_package when module is None (import failed)."""
    with pytest.raises(MissingOptionalDependency) as exc_info:
        require_package(
            None,
            package_name="fake-package",
            feature_name="Fake Feature",
            install_cmd="pip install fake-package",
        )

    error = exc_info.value
    assert error.package_name == "fake-package"
    assert error.feature_name == "Fake Feature"
    assert error.install_cmd == "pip install fake-package"
    assert "Fake Feature" in str(error)
    assert "pip install fake-package" in str(error)


def test_require_package_with_additional_info() -> None:
    """Test require_package with additional installation info."""
    with pytest.raises(MissingOptionalDependency) as exc_info:
        require_package(
            None,
            package_name="complex-package",
            feature_name="Complex Feature",
            install_cmd="pip install complex-package",
            additional_info="Requires system library: brew install libfoo",
        )

    error = exc_info.value
    assert error.additional_info == "Requires system library: brew install libfoo"
    assert "brew install libfoo" in str(error)


def test_require_package_default_install_cmd() -> None:
    """Test require_package generates default install command."""
    with pytest.raises(MissingOptionalDependency) as exc_info:
        require_package(None, package_name="simple-pkg", feature_name="Simple Feature")

    error = exc_info.value
    assert error.install_cmd == "pip install simple-pkg"
    assert "pip install simple-pkg" in str(error)


def test_has_package_with_available_module() -> None:
    """Test has_package returns True for available module."""
    import sys

    assert has_package(sys) is True


def test_has_package_with_missing_module() -> None:
    """Test has_package returns False for None module."""
    assert has_package(None) is False


def test_missing_optional_dependency_error_message() -> None:
    """Test MissingOptionalDependency error message format."""
    error = MissingOptionalDependency(
        package_name="genesis-world",
        feature_name="Genesis Physics Engine",
        install_cmd="pip install genesis-world",
        additional_info="See: https://example.com",
    )

    msg = str(error)
    assert "Genesis Physics Engine" in msg
    assert "genesis-world" in msg
    assert "pip install genesis-world" in msg
    assert "https://example.com" in msg


def test_missing_optional_dependency_without_additional_info() -> None:
    """Test MissingOptionalDependency without additional info."""
    error = MissingOptionalDependency(
        package_name="z3-solver",
        feature_name="Z3 SMT Solver",
        install_cmd="pip install z3-solver",
    )

    msg = str(error)
    assert "Z3 SMT Solver" in msg
    assert "z3-solver" in msg
    assert "pip install z3-solver" in msg
    assert error.additional_info is None


def test_require_package_type_preservation() -> None:
    """Test that require_package preserves module type."""
    import json

    # Test with a real module
    result = require_package(json, "json", "JSON Module", "builtin")
    assert result is json
    assert hasattr(result, "dumps")  # Verify it's the actual json module


def test_integration_pattern_genesis() -> None:
    """Test the pattern used in genesis_physics_wrapper.py."""
    # Simulate the pattern:
    # try:
    #     import genesis as gs
    # except ImportError:
    #     gs = None
    #
    # gs = require_package(gs, "genesis-world", "Genesis", ...)

    fake_genesis = None  # Simulate import failure

    with pytest.raises(MissingOptionalDependency) as exc_info:
        require_package(
            fake_genesis,
            package_name="genesis-world",
            feature_name="Genesis Physics Engine",
            install_cmd="pip install genesis-world",
            additional_info=(
                "Genesis provides unified physics simulation including:\n"
                "  - Rigid body dynamics\n"
                "  - Soft body simulation"
            ),
        )

    error = exc_info.value
    assert "Genesis Physics Engine" in str(error)
    assert "Rigid body dynamics" in str(error)


def test_integration_pattern_z3() -> None:
    """Test the pattern used in tic_verifier.py."""
    fake_z3 = None  # Simulate import failure

    with pytest.raises(MissingOptionalDependency) as exc_info:
        require_package(
            fake_z3,
            package_name="z3-solver",
            feature_name="Z3 SMT Solver",
            install_cmd="pip install z3-solver",
            additional_info="Z3 provides formal verification for Typed Intent Calculus.",
        )

    error = exc_info.value
    assert "Z3 SMT Solver" in str(error)
    assert "formal verification" in str(error)


def test_integration_pattern_pydatalog() -> None:
    """Test the pattern used in prolog_engine.py."""
    fake_pydatalog = None  # Simulate import failure

    with pytest.raises(MissingOptionalDependency) as exc_info:
        require_package(
            fake_pydatalog,
            package_name="pyDatalog",
            feature_name="Prolog-Style Logic Programming",
            install_cmd="pip install pyDatalog",
            additional_info="pyDatalog enables declarative logic programming in Python.",
        )

    error = exc_info.value
    assert "Prolog-Style Logic Programming" in str(error)
    assert "declarative logic" in str(error)


def test_has_package_type_guard() -> None:
    """Test has_package can be used as a type guard."""
    import json

    # Test with real module
    if has_package(json):
        # Should be able to use json without type errors
        assert json.dumps({"test": "value"}) == '{"test": "value"}'

    # Test with None
    fake_module = None
    if not has_package(fake_module):
        # Should branch correctly
        assert fake_module is None
