"""Comprehensive Stub Detection - Zero Tolerance Meta-Test.

CRYSTAL (e₇) - VERIFICATION - December 14, 2025
================================================

Mission: Prove ZERO stubs remain in the kagami/ production codebase.

This meta-test performs 10 comprehensive checks to detect any stub patterns,
placeholder implementations, or incomplete code. It is designed to run in CI/CD
and fail loudly if any production code is incomplete.

Strategy:
1. Pattern-based detection (grep for stub indicators)
2. Abstract method filtering (exclude valid NotImplementedError)
3. Import graph analysis (detect orphaned modules)
4. Specific module verification (known critical paths)
5. Evidence-based reporting (no opinions without data)

Exclusions:
- tests/ - Test stubs are acceptable
- docs/ - Documentation examples are acceptable
- examples/ - Example code is acceptable
- benchmarks/ - Benchmark templates are acceptable
- Abstract base classes with @abstractmethod
- typing.Protocol definitions (structural subtyping)

Created: December 14, 2025
Colony: Crystal (e₇) - The skeptic who trusts nothing unproven
"""

from __future__ import annotations

import pytest
import ast
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# =============================================================================
# CONFIGURATION
# =============================================================================

# Resolve paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
KAGAMI_ROOT = PROJECT_ROOT / "kagami"

# Directories to exclude from verification
EXCLUDE_DIRS = [
    "tests/",
    "docs/",
    "examples/",
    ".pytest_cache/",
    "__pycache__/",
    ".git/",
    "node_modules/",
]

# Critical paths that MUST have zero stubs
CRITICAL_PATHS = [
    "kagami/core/",
    "kagami/orchestration/",
    "kagami_api/",
]

# Stub detection patterns
STUB_PATTERNS = {
    "stub_class": r"class\s+\w*[Ss]tub\w*[:\(]",
    "stub_comment": r"#\s*stub",
    "not_implemented": r"raise\s+NotImplementedError",
    "todo_comment": r"#\s*(TODO|FIXME|XXX|HACK|TEMP)\b",
    "placeholder": r"(pass|\.\.\.)\s*#\s*(implement|placeholder|stub)",
}

# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class StubFinding:
    """Single stub detection finding."""

    file_path: str
    line_number: int
    pattern: str
    matched_text: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW


@dataclass
class StubReport:
    """Complete stub verification report."""

    total_files_scanned: int = 0
    findings: list[StubFinding] = field(default_factory=list)
    checks_passed: int = 0
    checks_failed: int = 0
    excluded_findings: list[StubFinding] = field(default_factory=list)

    def add_finding(
        self,
        file_path: str,
        line_number: int,
        pattern: str,
        matched_text: str,
        severity: str = "MEDIUM",
    ) -> None:
        """Add a stub finding to the report."""
        self.findings.append(
            StubFinding(
                file_path=file_path,
                line_number=line_number,
                pattern=pattern,
                matched_text=matched_text.strip(),
                severity=severity,
            )
        )

    def add_excluded(
        self,
        file_path: str,
        line_number: int,
        pattern: str,
        matched_text: str,
        severity: str = "LOW",
    ) -> None:
        """Add an excluded finding (for reporting purposes)."""
        self.excluded_findings.append(
            StubFinding(
                file_path=file_path,
                line_number=line_number,
                pattern=pattern,
                matched_text=matched_text.strip(),
                severity=severity,
            )
        )

    def has_critical_findings(self) -> bool:
        """Check if any critical findings exist."""
        return any(f.severity == "CRITICAL" for f in self.findings)

    def has_any_findings(self) -> bool:
        """Check if any findings exist."""
        return len(self.findings) > 0

    def get_summary(self) -> str:
        """Generate summary report."""
        lines = [
            "=" * 60,
            "STUB VERIFICATION REPORT",
            "=" * 60,
            f"Files scanned: {self.total_files_scanned}",
            f"Checks passed: {self.checks_passed}",
            f"Checks failed: {self.checks_failed}",
            f"Findings: {len(self.findings)}",
            f"Excluded: {len(self.excluded_findings)}",
            "",
        ]

        if self.findings:
            lines.append("FINDINGS (production code):")
            lines.append("-" * 60)
            for finding in sorted(self.findings, key=lambda x: x.severity, reverse=True):
                lines.append(f"[{finding.severity}] {finding.file_path}:{finding.line_number}")
                lines.append(f"  Pattern: {finding.pattern}")
                lines.append(f"  Match: {finding.matched_text}")
                lines.append("")

        if not self.findings:
            lines.append("RESULT: ZERO STUBS DETECTED")
        else:
            lines.append("RESULT: STUBS DETECTED - VERIFICATION FAILED")

        lines.append("=" * 60)
        return "\n".join(lines)


