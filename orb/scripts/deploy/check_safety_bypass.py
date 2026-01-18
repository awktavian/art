#!/usr/bin/env python3
"""
Fail CI if forbidden safety bypass patterns are introduced.

Forbidden (non-test) code patterns:
    - SKIP_SAFETY flags
    - LIGHTWEIGHT_MODE toggles
    - DEGRADED_MODE toggles
    - Direct pytest detection via `if "pytest" in sys.modules`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SELF_PATH = Path(__file__).resolve()
REPO_ROOT = SELF_PATH.parents[1]
SCAN_ROOTS = [REPO_ROOT / "kagami", REPO_ROOT / "scripts"]
SKIP_PARTS = {"tests", "docs", "__pycache__"}

FORBIDDEN_PATTERNS = [
    ("SKIP_SAFETY flag", re.compile(r"SKIP_SAFETY")),
    ("LIGHTWEIGHT_MODE flag", re.compile(r"LIGHTWEIGHT_MODE")),
    ("DEGRADED_MODE flag", re.compile(r"DEGRADED_MODE")),
    (
        "pytest sys.modules detection",
        re.compile(r'if\s+[\'"]pytest[\'"]\s+in\s+sys\.modules'),
    ),
]


def should_scan(path: Path) -> bool:
    if path.suffix != ".py":
        return False
    if path.resolve() == SELF_PATH:
        return False
    # Skip generated / test / doc files
    return not any(part in SKIP_PARTS for part in path.parts)


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        return findings

    for description, pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            findings.append(f"{path.relative_to(REPO_ROOT)} :: {description}")
    return findings


def main() -> None:
    findings: list[str] = []

    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if should_scan(path):
                findings.extend(scan_file(path))

    if findings:
        print("❌ Forbidden safety bypass patterns detected:")
        for finding in findings:
            print(f"  - {finding}")
        sys.exit(1)

    print("✅ No forbidden safety bypass patterns detected.")


if __name__ == "__main__":
    main()
