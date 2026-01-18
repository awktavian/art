"""Example usage of Kagami state persistence layer.

CREATED: December 28, 2025
PURPOSE: Demonstrate how to use the persistence API.

This example shows:
1. Configuring persistence with different backends
2. Saving colony states
3. Saving world model checkpoints
4. Loading state for crash recovery
5. Auto-save configuration
"""

import asyncio

import torch

from kagami.core.persistence import (
    BackendType,
    ColonyStateSnapshot,
    WorldModelCheckpoint,
    configure_persistence,
)


async def example_basic_usage():
    """Example: Basic checkpoint save and load."""
    print("\n=== Basic Usage ===\n")

    # 1. Configure persistence (filesystem backend)
    manager = configure_persistence(
        backend_type=BackendType.FILESYSTEM, data_dir="/tmp/kagami_state_example"
    )
    print("Configured persistence with filesystem backend")

    # 2. Create sample colony state
    colony_state = ColonyStateSnapshot(
        hidden_states={
            0: torch.randn(4, 128),  # Spark
            1: torch.randn(4, 128),  # Forge
            2: torch.randn(4, 128),  # Flow
            3: torch.randn(4, 128),  # Nexus
            4: torch.randn(4, 128),  # Beacon
            5: torch.randn(4, 128),  # Grove
            6: torch.randn(4, 128),  # Crystal
        },
        stochastic_states={i: torch.randn(4, 64) for i in range(7)},
        e8_embeddings={i: torch.randn(8) for i in range(7)},
        timestep=100,
        active_colonies=[0, 1, 2, 3, 4, 5, 6],
        metadata={"phase": "training", "epoch": 5},
    )
    print("Created colony state snapshot (7 colonies, timestep 100)")

    # 3. Save checkpoint
    checkpoint_id = await manager.save_state(
        name="example_checkpoint",
        colony_state=colony_state,
        metadata={"author": "example_script", "version": "1.0"},
    )
    print(f"Saved checkpoint: {checkpoint_id}")

    # 4. Load checkpoint
    loaded = await manager.load_state(checkpoint_id)
    print(f"Loaded checkpoint: {loaded.checkpoint_id}")
    print(f"  Timestep: {loaded.colony_state.timestep}")
    print(f"  Active colonies: {loaded.colony_state.active_colonies}")

    # 5. List all checkpoints
    checkpoints = await manager.list_checkpoints(limit=5)
    print("\nAvailable checkpoints:")
    for cp in checkpoints:
        print(f"  - {cp.name} (ID: {cp.checkpoint_id})")
        print(f"    Components: {cp.components}")
        print(f"    Size: {cp.size_bytes} bytes")

    await manager.close()


async def example_world_model():
    """Example: Saving world model checkpoint."""
    print("\n=== World Model Checkpoint ===\n")

    manager = configure_persistence(
        backend_type=BackendType.FILESYSTEM, data_dir="/tmp/kagami_state_example"
    )

    # Create dummy world model
    model_checkpoint = WorldModelCheckpoint(
        model_state_dict={
            "encoder.weight": torch.randn(256, 128),
            "encoder.bias": torch.randn(256),
            "decoder.weight": torch.randn(128, 256),
            "decoder.bias": torch.randn(128),
            "rssm.hidden": torch.randn(512, 256),
        },
        trajectory_cache={
            "trajectory_0": torch.randn(100, 8),  # E8 quantized
            "trajectory_1": torch.randn(100, 8),
        },
        epoch=10,
        step=5000,
        loss=0.0823,
        metrics={
            "accuracy": 0.95,
            "reconstruction_error": 0.12,
            "kl_divergence": 0.05,
        },
        model_version="2.0.0",
        config={
            "hidden_dim": 256,
            "stochastic_dim": 64,
            "num_colonies": 7,
        },
        metadata={
            "training_time": "2.5 hours",
            "device": "cuda",
        },
    )
    print("Created world model checkpoint (epoch 10, loss 0.0823)")

    # Save
    checkpoint_id = await manager.save_state(
        name="world_model_epoch_10",
        world_model=model_checkpoint,
        metadata={"training_complete": True},
    )
    print(f"Saved world model: {checkpoint_id}")

    # Load
    loaded = await manager.load_state(checkpoint_id)
    print("Loaded world model:")
    print(f"  Epoch: {loaded.world_model.epoch}")
    print(f"  Step: {loaded.world_model.step}")
    print(f"  Loss: {loaded.world_model.loss:.4f}")
    print(f"  Metrics: {loaded.world_model.metrics}")

    await manager.close()


