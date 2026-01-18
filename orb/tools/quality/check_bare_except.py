#!/usr/bin/env python3
"""
Detect bare except clauses without exception types.

Quality gate: Bare 'except:' catches all exceptions, including SystemExit and KeyboardInterrupt.
Exemptions: Add '# quality-gate: exempt bare-except' on same line or line before.
"""

import ast
import sys
from pathlib import Path


EXEMPT_COMMENT = "# quality-gate: exempt bare-except"


class BareExceptVisitor(ast.NodeVisitor):
    """AST visitor to find bare except clauses."""

    def __init__(self, source_lines: list[str]):
        self.source_lines = source_lines
        self.violations: list[tuple[int, str]] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Check if except handler has no type."""
        if node.type is None:  # Bare except:
            lineno = node.lineno

            # Check for exemption comment
            is_exempt = False

            # Check same line
            if lineno <= len(self.source_lines):
                line = self.source_lines[lineno - 1]
                if EXEMPT_COMMENT in line:
                    is_exempt = True

            # Check previous line
            if not is_exempt and lineno > 1:
                prev_line = self.source_lines[lineno - 2]
                if EXEMPT_COMMENT in prev_line:
                    is_exempt = True

            if not is_exempt:
                context = (
                    self.source_lines[lineno - 1].strip()
                    if lineno <= len(self.source_lines)
                    else ""
                )
                self.violations.append((lineno, context))

        self.generic_visit(node)


def check_bare_except(file_path: Path) -> list[tuple[int, str]]:
    """
    Check file for bare except clauses.

    Returns:
        List of (line_number, context) tuples for violations.
    """
    try:
        source = file_path.read_text(encoding="utf-8")
        source_lines = source.splitlines()
        tree = ast.parse(source, filename=str(file_path))

        visitor = BareExceptVisitor(source_lines)
        visitor.visit(tree)

        return visitor.violations
    except SyntaxError:
        # Skip files with syntax errors (caught by other linters)
        return []
    except Exception as e:
        print(f"⚠️  Error parsing {file_path}: {e}", file=sys.stderr)
        return []


def main() -> int:
    """Run bare except check on Python files."""
    kagami_root = Path("kagami")
    if not kagami_root.exists():
        print("❌ kagami/ directory not found", file=sys.stderr)
        return 1

    # Find all Python files
    python_files = list(kagami_root.rglob("*.py"))

    all_violations: dict[Path, list[tuple[int, str]]] = {}

    for file_path in python_files:
        violations = check_bare_except(file_path)
        if violations:
            all_violations[file_path] = violations

    # Report results
    if all_violations:
        total_violations = sum(len(v) for v in all_violations.values())
        print(
            f"\n❌ Bare Except Violations: {total_violations} found in {len(all_violations)} files\n"
        )

        for file_path, violations in sorted(all_violations.items()):
            print(f"\n{file_path}:")
            for lineno, context in violations:
                print(f"  Line {lineno}: {context}")

        print(f"\nTo exempt, add '{EXEMPT_COMMENT}' on same line or line before.")
        print("Prefer: except Exception:  or  except (TypeError, ValueError):\n")
        return 1

    print(f"✅ Bare Except Check: No violations in {len(python_files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
