"""Base configuration class with shared loading/validation patterns."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, TypeVar

T = TypeVar("T", bound="BaseConfig")


@dataclass
class BaseConfig:
    """Base configuration with environment and file loading support.

    Subclasses should define their fields and optionally override
    _env_prefix for environment variable loading.
    """

    _env_prefix: ClassVar[str] = "KAGAMI_"

    @classmethod
    def from_env(cls: type[T], **overrides: Any) -> T:
        """Load config from environment variables.

        Looks for {_env_prefix}{FIELD_NAME} for each field.
        """
        kwargs: dict[str, Any] = {}
        for f in cls.__dataclass_fields__:
            env_key = f"{cls._env_prefix}{f.upper()}"
            if env_key in os.environ:
                kwargs[f] = os.environ[env_key]
        kwargs.update(overrides)
        return cls(**kwargs)

    @classmethod
    def from_file(cls: type[T], path: Path | str, **overrides: Any) -> T:
        """Load config from JSON file."""
        with open(path) as f:
            data = json.load(f)
        data.update(overrides)
        return cls(**data)

    def validate(self) -> None:
        """Override in subclasses to add validation logic."""
