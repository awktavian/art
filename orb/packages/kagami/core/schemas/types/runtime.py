"""Runtime type checking and validation utilities.

This module provides utilities for runtime type checking, especially useful
when working with optional dependencies and dynamic type resolution.

Usage:
    from kagami.core.schemas.types.runtime import check_implements_protocol, safe_cast

    if check_implements_protocol(obj, WorldModelProtocol):
        model = safe_cast(obj, WorldModelProtocol)
"""

from __future__ import annotations

from typing import Any, TypeVar, cast, get_args, get_origin

T = TypeVar("T")
# Note: Cannot use `bound=Protocol` directly in Python 3.11+
# Using Any instead for protocol type variable
P = TypeVar("P")


def check_implements_protocol(obj: Any, protocol: type[P]) -> bool:
    """Check if object implements a protocol at runtime.

    Args:
        obj: Object to check
        protocol: Protocol class to check against

    Returns:
        True if object implements protocol, False otherwise

    Example:
        >>> from kagami.core.schemas.types.optional_deps import WorldModelProtocol
        >>> if check_implements_protocol(model, WorldModelProtocol):
        ...     result = model.encode(data)
    """
    if not hasattr(protocol, "__protocol_attrs__"):
        # Not a protocol, fall back to isinstance
        try:
            return isinstance(obj, protocol)

        except TypeError:
            return False

    # Check if object has all required protocol attributes
    try:
        return isinstance(obj, protocol)
    except TypeError:
        # Protocol not runtime checkable, check manually
        required_attrs: set[str] = getattr(protocol, "__protocol_attrs__", set())
        return all(hasattr(obj, attr) for attr in required_attrs)


def safe_cast(obj: Any, target_type: type[T]) -> T:
    """Safely cast object to target type with runtime validation.

    Args:
        obj: Object to cast
        target_type: Target type to cast to

    Returns:
        Object cast to target type

    Raises:
        TypeError: If object doesn't match target type

    Example:
        >>> model = safe_cast(maybe_model, WorldModel)
    """
    # If target_type is a Protocol, check implementation
    if hasattr(target_type, "__protocol_attrs__"):
        if not check_implements_protocol(obj, target_type):
            raise TypeError(
                f"Object {type(obj).__name__} does not implement protocol {target_type.__name__}"
            )
        return cast(T, obj)

    # For regular types, use isinstance check
    if not isinstance(obj, target_type):
        raise TypeError(
            f"Object of type {type(obj).__name__} cannot be cast to {target_type.__name__}"
        )

    return obj


def optional_cast(obj: Any | None, target_type: type[T]) -> T | None:
    """Safely cast optional object to target type.

    Args:
        obj: Object to cast (or None)
        target_type: Target type to cast to

    Returns:
        Object cast to target type, or None if input was None

    Example:
        >>> model = optional_cast(maybe_model, WorldModel)
        >>> if model is not None:
        ...     result = model.encode(data)
    """
    if obj is None:
        return None
    return safe_cast(obj, target_type)


def is_optional_type(tp: Any) -> bool:
    """Check if a type is Optional[T] (i.e., T | None).

    Args:
        tp: Type to check

    Returns:
        True if type is Optional, False otherwise

    Example:
        >>> is_optional_type(Optional[int])
        True
        >>> is_optional_type(int)
        False
    """
    origin = get_origin(tp)
    if origin is None:
        return False

    # Check for Union[T, None] or T | None
    if origin is type(None) or str(origin) in ("UnionType", "Union"):
        args = get_args(tp)
        return type(None) in args

    return False


def get_optional_inner_type(tp: Any) -> type[Any] | None:
    """Extract inner type from Optional[T].

    Args:
        tp: Optional type to extract from

    Returns:
        Inner type T if input is Optional[T], None otherwise

    Example:
        >>> get_optional_inner_type(Optional[int])
        <class 'int'>
    """
    if not is_optional_type(tp):
        return None

    args = get_args(tp)
    # Remove None from union
    non_none_args = [arg for arg in args if arg is not type(None)]

    if len(non_none_args) == 1:
        result: type[Any] | None = non_none_args[0]
        return result

    # Multiple non-None types in union
    return None