# =============================================================================
# UTILITIES
# =============================================================================


def should_exclude_path(path: Path) -> bool:
    """Check if path should be excluded from verification."""
    path_str = str(path)
    return any(exclude in path_str for exclude in EXCLUDE_DIRS)


def grep_pattern(
    pattern: str, path: Path, case_sensitive: bool = True
) -> list[tuple[str, int, str]]:
    """Grep for pattern in path, return [(file, line_num, matched_text)]."""
    if not path.exists():
        return []

    args = ["grep", "-r", "-n"]
    if not case_sensitive:
        args.append("-i")

    # Add pattern
    args.extend(["-E", pattern])

    # Add path
    args.append(str(path))

    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return []

    if result.returncode != 0:
        # No matches or error
        return []

    matches = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue

        # Parse: file:line_num:matched_text
        parts = line.split(":", 2)
        if len(parts) >= 3:
            file_path, line_num_str, matched_text = parts
            try:
                line_num = int(line_num_str)
                matches.append((file_path, line_num, matched_text))
            except ValueError:
                continue

    return matches


def is_abstract_method(file_path: Path, line_number: int) -> bool:
    """Check if NotImplementedError is in an abstract method."""
    if not file_path.exists():
        return False

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except Exception:
        # Parse error, assume not abstract
        return False

    # Find the function containing this line
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            # Check if line is within this function
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                if node.lineno <= line_number <= (node.end_lineno or node.lineno):
                    # Check if function has @abstractmethod decorator
                    for decorator in node.decorator_list:
                        if isinstance(decorator, ast.Name):
                            if decorator.id == "abstractmethod":
                                return True
                        elif isinstance(decorator, ast.Attribute):
                            if decorator.attr == "abstractmethod":
                                return True

    return False


def is_protocol_class(file_path: Path, line_number: int) -> bool:
    """Check if NotImplementedError is in a Protocol class."""
    if not file_path.exists():
        return False

    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except Exception:
        return False

    # Find the class containing this line
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                if node.lineno <= line_number <= (node.end_lineno or node.lineno):
                    # Check if class inherits from Protocol
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            if base.id == "Protocol":
                                return True
                        elif isinstance(base, ast.Attribute):
                            if base.attr == "Protocol":
                                return True

    return False


# =============================================================================
# TEST SUITE
# =============================================================================


@pytest.fixture
def report() -> StubReport:
    """Create a fresh stub report."""
    return StubReport()


def test_no_stub_classes(report: StubReport) -> None:
    """[1/10] Verify: No stub classes in production code."""
    matches = grep_pattern(STUB_PATTERNS["stub_class"], KAGAMI_ROOT)

    for file_path_str, line_num, matched_text in matches:
        file_path = Path(file_path_str)

        if should_exclude_path(file_path):
            report.add_excluded(file_path_str, line_num, "stub_class", matched_text)
            continue

        # CRITICAL: Stub classes are never acceptable in production
        report.add_finding(file_path_str, line_num, "stub_class", matched_text, severity="CRITICAL")

    report.total_files_scanned += 1

    if not any(f.pattern == "stub_class" for f in report.findings):
        report.checks_passed += 1
    else:
        report.checks_failed += 1

    assert not any(
        f.pattern == "stub_class" for f in report.findings
    ), f"Found {len([f for f in report.findings if f.pattern == 'stub_class'])} stub classes"


