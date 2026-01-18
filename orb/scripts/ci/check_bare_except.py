#!/usr/bin/env python3
"""Check for bare except clauses in Python code.

Bare except clauses (except:) catch all exceptions including
SystemExit, KeyboardInterrupt, etc. which can hide bugs.

This is already covered by ruff E722, but this provides a focused report.
"""

import ast
import sys
from pathlib import Path


# Directories to check
CHECK_DIRS = ["packages"]


def find_bare_excepts(path: Path) -> list[tuple[int, str]]:
    """Find bare except clauses in a Python file.

    Returns list of (line_number, context) tuples.
    """
    results = []

    try:
        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content)
    except (SyntaxError, UnicodeDecodeError):
        return results

    lines = content.split("\n")

    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                # Bare except
                line_no = node.lineno
                context = lines[line_no - 1].strip() if line_no <= len(lines) else ""
                results.append((line_no, context))

    return results


def check_files(root: Path) -> dict[Path, list]:
    """Check all Python files for bare excepts."""
    findings = {}

    for check_dir in CHECK_DIRS:
        dir_path = root / check_dir
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            bare_excepts = find_bare_excepts(py_file)
            if bare_excepts:
                findings[py_file.relative_to(root)] = bare_excepts

    return findings


def main() -> int:
    """Main entry point."""
    root = Path(__file__).parent.parent.parent

    findings = check_files(root)

    print("=" * 60)
    print("BARE EXCEPT CHECK")
    print("=" * 60)

    if findings:
        total = sum(len(v) for v in findings.values())
        print(f"\n⚠️  Found {total} bare except clauses in {len(findings)} files:")

        for path, excepts in sorted(findings.items()):
            print(f"\n  {path}:")
            for line_no, context in excepts:
                print(f"    Line {line_no}: {context}")
    else:
        print("\n✅ No bare except clauses found")

    print()

    # Advisory only - ruff handles enforcement
    return 0


if __name__ == "__main__":
    sys.exit(main())
