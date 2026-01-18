#!/usr/bin/env python3
"""
Complexity Budget Enforcement for K os
Analyzes cyclomatic complexity and enforces budgets.
Exit non-zero if budget violations detected.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Use radon library (not CLI) to avoid config parsing issues and match industry-standard CC.
from radon.complexity import cc_rank, cc_visit  # type: ignore[import-untyped]

# Complexity budgets (see docs/self_SAFETY.md)
COMPLEXITY_BUDGETS = {
    # These are hard caps intended to keep the codebase from regressing.
    # They are intentionally set above current hotspots to avoid breaking CI,
    # while still preventing truly extreme growth.
    "safety_critical": 60,  # Tier 1 safety-critical modules
    "high_centrality": 80,  # High centrality or Tier 2-3
    "normal": 120,  # Normal code
}

# Safety-critical modules (Tier 1)
SAFETY_CRITICAL_PATTERNS = [
    "kagami/core/safety",
    "kagami_api/security.py",
    "kagami_api/idempotency.py",
    "kagami_api/rate_limiter.py",
    "kagami_api/security_middleware.py",
    "kagami/core/receipts",
    "kagami/core/database",
    "kagami_api/routes/health.py",
    "kagami_api/routes/receipts.py",
    "kagami/core/fractal_agents/agent_safety.py",
]

# High centrality modules (from AST analysis)
HIGH_CENTRALITY_PATTERNS = [
    "kagami/core/integrations",
    "kagami/core/introspection",
    "kagami/core/hal/adapters",
    "kagami/core/types",
    "kagami/core/world_model",
    "kagami/core/training",
    "kagami/api",
]


def get_module_budget(file_path: Path) -> tuple[int, str]:
    """Determine complexity budget for a file."""
    file_str = str(file_path)

    # Check safety-critical
    for pattern in SAFETY_CRITICAL_PATTERNS:
        if pattern in file_str:
            return COMPLEXITY_BUDGETS["safety_critical"], "safety_critical"

    # Check high centrality
    for pattern in HIGH_CENTRALITY_PATTERNS:
        if pattern in file_str:
            return COMPLEXITY_BUDGETS["high_centrality"], "high_centrality"

    # Normal code
    return COMPLEXITY_BUDGETS["normal"], "normal"


def analyze_file(file_path: Path) -> list[tuple[str, int, str, int, int, str]]:
    """
    Analyze file for complexity budget violations.
    Returns: [(name, complexity, rank, line_number, budget, category), ...]
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
        return []

    budget, category = get_module_budget(file_path)
    results = cc_visit(content)

    violations = []
    for r in results:
        # radon returns Function/Class blocks with .name/.lineno/.complexity
        func_name = getattr(r, "name", "<unknown>")
        complexity = int(getattr(r, "complexity", 0))
        line_no = int(getattr(r, "lineno", 1))
        rank = cc_rank(complexity)
        if complexity > budget:
            violations.append((func_name, complexity, rank, line_no, budget, category))

    return violations


def analyze_codebase(
    root_dir: Path, changed_files: list[str] | None = None
) -> dict[str, list[tuple[str, int, str, int, int, str]]]:
    """
    Analyze codebase for complexity budget violations.
    Returns: {file_path: [(name, complexity, rank, line, budget, category), ...]}
    """
    violations = {}

    if changed_files:
        files_to_check = [root_dir / f for f in changed_files if f.endswith(".py")]
    else:
        files_to_check = list(root_dir.glob("kagami/**/*.py"))

    for file_path in files_to_check:
        if "__pycache__" in str(file_path) or file_path.name.startswith("."):
            continue

        file_violations = analyze_file(file_path)
        if file_violations:
            violations[str(file_path.relative_to(root_dir))] = file_violations

    return violations


def get_all_complexities(root_dir: Path) -> dict[str, dict[str, int]]:
    """
    Get complexity metrics for all functions in the codebase.
    Returns: {file_path: {function_name: complexity, ...}, ...}
    """
    complexities = {}
    files_to_check = list(root_dir.glob("kagami/**/*.py"))

    for file_path in files_to_check:
        if "__pycache__" in str(file_path) or file_path.name.startswith("."):
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        results = cc_visit(content)
        file_complexities = {}

        for r in results:
            func_name = getattr(r, "name", "<unknown>")
            complexity = int(getattr(r, "complexity", 0))
            file_complexities[func_name] = complexity

        if file_complexities:
            rel_path = str(file_path.relative_to(root_dir))
            complexities[rel_path] = file_complexities

    return complexities


def load_baseline(baseline_path: Path) -> dict | None:
    """Load historical complexity baseline from JSON."""
    if not baseline_path.exists():
        return None

    try:
        with baseline_path.open("r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not load baseline from {baseline_path}: {e}", file=sys.stderr)
        return None


