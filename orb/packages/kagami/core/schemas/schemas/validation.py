"""Comprehensive input validation schemas for K os API endpoints.

This module provides Pydantic models for validating all API inputs
to prevent security vulnerabilities and ensure data integrity.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

_field_validator: Any = None
try:
    from pydantic import field_validator

    _field_validator = field_validator
except Exception:
    try:
        from pydantic import validator

        _field_validator = validator
    except Exception:
        pass


class CommandRequest(BaseModel):  # type: ignore[no-redef]
    """Validated command execution request."""

    command: str = Field(..., min_length=1, max_length=500)
    args: list[str] = Field(default_factory=list[Any], max_length=20)
    kwargs: dict[str, Any] = Field(default_factory=dict[str, Any])

    @_field_validator("command")
    @classmethod
    def validate_command(cls, v):  # type: ignore[no-untyped-def]
        """Validate command name."""
        import re

        if not re.match("^[a-zA-Z0-9_\\-\\.]+$", v):
            raise ValueError("Invalid command name format")
        return v

    @_field_validator("args")
    @classmethod
    def validate_args(cls, v):  # type: ignore[no-untyped-def]
        """Validate command arguments."""
        for arg in v:
            if not isinstance(arg, str) or len(arg) > 200:
                raise ValueError("Invalid argument")
        return v


class ARPositionRequest(BaseModel):
    """Validated AR position update."""

    mascot: str = Field(..., min_length=1, max_length=50)
    position: dict[str, float] = Field(...)
    rotation: dict[str, float] | None = None
    scale: float | None = Field(None, ge=0.1, le=10.0)

    @_field_validator("mascot")
    @classmethod
    def validate_mascot_name(cls, v):  # type: ignore[no-untyped-def]
        """Validate mascot name."""
        import re

        if not re.match("^[a-zA-Z0-9_\\-]+$", v):
            raise ValueError("Invalid mascot name")
        return v

    @_field_validator("position")
    @classmethod
    def validate_position(cls, v):  # type: ignore[no-untyped-def]
        """Validate 3D position."""
        required_keys = {"x", "y", "z"}
        if not all(k in v for k in required_keys):
            raise ValueError("Position must have x, y, z coordinates")
        for key, val in v.items():
            if not isinstance(val, (int, float)) or abs(val) > 1000:
                raise ValueError(f"Invalid position value for {key}")
        return v


class ARImageRequest(BaseModel):
    """Validated AR image capture request.

    Mascot and format are optional for lightweight/test flows. When omitted,
    defaults favor permissive behavior to keep AR analyze endpoint usable in
    environments without strict client payloads.
    """

    mascot: str | None = Field(None, min_length=1, max_length=50)
    image_data: str | None = Field(None, min_length=1, max_length=10000000)
    format: str | None = Field(None, pattern="^(png|jpg|jpeg)$")

    @_field_validator("image_data")
    @classmethod
    def validate_image_data(cls, v):  # type: ignore[no-untyped-def]
        """Validate base64 image data."""
        import base64

        if v is None:
            return v
        try:
            base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("Invalid base64 image data") from None
        return v


class FilesQueryRequest(BaseModel):
    """Validated files query request."""

    path: str | None = Field(None, max_length=500)
    pattern: str | None = Field(None, max_length=100)
    include_hidden: bool = Field(False)
    max_results: int = Field(100, ge=1, le=1000)
    sort_by: str | None = Field(None, pattern="^(name|size|modified|created)$")

    @_field_validator("path")
    @classmethod
    def validate_path(cls, v):  # type: ignore[no-untyped-def]
        """Validate file path."""
        if v and (".." in v or v.startswith("/")):
            raise ValueError("Invalid path")
        return v

    @_field_validator("pattern")
    @classmethod
    def validate_pattern(cls, v):  # type: ignore[no-untyped-def]
        """Validate search pattern."""
        if v:
            invalid_chars = ["<", ">", "|", "\x00"]
            if any(char in v for char in invalid_chars):
                raise ValueError("Invalid pattern characters")
        return v


class ToolSearchParams(BaseModel):
    """Validated tool search parameters."""

    query: str = Field(..., min_length=1, max_length=500)
    tags: list[str] | None = Field(None, max_length=20)
    category: str | None = Field(None, max_length=50)
    limit: int = Field(10, ge=1, le=100)

    @_field_validator("tags")
    @classmethod
    def validate_tags(cls, v):  # type: ignore[no-untyped-def]
        """Validate tag list[Any]."""
        if v:
            for tag in v:
                if not isinstance(tag, str) or len(tag) > 50:
                    raise ValueError("Invalid tag")
        return v


class ToolExecutionParams(BaseModel):
    """Validated tool execution parameters."""

    tool_name: str = Field(..., min_length=1, max_length=100)
    parameters: dict[str, Any] = Field(default_factory=dict[str, Any])
    context: dict[str, Any] | None = Field(None)
    timeout: float | None = Field(None, ge=0.1, le=300.0)

    @_field_validator("tool_name")
    @classmethod
    def validate_tool_name(cls, v):  # type: ignore[no-untyped-def]
        """Validate tool name."""
        import re

        if not re.match("^[a-zA-Z0-9_\\-\\.]+$", v):
            raise ValueError("Invalid tool name format")
        return v

    @_field_validator("parameters")
    @classmethod
    def validate_parameters(cls, v):  # type: ignore[no-untyped-def]
        """Validate execution parameters."""
        import json

        try:
            serialized = json.dumps(v)
            if len(serialized) > 100000:
                raise ValueError("Parameters too large")
        except Exception:
            raise ValueError("Parameters must be JSON serializable") from None
        return v


class LoginRequest(BaseModel):
    """Validated login request."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    remember_me: bool = Field(False)

    @_field_validator("username")
    @classmethod
    def validate_username(cls, v):  # type: ignore[no-untyped-def]
        """Validate username format."""
        import re

        if not re.match("^[a-zA-Z0-9_\\-]+$", v):
            raise ValueError("Username can only contain letters, numbers, underscore, and hyphen")
        return v


