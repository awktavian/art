"""K os Boot System.

DEFERRED BOOT (December 30, 2025):
==================================
Enable with KAGAMI_DEFERRED_BOOT=1 for:
- Instant API start (~500ms vs ~17s)
- Request queueing while models load
- Hot-swap model upgrades at runtime
"""

from .deferred_loader import (
    DeferredModelLoader,
    get_deferred_loader,
)
from .graph import (
    BootGraph,
    BootGraphExecutionError,
    BootGraphReport,
    BootNode,
    BootNodeStatus,
)

__all__ = [
    "BootGraph",
    "BootGraphExecutionError",
    "BootGraphReport",
    "BootNode",
    "BootNodeStatus",
    "DeferredModelLoader",
    "get_deferred_loader",
]
