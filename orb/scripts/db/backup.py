#!/usr/bin/env python3
"""Database backup script.

Usage:
    python scripts/db/backup.py [--output PATH] [--format FORMAT]

Examples:
    # Backup to default location
    python scripts/db/backup.py

    # Backup to specific file
    python scripts/db/backup.py --output /backups/kagami_2025_12_28.sql

    # Backup as custom format (better compression)
    python scripts/db/backup.py --format custom

Environment Variables:
    DATABASE_URL: PostgreSQL connection string (required)
"""

import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
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


def backup_database(output_path: Path, format: str = "plain") -> None:
    """Backup database using pg_dump.

    Args:
        output_path: Output file path
        format: Backup format (plain, custom, tar)
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable must be set")

    db_config = parse_database_url(database_url)

    # Build pg_dump command
    cmd = [
        "pg_dump",
        "-h", db_config["host"],
        "-p", db_config["port"],
        "-U", db_config["user"],
        "-d", db_config["database"],
    ]

    # Add format flag
    if format == "custom":
        cmd.extend(["-Fc"])  # Custom format (compressed)
    elif format == "tar":
        cmd.extend(["-Ft"])  # Tar format
    else:
        cmd.extend(["-Fp"])  # Plain SQL format

    # Add output file
    cmd.extend(["-f", str(output_path)])

    # Set password environment variable
    env = os.environ.copy()
    if db_config["password"]:
        env["PGPASSWORD"] = db_config["password"]

    logger.info(f"Backing up database to {output_path}...")
    logger.info(f"Database: {db_config['database']} @ {db_config['host']}:{db_config['port']}")

    try:
        result = subprocess.run(
            cmd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

        if result.stderr:
            logger.warning(f"pg_dump warnings: {result.stderr}")

        # Get file size
        size_mb = output_path.stat().st_size / (1024 * 1024)
        logger.info(f"Backup complete! Size: {size_mb:.2f} MB")

    except subprocess.CalledProcessError as e:
        logger.error(f"Backup failed: {e.stderr}")
        raise
    except FileNotFoundError:
        logger.error(
            "pg_dump not found. Please install PostgreSQL client tools.\n"
            "  Ubuntu/Debian: sudo apt-get install postgresql-client\n"
            "  macOS: brew install postgresql"
        )
        raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Database backup tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Generate default backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_output = project_root / "backups" / f"kagami_{timestamp}.sql"

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=default_output,
        help=f"Output file path (default: {default_output})",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["plain", "custom", "tar"],
        default="plain",
        help="Backup format (default: plain)",
    )

    args = parser.parse_args()

    # Create backups directory if needed
    args.output.parent.mkdir(parents=True, exist_ok=True)

    try:
        backup_database(args.output, args.format)
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
