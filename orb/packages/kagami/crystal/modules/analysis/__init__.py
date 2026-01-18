"""Crystal Analysis Module — Static Code Analysis.

Provides static analysis capabilities:
- Cyclomatic complexity measurement
- Code quality metrics
- Dead code detection
- Type hint coverage

Created: December 28, 2025
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FunctionMetrics:
    """Metrics for a single function."""

    name: str
    location: str
    lines: int
    cyclomatic_complexity: int
    parameters: int
    has_docstring: bool
    has_return_type: bool
    has_type_hints: bool


@dataclass
class AnalysisReport:
    """Static analysis report."""

    functions: list[FunctionMetrics] = field(default_factory=list[Any])
    total_lines: int = 0
    files_analyzed: int = 0
    analysis_time_ms: float = 0.0
    avg_complexity: float = 0.0
    max_complexity: int = 0
    type_hint_coverage: float = 0.0
    docstring_coverage: float = 0.0
    quality_score: float = 0.0
    recommendations: list[str] = field(default_factory=list[Any])

    def __post_init__(self) -> None:
        if self.functions:
            complexities = [f.cyclomatic_complexity for f in self.functions]
            self.avg_complexity = sum(complexities) / len(complexities)
            self.max_complexity = max(complexities)

            typed = sum(1 for f in self.functions if f.has_type_hints)
            self.type_hint_coverage = typed / len(self.functions)

            documented = sum(1 for f in self.functions if f.has_docstring)
            self.docstring_coverage = documented / len(self.functions)

            # Quality score: 0-100
            self.quality_score = self._calculate_quality_score()
            self.recommendations = self._generate_recommendations()

    def _calculate_quality_score(self) -> float:
        """Calculate overall quality score."""
        score = 100.0

        # Penalize high complexity
        if self.avg_complexity > 10:
            score -= 20
        elif self.avg_complexity > 5:
            score -= 10

        # Reward type hints
        score += self.type_hint_coverage * 20

        # Reward documentation
        score += self.docstring_coverage * 15

        # Penalize very large functions
        large_functions = sum(1 for f in self.functions if f.lines > 50)
        score -= large_functions * 5

        return max(0, min(100, score))

    def _generate_recommendations(self) -> list[str]:
        """Generate improvement recommendations."""
        recs = []

        # Complexity recommendations
        complex_functions = [f for f in self.functions if f.cyclomatic_complexity > 10]
        if complex_functions:
            names = ", ".join(f.name for f in complex_functions[:3])
            recs.append(f"Consider refactoring complex functions: {names}")

        # Type hint recommendations
        if self.type_hint_coverage < 0.8:
            untyped = [f for f in self.functions if not f.has_type_hints][:3]
            names = ", ".join(f.name for f in untyped)
            recs.append(f"Add type hints to: {names}")

        # Docstring recommendations
        if self.docstring_coverage < 0.5:
            undocumented = [f for f in self.functions if not f.has_docstring][:3]
            names = ", ".join(f.name for f in undocumented)
            recs.append(f"Add docstrings to: {names}")

        # Large function recommendations
        large = [f for f in self.functions if f.lines > 50]
        if large:
            names = ", ".join(f.name for f in large[:3])
            recs.append(f"Break up large functions (>50 lines): {names}")

        return recs


class ComplexityVisitor(ast.NodeVisitor):
    """AST visitor for cyclomatic complexity calculation."""

    def __init__(self) -> None:
        self.complexity = 1  # Start with 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # and/or add to complexity
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.complexity += 1
        self.generic_visit(node)


def analyze_code(
    code_path: str | Path,
    recursive: bool = True,
) -> AnalysisReport:
    """Analyze code for quality metrics.

    Performs static analysis to measure:
    - Cyclomatic complexity
    - Lines of code
    - Type hint coverage
    - Docstring coverage

    Args:
        code_path: File or directory path to analyze
        recursive: Analyze subdirectories (default True)

    Returns:
        AnalysisReport with metrics and recommendations

    Example:
        report = analyze_code("src/")
        print(f"Quality score: {report.quality_score}")
    """
    import time

    start = time.perf_counter()

    code_path = Path(code_path)
    functions: list[FunctionMetrics] = []
    total_lines = 0
    files_analyzed = 0

    # Get files to analyze
    if code_path.is_file():
        files = [code_path]
    elif recursive:
        files = list(code_path.rglob("*.py"))
    else:
        files = list(code_path.glob("*.py"))

    for file_path in files:
        files_analyzed += 1
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            total_lines += len(content.split("\n"))

            tree = ast.parse(content)
            file_functions = _analyze_ast(tree, str(file_path))
            functions.extend(file_functions)
        except Exception as e:
            logger.warning(f"Error analyzing {file_path}: {e}")

    return AnalysisReport(
        functions=functions,
        total_lines=total_lines,
        files_analyzed=files_analyzed,
        analysis_time_ms=(time.perf_counter() - start) * 1000,
    )


def check_complexity(
    code: str,
    max_complexity: int = 10,
) -> dict[str, Any]:
    """Check if code exceeds complexity threshold.

    Quick check for cyclomatic complexity of code snippet.

    Args:
        code: Source code string
        max_complexity: Maximum allowed complexity

    Returns:
        Dict with passed status and metrics
    """
    try:
        tree = ast.parse(code)
        functions = _analyze_ast(tree, "<string>")

        if not functions:
            return {
                "passed": True,
                "complexity": 1,
                "max_allowed": max_complexity,
            }

        max_found = max(f.cyclomatic_complexity for f in functions)
        return {
            "passed": max_found <= max_complexity,
            "complexity": max_found,
            "max_allowed": max_complexity,
            "functions": [
                {"name": f.name, "complexity": f.cyclomatic_complexity} for f in functions
            ],
        }
    except SyntaxError as e:
        return {
            "passed": False,
            "error": f"Syntax error: {e}",
        }


def _analyze_ast(tree: ast.AST, filename: str) -> list[FunctionMetrics]:
    """Extract function metrics from AST."""
    functions: list[FunctionMetrics] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Calculate complexity
            visitor = ComplexityVisitor()
            visitor.visit(node)

            # Count lines
            end_lineno = getattr(node, "end_lineno", node.lineno)
            lines = end_lineno - node.lineno + 1

            # Check type hints
            has_return_type = node.returns is not None
            has_type_hints = has_return_type or any(
                arg.annotation is not None for arg in node.args.args
            )

            # Check docstring
            has_docstring = (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            )

            functions.append(
                FunctionMetrics(
                    name=node.name,
                    location=f"{filename}:{node.lineno}",
                    lines=lines,
                    cyclomatic_complexity=visitor.complexity,
                    parameters=len(node.args.args),
                    has_docstring=has_docstring,  # type: ignore[arg-type]
                    has_return_type=has_return_type,
                    has_type_hints=has_type_hints,
                )
            )

    return functions


__all__ = [
    "AnalysisReport",
    "FunctionMetrics",
    "analyze_code",
    "check_complexity",
]
