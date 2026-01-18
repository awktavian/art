#!/usr/bin/env python3
"""Validate KagamiOS secrets are properly configured.

Usage:
    ENVIRONMENT=production python scripts/operations/validate_secrets.py

Security validation:
- Checks for weak/placeholder secrets
- Validates minimum entropy requirements
- Enforces production secret policies
- Prevents common misconfigurations

Exit codes:
    0: All secrets valid
    1: Validation failed (missing or weak secrets)
    2: Configuration error
"""

from __future__ import annotations

import os
import re
import sys


REQUIRED_SECRETS = {
    "production": [
        "JWT_SECRET",
        "CSRF_SECRET",
        "KAGAMI_CACHE_SECRET",
        "REDIS_PASSWORD",
        "KAGAMI_ENCRYPTION_KEYS",
        "DATABASE_URL",
        "REDIS_URL",
        "API_KEYS",
    ],
    "staging": [
        "JWT_SECRET",
        "CSRF_SECRET",
        "DATABASE_URL",
        "REDIS_URL",
    ],
}

# Minimum lengths (in characters) for security
MIN_LENGTHS = {
    "JWT_SECRET": 32,
    "CSRF_SECRET": 24,
    "KAGAMI_CACHE_SECRET": 24,
    "REDIS_PASSWORD": 16,
    "KAGAMI_ENCRYPTION_KEYS": 40,
    "API_KEYS": 16,
}

# Weak patterns that should never appear in production
WEAK_PATTERNS = [
    r"changeme",
    r"change.me",
    r"change-me",
    r"test",
    r"development",
    r"localhost",
    r"12345",
    r"password",
    r"secret",
    r"admin",
    r"root",
    r"default",
]


