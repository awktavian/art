#!/usr/bin/env python3
"""Database restore script.

Usage:
    python scripts/db/restore.py <backup_file> [--clean]

Examples:
    # Restore from backup
    python scripts/db/restore.py backups/kagami_20251228.sql

    # Restore with clean (drop existing objects first)
    python scripts/db/restore.py backups/kagami_20251228.sql --clean

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (required)
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_database_url(url: str) -> dict[str, str]:
    """Parse DATABASE_URL into components.

    Args:
        url: Database URL

    Returns:
        Dict with host, port, database, user, password
    """
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 26257),
        "database": parsed.path.lstrip("/") or "kagami",
        "user": parsed.username or "root",
        "password": parsed.password or "",
    }


def detect_backup_format(backup_path: Path) -> str:
    """Detect backup format from file extension.

    Args:
        backup_path: Path to backup file

    Returns:
        Format string (plain, custom, tar)
    """
    suffix = backup_path.suffix.lower()
    if suffix == ".dump":
        return "custom"
    elif suffix in [".tar", ".tgz"]:
        return "tar"
    else:
        return "plain"


def restore_database(backup_path: Path, clean: bool = False) -> None:
    """Restore database from backup.

    Args:
        backup_path: Path to backup file
        clean: Whether to clean (drop) existing objects first
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set")

    db_config = parse_database_url(database_url)
    backup_format = detect_backup_format(backup_path)

    logger.info(f"Restoring database from {backup_path}...")
    logger.info(f"Database: {db_config['database']} @ {db_config['host']}:{db_config['port']}")
    logger.info(f"Format: {backup_format}")

    # Confirm for clean restore
    if clean:
        logger.warning("WARNING: --clean will drop all existing database objects!")
        confirm = input("Are you sure? [y/N]: ")
        if confirm.lower() != "y":
            logger.info("Restore cancelled.")
            return

    # Build restore command based on format
    if backup_format == "plain":
        # Use psql for plain SQL files
        cmd = [
            "psql",
            "-h",
            db_config["host"],
            "-p",
            db_config["port"],
            "-U",
            db_config["user"],
            "-d",
            db_config["database"],
            "-f",
            str(backup_path),
        ]
    else:
        # Use pg_restore for custom/tar formats
        cmd = [
            "pg_restore",
            "-h",
            db_config["host"],
            "-p",
            db_config["port"],
            "-U",
            db_config["user"],
            "-d",
            db_config["database"],
        ]

        if clean:
            cmd.append("--clean")

        cmd.append(str(backup_path))

    # Set password environment variable
    env = os.environ.copy()
    if db_config["password"]:
        env["PGPASSWORD"] = db_config["password"]

    try:
        result = subprocess.run(
            cmd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        if result.stderr:
            logger.warning(f"Restore warnings: {result.stderr}")

        logger.info("Restore complete!")

    except subprocess.CalledProcessError as e:
        logger.error(f"Restore failed: {e.stderr}")
        raise
    except FileNotFoundError:
        tool = "psql" if backup_format == "plain" else "pg_restore"
        logger.error(
            f"{tool} not found. Please install PostgreSQL client tools.\n"
            "  Ubuntu/Debian: sudo apt-get install postgresql-client\n"
            "  macOS: brew install postgresql"
        )
        raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database restore tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "backup_file",
        type=Path,
        help="Path to backup file",
    )
    parser.add_argument(
        "--clean",
        "-c",
        action="store_true",
        help="Clean (drop) existing objects before restore",
    )

    args = parser.parse_args()

    try:
        restore_database(args.backup_file, args.clean)
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