async def example_partial_save():
    """Example: Partial state save (only specific components)."""
    print("\n=== Partial State Save ===\n")

    manager = configure_persistence(
        backend_type=BackendType.FILESYSTEM, data_dir="/tmp/kagami_state_example"
    )

    # Create states
    colony_state = ColonyStateSnapshot(
        hidden_states={i: torch.randn(4, 128) for i in range(7)},
        stochastic_states={i: torch.randn(4, 64) for i in range(7)},
        e8_embeddings={i: torch.randn(8) for i in range(7)},
        timestep=200,
    )

    # Save only colonies (not world model, receipts, memory)
    checkpoint_id = await manager.save_state(
        name="colonies_only",
        include=["colonies"],  # Only save colonies
        colony_state=colony_state,
    )
    print(f"Saved partial checkpoint (colonies only): {checkpoint_id}")

    # Load
    loaded = await manager.load_state(checkpoint_id)
    print(f"Loaded checkpoint components: {loaded.metadata.components}")
    print(f"  Colony state: {'✓' if loaded.colony_state else '✗'}")
    print(f"  World model: {'✓' if loaded.world_model else '✗'}")
    print(f"  Receipts: {'✓' if loaded.receipts else '✗'}")
    print(f"  Stigmergy: {'✓' if loaded.stigmergy else '✗'}")

    await manager.close()


async def example_crash_recovery():
    """Example: Crash recovery from most recent checkpoint."""
    print("\n=== Crash Recovery ===\n")

    manager = configure_persistence(
        backend_type=BackendType.FILESYSTEM, data_dir="/tmp/kagami_state_example"
    )

    # Simulate saving multiple checkpoints over time
    for i in range(3):
        colony_state = ColonyStateSnapshot(
            hidden_states={j: torch.randn(4, 128) for j in range(7)},
            stochastic_states={j: torch.randn(4, 64) for j in range(7)},
            e8_embeddings={j: torch.randn(8) for j in range(7)},
            timestep=i * 100,
        )
        await manager.save_state(f"checkpoint_{i}", colony_state=colony_state)
        print(f"Saved checkpoint_{i} (timestep {i * 100})")

    print("\n--- Simulating crash and recovery ---\n")

    # Crash recovery: Load most recent checkpoint
    checkpoints = await manager.list_checkpoints()
    if checkpoints:
        most_recent = checkpoints[0]
        print(f"Most recent checkpoint: {most_recent.name}")
        print(f"  Timestamp: {most_recent.timestamp}")
        print(f"  Components: {most_recent.components}")

        # Load it
        recovered = await manager.load_state(most_recent.checkpoint_id)
        print("\nRecovered state:")
        print(f"  Timestep: {recovered.colony_state.timestep}")
        print(f"  Active colonies: {len(recovered.colony_state.active_colonies)}")
        print("\n✓ Recovery successful!")
    else:
        print("✗ No checkpoints found")

    await manager.close()


async def example_autosave():
    """Example: Auto-save configuration."""
    print("\n=== Auto-Save Configuration ===\n")

    manager = configure_persistence(
        backend_type=BackendType.FILESYSTEM, data_dir="/tmp/kagami_state_example"
    )

    # Configure auto-save
    await manager.configure_autosave(
        enabled=True,
        interval_seconds=300,  # Every 5 minutes
        keep_last_n=5,  # Keep 5 most recent
        components=["colonies", "world_model"],
    )
    print("Auto-save configured:")
    print("  Enabled: True")
    print("  Interval: 300 seconds (5 minutes)")
    print("  Keep last: 5 checkpoints")
    print("  Components: colonies, world_model")

    # Auto-save will run in background
    # (In real usage, state would be captured automatically)

    # Disable auto-save
    await manager.configure_autosave(enabled=False)
    print("\nAuto-save disabled")

    await manager.close()


async def example_multiple_backends():
    """Example: Using multiple backends."""
    print("\n=== Multiple Backends ===\n")

    # Hot storage: Redis (fast, temporary)
    try:
        redis_manager = configure_persistence(
            backend_type=BackendType.REDIS, host="localhost", port=6379, ttl_seconds=3600
        )
        print("✓ Configured Redis backend (hot storage)")
    except Exception as e:
        print(f"✗ Redis not available: {e}")
        redis_manager = None

    # Cold storage: Filesystem (persistent)
    fs_manager = configure_persistence(
        backend_type=BackendType.FILESYSTEM, data_dir="/tmp/kagami_state_example"
    )
    print("✓ Configured Filesystem backend (cold storage)")

    # Usage pattern: Save to Redis for quick access, archive to filesystem
    colony_state = ColonyStateSnapshot(
        hidden_states={i: torch.randn(4, 128) for i in range(7)},
        stochastic_states={i: torch.randn(4, 64) for i in range(7)},
        e8_embeddings={i: torch.randn(8) for i in range(7)},
    )

    if redis_manager:
        await redis_manager.save_state("hot_checkpoint", colony_state=colony_state)
        print("Saved to Redis (hot)")

    await fs_manager.save_state("cold_checkpoint", colony_state=colony_state)
    print("Saved to Filesystem (cold)")

    if redis_manager:
        await redis_manager.close()
    await fs_manager.close()


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Kagami State Persistence - Example Usage")
    print("=" * 60)

    try:
        await example_basic_usage()
        await example_world_model()
        await example_partial_save()
        await example_crash_recovery()
        await example_autosave()
        await example_multiple_backends()

        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
