#!/usr/bin/env python3
"""Batch Size Validator for K os CI/CD.

Ensures commits respect the ≤10 files per batch operational rule.
Fails CI if batch size exceeded without [batch-override] marker.

Usage:
    python scripts/ci/validate_batch_size.py --base-ref origin/main
    python scripts/ci/validate_batch_size.py --base-ref main --limit 10
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_changed_python_files(base_ref: str) -> list[str]:
    """Get list of changed Python files compared to base ref.

    Args:
        base_ref: Base git reference (e.g., 'origin/main')

    Returns:
        List of changed .py file paths
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        files = [
            line.strip() for line in result.stdout.splitlines() if line.strip().endswith(".py")
        ]
        return files
    except subprocess.CalledProcessError as e:
        print(f"Error getting changed files: {e}")
        return []


def check_batch_override(base_ref: str) -> bool:
    """Check if [batch-override] marker is present in commit messages.

    Args:
        base_ref: Base git reference

    Returns:
        True if override marker found
    """
    try:
        result = subprocess.run(
            ["git", "log", f"{base_ref}..HEAD", "--pretty=%B"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return "[batch-override]" in result.stdout
    except subprocess.CalledProcessError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Base git reference for comparison (default: origin/main)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum files per batch (default: 10)",
    )
    args = parser.parse_args(argv or sys.argv[1:])

    # Get changed files
    changed_files = get_changed_python_files(args.base_ref)
    num_changed = len(changed_files)

    print(f"Changed Python files: {num_changed}")

    if num_changed <= args.limit:
        print(f"✅ Batch size within limit ({num_changed} ≤ {args.limit})")
        return 0

    # Check for override marker
    if check_batch_override(args.base_ref):
        print(f"✅ [batch-override] detected, allowing {num_changed} files")
        return 0

    # Violation
    print(f"❌ Batch size limit exceeded: {num_changed} files > {args.limit}")
    print("\nChanged files:")
    for f in changed_files[:20]:
        print(f"  - {f}")
    if num_changed > 20:
        print(f"  ... and {num_changed - 20} more")

    print("\nPer K os operational rules (see .cursor/rules/):")
    print("  - Limit changes to ≤10 files per batch")
    print("  - Validate after each batch to prevent mass breakage")
    print("  - Add [batch-override] to commit message for approved large refactors")

    return 1


if __name__ == "__main__":
    sys.exit(main())
