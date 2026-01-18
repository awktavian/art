"""Optional package import utilities.

Provides utilities for handling optional dependencies with clear error messages.
"""

from __future__ import annotations

import logging
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MissingOptionalDependency(ImportError):
    """Error raised when an optional dependency is missing.

    Provides structured information about:
    - Which package is missing
    - What feature requires it
    - How to install it
    - Any additional context
    """

    def __init__(
        self,
        package_name: str,
        feature_name: str,
        install_cmd: str | None = None,
        additional_info: str | None = None,
    ) -> None:
        self.package_name = package_name
        self.feature_name = feature_name
        self.install_cmd = install_cmd or f"pip install {package_name}"
        self.additional_info = additional_info

        msg = (
            f"{feature_name} requires the '{package_name}' package.\n\n"
            f"Install with:\n  {self.install_cmd}"
        )
        if additional_info:
            msg += f"\n\n{additional_info}"

        super().__init__(msg)


def require_package(
    module: T | None,
    package_name: str,
    feature_name: str,
    install_cmd: str | None = None,
    additional_info: str | None = None,
) -> T:
    """Require an optional package, raising a clear error if not available.

    Args:
        module: The imported module (or None if import failed)
        package_name: Name of the pip package
        feature_name: Human-readable name of the feature requiring this package
        install_cmd: Installation command (defaults to `pip install {package_name}`)
        additional_info: Additional helpful information

    Returns:
        The module if available

    Raises:
        MissingOptionalDependency: If the module is not available
    """
    if module is not None:
        return module

    raise MissingOptionalDependency(
        package_name=package_name,
        feature_name=feature_name,
        install_cmd=install_cmd,
        additional_info=additional_info,
    )


def has_package(module: Any | None) -> bool:
    """Check if an optional package is available.

    Args:
        module: The imported module (or None if import failed)

    Returns:
        True if the module is available
    """
    return module is not None


# Backward compatibility alias
is_package_available = has_package


__all__ = ["MissingOptionalDependency", "has_package", "is_package_available", "require_package"]
