"""Input validation middleware for K os API endpoints.

This module provides comprehensive input validation to prevent
common security vulnerabilities like path traversal, XSS, and SQL injection.
"""

import os
import re
from pathlib import Path
from typing import Any

try:
    import bleach as _bleach_module

    bleach: Any = _bleach_module
except Exception:
    bleach = None
    try:
        import logging as _logging

        _logging.getLogger(__name__).warning(
            "bleach not installed; HTML sanitization degraded (script tags removed only)"
        )
    except Exception:
        pass
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class InputValidator:
    """Comprehensive input validation for API requests."""

    PATH_TRAVERSAL_PATTERN = re.compile("\\.\\.[\\\\/]")
    SQL_INJECTION_PATTERN = re.compile(
        "(\\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|CREATE|ALTER|EXEC|EXECUTE)\\b|--|;|'|\\\"|`)",
        re.IGNORECASE,
    )
    SCRIPT_TAG_PATTERN = re.compile("<script[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
    MAX_FILE_SIZE = 10 * 1024 * 1024
    ALLOWED_FILE_EXTENSIONS = {
        ".txt",
        ".md",
        ".json",
        ".yaml",
        ".yml",
        ".csv",
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".css",
        ".html",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".pdf",
    }

    @staticmethod
    def validate_path(path: str, base_dir: Path | None = None) -> str:
        """Validate file path to prevent traversal attacks.

        SECURITY: This method:
        1. Resolves all symlinks to canonical paths
        2. Blocks symlinks that escape allowed directories
        3. Validates against allowed directory whitelist

        Args:
            path: File path to validate
            base_dir: Optional base directory to restrict paths to

        Returns:
            Sanitized and resolved path

        Raises:
            HTTPException: If path is invalid or outside allowed directories
        """
        if not path:
            raise HTTPException(status_code=400, detail="Path cannot be empty")

        try:
            import tempfile

            path_obj = Path(path)
            # Resolve FIRST to canonicalize and eliminate traversal attempts
            resolved = path_obj.resolve()
            cwd = Path.cwd()

            # SECURITY: Block symlinks that could escape allowed directories
            if path_obj.exists() and path_obj.is_symlink():
                # Check if symlink target is within allowed directories
                symlink_target = resolved
                allowed_dirs = [
                    Path.home() / ".kagami",
                    Path(tempfile.gettempdir()),
                    cwd,
                ]
                if base_dir:
                    allowed_dirs.append(Path(base_dir).resolve())

                if not any(symlink_target.is_relative_to(allowed) for allowed in allowed_dirs):
                    raise HTTPException(
                        status_code=400, detail="Symlink points outside allowed directories"
                    )

            # If base_dir is specified, validate strictly against it
            if base_dir:
                base_resolved = Path(base_dir).resolve()
                if not resolved.is_relative_to(base_resolved):
                    raise HTTPException(
                        status_code=400, detail="Path is outside the allowed base directory"
                    )
                return str(resolved)

            # For absolute paths, check against allowed directories
            if path_obj.is_absolute():
                allowed_dirs = [
                    Path.home() / ".kagami",
                    Path(tempfile.gettempdir()),
                    cwd,
                ]
                # Check resolved path against allowed directories
                # This prevents all traversal attacks since resolve() canonicalizes
                if not any(resolved.is_relative_to(allowed) for allowed in allowed_dirs):
                    raise HTTPException(
                        status_code=400, detail="Access to this path is not allowed"
                    )

            # Return the resolved (canonical) path, not the original
            return str(resolved)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid path: {e!s}") from None

    @staticmethod
    def validate_filename(filename: str) -> str:
        """Validate filename for safety.

        Args:
            filename: Filename to validate

        Returns:
            Sanitized filename

        Raises:
            HTTPException: If filename is invalid
        """
        if not filename:
            raise HTTPException(status_code=400, detail="Filename cannot be empty")
        filename = os.path.basename(filename)
        if "\x00" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename: Null byte detected")
        ext = Path(filename).suffix.lower()
        if ext and ext not in InputValidator.ALLOWED_FILE_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(InputValidator.ALLOWED_FILE_EXTENSIONS)}",
            )
        return filename

    @staticmethod
    def sanitize_html(content: str) -> str:
        """Sanitize HTML content to prevent XSS.

        Args:
            content: HTML content to sanitize

        Returns:
            Sanitized HTML
        """
        content = InputValidator.SCRIPT_TAG_PATTERN.sub("", content)
        allowed_tags = [
            "p",
            "br",
            "span",
            "div",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "strong",
            "em",
            "u",
            "code",
            "pre",
            "blockquote",
            "ul",
            "ol",
            "li",
            "a",
            "img",
        ]
        allowed_attributes = {"a": ["href", "title"], "img": ["src", "alt", "width", "height"]}
        if bleach is None:
            return content
        return str(
            bleach.clean(content, tags=allowed_tags, attributes=allowed_attributes, strip=True)
        )

    @staticmethod
    def validate_query_params(params: dict[str, Any]) -> dict[str, Any]:
        """Validate query parameters for SQL injection.

        Args:
            params: Query parameters to validate

        Returns:
            Validated parameters

        Raises:
            HTTPException: If parameters contain SQL injection attempts
        """
        for key, value in params.items():
            if isinstance(value, str):
                if InputValidator.SQL_INJECTION_PATTERN.search(value):
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid parameter '{key}': Potential SQL injection detected",
                    )
        return params

    @staticmethod
    def validate_json_data(data: dict[str, Any], max_depth: int = 10) -> dict[str, Any]:
        """Validate JSON data for safety.

        Args:
            data: JSON data to validate
            max_depth: Maximum nesting depth allowed

        Returns:
            Validated data

        Raises:
            HTTPException: If data is invalid
        """

        def check_depth(obj: Any, current_depth: int = 0) -> None:
            if current_depth > max_depth:
                raise HTTPException(status_code=400, detail="JSON nesting too deep")
            if isinstance(obj, dict):
                for value in obj.values():
                    check_depth(value, current_depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    check_depth(item, current_depth + 1)

        check_depth(data)
        return data

    @staticmethod
    def validate_file_size(size: int) -> None:
        """Validate file size.

        Args:
            size: File size in bytes

        Raises:
            HTTPException: If file is too large
        """
        if size > InputValidator.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size: {InputValidator.MAX_FILE_SIZE // 1024 // 1024}MB",
            )


async def input_validation_middleware(request: Request, call_next) -> Any:  # type: ignore[no-untyped-def]
    """Middleware to validate all incoming requests.

    Args:
        request: FastAPI request object
        call_next: Next middleware in chain

    Returns:
        Response from next middleware or error response
    """
    if request.url.path in ["/health", "/docs", "/openapi.json", "/redoc"]:
        return await call_next(request)
    try:
        hot_json_only = {"/api/command/parse", "/api/command/execute"}
        if request.url.path not in hot_json_only and request.query_params:
            InputValidator.validate_query_params(dict(request.query_params))
        ct = request.headers.get("content-type", "").lower()
        if "application/json" in ct:
            try:
                length = int(request.headers.get("content-length", "0"))
                if length > 1000000:
                    return JSONResponse(status_code=413, content={"detail": "JSON too large"})
            except Exception:
                pass
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    except Exception:
        return JSONResponse(
            status_code=500, content={"detail": "Internal server error during validation"}
        )
    response = await call_next(request)
    return response
