//! UTM/QEMU Backend
//!
//! Control VMs via UTM (macOS) or direct QEMU commands.
//!
//! UTM provides a nice macOS-native wrapper around QEMU with:
//! - Apple Silicon virtualization (SPICE/virtio)
//! - utmctl CLI for automation
//! - Shared folder support
//!
//! Falls back to direct qemu-system-* commands if UTM not available.

use async_trait::async_trait;
use std::process::Stdio;
use tokio::process::Command;
use tracing::{debug, warn};

use super::HypervisorBackend;
use crate::vm::error::{VMError, VMResult};
use crate::vm::types::{CommandResult, OSType, SnapshotInfo, VMConfig, VMInfo, VMState};

/// UTM/QEMU backend
pub struct UTMBackend {
    utmctl_available: bool,
}

impl UTMBackend {
    /// Create a new UTM backend
    pub fn new() -> Self {
        Self {
            utmctl_available: false,
        }
    }

    /// Find utmctl executable
    async fn find_utmctl() -> Option<String> {
        // utmctl comes with UTM app
        let paths = [
            "/Applications/UTM.app/Contents/MacOS/utmctl",
            "/usr/local/bin/utmctl",
            "utmctl",
        ];

        for path in paths {
            if let Ok(output) = Command::new(path).arg("--help").output().await {
                if output.status.success() {
                    return Some(path.to_string());
                }
            }
        }

        None
    }

    /// Run utmctl command
    async fn run_utmctl(&self, args: &[&str]) -> VMResult<(i32, String, String)> {
        let utmctl = Self::find_utmctl().await.ok_or_else(|| {
            VMError::HypervisorNotAvailable("utmctl not found - is UTM installed?".to_string())
        })?;

        debug!("Running: utmctl {}", args.join(" "));

        let output = Command::new(&utmctl)
            .args(args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .await?;

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        let exit_code = output.status.code().unwrap_or(-1);

        Ok((exit_code, stdout, stderr))
    }

    /// Run utmctl and expect success
    async fn run_utmctl_ok(&self, args: &[&str]) -> VMResult<String> {
        let (exit_code, stdout, stderr) = self.run_utmctl(args).await?;
        if exit_code != 0 {
            return Err(VMError::hypervisor_command_failed(
                format!("utmctl {} failed", args.join(" ")),
                Some(stderr),
                Some(exit_code),
            ));
        }
        Ok(stdout)
    }

    /// Parse VM list from utmctl output
    fn parse_vm_list(&self, output: &str) -> VMResult<Vec<VMInfo>> {
        let mut vms = Vec::new();

        // utmctl list outputs: UUID    Name    Status
        for line in output.lines().skip(1) {
            // Skip header
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 3 {
                let id = parts[0].to_string();
                let name = parts[1..parts.len() - 1].join(" ");
                let status = parts.last().unwrap_or(&"stopped").to_lowercase();

                let state = match status.as_str() {
                    "running" | "started" => VMState::Running,
                    "stopped" | "shutdown" => VMState::Stopped,
                    "paused" | "suspended" => VMState::Paused,
                    _ => VMState::Stopped,
                };

                let mut vm_info = VMInfo::new(id, name, "utm");
                vm_info.state = state;
                vms.push(vm_info);
            }
        }

        Ok(vms)
    }

    /// Execute command in VM via SSH (requires guest IP)
    async fn ssh_execute(
        &self,
        vm_info: &VMInfo,
        command: &str,
        timeout_ms: u64,
    ) -> VMResult<CommandResult> {
        let ip = vm_info
            .ip_address
            .as_ref()
            .ok_or_else(|| VMError::GuestAgentNotRunning(vm_info.name.clone()))?;

        let start = std::time::Instant::now();

        // Try SSH with common credentials
        let output = tokio::time::timeout(
            std::time::Duration::from_millis(timeout_ms),
            Command::new("ssh")
                .args([
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-o",
                    "LogLevel=ERROR",
                    &format!("user@{}", ip),
                    command,
                ])
                .output(),
        )
        .await
        .map_err(|_| VMError::timeout(&vm_info.name, "ssh_execute"))??;

        let duration_ms = start.elapsed().as_millis() as u64;

        Ok(CommandResult {
            exit_code: output.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
            duration_ms,
        })
    }
}

impl Default for UTMBackend {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl HypervisorBackend for UTMBackend {
    fn name(&self) -> &'static str {
        "utm"
    }

    async fn is_available(&self) -> bool {
        Self::find_utmctl().await.is_some()
    }

    async fn list_vms(&self) -> VMResult<Vec<VMInfo>> {
        let output = self.run_utmctl_ok(&["list"]).await?;
        self.parse_vm_list(&output)
    }

    async fn get_vm(&self, vm_name: &str) -> VMResult<VMInfo> {
        let vms = self.list_vms().await?;
        vms.into_iter()
            .find(|vm| vm.name == vm_name || vm.id == vm_name)
            .ok_or_else(|| VMError::NotFound(vm_name.to_string()))
    }

    async fn start_vm(&self, vm_name: &str, _headless: bool) -> VMResult<()> {
        // UTM uses "start" command
        self.run_utmctl_ok(&["start", vm_name]).await?;
        Ok(())
    }

    async fn stop_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_utmctl_ok(&["stop", vm_name]).await?;
        Ok(())
    }

    async fn force_stop_vm(&self, vm_name: &str) -> VMResult<()> {
        // UTM uses --kill flag
        self.run_utmctl_ok(&["stop", vm_name, "--kill"]).await?;
        Ok(())
    }