class RegisterRequest(BaseModel):
    """Validated registration request."""

    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., pattern="^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$")
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=100)

    @_field_validator("password")
    @classmethod
    def validate_password_strength(cls, v):  # type: ignore[no-untyped-def]
        """Validate password meets security requirements."""
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class WidgetCreateRequest(BaseModel):
    """Validated widget creation request."""

    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., pattern="^[a-zA-Z0-9_]+$", max_length=50)
    config: dict[str, Any] = Field(default_factory=dict[str, Any])
    position: dict[str, int] | None = None
    size: dict[str, int] | None = None

    @_field_validator("config")
    @classmethod
    def validate_config(cls, v):  # type: ignore[no-untyped-def]
        """Validate widget configuration."""
        import json

        try:
            serialized = json.dumps(v)
            if len(serialized) > 50000:
                raise ValueError("Configuration too large")
        except Exception:
            raise ValueError("Configuration must be JSON serializable") from None
        return v

    @_field_validator("position", "size")
    @classmethod
    def validate_dimensions(cls, v):  # type: ignore[no-untyped-def]
        """Validate position/size dimensions."""
        if v:
            required_keys = {"x", "y"} if "x" in (v or {}) else {"width", "height"}
            if not all(k in v for k in required_keys):
                raise ValueError(f"Must have {required_keys} properties") from None
            for val in v.values():
                if not isinstance(val, int) or val < 0 or val > 10000:
                    raise ValueError("Invalid dimension value") from None
        return v


class ProjectCreateRequest(BaseModel):
    """Validated project creation request."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)
    tags: list[str] = Field(default_factory=list[Any], max_length=20)
    deadline: datetime | None = None
    priority: str = Field("medium", pattern="^(low|medium|high|critical)$")

    @_field_validator("tags")
    @classmethod
    def validate_tags(cls, v):  # type: ignore[no-untyped-def]
        """Validate project tags."""
        for tag in v:
            if not isinstance(tag, str) or len(tag) > 30:
                raise ValueError("Invalid tag")
        return v

    @_field_validator("deadline")
    @classmethod
    def validate_deadline(cls, v):  # type: ignore[no-untyped-def]
        """Ensure deadline is in the future."""
        if v and v < datetime.utcnow():
            raise ValueError("Deadline must be in the future")
        return v


class WorkflowRequest(BaseModel):
    """Validated workflow creation request."""

    description: str = Field(..., min_length=10, max_length=1000)
    apps: list[str] | None = Field(None, max_length=10)
    max_steps: int = Field(10, ge=1, le=50)

    @_field_validator("apps")
    @classmethod
    def validate_apps(cls, v):  # type: ignore[no-untyped-def]
        """Validate app list[Any]."""
        if v:
            for app in v:
                if not isinstance(app, str) or len(app) > 50:
                    raise ValueError("Invalid app name")
        return v


class GAIARequest(BaseModel):
    """Base model for GAIA API requests."""

    timeout: float | None = Field(None, ge=0.1, le=60.0)
    priority: str | None = Field(None, pattern="^(low|normal|high)$")


class ReasoningValidatedRequest(GAIARequest):
    """Validated GAIA reasoning request."""

    query: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field("hybrid", pattern="^(deductive|inductive|abductive|hybrid)$")


class AnalysisValidatedRequest(GAIARequest):
    """Validated GAIA analysis request."""

    data: dict[str, Any] = Field(...)
    analysis_type: str = Field("comprehensive", max_length=50)

    @_field_validator("data")
    @classmethod
    def validate_data_size(cls, v):  # type: ignore[no-untyped-def]
        """Validate analysis data size."""
        import json

        try:
            serialized = json.dumps(v)
            if len(serialized) > 1000000:
                raise ValueError("Data too large for analysis")
        except Exception:
            raise ValueError("Data must be JSON serializable") from None
        return v


class RedisPathRequest(BaseModel):
    """Validated Redis filesystem path request."""

    path: str = Field(..., min_length=1, max_length=500)

    @_field_validator("path")
    @classmethod
    def validate_redis_path(cls, v):  # type: ignore[no-untyped-def]
        """Validate Redis filesystem path."""
        if ".." in v or v.startswith("/"):
            raise ValueError("Invalid path") from None
        if "\x00" in v:
            raise ValueError("Path cannot contain null bytes")
        return v
