#!/usr/bin/env python3
"""Database rollback script using Alembic.

Usage:
    python scripts/db/rollback.py [--steps N | --target REVISION]

Examples:
    # Rollback one migration
    python scripts/db/rollback.py

    # Rollback 3 migrations
    python scripts/db/rollback.py --steps 3

    # Rollback to specific revision
    python scripts/db/rollback.py --target abc123

    # Rollback all migrations
    python scripts/db/rollback.py --all

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (required)
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from alembic import command
from alembic.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_alembic_config() -> Config:
    """Get Alembic configuration.

    Returns:
        Alembic Config object

    Raises:
        ValueError: If DATABASE_URL not set
    """
    if not os.getenv("DATABASE_URL"):
        raise ValueError(
            "DATABASE_URL environment variable must be set.\n"
            "Example: export DATABASE_URL='postgresql://user:pass@localhost:26257/kagami'"
        )

    alembic_ini = project_root / "alembic.ini"
    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")

    config = Config(str(alembic_ini))
    return config


def rollback_steps(steps: int = 1) -> None:
    """Rollback N migration steps.

    Args:
        steps: Number of steps to rollback (default: 1)
    """
    config = get_alembic_config()
    logger.info(f"Rolling back {steps} migration(s)...")
    command.downgrade(config, f"-{steps}")
    logger.info("Rollback complete!")


def rollback_to_revision(revision: str) -> None:
    """Rollback to specific revision.

    Args:
        revision: Target revision ID
    """
    config = get_alembic_config()
    logger.info(f"Rolling back to revision {revision}...")
    command.downgrade(config, revision)
    logger.info("Rollback complete!")


def rollback_all() -> None:
    """Rollback all migrations (to base)."""
    config = get_alembic_config()
    logger.warning("Rolling back ALL migrations to base...")
    confirm = input("Are you sure? This will undo all migrations. [y/N]: ")
    if confirm.lower() != "y":
        logger.info("Rollback cancelled.")
        return

    command.downgrade(config, "base")
    logger.info("Rollback complete!")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database rollback tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--steps",
        "-s",
        type=int,
        default=1,
        help="Number of migrations to rollback (default: 1)",
    )
    parser.add_argument(
        "--target",
        "-t",
        help="Target revision to rollback to",
        default=None,
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Rollback all migrations (to base)",
    )

    args = parser.parse_args()

    try:
        if args.all:
            rollback_all()
        elif args.target:
            rollback_to_revision(args.target)
        else:
            rollback_steps(args.steps)
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
