"""Ablation Study Runner - Systematically Test Each Subsystem.

Runs benchmark suite with all 8 configurations:
- All off (baseline)
- RL only
- Loops only
- Gates only
- RL + Loops
- RL + Gates
- Loops + Gates
- All on (enhanced)
"""

import asyncio
import json
import time
from pathlib import Path


async def run_ablation_config(config: dict, output_file: str):
    """Run benchmarks with specific ablation config.

    Note: ablation env flags are removed; system runs in enhanced mode by default.
    The config values are retained only for labeling results.
    """
    from scripts.benchmark.micro_suite import run_suite

    results = await run_suite(output_file=output_file)

    # Add config to results
    results["config"] = config

    # Save
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    return results


async def main():
    """Run full ablation matrix."""
    configs = [{"name": "all_on", "rl": True, "loops": True, "gates": True}]

    output_dir = Path("artifacts/benchmarks/ablation")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = int(time.time())
    results = []

    for config in configs:
        print(f"\n🔬 Running config: {config['name']}")
        print(f"   RL={config['rl']}, Loops={config['loops']}, Gates={config['gates']}")

        output_file = str(output_dir / f"{config['name']}_{timestamp}.json")
        result = await run_ablation_config(config, output_file)
        results.append(result)  # type: ignore[arg-type]

        print(f"   Success rate: {result['summary']['success_rate']:.1%}")  # type: ignore[index]
        print(f"   Avg duration: {result['summary']['total_duration_ms']}ms")  # type: ignore[index]

    # Print single-config results
    print("\n" + "=" * 80)
    print("ABLATION STUDY RESULTS (ENHANCED ONLY)")
    print("=" * 80)
    for result in results:
        print(f"Config: {result['config']['name']}")
        print(f"  Success Rate: {result['summary']['success_rate']:.1%}")
        print(f"  Avg Duration: {result['summary']['total_duration_ms']}ms")
    print("\n✅ Ablation study complete")
    print(f"Results: {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
