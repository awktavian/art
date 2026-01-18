"""Crystal Capability Layer — Verification Infrastructure.

Crystal (e₇, Parabolic catastrophe, D₅) is The Judge.
This package provides verification, testing, and security tools.

MODULES:
========
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

# Verify an API invariant
result = run_verification(
    pre="x > 0",
    post="y == x * 2",
    variables={"x": "int", "y": "int"},
)

# Security scan
vulns = security_scan(code_path="src/")

# Generate property-based tests
tests = generate_tests(function_signature="def add(a: int, b: int) -> int")

Created: December 28, 2025
"""

from kagami.crystal.modules.analysis import (
    AnalysisReport,
    analyze_code,
    check_complexity,
)
from kagami.crystal.modules.security import (
    SecurityReport,
    find_vulnerabilities,
    security_scan,
)
from kagami.crystal.modules.testing import (
    TestSuite,
    generate_property_tests,
    generate_tests,
)
from kagami.crystal.modules.verification import (
    VerificationResult,
    run_verification,
    verify_invariant,
    verify_reachability,
)

__all__ = [
    "AnalysisReport",
    "SecurityReport",
    "TestSuite",
    "VerificationResult",
    # Analysis
    "analyze_code",
    "check_complexity",
    "find_vulnerabilities",
    "generate_property_tests",
    # Testing
    "generate_tests",
    # Verification
    "run_verification",
    # Security
    "security_scan",
    "verify_invariant",
    "verify_reachability",
]
