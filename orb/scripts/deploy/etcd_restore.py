#!/usr/bin/env python3
"""etcd restore script for K os.

Restores etcd data from snapshot backups.
WARNING: This will stop the etcd cluster and restore from backup.
         All data written after the backup will be lost.
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("etcd_restore")


def get_etcd_data_dir() -> Path:
    """Get etcd data directory from environment or default."""
    data_dir = os.getenv("ETCD_DATA_DIR", "/var/lib/etcd")
    return Path(data_dir)


def verify_snapshot(snapshot_file: Path) -> bool:
    """Verify snapshot integrity.

    Args:
        snapshot_file: Snapshot file to verify

    Returns:
        True if valid

    Raises:
        RuntimeError: If verification fails
    """
    logger.info(f"Verifying snapshot: {snapshot_file}")

    try:
        cmd = [
            "etcdctl",
            "snapshot",
            "status",
            str(snapshot_file),
            "--write-out=table",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "ETCDCTL_API": "3"},
        )

        logger.info("✅ Snapshot is valid")
        logger.info(f"\n{result.stdout}")
        return True

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Snapshot verification failed: {e.stderr}") from e


def restore_snapshot(
    snapshot_file: Path,
    data_dir: Path,
    cluster_name: str = "kagami-etcd-cluster",
) -> None:
    """Restore etcd from snapshot.

    Args:
        snapshot_file: Snapshot file to restore
        data_dir: etcd data directory
        cluster_name: Cluster name

    Raises:
        RuntimeError: If restore fails
    """
    logger.warning("")
    logger.warning("=" * 60)
    logger.warning("⚠️  DESTRUCTIVE OPERATION")
    logger.warning("=" * 60)
    logger.warning(f"This will restore etcd from: {snapshot_file}")
    logger.warning("All current data will be replaced!")
    logger.warning("")

    # Verify snapshot first
    verify_snapshot(snapshot_file)

    # Confirm
    response = input("Type 'yes' to continue: ")
    if response.lower() != "yes":
        logger.info("Restore cancelled")
        return

    logger.info("")
    logger.info("Restoring snapshot...")

    try:
        # Restore snapshot
        cmd = [
            "etcdctl",
            "snapshot",
            "restore",
            str(snapshot_file),
            f"--name={cluster_name}",
            f"--data-dir={data_dir}",
            "--initial-cluster-token=kagami-etcd-cluster",
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "ETCDCTL_API": "3"},
        )

        if result.returncode != 0:
            raise RuntimeError(f"Restore failed: {result.stderr}")

        logger.info("✅ Snapshot restored successfully")
        logger.info("")
        logger.info("=" * 60)
        logger.info("⚠️  IMPORTANT: Restart etcd cluster now")
        logger.info("=" * 60)
        logger.info("For Docker Compose:")
        logger.info("  docker-compose restart etcd1 etcd2 etcd3")
        logger.info("")
        logger.info("For Kubernetes:")
        logger.info("  kubectl rollout restart statefulset/etcd -n kagami")
        logger.info("")

    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Restore command failed: {e.stderr}") from e
    except Exception as e:
        raise RuntimeError(f"Restore failed: {e}") from e


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Restore etcd data from backup")
    parser.add_argument(
        "snapshot",
        type=Path,
        help="Snapshot file to restore",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="etcd data directory (default: from ETCD_DATA_DIR env or /var/lib/etcd)",
    )
    parser.add_argument(
        "--cluster-name",
        default="kagami-etcd-cluster",
        help="Cluster name (default: kagami-etcd-cluster)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt (dangerous!)",
    )

    args = parser.parse_args()

    # Validate snapshot file
    if not args.snapshot.exists():
        logger.error(f"Snapshot file not found: {args.snapshot}")
        return 1

    # Get data directory
    data_dir = args.data_dir or get_etcd_data_dir()

    try:
        restore_snapshot(
            snapshot_file=args.snapshot,
            data_dir=data_dir,
            cluster_name=args.cluster_name,
        )

        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ Restore completed successfully")
        logger.info("=" * 60)

        return 0

    except Exception as e:
        logger.error("")
        logger.error("=" * 60)
        logger.error(f"❌ Restore failed: {e}")
        logger.error("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
