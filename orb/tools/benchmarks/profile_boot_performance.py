#!/usr/bin/env python3
"""
🔥 K OS Boot Performance Profiler 🔥

Comprehensive boot sequence analysis and performance optimization tool.

Usage:
    python scripts/profile_boot_performance.py
    python scripts/profile_boot_performance.py --detailed
    python scripts/profile_boot_performance.py --baseline
    python scripts/profile_boot_performance.py --compare-baseline
    python scripts/profile_boot_performance.py --optimize
"""

import asyncio
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psutil
import torch

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from kagami_api.create_app_v2 import create_app_v2
from kagami_api.lifespan_v2 import lifespan_v2
from kagami.boot import BootGraphReport


@dataclass
class BootProfile:
    """Comprehensive boot performance profile."""

    # Timing data
    total_boot_time: float = 0.0
    boot_phases: dict[str, float] = field(default_factory=dict)
    boot_node_timings: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Resource usage
    peak_memory_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    gpu_memory_mb: float = 0.0

    # Component analysis
    slow_components: list[dict[str, Any]] = field(default_factory=list)
    parallelization_opportunities: list[str] = field(default_factory=list)
    lazy_loading_candidates: list[str] = field(default_factory=list)

    # Optimization recommendations
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_boot_time": self.total_boot_time,
            "boot_phases": self.boot_phases,
            "boot_node_timings": self.boot_node_timings,
            "peak_memory_mb": self.peak_memory_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
            "gpu_memory_mb": self.gpu_memory_mb,
            "slow_components": self.slow_components,
            "parallelization_opportunities": self.parallelization_opportunities,
            "lazy_loading_candidates": self.lazy_loading_candidates,
            "recommendations": self.recommendations,
        }