class TypeValidator:
    """Runtime type validator for complex type checking scenarios.

    Example:
        >>> validator = TypeValidator()
        >>> validator.register_protocol(WorldModelProtocol)
        >>> if validator.validate(obj, WorldModelProtocol):
        ...     # obj implements WorldModelProtocol
    """

    def __init__(self) -> None:
        self._registered_protocols: dict[str, type[Any]] = {}

    def register_protocol(self, protocol: type[P]) -> None:
        """Register a protocol for validation.

        Args:
            protocol: Protocol to register
        """
        self._registered_protocols[protocol.__name__] = protocol

    def validate(self, obj: Any, expected_type: type[T]) -> bool:
        """Validate that object matches expected type.

        Args:
            obj: Object to validate
            expected_type: Expected type

        Returns:
            True if object matches type, False otherwise
        """
        # Check if it's a registered protocol
        type_name = getattr(expected_type, "__name__", None)
        if type_name in self._registered_protocols:
            return check_implements_protocol(obj, expected_type)

        # Fall back to isinstance
        try:
            return isinstance(obj, expected_type)
        except TypeError:
            return False

    def validate_optional(self, obj: Any | None, expected_type: type[T]) -> bool:
        """Validate that object matches Optional[expected_type].

        Args:
            obj: Object to validate (may be None)
            expected_type: Expected inner type

        Returns:
            True if object is None or matches type, False otherwise
        """
        if obj is None:
            return True
        return self.validate(obj, expected_type)


# Global validator instance
_global_validator = TypeValidator()


def register_protocol(protocol: type[P]) -> None:
    """Register a protocol in the global validator.

    Args:
        protocol: Protocol to register

    Example:
        >>> register_protocol(WorldModelProtocol)
    """
    _global_validator.register_protocol(protocol)


def validate_type(obj: Any, expected_type: type[T]) -> bool:
    """Validate object against expected type using global validator.

    Args:
        obj: Object to validate
        expected_type: Expected type

    Returns:
        True if object matches type, False otherwise

    Example:
        >>> if validate_type(model, WorldModel):
        ...     result = model.encode(data)
    """
    return _global_validator.validate(obj, expected_type)


def ensure_type(obj: Any, expected_type: type[T], name: str = "object") -> T:
    """Ensure object matches expected type, raise TypeError if not.

    Args:
        obj: Object to check
        expected_type: Expected type
        name: Name for error messages

    Returns:
        Object cast to expected type

    Raises:
        TypeError: If object doesn't match expected type

    Example:
        >>> model = ensure_type(maybe_model, WorldModel, "world model")
    """
    if not validate_type(obj, expected_type):
        raise TypeError(
            f"{name} must be of type {expected_type.__name__}, got {type(obj).__name__}"
        )
    return cast(T, obj)


def ensure_optional_type(obj: Any | None, expected_type: type[T], name: str = "object") -> T | None:
    """Ensure object matches Optional[expected_type].

    Args:
        obj: Object to check (may be None)
        expected_type: Expected inner type
        name: Name for error messages

    Returns:
        Object cast to expected type, or None

    Raises:
        TypeError: If object doesn't match expected type

    Example:
        >>> model = ensure_optional_type(maybe_model, WorldModel, "world model")
    """
    if obj is None:
        return None
    return ensure_type(obj, expected_type, name)


# ============================================================================
# Attribute Checking Utilities
# ============================================================================


def has_method(obj: Any, method_name: str) -> bool:
    """Check if object has a callable method.

    Args:
        obj: Object to check
        method_name: Name of method to look for

    Returns:
        True if object has callable method, False otherwise
    """
    return hasattr(obj, method_name) and callable(getattr(obj, method_name))


def has_methods(obj: Any, *method_names: str) -> bool:
    """Check if object has all specified methods.

    Args:
        obj: Object to check
        method_names: Names of methods to look for

    Returns:
        True if object has all methods, False otherwise
    """
    return all(has_method(obj, name) for name in method_names)


def has_attribute(obj: Any, attr_name: str, attr_type: type[T] | None = None) -> bool:
    """Check if object has an attribute of specified type.

    Args:
        obj: Object to check
        attr_name: Name of attribute to look for
        attr_type: Optional type to check attribute against

    Returns:
        True if object has attribute of correct type, False otherwise
    """
    if not hasattr(obj, attr_name):
        return False

    if attr_type is None:
        return True

    attr_value = getattr(obj, attr_name)
    return isinstance(attr_value, attr_type)
