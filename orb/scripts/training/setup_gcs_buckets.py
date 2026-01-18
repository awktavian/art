#!/usr/bin/env python3
"""Setup GCS buckets for TPU training infrastructure.

Creates required buckets and directory structure:
- gs://kagami-training-data/ - Training data shards
- gs://kagami-checkpoints/ - Model checkpoints
- gs://kagami-models/ - Final trained models

Usage:
    python scripts/training/setup_gcs_buckets.py --project kagami-prod

Prerequisites:
    - gcloud CLI authenticated
    - Access to GCP project

Created: January 12, 2026
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GCSBucketConfig:
    """Configuration for a GCS bucket."""

    name: str
    location: str = "us-central1"
    storage_class: str = "STANDARD"
    lifecycle_days: int | None = None  # Days before deletion (None = no lifecycle)
    directories: list[str] | None = None


# Bucket definitions
BUCKETS = [
    GCSBucketConfig(
        name="kagami-training-data",
        location="us-central1",
        storage_class="STANDARD",
        directories=[
            "genesis/v1/",
            "qm9/v1/",
            "tree_of_life/v1/",
            "language/v1/",
        ],
    ),
    GCSBucketConfig(
        name="kagami-checkpoints",
        location="us-central1",
        storage_class="STANDARD",
        lifecycle_days=90,  # Delete checkpoints after 90 days
        directories=[
            "organism-rssm/",
            "distillation/",
        ],
    ),
    GCSBucketConfig(
        name="kagami-models",
        location="us-central1",
        storage_class="STANDARD",
        directories=[
            "teacher/",
            "student-small/",
            "student-base/",
            "student-large/",
            "onnx/",
            "coreml/",
            "tflite/",
        ],
    ),
]


def run_gcloud(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a gcloud command."""
    cmd = ["gcloud"] + args
    logger.debug(f"Running: {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def bucket_exists(bucket_name: str) -> bool:
    """Check if a GCS bucket exists."""
    result = run_gcloud(
        ["storage", "buckets", "describe", f"gs://{bucket_name}"],
        check=False,
    )
    return result.returncode == 0


def create_bucket(config: GCSBucketConfig, project: str) -> bool:
    """Create a GCS bucket."""
    if bucket_exists(config.name):
        logger.info(f"✓ Bucket gs://{config.name} already exists")
        return True

    logger.info(f"Creating bucket gs://{config.name}...")

    result = run_gcloud(
        [
            "storage",
            "buckets",
            "create",
            f"gs://{config.name}",
            f"--project={project}",
            f"--location={config.location}",
            f"--default-storage-class={config.storage_class}",
            "--uniform-bucket-level-access",
        ],
        check=False,
    )

    if result.returncode != 0:
        logger.error(f"Failed to create bucket: {result.stderr}")
        return False

    logger.info(f"✓ Created bucket gs://{config.name}")
    return True


def create_directories(config: GCSBucketConfig) -> None:
    """Create directory markers in bucket."""
    if not config.directories:
        return

    for dir_path in config.directories:
        # GCS doesn't have real directories, but we create marker objects
        marker_path = f"gs://{config.name}/{dir_path}.keep"
        result = run_gcloud(
            [
                "storage",
                "cp",
                "-",
                marker_path,
            ],
            check=False,
        )
        if result.returncode == 0:
            logger.info(f"  ✓ Created directory {dir_path}")
        else:
            # Try using gsutil as fallback
            subprocess.run(
                f"echo '' | gsutil cp - {marker_path}",
                shell=True,
                check=False,
            )


def set_lifecycle(config: GCSBucketConfig) -> None:
    """Set lifecycle policy on bucket."""
    if config.lifecycle_days is None:
        return

    lifecycle_json = f"""
    {{
        "rule": [
            {{
                "action": {{"type": "Delete"}},
                "condition": {{"age": {config.lifecycle_days}}}
            }}
        ]
    }}
    """

    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(lifecycle_json)
        lifecycle_file = f.name

    result = run_gcloud(
        [
            "storage",
            "buckets",
            "update",
            f"gs://{config.name}",
            f"--lifecycle-file={lifecycle_file}",
        ],
        check=False,
    )

    if result.returncode == 0:
        logger.info(f"  ✓ Set {config.lifecycle_days}-day lifecycle on {config.name}")

    import os

    os.unlink(lifecycle_file)


def setup_cors(bucket_name: str) -> None:
    """Set CORS policy for web access."""
    cors_json = """
    [
        {
            "origin": ["*"],
            "method": ["GET", "HEAD"],
            "responseHeader": ["Content-Type"],
            "maxAgeSeconds": 3600
        }
    ]
    """

    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write(cors_json)
        cors_file = f.name

    run_gcloud(
        [
            "storage",
            "buckets",
            "update",
            f"gs://{bucket_name}",
            f"--cors-file={cors_file}",
        ],
        check=False,
    )

    import os

    os.unlink(cors_file)


def verify_setup() -> bool:
    """Verify all buckets are accessible."""
    all_ok = True

    for config in BUCKETS:
        result = run_gcloud(
            ["storage", "ls", f"gs://{config.name}/"],
            check=False,
        )
        if result.returncode == 0:
            logger.info(f"✓ Verified gs://{config.name}")
        else:
            logger.error(f"✗ Cannot access gs://{config.name}")
            all_ok = False

    return all_ok


def print_summary() -> None:
    """Print summary of bucket URLs."""
    print("\n" + "=" * 60)
    print("GCS Bucket Setup Complete")
    print("=" * 60)
    print("\nBucket URLs:")
    for config in BUCKETS:
        print(f"  • gs://{config.name}/")
        if config.directories:
            for dir_path in config.directories[:3]:
                print(f"    └── {dir_path}")
            if len(config.directories) > 3:
                print(f"    └── ... ({len(config.directories) - 3} more)")

    print("\nUsage in training:")
    print("  --data-dir gs://kagami-training-data/genesis/v1")
    print("  --checkpoint-dir gs://kagami-checkpoints/organism-rssm")
    print("  --model-dir gs://kagami-models/teacher")
    print("=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Setup GCS buckets for TPU training")
    parser.add_argument(
        "--project",
        type=str,
        default="kagami-prod",
        help="GCP project ID",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify existing buckets",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    # Check gcloud is available
    try:
        result = subprocess.run(
            ["gcloud", "--version"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.debug(f"gcloud version: {result.stdout.split()[0]}")
    except FileNotFoundError:
        logger.error("gcloud CLI not found. Install from: https://cloud.google.com/sdk")
        sys.exit(1)

    if args.verify_only:
        if verify_setup():
            print_summary()
            sys.exit(0)
        else:
            sys.exit(1)

    # Create buckets
    logger.info(f"Setting up GCS buckets in project: {args.project}")
    print()

    for config in BUCKETS:
        if not create_bucket(config, args.project):
            logger.error(f"Failed to create {config.name}")
            continue

        create_directories(config)
        set_lifecycle(config)

    print()

    # Verify
    if verify_setup():
        print_summary()
    else:
        logger.error("Some buckets are not accessible")
        sys.exit(1)


if __name__ == "__main__":
    main()
