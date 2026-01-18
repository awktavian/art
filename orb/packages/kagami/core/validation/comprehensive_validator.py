"""Comprehensive input validation framework for production-ready robustness.

This module provides comprehensive input validation with detailed error reporting,
type safety, and security validation for all public APIs.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, TypeVar

from kagami.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T")
ValidationLevel = Literal["strict", "permissive", "security_focused"]


@dataclass
class ValidationResult:
    """Result of a validation operation."""

    valid: bool
    value: Any = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    sanitized_value: Any = None

    def raise_if_invalid(self) -> None:
        """Raise ValidationError if validation failed."""
        if not self.valid:
            error_msg = f"Validation failed: {'; '.join(self.errors)}"
            raise ValidationError(
                error_msg, context={"errors": self.errors, "warnings": self.warnings}
            )


@dataclass
class ValidationRule:
    """Represents a single validation rule."""

    name: str
    validator: Callable[[Any], bool]
    error_message: str
    severity: Literal["error", "warning"] = "error"


@dataclass
class ValidationConfig:
    """Configuration for validation behavior."""

    level: ValidationLevel = "strict"
    allow_none: bool = False
    sanitize: bool = True
    max_recursion_depth: int = 10
    security_scan: bool = True
    log_validation_errors: bool = True


class ComprehensiveValidator:
    """Production-grade validator with comprehensive input validation."""

    def __init__(self, config: ValidationConfig | None = None):
        self.config = config or ValidationConfig()
        self._init_security_patterns()

    def _init_security_patterns(self) -> None:
        """Initialize security validation patterns."""
        self.security_patterns = {
            "sql_injection": re.compile(
                r"(\bunion\b|\bselect\b|\binsert\b|\bupdate\b|\bdelete\b|\bdrop\b|\btruncate\b)",
                re.IGNORECASE,
            ),
            "script_injection": re.compile(
                r"(<script|javascript:|data:text/html|eval\(|setTimeout\()", re.IGNORECASE
            ),
            "path_traversal": re.compile(r"(\.\.\/|\.\.\\|%2e%2e|\.\.%2f|\.\.%5c)", re.IGNORECASE),
            "command_injection": re.compile(
                r"(;\s*\w+|&&\s*\w+|\|\|\s*\w+|`\w+`|\$\(\w+\))", re.IGNORECASE
            ),
        }

    def validate_string(
        self,
        value: Any,
        *,
        min_length: int | None = None,
        max_length: int | None = None,
        pattern: str | re.Pattern[str] | None = None,
        allowed_chars: str | None = None,
        forbidden_patterns: list[str] | None = None,
        field_name: str = "string",
        required: bool = True,
    ) -> ValidationResult:
        """Validate string input with comprehensive checks."""

        result = ValidationResult()

        # Handle None values
        if value is None:
            if required and not self.config.allow_none:
                result.errors.append(f"{field_name} is required but was None")
                return result
            if not required:
                result.valid = True
                result.value = None
                result.sanitized_value = None
                return result

        # Type conversion and validation
        if not isinstance(value, str):
            try:
                value = str(value)
                result.warnings.append(
                    f"{field_name} was converted from {type(value).__name__} to string"
                )
            except Exception as e:
                result.errors.append(f"{field_name} could not be converted to string: {e}")
                return result

        original_value = value

        # Security scanning
        if self.config.security_scan:
            security_issues = self._scan_for_security_issues(value)
            if security_issues:
                if self.config.level == "security_focused":
                    result.errors.extend(
                        [f"Security issue in {field_name}: {issue}" for issue in security_issues]
                    )
                    return result
                else:
                    result.warnings.extend(
                        [
                            f"Potential security issue in {field_name}: {issue}"
                            for issue in security_issues
                        ]
                    )

        # Sanitization
        if self.config.sanitize:
            value = self._sanitize_string(value)
            if value != original_value:
                result.warnings.append(f"{field_name} was sanitized")

        # Length validation
        if min_length is not None and len(value) < min_length:
            result.errors.append(
                f"{field_name} must be at least {min_length} characters, got {len(value)}"
            )

        if max_length is not None and len(value) > max_length:
            if self.config.level == "strict":
                result.errors.append(
                    f"{field_name} must not exceed {max_length} characters, got {len(value)}"
                )
            else:
                value = value[:max_length]
                result.warnings.append(f"{field_name} was truncated to {max_length} characters")

        # Pattern validation
        if pattern is not None:
            if isinstance(pattern, str):
                pattern = re.compile(pattern)
            if not pattern.match(value):
                result.errors.append(f"{field_name} does not match required pattern")

        # Character validation
        if allowed_chars is not None:
            invalid_chars = set(value) - set(allowed_chars)
            if invalid_chars:
                result.errors.append(
                    f"{field_name} contains invalid characters: {', '.join(invalid_chars)}"
                )

        # Forbidden pattern validation
        if forbidden_patterns:
            for forbidden_pattern in forbidden_patterns:
                if isinstance(forbidden_pattern, str):
                    forbidden_pattern = re.compile(forbidden_pattern)
                if forbidden_pattern.search(value):
                    result.errors.append(f"{field_name} contains forbidden pattern")

        result.valid = len(result.errors) == 0
        result.value = original_value
        result.sanitized_value = value

        if self.config.log_validation_errors and result.errors:
            logger.warning(f"String validation failed for {field_name}: {result.errors}")

        return result

    def validate_integer(
        self,
        value: Any,
        *,
        min_value: int | None = None,
        max_value: int | None = None,
        field_name: str = "integer",
        required: bool = True,
    ) -> ValidationResult:
        """Validate integer input with range checking."""

        result = ValidationResult()

        # Handle None values
        if value is None:
            if required and not self.config.allow_none:
                result.errors.append(f"{field_name} is required but was None")
                return result
            if not required:
                result.valid = True
                result.value = None
                result.sanitized_value = None
                return result

        # Type conversion and validation
        original_value = value
        if not isinstance(value, int):
            try:
                if isinstance(value, str):
                    value = int(value.strip())
                elif isinstance(value, float):
                    if value.is_integer():
                        value = int(value)
                    else:
                        result.errors.append(f"{field_name} is not a whole number: {value}")
                        return result
                else:
                    value = int(value)
                result.warnings.append(
                    f"{field_name} was converted from {type(original_value).__name__} to integer"
                )
            except (ValueError, TypeError) as e:
                result.errors.append(f"{field_name} could not be converted to integer: {e}")
                return result

        # Range validation
        if min_value is not None and value < min_value:
            result.errors.append(f"{field_name} must be at least {min_value}, got {value}")

        if max_value is not None and value > max_value:
            result.errors.append(f"{field_name} must not exceed {max_value}, got {value}")

        result.valid = len(result.errors) == 0
        result.value = original_value
        result.sanitized_value = value

        if self.config.log_validation_errors and result.errors:
            logger.warning(f"Integer validation failed for {field_name}: {result.errors}")

        return result

    def validate_float(
        self,
        value: Any,
        *,
        min_value: float | None = None,
        max_value: float | None = None,
        field_name: str = "float",
        required: bool = True,
    ) -> ValidationResult:
        """Validate float input with range checking."""

        result = ValidationResult()

        # Handle None values
        if value is None:
            if required and not self.config.allow_none:
                result.errors.append(f"{field_name} is required but was None")
                return result
            if not required:
                result.valid = True
                result.value = None
                result.sanitized_value = None
                return result

        # Type conversion and validation
        original_value = value
        if not isinstance(value, (int, float)):
            try:
                if isinstance(value, str):
                    value = float(value.strip())
                else:
                    value = float(value)
                result.warnings.append(
                    f"{field_name} was converted from {type(original_value).__name__} to float"
                )
            except (ValueError, TypeError) as e:
                result.errors.append(f"{field_name} could not be converted to float: {e}")
                return result
        else:
            value = float(value)

        # Range validation
        if min_value is not None and value < min_value:
            result.errors.append(f"{field_name} must be at least {min_value}, got {value}")

        if max_value is not None and value > max_value:
            result.errors.append(f"{field_name} must not exceed {max_value}, got {value}")

        result.valid = len(result.errors) == 0
        result.value = original_value
        result.sanitized_value = value

        if self.config.log_validation_errors and result.errors:
            logger.warning(f"Float validation failed for {field_name}: {result.errors}")

        return result

    def validate_path(
        self,
        value: Any,
        *,
        must_exist: bool = False,
        must_be_file: bool = False,
        must_be_directory: bool = False,
        allowed_extensions: list[str] | None = None,
        forbidden_paths: list[str] | None = None,
        field_name: str = "path",
        required: bool = True,
    ) -> ValidationResult:
        """Validate file path with security and existence checks."""

        result = ValidationResult()

        # Handle None values
        if value is None:
            if required and not self.config.allow_none:
                result.errors.append(f"{field_name} is required but was None")
                return result
            if not required:
                result.valid = True
                result.value = None
                result.sanitized_value = None
                return result

        # Convert to Path object
        try:
            if isinstance(value, str):
                path = Path(value)
            elif isinstance(value, Path):
                path = value
            else:
                result.errors.append(
                    f"{field_name} must be a string or Path object, got {type(value).__name__}"
                )
                return result
        except Exception as e:
            result.errors.append(f"{field_name} could not be converted to Path: {e}")
            return result

        original_value = value

        # Security validation - check for path traversal
        if self.config.security_scan:
            path_str = str(path)
            if self.security_patterns["path_traversal"].search(path_str):
                result.errors.append(f"{field_name} contains path traversal attempt")
                return result

        # Normalize path
        try:
            normalized_path = path.resolve()
        except Exception as e:
            result.errors.append(f"{field_name} could not be resolved: {e}")
            return result

        # Existence validation
        if must_exist and not normalized_path.exists():
            result.errors.append(f"{field_name} does not exist: {normalized_path}")

        if must_be_file and normalized_path.exists() and not normalized_path.is_file():
            result.errors.append(f"{field_name} must be a file, got directory: {normalized_path}")

        if must_be_directory and normalized_path.exists() and not normalized_path.is_dir():
            result.errors.append(f"{field_name} must be a directory, got file: {normalized_path}")

        # Extension validation
        if allowed_extensions and normalized_path.exists() and normalized_path.is_file():
            ext = normalized_path.suffix.lower()
            if ext not in [f".{ext.lstrip('.')}" for ext in allowed_extensions]:
                result.errors.append(
                    f"{field_name} has invalid extension '{ext}', allowed: {allowed_extensions}"
                )

        # Forbidden path validation
        if forbidden_paths:
            path_str = str(normalized_path)
            for forbidden in forbidden_paths:
                if path_str.startswith(forbidden):
                    result.errors.append(f"{field_name} is in forbidden location: {forbidden}")

        result.valid = len(result.errors) == 0
        result.value = original_value
        result.sanitized_value = normalized_path

        if self.config.log_validation_errors and result.errors:
            logger.warning(f"Path validation failed for {field_name}: {result.errors}")

        return result

    def validate_email(
        self, value: Any, *, field_name: str = "email", required: bool = True
    ) -> ValidationResult:
        """Validate email address format."""

        result = ValidationResult()

        # Handle None values
        if value is None:
            if required and not self.config.allow_none:
                result.errors.append(f"{field_name} is required but was None")
                return result
            if not required:
                result.valid = True
                result.value = None
                result.sanitized_value = None
                return result

        # Convert to string
        if not isinstance(value, str):
            try:
                value = str(value)
            except Exception as e:
                result.errors.append(f"{field_name} could not be converted to string: {e}")
                return result

        original_value = value
        value = value.strip().lower()

        # Basic email pattern validation
        email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

        if not email_pattern.match(value):
            result.errors.append(f"{field_name} is not a valid email address")

        result.valid = len(result.errors) == 0
        result.value = original_value
        result.sanitized_value = value

        if self.config.log_validation_errors and result.errors:
            logger.warning(f"Email validation failed for {field_name}: {result.errors}")

        return result

    def validate_dict(
        self,
        value: Any,
        *,
        required_keys: list[str] | None = None,
        optional_keys: list[str] | None = None,
        key_validator: Callable[[str], ValidationResult] | None = None,
        value_validator: Callable[[Any], ValidationResult] | None = None,
        max_size: int | None = None,
        field_name: str = "dictionary",
        required: bool = True,
    ) -> ValidationResult:
        """Validate dictionary structure and contents."""

        result = ValidationResult()

        # Handle None values
        if value is None:
            if required and not self.config.allow_none:
                result.errors.append(f"{field_name} is required but was None")
                return result
            if not required:
                result.valid = True
                result.value = None
                result.sanitized_value = None
                return result

        # Type validation
        if not isinstance(value, Mapping):
            result.errors.append(f"{field_name} must be a dictionary, got {type(value).__name__}")
            return result

        original_value = value
        sanitized_dict = {}

        # Size validation
        if max_size is not None and len(value) > max_size:
            result.errors.append(
                f"{field_name} has too many items: {len(value)}, maximum allowed: {max_size}"
            )

        # Key validation
        all_allowed_keys = set()
        if required_keys:
            all_allowed_keys.update(required_keys)
            for key in required_keys:
                if key not in value:
                    result.errors.append(f"{field_name} missing required key: '{key}'")

        if optional_keys:
            all_allowed_keys.update(optional_keys)

        # Check for unexpected keys
        if required_keys or optional_keys:
            unexpected_keys = set(value.keys()) - all_allowed_keys
            if unexpected_keys:
                if self.config.level == "strict":
                    result.errors.append(
                        f"{field_name} contains unexpected keys: {list(unexpected_keys)}"
                    )
                else:
                    result.warnings.append(
                        f"{field_name} contains unexpected keys (ignored): {list(unexpected_keys)}"
                    )

        # Validate individual keys and values
        for key, val in value.items():
            # Validate key
            if key_validator:
                key_result = key_validator(key)
                if not key_result.valid:
                    result.errors.extend(
                        [f"Key '{key}' in {field_name}: {error}" for error in key_result.errors]
                    )
                    continue
                sanitized_key = key_result.sanitized_value or key
            else:
                sanitized_key = key

            # Validate value
            if value_validator:
                val_result = value_validator(val)
                if not val_result.valid:
                    result.errors.extend(
                        [
                            f"Value for key '{key}' in {field_name}: {error}"
                            for error in val_result.errors
                        ]
                    )
                    continue
                sanitized_val = (
                    val_result.sanitized_value if val_result.sanitized_value is not None else val
                )
            else:
                sanitized_val = val

            sanitized_dict[sanitized_key] = sanitized_val

        result.valid = len(result.errors) == 0
        result.value = original_value
        result.sanitized_value = sanitized_dict

        if self.config.log_validation_errors and result.errors:
            logger.warning(f"Dictionary validation failed for {field_name}: {result.errors}")

        return result

    def validate_list(
        self,
        value: Any,
        *,
        item_validator: Callable[[Any], ValidationResult] | None = None,
        min_length: int | None = None,
        max_length: int | None = None,
        unique_items: bool = False,
        field_name: str = "list",
        required: bool = True,
    ) -> ValidationResult:
        """Validate list structure and contents."""

        result = ValidationResult()

        # Handle None values
        if value is None:
            if required and not self.config.allow_none:
                result.errors.append(f"{field_name} is required but was None")
                return result
            if not required:
                result.valid = True
                result.value = None
                result.sanitized_value = None
                return result

        # Type validation
        if not isinstance(value, Sequence) or isinstance(value, str):
            result.errors.append(
                f"{field_name} must be a list or sequence, got {type(value).__name__}"
            )
            return result

        original_value = value
        sanitized_list = []

        # Length validation
        if min_length is not None and len(value) < min_length:
            result.errors.append(
                f"{field_name} must have at least {min_length} items, got {len(value)}"
            )

        if max_length is not None and len(value) > max_length:
            if self.config.level == "strict":
                result.errors.append(
                    f"{field_name} must not exceed {max_length} items, got {len(value)}"
                )
            else:
                value = value[:max_length]
                result.warnings.append(f"{field_name} was truncated to {max_length} items")

        # Validate individual items
        seen_items = set() if unique_items else None
        for i, item in enumerate(value):
            if item_validator:
                item_result = item_validator(item)
                if not item_result.valid:
                    result.errors.extend(
                        [f"Item {i} in {field_name}: {error}" for error in item_result.errors]
                    )
                    continue
                sanitized_item = (
                    item_result.sanitized_value if item_result.sanitized_value is not None else item
                )
            else:
                sanitized_item = item

            # Check uniqueness
            if unique_items:
                # Convert to hashable type for set operations
                hashable_item = self._make_hashable(sanitized_item)
                if hashable_item in seen_items:
                    result.errors.append(f"Duplicate item found in {field_name} at index {i}")
                    continue
                seen_items.add(hashable_item)

            sanitized_list.append(sanitized_item)

        result.valid = len(result.errors) == 0
        result.value = original_value
        result.sanitized_value = sanitized_list

        if self.config.log_validation_errors and result.errors:
            logger.warning(f"List validation failed for {field_name}: {result.errors}")

        return result

    def _scan_for_security_issues(self, text: str) -> list[str]:
        """Scan text for potential security issues."""
        issues = []

        for issue_type, pattern in self.security_patterns.items():
            if pattern.search(text):
                issues.append(f"Potential {issue_type.replace('_', ' ')} detected")

        return issues

    def _sanitize_string(self, text: str) -> str:
        """Sanitize string by removing/escaping dangerous characters."""
        # Remove null bytes
        text = text.replace("\x00", "")

        # Remove or escape control characters (except common whitespace)
        sanitized = "".join(char for char in text if ord(char) >= 32 or char in "\t\n\r")

        # Trim whitespace
        sanitized = sanitized.strip()

        return sanitized

    def _make_hashable(self, item: Any) -> Any:
        """Convert item to hashable type for uniqueness checking."""
        if isinstance(item, (str, int, float, bool, type(None))):
            return item
        elif isinstance(item, (list, tuple)):
            return tuple(self._make_hashable(x) for x in item)
        elif isinstance(item, dict):
            return tuple(sorted((k, self._make_hashable(v)) for k, v in item.items()))
        elif hasattr(item, "__dict__"):
            return str(item)
        else:
            return str(item)


# Global validator instance
_default_validator = ComprehensiveValidator()


# Convenience functions using the default validator
def validate_string(*args, **kwargs) -> ValidationResult:
    """Validate string using default validator."""
    return _default_validator.validate_string(*args, **kwargs)


def validate_integer(*args, **kwargs) -> ValidationResult:
    """Validate integer using default validator."""
    return _default_validator.validate_integer(*args, **kwargs)


def validate_float(*args, **kwargs) -> ValidationResult:
    """Validate float using default validator."""
    return _default_validator.validate_float(*args, **kwargs)


def validate_path(*args, **kwargs) -> ValidationResult:
    """Validate path using default validator."""
    return _default_validator.validate_path(*args, **kwargs)


def validate_email(*args, **kwargs) -> ValidationResult:
    """Validate email using default validator."""
    return _default_validator.validate_email(*args, **kwargs)


def validate_dict(*args, **kwargs) -> ValidationResult:
    """Validate dictionary using default validator."""
    return _default_validator.validate_dict(*args, **kwargs)


def validate_list(*args, **kwargs) -> ValidationResult:
    """Validate list using default validator."""
    return _default_validator.validate_list(*args, **kwargs)


__all__ = [
    "ComprehensiveValidator",
    "ValidationConfig",
    "ValidationLevel",
    "ValidationResult",
    "ValidationRule",
    "validate_dict",
    "validate_email",
    "validate_float",
    "validate_integer",
    "validate_list",
    "validate_path",
    "validate_string",
]
