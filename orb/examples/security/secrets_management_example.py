#!/usr/bin/env python3
"""Example: Comprehensive secrets management usage.

This example demonstrates:
1. Creating a secrets manager
2. Storing and retrieving secrets
3. Secret rotation
4. Audit logging
5. Integration with config system
"""

import asyncio
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def basic_usage_example():
    """Basic secrets management."""
    print("\n" + "=" * 60)
    print("BASIC USAGE EXAMPLE")
    print("=" * 60 + "\n")

    from kagami.core.security import (
        create_secrets_manager,
        SecretBackendType,
    )

    # Create secrets manager with local backend
    manager = create_secrets_manager(
        backend_type=SecretBackendType.LOCAL_ENCRYPTED,
        config={
            "storage_path": str(Path.home() / ".kagami" / "secrets" / "example.enc"),
            "master_key_path": str(Path.home() / ".kagami" / "secrets" / "example.key"),
            "auto_generate_key": True,
        },
        enable_cache=True,
        cache_ttl_seconds=300,
    )

    # Store a secret
    print("1. Storing secret...")
    await manager.set_secret(
        name="API_KEY",
        value="sk_live_1234567890abcdef",
        user="admin",
        rotation_enabled=True,
        rotation_days=90,
    )
    print("   ✓ Secret stored\n")

    # Retrieve a secret
    print("2. Retrieving secret...")
    api_key = await manager.get_secret("API_KEY", user="app")
    print(f"   ✓ Retrieved: {api_key[:10]}...\n")

    # List all secrets
    print("3. Listing all secrets...")
    secrets = await manager.list_secrets()
    print(f"   ✓ Found {len(secrets)} secrets: {secrets}\n")


async def rotation_example():
    """Secret rotation example."""
    print("\n" + "=" * 60)
    print("ROTATION EXAMPLE")
    print("=" * 60 + "\n")

    from kagami.core.security import (
        create_secrets_manager,
        SecretBackendType,
        SecretRotator,
        RotationPolicy,
    )

    # Create manager
    manager = create_secrets_manager(
        backend_type=SecretBackendType.LOCAL_ENCRYPTED,
        config={
            "storage_path": str(Path.home() / ".kagami" / "secrets" / "example.enc"),
            "master_key_path": str(Path.home() / ".kagami" / "secrets" / "example.key"),
            "auto_generate_key": True,
        },
    )

    # Create initial secret
    print("1. Creating initial secret...")
    await manager.set_secret(
        name="JWT_SECRET",
        value="initial_jwt_secret_12345",
        user="admin",
    )
    print("   ✓ Secret created\n")

    # Set up rotation
    print("2. Setting up rotation policy...")
    policy = RotationPolicy(
        secret_name="JWT_SECRET",
        rotation_days=90,
        grace_period_seconds=300,
        auto_generate=True,
        generation_length=64,
    )

    rotator = SecretRotator(
        secrets_manager=manager,
        policies=[policy],
    )
    print("   ✓ Rotation policy configured\n")

    # Rotate secret
    print("3. Rotating secret...")
    event = await rotator.rotate_secret("JWT_SECRET", user="admin")

    if event.status.value == "success":
        print(f"   ✓ Rotation successful: {event.old_version} → {event.new_version}\n")
    else:
        print(f"   ✗ Rotation failed: {event.error}\n")

    # Get rotation summary
    print("4. Rotation summary:")
    summary = rotator.get_rotation_summary()
    print(f"   Total rotations: {summary['total_rotations']}")
    print(f"   Successful: {summary['successful']}")
    print(f"   Success rate: {summary['success_rate']:.1%}\n")


