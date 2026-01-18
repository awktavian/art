//! Virtual Machine Control Module
//!
//! Unified API for managing virtual machines across different hypervisors:
//! - **Parallels** (macOS) - via prlctl CLI
//! - **UTM/QEMU** (macOS) - via qemu commands and utmctl
//! - **libvirt/KVM** (Linux) - via virsh CLI
//! - **Hyper-V** (Windows) - via PowerShell/WMI
//! - **Lume** (macOS) - for CUA sandboxed VMs
//!
//! # Architecture
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────────┐
//! │                    VM Controller (Unified API)                   │
//! ├─────────────────────────────────────────────────────────────────┤
//! │  list_vms() │ start() │ stop() │ snapshot() │ execute() │ ...  │
//! └─────────────────────────────────────────────────────────────────┘
//!                                  │
//!         ┌────────────────────────┼────────────────────────┐
//!         ▼                        ▼                        ▼
//! ┌───────────────┐      ┌───────────────┐      ┌───────────────┐
//! │   Parallels   │      │   UTM/QEMU    │      │   libvirt     │
//! │    Backend    │      │    Backend    │      │    Backend    │
//! └───────────────┘      └───────────────┘      └───────────────┘
//! ```
//!
//! # HTTP API
//!
//! The VM module exposes a REST API at `/vm`:
//!
//! ```text
//! GET  /vm/hypervisors         - List available hypervisors
//! GET  /vm                     - List all VMs
//! GET  /vm/:name               - Get VM details
//! POST /vm/:name/start         - Start VM
//! POST /vm/:name/stop          - Stop VM
//! POST /vm/:name/execute       - Execute command in VM
//! GET  /vm/:name/screenshot    - Capture screenshot
//! ```
//!
//! See [`routes`] for full endpoint documentation.
//!
//! # Safety
//!
//! ```text
//! h(x) >= 0 always
//! ```
//!
//! VM operations maintain the safety invariant - destructive operations
//! require explicit confirmation.
//!
//! Colony: Nexus (e4) — Orchestration and compute

pub mod controller;
pub mod error;
pub mod hypervisor;
pub mod routes;
pub mod types;

// Re-export main types at module level
pub use controller::VMController;
pub use error::{VMError, VMResult};
pub use hypervisor::{
    HyperVBackend, HypervisorBackend, LibvirtBackend, LumeBackend, ParallelsBackend, UTMBackend,
};
pub use routes::vm_router;
pub use types::{
    CommandResult, NetworkConfig, OSType, PortForward, ResourceConfig, SnapshotInfo, VMConfig,
    VMInfo, VMState,
};

/*
 * Nexus orchestrates compute.
 * VMs provide isolation.
 * h(x) >= 0 always
 */
