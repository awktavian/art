#!/usr/bin/env python3
"""
Generate quality dashboard JSON and summary report.

Runs all quality checks and aggregates results.
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


CHECKS = [
    {
        "name": "file_length",
        "script": "scripts/ci/check_file_length.py",
        "description": "Files exceed 500 lines",
    },
    {
        "name": "bare_except",
        "script": "scripts/ci/check_bare_except.py",
        "description": "Bare except clauses without type",
    },
    {
        "name": "duplicate_classes",
        "script": "scripts/ci/detect_duplicates.py",
        "description": "Duplicate class names across files",
    },
    {
        "name": "type_coverage",
        "script": "scripts/ci/check_type_coverage.py",
        "description": "Type annotation coverage < 80%",
    },
    {
        "name": "docstrings",
        "script": "scripts/ci/check_docstrings.py",
        "description": "Missing docstrings on public functions",
    },
]


def run_check(check: dict[str, str]) -> dict[str, Any]:
    """
    Run a single quality check.

    Returns:
        Result dictionary with status, duration, output.
    """
    start_time = time.time()

    try:
        result = subprocess.run(
            ["python3", check["script"]],
            capture_output=True,
            text=True,
            timeout=60,
        )
        duration = time.time() - start_time

        return {
            "name": check["name"],
            "description": check["description"],
            "status": "pass" if result.returncode == 0 else "fail",
            "exit_code": result.returncode,
            "duration": round(duration, 2),
            "output": result.stdout,
            "error": result.stderr if result.stderr else None,
        }
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return {
            "name": check["name"],
            "description": check["description"],
            "status": "timeout",
            "exit_code": -1,
            "duration": round(duration, 2),
            "output": None,
            "error": "Check timed out after 60 seconds",
        }
    except Exception as e:
        duration = time.time() - start_time
        return {
            "name": check["name"],
            "description": check["description"],
            "status": "error",
            "exit_code": -1,
            "duration": round(duration, 2),
            "output": None,
            "error": str(e),
        }


def generate_summary(results: list[dict[str, Any]]) -> str:
    """Generate human-readable summary."""
    passed = [r for r in results if r["status"] == "pass"]
    failed = [r for r in results if r["status"] == "fail"]
    errors = [r for r in results if r["status"] in ("error", "timeout")]

    total_duration = sum(r["duration"] for r in results)

    summary = []
    summary.append("\n" + "=" * 60)
    summary.append("CODE QUALITY DASHBOARD")
    summary.append("=" * 60 + "\n")

    # Overall status
    if failed or errors:
        summary.append(f"❌ OVERALL: FAIL ({len(failed)} failures, {len(errors)} errors)")
    else:
        summary.append(f"✅ OVERALL: PASS (all {len(passed)} checks passed)")

    summary.append(f"⏱️  Total duration: {total_duration:.2f}s\n")

    # Individual check results
    summary.append("CHECK RESULTS:")
    summary.append("-" * 60)

    for result in results:
        status_icon = "✅" if result["status"] == "pass" else "❌"
        summary.append(
            f"{status_icon} {result['name']:20s} {result['duration']:6.2f}s  {result['description']}"
        )

    summary.append("\n" + "=" * 60)

    # Details for failures
    if failed:
        summary.append("\nFAILURE DETAILS:")
        summary.append("-" * 60 + "\n")
        for result in failed:
            summary.append(f"{result['name']}:")
            if result["output"]:
                summary.append(result["output"])
            summary.append("")

    # Details for errors
    if errors:
        summary.append("\nERROR DETAILS:")
        summary.append("-" * 60 + "\n")
        for result in errors:
            summary.append(f"{result['name']}: {result['error']}")
            summary.append("")

    return "\n".join(summary)


def main() -> int:
    """Run all quality checks and generate dashboard."""
    print("Running quality checks...\n")

    results = []
    for check in CHECKS:
        print(f"Running {check['name']}...", end=" ", flush=True)
        result = run_check(check)
        results.append(result)

        status_icon = "✅" if result["status"] == "pass" else "❌"
        print(f"{status_icon} ({result['duration']:.2f}s)")

    # Generate dashboard JSON
    dashboard = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": results,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r["status"] == "pass"),
            "failed": sum(1 for r in results if r["status"] == "fail"),
            "errors": sum(1 for r in results if r["status"] in ("error", "timeout")),
            "total_duration": sum(r["duration"] for r in results),
        },
    }

    # Write JSON
    output_path = Path("quality_dashboard.json")
    output_path.write_text(json.dumps(dashboard, indent=2))
    print(f"\n📊 Dashboard saved to {output_path}")

    # Print summary
    summary = generate_summary(results)
    print(summary)

    # Return non-zero if any check failed
    if dashboard["summary"]["failed"] > 0 or dashboard["summary"]["errors"] > 0:  # type: ignore[index]
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