async def audit_logging_example():
    """Audit logging example."""
    print("\n" + "=" * 60)
    print("AUDIT LOGGING EXAMPLE")
    print("=" * 60 + "\n")

    from kagami.core.security import create_secrets_manager, SecretBackendType
    from datetime import datetime, timedelta

    # Create manager
    manager = create_secrets_manager(
        backend_type=SecretBackendType.LOCAL_ENCRYPTED,
        config={
            "storage_path": str(Path.home() / ".kagami" / "secrets" / "example.enc"),
            "master_key_path": str(Path.home() / ".kagami" / "secrets" / "example.key"),
            "auto_generate_key": True,
        },
    )

    # Perform various operations
    print("1. Performing operations...")
    await manager.set_secret("SECRET1", "value_123456789", user="alice")
    await manager.get_secret("SECRET1", user="bob")
    await manager.set_secret("SECRET2", "value_987654321", user="charlie")
    print("   ✓ Operations complete\n")

    # Get audit log
    print("2. Audit log entries:")
    audit_log = manager.get_audit_log(
        start_time=datetime.utcnow() - timedelta(minutes=5)
    )

    for entry in audit_log[-5:]:  # Last 5 entries
        print(f"   [{entry.timestamp}] {entry.user}: {entry.action} on {entry.secret_name}")

    print()


async def config_integration_example():
    """Config integration example."""
    print("\n" + "=" * 60)
    print("CONFIG INTEGRATION EXAMPLE")
    print("=" * 60 + "\n")

    from kagami.core.security.config_integration import SecretConfigProvider
    from kagami.core.security import create_secrets_manager, SecretBackendType
    import os

    # Set some environment variables for demo
    os.environ["TEST_API_KEY"] = "env_api_key_123"
    os.environ["TEST_DB_PASS"] = "env_db_pass_456"

    # Create manager
    manager = create_secrets_manager(
        backend_type=SecretBackendType.LOCAL_ENCRYPTED,
        config={
            "storage_path": str(Path.home() / ".kagami" / "secrets" / "example.enc"),
            "master_key_path": str(Path.home() / ".kagami" / "secrets" / "example.key"),
            "auto_generate_key": True,
        },
    )

    # Create config provider
    provider = SecretConfigProvider(
        secrets_manager=manager,
        enable_fallback=True,
    )

    # Get from environment (fallback)
    print("1. Getting from environment (fallback)...")
    value = await provider.get("TEST_API_KEY")
    print(f"   TEST_API_KEY: {value}\n")

    # Migrate to secrets manager
    print("2. Migrating secrets from environment...")
    results = await provider.migrate_from_env(["TEST_API_KEY", "TEST_DB_PASS"])

    for key, success in results.items():
        status = "✓" if success else "✗"
        print(f"   {status} {key}")

    print()

    # Now get from secrets manager
    print("3. Getting from secrets manager...")
    value = await provider.get("TEST_API_KEY")
    print(f"   TEST_API_KEY: {value}\n")


async def secret_generation_example():
    """Secret generation example."""
    print("\n" + "=" * 60)
    print("SECRET GENERATION EXAMPLE")
    print("=" * 60 + "\n")

    from kagami.core.security import (
        generate_secret,
        validate_secret_strength,
    )

    # Generate strong secret
    print("1. Generating strong secret...")
    secret = generate_secret(length=32, use_symbols=True)
    print(f"   Generated: {secret}\n")

    # Validate strength
    print("2. Validating secret strength...")
    is_valid, error = validate_secret_strength(secret, min_length=16)

    if is_valid:
        print("   ✓ Secret is strong\n")
    else:
        print(f"   ✗ Validation failed: {error}\n")

    # Test weak secret
    print("3. Testing weak secret...")
    weak_secret = "password123"
    is_valid, error = validate_secret_strength(weak_secret)

    if not is_valid:
        print(f"   ✓ Correctly identified as weak: {error}\n")


async def main():
    """Run all examples."""
    print("\n" + "=" * 60)
    print("KAGAMI SECRETS MANAGEMENT EXAMPLES")
    print("=" * 60)

    try:
        # Run examples
        await basic_usage_example()
        await rotation_example()
        await audit_logging_example()
        await config_integration_example()
        await secret_generation_example()

        print("\n" + "=" * 60)
        print("ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print("=" * 60 + "\n")

    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
