#!/usr/bin/env python3
"""Unified secrets setup wizard.

Cross-platform interactive setup for storing Kagami credentials.
Works on macOS (Keychain), Linux (LocalEncrypted), Windows (LocalEncrypted), and CI (Environment).

Usage:
    python -m scripts.security.setup_secrets
    python scripts/security/setup_secrets.py

Created: December 31, 2025
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from kagami.core.security import get_secret, set_secret, get_secrets_backend, list_secrets


# Credential definitions: (key, prompt, is_secret, category)
CREDENTIALS = [
    # Smart Home - UniFi
    ("unifi_host", "UniFi Controller IP (e.g., 192.168.1.1)", False, "UniFi"),
    ("unifi_local_username", "UniFi Local Admin Username", False, "UniFi"),
    ("unifi_local_password", "UniFi Local Admin Password", True, "UniFi"),
    # Smart Home - Control4
    ("control4_host", "Control4 Director IP (e.g., 192.168.1.2)", False, "Control4"),
    ("control4_username", "Control4 Username (email)", False, "Control4"),
    ("control4_password", "Control4 Password", True, "Control4"),
    # Smart Home - Eight Sleep
    ("eight_sleep_email", "Eight Sleep Email", False, "Eight Sleep"),
    ("eight_sleep_password", "Eight Sleep Password", True, "Eight Sleep"),
    # Smart Home - August
    ("august_email", "August Lock Email", False, "August"),
    ("august_password", "August Lock Password", True, "August"),
    # Smart Home - Tesla
    ("tesla_client_id", "Tesla API Client ID", False, "Tesla"),
    ("tesla_client_secret", "Tesla API Client Secret", True, "Tesla"),
    # Smart Home - DSC Security
    ("dsc_code", "DSC Panel Arm/Disarm Code", True, "DSC"),
    # API Keys
    ("anthropic_api_key", "Anthropic API Key", True, "API Keys"),
    ("openai_api_key", "OpenAI API Key", True, "API Keys"),
    ("composio_api_key", "Composio API Key", True, "API Keys"),
    # Application Secrets
    ("jwt_secret", "JWT Secret (64+ chars recommended)", True, "Application"),
    ("csrf_secret", "CSRF Secret (64+ chars recommended)", True, "Application"),
]


def print_header(title: str) -> None:
    """Print a section header."""
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def print_category(category: str) -> None:
    """Print a category header."""
    print()
    print(f"─── {category} ───")


def setup_interactive() -> None:
    """Run interactive setup wizard."""
    print_header("KAGAMI SECRETS SETUP WIZARD")

    backend = get_secrets_backend()
    print(f"\nBackend: {backend.backend_type}")
    print("Credentials will be stored securely.")
    print("Press Enter to skip any credential.\n")

    current_category = None
    secrets_set = 0
    secrets_skipped = 0

    for key, prompt, is_secret, category in CREDENTIALS:
        # Print category header on change
        if category != current_category:
            print_category(category)
            current_category = category

        # Check existing value
        current = get_secret(key)
        status = "✓ stored" if current else "not set"

        # Get input
        if is_secret:
            value = getpass.getpass(f"  {prompt} [{status}]: ")
        else:
            value = input(f"  {prompt} [{status}]: ")

        # Store or skip
        if value:
            if set_secret(key, value):
                print("    ✅ Saved")
                secrets_set += 1
            else:
                print("    ❌ Failed to save")
        elif current:
            print("    ⏭️  Keeping existing")
            secrets_skipped += 1
        else:
            secrets_skipped += 1

    # Summary
    print_header("SUMMARY")
    print(f"\n  Secrets set: {secrets_set}")
    print(f"  Skipped: {secrets_skipped}")

    # List all stored secrets
    print("\nSTORED SECRETS:")
    stored = list_secrets()
    for key in sorted(stored):
        print(f"  ✅ {key}")

    if not stored:
        print("  (none)")

    print("\n✅ Setup complete!")
    print("\nUsage in code:")
    print("  from kagami.core.security import get_secret")
    print('  password = get_secret("unifi_local_password")')


def list_stored() -> None:
    """List all stored secrets."""
    print_header("STORED SECRETS")

    stored = list_secrets()
    backend = get_secrets_backend()
    print(f"\nBackend: {backend.backend_type}")
    print()

    if stored:
        for key in sorted(stored):
            print(f"  ✅ {key}")
    else:
        print("  (no secrets stored)")


def get_single(key: str) -> None:
    """Get a single secret value."""
    value = get_secret(key)
    if value:
        print(value)
    else:
        print(f"Not found: {key}", file=sys.stderr)
        sys.exit(1)


def set_single(key: str, value: str) -> None:
    """Set a single secret."""
    if set_secret(key, value):
        print(f"✅ Stored {key}")
    else:
        print(f"❌ Failed to store {key}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) == 1 or sys.argv[1] == "setup":
        setup_interactive()
    elif sys.argv[1] == "list":
        list_stored()
    elif sys.argv[1] == "get" and len(sys.argv) >= 3:
        get_single(sys.argv[2])
    elif sys.argv[1] == "set" and len(sys.argv) >= 4:
        set_single(sys.argv[2], sys.argv[3])
    else:
        print("Usage:")
        print("  python -m scripts.security.setup_secrets setup  # Interactive setup")
        print("  python -m scripts.security.setup_secrets list   # List stored secrets")
        print("  python -m scripts.security.setup_secrets get <key>")
        print("  python -m scripts.security.setup_secrets set <key> <value>")


if __name__ == "__main__":
    main()
