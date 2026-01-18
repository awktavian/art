//! Hypervisor Backends
//!
//! Implementations for different hypervisor platforms.

mod hyper_v;
mod libvirt;
mod lume;
mod parallels;
mod utm;

use async_trait::async_trait;

pub use hyper_v::HyperVBackend;
pub use libvirt::LibvirtBackend;
pub use lume::LumeBackend;
pub use parallels::ParallelsBackend;
pub use utm::UTMBackend;

use crate::vm::error::VMResult;
use crate::vm::types::{CommandResult, SnapshotInfo, VMConfig, VMInfo};

// ============================================================================
// Hypervisor Trait
// ============================================================================

/// Trait defining the interface for hypervisor backends
#[async_trait]
pub trait HypervisorBackend: Send + Sync {
    /// Get the hypervisor name
    fn name(&self) -> &'static str;

    /// Check if this hypervisor is available on the system
    async fn is_available(&self) -> bool;

    // ========================================================================
    // VM Discovery
    // ========================================================================

    /// List all VMs managed by this hypervisor
    async fn list_vms(&self) -> VMResult<Vec<VMInfo>>;

    /// Get information about a specific VM
    async fn get_vm(&self, vm_name: &str) -> VMResult<VMInfo>;

    // ========================================================================
    // VM Lifecycle
    // ========================================================================

    /// Start a VM
    async fn start_vm(&self, vm_name: &str, headless: bool) -> VMResult<()>;

    /// Stop a VM (graceful shutdown)
    async fn stop_vm(&self, vm_name: &str) -> VMResult<()>;

    /// Force stop a VM (power off)
    async fn force_stop_vm(&self, vm_name: &str) -> VMResult<()>;

    /// Pause a VM
    async fn pause_vm(&self, vm_name: &str) -> VMResult<()>;

    /// Resume a paused VM
    async fn resume_vm(&self, vm_name: &str) -> VMResult<()>;

    /// Restart a VM
    async fn restart_vm(&self, vm_name: &str) -> VMResult<()>;

    // ========================================================================
    // VM Provisioning
    // ========================================================================

    /// Create a new VM
    async fn create_vm(&self, config: &VMConfig) -> VMResult<VMInfo>;

    /// Clone an existing VM
    async fn clone_vm(&self, source_vm: &str, new_name: &str) -> VMResult<VMInfo>;

    /// Delete a VM
    async fn delete_vm(&self, vm_name: &str, delete_files: bool) -> VMResult<()>;

    // ========================================================================
    // Snapshots
    // ========================================================================

    /// List snapshots for a VM
    async fn list_snapshots(&self, vm_name: &str) -> VMResult<Vec<SnapshotInfo>>;

    /// Create a snapshot
    async fn create_snapshot(
        &self,
        vm_name: &str,
        snapshot_name: &str,
        description: Option<&str>,
    ) -> VMResult<SnapshotInfo>;

    /// Restore a snapshot
    async fn restore_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()>;

    /// Delete a snapshot
    async fn delete_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()>;

    // ========================================================================
    // Resource Management
    // ========================================================================

    /// Update VM resources (CPU, memory)
    async fn update_resources(
        &self,
        vm_name: &str,
        cpu_count: Option<u32>,
        memory_mb: Option<u64>,
    ) -> VMResult<()>;

    // ========================================================================
    // Guest Agent Communication
    // ========================================================================

    /// Execute a command inside the VM
    async fn execute_command(
        &self,
        vm_name: &str,
        command: &str,
        timeout_ms: u64,
    ) -> VMResult<CommandResult>;

    /// Copy a file to the VM
    async fn copy_to_vm(
        &self,
        vm_name: &str,
        local_path: &str,
        remote_path: &str,
    ) -> VMResult<()>;

    /// Copy a file from the VM
    async fn copy_from_vm(
        &self,
        vm_name: &str,
        remote_path: &str,
        local_path: &str,
    ) -> VMResult<()>;

    // ========================================================================
    // Screenshots
    // ========================================================================

    /// Capture a screenshot of the VM display
    async fn screenshot(&self, vm_name: &str) -> VMResult<Vec<u8>>;
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Detect available hypervisors on the current system
pub async fn detect_hypervisors() -> Vec<Box<dyn HypervisorBackend>> {
    let mut available: Vec<Box<dyn HypervisorBackend>> = Vec::new();

    // Check each hypervisor
    let parallels = ParallelsBackend::new();
    if parallels.is_available().await {
        available.push(Box::new(parallels));
    }

    let utm = UTMBackend::new();
    if utm.is_available().await {
        available.push(Box::new(utm));
    }

    let lume = LumeBackend::new();
    if lume.is_available().await {
        available.push(Box::new(lume));
    }

    let libvirt = LibvirtBackend::new();
    if libvirt.is_available().await {
        available.push(Box::new(libvirt));
    }

    let hyperv = HyperVBackend::new();
    if hyperv.is_available().await {
        available.push(Box::new(hyperv));
    }

    available
}

/// Get hypervisor by name
pub fn get_hypervisor(name: &str) -> Option<Box<dyn HypervisorBackend>> {
    match name.to_lowercase().as_str() {
        "parallels" => Some(Box::new(ParallelsBackend::new())),
        "utm" | "qemu" => Some(Box::new(UTMBackend::new())),
        "lume" | "cua" => Some(Box::new(LumeBackend::new())),
        "libvirt" | "kvm" => Some(Box::new(LibvirtBackend::new())),
        "hyperv" | "hyper-v" => Some(Box::new(HyperVBackend::new())),
        _ => None,
    }
}
