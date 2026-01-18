#!/usr/bin/env python3
"""Database migration script using Alembic.

Usage:
    python scripts/db/migrate.py [--target REVISION]

Examples:
    # Migrate to latest
    python scripts/db/migrate.py

    # Migrate to specific revision
    python scripts/db/migrate.py --target abc123

    # Show current version
    python scripts/db/migrate.py --show

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

    # Path to alembic.ini
    alembic_ini = project_root / "alembic.ini"
    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")

    config = Config(str(alembic_ini))
    return config


def show_current_revision() -> None:
    """Show current database revision."""
    config = get_alembic_config()
    command.current(config, verbose=True)


def migrate_to_head() -> None:
    """Migrate database to latest revision."""
    config = get_alembic_config()
    logger.info("Migrating database to latest revision...")
    command.upgrade(config, "head")
    logger.info("Migration complete!")


def migrate_to_revision(revision: str) -> None:
    """Migrate database to specific revision.

    Args:
        revision: Target revision ID
    """
    config = get_alembic_config()
    logger.info(f"Migrating database to revision {revision}...")
    command.upgrade(config, revision)
    logger.info("Migration complete!")


def show_migration_history() -> None:
    """Show migration history."""
    config = get_alembic_config()
    command.history(config, verbose=True)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database migration tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--target",
        "-t",
        help="Target revision (default: head)",
        default=None,
    )
    parser.add_argument(
        "--show",
        "-s",
        action="store_true",
        help="Show current revision",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show migration history",
    )

    args = parser.parse_args()

    try:
        if args.show:
            show_current_revision()
        elif args.history:
            show_migration_history()
        elif args.target:
            migrate_to_revision(args.target)
        else:
            migrate_to_head()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