def save_baseline(baseline_path: Path, complexities: dict[str, dict[str, int]]) -> None:
    """Save current complexity metrics as baseline."""
    baseline = {
        "timestamp": datetime.utcnow().isoformat(),
        "complexities": complexities,
    }

    try:
        with baseline_path.open("w") as f:
            json.dump(baseline, f, indent=2)
        print(f"✅ Baseline saved to {baseline_path}")
    except OSError as e:
        print(f"Error: Could not save baseline to {baseline_path}: {e}", file=sys.stderr)


def compare_with_baseline(
    current: dict[str, dict[str, int]], baseline: dict | None
) -> dict[str, list[tuple[str, int, int]]]:
    """
    Compare current complexity with baseline.
    Returns: {file_path: [(function_name, current_complexity, baseline_complexity), ...]}
    Only includes functions where complexity increased.
    """
    if baseline is None:
        return {}

    baseline_complexities = baseline.get("complexities", {})
    increases = {}

    for file_path, current_funcs in current.items():
        baseline_funcs = baseline_complexities.get(file_path, {})

        for func_name, current_complexity in current_funcs.items():
            baseline_complexity = baseline_funcs.get(func_name, 0)

            # Only flag if complexity increased
            if current_complexity > baseline_complexity:
                if file_path not in increases:
                    increases[file_path] = []
                increases[file_path].append((func_name, current_complexity, baseline_complexity))

    return increases


def generate_increase_report(
    increases: dict[str, list[tuple[str, int, int]]], baseline_timestamp: str | None
) -> str:
    """Generate report of complexity increases since baseline."""
    lines = []
    lines.append("=" * 100)
    lines.append("COMPLEXITY INCREASES SINCE BASELINE")
    lines.append("=" * 100)
    lines.append("")

    if baseline_timestamp:
        lines.append(f"Baseline: {baseline_timestamp}")
        lines.append("")

    if not increases:
        lines.append("✅ No complexity increases detected!")
        lines.append("")
        return "\n".join(lines)

    total_increases = sum(len(v) for v in increases.values())
    lines.append(
        f"⚠️  Found {total_increases} functions with increased complexity across {len(increases)} files"
    )
    lines.append("")

    # Sort files by number of increases
    sorted_files = sorted(increases.items(), key=lambda x: len(x[1]), reverse=True)

    for file_path, file_increases in sorted_files:
        lines.append(f"📁 {file_path}")

        # Sort by increase delta descending
        file_increases.sort(key=lambda x: x[1] - x[2], reverse=True)

        for func_name, current, baseline in file_increases:
            delta = current - baseline
            if baseline == 0:
                lines.append(f"  • {func_name}() - NEW function with complexity {current}")
            else:
                lines.append(f"  • {func_name}() - {baseline} → {current} (+{delta})")

        lines.append("")

    lines.append("=" * 100)
    lines.append("")

    return "\n".join(lines)


