"""Examples of migrating code to use resource managers.

This file shows before/after examples of common resource usage patterns.
"""

import asyncio
from pathlib import Path


# ==============================================================================
# Example 1: File Operations
# ==============================================================================


def example_1_before():
    """File operations WITHOUT resource management (UNSAFE)."""
    # This code has resource leaks if exceptions occur

    # Reading a file
    f = open("data.txt")
    data = f.read()
    f.close()  # Never called if exception above

    # Writing a file
    f = open("output.txt", "w")
    f.write(data)
    f.close()  # Never called if exception above


async def example_1_after():
    """File operations WITH resource management (SAFE)."""
    from kagami.core.resources import FileManager, FileMode
    from kagami.core.resources.file_manager import read_file, write_file

    # Method 1: Using FileManager
    async with FileManager("data.txt", FileMode.READ) as f:
        data = await f.read()
        # Automatic cleanup even on error

    async with FileManager("output.txt", FileMode.WRITE) as f:
        await f.write(data)
        # Automatic cleanup even on error

    # Method 2: Using convenience functions (recommended for simple operations)
    data = await read_file("data.txt")
    await write_file("output.txt", data)


# ==============================================================================
# Example 2: JSON File Operations
# ==============================================================================


def example_2_before():
    """JSON file operations WITHOUT resource management (UNSAFE)."""
    import json

    # Load JSON
    with open("config.json") as f:
        config = json.load(f)

    # Save JSON
    with open("output.json", "w") as f:
        json.dump(config, f)


async def example_2_after():
    """JSON file operations WITH resource management (SAFE)."""
    import json
    from kagami.core.resources import FileManager, FileMode

    # Load JSON
    async with FileManager("config.json", FileMode.READ) as f:
        content = await f.read()
        config = json.loads(content)

    # Save JSON
    async with FileManager("output.json", FileMode.WRITE) as f:
        await f.write(json.dumps(config, indent=2))


# ==============================================================================
# Example 3: Database Operations
# ==============================================================================


async def example_3_before():
    """Database operations WITHOUT resource management (UNSAFE)."""
    from kagami.core.database.async_connection import get_async_db_session
    from sqlalchemy import select

    # Query without proper cleanup
    async with get_async_db_session() as session:
        await session.execute(select("*"))
        await session.commit()
        # No automatic rollback on error


async def example_3_after():
    """Database operations WITH resource management (SAFE)."""
    from kagami.core.resources import DatabaseConnectionManager
    from sqlalchemy import select

    # Method 1: With auto-commit
    async with DatabaseConnectionManager.from_pool() as mgr:
        await mgr.execute(select("*"))
        # Auto-commit on success, auto-rollback on error

    # Method 2: Manual transaction control
    async with DatabaseConnectionManager.from_pool(auto_commit=False) as mgr:
        await mgr.execute(select("*"))
        await mgr.execute(select("*"))
        await mgr.commit()  # Manual commit


# ==============================================================================
# Example 4: Redis Operations
# ==============================================================================


async def example_4_before():
    """Redis operations WITHOUT resource management (UNSAFE)."""
    from kagami.core.caching.redis.factory import get_redis_client

    redis = await get_redis_client()
    await redis.set("key", "value")
    await redis.get("key")
    # Connection not properly returned to pool


async def example_4_after():
    """Redis operations WITH resource management (SAFE)."""
    from kagami.core.resources import RedisConnectionManager

    # Single operations
    async with RedisConnectionManager.from_pool() as redis:
        await redis.set("key", "value", ex=3600)
        await redis.get("key")
        # Connection automatically returned to pool

    # Batch operations with pipeline
    async with RedisConnectionManager.from_pool() as redis:
        async with redis.pipeline() as pipe:
            pipe.set("key1", "value1")
            pipe.set("key2", "value2")
            pipe.set("key3", "value3")
            await pipe.execute()


# ==============================================================================
# Example 5: GPU Memory Operations
# ==============================================================================


async def example_5_before():
    """GPU operations WITHOUT resource management (UNSAFE)."""
    import torch

    # Allocate tensors
    tensor1 = torch.randn(1000, 1000, device="cuda")
    tensor2 = torch.randn(1000, 1000, device="cuda")

    # Compute
    torch.matmul(tensor1, tensor2)

    # Memory never freed, accumulates over time
    # Can lead to CUDA out-of-memory errors


async def example_5_after():
    """GPU operations WITH resource management (SAFE)."""
    from kagami.core.resources import GPUMemoryManager
    import torch

    # Method 1: Use manager's allocation methods
    async with GPUMemoryManager(device="cuda:0") as gpu:
        tensor1 = gpu.randn((1000, 1000))
        tensor2 = gpu.randn((1000, 1000))
        torch.matmul(tensor1, tensor2)
        # All GPU memory automatically freed and cache cleared

    # Method 2: Track existing tensors
    async with GPUMemoryManager() as gpu:
        tensor1 = torch.randn(1000, 1000, device="cuda")
        gpu.track(tensor1, "tensor1")

        tensor2 = torch.randn(1000, 1000, device="cuda")
        gpu.track(tensor2, "tensor2")

        torch.matmul(tensor1, tensor2)
        # All tracked tensors cleaned up


# ==============================================================================
# Example 6: WebSocket Operations
# ==============================================================================


async def example_6_before(websocket):
    """WebSocket operations WITHOUT resource management (UNSAFE)."""
    # Send data
    await websocket.send({"type": "message", "data": "hello"})

    # Receive data
    await websocket.receive()

    # Connection never closed on error