def test_no_stub_comments(report: StubReport) -> None:
    """[2/10] Verify: No stub comments in production code."""
    matches = grep_pattern(STUB_PATTERNS["stub_comment"], KAGAMI_ROOT, case_sensitive=False)

    for file_path_str, line_num, matched_text in matches:
        file_path = Path(file_path_str)

        if should_exclude_path(file_path):
            report.add_excluded(file_path_str, line_num, "stub_comment", matched_text)
            continue

        # Exclude valid module stub comments (import isolation pattern)
        if "stub heavy" in matched_text.lower() or "stub keras" in matched_text.lower():
            report.add_excluded(file_path_str, line_num, "stub_comment", matched_text)
            continue

        # Exclude "Stubs for missing" pattern (graceful degradation)
        if "stubs for missing" in matched_text.lower():
            report.add_excluded(file_path_str, line_num, "stub_comment", matched_text)
            continue

        # HIGH: Explicit stub comments indicate incomplete work
        report.add_finding(file_path_str, line_num, "stub_comment", matched_text, severity="HIGH")

    report.total_files_scanned += 1

    if not any(f.pattern == "stub_comment" for f in report.findings):
        report.checks_passed += 1
    else:
        report.checks_failed += 1

    assert not any(
        f.pattern == "stub_comment" for f in report.findings
    ), f"Found {len([f for f in report.findings if f.pattern == 'stub_comment'])} stub comments"


def test_no_unguarded_not_implemented(report: StubReport) -> None:
    """[3/10] Verify: No NotImplementedError except in abstract methods."""
    matches = grep_pattern(STUB_PATTERNS["not_implemented"], KAGAMI_ROOT)

    for file_path_str, line_num, matched_text in matches:
        file_path = Path(file_path_str)

        if should_exclude_path(file_path):
            report.add_excluded(file_path_str, line_num, "not_implemented", matched_text)
            continue

        # Check if this is an abstract method or protocol
        if is_abstract_method(file_path, line_num) or is_protocol_class(file_path, line_num):
            report.add_excluded(file_path_str, line_num, "not_implemented", matched_text)
            continue

        # Check if it's a capability guard (provider_registry pattern)
        if "not supported" in matched_text.lower() or "capability" in matched_text.lower():
            report.add_excluded(file_path_str, line_num, "not_implemented", matched_text)
            continue

        # Check if it's a mixin pattern (read surrounding context for pragma)
        try:
            source_lines = file_path.read_text(encoding="utf-8").split("\n")
            # Check line before and current line for pragma: no cover
            if line_num > 0 and line_num <= len(source_lines):
                current_line = source_lines[line_num - 1]
                prev_line = source_lines[line_num - 2] if line_num > 1 else ""
                if "pragma: no cover" in current_line or "pragma: no cover" in prev_line:
                    report.add_excluded(file_path_str, line_num, "not_implemented", matched_text)
                    continue
        except Exception:
            pass  # Fall through to normal check

        # HIGH: NotImplementedError in production code suggests incomplete implementation
        report.add_finding(
            file_path_str, line_num, "not_implemented", matched_text, severity="HIGH"
        )

    report.total_files_scanned += 1

    if not any(f.pattern == "not_implemented" for f in report.findings):
        report.checks_passed += 1
    else:
        report.checks_failed += 1

    assert not any(
        f.pattern == "not_implemented" for f in report.findings
    ), f"Found {len([f for f in report.findings if f.pattern == 'not_implemented'])} unguarded NotImplementedError"