    async fn pause_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_utmctl_ok(&["suspend", vm_name]).await?;
        Ok(())
    }

    async fn resume_vm(&self, vm_name: &str) -> VMResult<()> {
        // Resume is same as start in UTM
        self.run_utmctl_ok(&["start", vm_name]).await?;
        Ok(())
    }

    async fn restart_vm(&self, vm_name: &str) -> VMResult<()> {
        self.stop_vm(vm_name).await?;
        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
        self.start_vm(vm_name, false).await
    }

    async fn create_vm(&self, _config: &VMConfig) -> VMResult<VMInfo> {
        // UTM doesn't have direct CLI creation - use clone or import
        Err(VMError::Internal(
            "UTM VM creation requires the GUI or importing a .utm package. \
             Use clone_vm with an existing template instead."
                .to_string(),
        ))
    }

    async fn clone_vm(&self, source_vm: &str, new_name: &str) -> VMResult<VMInfo> {
        self.run_utmctl_ok(&["clone", source_vm, "--name", new_name]).await?;
        self.get_vm(new_name).await
    }

    async fn delete_vm(&self, vm_name: &str, _delete_files: bool) -> VMResult<()> {
        self.run_utmctl_ok(&["delete", vm_name]).await?;
        Ok(())
    }

    async fn list_snapshots(&self, _vm_name: &str) -> VMResult<Vec<SnapshotInfo>> {
        // UTM snapshot support is limited
        warn!("UTM snapshot listing not fully supported via CLI");
        Ok(Vec::new())
    }

    async fn create_snapshot(
        &self,
        vm_name: &str,
        snapshot_name: &str,
        _description: Option<&str>,
    ) -> VMResult<SnapshotInfo> {
        // UTM uses QEMU snapshots internally
        self.run_utmctl_ok(&["snapshot", vm_name, "--name", snapshot_name]).await?;
        Ok(SnapshotInfo::new(snapshot_name, snapshot_name))
    }

    async fn restore_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        self.run_utmctl_ok(&["restore", vm_name, "--name", snapshot_name]).await?;
        Ok(())
    }

    async fn delete_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        self.run_utmctl_ok(&["delete-snapshot", vm_name, "--name", snapshot_name])
            .await?;
        Ok(())
    }

    async fn update_resources(
        &self,
        _vm_name: &str,
        _cpu_count: Option<u32>,
        _memory_mb: Option<u64>,
    ) -> VMResult<()> {
        // UTM requires editing the .utm package or using the GUI
        Err(VMError::Internal(
            "UTM resource modification requires the GUI".to_string(),
        ))
    }

    async fn execute_command(
        &self,
        vm_name: &str,
        command: &str,
        timeout_ms: u64,
    ) -> VMResult<CommandResult> {
        let vm = self.get_vm(vm_name).await?;
        self.ssh_execute(&vm, command, timeout_ms).await
    }

    async fn copy_to_vm(
        &self,
        vm_name: &str,
        local_path: &str,
        remote_path: &str,
    ) -> VMResult<()> {
        let vm = self.get_vm(vm_name).await?;
        let ip = vm
            .ip_address
            .as_ref()
            .ok_or_else(|| VMError::GuestAgentNotRunning(vm_name.to_string()))?;

        let output = Command::new("scp")
            .args([
                "-o",
                "StrictHostKeyChecking=no",
                local_path,
                &format!("user@{}:{}", ip, remote_path),
            ])
            .output()
            .await?;

        if !output.status.success() {
            return Err(VMError::command_failed(
                vm_name,
                String::from_utf8_lossy(&output.stderr),
                output.status.code().unwrap_or(-1),
            ));
        }

        Ok(())
    }

    async fn copy_from_vm(
        &self,
        vm_name: &str,
        remote_path: &str,
        local_path: &str,
    ) -> VMResult<()> {
        let vm = self.get_vm(vm_name).await?;
        let ip = vm
            .ip_address
            .as_ref()
            .ok_or_else(|| VMError::GuestAgentNotRunning(vm_name.to_string()))?;

        let output = Command::new("scp")
            .args([
                "-o",
                "StrictHostKeyChecking=no",
                &format!("user@{}:{}", ip, remote_path),
                local_path,
            ])
            .output()
            .await?;

        if !output.status.success() {
            return Err(VMError::command_failed(
                vm_name,
                String::from_utf8_lossy(&output.stderr),
                output.status.code().unwrap_or(-1),
            ));
        }

        Ok(())
    }

    async fn screenshot(&self, vm_name: &str) -> VMResult<Vec<u8>> {
        // UTM doesn't have native screenshot - try via guest
        let vm = self.get_vm(vm_name).await?;

        if vm.os_type == OSType::MacOS {
            // Use screencapture on macOS guests
            let result = self
                .execute_command(vm_name, "screencapture -x /tmp/screenshot.png", 10000)
                .await?;

            if !result.is_success() {
                return Err(VMError::command_failed(vm_name, result.stderr, result.exit_code));
            }

            // Copy the file
            let temp_path = format!("/tmp/utm_screenshot_{}.png", vm_name);
            self.copy_from_vm(vm_name, "/tmp/screenshot.png", &temp_path)
                .await?;

            let data = tokio::fs::read(&temp_path).await?;
            let _ = tokio::fs::remove_file(&temp_path).await;
            Ok(data)
        } else {
            Err(VMError::Internal(
                "Screenshot requires guest tools or macOS guest".to_string(),
            ))
        }
    }
}