def validate_secret_strength(name: str, value: str) -> tuple[bool, str]:
    """Validate secret meets minimum strength requirements.

    Args:
        name: Secret name
        value: Secret value

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value:
        return False, f"{name} is empty"

    # Check for weak patterns
    value_lower = value.lower()
    for pattern in WEAK_PATTERNS:
        if re.search(pattern, value_lower):
            return False, f"{name} contains weak pattern: '{pattern}'"

    # Check minimum length
    if name in MIN_LENGTHS:
        min_len = MIN_LENGTHS[name]
        if len(value) < min_len:
            return False, f"{name} is too short (min {min_len} chars, got {len(value)})"

    # Special validation for DATABASE_URL
    if name == "DATABASE_URL":
        if not _validate_database_url(value):
            return (
                False,
                f"{name} has insecure configuration (missing authentication or using default port)",
            )

    # Special validation for REDIS_URL
    if name == "REDIS_URL":
        if not _validate_redis_url(value):
            return (
                False,
                f"{name} has insecure configuration (missing password or using default config)",
            )

    # Check entropy (basic heuristic)
    if not _has_sufficient_entropy(value):
        return False, f"{name} has insufficient entropy (appears non-random)"

    return True, "OK"


def _validate_database_url(url: str) -> bool:
    """Validate database URL security.

    Args:
        url: Database connection URL

    Returns:
        True if URL is secure
    """
    url_lower = url.lower()

    # Allow test/development SQLite
    if url_lower.startswith("sqlite://"):
        return True

    # Production databases must have authentication
    if url_lower.startswith("cockroachdb://") or url_lower.startswith("postgresql://"):
        # Check for username and password
        if "@" not in url:
            return False

        # Check for sslmode=disable in production (warning, not failure)
        if "sslmode=disable" in url_lower:
            print("⚠️  WARNING: DATABASE_URL has sslmode=disable (insecure)", file=sys.stderr)

        return True

    return False


def _validate_redis_url(url: str) -> bool:
    """Validate Redis URL security.

    Args:
        url: Redis connection URL

    Returns:
        True if URL is secure
    """
    url_lower = url.lower()

    # Allow localhost for development
    if "localhost" in url_lower or "127.0.0.1" in url_lower:
        return True

    # Production Redis should have password
    if not url_lower.startswith("redis://:") and not url_lower.startswith("rediss://"):
        print("⚠️  WARNING: REDIS_URL missing password authentication", file=sys.stderr)

    # Prefer TLS (rediss://)
    if url_lower.startswith("redis://") and not (
        "localhost" in url_lower or "127.0.0.1" in url_lower
    ):
        print("⚠️  WARNING: REDIS_URL not using TLS (use rediss://)", file=sys.stderr)

    return True


def _has_sufficient_entropy(value: str) -> bool:
    """Check if value has sufficient entropy (basic heuristic).

    Args:
        value: Secret value to check

    Returns:
        True if value appears to have sufficient entropy
    """
    if len(value) < 8:
        return False

    # Count unique characters
    unique_chars = len(set(value))
    if unique_chars < len(value) * 0.4:  # At least 40% unique characters
        return False

    # Check for character diversity
    has_lower = any(c.islower() for c in value)
    has_upper = any(c.isupper() for c in value)
    has_digit = any(c.isdigit() for c in value)
    has_special = any(not c.isalnum() for c in value)

    # At least 2 character types
    char_types = sum([has_lower, has_upper, has_digit, has_special])
    if char_types < 2:
        return False

    return True


def main() -> None:
    """Validate all required secrets for the current environment."""
    environment = os.getenv("ENVIRONMENT", "development").lower()

    if environment not in ("production", "staging"):
        print(f"✅ Skipping validation (ENVIRONMENT={environment})")
        print("   Secret validation only enforced in production and staging")
        sys.exit(0)

    required = REQUIRED_SECRETS.get(environment, [])

    print(f"🔍 Validating secrets for {environment} environment...")
    print(f"   Required secrets: {len(required)}")
    print()

    errors: list[str] = []
    warnings: list[str] = []

    for secret_name in required:
        value = os.getenv(secret_name)

        if not value:
            errors.append(f"❌ {secret_name}: NOT SET")
            continue

        valid, message = validate_secret_strength(secret_name, value)
        if not valid:
            errors.append(f"❌ {secret_name}: {message}")
        else:
            print(f"✅ {secret_name}: OK")

    print()

    # Check for TLS configuration
    if environment == "production":
        _check_tls_config(errors, warnings)

    if warnings:
        print("⚠️  WARNINGS:")
        for warning in warnings:
            print(f"   {warning}")
        print()

    if errors:
        print("🔴 VALIDATION FAILED:")
        for error in errors:
            print(f"   {error}")
        print()
        print("💡 Generate secure secrets with:")
        print(f"   python scripts/operations/generate_secrets.py --env {environment}")
        print()
        print("📖 See docs/operations/SECRET_ROTATION.md for secret management best practices")
        sys.exit(1)
    else:
        print(f"✅ All {len(required)} secrets validated")
        if warnings:
            print(f"⚠️  {len(warnings)} warnings (see above)")
            sys.exit(0)
        sys.exit(0)


def _check_tls_config(errors: list[str], warnings: list[str]) -> None:
    """Check TLS configuration for production.

    Args:
        errors: List to append errors to
        warnings: List to append warnings to
    """
    # Check etcd TLS
    etcd_endpoints = os.getenv("ETCD_ENDPOINTS", "")
    if etcd_endpoints and not etcd_endpoints.startswith("https://"):
        if "localhost" not in etcd_endpoints and "127.0.0.1" not in etcd_endpoints:
            warnings.append("ETCD_ENDPOINTS not using TLS (use https://)")

    etcd_ca = os.getenv("ETCD_CA_CERT")
    if not etcd_ca and "localhost" not in etcd_endpoints:
        warnings.append("ETCD_CA_CERT not set (TLS disabled)")

    # Check Redis TLS
    redis_url = os.getenv("REDIS_URL", "")
    if redis_url and not redis_url.startswith("rediss://"):
        if "localhost" not in redis_url and "127.0.0.1" not in redis_url:
            warnings.append("REDIS_URL not using TLS (use rediss://)")

    # Check database TLS
    db_url = os.getenv("DATABASE_URL", "")
    if "sslmode=disable" in db_url.lower():
        if "localhost" not in db_url and "127.0.0.1" not in db_url:
            warnings.append("DATABASE_URL has sslmode=disable (insecure)")


if __name__ == "__main__":
    main()