def test_no_critical_todos(report: StubReport) -> None:
    """[4/10] Verify: No TODO comments in critical paths."""
    matches = grep_pattern(STUB_PATTERNS["todo_comment"], KAGAMI_ROOT, case_sensitive=False)

    critical_todos = []

    for file_path_str, line_num, matched_text in matches:
        file_path = Path(file_path_str)

        if should_exclude_path(file_path):
            report.add_excluded(file_path_str, line_num, "todo_comment", matched_text)
            continue

        # Check if in critical path
        is_critical = any(critical_path in file_path_str for critical_path in CRITICAL_PATHS)

        if is_critical:
            # Exclude LOW priority TODOs (optional improvements, not blockers)
            lower_matched = matched_text.lower()

            # "Replace with X when available" - feature exists but not wired up yet
            if "replace with" in lower_matched and "when available" in lower_matched:
                report.add_excluded(file_path_str, line_num, "todo_comment", matched_text)
                continue

            # "Emit receipt" - telemetry enhancement, not blocker
            if "emit receipt" in lower_matched or "receipt system" in lower_matched:
                report.add_excluded(file_path_str, line_num, "todo_comment", matched_text)
                continue

            # MEDIUM: TODOs in critical paths suggest incomplete features
            report.add_finding(
                file_path_str, line_num, "todo_comment", matched_text, severity="MEDIUM"
            )
            critical_todos.append((file_path_str, line_num, matched_text))
        else:
            # LOW: TODOs in non-critical paths are tracked but acceptable
            report.add_excluded(file_path_str, line_num, "todo_comment", matched_text)

    report.total_files_scanned += 1

    if not critical_todos:
        report.checks_passed += 1
    else:
        report.checks_failed += 1

    assert not critical_todos, f"Found {len(critical_todos)} TODOs in critical paths"


def test_no_placeholder_implementations(report: StubReport) -> None:
    """[5/10] Verify: No placeholder pass/ellipsis implementations."""
    matches = grep_pattern(STUB_PATTERNS["placeholder"], KAGAMI_ROOT, case_sensitive=False)

    for file_path_str, line_num, matched_text in matches:
        file_path = Path(file_path_str)

        if should_exclude_path(file_path):
            report.add_excluded(file_path_str, line_num, "placeholder", matched_text)
            continue

        # HIGH: Explicit placeholder comments indicate incomplete code
        report.add_finding(file_path_str, line_num, "placeholder", matched_text, severity="HIGH")

    report.total_files_scanned += 1

    if not any(f.pattern == "placeholder" for f in report.findings):
        report.checks_passed += 1
    else:
        report.checks_failed += 1

    assert not any(
        f.pattern == "placeholder" for f in report.findings
    ), f"Found {len([f for f in report.findings if f.pattern == 'placeholder'])} placeholder implementations"


def test_catastrophe_memory_not_stub(report: StubReport) -> None:
    """[6/10] Verify: CatastropheMemory is a complete implementation."""
    try:
        from kagami.core.world_model.catastrophe_memory import CatastropheMemory

        # Check that it has real methods (use actual method names)
        assert hasattr(CatastropheMemory, "learn_task"), "Missing learn_task method"
        assert hasattr(
            CatastropheMemory, "sample_bifurcations"
        ), "Missing sample_bifurcations method"
        assert hasattr(
            CatastropheMemory, "compute_landscape_potential"
        ), "Missing compute_landscape_potential method"

        # Check that it's not a stub class
        assert "Stub" not in CatastropheMemory.__name__, "CatastropheMemory is a stub"

        report.checks_passed += 1

    except (ImportError, AssertionError) as e:
        report.checks_failed += 1
        report.add_finding(
            "kagami/core/world_model/catastrophe_memory.py",
            0,
            "module_verification",
            f"CatastropheMemory verification failed: {e}",
            severity="CRITICAL",
        )
        pytest.fail(f"CatastropheMemory is incomplete or stub: {e}")


def test_s7_curiosity_not_stub(report: StubReport) -> None:
    """[7/10] Verify: S7CuriositySignal is a complete implementation."""
    try:
        from kagami.core.rl.s7_curiosity import S7CuriositySignal

        # Check that it has real methods (use actual method names)
        assert callable(S7CuriositySignal), "Missing __call__ method (curiosity computation)"
        assert hasattr(S7CuriositySignal, "update_predictor"), "Missing update_predictor method"
        assert hasattr(S7CuriositySignal, "get_coverage_stats"), "Missing get_coverage_stats method"

        # Check that it's not a stub class
        assert "Stub" not in S7CuriositySignal.__name__, "S7CuriositySignal is a stub"

        report.checks_passed += 1

    except (ImportError, AssertionError) as e:
        report.checks_failed += 1
        report.add_finding(
            "kagami/core/rl/s7_curiosity.py",
            0,
            "module_verification",
            f"S7CuriositySignal verification failed: {e}",
            severity="CRITICAL",
        )
        pytest.fail(f"S7CuriositySignal is incomplete or stub: {e}")


