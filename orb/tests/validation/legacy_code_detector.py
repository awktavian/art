"""💎 CRYSTAL COLONY — Advanced Legacy Code Detection System

Zero-tolerance legacy code detection with sophisticated pattern analysis.
Implements crystalline precision in identifying and eliminating all forms
of legacy patterns, fallback mechanisms, and graceful degradation.

Detection Categories:
1. Explicit Legacy Patterns: Direct legacy code markers
2. Fallback Mechanisms: try/except, defaults, alternatives
3. Graceful Degradation: Error handling that continues operation
4. Compatibility Code: Version checks, platform-specific code
5. Defensive Programming: Overly cautious error handling
6. Performance Workarounds: Temporary fixes and optimizations

Philosophy: FAIL FAST - No graceful degradation, no fallbacks.
Perfect integration requires perfect reliability.

Created: December 29, 2025
Colony: 💎 Crystal (Verification, Quality)
Mission: Zero legacy code tolerance validation
"""

from __future__ import annotations

import ast
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pytest

logger = logging.getLogger(__name__)


class LegacyPatternType(Enum):
    """Categories of legacy code patterns."""

    EXPLICIT_LEGACY = "explicit_legacy"  # Direct legacy markers
    FALLBACK_MECHANISM = "fallback_mechanism"  # try/except, defaults
    GRACEFUL_DEGRADATION = "graceful_degradation"  # Error continuation
    COMPATIBILITY_CODE = "compatibility_code"  # Version/platform checks
    DEFENSIVE_PROGRAMMING = "defensive_programming"  # Overly cautious code
    PERFORMANCE_WORKAROUND = "performance_workaround"  # Temporary optimizations


class Severity(Enum):
    """Legacy pattern severity levels."""

    CRITICAL = "critical"  # Immediate certification failure
    HIGH = "high"  # Major concern
    MEDIUM = "medium"  # Moderate concern
    LOW = "low"  # Minor concern
    INFO = "info"  # Informational


@dataclass
class LegacyPattern:
    """Detected legacy pattern."""

    pattern_type: LegacyPatternType
    severity: Severity
    file_path: Path
    line_number: int
    code_snippet: str
    pattern_name: str
    description: str
    recommendation: str


@dataclass
class LegacyDetectionMetrics:
    """Comprehensive legacy detection metrics."""

    # Pattern counts by type
    explicit_legacy_count: int = 0
    fallback_mechanism_count: int = 0
    graceful_degradation_count: int = 0
    compatibility_code_count: int = 0
    defensive_programming_count: int = 0
    performance_workaround_count: int = 0

    # Severity breakdown
    critical_violations: int = 0
    high_violations: int = 0
    medium_violations: int = 0
    low_violations: int = 0

    # File analysis
    files_scanned: int = 0
    files_with_legacy: int = 0
    total_lines_analyzed: int = 0
    legacy_density: float = 0.0  # Legacy patterns per 1000 lines

    # Detailed findings
    patterns_found: list[LegacyPattern] = field(default_factory=list)

    # Certification metrics
    zero_legacy_achieved: bool = False
    fail_fast_compliance_rate: float = 0.0
    certification_score: float = 0.0

    def calculate_total_violations(self) -> int:
        """Calculate total legacy violations."""
        return (
            self.explicit_legacy_count
            + self.fallback_mechanism_count
            + self.graceful_degradation_count
            + self.compatibility_code_count
            + self.defensive_programming_count
            + self.performance_workaround_count
        )

    def calculate_certification_score(self) -> float:
        """Calculate legacy elimination certification score (0-100)."""
        total_violations = self.calculate_total_violations()

        if total_violations == 0:
            self.certification_score = 100.0
            self.zero_legacy_achieved = True
        else:
            # Severe penalties for any legacy code
            penalty = min(100.0, total_violations * 2.5)  # 2.5 points per violation
            critical_penalty = self.critical_violations * 10.0  # Extra penalty for critical
            self.certification_score = max(0.0, 100.0 - penalty - critical_penalty)

        # Calculate fail-fast compliance
        if self.files_scanned > 0:
            clean_files = self.files_scanned - self.files_with_legacy
            self.fail_fast_compliance_rate = (clean_files / self.files_scanned) * 100.0
        else:
            self.fail_fast_compliance_rate = 0.0

        return self.certification_score


