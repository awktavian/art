"""VM Adapters for Computer Control.

Three-tier architecture for full computer control:

Tier 1 (Host): Peekaboo for direct macOS control
Tier 2 (Sandboxed): CUA/Lume for isolated macOS VMs (97% native perf)
Tier 3 (Multi-OS): Parallels for Windows/Linux VMs

All adapters implement VMAdapterProtocol for unified control.

Usage:
    # Tier 1: Direct host control
    from kagami_hal.adapters.vm import PeekabooAdapter
    adapter = PeekabooAdapter()
    await adapter.initialize()
    await adapter.screenshot()
    await adapter.click(100, 200)

    # Tier 2: Sandboxed macOS VM
    from kagami_hal.adapters.vm import CUALumeAdapter
    adapter = CUALumeAdapter()
    await adapter.initialize()
    await adapter.start()
    await adapter.screenshot()

    # Tier 3: Multi-OS VM
    from kagami_hal.adapters.vm import ParallelsAdapter
    adapter = ParallelsAdapter("Windows-11")
    await adapter.initialize()
    await adapter.start()
    result = await adapter.execute("dir C:\\")

    # VM Pool for concurrent automation
    from kagami_hal.adapters.vm import get_vm_pool
    pool = await get_vm_pool()
    async with pool.acquire() as vm:
        await vm.screenshot()
        await vm.click(100, 200)

Created: December 30, 2025
"""

# Types
# Base class
from .base import BaseVMAdapter
from .cua_lume import CUALumeAdapter
from .parallels import ParallelsAdapter

# Adapters
from .peekaboo import PeekabooAdapter

# Pool
from .pool import (
    PoolConfig,
    PooledVM,
    PoolStats,
    VMPool,
    get_vm_pool,
    shutdown_vm_pool,
)

# Protocol
from .protocol import VMAdapterProtocol
from .types import (
    AccessibilityElement,
    ClickOptions,
    CommandResult,
    OSType,
    TypeOptions,
    VMConfig,
    VMDisplayInfo,
    VMState,
    VMStatus,
    VMTier,
)

__all__ = [
    # Types
    "AccessibilityElement",
    # Base
    "BaseVMAdapter",
    "CUALumeAdapter",
    "ClickOptions",
    "CommandResult",
    "OSType",
    "ParallelsAdapter",
    # Adapters
    "PeekabooAdapter",
    # Pool
    "PoolConfig",
    "PoolStats",
    "PooledVM",
    "TypeOptions",
    # Protocol
    "VMAdapterProtocol",
    "VMConfig",
    "VMDisplayInfo",
    "VMPool",
    "VMState",
    "VMStatus",
    "VMTier",
    "get_vm_pool",
    "shutdown_vm_pool",
]
