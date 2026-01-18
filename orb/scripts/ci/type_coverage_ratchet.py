#!/usr/bin/env python3
"""Type coverage ratchet - prevent type safety from regressing.

This script ensures the number of mypy errors never increases.
If errors decrease, the baseline is automatically updated.

Usage:
    python scripts/ci/type_coverage_ratchet.py

Exit codes:
    0: Type coverage maintained or improved
    1: Type coverage regressed (more errors than baseline)
"""

import subprocess
import sys
from pathlib import Path


def count_mypy_errors(path: str) -> int:
    """Count mypy errors in a path.

    Args:
        path: Directory or file to check

    Returns:
        Number of errors found
    """
    result = subprocess.run(
        ["mypy", path, "--show-error-codes", "--no-error-summary"],
        capture_output=True,
        text=True,
    )
    return result.stdout.count(" error:")


def main() -> int:
    """Run the type coverage ratchet check."""
    baseline_file = Path(".mypy-baseline.txt")

    if not baseline_file.exists():
        print("❌ No baseline file found (.mypy-baseline.txt)")
        print("   Run: echo '2340' > .mypy-baseline.txt")
        return 1

    # Read baseline
    with open(baseline_file) as f:
        baseline = int(f.read().strip())

    # Count current errors
    current = count_mypy_errors("kagami/")

    print(f"Baseline errors: {baseline}")
    print(f"Current errors:  {current}")

    if current > baseline:
        print(f"❌ Type coverage regressed by {current - baseline} errors!")
        print("   Fix type errors before merging.")
        return 1
    elif current < baseline:
        improvement = baseline - current
        pct = (improvement / baseline) * 100
        print(f"✅ Type coverage improved by {improvement} errors ({pct:.1f}%)!")
        print(f"   Updating baseline to {current}")
        with open(baseline_file, "w") as f:
            f.write(str(current))
    else:
        print("✅ Type coverage maintained")

    return 0


if __name__ == "__main__":
    sys.exit(main())
