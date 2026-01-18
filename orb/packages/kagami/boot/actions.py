"""Boot actions compatibility shim.

This module maintains backwards compatibility by re-exporting all actions
from the new categorized modules.

New code should import directly from:
  - kagami.boot.actions.init
  - kagami.boot.actions.registration
  - kagami.boot.actions.wiring
  - kagami.boot.actions.shutdown
"""

from __future__ import annotations

# Re-export initialization actions
# Re-export helper functions (needed by some actions)
from kagami.boot.actions.init import (
    _env_int,
    _should_enable_loader,
    enforce_full_operation_check,
    shutdown_e8_bus,
    shutdown_etcd,
    startup_cbf_system,
    startup_database,
    startup_e8_bus,
    startup_etcd,
    startup_feature_flags,
    startup_redis,
)

# Re-export registration actions
from kagami.boot.actions.registration import (
    startup_ambient_os,
    startup_hal,
    startup_socketio,
)

# Re-export shutdown actions
from kagami.boot.actions.shutdown import shutdown_all

# Re-export wiring actions
from kagami.boot.actions.wiring import (
    coordinate_background_tasks,
    startup_background_tasks,
    startup_brain,
    startup_learning_systems,
    startup_orchestrator,
)

__all__ = [
    # Helpers
    "_env_int",
    "_should_enable_loader",
    "coordinate_background_tasks",
    # Initialization
    "enforce_full_operation_check",
    # Shutdown
    "shutdown_all",
    "shutdown_e8_bus",
    "shutdown_etcd",
    "startup_ambient_os",
    "startup_background_tasks",
    "startup_brain",
    "startup_cbf_system",
    "startup_database",
    "startup_e8_bus",
    "startup_etcd",
    "startup_feature_flags",
    # Registration
    "startup_hal",
    "startup_learning_systems",
    # Wiring
    "startup_orchestrator",
    "startup_redis",
    "startup_socketio",
]