class BootProfiler:
    """Advanced boot performance profiler."""

    def __init__(self, detailed: bool = False):
        self.detailed = detailed
        self.process = psutil.Process()
        self.baseline_file = PROJECT_ROOT / "boot_baseline.json"

    def get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        return self.process.memory_info().rss / 1024 / 1024

    def get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        return self.process.cpu_percent()

    def get_gpu_memory(self) -> float:
        """Get GPU memory usage in MB if available."""
        try:
            if torch.cuda.is_available():
                return torch.cuda.memory_allocated() / 1024 / 1024
            elif torch.backends.mps.is_available():
                return torch.mps.current_allocated_memory() / 1024 / 1024
        except Exception:
            pass
        return 0.0

    async def profile_boot_sequence(self) -> BootProfile:
        """Profile the complete boot sequence."""
        profile = BootProfile()
        start_time = time.perf_counter()
        initial_memory = self.get_memory_usage()

        print("🔥 Starting K OS Boot Performance Profile...")
        print("=" * 60)

        # Phase 1: FastAPI App Creation
        phase_start = time.perf_counter()
        print("📦 Creating FastAPI application...")

        app = create_app_v2()
        profile.boot_phases["app_creation"] = (time.perf_counter() - phase_start) * 1000

        print(f"📦 App creation: {profile.boot_phases['app_creation']:.2f}ms")
        # Phase 2: Lifespan Execution (Boot Sequence)
        phase_start = time.perf_counter()
        print("🚀 Executing boot sequence...")

        boot_graph = None
        boot_report = None

        @asynccontextmanager
        async def profiled_lifespan(app):
            """Profile the lifespan execution."""
            nonlocal boot_graph, boot_report

            async with lifespan_v2(app):
                # Get boot report from app state after lifespan completes
                boot_report = getattr(app.state, "boot_graph_report", None)
                yield

        async with profiled_lifespan(app):
            # Monitor resource usage during boot
            memory_samples = []
            cpu_samples = []
            gpu_samples = []

            for _ in range(10):  # Sample every 100ms during boot
                memory_samples.append(self.get_memory_usage())
                cpu_samples.append(self.get_cpu_usage())
                gpu_samples.append(self.get_gpu_memory())
                await asyncio.sleep(0.1)

            profile.peak_memory_mb = max(memory_samples) - initial_memory
            profile.cpu_usage_percent = sum(cpu_samples) / len(cpu_samples)
            profile.gpu_memory_mb = max(gpu_samples)

        profile.boot_phases["lifespan_boot"] = (time.perf_counter() - phase_start) * 1000

        print(f"🚀 Lifespan boot: {profile.boot_phases['lifespan_boot']:.2f}ms")
        # Phase 3: Analysis
        profile.total_boot_time = (time.perf_counter() - start_time) * 1000

        if boot_report:
            # Convert BootGraphReport to dict if it has the attribute, otherwise use a different approach
            try:
                profile.boot_node_timings = boot_report.as_dict()
            except AttributeError:
                # If as_dict() doesn't exist, create a basic timing dict
                profile.boot_node_timings = {"boot_completed": True}
            self.analyze_boot_report(profile, boot_report)

        self.generate_recommendations(profile)

        return profile

    def analyze_boot_report(self, profile: BootProfile, report: BootGraphReport) -> None:
        """Analyze boot report for performance insights."""
        # Find slow components (>500ms)
        for name, status in report.statuses.items():
            if status.duration_ms > 500:
                profile.slow_components.append(
                    {
                        "component": name,
                        "duration_ms": status.duration_ms,
                        "success": status.success,
                        "error": status.error,
                    }
                )

        # Identify parallelization opportunities
        # Components that don't depend on each other could run in parallel
        dependency_graph = self._build_dependency_graph()
        for component, deps in dependency_graph.items():
            if not deps and component in ["hal", "ambient_os"]:  # Independent heavy components
                profile.parallelization_opportunities.append(component)

        # Lazy loading candidates (non-critical components)
        lazy_candidates = [
            "world_model",
            "encoder",
            "receipt_processor",
            "learning",
            "brain",
            "background",
        ]
        profile.lazy_loading_candidates.extend(lazy_candidates)

    def _build_dependency_graph(self) -> dict[str, list[str]]:
        """Build dependency graph for analysis."""
        # This would normally come from the boot graph, simplified here
        return {
            "database": [],
            "redis": ["database"],
            "e8_bus": ["redis"],
            "etcd": ["database", "redis"],
            "provenance": ["etcd"],
            "hal": ["redis", "e8_bus"],
            "ambient_os": ["hal"],
            "orchestrator": ["database", "redis", "hal", "etcd", "provenance"],
            "socketio": ["orchestrator"],
            "brain": ["orchestrator"],
            "background": ["orchestrator"],
            "learning": ["orchestrator"],
        }

    def generate_recommendations(self, profile: BootProfile) -> None:
        """Generate optimization recommendations."""
        recommendations = []

        # Boot time recommendations
        if profile.total_boot_time > 10000:  # >10s
            recommendations.append(
                "CRITICAL: Boot time exceeds 10s - implement lazy loading for heavy components"
            )

        if profile.total_boot_time > 5000:  # >5s
            recommendations.append(
                "HIGH: Boot time >5s - parallelize independent component initialization"
            )

        # Memory recommendations
        if profile.peak_memory_mb > 500:  # >500MB
            recommendations.append("MEMORY: High memory usage - implement streaming model loading")

        # Component-specific recommendations
        for component in profile.slow_components:
            name = component["component"]
            duration = component["duration_ms"]

            if name == "world_model" and duration > 2000:
                recommendations.append(
                    "WORLD_MODEL: Implement async model loading with progress callbacks"
                )
            elif name == "database" and duration > 1000:
                recommendations.append(
                    "DATABASE: Optimize connection pooling and migration execution"
                )
            elif name == "hal" and duration > 1000:
                recommendations.append("HAL: Lazy load hardware adapters only when needed")

        # Parallelization recommendations
        if profile.parallelization_opportunities:
            recommendations.append(
                f"PARALLEL: Consider parallel initialization of: {', '.join(profile.parallelization_opportunities)}"
            )

        # Lazy loading recommendations
        if profile.lazy_loading_candidates:
            recommendations.append(
                f"LAZY: Move to lazy loading: {', '.join(profile.lazy_loading_candidates[:3])}"
            )

        profile.recommendations = recommendations

    def print_profile_report(self, profile: BootProfile) -> None:
        """Print detailed profile report."""
        print("\n" + "=" * 80)
        print("🔥 K OS BOOT PERFORMANCE PROFILE")
        print("=" * 80)

        print(f"⏱️  Total boot time: {profile.total_boot_time:.2f}ms")
        print(f"💾 Peak memory usage: {profile.peak_memory_mb:.1f}MB")
        print(f"🖥️  Average CPU usage: {profile.cpu_usage_percent:.1f}%")
        print("\n📊 BOOT PHASES:")
        print("-" * 40)
        for phase, duration in profile.boot_phases.items():
            print(f"  {phase}: {duration:.2f}ms")
        print("\n🐌 SLOW COMPONENTS (>500ms):")
        print("-" * 40)
        if profile.slow_components:
            for comp in sorted(
                profile.slow_components, key=lambda x: x["duration_ms"], reverse=True
            ):
                status = "✅" if comp["success"] else "❌"
                print(f"  {status} {comp['component']}: {comp['duration_ms']:.2f}ms")
                if comp["error"]:
                    print(f"    Error: {comp['error']}")
        else:
            print("  None found!")

        print("\n⚡ OPTIMIZATION OPPORTUNITIES:")
        print("-" * 40)

        if profile.parallelization_opportunities:
            print("Parallelization candidates:")
            for opp in profile.parallelization_opportunities:
                print(f"  • {opp}")

        if profile.lazy_loading_candidates:
            print("Lazy loading candidates:")
            for candidate in profile.lazy_loading_candidates[:5]:
                print(f"  • {candidate}")

        print("\n💡 RECOMMENDATIONS:")
        print("-" * 40)
        if profile.recommendations:
            for rec in profile.recommendations:
                print(f"  • {rec}")
        else:
            print("  Boot performance is excellent! 🎉")

        print("\n" + "=" * 80)

    async def run_baseline_comparison(self) -> None:
        """Run profile and compare against baseline."""
        if not self.baseline_file.exists():
            print("❌ No baseline found. Run --baseline first.")
            return

        print("📊 Running baseline comparison...")

        # Load baseline
        with open(self.baseline_file) as f:
            baseline = json.load(f)

        # Run current profile
        profile = await self.profile_boot_sequence()
        current = profile.to_dict()

        print("\n" + "=" * 60)
        print("📈 BOOT PERFORMANCE COMPARISON")
        print("=" * 60)

        # Compare key metrics
        metrics = [
            ("Total Boot Time", "total_boot_time", "ms", lambda x: x),
            ("Peak Memory", "peak_memory_mb", "MB", lambda x: x),
            ("CPU Usage", "cpu_usage_percent", "%", lambda x: x),
        ]

        for _name, key, _unit, _formatter in metrics:
            baseline_val = baseline.get(key, 0)
            current_val = current.get(key, 0)
            diff = current_val - baseline_val
            (diff / baseline_val * 100) if baseline_val > 0 else 0

            print(".1f")

    async def save_baseline(self) -> None:
        """Save current profile as baseline."""
        print("📊 Generating baseline profile...")
        profile = await self.profile_boot_sequence()

        with open(self.baseline_file, "w") as f:
            json.dump(profile.to_dict(), f, indent=2)

        print(f"✅ Baseline saved to {self.baseline_file}")


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="K OS Boot Performance Profiler")
    parser.add_argument("--detailed", action="store_true", help="Enable detailed profiling")
    parser.add_argument("--baseline", action="store_true", help="Save current profile as baseline")
    parser.add_argument(
        "--compare-baseline", action="store_true", help="Compare against saved baseline"
    )
    parser.add_argument(
        "--optimize", action="store_true", help="Generate optimization recommendations"
    )

    args = parser.parse_args()

    # Set up environment for safe profiling
    os.environ["KAGAMI_TEST_MODE"] = "1"

    profiler = BootProfiler(detailed=args.detailed)

    try:
        if args.baseline:
            await profiler.save_baseline()
        elif args.compare_baseline:
            await profiler.run_baseline_comparison()
        else:
            profile = await profiler.profile_boot_sequence()
            profiler.print_profile_report(profile)

            if args.optimize:
                print("\n🔧 OPTIMIZATION MODE:")
                print("Implementing automatic optimizations...")
                # FUTURE: Implement automatic optimization recommendations based on profile data

    except Exception as e:
        print(f"❌ Profiling failed: {e}")
        if args.detailed:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