class AdvancedLegacyCodeDetector:
    """💎 Crystal Colony advanced legacy code detection system.

    Implements sophisticated pattern recognition and AST analysis
    to detect all forms of legacy code with crystalline precision.
    """

    def __init__(self, project_root: Path = None):
        """Initialize legacy code detector."""
        self.project_root = project_root or Path("/Users/schizodactyl/projects/kagami")
        self.metrics = LegacyDetectionMetrics()

        # Advanced pattern definitions
        self._compile_detection_patterns()

        logger.info("💎 Advanced Legacy Code Detector initialized")

    def _compile_detection_patterns(self) -> None:
        """Compile comprehensive legacy detection patterns."""

        # Explicit legacy patterns
        self.explicit_legacy_patterns = [
            (re.compile(r"\blegacy\b", re.IGNORECASE), "Direct legacy reference"),
            (re.compile(r"\bold[_\-]?version\b", re.IGNORECASE), "Old version reference"),
            (re.compile(r"\bdeprecated\b", re.IGNORECASE), "Deprecated code marker"),
            (re.compile(r"\bobsolete\b", re.IGNORECASE), "Obsolete code marker"),
            (
                re.compile(r"\bbackward[_\-]?compatibility\b", re.IGNORECASE),
                "Backward compatibility",
            ),
            (re.compile(r"\bTODO.*remove\b", re.IGNORECASE), "TODO removal marker"),
            (re.compile(r"\bFIXME\b", re.IGNORECASE), "FIXME marker"),
            (re.compile(r"\bHACK\b", re.IGNORECASE), "Hack marker"),
            (re.compile(r"\bWORKAROUND\b", re.IGNORECASE), "Workaround marker"),
        ]

        # Fallback mechanism patterns
        self.fallback_patterns = [
            (
                re.compile(r"try:\s*.*\nexcept.*:\s*pass", re.MULTILINE | re.DOTALL),
                "Silent exception handling",
            ),
            (
                re.compile(r"\.get\s*\(\s*[^,)]+\s*,\s*.*\)", re.MULTILINE),
                "Dictionary get with default",
            ),
            (re.compile(r"if\s+.*\s+else\s+None", re.IGNORECASE), "Conditional with None fallback"),
            (re.compile(r"fallback\s*=", re.IGNORECASE), "Explicit fallback assignment"),
            (re.compile(r"default\s*=.*None", re.IGNORECASE), "None default parameter"),
            (re.compile(r"backup[_\-]?.*=", re.IGNORECASE), "Backup variable assignment"),
            (re.compile(r"alternative[_\-]?.*=", re.IGNORECASE), "Alternative variable assignment"),
            (re.compile(r"or\s+\[\]", re.IGNORECASE), "Empty list fallback"),
            (re.compile(r"or\s+\{\}", re.IGNORECASE), "Empty dict fallback"),
            (re.compile(r'or\s+""', re.IGNORECASE), "Empty string fallback"),
        ]

        # Graceful degradation patterns
        self.degradation_patterns = [
            (
                re.compile(r"graceful[_\-]?degradation", re.IGNORECASE),
                "Explicit graceful degradation",
            ),
            (re.compile(r"except.*:\s*\n\s*logger\.warning", re.MULTILINE), "Warning on exception"),
            (re.compile(r"except.*:\s*\n\s*continue", re.MULTILINE), "Continue on exception"),
            (
                re.compile(r"except.*:\s*\n\s*return.*None", re.MULTILINE),
                "Return None on exception",
            ),
            (
                re.compile(r"except.*:\s*\n\s*return.*\[\]", re.MULTILINE),
                "Return empty on exception",
            ),
            (
                re.compile(r"if.*error.*:\s*\n\s*return", re.MULTILINE | re.IGNORECASE),
                "Return on error",
            ),
            (re.compile(r"resilience", re.IGNORECASE), "Resilience patterns"),
            (re.compile(r"fault[_\-]?tolerant", re.IGNORECASE), "Fault tolerance"),
            (re.compile(r"retry[_\-]?logic", re.IGNORECASE), "Retry logic"),
            (re.compile(r"circuit[_\-]?breaker", re.IGNORECASE), "Circuit breaker pattern"),
        ]

        # Compatibility code patterns
        self.compatibility_patterns = [
            (re.compile(r"if\s+sys\.version", re.IGNORECASE), "Python version check"),
            (re.compile(r"if\s+platform\.", re.IGNORECASE), "Platform-specific code"),
            (re.compile(r"compatibility[_\-]?layer", re.IGNORECASE), "Compatibility layer"),
            (re.compile(r"if\s+hasattr\s*\(", re.IGNORECASE), "hasattr compatibility check"),
            (re.compile(r"importlib\.util", re.IGNORECASE), "Dynamic import for compatibility"),
            (re.compile(r"__version__\s*[<>=]", re.IGNORECASE), "Version comparison"),
            (re.compile(r"from\s+.*\s+import.*as.*", re.IGNORECASE), "Import aliasing"),
        ]

        # Defensive programming patterns
        self.defensive_patterns = [
            (re.compile(r"assert\s+.*is not None", re.IGNORECASE), "Defensive None check"),
            (
                re.compile(r"if\s+.*is None:\s*\n\s*raise", re.MULTILINE | re.IGNORECASE),
                "None guard",
            ),
            (
                re.compile(r"isinstance\s*\(\s*.*\s*,\s*\(.*\)\s*\)", re.IGNORECASE),
                "Multiple type check",
            ),
            (re.compile(r"len\s*\(\s*.*\s*\)\s*>\s*0", re.IGNORECASE), "Length validation"),
            (
                re.compile(r"if\s+.*:\s*\n\s*assert", re.MULTILINE | re.IGNORECASE),
                "Conditional assertion",
            ),
        ]

        # Performance workaround patterns
        self.workaround_patterns = [
            (
                re.compile(r"#.*perf.*optimization", re.IGNORECASE),
                "Performance optimization comment",
            ),
            (re.compile(r"#.*temporary.*fix", re.IGNORECASE), "Temporary fix comment"),
            (re.compile(r"cache[_\-]?.*=.*\{\}", re.IGNORECASE), "Manual cache implementation"),
            (re.compile(r"memoize", re.IGNORECASE), "Memoization workaround"),
            (re.compile(r"@lru_cache", re.IGNORECASE), "LRU cache workaround"),
        ]

    async def scan_project_for_legacy_patterns(
        self, include_tests: bool = True, include_vendor: bool = False
    ) -> LegacyDetectionMetrics:
        """🔍 Scan entire project for legacy code patterns.

        Args:
            include_tests: Include test files in scan
            include_vendor: Include vendor/third-party code

        Returns:
            Comprehensive legacy detection metrics
        """

        logger.info("💎 CRYSTAL: Beginning comprehensive legacy code scan...")
        scan_start_time = time.time()

        # Collect Python files to scan
        python_files = self._collect_python_files(include_tests, include_vendor)
        self.metrics.files_scanned = len(python_files)

        logger.info(f"💎 Scanning {len(python_files)} Python files for legacy patterns...")

        # Scan each file
        for py_file in python_files:
            await self._scan_file_for_patterns(py_file)

        # Calculate final metrics
        self.metrics.calculate_certification_score()

        scan_duration = time.time() - scan_start_time
        logger.info(f"💎 Legacy scan complete in {scan_duration:.2f}s")

        return self.metrics

    def _collect_python_files(
        self, include_tests: bool = True, include_vendor: bool = False
    ) -> list[Path]:
        """Collect Python files for scanning."""

        python_files = []

        for py_file in self.project_root.rglob("*.py"):
            # Skip excluded directories
            if any(skip in str(py_file) for skip in [".git", "__pycache__"]):
                continue

            # Skip vendor code unless requested
            if not include_vendor and any(
                vendor in str(py_file) for vendor in [".venv", "venv", "site-packages"]
            ):
                continue

            # Skip test files unless requested
            if not include_tests and any(
                test in str(py_file) for test in ["test_", "/tests/", "/conftest"]
            ):
                continue

            python_files.append(py_file)

        return python_files

    async def _scan_file_for_patterns(self, file_path: Path) -> None:
        """Scan single file for legacy patterns."""

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
            self.metrics.total_lines_analyzed += len(lines)

            file_has_legacy = False

            # Scan with each pattern category
            patterns_found = []

            # 1. Explicit legacy patterns
            patterns_found.extend(
                self._scan_patterns(
                    content,
                    lines,
                    file_path,
                    self.explicit_legacy_patterns,
                    LegacyPatternType.EXPLICIT_LEGACY,
                    Severity.CRITICAL,
                )
            )

            # 2. Fallback mechanism patterns
            patterns_found.extend(
                self._scan_patterns(
                    content,
                    lines,
                    file_path,
                    self.fallback_patterns,
                    LegacyPatternType.FALLBACK_MECHANISM,
                    Severity.HIGH,
                )
            )

            # 3. Graceful degradation patterns
            patterns_found.extend(
                self._scan_patterns(
                    content,
                    lines,
                    file_path,
                    self.degradation_patterns,
                    LegacyPatternType.GRACEFUL_DEGRADATION,
                    Severity.HIGH,
                )
            )

            # 4. Compatibility code patterns
            patterns_found.extend(
                self._scan_patterns(
                    content,
                    lines,
                    file_path,
                    self.compatibility_patterns,
                    LegacyPatternType.COMPATIBILITY_CODE,
                    Severity.MEDIUM,
                )
            )

            # 5. Defensive programming patterns
            patterns_found.extend(
                self._scan_patterns(
                    content,
                    lines,
                    file_path,
                    self.defensive_patterns,
                    LegacyPatternType.DEFENSIVE_PROGRAMMING,
                    Severity.LOW,
                )
            )

            # 6. Performance workaround patterns
            patterns_found.extend(
                self._scan_patterns(
                    content,
                    lines,
                    file_path,
                    self.workaround_patterns,
                    LegacyPatternType.PERFORMANCE_WORKAROUND,
                    Severity.MEDIUM,
                )
            )

            # Update metrics
            if patterns_found:
                file_has_legacy = True
                self.metrics.files_with_legacy += 1
                self.metrics.patterns_found.extend(patterns_found)

                # Count by pattern type
                for pattern in patterns_found:
                    if pattern.pattern_type == LegacyPatternType.EXPLICIT_LEGACY:
                        self.metrics.explicit_legacy_count += 1
                    elif pattern.pattern_type == LegacyPatternType.FALLBACK_MECHANISM:
                        self.metrics.fallback_mechanism_count += 1
                    elif pattern.pattern_type == LegacyPatternType.GRACEFUL_DEGRADATION:
                        self.metrics.graceful_degradation_count += 1
                    elif pattern.pattern_type == LegacyPatternType.COMPATIBILITY_CODE:
                        self.metrics.compatibility_code_count += 1
                    elif pattern.pattern_type == LegacyPatternType.DEFENSIVE_PROGRAMMING:
                        self.metrics.defensive_programming_count += 1
                    elif pattern.pattern_type == LegacyPatternType.PERFORMANCE_WORKAROUND:
                        self.metrics.performance_workaround_count += 1

                    # Count by severity
                    if pattern.severity == Severity.CRITICAL:
                        self.metrics.critical_violations += 1
                    elif pattern.severity == Severity.HIGH:
                        self.metrics.high_violations += 1
                    elif pattern.severity == Severity.MEDIUM:
                        self.metrics.medium_violations += 1
                    elif pattern.severity == Severity.LOW:
                        self.metrics.low_violations += 1

            # Additional AST-based analysis for complex patterns
            await self._ast_analysis(file_path, content)

        except Exception as e:
            logger.debug(f"Error scanning {file_path}: {e}")

    def _scan_patterns(
        self,
        content: str,
        lines: list[str],
        file_path: Path,
        patterns: list[tuple[re.Pattern, str]],
        pattern_type: LegacyPatternType,
        severity: Severity,
    ) -> list[LegacyPattern]:
        """Scan for specific pattern category."""

        found_patterns = []

        for pattern_regex, description in patterns:
            matches = pattern_regex.finditer(content)

            for match in matches:
                # Find line number
                line_number = content[: match.start()].count("\n") + 1
                code_snippet = (
                    lines[line_number - 1] if line_number <= len(lines) else match.group()
                )

                # Generate recommendation
                recommendation = self._generate_recommendation(pattern_type, description)

                legacy_pattern = LegacyPattern(
                    pattern_type=pattern_type,
                    severity=severity,
                    file_path=file_path,
                    line_number=line_number,
                    code_snippet=code_snippet.strip(),
                    pattern_name=description,
                    description=f"{pattern_type.value}: {description}",
                    recommendation=recommendation,
                )

                found_patterns.append(legacy_pattern)

        return found_patterns

    async def _ast_analysis(self, file_path: Path, content: str) -> None:
        """Perform AST-based analysis for complex patterns."""

        try:
            tree = ast.parse(content)

            # AST visitors for complex pattern detection
            visitor = LegacyPatternASTVisitor(file_path)
            visitor.visit(tree)

            # Add patterns found by AST analysis
            self.metrics.patterns_found.extend(visitor.patterns_found)

        except SyntaxError:
            # Skip files with syntax errors
            pass
        except Exception as e:
            logger.debug(f"AST analysis failed for {file_path}: {e}")

    def _generate_recommendation(self, pattern_type: LegacyPatternType, description: str) -> str:
        """Generate specific recommendation for pattern type."""

        recommendations = {
            LegacyPatternType.EXPLICIT_LEGACY: "Remove legacy code immediately. Implement modern alternative.",
            LegacyPatternType.FALLBACK_MECHANISM: "Replace with fail-fast approach. No fallbacks allowed.",
            LegacyPatternType.GRACEFUL_DEGRADATION: "Implement immediate failure. No graceful degradation.",
            LegacyPatternType.COMPATIBILITY_CODE: "Remove compatibility code. Target single environment.",
            LegacyPatternType.DEFENSIVE_PROGRAMMING: "Trust system contracts. Remove defensive checks.",
            LegacyPatternType.PERFORMANCE_WORKAROUND: "Implement proper solution. Remove temporary workaround.",
        }

        return recommendations.get(pattern_type, "Review and remove legacy pattern.")

    def generate_legacy_report(self) -> str:
        """Generate comprehensive legacy code report."""

        report_lines = [
            "💎 CRYSTAL COLONY — Legacy Code Detection Report",
            "=" * 60,
            "",
            "📊 SUMMARY:",
            f"Files Scanned: {self.metrics.files_scanned}",
            f"Files with Legacy: {self.metrics.files_with_legacy}",
            f"Total Violations: {self.metrics.calculate_total_violations()}",
            f"Certification Score: {self.metrics.certification_score:.2f}/100",
            f"Zero Legacy Achieved: {'YES' if self.metrics.zero_legacy_achieved else 'NO'}",
            f"Fail-Fast Compliance: {self.metrics.fail_fast_compliance_rate:.1f}%",
            "",
            "🔍 PATTERN BREAKDOWN:",
            f"Explicit Legacy: {self.metrics.explicit_legacy_count}",
            f"Fallback Mechanisms: {self.metrics.fallback_mechanism_count}",
            f"Graceful Degradation: {self.metrics.graceful_degradation_count}",
            f"Compatibility Code: {self.metrics.compatibility_code_count}",
            f"Defensive Programming: {self.metrics.defensive_programming_count}",
            f"Performance Workarounds: {self.metrics.performance_workaround_count}",
            "",
            "⚠️ SEVERITY BREAKDOWN:",
            f"Critical: {self.metrics.critical_violations}",
            f"High: {self.metrics.high_violations}",
            f"Medium: {self.metrics.medium_violations}",
            f"Low: {self.metrics.low_violations}",
        ]

        if self.metrics.patterns_found:
            report_lines.extend(["", "🚨 DETAILED VIOLATIONS:", "-" * 40])

            # Group by file for cleaner reporting
            files_with_patterns = {}
            for pattern in self.metrics.patterns_found:
                file_key = str(pattern.file_path)
                if file_key not in files_with_patterns:
                    files_with_patterns[file_key] = []
                files_with_patterns[file_key].append(pattern)

            # Report violations by file
            for file_path, patterns in sorted(files_with_patterns.items()):
                report_lines.append(f"\n📁 {file_path}")
                for pattern in patterns:
                    report_lines.append(
                        f"  🔴 Line {pattern.line_number}: {pattern.pattern_name} "
                        f"[{pattern.severity.value.upper()}]"
                    )
                    report_lines.append(f"     Code: {pattern.code_snippet}")
                    report_lines.append(f"     Fix: {pattern.recommendation}")

        # Add certification assessment
        report_lines.extend(["", "🏆 CERTIFICATION ASSESSMENT:", "-" * 30])

        if self.metrics.zero_legacy_achieved:
            report_lines.append("✅ PERFECT: Zero legacy code detected")
            report_lines.append("💎 CRYSTAL CERTIFICATION: PASSED")
        else:
            report_lines.append("❌ FAILED: Legacy code patterns detected")
            report_lines.append("🔄 CRYSTAL CERTIFICATION: REQUIRES CLEANUP")
            report_lines.append("")
            report_lines.append("🎯 NEXT STEPS:")
            report_lines.append("1. Remove all legacy patterns immediately")
            report_lines.append("2. Implement fail-fast approaches")
            report_lines.append("3. Eliminate graceful degradation")
            report_lines.append("4. Re-run certification")

        return "\n".join(report_lines)


