#!/usr/bin/env python3
"""Generate KAGAMI_CACHE_SECRET for signed serialization.

Creates a cryptographically secure 256-bit secret key for HMAC signatures.

Usage:
    python scripts/security/generate_cache_secret.py

Output:
    - Prints secret key to stdout (for .env file)
    - Prints shell export command (for temporary use)
    - Validates key format

Created: December 20, 2025
Colony: Forge (e₂) - Security tooling
"""

from __future__ import annotations

import secrets
import sys


def generate_secret_key() -> str:
    """Generate cryptographically secure 256-bit key.

    Returns:
        64-character hex string (32 bytes)
    """
    return secrets.token_hex(32)


def validate_secret_key(key_hex: str) -> bool:
    """Validate secret key format.

    Args:
        key_hex: Hex string to validate

    Returns:
        True if valid format
    """
    try:
        key_bytes = bytes.fromhex(key_hex)
        return len(key_bytes) >= 32
    except ValueError:
        return False


def main() -> int:
    """Generate and display secret key."""
    print("=" * 80)
    print("KAGAMI CACHE SECRET KEY GENERATOR")
    print("=" * 80)
    print()

    # Generate key
    secret_key = generate_secret_key()

    # Validate
    if not validate_secret_key(secret_key):
        print("ERROR: Generated key failed validation", file=sys.stderr)
        return 1

    # Display
    print("✓ Generated 256-bit (32-byte) secret key:")
    print()
    print(f"    {secret_key}")
    print()

    print("=" * 80)
    print("SETUP INSTRUCTIONS")
    print("=" * 80)
    print()

    print("1. Add to .env file (development):")
    print()
    print(f"    export KAGAMI_CACHE_SECRET={secret_key}")
    print()

    print("2. Add to systemd service (production):")
    print()
    print("    [Service]")
    print(f'    Environment="KAGAMI_CACHE_SECRET={secret_key}"')
    print()

    print("3. Temporary shell export:")
    print()
    print(f"    export KAGAMI_CACHE_SECRET={secret_key}")
    print()

    print("4. Docker Compose:")
    print()
    print("    environment:")
    print(f"      - KAGAMI_CACHE_SECRET={secret_key}")
    print()

    print("=" * 80)
    print("SECURITY NOTES")
    print("=" * 80)
    print()
    print("⚠ NEVER commit this key to version control (.gitignore .env)")
    print("⚠ Store securely (password manager, secrets vault)")
    print("⚠ Rotate periodically (every 90 days recommended)")
    print("⚠ If compromised, regenerate and purge all caches")
    print()

    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)
    print()
    print("Verify setup:")
    print()
    print(
        '    python -c "from kagami.core.security.signed_serialization import _get_secret_key; '
        "_get_secret_key(); print('Secret key configured')\""
    )
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
