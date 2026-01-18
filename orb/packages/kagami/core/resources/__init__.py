"""Resource management and cleanup for Kagami.

This module provides comprehensive resource lifecycle management including:
- File handle management
- Database connection pooling
- GPU memory management
- WebSocket lifecycle
- Generic async resource patterns
- Resource leak detection and tracking

The resource management system ensures proper cleanup of resources
even in error conditions, preventing resource leaks and memory bloat.

Usage:
    # File management
    async with FileManager(path) as f:
        data = await f.read()

    # Database connections
    async with DatabaseConnectionManager() as conn:
        result = await conn.execute(query)

    # GPU memory
    async with GPUMemoryManager() as gpu:
        tensor = gpu.allocate((1000, 1000))
        result = await model(tensor)

    # WebSocket
    async with WebSocketManager(ws) as manager:
        await manager.send(data)

    # Generic resources
    async with AsyncResourceManager(resource, cleanup_fn) as r:
        await r.use()

Resource tracking:
    from kagami.core.resources import get_resource_tracker

    tracker = get_resource_tracker()
    stats = tracker.get_stats()
    leaks = tracker.detect_leaks()
"""

from kagami.core.resources.async_resource import (
    AsyncResource,
    AsyncResourceManager,
    ResourceCleanupError,
)
from kagami.core.resources.connection_manager import (
    ConnectionManager,
    DatabaseConnectionManager,
    RedisConnectionManager,
)
from kagami.core.resources.file_manager import FileManager, FileMode
from kagami.core.resources.gpu_manager import GPUMemoryManager, GPUResource
from kagami.core.resources.tracker import (
    ResourceTracker,
    get_resource_tracker,
    track_resource,
)
from kagami.core.resources.websocket_manager import (
    WebSocketConnectionError,
    WebSocketManager,
)

__all__ = [
    # Generic async resources
    "AsyncResource",
    "AsyncResourceManager",
    # Connection management
    "ConnectionManager",
    "DatabaseConnectionManager",
    # File management
    "FileManager",
    "FileMode",
    # GPU management
    "GPUMemoryManager",
    "GPUResource",
    "RedisConnectionManager",
    "ResourceCleanupError",
    # Resource tracking
    "ResourceTracker",
    "WebSocketConnectionError",
    # WebSocket management
    "WebSocketManager",
    "get_resource_tracker",
    "track_resource",
]
