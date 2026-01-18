#!/usr/bin/env python3
"""Generate weekly type safety report.

Produces a markdown report showing:
- Total error count
- Errors by type (top 10)
- Errors by module (top 10)
- Progress vs baseline

Usage:
    python scripts/ci/type_safety_dashboard.py > report.md
"""

import subprocess
from datetime import datetime


def count_errors_by_type() -> dict[str, int]:
    """Count mypy errors by category.

    Returns:
        Dictionary mapping error type to count
    """
    result = subprocess.run(
        ["mypy", "kagami/", "--show-error-codes", "--no-error-summary"],
        capture_output=True,
        text=True,
    )

    error_counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        if " error:" in line and "[" in line:
            error_type = line.split("[")[1].split("]")[0]
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

    return error_counts


def count_errors_by_module() -> dict[str, int]:
    """Count errors by top-level module.

    Returns:
        Dictionary mapping module name to error count
    """
    result = subprocess.run(
        ["mypy", "kagami/", "--show-error-codes", "--no-error-summary"],
        capture_output=True,
        text=True,
    )

    module_counts: dict[str, int] = {}
    for line in result.stdout.splitlines():
        if " error:" in line and "kagami/" in line:
            parts = line.split(":")[0].split("/")
            if len(parts) >= 2:
                module = parts[1]  # kagami/MODULE/...
                module_counts[module] = module_counts.get(module, 0) + 1

    return module_counts


def main():
    """Generate and print the type safety dashboard."""
    print(f"# Type Safety Report - {datetime.now().strftime('%Y-%m-%d')}")
    print()

    # Total errors
    result = subprocess.run(
        ["mypy", "kagami/", "--no-error-summary"],
        capture_output=True,
        text=True,
    )
    total = result.stdout.count(" error:")
    print(f"**Total Errors:** {total}")
    print()

    # By type
    print("## Errors by Type")
    print()
    by_type = count_errors_by_type()
    for error_type, count in sorted(by_type.items(), key=lambda x: -x[1])[:10]:
        print(f"- `{error_type}`: {count}")
    print()

    # By module
    print("## Errors by Module")
    print()
    by_module = count_errors_by_module()
    for module, count in sorted(by_module.items(), key=lambda x: -x[1])[:10]:
        print(f"- `kagami/{module}/`: {count}")
    print()

    # Progress
    try:
        with open(".mypy-baseline.txt") as f:
            baseline = int(f.read().strip())

        print("## Progress")
        print()
        print(f"- Baseline: {baseline}")
        print(f"- Current: {total}")
        delta = baseline - total
        pct = (delta / baseline * 100) if baseline > 0 else 0
        if delta > 0:
            print(f"- Improvement: {delta} errors ({pct:.1f}%)")
        elif delta < 0:
            print(f"- Regression: {-delta} errors ({-pct:.1f}%)")
        else:
            print("- No change")
    except FileNotFoundError:
        print("## Progress")
        print()
        print("- No baseline file found (.mypy-baseline.txt)")


if __name__ == "__main__":
    main()
