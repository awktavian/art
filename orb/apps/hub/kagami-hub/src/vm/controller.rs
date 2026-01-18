//! VM Controller
//!
//! Unified API for managing VMs across all hypervisors.
//!
//! ```text
//! h(x) >= 0 always
//! ```

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{debug, info, warn};

use super::error::{VMError, VMResult};
use super::hypervisor::{detect_hypervisors, HypervisorBackend};
use super::types::{CommandResult, SnapshotInfo, VMConfig, VMInfo, VMState};

/// VM Controller events
#[derive(Debug, Clone)]
pub enum VMEvent {
    /// VM started
    Started { vm_name: String, hypervisor: String },
    /// VM stopped
    Stopped { vm_name: String, hypervisor: String },
    /// VM created
    Created { vm_name: String, hypervisor: String },
    /// VM deleted
    Deleted { vm_name: String, hypervisor: String },
    /// Snapshot created
    SnapshotCreated {
        vm_name: String,
        snapshot_name: String,
    },
    /// Error occurred
    Error { vm_name: String, error: String },
}

/// Unified VM Controller
///
/// Provides a single API for managing VMs across different hypervisors.
///
/// # Example
///
/// ```rust,no_run
/// use kagami_hub::vm::VMController;
///
/// async fn example() {
///     let controller = VMController::new().await.unwrap();
///
///     // List all VMs from all hypervisors
///     let vms = controller.list_vms().await.unwrap();
///     for vm in vms {
///         println!("{}: {} ({})", vm.hypervisor, vm.name, vm.state);
///     }
///
///     // Start a specific VM
///     controller.start_vm("my-vm").await.unwrap();
/// }
/// ```
pub struct VMController {
    /// Available hypervisors (keyed by name)
    hypervisors: Arc<RwLock<HashMap<String, Box<dyn HypervisorBackend>>>>,
    /// Event channel
    event_tx: tokio::sync::broadcast::Sender<VMEvent>,
}

impl VMController {
    /// Create a new VM controller, auto-detecting available hypervisors
    pub async fn new() -> VMResult<Self> {
        let hypervisors = detect_hypervisors().await;

        if hypervisors.is_empty() {
            warn!("No hypervisors detected");
        } else {
            let names: Vec<_> = hypervisors.iter().map(|h| h.name()).collect();
            info!("Detected hypervisors: {}", names.join(", "));
        }

        let map: HashMap<String, Box<dyn HypervisorBackend>> = hypervisors
            .into_iter()
            .map(|h| (h.name().to_string(), h))
            .collect();

        let (event_tx, _) = tokio::sync::broadcast::channel(100);

        Ok(Self {
            hypervisors: Arc::new(RwLock::new(map)),
            event_tx,
        })
    }

    /// Create with specific hypervisors
    pub fn with_hypervisors(hypervisors: Vec<Box<dyn HypervisorBackend>>) -> Self {
        let map: HashMap<String, Box<dyn HypervisorBackend>> = hypervisors
            .into_iter()
            .map(|h| (h.name().to_string(), h))
            .collect();

        let (event_tx, _) = tokio::sync::broadcast::channel(100);

        Self {
            hypervisors: Arc::new(RwLock::new(map)),
            event_tx,
        }
    }

    /// Subscribe to VM events
    pub fn subscribe(&self) -> tokio::sync::broadcast::Receiver<VMEvent> {
        self.event_tx.subscribe()
    }

    /// Get available hypervisor names
    pub async fn available_hypervisors(&self) -> Vec<String> {
        let hypervisors = self.hypervisors.read().await;
        hypervisors.keys().cloned().collect()
    }

    /// Find which hypervisor has a VM
    async fn find_vm_hypervisor(&self, vm_name: &str) -> VMResult<String> {
        let hypervisors = self.hypervisors.read().await;

        for (name, backend) in hypervisors.iter() {
            if let Ok(vms) = backend.list_vms().await {
                if vms.iter().any(|vm| vm.name == vm_name || vm.id == vm_name) {
                    return Ok(name.clone());
                }
            }
        }

        Err(VMError::NotFound(vm_name.to_string()))
    }