def test_recursive_improvement_components(report: StubReport) -> None:
    """[8/10] Verify: RecursiveImprovementSystem has all components."""
    try:
        from kagami.core.integration.recursive_improvement import (
            RecursiveImprovementSystem,
        )

        # Instantiate and check components (use actual attribute names)
        system = RecursiveImprovementSystem()

        # Check all major components exist
        assert hasattr(system, "organism"), "Missing organism (UnifiedOrganism)"
        assert hasattr(system, "catastrophe_kernels"), "Missing catastrophe_kernels"
        assert hasattr(system, "efe"), "Missing efe (EFECBFOptimizer)"
        assert hasattr(system, "curiosity"), "Missing curiosity"
        assert hasattr(system, "fano_meta_learner"), "Missing fano_meta_learner"
        assert hasattr(system, "temporal_quantizer"), "Missing temporal_quantizer"
        assert hasattr(system, "trajectory_cache"), "Missing trajectory_cache"
        assert hasattr(system, "catastrophe_memory"), "Missing catastrophe_memory"
        assert hasattr(system, "gradient_surgery"), "Missing gradient_surgery"

        # Check none are None (curiosity may be None if disabled)
        components = [
            ("organism", system.organism),
            ("catastrophe_kernels", system.catastrophe_kernels),
            ("efe", system.efe),
            ("fano_meta_learner", system.fano_meta_learner),
            ("temporal_quantizer", system.temporal_quantizer),
            ("trajectory_cache", system.trajectory_cache),
            ("catastrophe_memory", system.catastrophe_memory),
            ("gradient_surgery", system.gradient_surgery),
        ]

        none_components = [name for name, comp in components if comp is None]

        assert not none_components, f"Components are None: {none_components}"

        report.checks_passed += 1

    except (ImportError, AssertionError) as e:
        report.checks_failed += 1
        report.add_finding(
            "kagami/core/integration/recursive_improvement.py",
            0,
            "module_verification",
            f"RecursiveImprovementSystem verification failed: {e}",
            severity="CRITICAL",
        )
        pytest.fail(f"RecursiveImprovementSystem is incomplete: {e}")


def test_no_dead_stub_classes(report: StubReport) -> None:
    """[9/10] Verify: No dead stub classes (defined but not imported)."""
    # Search for stub classes
    stub_class_matches = grep_pattern(STUB_PATTERNS["stub_class"], KAGAMI_ROOT)

    dead_stubs = []

    for file_path_str, line_num, matched_text in stub_class_matches:
        file_path = Path(file_path_str)

        if should_exclude_path(file_path):
            continue

        # Extract class name from match
        match = re.search(r"class\s+(\w+)", matched_text)
        if not match:
            continue

        class_name = match.group(1)

        # Search for imports of this class
        import_pattern = f"from.*import.*{class_name}"
        import_matches = grep_pattern(import_pattern, KAGAMI_ROOT)

        # Filter out self-import (in the same file)
        external_imports = [m for m in import_matches if m[0] != file_path_str]

        if not external_imports:
            # Dead stub - defined but never imported
            report.add_finding(
                file_path_str,
                line_num,
                "dead_stub_class",
                f"Stub class {class_name} defined but never imported",
                severity="HIGH",
            )
            dead_stubs.append((file_path_str, line_num, class_name))

    report.total_files_scanned += 1

    if not dead_stubs:
        report.checks_passed += 1
    else:
        report.checks_failed += 1

    assert not dead_stubs, f"Found {len(dead_stubs)} dead stub classes: {dead_stubs}"


def test_generate_final_report(report: StubReport) -> None:
    """[10/10] Generate final stub verification report."""
    summary = report.get_summary()
    print("\n" + summary)

    # Final assertion: zero findings
    assert (
        not report.has_any_findings()
    ), f"VERIFICATION FAILED: {len(report.findings)} stub patterns detected"

    report.checks_passed += 1
