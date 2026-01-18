#!/usr/bin/env python3
"""
Check type annotation coverage in Python files.

Quality gate: Minimum 80% of functions must have type annotations.
Exemptions: Add '# quality-gate: exempt type-coverage' to first 10 lines.
"""

import ast
import sys
from pathlib import Path


MIN_COVERAGE = 0.80
EXEMPT_COMMENT = "# quality-gate: exempt type-coverage"


class TypeAnnotationChecker(ast.NodeVisitor):
    """AST visitor to count type annotations."""

    def __init__(self):
        self.total_functions = 0
        self.annotated_functions = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Count function with/without type annotations."""
        # Skip private/dunder methods (convention exemption)
        if node.name.startswith("_"):
            self.generic_visit(node)
            return

        self.total_functions += 1

        # Check if function has return annotation
        has_return = node.returns is not None

        # Check if all arguments have annotations
        args_annotated = all(
            arg.annotation is not None
            for arg in node.args.args
            if arg.arg != "self" and arg.arg != "cls"
        )

        if has_return and args_annotated:
            self.annotated_functions += 1

        self.generic_visit(node)


def check_type_coverage(file_path: Path) -> tuple[float, int, int, bool]:
    """
    Check type annotation coverage for file.

    Returns:
        (coverage, annotated_count, total_count, is_exempt)
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        lines = source.splitlines()

        # Check for exemption
        is_exempt = any(EXEMPT_COMMENT in line for line in lines[:10])

        tree = ast.parse(source, filename=str(file_path))
        checker = TypeAnnotationChecker()
        checker.visit(tree)

        if checker.total_functions == 0:
            return 1.0, 0, 0, is_exempt

        coverage = checker.annotated_functions / checker.total_functions
        return coverage, checker.annotated_functions, checker.total_functions, is_exempt

    except SyntaxError:
        return 1.0, 0, 0, False
    except Exception as e:
        print(f"⚠️  Error analyzing {file_path}: {e}", file=sys.stderr)
        return 1.0, 0, 0, False


def main() -> int:
    """Run type coverage check."""
    kagami_root = Path("kagami")
    if not kagami_root.exists():
        print("❌ kagami/ directory not found", file=sys.stderr)
        return 1

    # Find all Python files
    python_files = list(kagami_root.rglob("*.py"))

    violations: list[tuple[Path, float, int, int]] = []
    exempt_files: list[Path] = []

    total_annotated = 0
    total_functions = 0

    for file_path in python_files:
        coverage, annotated, total, is_exempt = check_type_coverage(file_path)

        total_annotated += annotated
        total_functions += total

        if is_exempt:
            exempt_files.append(file_path)
        elif coverage < MIN_COVERAGE and total > 0:
            violations.append((file_path, coverage, annotated, total))

    # Report results
    if violations:
        print(
            f"\n❌ Type Coverage Violations: {len(violations)} files below {MIN_COVERAGE * 100:.0f}% coverage\n"
        )

        for file_path, coverage, annotated, total in sorted(violations, key=lambda x: x[1]):
            print(f"  {file_path}: {coverage * 100:.1f}% ({annotated}/{total} functions)")

        print(f"\nTo exempt, add '{EXEMPT_COMMENT}' to first 10 lines.")
        print("Add type hints: def func(arg: Type) -> ReturnType:\n")
        return 1

    overall_coverage = total_annotated / total_functions if total_functions > 0 else 1.0
    print(
        f"✅ Type Coverage: {overall_coverage * 100:.1f}% ({total_annotated}/{total_functions} functions)"
    )
    if exempt_files:
        print(f"   ({len(exempt_files)} exempt files)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
