#!/usr/bin/env python3
"""Run All Examples — Validation Script.

Runs all examples and reports pass/fail status with timing.

Usage:
    python examples/run_all.py
    python examples/run_all.py --verbose
    python examples/run_all.py --quick  # Skip slow examples

Created: December 31, 2025
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Add examples/common to path
sys.path.insert(0, str(Path(__file__).parent))

from common.output import (
    print_header,
    print_section,
    print_metrics,
    print_footer,
    print_separator,
    print_table,
)
from common.metrics import Timer


@dataclass
class ExampleResult:
    """Result of running an example."""

    name: str
    passed: bool
    elapsed: float
    error: str | None = None


# Examples to run, in order
EXAMPLES = [
    # Quick Start
    ("hello_kagami.py", "First contact", False),
    # Core Features
    ("smarthome_demo.py", "Smart home control", False),
    ("digital_integration_demo.py", "Composio integration", False),
    ("cross_domain_triggers_demo.py", "Digital → Physical", False),
    ("wakefulness_demo.py", "Sleep-aware behavior", False),
    ("client_apps_demo.py", "Multi-platform clients", False),
    ("workshop_demo.py", "Maker tools", False),
    # Safety
    ("cbf_essentials.py", "CBF basics", False),
    ("cbf_training.py", "CBF training", True),  # slow
]


def run_example(example: str, verbose: bool = False) -> ExampleResult:
    """Run a single example and return result."""
    example_path = Path(__file__).parent / example
    project_root = Path(__file__).parent.parent

    if not example_path.exists():
        return ExampleResult(
            name=example,
            passed=False,
            elapsed=0,
            error="File not found",
        )

    start = time.perf_counter()

    # Set up environment with packages in PYTHONPATH
    env = os.environ.copy()
    packages_path = str(project_root / "packages")
    existing_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{packages_path}:{existing_path}" if existing_path else packages_path

    try:
        result = subprocess.run(
            [sys.executable, str(example_path)],
            capture_output=not verbose,
            timeout=60,  # 1 minute timeout
            text=True,
            env=env,
        )
        elapsed = time.perf_counter() - start

        if result.returncode == 0:
            return ExampleResult(name=example, passed=True, elapsed=elapsed)
        else:
            error = result.stderr[:200] if result.stderr else f"Exit code {result.returncode}"
            return ExampleResult(name=example, passed=False, elapsed=elapsed, error=error)

    except subprocess.TimeoutExpired:
        elapsed = time.perf_counter() - start
        return ExampleResult(
            name=example,
            passed=False,
            elapsed=elapsed,
            error="Timeout (60s)",
        )
    except Exception as e:
        elapsed = time.perf_counter() - start
        return ExampleResult(name=example, passed=False, elapsed=elapsed, error=str(e))


def main():
    """Run all examples and report results."""
    parser = argparse.ArgumentParser(description="Run all Kagami examples")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show example output")
    parser.add_argument("--quick", "-q", action="store_true", help="Skip slow examples")
    args = parser.parse_args()

    print_header("RUN ALL EXAMPLES", "🧪")

    results: list[ExampleResult] = []
    examples_to_run = [(e, d, s) for e, d, s in EXAMPLES if not (args.quick and s)]

    print_section(1, f"Running {len(examples_to_run)} examples")
    print()

    with Timer() as total_timer:
        for i, (example, _description, is_slow) in enumerate(examples_to_run, 1):
            status = "⏳" if is_slow and args.quick else ""
            print(f"   [{i:2d}/{len(examples_to_run)}] {example:40s} {status}", end="", flush=True)

            result = run_example(example, verbose=args.verbose)
            results.append(result)

            if result.passed:
                print(f"✓ {result.elapsed:.2f}s")
            else:
                print(f"✗ {result.error or 'Failed'}")

    # Summary
    print_separator()
    print_section(2, "Results Summary")

    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]

    print()

    if failed:
        print("   Failed examples:")
        for r in failed:
            print(f"      ✗ {r.name}: {r.error or 'Unknown error'}")
        print()

    # Results table
    print_table(
        headers=["Example", "Status", "Time"],
        rows=[[r.name, "✓ Pass" if r.passed else "✗ Fail", f"{r.elapsed:.2f}s"] for r in results],
    )

    print_metrics(
        {
            "Total time": f"{total_timer.elapsed:.2f}s",
            "Examples run": len(results),
            "Passed": len(passed),
            "Failed": len(failed),
            "Pass rate": f"{len(passed)/len(results)*100:.0f}%" if results else "N/A",
        }
    )

    success = len(failed) == 0

    print_footer(
        message="All examples passed!" if success else f"{len(failed)} examples failed",
        next_steps=[
            "Run individual examples with python examples/<name>.py",
            "Use --verbose to see full output",
            "Check error messages above for failures",
        ]
        if not success
        else [
            "Examples are ready for production",
            "Run python examples/hello_kagami.py to start",
        ],
        success=success,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
