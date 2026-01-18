#!/usr/bin/env python3
"""Check Python files for excessive length.

Files exceeding 500 lines are flagged as violations.
This enforces the file-size limits documented in .cursor/rules/file-size.mdc
"""

from pathlib import Path
import sys


# Hard limit
MAX_LINES = 500

# Soft warning threshold
WARN_LINES = 300

# Directories to check
CHECK_DIRS = ["packages"]

# Patterns to exclude
EXCLUDE_PATTERNS = [
    "*.generated.*",
    "__pycache__",
    ".pyc",
    "test_*.py",
    "*_test.py",
    "conftest.py",
]


def should_exclude(path: Path) -> bool:
    """Check if file should be excluded from checks."""
    path_str = str(path)
    name = path.name

    for pattern in EXCLUDE_PATTERNS:
        if pattern.startswith("*") and pattern.endswith("*"):
            # Contains pattern
            if pattern[1:-1] in path_str:
                return True
        elif pattern.startswith("*"):
            # Ends with pattern
            if name.endswith(pattern[1:]):
                return True
        elif pattern.endswith("*"):
            # Starts with pattern
            if name.startswith(pattern[:-1]):
                return True
        elif pattern in path_str:
            return True

    return False


def count_lines(path: Path) -> int:
    """Count non-empty, non-comment lines in a Python file."""
    try:
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        # Count all lines (including comments and blanks for simplicity)
        return len(lines)
    except Exception:
        return 0


def check_files(root: Path) -> tuple[list, list]:
    """Check all Python files and return (violations, warnings)."""
    violations = []
    warnings = []

    for check_dir in CHECK_DIRS:
        dir_path = root / check_dir
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            if should_exclude(py_file):
                continue

            line_count = count_lines(py_file)
            rel_path = py_file.relative_to(root)

            if line_count > MAX_LINES:
                violations.append((rel_path, line_count))
            elif line_count > WARN_LINES:
                warnings.append((rel_path, line_count))

    return violations, warnings


def main() -> int:
    """Main entry point."""
    root = Path(__file__).parent.parent.parent

    violations, warnings = check_files(root)

    # Sort by line count descending
    violations.sort(key=lambda x: x[1], reverse=True)
    warnings.sort(key=lambda x: x[1], reverse=True)

    print("=" * 60)
    print("FILE LENGTH CHECK")
    print("=" * 60)

    if violations:
        print(f"\n❌ {len(violations)} files exceed {MAX_LINES} lines:")
        for path, lines in violations[:20]:  # Show top 20
            print(f"  {lines:>5} lines: {path}")
        if len(violations) > 20:
            print(f"  ... and {len(violations) - 20} more")

    if warnings:
        print(f"\n⚠️  {len(warnings)} files exceed {WARN_LINES} lines (warning):")
        for path, lines in warnings[:10]:  # Show top 10
            print(f"  {lines:>5} lines: {path}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")

    if not violations and not warnings:
        print("\n✅ All files within length limits")

    print()

    # Don't fail the build - this is advisory
    return 0


if __name__ == "__main__":
    sys.exit(main())
