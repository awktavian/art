#!/usr/bin/env python3
"""Hello Kagami — First Contact with the 7-Colony Organism.

This example demonstrates:
1. Initializing the unified organism (7 colonies + Kagami coordinator)
2. Fano routing (intent → colony selection)
3. Safety monitoring (h(x) ≥ 0)
4. Simple task execution

Run: python examples/hello_kagami.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from kagami.core.unified_agents.unified_organism import UnifiedOrganism


async def main() -> None:
    """Execute a simple creative task via Kagami routing."""
    print("🌀 Initializing Kagami organism...")
    print("   (7 colonies + coordinator)\n")

    # Initialize the full organism
    organism = UnifiedOrganism()

    # Optional: Initialize async components if needed
    # await organism.initialize()

    print("✓ Organism initialized\n")
    print("=" * 60)

    # Example 1: Creative task (routes to Spark)
    creative_intent = "Generate a creative story idea about a mirror that reflects the future"

    print(f"\n📝 Intent: {creative_intent}")
    print("🎯 Expected routing: Spark (e₁) — creative ideation\n")

    try:
        # Execute via Fano routing
        result = await organism.execute_intent(creative_intent)

        print("✓ Execution complete")
        print("\n📤 Output:")
        print(f"   {result.get('output', 'No output')}\n")

        # Check safety
        safety = organism.safety if hasattr(organism, "safety") else None
        if safety:
            h_x = getattr(safety, "h_x", 0.5)
            print(f"🛡️  Safety: h(x) = {h_x:.3f}")
            if h_x >= 0.5:
                print("   🟢 Safe zone")
            elif h_x >= 0:
                print("   🟡 Caution zone")
            else:
                print("   🔴 VIOLATION (should not happen)")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)
    print("\n🌿 More examples:")
    print("   - Research: 'Research the latest papers on E8 lattices'")
    print("   - Plan: 'Design an architecture for multi-agent coordination'")
    print("   - Debug: 'Fix the type error in validation.py'")
    print("   - Test: 'Verify safety constraints hold for all inputs'\n")

    print("📚 Next steps:")
    print("   - Read QUICKSTART.md for 15-minute tutorial")
    print("   - Read docs/architecture.md for system overview")
    print("   - Try modifying this script with different intents\n")

    print("鏡 The mirror reflects.")


if __name__ == "__main__":
    asyncio.run(main())
