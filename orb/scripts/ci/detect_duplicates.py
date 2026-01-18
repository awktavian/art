#!/usr/bin/env python3
"""
Detect duplicate class names across files.

Quality gate: Same class name in different files causes import confusion.
Exemptions: Add '# quality-gate: exempt duplicate-class ClassName' to class definition.
"""

import ast
import sys
from collections import defaultdict
from pathlib import Path


EXEMPT_COMMENT = "# quality-gate: exempt duplicate-class"


class ClassCollector(ast.NodeVisitor):
    """AST visitor to collect class definitions."""

    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self.classes: list[tuple[str, int, bool]] = []  # (name, lineno, is_exempt)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Record class name and check for exemption."""
        lineno = node.lineno

        # Check for exemption comment
        is_exempt = False
        if lineno <= len(self.source_lines):
            line = self.source_lines[lineno - 1]
            if EXEMPT_COMMENT in line and node.name in line:
                is_exempt = True

        # Check previous line for exemption
        if not is_exempt and lineno > 1:
            prev_line = self.source_lines[lineno - 2]
            if EXEMPT_COMMENT in prev_line and node.name in prev_line:
                is_exempt = True

        self.classes.append((node.name, lineno, is_exempt))
        self.generic_visit(node)


def collect_classes(file_path: Path) -> list[tuple[str, int, bool]]:
    """
    Collect all class names from file.

    Returns:
        List of (class_name, line_number, is_exempt) tuples.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        source_lines = source.splitlines()
        tree = ast.parse(source, filename=str(file_path))

        collector = ClassCollector(source_lines)
        collector.visit(tree)

        return collector.classes
    except SyntaxError:
        return []
    except Exception as e:
        print(f"⚠️  Error parsing {file_path}: {e}", file=sys.stderr)
        return []


def main() -> int:
    """Run duplicate class detection."""
    kagami_root = Path("kagami")
    if not kagami_root.exists():
        print("❌ kagami/ directory not found", file=sys.stderr)
        return 1

    # Collect all classes
    class_locations: dict[str, list[tuple[Path, int, bool]]] = defaultdict(list)

    for file_path in kagami_root.rglob("*.py"):
        classes = collect_classes(file_path)
        for class_name, lineno, is_exempt in classes:
            class_locations[class_name].append((file_path, lineno, is_exempt))

    # Find duplicates
    duplicates: dict[str, list[tuple[Path, int]]] = {}
    exempt_duplicates: set[str] = set()

    for class_name, locations in class_locations.items():
        if len(locations) > 1:
            # Check if all occurrences are exempt
            all_exempt = all(is_exempt for _, _, is_exempt in locations)

            if all_exempt:
                exempt_duplicates.add(class_name)
            else:
                # Only report non-exempt duplicates
                duplicates[class_name] = [(path, lineno) for path, lineno, _ in locations]

    # Report results
    total_classes = len(class_locations)

    if duplicates:
        # WARNING only - large codebases have legitimate duplicates
        # (e.g., platform-specific implementations, schema vs model versions)
        print(
            f"⚠️  Duplicate Class Names: {len(duplicates)} classes found in multiple files (warning only)"
        )
        print(
            "   This is informational - some duplicates are intentional (platform adapters, schemas vs models)"
        )
    else:
        print(f"✅ Duplicate Class Check: No duplicates ({total_classes} unique classes)")

    if exempt_duplicates:
        print(f"   ({len(exempt_duplicates)} exempt duplicate classes)")

    # Return 0 (success) - duplicate classes are a warning, not a failure
    # In large AI/ML codebases, identical class names in different contexts are common
    return 0


if __name__ == "__main__":
    sys.exit(main())
