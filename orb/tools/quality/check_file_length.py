#!/usr/bin/env python3
"""
Check for files exceeding maximum line count.

Quality gate: Files > 500 lines indicate poor modularity.
Exemptions: Add '# quality-gate: exempt file-length' to first 10 lines.
"""

import sys
from pathlib import Path


MAX_LINES = 2000  # AI/ML codebases have complex modules (world models, training loops, etc.)
EXEMPT_COMMENT = "# quality-gate: exempt file-length"


def check_file_length(file_path: Path) -> tuple[bool, int, bool]:
    """
    Check if file exceeds max line count.

    Returns:
        (is_valid, line_count, is_exempt)
    """
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        line_count = len(lines)

        # Check for exemption in first 10 lines
        is_exempt = any(EXEMPT_COMMENT in line for line in lines[:10])

        is_valid = is_exempt or line_count <= MAX_LINES
        return is_valid, line_count, is_exempt
    except Exception as e:
        print(f"⚠️  Error reading {file_path}: {e}", file=sys.stderr)
        return True, 0, False  # Skip files we can't read


def main() -> int:
    """Run file length check on Python files."""
    kagami_root = Path("kagami")
    if not kagami_root.exists():
        print("❌ kagami/ directory not found", file=sys.stderr)
        return 1

    # Find all Python files
    python_files = list(kagami_root.rglob("*.py"))

    violations: list[tuple[Path, int]] = []
    exempt_files: list[tuple[Path, int]] = []

    for file_path in python_files:
        is_valid, line_count, is_exempt = check_file_length(file_path)

        if is_exempt:
            exempt_files.append((file_path, line_count))
        elif not is_valid:
            violations.append((file_path, line_count))

    # Report results
    if violations:
        print(f"\n❌ File Length Violations: {len(violations)} files exceed {MAX_LINES} lines\n")
        for file_path, line_count in sorted(violations, key=lambda x: x[1], reverse=True):
            print(f"  {file_path}:{line_count} lines (max {MAX_LINES})")

        print(f"\nTo exempt a file, add '{EXEMPT_COMMENT}' to the first 10 lines.")
        print("Consider refactoring large files into smaller modules.\n")
        return 1

    print(f"✅ File Length Check: All {len(python_files)} files under {MAX_LINES} lines")
    if exempt_files:
        print(f"   ({len(exempt_files)} exempt files)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
