#!/usr/bin/env python3
"""Manual secret rotation script.

Usage:
    python scripts/security/rotate_secrets.py --name JWT_SECRET
    python scripts/security/rotate_secrets.py --all
    python scripts/security/rotate_secrets.py --check
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kagami.core.security.rotation import (
    SecretRotator,
    create_default_policies,
)
from kagami.core.security.secrets_manager import (
    SecretBackendType,
    create_secrets_manager,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def rotate_single_secret(
    rotator: SecretRotator,
    name: str,
    new_value: str | None = None,
) -> bool:
    """Rotate a single secret.

    Args:
        rotator: SecretRotator instance
        name: Secret name
        new_value: Optional new value (auto-generated if not provided)

    Returns:
        True if successful
    """
    try:
        event = await rotator.rotate_secret(
            secret_name=name,
            new_value=new_value,
            user="manual-rotation",
        )

        if event.status.value == "success":
            logger.info(
                f"✓ Successfully rotated '{name}' "
                f"(version: {event.old_version} → {event.new_version})"
            )
            return True
        else:
            logger.error(f"✗ Failed to rotate '{name}': {event.error}")
            return False

    except Exception as e:
        logger.error(f"✗ Error rotating '{name}': {e}")
        return False


async def rotate_all_due(rotator: SecretRotator) -> dict:
    """Rotate all secrets that are due.

    Args:
        rotator: SecretRotator instance

    Returns:
        Dictionary with results
    """
    logger.info("Checking for secrets due for rotation...")

    events = await rotator.rotate_all_due(user="manual-rotation")

    results = {
        "total": len(events),
        "successful": len([e for e in events if e.status.value == "success"]),
        "failed": len([e for e in events if e.status.value == "failed"]),
        "events": events,
    }

    return results


async def check_rotation_status(manager, rotator: SecretRotator) -> None:
    """Check rotation status for all secrets.

    Args:
        manager: SecretsManager instance
        rotator: SecretRotator instance
    """
    logger.info("Checking rotation status for all secrets...")

    secrets = await manager.list_secrets()

    print(f"\n{'=' * 80}")
    print(f"{'Secret Name':<30} {'Days Since Rotation':<20} {'Status':<15}")
    print(f"{'=' * 80}")

    for secret_name in secrets:
        try:
            metadata = await manager.backend.get_secret_metadata(secret_name)

            if metadata:
                if metadata.last_rotated:
                    from datetime import datetime

                    days_since = (datetime.utcnow() - metadata.last_rotated).days
                else:
                    days_since = (datetime.utcnow() - metadata.created_at).days

                # Check if rotation is due
                if metadata.rotation_enabled:
                    if days_since >= metadata.rotation_days:
                        status = "⚠ DUE"
                    elif days_since >= metadata.rotation_days * 0.8:
                        status = "⚡ SOON"
                    else:
                        status = "✓ OK"
                else:
                    status = "○ DISABLED"

                print(f"{secret_name:<30} {days_since:<20} {status:<15}")

        except Exception as e:
            print(f"{secret_name:<30} {'N/A':<20} {'✗ ERROR':<15}")
            logger.debug(f"Error checking '{secret_name}': {e}")

    print(f"{'=' * 80}\n")

    # Print rotation history summary
    summary = rotator.get_rotation_summary()
    print("Rotation History Summary:")
    print(f"  Total rotations: {summary['total_rotations']}")
    print(f"  Successful: {summary['successful']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Success rate: {summary['success_rate']:.1%}")
    print(f"  Active policies: {summary['policies_count']}")


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Manual secret rotation tool")

    parser.add_argument(
        "--name",
        type=str,
        help="Secret name to rotate",
    )
    parser.add_argument(
        "--new-value",
        type=str,
        help="New secret value (auto-generated if not provided)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Rotate all secrets due for rotation",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check rotation status without rotating",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="local",
        choices=["local", "aws", "gcp", "azure", "vault"],
        help="Secret backend to use (default: local)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be rotated without actually rotating",
    )

    args = parser.parse_args()

    # Configure backend
    backend_type_map = {
        "local": SecretBackendType.LOCAL_ENCRYPTED,
        "aws": SecretBackendType.AWS_SECRETS_MANAGER,
        "gcp": SecretBackendType.GCP_SECRET_MANAGER,
        "azure": SecretBackendType.AZURE_KEY_VAULT,
        "vault": SecretBackendType.HASHICORP_VAULT,
    }

    backend_type = backend_type_map[args.backend]
    backend_config = {}

    if args.backend == "local":
        backend_config = {
            "storage_path": str(Path.home() / ".kagami" / "secrets" / "secrets.enc"),
            "master_key_path": str(Path.home() / ".kagami" / "secrets" / "master.key"),
            "auto_generate_key": True,
        }

    # Create secrets manager
    manager = create_secrets_manager(
        backend_type=backend_type,
        config=backend_config,
    )

    # Create rotator with default policies
    policies = create_default_policies()
    rotator = SecretRotator(secrets_manager=manager, policies=policies)

    # Execute command
    if args.check:
        await check_rotation_status(manager, rotator)

    elif args.all:
        if args.dry_run:
            logger.info("DRY RUN MODE - No secrets will be rotated")
            secrets_due = await manager.get_secrets_needing_rotation()
            print(f"\nSecrets due for rotation ({len(secrets_due)}):")
            for name in secrets_due:
                print(f"  - {name}")
            print()
        else:
            results = await rotate_all_due(rotator)

            print(f"\n{'=' * 60}")
            print("Rotation Summary")
            print(f"{'=' * 60}")
            print(f"Total secrets: {results['total']}")
            print(f"Successful: {results['successful']}")
            print(f"Failed: {results['failed']}")
            print(f"{'=' * 60}\n")

            for event in results["events"]:
                status = "✓" if event.status.value == "success" else "✗"
                print(f"{status} {event.secret_name}")

    elif args.name:
        if args.dry_run:
            logger.info(f"DRY RUN MODE - Would rotate secret '{args.name}'")
            metadata = await manager.backend.get_secret_metadata(args.name)
            if metadata:
                print(f"\nSecret: {args.name}")
                print(f"Rotation enabled: {metadata.rotation_enabled}")
                print(f"Rotation days: {metadata.rotation_days}")
                print(f"Last rotated: {metadata.last_rotated or 'Never'}")
            else:
                print(f"Secret '{args.name}' not found")
        else:
            await rotate_single_secret(rotator, args.name, args.new_value)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
