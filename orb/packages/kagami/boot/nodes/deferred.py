"""Deferred Boot Nodes — Non-Blocking Startup.

CREATED: December 30, 2025

Enable with KAGAMI_DEFERRED_BOOT=1
"""

from __future__ import annotations

import os

from kagami.boot import BootNode
from kagami.boot.actions import (
    enforce_full_operation_check,
    shutdown_e8_bus,
    shutdown_etcd,
    startup_ambient_os,
    startup_cbf_system,
    startup_database,
    startup_e8_bus,
    startup_etcd,
    startup_hal,
    startup_redis,
)
from kagami.boot.actions.wiring import startup_safety
from kagami.boot.infrastructure import shutdown_provenance, startup_provenance
from kagami.boot.nodes import health_flag


def get_deferred_nodes() -> list[BootNode]:
    """Return deferred boot nodes — instant API start."""
    from kagami.boot.actions.deferred_boot import startup_orchestrator_deferred

    return [
        BootNode(
            name="enforce_full_operation",
            start=enforce_full_operation_check,
            timeout_s=2.0,
        ),
        BootNode(
            name="database",
            start=startup_database,
            dependencies=("enforce_full_operation",),
            health_check=health_flag("db_ready", "db_ready"),
            timeout_s=15.0,
        ),
        BootNode(
            name="redis",
            start=startup_redis,
            dependencies=("enforce_full_operation",),
            health_check=health_flag("redis_ready", "redis_ready"),
            timeout_s=3.0,
        ),
        BootNode(
            name="etcd",
            start=startup_etcd,
            stop=shutdown_etcd,
            dependencies=("enforce_full_operation",),
            health_check=health_flag("etcd_ready", "etcd_ready"),
            timeout_s=5.0,
        ),
        BootNode(
            name="hal",
            start=startup_hal,
            dependencies=("enforce_full_operation",),
            health_check=health_flag("hal_manager", "hal_ready"),
        ),
        BootNode(
            name="e8_bus",
            start=startup_e8_bus,
            stop=shutdown_e8_bus,
            dependencies=("redis",),
            health_check=health_flag("e8_bus_ready", "e8_bus_ready"),
            timeout_s=3.0,
        ),
        BootNode(
            name="cbf_system",
            start=startup_cbf_system,
            dependencies=("redis",),
            health_check=health_flag("cbf_ready", "cbf_ready"),
            timeout_s=5.0,
        ),
        BootNode(
            name="ambient_os",
            start=startup_ambient_os,
            dependencies=("redis",),
            health_check=health_flag("device_coordinator", "ambient_os_ready"),
            timeout_s=3.0,
        ),
        BootNode(
            name="safety_monitor",
            start=startup_safety,
            dependencies=("cbf_system",),
            health_check=health_flag("cbf_monitor", "cbf_monitor_ready"),
            timeout_s=3.0,
        ),
        BootNode(
            name="provenance",
            start=startup_provenance,
            stop=shutdown_provenance,
            dependencies=("etcd",),
            health_check=health_flag("provenance_ready", "provenance_ready"),
            timeout_s=3.0,
        ),
        # DEFERRED: Instant start, models load in background
        BootNode(
            name="orchestrator",
            start=startup_orchestrator_deferred,
            dependencies=("database", "redis", "etcd", "cbf_system", "provenance"),
            health_check=health_flag("orchestrator_ready", "orchestrator_ready"),
            timeout_s=5.0,  # Fast - models load async
        ),
    ]


def should_use_deferred_boot() -> bool:
    """Check if deferred boot is enabled."""
    for var in ["KAGAMI_DEFERRED_BOOT", "KAGAMI_FAST_BOOT"]:
        if os.getenv(var, "").lower() in ("1", "true", "yes"):
            return True
    return False


def get_boot_nodes() -> list[BootNode]:
    """Get appropriate boot nodes."""
    if should_use_deferred_boot():
        return get_deferred_nodes()
    from kagami.boot.nodes.core import get_core_nodes

    return get_core_nodes()


__all__ = ["get_boot_nodes", "get_deferred_nodes", "should_use_deferred_boot"]
