#!/usr/bin/env python3
"""
Coverage threshold enforcement script for CI pipeline.

Parses coverage.xml (Cobertura format) and enforces minimum coverage threshold.
Fails the build if coverage is below the threshold.

Usage:
    python scripts/ci/enforce_coverage_threshold.py coverage.xml [--threshold 80]
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_coverage_xml(coverage_file: Path) -> float:
    """
    Parse Cobertura coverage.xml and extract total line coverage percentage.

    Args:
        coverage_file: Path to coverage.xml

    Returns:
        Coverage percentage (0-100)

    Raises:
        FileNotFoundError: If coverage file doesn't exist
        ValueError: If coverage file is malformed
    """
    if not coverage_file.exists():
        raise FileNotFoundError(f"Coverage file not found: {coverage_file}")

    try:
        tree = ET.parse(coverage_file)  # noqa: S314 - trusted file from local CI
        root = tree.getroot()

        # Cobertura format: <coverage line-rate="0.xxxx" ...>
        line_rate = root.get("line-rate")
        if line_rate is None:
            raise ValueError("Invalid coverage.xml: missing 'line-rate' attribute")

        coverage_pct = float(line_rate) * 100
        return coverage_pct

    except ET.ParseError as e:
        raise ValueError(f"Failed to parse coverage.xml: {e}") from e
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid line-rate value in coverage.xml: {e}") from e


def format_coverage_report(coverage_pct: float, threshold: float) -> str:
    """
    Format coverage report for terminal output.

    Args:
        coverage_pct: Current coverage percentage
        threshold: Required threshold percentage

    Returns:
        Formatted report string
    """
    status = "✅ PASS" if coverage_pct >= threshold else "❌ FAIL"
    delta = coverage_pct - threshold

    report = f"""
════════════════════════════════════════════════════════════════════════
  Coverage Gate: {status}
════════════════════════════════════════════════════════════════════════

  Current Coverage:  {coverage_pct:.2f}%
  Required:          {threshold:.2f}%
  Delta:             {delta:+.2f}%

"""

    if coverage_pct >= threshold:
        report += "  ✅ Coverage threshold met. Build passing.\n"
    else:
        report += f"  ❌ Coverage below threshold by {abs(delta):.2f}%.\n"
        report += "  → Add tests to improve coverage before merging.\n"

    report += "\n════════════════════════════════════════════════════════════════════════\n"

    return report


def main() -> int:
    """
    Main entry point.

    Returns:
        0 if coverage meets threshold, 1 otherwise
    """
    parser = argparse.ArgumentParser(description="Enforce coverage threshold for CI pipeline")
    parser.add_argument(
        "coverage_file",
        type=Path,
        help="Path to coverage.xml (Cobertura format)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=75.0,
        help="Minimum coverage threshold percentage (default: 75.0)",
    )

    args = parser.parse_args()

    try:
        coverage_pct = parse_coverage_xml(args.coverage_file)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Generate and print report
    report = format_coverage_report(coverage_pct, args.threshold)
    print(report)

    # Return exit code based on threshold
    if coverage_pct >= args.threshold:
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
