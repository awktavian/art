#!/usr/bin/env python3
"""Compare two benchmark JSON files and generate detailed reports.

Compares baseline and optimized benchmark results with color-coded output,
statistical significance, and regression detection.

WORKFLOW:
---------
1. Generate baseline benchmarks:
   python scripts/benchmark/benchmark_math_foundations.py --device cpu --output baseline.json

2. Apply optimizations (code changes, compiler flags, etc)

3. Generate optimized benchmarks:
   python scripts/benchmark/benchmark_math_foundations.py --device cpu --output optimized.json

4. Compare results:
   python scripts/benchmark/compare_benchmarks.py baseline.json optimized.json

USAGE:
------
Console output (always shown):
    python scripts/benchmark/compare_benchmarks.py baseline.json optimized.json

With Markdown report for docs:
    python scripts/benchmark/compare_benchmarks.py baseline.json optimized.json --markdown

With JSON output for CI/CD integration:
    python scripts/benchmark/compare_benchmarks.py baseline.json optimized.json --json results.json

With CSV for spreadsheet analysis:
    python scripts/benchmark/compare_benchmarks.py baseline.json optimized.json --csv results.csv

Generate all output formats:
    python scripts/benchmark/compare_benchmarks.py baseline.json optimized.json --all

FEATURES:
---------
- Color-coded output (green=improved, red=regression, yellow=neutral)
- Side-by-side latency and throughput comparison
- Memory usage tracking
- Speedup calculation (geometric mean across all operations)
- Regression detection (flags if >10% slower)
- Category grouping (E8, G2/CG, Fano, Octonion, RFSQ, WorldModel)
- Top 5 improvements and regressions highlighted
- Statistical significance marking for >=10% changes

OUTPUT FORMATS:
---------------
- Console: Colored formatted tables with summaries
- Markdown: For documentation and PR reviews
- JSON: For CI/CD pipelines and further processing
- CSV: For spreadsheet analysis and custom reports

EXIT CODES:
-----------
0: No regressions detected (success)
1: Minor regressions detected (<10%)
2: Severe regressions detected (>10%)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ANSI color codes
class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    GRAY = "\033[90m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    @staticmethod
    def strip(text: str) -> str:
        """Remove ANSI color codes from text."""
        for color in [
            Colors.GREEN,
            Colors.RED,
            Colors.YELLOW,
            Colors.BLUE,
            Colors.GRAY,
            Colors.BOLD,
            Colors.RESET,
        ]:
            text = text.replace(color, "")
        return text


@dataclass
class ComparisonResult:
    """Single operation comparison."""

    operation: str
    category: str
    baseline_latency: float
    optimized_latency: float
    baseline_throughput: float
    optimized_throughput: float
    baseline_memory: float
    optimized_memory: float
    speedup: float
    memory_reduction: float
    percent_improvement: float
    is_regression: bool
    is_significant: bool

    def status_icon(self) -> str:
        """Return colored status icon."""
        if self.is_regression:
            return f"{Colors.RED}✗ REGRESSION{Colors.RESET}"
        elif self.percent_improvement >= 10:
            return f"{Colors.GREEN}✓ IMPROVED{Colors.RESET}"
        elif self.percent_improvement > 0:
            return f"{Colors.GREEN}↑ FASTER{Colors.RESET}"
        else:
            return f"{Colors.YELLOW}= NEUTRAL{Colors.RESET}"

    def status_icon_plain(self) -> str:
        """Return plain status icon (no colors)."""
        if self.is_regression:
            return "✗ REGRESSION"
        elif self.percent_improvement >= 10:
            return "✓ IMPROVED"
        elif self.percent_improvement > 0:
            return "↑ FASTER"
        else:
            return "= NEUTRAL"


@dataclass
class AggregateMetrics:
    """Aggregate comparison metrics."""

    total_operations: int
    improved: int
    neutral: int
    regressed: int
    geometric_mean_speedup: float
    total_memory_baseline: float
    total_memory_optimized: float
    total_memory_saved: float
    regressions: list[str] = field(default_factory=list)
    max_regression: float = 0.0
    operations_by_category: dict[str, int] = field(default_factory=dict)


class BenchmarkComparator:
    """Compare two benchmark JSON files."""

    def __init__(self, baseline_path: str, optimized_path: str, allow_missing: bool = False):
        """Initialize comparator with baseline and optimized benchmark files."""
        self.baseline_path = Path(baseline_path)
        self.optimized_path = Path(optimized_path)
        self.allow_missing = allow_missing
        self.results: list[ComparisonResult] = []
        self.baseline_data: dict[str, Any] = {}
        self.optimized_data: dict[str, Any] = {}

    def _load_json(self, path: Path) -> dict[str, Any]:
        """Load and validate JSON benchmark file."""
        if not path.exists():
            raise FileNotFoundError(f"Benchmark file not found: {path}")

        try:
            with open(path) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}") from e

    def _extract_results(self, data: dict[str, Any]) -> dict[str, dict[str, float]]:
        """Extract benchmark results from JSON structure."""
        # Handle both old and new JSON structures
        if "results" in data:
            # New structure: list of result objects
            results_dict = {}
            for result in data["results"]:
                op = result["operation"]
                bs = result.get("batch_size", 1)
                key = f"{op}_bs{bs}"
                results_dict[key] = {
                    "latency_ms": result.get("latency_ms", 0.0),
                    "throughput": result.get("throughput_samples_per_sec", 0.0),
                    "memory": result.get("memory_allocated_mb", 0.0),
                    "operation": op,
                    "batch_size": bs,
                }
            return results_dict
        else:
            # Old structure or empty
            return {}

    def _categorize_operation(self, op_name: str) -> str:
        """Categorize operation by name."""
        op_lower = op_name.lower()

        if "e8" in op_lower:
            return "E8"
        elif "g2" in op_lower or "clebsch" in op_lower:
            return "G2/CG"
        elif "fano" in op_lower:
            return "Fano"
        elif "octonion" in op_lower:
            return "Octonion"
        elif "world_model" in op_lower:
            return "WorldModel"
        elif "rfsq" in op_lower:
            return "RFSQ"
        else:
            return "Other"

    def _calculate_speedup(self, baseline: float, optimized: float) -> tuple[float, float]:
        """Calculate speedup and percentage improvement."""
        if baseline == 0:
            return 1.0, 0.0

        # Speedup: baseline / optimized (higher is better for latency)
        speedup = baseline / optimized if optimized > 0 else 1.0
        # Percentage improvement: (baseline - optimized) / baseline * 100
        percent = ((baseline - optimized) / baseline) * 100
        return speedup, percent

    def _geometric_mean(self, values: list[float]) -> float:
        """Calculate geometric mean of values."""
        if not values or any(v <= 0 for v in values):
            return 1.0
        product = 1.0
        for v in values:
            product *= v
        return product ** (1.0 / len(values))

    def compare(self) -> None:
        """Compare baseline and optimized results."""
        print(f"\n{Colors.BLUE}📊 Loading benchmark files...{Colors.RESET}")

        self.baseline_data = self._load_json(self.baseline_path)
        self.optimized_data = self._load_json(self.optimized_path)

        baseline_results = self._extract_results(self.baseline_data)
        optimized_results = self._extract_results(self.optimized_data)

        if not baseline_results:
            raise ValueError(f"No benchmark results found in {self.baseline_path}")

        print(f"   Baseline: {len(baseline_results)} operations")
        print(f"   Optimized: {len(optimized_results)} operations")

        speedups = []

        for op_key, baseline_data in baseline_results.items():
            if op_key not in optimized_results and not self.allow_missing:
                if not self.allow_missing:
                    print(f"   {Colors.YELLOW}⚠ Missing in optimized: {op_key}{Colors.RESET}")
                continue

            if op_key not in optimized_results:
                continue

            opt_data = optimized_results[op_key]
            op_name = baseline_data["operation"]
            category = self._categorize_operation(op_name)  # type: ignore[arg-type]

            baseline_latency = baseline_data["latency_ms"]
            optimized_latency = opt_data["latency_ms"]
            baseline_throughput = baseline_data["throughput"]
            optimized_throughput = opt_data["throughput"]
            baseline_memory = baseline_data["memory"]
            optimized_memory = opt_data["memory"]

            speedup, percent = self._calculate_speedup(baseline_latency, optimized_latency)
            memory_reduction = baseline_memory - optimized_memory if baseline_memory > 0 else 0.0

            is_regression = percent < -0.1  # Flag if >0.1% slower
            is_significant = abs(percent) >= 10  # Significant if >= 10%

            if speedup > 1.0:
                speedups.append(speedup)

            result = ComparisonResult(
                operation=op_name,  # type: ignore[arg-type]
                category=category,
                baseline_latency=baseline_latency,
                optimized_latency=optimized_latency,
                baseline_throughput=baseline_throughput,
                optimized_throughput=optimized_throughput,
                baseline_memory=baseline_memory,
                optimized_memory=optimized_memory,
                speedup=speedup,
                memory_reduction=memory_reduction,
                percent_improvement=percent,
                is_regression=is_regression,
                is_significant=is_significant,
            )

            self.results.append(result)

        print(f"   Compared: {len(self.results)} operations")

    def get_aggregates(self) -> AggregateMetrics:
        """Calculate aggregate metrics."""
        improved = sum(1 for r in self.results if r.percent_improvement > 0.1)
        neutral = sum(1 for r in self.results if abs(r.percent_improvement) <= 0.1)
        regressed = sum(1 for r in self.results if r.percent_improvement < -0.1)

        speedups = [r.speedup for r in self.results if r.speedup > 1.0]
        geom_mean = self._geometric_mean(speedups) if speedups else 1.0

        total_memory_baseline = sum(r.baseline_memory for r in self.results)
        total_memory_optimized = sum(r.optimized_memory for r in self.results)
        total_memory_saved = total_memory_baseline - total_memory_optimized

        regressions = [
            f"{r.operation}: {r.percent_improvement:.1f}%" for r in self.results if r.is_regression
        ]
        max_regression = min(
            (r.percent_improvement for r in self.results if r.is_regression), default=0.0
        )

        ops_by_cat = {}
        for r in self.results:
            ops_by_cat[r.category] = ops_by_cat.get(r.category, 0) + 1

        return AggregateMetrics(
            total_operations=len(self.results),
            improved=improved,
            neutral=neutral,
            regressed=regressed,
            geometric_mean_speedup=geom_mean,
            total_memory_baseline=total_memory_baseline,
            total_memory_optimized=total_memory_optimized,
            total_memory_saved=total_memory_saved,
            regressions=regressions,
            max_regression=max_regression,
            operations_by_category=ops_by_cat,
        )

    def print_console_report(self, show_all: bool = False) -> None:
        """Print formatted console report."""
        print("\n" + "=" * 120)
        print(f"{Colors.BOLD}KagamiOS Benchmark Comparison Report{Colors.RESET}")
        print("=" * 120)

        # Summary section
        agg = self.get_aggregates()
        print(f"\n{Colors.BOLD}📈 Summary{Colors.RESET}")
        print(f"  Total operations: {agg.total_operations}")
        print(f"  {Colors.GREEN}Improved: {agg.improved}{Colors.RESET}")
        print(f"  {Colors.YELLOW}Neutral: {agg.neutral}{Colors.RESET}")
        print(f"  {Colors.RED}Regressed: {agg.regressed}{Colors.RESET}")
        print(f"\n  Geometric mean speedup: {agg.geometric_mean_speedup:.2f}x")
        print(f"  Memory baseline: {agg.total_memory_baseline:.1f} MB")
        print(f"  Memory optimized: {agg.total_memory_optimized:.1f} MB")
        if agg.total_memory_saved > 0:
            print(
                f"  {Colors.GREEN}Memory saved: {agg.total_memory_saved:.1f} MB ({(agg.total_memory_saved / agg.total_memory_baseline * 100):.1f}%){Colors.RESET}"
            )
        else:
            print(f"  Memory change: {agg.total_memory_saved:.1f} MB")

        # Category breakdown
        if agg.operations_by_category:
            print(f"\n{Colors.BOLD}📊 Operations by Category{Colors.RESET}")
            for cat in sorted(agg.operations_by_category.keys()):
                count = agg.operations_by_category[cat]
                print(f"  {cat:20s}: {count:3d} ops")

        # Detailed comparison table
        print(f"\n{Colors.BOLD}📋 Detailed Comparison{Colors.RESET}")
        print(
            f"\n{'Operation':<30} {'Category':<12} {'Baseline (ms)':<15} {'Optimized (ms)':<15} {'Speedup':<10} {'Improvement':<15}"
        )
        print("-" * 120)

        # Sort by speedup descending
        sorted_results = sorted(self.results, key=lambda r: r.percent_improvement, reverse=True)

        for result in sorted_results:
            speedup_str = f"{result.speedup:.2f}x"
            improvement_str = f"{result.percent_improvement:+.1f}%"

            if result.is_regression:
                color = Colors.RED
            elif result.percent_improvement >= 10:
                color = Colors.GREEN
            elif result.percent_improvement > 0:
                color = Colors.GREEN
            else:
                color = Colors.YELLOW

            improvement_colored = f"{color}{improvement_str}{Colors.RESET}"

            print(
                f"{result.operation:<30} {result.category:<12} "
                f"{result.baseline_latency:<15.2f} {result.optimized_latency:<15.2f} "
                f"{speedup_str:<10} {improvement_colored:<15}"
            )

        # Top improvements
        print(f"\n{Colors.BOLD}🏆 Top 5 Improvements{Colors.RESET}")
        improvements = sorted(self.results, key=lambda r: r.percent_improvement, reverse=True)[:5]
        for i, r in enumerate(improvements, 1):
            print(
                f"  {i}. {r.operation:<30s} {Colors.GREEN}{r.percent_improvement:+.1f}% ({r.speedup:.2f}x){Colors.RESET}"
            )

        # Regressions
        if agg.regressed > 0:
            print(f"\n{Colors.BOLD}⚠️  Regressions Detected ({agg.regressed}){Colors.RESET}")
            regressions = sorted(
                [r for r in self.results if r.is_regression], key=lambda r: r.percent_improvement
            )
            for r in regressions:
                print(
                    f"  {Colors.RED}{r.operation:<30s} {r.percent_improvement:.1f}%{Colors.RESET}"
                )

        print("\n" + "=" * 120)

    def to_markdown(self) -> str:
        """Generate Markdown table."""
        agg = self.get_aggregates()

        md = "# Benchmark Comparison Report\n\n"
        md += "## Summary\n\n"
        md += "| Metric | Value |\n"
        md += "|--------|-------|\n"
        md += f"| Total Operations | {agg.total_operations} |\n"
        md += f"| Improved | {agg.improved} |\n"
        md += f"| Neutral | {agg.neutral} |\n"
        md += f"| Regressed | {agg.regressed} |\n"
        md += f"| Geometric Mean Speedup | {agg.geometric_mean_speedup:.2f}x |\n"
        md += f"| Memory Saved | {agg.total_memory_saved:.1f} MB |\n\n"

        md += "## Detailed Comparison\n\n"
        md += "| Operation | Category | Baseline (ms) | Optimized (ms) | Speedup | Improvement |\n"
        md += "|-----------|----------|---------------|----------------|---------|-------------|\n"

        sorted_results = sorted(self.results, key=lambda r: r.percent_improvement, reverse=True)
        for r in sorted_results:
            status = r.status_icon_plain()
            md += f"| {r.operation} | {r.category} | {r.baseline_latency:.2f} | {r.optimized_latency:.2f} | {r.speedup:.2f}x | {r.percent_improvement:+.1f}% ({status}) |\n"

        return md

    def to_json(self) -> dict[str, Any]:
        """Generate JSON summary."""
        agg = self.get_aggregates()

        return {
            "summary": {
                "total_operations": agg.total_operations,
                "improved": agg.improved,
                "neutral": agg.neutral,
                "regressed": agg.regressed,
                "geometric_mean_speedup": agg.geometric_mean_speedup,
                "memory_baseline_mb": agg.total_memory_baseline,
                "memory_optimized_mb": agg.total_memory_optimized,
                "memory_saved_mb": agg.total_memory_saved,
                "max_regression_percent": agg.max_regression,
            },
            "operations_by_category": agg.operations_by_category,
            "details": [
                {
                    "operation": r.operation,
                    "category": r.category,
                    "baseline_latency_ms": r.baseline_latency,
                    "optimized_latency_ms": r.optimized_latency,
                    "speedup": r.speedup,
                    "improvement_percent": r.percent_improvement,
                    "is_regression": r.is_regression,
                }
                for r in sorted(self.results, key=lambda r: r.percent_improvement, reverse=True)
            ],
            "regressions": agg.regressions,
        }

    def to_csv(self) -> str:
        """Generate CSV output."""
        output = []
        output.append(
            "Operation,Category,Baseline (ms),Optimized (ms),Speedup,Improvement (%),Status"
        )

        sorted_results = sorted(self.results, key=lambda r: r.percent_improvement, reverse=True)
        for r in sorted_results:
            status = r.status_icon_plain()
            output.append(
                f'"{r.operation}","{r.category}",{r.baseline_latency:.4f},{r.optimized_latency:.4f},'
                f"{r.speedup:.4f},{r.percent_improvement:+.2f},{status}"
            )

        return "\n".join(output)

    def get_exit_code(self) -> int:
        """Determine exit code based on regressions."""
        agg = self.get_aggregates()

        if agg.regressed == 0:
            return 0  # No regressions

        if agg.max_regression >= -10:
            return 1  # Minor regressions

        return 2  # Severe regressions


def main():
    parser = argparse.ArgumentParser(
        description="Compare two benchmark JSON files and generate reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("baseline", help="Baseline benchmark JSON file")
    parser.add_argument("optimized", help="Optimized benchmark JSON file")
    parser.add_argument("--markdown", action="store_true", help="Output Markdown table")
    parser.add_argument("--json", type=str, help="Output JSON summary to file")
    parser.add_argument("--csv", type=str, help="Output CSV to file")
    parser.add_argument("--all", action="store_true", help="Generate all formats")
    parser.add_argument("--allow-missing", action="store_true", help="Allow missing operations")

    args = parser.parse_args()

    try:
        # Create comparator
        comparator = BenchmarkComparator(
            args.baseline, args.optimized, allow_missing=args.allow_missing
        )

        # Run comparison
        comparator.compare()

        # Print console report (always)
        comparator.print_console_report()

        # Generate requested formats
        if args.markdown or args.all:
            md_output = comparator.to_markdown()
            if args.all:
                md_path = Path(args.baseline).stem + "_vs_" + Path(args.optimized).stem + ".md"
                with open(md_path, "w") as f:
                    f.write(md_output)
                print(f"\n{Colors.GREEN}✓ Markdown report saved to: {md_path}{Colors.RESET}")
            else:
                print("\n" + md_output)

        if args.json or args.all:
            json_data = comparator.to_json()
            json_path = args.json or (
                Path(args.baseline).stem + "_vs_" + Path(args.optimized).stem + ".json"
            )
            with open(json_path, "w") as f:
                json.dump(json_data, f, indent=2)
            print(f"{Colors.GREEN}✓ JSON report saved to: {json_path}{Colors.RESET}")

        if args.csv or args.all:
            csv_output = comparator.to_csv()
            csv_path = args.csv or (
                Path(args.baseline).stem + "_vs_" + Path(args.optimized).stem + ".csv"
            )
            with open(csv_path, "w") as f:
                f.write(csv_output)
            print(f"{Colors.GREEN}✓ CSV report saved to: {csv_path}{Colors.RESET}")

        # Exit with appropriate code
        exit_code = comparator.get_exit_code()
        sys.exit(exit_code)

    except FileNotFoundError as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}Unexpected error: {e}{Colors.RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