async def example_6_after(websocket):
    """WebSocket operations WITH resource management (SAFE)."""
    from kagami.core.resources import WebSocketManager

    # Basic usage
    async with WebSocketManager(websocket) as ws:
        await ws.send({"type": "message", "data": "hello"})
        await ws.receive()
        # Automatic graceful close

    # With heartbeat
    async with WebSocketManager(websocket, heartbeat_interval=30) as ws:
        # Pings sent automatically every 30 seconds
        await ws.send({"type": "data", "value": 42})
        await ws.receive()


# ==============================================================================
# Example 7: Multiple Resources Together
# ==============================================================================


async def example_7_before():
    """Multiple resources WITHOUT resource management (UNSAFE)."""
    import torch

    # Multiple resources without coordination
    f1 = open("data.txt")
    f1.read()

    tensor = torch.randn(1000, 1000, device="cuda")
    result = process(tensor)

    f2 = open("output.txt", "w")
    f2.write(str(result))

    # If any step fails, resources leak


async def example_7_after():
    """Multiple resources WITH resource management (SAFE)."""
    from kagami.core.resources import AsyncResourceManager
    from kagami.core.resources import FileManager, GPUMemoryManager, FileMode

    # Method 1: Nested context managers
    async with FileManager("data.txt", FileMode.READ) as f:
        await f.read()

        async with GPUMemoryManager() as gpu:
            tensor = gpu.randn((1000, 1000))
            result = await process(tensor)

            async with FileManager("output.txt", FileMode.WRITE) as out:
                await out.write(str(result))
                # All resources cleaned up in reverse order

    # Method 2: Use ResourceManager for batch cleanup
    async with AsyncResourceManager() as mgr:
        # Add multiple resources
        await mgr.add(
            open("data.txt"),
            lambda f: f.close(),
            resource_type="file",
        )

        # All resources cleaned up together


# ==============================================================================
# Example 8: Adding Finally Blocks (When Context Managers Not Possible)
# ==============================================================================


async def example_8_before():
    """Operations WITHOUT proper cleanup (UNSAFE)."""

    async def process_batch(items):
        connection = await create_connection()
        for item in items:
            await connection.process(item)
        # Connection never closed on error


async def example_8_after():
    """Operations WITH proper cleanup using finally (SAFE)."""

    async def process_batch(items):
        connection = None
        try:
            connection = await create_connection()
            for item in items:
                await connection.process(item)
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise
        finally:
            if connection:
                try:
                    await connection.close()
                except Exception as e:
                    logger.error(f"Connection cleanup failed: {e}")


# ==============================================================================
# Example 9: Resource Leak Detection
# ==============================================================================


async def example_9_monitoring():
    """Monitor for resource leaks."""
    from kagami.core.resources.tracker import (
        get_resource_tracker,
        check_for_leaks,
        get_resource_stats,
    )

    # Get current statistics
    stats = get_resource_stats()
    print(f"Total tracked: {stats['total_tracked']}")
    print(f"By type: {stats['by_type']}")

    # Check for leaks (resources older than 5 minutes)
    leaks = await check_for_leaks(threshold=300)
    if leaks:
        print(f"WARNING: Found {len(leaks)} resource leaks")
        for leak in leaks:
            print(f"  {leak.resource_type}: {leak.resource_id}")

    # Get specific resource type
    tracker = get_resource_tracker()
    file_resources = tracker.get_resources("file")
    print(f"Open files: {len(file_resources)}")


# ==============================================================================
# Example 10: Real-World Migration (Forge Persistence)
# ==============================================================================


async def example_10_before_real():
    """Real example from kagami/forge/persistence_manager.py (BEFORE)."""
    import json

    path = Path("data.json")

    # Original code with potential leak
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        # If json.load fails, file still closed due to 'with'
        # But no resource tracking or metrics

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
        # Same issue - works but no tracking


async def example_10_after_real():
    """Real example from kagami/forge/persistence_manager.py (AFTER)."""
    import json
    from kagami.core.resources import FileManager, FileMode

    path = Path("data.json")

    # New code with tracking and metrics
    async with FileManager(path, FileMode.READ) as f:
        content = await f.read()
        data = json.loads(content)
        # Resource tracked, metrics collected

    async with FileManager(path, FileMode.WRITE) as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        # Resource tracked, metrics collected


# ==============================================================================
# Utility Functions
# ==============================================================================


async def process(tensor):
    """Dummy process function."""
    return tensor.sum()


async def create_connection():
    """Dummy connection creation."""

    class DummyConnection:
        async def process(self, item):
            pass

        async def close(self):
            pass

    return DummyConnection()


# ==============================================================================
# Main
# ==============================================================================


async def main():
    """Run all examples."""
    print("=" * 80)
    print("Resource Management Migration Examples")
    print("=" * 80)

    # File operations
    print("\nExample 1: File Operations")
    await example_1_after()

    # JSON operations
    print("\nExample 2: JSON Operations")
    await example_2_after()

    # Database operations
    print("\nExample 3: Database Operations")
    # await example_3_after()  # Requires database

    # Redis operations
    print("\nExample 4: Redis Operations")
    # await example_4_after()  # Requires Redis

    # GPU operations
    print("\nExample 5: GPU Operations")
    # await example_5_after()  # Requires CUDA

    # Monitoring
    print("\nExample 9: Resource Monitoring")
    await example_9_monitoring()

    print("\nAll examples completed!")


if __name__ == "__main__":
    asyncio.run(main())
