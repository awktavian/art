"""Fallback utilities for optional dependencies.

Provides graceful degradation when optional packages are not installed.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class MissingDependencyError(ImportError):
    """Raised when an optional dependency is required but not installed."""

    def __init__(self, package: str, feature: str | None = None):
        self.package = package
        self.feature = feature
        msg = f"Package '{package}' is required"
        if feature:
            msg += f" for {feature}"
        msg += f". Install with: pip install {package}"
        super().__init__(msg)


class LazyImport:
    """Lazy import wrapper that defers module loading until first access.

    Usage:
        torch = LazyImport("torch")
        # torch is not imported yet
        x = torch.tensor([1, 2, 3])  # Now torch is imported
    """

    def __init__(self, module_name: str, package: str | None = None):
        self._module_name = module_name
        self._package = package or module_name
        self._module: Any = None

    def _load(self) -> Any:
        if self._module is None:
            try:
                self._module = importlib.import_module(self._module_name)
            except ImportError as e:
                raise MissingDependencyError(self._package) from e
        return self._module

    def __getattr__(self, name: str) -> Any:
        return getattr(self._load(), name)

    def __dir__(self) -> list[str]:
        return dir(self._load())


def create_fallback_class(
    class_name: str,
    package: str,
    feature: str | None = None,
) -> type:
    """Create a fallback class that raises MissingDependencyError on instantiation.

    Args:
        class_name: Name for the fallback class
        package: Package that needs to be installed
        feature: Optional feature description

    Returns:
        A class that raises MissingDependencyError when instantiated
    """

    class FallbackClass:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise MissingDependencyError(package, feature)

        def __class_getitem__(cls, item: Any) -> type:
            return cls

    FallbackClass.__name__ = class_name
    FallbackClass.__qualname__ = class_name
    return FallbackClass


def create_fallback_function(
    func_name: str,
    package: str,
    feature: str | None = None,
) -> Callable[..., Any]:
    """Create a fallback function that raises MissingDependencyError when called.

    Args:
        func_name: Name for the fallback function
        package: Package that needs to be installed
        feature: Optional feature description

    Returns:
        A function that raises MissingDependencyError when called
    """

    def fallback(*args: Any, **kwargs: Any) -> Any:
        raise MissingDependencyError(package, feature)

    fallback.__name__ = func_name
    fallback.__qualname__ = func_name
    return fallback


__all__ = [
    "LazyImport",
    "MissingDependencyError",
    "create_fallback_class",
    "create_fallback_function",
]
