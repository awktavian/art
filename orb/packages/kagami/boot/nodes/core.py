from __future__ import annotations

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
    startup_orchestrator,
    startup_redis,
)
from kagami.boot.actions.wiring import startup_safety
from kagami.boot.infrastructure import shutdown_provenance, startup_provenance
from kagami.boot.nodes import health_flag


def get_core_nodes() -> list[BootNode]:
    """Return core boot nodes for K os startup.

    Boot order (dependencies respected):
    1. enforce_full_operation (gate)
    2. database, redis, etcd (parallel - infrastructure)
    3. hal (parallel - depends on enforce_full_operation)
    4. e8_bus, cbf_system, ambient_os (parallel - depends on redis)
    4. safety_monitor (depends on cbf_system)
    5. provenance (depends on etcd)
    6. orchestrator (depends on database, redis, etcd, cbf_system, provenance)
    """
    return [
        BootNode(
            name="enforce_full_operation",
            start=enforce_full_operation_check,
            timeout_s=2.0,
        ),
        # TIER 1: Infrastructure (parallel)
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
        # HAL is optional but should be wired into app.state for vitals endpoints
        BootNode(
            name="hal",
            start=startup_hal,
            dependencies=("enforce_full_operation",),
            health_check=health_flag("hal_manager", "hal_ready"),
        ),
        # TIER 2: Core systems (parallel, depends on redis)
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
        # TIER 3: Safety and provenance
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
            dependencies=("redis",),  # Changed from etcd - provenance can work without etcd
            health_check=health_flag("provenance_ready", "provenance_ready"),
            timeout_s=3.0,
        ),
        # TIER 4: Orchestrator (required for background nodes)
        BootNode(
            name="orchestrator",
            start=startup_orchestrator,
            dependencies=("database", "redis", "cbf_system"),  # Removed etcd, provenance
            health_check=health_flag("fractal_organism", "organism_ready"),
            timeout_s=60.0,
        ),
    ]
