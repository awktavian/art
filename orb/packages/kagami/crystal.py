"""Crystal Capability Layer — Verification Infrastructure (CONSOLIDATED).

Crystal (e₇, Parabolic catastrophe, D₅) is The Judge.
This module provides verification, testing, security, and analysis tools.

MODULES (consolidated from kagami/crystal/):
============================================
- verification: Formal verification (Z3, Prolog, TIC)
- security: Security scanning and vulnerability detection
- testing: Test generation and property-based testing
- analysis: Static code analysis

USAGE:
======
from kagami.crystal import (
    run_verification,
    security_scan,
    generate_tests,
    analyze_code,
)

Created: December 28, 2025
Consolidated: December 31, 2025
"""

from __future__ import annotations

import ast
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# VERIFICATION MODULE
# =============================================================================


@dataclass
class VerificationResult:
    """Result of a verification operation."""

    verified: bool
    tool: str
    proof_time_ms: float = 0.0
    counter_example: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    crystal_verdict: str = ""

    def __post_init__(self) -> None:
        if not self.crystal_verdict:
            self.crystal_verdict = f"{'PROVED' if self.verified else 'DISPROVED'} via {self.tool}"


def run_verification(
    pre: str,
    post: str,
    variables: dict[str, str],
    tool: str = "z3",
) -> VerificationResult:
    """Run formal verification on pre/post conditions."""
    start = time.perf_counter()

    if tool == "z3":
        result = _verify_with_z3(pre, post, variables)
    elif tool == "prolog":
        result = _verify_with_prolog(pre, post, variables)
    else:
        result = VerificationResult(
            verified=False,
            tool=tool,
            details={"error": f"Unknown tool: {tool}"},
        )

    result.proof_time_ms = (time.perf_counter() - start) * 1000
    return result


def verify_invariant(
    pre_condition: str,
    post_condition: str,
    variables: dict[str, str],
) -> VerificationResult:
    """Verify an API invariant using Z3."""
    return run_verification(pre_condition, post_condition, variables, tool="z3")


def verify_reachability(
    edges: list[tuple[str, str]],
    from_node: str,
    to_node: str,
) -> VerificationResult:
    """Verify graph reachability using Prolog."""
    start = time.perf_counter()

    try:
        from kagami.core.reasoning.symbolic.prolog_engine import KnowledgeBase

        kb = KnowledgeBase()
        for src, dst in edges:
            kb.add_edge(src, dst)

        reachable = kb.is_reachable(from_node, to_node)

        return VerificationResult(
            verified=reachable,
            tool="prolog",
            proof_time_ms=(time.perf_counter() - start) * 1000,
            details={"from": from_node, "to": to_node, "edge_count": len(edges)},
            crystal_verdict=(
                f"PROVED: {to_node} is reachable from {from_node}."
                if reachable
                else f"DISPROVED: No path exists from {from_node} to {to_node}."
            ),
        )
    except Exception as e:
        logger.error(f"Prolog reachability failed: {e}")
        return VerificationResult(
            verified=False,
            tool="prolog",
            proof_time_ms=(time.perf_counter() - start) * 1000,
            details={"error": str(e)},
        )


def _verify_with_z3(pre: str, post: str, variables: dict[str, str]) -> VerificationResult:
    """Verify using Z3 SMT solver."""
    try:
        from kagami.core.reasoning.symbolic.z3_solver import Z3ConstraintSolver

        solver = Z3ConstraintSolver()
        result = solver.verify_api_invariant(
            pre_condition=pre,
            post_condition=post,
            variables=variables,
        )

        return VerificationResult(
            verified=result.get("verified", False),
            tool="z3",
            counter_example=result.get("counterexample"),
            details=result,
            crystal_verdict=(
                "Invariant PROVED. The evidence supports the claim."
                if result.get("verified")
                else f"Invariant FAILED. Counterexample: {result.get('counterexample', 'unknown')}"
            ),
        )
    except Exception as e:
        logger.error(f"Z3 verification failed: {e}")
        return VerificationResult(verified=False, tool="z3", details={"error": str(e)})