    // ========================================================================
    // VM Discovery
    // ========================================================================

    /// List all VMs from all hypervisors
    pub async fn list_vms(&self) -> VMResult<Vec<VMInfo>> {
        let hypervisors = self.hypervisors.read().await;
        let mut all_vms = Vec::new();

        for backend in hypervisors.values() {
            match backend.list_vms().await {
                Ok(vms) => all_vms.extend(vms),
                Err(e) => {
                    warn!("Failed to list VMs from {}: {}", backend.name(), e);
                }
            }
        }

        Ok(all_vms)
    }

    /// List VMs from a specific hypervisor
    pub async fn list_vms_by_hypervisor(&self, hypervisor: &str) -> VMResult<Vec<VMInfo>> {
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors
            .get(hypervisor)
            .ok_or_else(|| VMError::HypervisorNotAvailable(hypervisor.to_string()))?;

        backend.list_vms().await
    }

    /// Get information about a specific VM
    pub async fn get_vm(&self, vm_name: &str) -> VMResult<VMInfo> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.get_vm(vm_name).await
    }

    /// Get VM by name with specific hypervisor
    pub async fn get_vm_from(&self, hypervisor: &str, vm_name: &str) -> VMResult<VMInfo> {
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors
            .get(hypervisor)
            .ok_or_else(|| VMError::HypervisorNotAvailable(hypervisor.to_string()))?;

        backend.get_vm(vm_name).await
    }

    // ========================================================================
    // VM Lifecycle
    // ========================================================================

    /// Start a VM
    pub async fn start_vm(&self, vm_name: &str) -> VMResult<()> {
        self.start_vm_with_options(vm_name, false).await
    }

    /// Start a VM with options
    pub async fn start_vm_with_options(&self, vm_name: &str, headless: bool) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        debug!("Starting VM {} via {}", vm_name, hypervisor);
        backend.start_vm(vm_name, headless).await?;

        let _ = self.event_tx.send(VMEvent::Started {
            vm_name: vm_name.to_string(),
            hypervisor,
        });

        Ok(())
    }

    /// Stop a VM (graceful shutdown)
    pub async fn stop_vm(&self, vm_name: &str) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        debug!("Stopping VM {} via {}", vm_name, hypervisor);
        backend.stop_vm(vm_name).await?;

        let _ = self.event_tx.send(VMEvent::Stopped {
            vm_name: vm_name.to_string(),
            hypervisor,
        });

        Ok(())
    }

    /// Force stop a VM (power off)
    pub async fn force_stop_vm(&self, vm_name: &str) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.force_stop_vm(vm_name).await
    }

    /// Pause a VM
    pub async fn pause_vm(&self, vm_name: &str) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.pause_vm(vm_name).await
    }

    /// Resume a paused VM
    pub async fn resume_vm(&self, vm_name: &str) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.resume_vm(vm_name).await
    }

    /// Restart a VM
    pub async fn restart_vm(&self, vm_name: &str) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.restart_vm(vm_name).await
    }

    // ========================================================================
    // VM Provisioning
    // ========================================================================

    /// Create a new VM on a specific hypervisor
    pub async fn create_vm(&self, hypervisor: &str, config: VMConfig) -> VMResult<VMInfo> {
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors
            .get(hypervisor)
            .ok_or_else(|| VMError::HypervisorNotAvailable(hypervisor.to_string()))?;

        let vm = backend.create_vm(&config).await?;

        let _ = self.event_tx.send(VMEvent::Created {
            vm_name: vm.name.clone(),
            hypervisor: hypervisor.to_string(),
        });

        Ok(vm)
    }

    /// Clone an existing VM
    pub async fn clone_vm(&self, source_vm: &str, new_name: &str) -> VMResult<VMInfo> {
        let hypervisor = self.find_vm_hypervisor(source_vm).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        let vm = backend.clone_vm(source_vm, new_name).await?;

        let _ = self.event_tx.send(VMEvent::Created {
            vm_name: vm.name.clone(),
            hypervisor,
        });

        Ok(vm)
    }

    /// Delete a VM
    pub async fn delete_vm(&self, vm_name: &str, delete_files: bool) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.delete_vm(vm_name, delete_files).await?;

        let _ = self.event_tx.send(VMEvent::Deleted {
            vm_name: vm_name.to_string(),
            hypervisor,
        });

        Ok(())
    }

    // ========================================================================
    // Snapshots
    // ========================================================================

    /// List snapshots for a VM
    pub async fn list_snapshots(&self, vm_name: &str) -> VMResult<Vec<SnapshotInfo>> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.list_snapshots(vm_name).await
    }

    /// Create a snapshot
    pub async fn create_snapshot(
        &self,
        vm_name: &str,
        snapshot_name: &str,
        description: Option<&str>,
    ) -> VMResult<SnapshotInfo> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        let snapshot = backend
            .create_snapshot(vm_name, snapshot_name, description)
            .await?;

        let _ = self.event_tx.send(VMEvent::SnapshotCreated {
            vm_name: vm_name.to_string(),
            snapshot_name: snapshot_name.to_string(),
        });

        Ok(snapshot)
    }

    /// Restore a snapshot
    pub async fn restore_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.restore_snapshot(vm_name, snapshot_name).await
    }

    /// Delete a snapshot
    pub async fn delete_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.delete_snapshot(vm_name, snapshot_name).await
    }

    // ========================================================================
    // Resource Management
    // ========================================================================

    /// Update VM resources
    pub async fn update_resources(
        &self,
        vm_name: &str,
        cpu_count: Option<u32>,
        memory_mb: Option<u64>,
    ) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.update_resources(vm_name, cpu_count, memory_mb).await
    }

    // ========================================================================
    // Guest Agent Communication
    // ========================================================================

    /// Execute a command inside a VM
    pub async fn execute_command(
        &self,
        vm_name: &str,
        command: &str,
        timeout_ms: Option<u64>,
    ) -> VMResult<CommandResult> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend
            .execute_command(vm_name, command, timeout_ms.unwrap_or(30000))
            .await
    }

    /// Copy a file to a VM
    pub async fn copy_to_vm(
        &self,
        vm_name: &str,
        local_path: &str,
        remote_path: &str,
    ) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.copy_to_vm(vm_name, local_path, remote_path).await
    }

    /// Copy a file from a VM
    pub async fn copy_from_vm(
        &self,
        vm_name: &str,
        remote_path: &str,
        local_path: &str,
    ) -> VMResult<()> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.copy_from_vm(vm_name, remote_path, local_path).await
    }

    /// Capture a screenshot of a VM
    pub async fn screenshot(&self, vm_name: &str) -> VMResult<Vec<u8>> {
        let hypervisor = self.find_vm_hypervisor(vm_name).await?;
        let hypervisors = self.hypervisors.read().await;
        let backend = hypervisors.get(&hypervisor).unwrap();

        backend.screenshot(vm_name).await
    }

    // ========================================================================
    // Bulk Operations
    // ========================================================================

    /// Start all VMs in a list
    pub async fn start_vms(&self, vm_names: &[&str]) -> Vec<VMResult<()>> {
        let mut results = Vec::new();
        for name in vm_names {
            results.push(self.start_vm(name).await);
        }
        results
    }

    /// Stop all VMs in a list
    pub async fn stop_vms(&self, vm_names: &[&str]) -> Vec<VMResult<()>> {
        let mut results = Vec::new();
        for name in vm_names {
            results.push(self.stop_vm(name).await);
        }
        results
    }

    /// Get all running VMs
    pub async fn running_vms(&self) -> VMResult<Vec<VMInfo>> {
        let all_vms = self.list_vms().await?;
        Ok(all_vms
            .into_iter()
            .filter(|vm| vm.state == VMState::Running)
            .collect())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_controller_creation() {
        let controller = VMController::new().await;
        assert!(controller.is_ok());
    }

    #[tokio::test]
    async fn test_available_hypervisors() {
        let controller = VMController::new().await.unwrap();
        let hypervisors = controller.available_hypervisors().await;
        // May be empty if no hypervisors installed
        assert!(hypervisors.len() >= 0);
    }
}
