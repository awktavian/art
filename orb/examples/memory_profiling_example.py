"""Example demonstrating memory profiling in realtime_renderer.

To enable memory profiling, set the ENABLE_MEMORY_PROFILING environment variable:

    ENABLE_MEMORY_PROFILING=1 python examples/memory_profiling_example.py

The profiler will:
- Log memory usage before/after each profiled function
- Track peak memory usage
- Detect memory leaks by comparing snapshots
- Log top memory allocations
"""

import asyncio
import os

# Enable memory profiling
os.environ["ENABLE_MEMORY_PROFILING"] = "1"

from kagami.forge.modules.genesis.realtime_renderer import (
    RealtimeConfig,
    RealtimeGenesisRenderer,
)


async def main() -> None:
    """Demo memory profiling during rendering."""
    # Create renderer with low resolution for faster testing
    config = RealtimeConfig(
        width=640,
        height=480,
        render_fps=15,
        display_fps=60,
        base_spp=32,
        enable_foveation=False,
        enable_motion_reprojection=True,
        show_viewer=True,
    )

    renderer = RealtimeGenesisRenderer(config)

    # Initialize (memory profiled)
    print("Initializing renderer...")
    await renderer.initialize()

    # Check initial memory stats
    stats = renderer.get_memory_stats()
    print(f"\nInitial memory stats: {stats}")

    # Add some objects
    renderer.add_floor()
    renderer.add_rigid_body(
        "sphere1",
        "sphere",
        position=(0.0, 0.0, 2.0),
        size=0.15,
        material="glass",
        velocity=(0.1, 0.05, 0.0, 0.0, 0.0, 0.0),
    )
    renderer.add_rigid_body(
        "sphere2",
        "sphere",
        position=(0.3, 0.0, 3.0),
        size=0.12,
        material="chrome",
        velocity=(-0.05, 0.1, 0.0, 0.0, 0.0, 0.0),
    )

    # Build the scene
    renderer.build()

    # Check memory after scene setup
    stats = renderer.get_memory_stats()
    print(f"\nMemory after scene setup: {stats}")

    # Log top allocations
    print("\nTop memory allocations:")
    renderer.log_memory_snapshot(top_n=5)

    # Run real-time rendering (memory profiled)
    print("\nStarting real-time rendering for 5 seconds...")
    await renderer.run_realtime(duration=5.0)

    # Final memory stats
    stats = renderer.get_memory_stats()
    print(f"\nFinal memory stats: {stats}")

    # Check for memory leaks
    print("\nTop allocations after rendering:")
    renderer.log_memory_snapshot(top_n=5)

    # Shutdown (will log final stats)
    await renderer.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
