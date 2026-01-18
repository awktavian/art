#!/usr/bin/env python3
"""Secrets migration wizard.

Migrates secrets from legacy sources to the unified secrets backend:
- .env files
- macOS Keychain (direct)
- Legacy JSON files (spotify_credentials.json)

Usage:
    python -m scripts.security.migrate_all_secrets
    python scripts/security/migrate_all_secrets.py

Created: December 31, 2025
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Add packages to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "packages"))

from kagami.core.security import get_secret, set_secret, list_secrets, get_secrets_backend


# Known secret keys that should be migrated
ENV_SECRETS = [
    # Application
    "JWT_SECRET",
    "CSRF_SECRET",
    "KAGAMI_CACHE_SECRET",
    "KAGAMI_ENCRYPTION_KEYS",
    # API Keys
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "COMPOSIO_API_KEY",
    "OPENWEATHERMAP_API_KEY",
    "PICOVOICE_ACCESS_KEY",
    "OPENAI_API_KEY",
    # Database
    "DATABASE_URL",
    "DATABASE_PASSWORD",
    "REDIS_URL",
    "REDIS_PASSWORD",
]

KEYCHAIN_SECRETS = [
    # UniFi
    "unifi_host",
    "unifi_username",
    "unifi_password",
    "unifi_local_username",
    "unifi_local_password",
    # Control4
    "control4_host",
    "control4_username",
    "control4_password",
    "control4_bearer_token",
    "control4_controller_name",
    # Eight Sleep
    "eight_sleep_email",
    "eight_sleep_password",
    # August
    "august_email",
    "august_password",
    "august_install_id",
    "august_access_token",
    # Tesla
    "tesla_access_token",
    "tesla_refresh_token",
    "tesla_client_id",
    "tesla_client_secret",
    # DSC
    "dsc_host",
    "dsc_port",
    "dsc_password",
    "dsc_code",
    # Other
    "denon_host",
    "lg_tv_host",
    "lg_tv_client_key",
    "samsung_tv_host",
    "samsung_tv_token",
]

LEGACY_FILES = [
    (Path.home() / ".kagami" / "spotify_credentials.json", "spotify_stored_credentials"),
]


def print_header(title: str) -> None:
    """Print a section header."""
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def migrate_from_env() -> dict[str, bool]:
    """Migrate secrets from environment variables."""
    print_header("MIGRATING FROM ENVIRONMENT VARIABLES")

    results = {}

    for key in ENV_SECRETS:
        value = os.getenv(key)
        if value:
            # Normalize key (lowercase)
            normalized = key.lower()

            # Check if already exists
            existing = get_secret(normalized)
            if existing:
                print(f"  ⏭️  {key} → already exists (skipping)")
                results[key] = True
                continue

            # Migrate
            if set_secret(normalized, value):
                print(f"  ✅ {key} → migrated")
                results[key] = True
            else:
                print(f"  ❌ {key} → failed")
                results[key] = False
        else:
            print(f"  ⏭️  {key} → not set in environment")
            results[key] = False

    return results


def migrate_from_keychain() -> dict[str, bool]:
    """Migrate secrets from macOS Keychain (if on macOS)."""
    print_header("MIGRATING FROM MACOS KEYCHAIN")

    if sys.platform != "darwin":
        print("  ⏭️  Not on macOS, skipping keychain migration")
        return {}

    results = {}

    for key in KEYCHAIN_SECRETS:
        try:
            # Try to get from keychain
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "kagami", "-a", key, "-w"],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                value = result.stdout.strip()
                if value:
                    # Check if already exists in unified backend
                    existing = get_secret(key)
                    if existing:
                        print(f"  ⏭️  {key} → already exists (skipping)")
                        results[key] = True
                        continue

                    # Migrate
                    if set_secret(key, value):
                        print(f"  ✅ {key} → migrated")
                        results[key] = True
                    else:
                        print(f"  ❌ {key} → failed")
                        results[key] = False
            else:
                print(f"  ⏭️  {key} → not in keychain")
                results[key] = False

        except FileNotFoundError:
            print("  ❌ 'security' command not found")
            break
        except Exception as e:
            print(f"  ❌ {key} → error: {e}")
            results[key] = False

    return results


def migrate_from_files() -> dict[str, bool]:
    """Migrate secrets from legacy JSON files."""
    print_header("MIGRATING FROM LEGACY FILES")

    results = {}

    for file_path, secret_key in LEGACY_FILES:
        if file_path.exists():
            try:
                with open(file_path) as f:
                    data = json.load(f)

                # Handle spotify_credentials.json specifically
                if "stored" in data:
                    value = data["stored"]
                else:
                    value = json.dumps(data)

                # Check if already exists
                existing = get_secret(secret_key)
                if existing:
                    print(f"  ⏭️  {file_path.name} → already migrated")
                    results[str(file_path)] = True
                    continue

                # Migrate
                if set_secret(secret_key, value):
                    print(f"  ✅ {file_path.name} → migrated to {secret_key}")
                    # Offer to delete legacy file
                    delete = input("     Delete legacy file? [y/N]: ").lower()
                    if delete == "y":
                        file_path.unlink()
                        print(f"     Deleted {file_path}")
                    results[str(file_path)] = True
                else:
                    print(f"  ❌ {file_path.name} → failed")
                    results[str(file_path)] = False

            except Exception as e:
                print(f"  ❌ {file_path.name} → error: {e}")
                results[str(file_path)] = False
        else:
            print(f"  ⏭️  {file_path.name} → not found")
            results[str(file_path)] = False

    return results


def verify_migration() -> None:
    """Verify all secrets are accessible."""
    print_header("VERIFICATION")

    backend = get_secrets_backend()
    print(f"\nBackend: {backend.backend_type}")

    stored = list_secrets()
    print(f"\nTotal secrets stored: {len(stored)}")

    if stored:
        print("\nStored secrets:")
        for key in sorted(stored):
            print(f"  ✅ {key}")
    else:
        print("\n  (no secrets stored)")


def main() -> None:
    """Run migration wizard."""
    print_header("KAGAMI SECRETS MIGRATION WIZARD")

    backend = get_secrets_backend()
    print(f"\nTarget backend: {backend.backend_type}")
    print("\nThis wizard will migrate secrets from:")
    print("  • Environment variables (.env)")
    print("  • macOS Keychain (if on macOS)")
    print("  • Legacy JSON files")
    print("\nExisting secrets will NOT be overwritten.")

    proceed = input("\nProceed? [Y/n]: ").lower()
    if proceed == "n":
        print("Aborted.")
        return

    # Run migrations
    env_results = migrate_from_env()
    keychain_results = migrate_from_keychain()
    file_results = migrate_from_files()

    # Summary
    print_header("MIGRATION SUMMARY")

    total_migrated = sum(
        1 for r in [*env_results.values(), *keychain_results.values(), *file_results.values()] if r
    )
    total_skipped = len(env_results) + len(keychain_results) + len(file_results) - total_migrated

    print(f"\n  Migrated: {total_migrated}")
    print(f"  Skipped/Failed: {total_skipped}")

    # Verify
    verify_migration()

    print("\n✅ Migration complete!")
    print("\nNext steps:")
    print("  1. Test your integrations")
    print("  2. Remove credentials from .env file (optional)")
    print("  3. Delete legacy files if prompted above")


if __name__ == "__main__":
    main()
