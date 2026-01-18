#!/usr/bin/env python3
"""Generate cryptographically secure secrets.

Usage:
    python scripts/security/generate_secrets.py --name JWT_SECRET --length 64
    python scripts/security/generate_secrets.py --batch --backend local
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from kagami.core.security.encryption import (
    generate_secret,
    validate_secret_strength,
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


COMMON_SECRETS = {
    "JWT_SECRET": {"length": 64, "rotation_days": 90},
    "KAGAMI_API_KEY": {"length": 48, "rotation_days": 90},
    "CSRF_SECRET": {"length": 32, "rotation_days": 30},
    "SESSION_SECRET": {"length": 32, "rotation_days": 30},
    "ENCRYPTION_KEY": {"length": 32, "rotation_days": 180},
    "SIGNING_KEY": {"length": 32, "rotation_days": 180},
    "WEBHOOK_SECRET": {"length": 32, "rotation_days": 90},
}


async def generate_and_store_secret(
    manager,
    name: str,
    length: int = 32,
    rotation_days: int = 90,
    overwrite: bool = False,
) -> bool:
    """Generate and store a secret.

    Args:
        manager: SecretsManager instance
        name: Secret name
        length: Secret length
        rotation_days: Days between rotations
        overwrite: Overwrite existing secret

    Returns:
        True if successful
    """
    try:
        # Check if secret already exists
        existing = await manager.get_secret(name, user="generator")
        if existing and not overwrite:
            logger.warning(f"Secret '{name}' already exists (use --overwrite to replace)")
            return False

        # Generate secret
        secret_value = generate_secret(length=length, use_symbols=True)

        # Validate strength
        is_valid, error = validate_secret_strength(secret_value, min_length=16)
        if not is_valid:
            logger.error(f"Generated secret failed validation: {error}")
            return False

        # Store secret
        version = await manager.set_secret(
            name=name,
            value=secret_value,
            user="generator",
            rotation_enabled=True,
            rotation_days=rotation_days,
        )

        logger.info(
            f"Generated and stored secret '{name}' "
            f"(version: {version}, length: {length}, rotation: {rotation_days} days)"
        )

        return True

    except Exception as e:
        logger.error(f"Failed to generate secret '{name}': {e}")
        return False


async def generate_batch(
    manager,
    secrets: dict,
    overwrite: bool = False,
) -> dict:
    """Generate multiple secrets.

    Args:
        manager: SecretsManager instance
        secrets: Dictionary of secret names to configurations
        overwrite: Overwrite existing secrets

    Returns:
        Dictionary of results
    """
    results = {}

    for name, config in secrets.items():
        success = await generate_and_store_secret(
            manager=manager,
            name=name,
            length=config.get("length", 32),
            rotation_days=config.get("rotation_days", 90),
            overwrite=overwrite,
        )
        results[name] = success

    return results


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Generate cryptographically secure secrets"
    )

    parser.add_argument(
        "--name",
        type=str,
        help="Secret name (e.g., JWT_SECRET)",
    )
    parser.add_argument(
        "--length",
        type=int,
        default=32,
        help="Secret length in characters (default: 32)",
    )
    parser.add_argument(
        "--rotation-days",
        type=int,
        default=90,
        help="Days between automatic rotations (default: 90)",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Generate all common secrets",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default="local",
        choices=["local", "aws", "gcp", "azure", "vault"],
        help="Secret backend to use (default: local)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing secrets",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Only print generated secret, don't store",
    )

    args = parser.parse_args()

    # Print-only mode (no storage)
    if args.print_only:
        if not args.name:
            print("Error: --name required with --print-only")
            sys.exit(1)

        secret_value = generate_secret(length=args.length, use_symbols=True)
        print(f"\nGenerated secret for '{args.name}':")
        print(secret_value)
        print(f"\nLength: {len(secret_value)} characters")

        is_valid, error = validate_secret_strength(secret_value)
        if is_valid:
            print("Validation: PASSED")
        else:
            print(f"Validation: FAILED - {error}")

        return

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

    # Backend-specific configuration
    if args.backend == "local":
        backend_config = {
            "storage_path": str(Path.home() / ".kagami" / "secrets" / "secrets.enc"),
            "master_key_path": str(Path.home() / ".kagami" / "secrets" / "master.key"),
            "auto_generate_key": True,
        }
    # For cloud backends, configuration would come from environment variables
    # or config files (not implemented here for security)

    # Create secrets manager
    manager = create_secrets_manager(
        backend_type=backend_type,
        config=backend_config,
    )

    # Generate secrets
    if args.batch:
        logger.info(f"Generating {len(COMMON_SECRETS)} common secrets...")
        results = await generate_batch(
            manager=manager,
            secrets=COMMON_SECRETS,
            overwrite=args.overwrite,
        )

        # Print summary
        successful = sum(1 for v in results.values() if v)
        failed = len(results) - successful

        print(f"\n{'='*60}")
        print("Batch Generation Summary")
        print(f"{'='*60}")
        print(f"Total secrets: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed/Skipped: {failed}")
        print(f"{'='*60}\n")

        for name, success in results.items():
            status = "✓" if success else "✗"
            print(f"{status} {name}")

    elif args.name:
        await generate_and_store_secret(
            manager=manager,
            name=args.name,
            length=args.length,
            rotation_days=args.rotation_days,
            overwrite=args.overwrite,
        )

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