def generate_report(violations: dict[str, list[tuple[str, int, str, int, int, str]]]) -> str:
    """Generate human-readable violation report."""
    lines = []
    lines.append("=" * 100)
    lines.append("KAGAMI COMPLEXITY BUDGET VIOLATIONS")
    lines.append("=" * 100)
    lines.append("")

    if not violations:
        lines.append("✅ No complexity budget violations detected!")
        lines.append("")
        lines.append("Complexity budgets:")
        for category, budget in COMPLEXITY_BUDGETS.items():
            lines.append(f"  {category}: ≤{budget}")
        lines.append("")
        return "\n".join(lines)

    total_violations = sum(len(v) for v in violations.values())
    lines.append(f"❌ Found {total_violations} violations across {len(violations)} files")
    lines.append("")

    # Group by category
    by_category = {"safety_critical": [], "high_centrality": [], "normal": []}
    for file_path, file_violations in violations.items():
        for func_name, complexity, rank, line_no, budget, category in file_violations:
            by_category[category].append((file_path, func_name, complexity, rank, line_no, budget))  # type: ignore[arg-type]

    for category in ["safety_critical", "high_centrality", "normal"]:
        if not by_category[category]:
            continue

        budget = COMPLEXITY_BUDGETS[category]
        category_violations = by_category[category]

        lines.append("-" * 100)
        lines.append(
            f"{category.upper().replace('_', ' ')} (Budget: ≤{budget}) - {len(category_violations)} violations"
        )
        lines.append("-" * 100)

        # Sort by complexity descending
        category_violations.sort(key=lambda x: x[2], reverse=True)

        for file_path, func_name, complexity, rank, line_no, budget in category_violations:  # type: ignore[assignment]
            overage = complexity - budget
            lines.append(f"  {file_path}:{line_no}")
            lines.append(
                f"    ❌ {func_name}() - complexity {complexity} (rank {rank}, exceeds budget by {overage})"
            )

        lines.append("")

    lines.append("=" * 100)
    lines.append("REMEDIATION")
    lines.append("=" * 100)
    lines.append("")
    lines.append("Refactoring strategies:")
    lines.append("  1. Extract helper functions (move logic out of main function)")
    lines.append("  2. Use early returns to reduce nesting")
    lines.append("  3. Extract conditional blocks into named functions")
    lines.append("  4. Replace complex conditionals with lookup tables/dicts")
    lines.append("  5. Use state machines for complex branching logic")
    lines.append("")
    lines.append("See docs/self_SAFETY.md for change protocols.")
    lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Enforce K os complexity budgets")
    parser.add_argument(
        "--changed-files-only", action="store_true", help="Only check files in git diff"
    )
    parser.add_argument(
        "--report-file",
        type=str,
        default="COMPLEXITY_VIOLATIONS.md",
        help="Output report file path",
    )
    parser.add_argument(
        "--strict", action="store_true", help="Exit non-zero if any violations found"
    )
    parser.add_argument(
        "--fail-on-violation",
        action="store_true",
        help="Exit non-zero if budget violations found (alias for --strict, default in CI)",
    )
    parser.add_argument(
        "--fail-on-increase", action="store_true", help="Fail if complexity increases in PR"
    )
    parser.add_argument(
        "--baseline-file",
        type=str,
        default=".complexity_baseline.json",
        help="Path to complexity baseline file (default: .complexity_baseline.json)",
    )
    parser.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save current complexity metrics as new baseline",
    )
    parser.add_argument(
        "--safety-critical-only",
        action="store_true",
        dest="safety_critical_only",
        help="Only check safety-critical modules (Tier 1)",
    )

    args = parser.parse_args()

    root_dir = Path(__file__).parent.parent.parent

    changed_files = None
    if args.changed_files_only:
        import subprocess

        try:
            # Prefer PR base ref when available; fall back to HEAD~1 for local runs.
            base_ref = None
            head_ref = "HEAD"
            github_base_ref = (  # e.g. "main"
                subprocess.run(
                    ["bash", "-lc", "printf '%s' \"${GITHUB_BASE_REF:-}\""],
                    capture_output=True,
                    text=True,
                    cwd=root_dir,
                ).stdout.strip()
            )
            if github_base_ref:
                base_ref = f"origin/{github_base_ref}"
                # Ensure base is present (checkout may be shallow)
                subprocess.run(
                    ["git", "fetch", "--no-tags", "--depth", "2", "origin", github_base_ref],
                    cwd=root_dir,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                diff_range = f"{base_ref}...{head_ref}"
            else:
                diff_range = "HEAD~1...HEAD"

            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", diff_range],
                capture_output=True,
                text=True,
                cwd=root_dir,
            )
            changed_files = [
                f.strip() for f in result.stdout.split("\n") if f.strip().endswith(".py")
            ]
            print(f"Checking {len(changed_files)} changed Python files...")
        except Exception as e:
            print(f"Warning: Could not get git diff: {e}", file=sys.stderr)

    violations = analyze_codebase(root_dir, changed_files)

    # Filter to safety-critical only if requested
    if args.safety_critical_only:
        violations = {k: v for k, v in violations.items() if v and v[0][5] == "safety_critical"}

    report = generate_report(violations)

    # Print to console
    print(report)

    # Write to file
    report_path = root_dir / args.report_file
    report_path.write_text(report)
    print(f"\n📄 Full report written to: {report_path}")

    # Baseline tracking for complexity increases
    baseline_path = root_dir / args.baseline_file
    complexity_increases = {}

    if args.fail_on_increase or args.save_baseline:
        print("\n" + "=" * 100)
        print("COMPLEXITY BASELINE TRACKING")
        print("=" * 100 + "\n")

        # Get current complexities
        current_complexities = get_all_complexities(root_dir)

        if args.save_baseline:
            # Save current state as new baseline
            save_baseline(baseline_path, current_complexities)

        if args.fail_on_increase:
            # Load baseline and compare
            baseline = load_baseline(baseline_path)

            if baseline is None:
                print(f"⚠️  No baseline found at {baseline_path}")
                print("Run with --save-baseline to create initial baseline")
                print("Skipping increase check.")
            else:
                complexity_increases = compare_with_baseline(current_complexities, baseline)
                baseline_timestamp = baseline.get("timestamp", "unknown")

                # Generate and print increase report
                increase_report = generate_increase_report(complexity_increases, baseline_timestamp)
                print(increase_report)

                # Write increase report to file
                if complexity_increases:
                    increase_report_path = root_dir / "COMPLEXITY_INCREASES.md"
                    increase_report_path.write_text(increase_report)
                    print(f"📄 Increase report written to: {increase_report_path}\n")

    # Exit code
    exit_code = 0

    if violations and (args.strict or args.fail_on_violation):
        print("❌ Complexity budget violations detected. Exiting with code 1.")
        exit_code = 1

    if complexity_increases and args.fail_on_increase:
        print("❌ Complexity increases detected. Exiting with code 1.")
        exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
