"""Crystal Security Module — Vulnerability Detection.

Provides security scanning and vulnerability detection:
- Static analysis for common vulnerabilities
- Dependency vulnerability scanning
- Secret detection
- Code injection detection

Created: December 28, 2025
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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
    location: str  # File:line
    recommendation: str
    cwe_id: str | None = None  # Common Weakness Enumeration ID


@dataclass
class SecurityReport:
    """Security scan report."""

    vulnerabilities: list[Vulnerability] = field(default_factory=list[Any])
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


# Common vulnerability patterns
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
        "recommendation": "Use subprocess with list[Any] arguments, avoid string concatenation",
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
    """Scan code for security vulnerabilities.

    Performs static analysis to detect common vulnerabilities:
    - Hardcoded secrets
    - SQL injection
    - Command injection
    - Path traversal
    - Dangerous function usage

    Args:
        code_path: File or directory path to scan
        patterns: Custom vulnerability patterns (optional)
        recursive: Scan subdirectories (default True)
        extensions: File extensions to scan

    Returns:
        SecurityReport with vulnerabilities found

    Example:
        report = security_scan("src/")
        if not report.passed:
            print(f"Found {len(report.vulnerabilities)} issues!")
    """
    import time

    start = time.perf_counter()

    code_path = Path(code_path)
    scan_patterns = {**VULN_PATTERNS, **(patterns or {})}
    vulnerabilities: list[Vulnerability] = []
    files_scanned = 0

    # Get files to scan
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


def find_vulnerabilities(
    code: str,
    filename: str = "<string>",
) -> list[Vulnerability]:
    """Find vulnerabilities in a code string.

    Useful for scanning code snippets or generated code.

    Args:
        code: Source code string
        filename: Filename for location reporting

    Returns:
        List of vulnerabilities found
    """
    vulnerabilities: list[Vulnerability] = []
    lines = code.split("\n")

    for name, pattern_info in VULN_PATTERNS.items():
        pattern = pattern_info["pattern"]
        for i, line in enumerate(lines, 1):
            if re.search(pattern, line, re.IGNORECASE):  # type: ignore[call-overload]
                vulnerabilities.append(
                    Vulnerability(
                        name=name,
                        severity=pattern_info["severity"],  # type: ignore[arg-type]
                        description=pattern_info["description"],  # type: ignore[arg-type]
                        location=f"{filename}:{i}",
                        recommendation=pattern_info["recommendation"],  # type: ignore[arg-type]
                        cwe_id=pattern_info.get("cwe_id"),  # type: ignore[arg-type]
                    )
                )

    return vulnerabilities


__all__ = [
    "SecurityReport",
    "Severity",
    "Vulnerability",
    "find_vulnerabilities",
    "security_scan",
]
