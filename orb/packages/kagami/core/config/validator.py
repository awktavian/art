# pyright: reportGeneralTypeIssues=false
"""
Configuration Validation System

Validates all environment variables and configuration at startup to fail fast
if any security issues or misconfigurations are detected.
"""

import os
from dataclasses import dataclass
from typing import Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass
class ValidationError:
    """Represents a configuration validation error"""

    key: str
    message: str
    severity: str  # 'critical', 'error', 'warning'


class KagamiConfig(BaseSettings):
    """Type-safe configuration with validation"""

    # Database
    database_url: str = Field(..., env="DATABASE_URL")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")

    # Security
    jwt_secret: str = Field(..., env="JWT_SECRET", min_length=32)
    csrf_secret: str = Field(..., env="CSRF_SECRET", min_length=32)
    api_keys: str = Field(default="", env="API_KEYS")

    # External Services
    openai_api_key: str | None = Field(default=None, env="OPENAI_API_KEY")
    anthropic_api_key: str | None = Field(default=None, env="ANTHROPIC_API_KEY")
    stripe_secret_key: str | None = Field(default=None, env="STRIPE_SECRET_KEY")

    # Application
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=False, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Feature Flags
    enable_audio: bool = Field(default=True, env="ENABLE_AUDIO")
    enable_forge: bool = Field(default=True, env="ENABLE_FORGE")
    enable_training: bool = Field(default=True, env="ENABLE_TRAINING")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @field_validator("jwt_secret", "csrf_secret")
    @classmethod
    def validate_secrets(cls, v: str) -> str:
        """Ensure secrets are not default insecure values"""
        insecure_patterns = [
            "change-me",
            "changeme",
            "default",
            "test-key",
            "dev-key",
            "secret",
            "password",
            "12345",
        ]

        v_lower = v.lower()
        for pattern in insecure_patterns:
            if pattern in v_lower:
                raise ValueError(
                    f"Secret contains insecure pattern '{pattern}'. "
                    f"Must use cryptographically secure random value."
                )

        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Ensure environment is valid"""
        valid = ["development", "staging", "production", "test"]
        if v not in valid:
            raise ValueError(f"Environment must be one of {valid}, got '{v}'")
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> Self:
        """Validate production-specific settings after all fields are set."""
        # Ensure debug is disabled in production
        if self.environment == "production" and self.debug:
            raise ValueError("DEBUG must be False in production environment")

        # Validate database URL security in production
        if self.environment == "production":
            if not self.database_url.startswith(("postgresql://", "cockroachdb://")):
                raise ValueError("DATABASE_URL must use postgresql:// or cockroachdb:// scheme")
            insecure = ["localhost", "127.0.0.1", "password", "postgres"]
            for pattern in insecure:
                if pattern in self.database_url.lower():
                    raise ValueError(
                        f"DATABASE_URL contains insecure pattern '{pattern}' in production"
                    )

        return self


def validate_required_env_vars() -> list[ValidationError]:
    """Validate that all required environment variables are set[Any]"""
    errors = []

    required_vars = {
        "DATABASE_URL": "Database connection string",
        "JWT_SECRET": "JWT signing secret",  # pragma: allowlist secret
        "CSRF_SECRET": "CSRF protection secret",  # pragma: allowlist secret
    }

    for var, description in required_vars.items():
        if not os.getenv(var):
            errors.append(
                ValidationError(
                    key=var,
                    message=f"Required environment variable not set[Any]: {description}",
                    severity="critical",
                )
            )

    return errors


def validate_secret_strength(secret: str, min_length: int = 32) -> bool:
    """Validate that a secret has sufficient entropy"""
    if len(secret) < min_length:
        return False

    # Check for sufficient character diversity
    has_lower = any(c.islower() for c in secret)
    has_upper = any(c.isupper() for c in secret)
    has_digit = any(c.isdigit() for c in secret)
    has_special = any(not c.isalnum() for c in secret)

    # At least 3 of 4 character types
    return sum([has_lower, has_upper, has_digit, has_special]) >= 3


def validate_production_config() -> list[ValidationError]:
    """
    Comprehensive production configuration validation.

    Checks for:
    - Insecure default secrets
    - Missing required variables
    - Debug mode in production
    - Weak secrets
    - Insecure database URLs
    """
    errors = []
    environment = os.getenv("ENVIRONMENT", "development")

    if environment != "production":
        return errors  # Only strict validation in production

    # Check for insecure secrets
    insecure_patterns = ["change-me", "dev-key", "test-key", "secret", "password"]

    for key in ["JWT_SECRET", "CSRF_SECRET", "API_KEYS"]:
        val = os.getenv(key, "")

        # Check for insecure patterns
        for pattern in insecure_patterns:
            if pattern in val.lower():
                errors.append(
                    ValidationError(
                        key=key,
                        message=f"Contains insecure pattern '{pattern}'",
                        severity="critical",
                    )
                )

        # Check secret strength
        if key in ["JWT_SECRET", "CSRF_SECRET"] and val:
            if not validate_secret_strength(val):
                errors.append(
                    ValidationError(
                        key=key,
                        message="Secret does not meet strength requirements (32+ chars, mixed case/digits/special)",
                        severity="critical",
                    )
                )

    # Check DEBUG is disabled
    if os.getenv("DEBUG", "false").lower() in ["true", "1", "yes"]:
        errors.append(
            ValidationError(
                key="DEBUG",
                message="DEBUG mode must be disabled in production",
                severity="critical",
            )
        )

    # Check database URL
    db_url = os.getenv("DATABASE_URL", "")
    if "localhost" in db_url or "127.0.0.1" in db_url:
        errors.append(
            ValidationError(
                key="DATABASE_URL",
                message="Database URL points to localhost in production",
                severity="critical",
            )
        )

    return errors


def validate_startup() -> None:
    """
    Main startup validation function.

    Validates all configuration and fails fast if any critical issues found.

    Raises:
        RuntimeError: If any critical validation errors are found
    """
    # Check required environment variables
    errors = validate_required_env_vars()

    # Production-specific checks
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        errors.extend(validate_production_config())

    # Try to load and validate config with Pydantic
    try:
        KagamiConfig()
    except Exception as e:
        errors.append(
            ValidationError(
                key="CONFIG", message=f"Configuration validation failed: {e!s}", severity="critical"
            )
        )

    # Report errors
    if errors:
        critical_errors = [e for e in errors if e.severity == "critical"]

        if critical_errors:
            error_msg = "Critical configuration errors found:\n"
            for error in critical_errors:
                error_msg += f"  - {error.key}: {error.message}\n"

            raise RuntimeError(error_msg)

        # Log warnings for non-critical errors
        import logging

        logger = logging.getLogger(__name__)
        for error in errors:
            logger.warning(f"Configuration warning - {error.key}: {error.message}")


def get_config() -> KagamiConfig:
    """
    Get validated configuration.

    Returns:
        KagamiConfig: Type-safe configuration object
    """
    return KagamiConfig()


if __name__ == "__main__":
    # Test validation
    try:
        validate_startup()
        print("✅ Configuration validation passed")
    except RuntimeError as e:
        print(f"❌ Configuration validation failed:\n{e}")
        exit(1)
