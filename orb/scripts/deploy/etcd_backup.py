#!/usr/bin/env python3
"""etcd backup script for K os.

Creates snapshots of etcd data for disaster recovery.
Supports both manual and automated backup workflows.
"""

import argparse
import datetime
import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("etcd_backup")


def get_etcd_endpoints() -> list[str]:
    """Get etcd endpoints from environment."""
    endpoints_str = os.getenv("ETCD_ENDPOINTS", "http://localhost:2379")
    return [e.strip() for e in endpoints_str.split(",") if e.strip()]


def create_backup(
    output_dir: Path,
    endpoint: str | None = None,
) -> Path:
    """Create etcd snapshot backup.

    Args:
        output_dir: Directory to store backup
        endpoint: etcd endpoint (uses env if not provided)

    Returns:
        Path to backup file

    Raises:
        RuntimeError: If backup fails
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate backup filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = output_dir / f"etcd_snapshot_{timestamp}.db"

    # Get endpoint
    if endpoint is None:
        endpoints = get_etcd_endpoints()
        endpoint = endpoints[0]

    logger.info(f"Creating etcd backup from {endpoint}...")
    logger.info(f"Output: {backup_file}")

    try:
        # Use etcdctl to create snapshot
        cmd = [
            "etcdctl",
            f"--endpoints={endpoint}",
            "snapshot",
            "save",
            str(backup_file),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "ETCDCTL_API": "3"},
        )

        if result.returncode != 0:
            raise RuntimeError(f"Backup failed: {result.stderr}")

        logger.info(f"✅ Backup created: {backup_file}")
        logger.info(f"   Size: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")

        # Verify snapshot
        verify_cmd = [
            "etcdctl",
            "snapshot",
            "status",
            str(backup_file),
            "--write-out=table",
        ]

        verify_result = subprocess.run(
            verify_cmd,
            capture_output=True,
            text=True,
            env={**os.environ, "ETCDCTL_API": "3"},
        )

        if verify_result.returncode == 0:
            logger.info("✅ Snapshot verified")
            logger.info(f"\n{verify_result.stdout}")
        else:
            logger.warning(f"⚠️  Snapshot verification failed: {verify_result.stderr}")

        return backup_file

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Backup command failed: {e.stderr}") from e
    except Exception as e:
        raise RuntimeError(f"Backup failed: {e}") from e


def upload_backup(backup_file: Path, destination: str) -> None:
    """Upload backup file to remote storage."""
    logger.info(f"Uploading {backup_file} to {destination}")
    if destination.startswith("s3://"):
        cmd = ["aws", "s3", "cp", str(backup_file), destination.rstrip("/") + "/"]
    elif destination.startswith("gs://"):
        cmd = ["gsutil", "cp", str(backup_file), destination.rstrip("/") + "/"]
    else:
        raise RuntimeError(f"Unsupported upload destination: {destination}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Upload failed: {result.stderr}")
    logger.info("✅ Upload completed")


def cleanup_old_backups(
    backup_dir: Path,
    keep_count: int = 7,
) -> None:
    """Remove old backup files, keeping most recent N.

    Args:
        backup_dir: Backup directory
        keep_count: Number of backups to keep
    """
    if not backup_dir.exists():
        return

    # Find all backup files
    backups = sorted(
        backup_dir.glob("etcd_snapshot_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if len(backups) <= keep_count:
        logger.info(f"Keeping all {len(backups)} backups")
        return

    # Remove old backups
    to_remove = backups[keep_count:]
    logger.info(f"Removing {len(to_remove)} old backups...")

    for backup in to_remove:
        try:
            backup.unlink()
            logger.info(f"   Removed: {backup.name}")
        except Exception as e:
            logger.warning(f"   Failed to remove {backup.name}: {e}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Backup etcd data for K os")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("backups/etcd"),
        help="Backup output directory (default: backups/etcd)",
    )
    parser.add_argument(
        "--endpoint",
        help="etcd endpoint (default: from ETCD_ENDPOINTS env)",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=7,
        help="Number of backups to keep (default: 7)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Don't remove old backups",
    )
    parser.add_argument(
        "--upload",
        help="Upload destination (s3://bucket/path or gs://bucket/path)",
    )

    args = parser.parse_args()

    try:
        # Create backup
        backup_file = create_backup(
            output_dir=args.output_dir,
            endpoint=args.endpoint,
        )

        # Cleanup old backups
        if not args.no_cleanup:
            cleanup_old_backups(
                backup_dir=args.output_dir,
                keep_count=args.keep,
            )

        if args.upload:
            upload_backup(backup_file, args.upload)

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ Backup completed successfully")
        logger.info(f"   File: {backup_file}")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error(f"❌ Backup failed: {e}")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
