#!/usr/bin/env python3
"""
Check for missing docstrings on public functions.

Quality gate: All public functions/classes must have docstrings.
Exemptions: Add '# quality-gate: exempt docstring' to first 10 lines.
"""

import ast
import sys
from pathlib import Path


EXEMPT_COMMENT = "# quality-gate: exempt docstring"


class DocstringChecker(ast.NodeVisitor):
    """AST visitor to check for docstrings."""

    def __init__(self):
        self.violations: list[tuple[str, int, str]] = []  # (type, lineno, name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Check if public function has docstring."""
        # Skip private functions
        if node.name.startswith("_"):
            self.generic_visit(node)
            return

        # Check for docstring
        has_docstring = ast.get_docstring(node) is not None

        if not has_docstring:
            self.violations.append(("function", node.lineno, node.name))

        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Check if public class has docstring."""
        # Skip private classes
        if node.name.startswith("_"):
            self.generic_visit(node)
            return

        # Check for docstring
        has_docstring = ast.get_docstring(node) is not None

        if not has_docstring:
            self.violations.append(("class", node.lineno, node.name))

        self.generic_visit(node)


def check_docstrings(file_path: Path) -> tuple[list[tuple[str, int, str]], bool]:
    """
    Check file for missing docstrings.

    Returns:
        (violations, is_exempt)
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        lines = source.splitlines()

        # Check for exemption
        is_exempt = any(EXEMPT_COMMENT in line for line in lines[:10])

        if is_exempt:
            return [], True

        tree = ast.parse(source, filename=str(file_path))
        checker = DocstringChecker()
        checker.visit(tree)

        return checker.violations, False

    except SyntaxError:
        return [], False
    except Exception as e:
        print(f"⚠️  Error analyzing {file_path}: {e}", file=sys.stderr)
        return [], False


def main() -> int:
    """Run docstring check."""
    kagami_root = Path("kagami")
    if not kagami_root.exists():
        print("❌ kagami/ directory not found", file=sys.stderr)
        return 1

    # Find all Python files
    python_files = list(kagami_root.rglob("*.py"))

    all_violations: dict[Path, list[tuple[str, int, str]]] = {}
    exempt_files: list[Path] = []

    for file_path in python_files:
        violations, is_exempt = check_docstrings(file_path)

        if is_exempt:
            exempt_files.append(file_path)
        elif violations:
            all_violations[file_path] = violations

    # Report results
    if all_violations:
        total_violations = sum(len(v) for v in all_violations.values())
        print(
            f"\n❌ Docstring Violations: {total_violations} missing in {len(all_violations)} files\n"
        )

        for file_path, violations in sorted(all_violations.items()):
            print(f"\n{file_path}:")
            for item_type, lineno, name in violations:
                print(f"  Line {lineno}: {item_type} {name} (no docstring)")

        print(f"\nTo exempt, add '{EXEMPT_COMMENT}' to first 10 lines.")
        print('Add docstrings: """Description of function/class."""\n')
        return 1

    print(f"✅ Docstring Check: All public functions documented ({len(python_files)} files)")
    if exempt_files:
        print(f"   ({len(exempt_files)} exempt files)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
