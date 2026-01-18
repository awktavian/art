#!/usr/bin/env python3
"""
Security findings aggregation script for CI pipeline.

Parses bandit.json and safety.json outputs and aggregates security findings.
Provides a summary of critical issues and recommendations.

Usage:
    python scripts/ci/aggregate_security_findings.py [--fail-on-critical]
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def parse_bandit_report(bandit_file: Path) -> dict[str, Any]:
    """
    Parse bandit.json report.

    Args:
        bandit_file: Path to bandit.json

    Returns:
        Dictionary with:
            - total: Total issues found
            - by_severity: Count by severity level
            - critical: List of critical/high severity issues
    """
    if not bandit_file.exists():
        return {
            "total": 0,
            "by_severity": {},
            "critical": [],
        }

    try:
        with open(bandit_file) as f:
            data = json.load(f)

        results = data.get("results", [])
        by_severity = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        critical = []

        for issue in results:
            severity = issue.get("issue_severity", "LOW")
            by_severity[severity] = by_severity.get(severity, 0) + 1

            if severity in ("HIGH", "MEDIUM"):
                critical.append(
                    {
                        "severity": severity,
                        "confidence": issue.get("issue_confidence", "UNKNOWN"),
                        "test_id": issue.get("test_id", "UNKNOWN"),
                        "issue_text": issue.get("issue_text", "No description"),
                        "filename": issue.get("filename", "unknown"),
                        "line_number": issue.get("line_number", 0),
                    }
                )

        return {
            "total": len(results),
            "by_severity": by_severity,
            "critical": critical,
        }

    except (json.JSONDecodeError, KeyError) as e:
        print(f"WARNING: Failed to parse bandit.json: {e}", file=sys.stderr)
        return {"total": 0, "by_severity": {}, "critical": []}


def parse_safety_report(safety_file: Path) -> dict[str, Any]:
    """
    Parse safety.json report.

    Args:
        safety_file: Path to safety.json

    Returns:
        Dictionary with:
            - total: Total vulnerabilities found
            - critical: List of critical vulnerabilities
    """
    if not safety_file.exists():
        return {
            "total": 0,
            "critical": [],
        }

    try:
        with open(safety_file) as f:
            data = json.load(f)

        vulnerabilities = data.get("vulnerabilities", [])
        critical = []

        for vuln in vulnerabilities:
            critical.append(
                {
                    "package": vuln.get("package_name", "unknown"),
                    "version": vuln.get("analyzed_version", "unknown"),
                    "vulnerability": vuln.get("vulnerability_id", "UNKNOWN"),
                    "severity": vuln.get("severity", "UNKNOWN"),
                    "description": vuln.get("advisory", "No description"),
                }
            )

        return {
            "total": len(vulnerabilities),
            "critical": critical,
        }

    except (json.JSONDecodeError, KeyError) as e:
        print(f"WARNING: Failed to parse safety.json: {e}", file=sys.stderr)
        return {"total": 0, "critical": []}


def format_security_report(bandit_data: dict, safety_data: dict) -> str:
    """
    Format aggregated security findings into a terminal report.

    Args:
        bandit_data: Parsed bandit data
        safety_data: Parsed safety data

    Returns:
        Formatted report string
    """
    total_issues = bandit_data["total"] + safety_data["total"]
    has_critical = len(bandit_data["critical"]) + len(safety_data["critical"]) > 0

    status = "⚠️  WARNINGS" if has_critical else "✅ CLEAN"

    report = f"""
════════════════════════════════════════════════════════════════════════
  Security Scan: {status}
════════════════════════════════════════════════════════════════════════

  Total Issues:         {total_issues}
  - Bandit (SAST):      {bandit_data["total"]}
  - Safety (Deps):      {safety_data["total"]}

"""

    # Bandit findings by severity
    if bandit_data["total"] > 0:
        by_sev = bandit_data["by_severity"]
        report += "  Bandit Severity:\n"
        report += f"    HIGH:   {by_sev.get('HIGH', 0)}\n"
        report += f"    MEDIUM: {by_sev.get('MEDIUM', 0)}\n"
        report += f"    LOW:    {by_sev.get('LOW', 0)}\n\n"

    # Critical Bandit issues
    if bandit_data["critical"]:
        report += f"  🔴 Critical Bandit Findings ({len(bandit_data['critical'])}):\n"
        for i, issue in enumerate(bandit_data["critical"][:5], 1):
            report += f"    {i}. [{issue['severity']}] {issue['test_id']}\n"
            report += f"       {issue['issue_text']}\n"
            report += f"       → {issue['filename']}:{issue['line_number']}\n\n"

        if len(bandit_data["critical"]) > 5:
            report += f"    ... and {len(bandit_data['critical']) - 5} more\n\n"

    # Critical Safety vulnerabilities
    if safety_data["critical"]:
        report += f"  🔴 Dependency Vulnerabilities ({len(safety_data['critical'])}):\n"
        for i, vuln in enumerate(safety_data["critical"][:5], 1):
            report += f"    {i}. [{vuln['severity']}] {vuln['package']} {vuln['version']}\n"
            report += f"       {vuln['vulnerability']}\n"
            report += f"       {vuln['description'][:80]}...\n\n"

        if len(safety_data["critical"]) > 5:
            report += f"    ... and {len(safety_data['critical']) - 5} more\n\n"

    if not has_critical:
        report += "  ✅ No critical security issues found.\n\n"
    else:
        report += "  ⚠️  Review findings above. Consider fixing before merge.\n\n"

    report += "════════════════════════════════════════════════════════════════════════\n"

    return report


def main() -> int:
    """
    Main entry point.

    Returns:
        0 if no critical issues (or --fail-on-critical not set), 1 otherwise
    """
    parser = argparse.ArgumentParser(
        description="Aggregate security findings from Bandit and Safety"
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Fail build if critical security issues are found",
    )
    parser.add_argument(
        "--bandit-file",
        type=Path,
        default=Path("bandit.json"),
        help="Path to bandit.json (default: bandit.json)",
    )
    parser.add_argument(
        "--safety-file",
        type=Path,
        default=Path("safety.json"),
        help="Path to safety.json (default: safety.json)",
    )

    args = parser.parse_args()

    # Parse reports
    bandit_data = parse_bandit_report(args.bandit_file)
    safety_data = parse_safety_report(args.safety_file)

    # Generate report
    report = format_security_report(bandit_data, safety_data)
    print(report)

    # Determine exit code
    has_critical = len(bandit_data["critical"]) + len(safety_data["critical"]) > 0

    if args.fail_on_critical and has_critical:
        print("ERROR: Critical security issues found. Failing build.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