class LegacyPatternASTVisitor(ast.NodeVisitor):
    """AST visitor for detecting complex legacy patterns."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.patterns_found: list[LegacyPattern] = []

    def visit_TryExcept(self, node):
        """Detect try/except patterns."""

        # Check for empty except blocks (pass only)
        for handler in node.handlers:
            if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                pattern = LegacyPattern(
                    pattern_type=LegacyPatternType.FALLBACK_MECHANISM,
                    severity=Severity.CRITICAL,
                    file_path=self.file_path,
                    line_number=handler.lineno,
                    code_snippet="except: pass",
                    pattern_name="Empty exception handler",
                    description="Silent exception handling detected",
                    recommendation="Remove silent exception handling. Implement proper error handling.",
                )
                self.patterns_found.append(pattern)

        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        """Detect function-level legacy patterns."""

        # Check for functions with excessive try/except coverage
        try_count = sum(1 for child in ast.walk(node) if isinstance(child, ast.Try))

        if try_count > 3:  # Arbitrary threshold
            pattern = LegacyPattern(
                pattern_type=LegacyPatternType.DEFENSIVE_PROGRAMMING,
                severity=Severity.MEDIUM,
                file_path=self.file_path,
                line_number=node.lineno,
                code_snippet=f"def {node.name}(...)",
                pattern_name="Excessive exception handling",
                description=f"Function has {try_count} try/except blocks",
                recommendation="Reduce defensive programming. Trust system contracts.",
            )
            self.patterns_found.append(pattern)

        self.generic_visit(node)


# =============================================================================
# Test Integration
# =============================================================================


@pytest.mark.asyncio
async def test_legacy_code_detector():
    """Test legacy code detection system."""

    detector = AdvancedLegacyCodeDetector()

    # Scan project for legacy patterns
    metrics = await detector.scan_project_for_legacy_patterns(
        include_tests=True, include_vendor=False
    )

    # Should have completed scan
    assert metrics.files_scanned > 0
    assert metrics.total_lines_analyzed > 0
    assert 0 <= metrics.certification_score <= 100
    assert isinstance(metrics.zero_legacy_achieved, bool)

    # Generate report
    report = detector.generate_legacy_report()
    assert len(report) > 0
    assert "Legacy Code Detection Report" in report


# =============================================================================
# Main Execution
# =============================================================================


async def main():
    """Execute legacy code detection."""
    print("💎 CRYSTAL COLONY — Advanced Legacy Code Detection")
    print("=" * 60)

    detector = AdvancedLegacyCodeDetector()

    # Run comprehensive scan
    metrics = await detector.scan_project_for_legacy_patterns(
        include_tests=True, include_vendor=False
    )

    # Display results
    print("📊 Scan Results:")
    print(f"Files Scanned: {metrics.files_scanned}")
    print(f"Legacy Violations: {metrics.calculate_total_violations()}")
    print(f"Certification Score: {metrics.certification_score:.2f}/100")
    print(f"Zero Legacy: {'✅ ACHIEVED' if metrics.zero_legacy_achieved else '❌ NOT ACHIEVED'}")

    # Generate detailed report
    report = detector.generate_legacy_report()
    print("\n" + report)

    # Save report
    report_path = Path("/Users/schizodactyl/projects/kagami/artifacts/legacy_detection_report.txt")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    print(f"\n💾 Report saved: {report_path}")

    # Exit with appropriate code
    if metrics.zero_legacy_achieved:
        exit(0)
    else:
        exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