def _verify_with_prolog(pre: str, post: str, variables: dict[str, str]) -> VerificationResult:
    """Verify using Prolog logic programming."""
    return VerificationResult(
        verified=False,
        tool="prolog",
        details={"error": "Prolog better suited for graph reachability queries"},
    )


# =============================================================================
# SECURITY MODULE
# =============================================================================


class Severity(Enum):
    """Vulnerability severity levels."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Vulnerability:
    """A detected vulnerability."""

    name: str
    severity: Severity
    description: str
    location: str
    recommendation: str
    cwe_id: str | None = None


@dataclass
class SecurityReport:
    """Security scan report."""

    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    files_scanned: int = 0
    scan_time_ms: float = 0.0
    passed: bool = True
    summary: str = ""

    def __post_init__(self) -> None:
        self.passed = not any(
            v.severity in (Severity.HIGH, Severity.CRITICAL) for v in self.vulnerabilities
        )
        critical = sum(1 for v in self.vulnerabilities if v.severity == Severity.CRITICAL)
        high = sum(1 for v in self.vulnerabilities if v.severity == Severity.HIGH)
        medium = sum(1 for v in self.vulnerabilities if v.severity == Severity.MEDIUM)
        self.summary = (
            f"Scanned {self.files_scanned} files. "
            f"Found: {critical} critical, {high} high, {medium} medium vulnerabilities."
        )


VULN_PATTERNS = {
    "hardcoded_secret": {
        "pattern": r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']',
        "severity": Severity.HIGH,
        "description": "Hardcoded secret or credential detected",
        "recommendation": "Use environment variables or secrets manager",
        "cwe_id": "CWE-798",
    },
    "sql_injection": {
        "pattern": r'(?:execute|cursor\.execute)\s*\(\s*[f"\'].*%s.*["\']',
        "severity": Severity.CRITICAL,
        "description": "Potential SQL injection vulnerability",
        "recommendation": "Use parameterized queries",
        "cwe_id": "CWE-89",
    },
    "command_injection": {
        "pattern": r'(?:os\.system|subprocess\.call|subprocess\.run)\s*\([^)]*(?:\+|format|f")',
        "severity": Severity.CRITICAL,
        "description": "Potential command injection vulnerability",
        "recommendation": "Use subprocess with list arguments, avoid string concatenation",
        "cwe_id": "CWE-78",
    },
    "path_traversal": {
        "pattern": r'open\s*\([^)]*(?:\+|format|f")[^)]*\.\.',
        "severity": Severity.HIGH,
        "description": "Potential path traversal vulnerability",
        "recommendation": "Validate and sanitize file paths",
        "cwe_id": "CWE-22",
    },
    "eval_usage": {
        "pattern": r"\beval\s*\(",
        "severity": Severity.HIGH,
        "description": "Use of eval() is dangerous",
        "recommendation": "Avoid eval(), use ast.literal_eval() for data parsing",
        "cwe_id": "CWE-94",
    },
    "pickle_usage": {
        "pattern": r"\bpickle\.loads?\s*\(",
        "severity": Severity.MEDIUM,
        "description": "Pickle deserialization can be dangerous with untrusted data",
        "recommendation": "Use safer serialization (JSON) for untrusted data",
        "cwe_id": "CWE-502",
    },
    "debug_enabled": {
        "pattern": r"DEBUG\s*=\s*True",
        "severity": Severity.LOW,
        "description": "Debug mode enabled",
        "recommendation": "Ensure DEBUG is False in production",
        "cwe_id": "CWE-489",
    },
}


def security_scan(
    code_path: str | Path,
    patterns: dict[str, Any] | None = None,
    recursive: bool = True,
    extensions: tuple[str, ...] = (".py",),
) -> SecurityReport:
    """Scan code for security vulnerabilities."""
    start = time.perf_counter()

    code_path = Path(code_path)
    scan_patterns = {**VULN_PATTERNS, **(patterns or {})}
    vulnerabilities: list[Vulnerability] = []
    files_scanned = 0

    if code_path.is_file():
        files = [code_path]
    elif recursive:
        files = [f for ext in extensions for f in code_path.rglob(f"*{ext}")]
    else:
        files = [f for ext in extensions for f in code_path.glob(f"*{ext}")]

    for file_path in files:
        files_scanned += 1
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            for name, pattern_info in scan_patterns.items():
                pattern = pattern_info["pattern"]
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        vulnerabilities.append(
                            Vulnerability(
                                name=name,
                                severity=pattern_info["severity"],
                                description=pattern_info["description"],
                                location=f"{file_path}:{i}",
                                recommendation=pattern_info["recommendation"],
                                cwe_id=pattern_info.get("cwe_id"),
                            )
                        )
        except Exception as e:
            logger.warning(f"Error scanning {file_path}: {e}")

    return SecurityReport(
        vulnerabilities=vulnerabilities,
        files_scanned=files_scanned,
        scan_time_ms=(time.perf_counter() - start) * 1000,
    )


def find_vulnerabilities(code: str, filename: str = "<string>") -> list[Vulnerability]:
    """Find vulnerabilities in a code string."""
    vulnerabilities: list[Vulnerability] = []
    lines = code.split("\n")

    for name, pattern_info in VULN_PATTERNS.items():
        pattern = pattern_info["pattern"]
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line, re.IGNORECASE):
                vulnerabilities.append(
                    Vulnerability(
                        name=name,
                        severity=pattern_info["severity"],
                        description=pattern_info["description"],
                        location=f"{filename}:{i}",
                        recommendation=pattern_info["recommendation"],
                        cwe_id=pattern_info.get("cwe_id"),
                    )
                )

    return vulnerabilities


# =============================================================================
# TESTING MODULE
# =============================================================================


@dataclass
class TestCase:
    """A single test case."""

    name: str
    inputs: dict[str, Any]
    expected: Any | None = None
    description: str = ""
    is_edge_case: bool = False


@dataclass
class TestSuite:
    """A collection of test cases."""

    name: str
    test_cases: list[TestCase] = field(default_factory=list)
    function_name: str = ""
    coverage_hints: list[str] = field(default_factory=list)

    def to_pytest(self) -> str:
        """Generate pytest code for this test suite."""
        lines = [
            "import pytest",
            "",
            f"# Test suite for {self.function_name}",
            "# Generated by Crystal verification module",
            "",
        ]

        for tc in self.test_cases:
            test_name = tc.name.replace(" ", "_").lower()
            lines.append(f"def test_{test_name}():")
            if tc.description:
                lines.append(f'    """{tc.description}"""')

            args = ", ".join(f"{k}={v!r}" for k, v in tc.inputs.items())
            if tc.expected is not None:
                lines.append(f"    result = {self.function_name}({args})")
                lines.append(f"    assert result == {tc.expected!r}")
            else:
                lines.append("    # No expected value provided")
                lines.append(f"    result = {self.function_name}({args})")
                lines.append("    assert result is not None  # Basic assertion")
            lines.append("")

        return "\n".join(lines)


def generate_tests(
    function_signature: str,
    function_name: str | None = None,
    num_tests: int = 5,
    include_edge_cases: bool = True,
) -> TestSuite:
    """Generate test cases from a function signature."""
    parsed = _parse_signature(function_signature)
    fn_name = function_name or parsed["name"]
    params = parsed["params"]

    test_cases: list[TestCase] = []

    for i in range(num_tests):
        inputs = {}
        for param_name, param_type in params.items():
            inputs[param_name] = _generate_value(param_type, i)

        test_cases.append(
            TestCase(
                name=f"{fn_name}_test_{i + 1}",
                inputs=inputs,
                description=f"Test case {i + 1} for {fn_name}",
            )
        )

    if include_edge_cases:
        edge_cases = _generate_edge_cases(params)
        for i, edge in enumerate(edge_cases):
            test_cases.append(
                TestCase(
                    name=f"{fn_name}_edge_{i + 1}",
                    inputs=edge,
                    description=f"Edge case {i + 1}",
                    is_edge_case=True,
                )
            )

    return TestSuite(name=f"TestSuite_{fn_name}", test_cases=test_cases, function_name=fn_name)


def generate_property_tests(function_signature: str, properties: list[str] | None = None) -> str:
    """Generate property-based tests using Hypothesis."""
    parsed = _parse_signature(function_signature)
    fn_name = parsed["name"]
    params = parsed["params"]

    lines = [
        "import pytest",
        "from hypothesis import given, strategies as st",
        "",
        f"# Property-based tests for {fn_name}",
        "",
    ]

    strategies = []
    for param_name, param_type in params.items():
        strategy = _type_to_hypothesis_strategy(param_type)
        strategies.append(f"{param_name}={strategy}")

    strategy_str = ", ".join(strategies)

    lines.append(f"@given({strategy_str})")
    args = ", ".join(params.keys())
    lines.append(f"def test_{fn_name}_properties({args}):")
    lines.append(f"    result = {fn_name}({args})")

    if properties:
        for prop in properties:
            lines.append(f"    assert {prop}")
    else:
        lines.append("    # Add property assertions here")
        lines.append("    assert result is not None")

    lines.append("")

    return "\n".join(lines)


def _parse_signature(signature: str) -> dict[str, Any]:
    """Parse a function signature string."""
    name_match = re.search(r"def\s+(\w+)", signature)
    fn_name = name_match.group(1) if name_match else "unknown"

    params_match = re.search(r"\(([^)]*)\)", signature)
    params: dict[str, str] = {}

    if params_match:
        params_str = params_match.group(1)
        for param in params_str.split(","):
            param = param.strip()
            if ":" in param:
                name, type_hint = param.split(":", 1)
                params[name.strip()] = type_hint.strip()
            elif param:
                params[param] = "Any"

    return {"name": fn_name, "params": params}


def _generate_value(type_hint: str, seed: int) -> Any:
    """Generate a test value for a type hint."""
    type_hint = type_hint.strip()

    if type_hint in ("int", "integer"):
        return [0, 1, -1, 42, 100][seed % 5]
    elif type_hint in ("float", "double"):
        return [0.0, 1.0, -1.0, 3.14, 0.001][seed % 5]
    elif type_hint in ("str", "string"):
        return ["", "hello", "test", "abc123", "special!@#"][seed % 5]
    elif type_hint in ("bool", "boolean"):
        return seed % 2 == 0
    elif type_hint.startswith("list"):
        return [[], [1], [1, 2], [1, 2, 3], list(range(10))][seed % 5]
    elif type_hint.startswith("dict"):
        return [{}, {"a": 1}, {"a": 1, "b": 2}][seed % 3]
    elif type_hint == "None":
        return None
    else:
        return f"<{type_hint}>"


def _generate_edge_cases(params: dict[str, str]) -> list[dict[str, Any]]:
    """Generate edge case inputs."""
    edge_cases = []

    boundaries = {
        "int": [0, -1, 1, 2**31 - 1, -(2**31)],
        "float": [0.0, -0.0, float("inf"), float("-inf"), float("nan")],
        "str": ["", " ", "\n", "\t", "a" * 1000],
        "bool": [True, False],
        "list": [[], [None], list(range(1000))],
    }

    for param_name, param_type in params.items():
        type_key = param_type.strip().lower()
        if type_key in boundaries:
            for boundary_value in boundaries[type_key][:2]:
                inputs = {p: _generate_value(t, 0) for p, t in params.items()}
                inputs[param_name] = boundary_value
                edge_cases.append(inputs)

    return edge_cases[:5]


def _type_to_hypothesis_strategy(type_hint: str) -> str:
    """Convert type hint to Hypothesis strategy."""
    type_hint = type_hint.strip().lower()

    strategies = {
        "int": "st.integers()",
        "float": "st.floats(allow_nan=False)",
        "str": "st.text(max_size=100)",
        "bool": "st.booleans()",
        "list": "st.lists(st.integers())",
        "dict": "st.dictionaries(st.text(), st.integers())",
    }

    return strategies.get(type_hint, "st.none()")


# =============================================================================
# ANALYSIS MODULE
# =============================================================================


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

    functions: list[FunctionMetrics] = field(default_factory=list)
    total_lines: int = 0
    files_analyzed: int = 0
    analysis_time_ms: float = 0.0
    avg_complexity: float = 0.0
    max_complexity: int = 0
    type_hint_coverage: float = 0.0
    docstring_coverage: float = 0.0
    quality_score: float = 0.0
    recommendations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.functions:
            complexities = [f.cyclomatic_complexity for f in self.functions]
            self.avg_complexity = sum(complexities) / len(complexities)
            self.max_complexity = max(complexities)

            typed = sum(1 for f in self.functions if f.has_type_hints)
            self.type_hint_coverage = typed / len(self.functions)

            documented = sum(1 for f in self.functions if f.has_docstring)
            self.docstring_coverage = documented / len(self.functions)

            self.quality_score = self._calculate_quality_score()
            self.recommendations = self._generate_recommendations()

    def _calculate_quality_score(self) -> float:
        """Calculate overall quality score."""
        score = 100.0

        if self.avg_complexity > 10:
            score -= 20
        elif self.avg_complexity > 5:
            score -= 10

        score += self.type_hint_coverage * 20
        score += self.docstring_coverage * 15

        large_functions = sum(1 for f in self.functions if f.lines > 50)
        score -= large_functions * 5

        return max(0, min(100, score))

    def _generate_recommendations(self) -> list[str]:
        """Generate improvement recommendations."""
        recs = []

        complex_functions = [f for f in self.functions if f.cyclomatic_complexity > 10]
        if complex_functions:
            names = ", ".join(f.name for f in complex_functions[:3])
            recs.append(f"Consider refactoring complex functions: {names}")

        if self.type_hint_coverage < 0.8:
            untyped = [f for f in self.functions if not f.has_type_hints][:3]
            names = ", ".join(f.name for f in untyped)
            recs.append(f"Add type hints to: {names}")

        if self.docstring_coverage < 0.5:
            undocumented = [f for f in self.functions if not f.has_docstring][:3]
            names = ", ".join(f.name for f in undocumented)
            recs.append(f"Add docstrings to: {names}")

        large = [f for f in self.functions if f.lines > 50]
        if large:
            names = ", ".join(f.name for f in large[:3])
            recs.append(f"Break up large functions (>50 lines): {names}")

        return recs


class ComplexityVisitor(ast.NodeVisitor):
    """AST visitor for cyclomatic complexity calculation."""

    def __init__(self) -> None:
        self.complexity = 1

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
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.complexity += 1
        self.generic_visit(node)


def analyze_code(code_path: str | Path, recursive: bool = True) -> AnalysisReport:
    """Analyze code for quality metrics."""
    start = time.perf_counter()

    code_path = Path(code_path)
    functions: list[FunctionMetrics] = []
    total_lines = 0
    files_analyzed = 0

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


def check_complexity(code: str, max_complexity: int = 10) -> dict[str, Any]:
    """Check if code exceeds complexity threshold."""
    try:
        tree = ast.parse(code)
        functions = _analyze_ast(tree, "<string>")

        if not functions:
            return {"passed": True, "complexity": 1, "max_allowed": max_complexity}

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
        return {"passed": False, "error": f"Syntax error: {e}"}


def _analyze_ast(tree: ast.AST, filename: str) -> list[FunctionMetrics]:
    """Extract function metrics from AST."""
    functions: list[FunctionMetrics] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            visitor = ComplexityVisitor()
            visitor.visit(node)

            end_lineno = getattr(node, "end_lineno", node.lineno)
            lines = end_lineno - node.lineno + 1

            has_return_type = node.returns is not None
            has_type_hints = has_return_type or any(
                arg.annotation is not None for arg in node.args.args
            )

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
                    has_docstring=has_docstring,
                    has_return_type=has_return_type,
                    has_type_hints=has_type_hints,
                )
            )

    return functions


__all__ = [
    "AnalysisReport",
    "FunctionMetrics",
    "SecurityReport",
    "Severity",
    "TestCase",
    "TestSuite",
    "VerificationResult",
    "Vulnerability",
    "analyze_code",
    "check_complexity",
    "find_vulnerabilities",
    "generate_property_tests",
    "generate_tests",
    "run_verification",
    "security_scan",
    "verify_invariant",
    "verify_reachability",
]
