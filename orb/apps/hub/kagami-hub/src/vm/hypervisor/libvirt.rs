//! libvirt/KVM Backend
//!
//! Control VMs via virsh CLI (Linux).
//!
//! libvirt provides:
//! - KVM virtualization with near-native performance
//! - Full lifecycle management
//! - Snapshots
//! - Network configuration
//! - Storage management

use async_trait::async_trait;
use std::process::Stdio;
use tokio::process::Command;
use tracing::debug;

use super::HypervisorBackend;
use crate::vm::error::{VMError, VMResult};
use crate::vm::types::{CommandResult, OSType, SnapshotInfo, VMConfig, VMInfo, VMState};

/// libvirt backend
pub struct LibvirtBackend {
    connection_uri: Option<String>,
}

impl LibvirtBackend {
    /// Create a new libvirt backend
    pub fn new() -> Self {
        Self {
            connection_uri: None,
        }
    }

    /// Create with specific connection URI
    pub fn with_uri(uri: impl Into<String>) -> Self {
        Self {
            connection_uri: Some(uri.into()),
        }
    }

    /// Run virsh command
    async fn run_virsh(&self, args: &[&str]) -> VMResult<(i32, String, String)> {
        let mut cmd = Command::new("virsh");

        if let Some(ref uri) = self.connection_uri {
            cmd.arg("-c").arg(uri);
        }

        cmd.args(args)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());

        debug!("Running: virsh {}", args.join(" "));

        let output = cmd.output().await.map_err(|e| {
            VMError::HypervisorNotAvailable(format!("virsh not available: {}", e))
        })?;

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        let exit_code = output.status.code().unwrap_or(-1);

        Ok((exit_code, stdout, stderr))
    }

    /// Run virsh and expect success
    async fn run_virsh_ok(&self, args: &[&str]) -> VMResult<String> {
        let (exit_code, stdout, stderr) = self.run_virsh(args).await?;
        if exit_code != 0 {
            return Err(VMError::hypervisor_command_failed(
                format!("virsh {} failed", args.join(" ")),
                Some(stderr),
                Some(exit_code),
            ));
        }
        Ok(stdout)
    }

    /// Parse VM list from virsh output
    fn parse_vm_list(&self, output: &str) -> VMResult<Vec<VMInfo>> {
        let mut vms = Vec::new();

        // virsh list --all format:
        // Id   Name       State
        // -----------------------
        // 1    vm-name    running
        for line in output.lines().skip(2) {
            // Skip header
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 3 {
                let id = parts[0].to_string();
                let name = parts[1].to_string();
                let status = parts[2].to_lowercase();

                let state = match status.as_str() {
                    "running" => VMState::Running,
                    "shut" | "off" => VMState::Stopped,
                    "paused" => VMState::Paused,
                    "idle" => VMState::Running,
                    _ => VMState::Stopped,
                };

                let mut vm_info = VMInfo::new(&id, &name, "libvirt");
                vm_info.state = state;
                vms.push(vm_info);
            } else if parts.len() == 2 {
                // Stopped VM (no ID)
                let name = parts[0].to_string();
                let status = parts[1].to_lowercase();

                let state = if status == "shut" {
                    VMState::Stopped
                } else {
                    VMState::Unknown
                };

                let mut vm_info = VMInfo::new("-", &name, "libvirt");
                vm_info.state = state;
                vms.push(vm_info);
            }
        }

        Ok(vms)
    }

    /// Get VM IP from DHCP leases
    async fn get_vm_ip(&self, vm_name: &str) -> Option<String> {
        // Try domifaddr
        if let Ok(output) = self.run_virsh(&["domifaddr", vm_name]).await {
            for line in output.1.lines() {
                if let Some(ip) = line.split_whitespace().nth(3) {
                    if ip.contains('.') {
                        return Some(ip.split('/').next().unwrap_or(ip).to_string());
                    }
                }
            }
        }

        // Try net-dhcp-leases
        if let Ok(output) = self.run_virsh(&["net-dhcp-leases", "default"]).await {
            for line in output.1.lines() {
                if line.contains(vm_name) {
                    if let Some(ip) = line.split_whitespace().nth(4) {
                        if ip.contains('.') {
                            return Some(ip.split('/').next().unwrap_or(ip).to_string());
                        }
                    }
                }
            }
        }

        None
    }

    /// Execute command via SSH
    async fn ssh_execute(
        &self,
        ip: &str,
        command: &str,
        timeout_ms: u64,
    ) -> VMResult<CommandResult> {
        let start = std::time::Instant::now();

        let output = tokio::time::timeout(
            std::time::Duration::from_millis(timeout_ms),
            Command::new("ssh")
                .args([
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-o",
                    "BatchMode=yes",
                    &format!("root@{}", ip),
                    command,
                ])
                .output(),
        )
        .await
        .map_err(|_| VMError::timeout(ip, "ssh_execute"))??;

        let duration_ms = start.elapsed().as_millis() as u64;

        Ok(CommandResult {
            exit_code: output.status.code().unwrap_or(-1),
            stdout: String::from_utf8_lossy(&output.stdout).to_string(),
            stderr: String::from_utf8_lossy(&output.stderr).to_string(),
            duration_ms,
        })
    }
}

impl Default for LibvirtBackend {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl HypervisorBackend for LibvirtBackend {
    fn name(&self) -> &'static str {
        "libvirt"
    }

    async fn is_available(&self) -> bool {
        matches!(self.run_virsh(&["version"]).await, Ok((0, _, _)))
    }

    async fn list_vms(&self) -> VMResult<Vec<VMInfo>> {
        let output = self.run_virsh_ok(&["list", "--all"]).await?;
        self.parse_vm_list(&output)
    }

    async fn get_vm(&self, vm_name: &str) -> VMResult<VMInfo> {
        // Get domain info
        let output = self.run_virsh_ok(&["dominfo", vm_name]).await?;

        let mut vm_info = VMInfo::new(vm_name, vm_name, "libvirt");

        for line in output.lines() {
            let parts: Vec<&str> = line.splitn(2, ':').collect();
            if parts.len() == 2 {
                let key = parts[0].trim().to_lowercase();
                let value = parts[1].trim();

                match key.as_str() {
                    "state" => {
                        vm_info.state = match value.to_lowercase().as_str() {
                            "running" => VMState::Running,
                            "shut off" | "shutoff" => VMState::Stopped,
                            "paused" => VMState::Paused,
                            _ => VMState::Unknown,
                        };
                    }
                    "cpu(s)" => {
                        vm_info.cpu_count = value.parse().unwrap_or(0);
                    }
                    "max memory" => {
                        // Format: "8388608 KiB"
                        if let Some(kb_str) = value.split_whitespace().next() {
                            if let Ok(kb) = kb_str.parse::<u64>() {
                                vm_info.memory_mb = kb / 1024;
                            }
                        }
                    }
                    _ => {}
                }
            }
        }

        // Try to get IP
        vm_info.ip_address = self.get_vm_ip(vm_name).await;

        // Get OS type from metadata
        if let Ok(output) = self.run_virsh(&["dumpxml", vm_name]).await {
            let xml = output.1.to_lowercase();
            if xml.contains("windows") || xml.contains("win") {
                vm_info.os_type = OSType::Windows;
            } else if xml.contains("linux") || xml.contains("ubuntu") || xml.contains("debian") {
                vm_info.os_type = OSType::Linux;
            }
        }

        Ok(vm_info)
    }

    async fn start_vm(&self, vm_name: &str, _headless: bool) -> VMResult<()> {
        // libvirt VMs are always "headless" from the host perspective
        self.run_virsh_ok(&["start", vm_name]).await?;
        Ok(())
    }

    async fn stop_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_virsh_ok(&["shutdown", vm_name]).await?;
        Ok(())
    }

    async fn force_stop_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_virsh_ok(&["destroy", vm_name]).await?;
        Ok(())
    }

    async fn pause_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_virsh_ok(&["suspend", vm_name]).await?;
        Ok(())
    }

    async fn resume_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_virsh_ok(&["resume", vm_name]).await?;
        Ok(())
    }

    async fn restart_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_virsh_ok(&["reboot", vm_name]).await?;
        Ok(())
    }

    async fn create_vm(&self, config: &VMConfig) -> VMResult<VMInfo> {
        // Creating a VM with virt-install
        // Pre-compute string values to avoid temporary lifetime issues
        let ram_str = config.resources.memory_mb.to_string();
        let vcpu_str = config.resources.cpu_count.to_string();
        let disk_str = format!("size={}", config.resources.disk_gb);
        let os_variant = match config.os_type {
            OSType::Linux => "linux2022",
            OSType::Windows => "win11",
            _ => "generic",
        };

        let mut args = vec![
            "--name",
            &config.name,
            "--ram",
            &ram_str,
            "--vcpus",
            &vcpu_str,
            "--disk",
            &disk_str,
            "--os-variant",
            os_variant,
            "--graphics",
            "vnc",
            "--noautoconsole",
        ];

        if let Some(ref iso) = config.iso_path {
            args.push("--cdrom");
            args.push(iso);
        }

        let output = Command::new("virt-install")
            .args(&args)
            .output()
            .await
            .map_err(|e| VMError::HypervisorNotAvailable(format!("virt-install: {}", e)))?;

        if !output.status.success() {
            return Err(VMError::hypervisor_command_failed(
                "virt-install failed",
                Some(String::from_utf8_lossy(&output.stderr).to_string()),
                output.status.code(),
            ));
        }

        self.get_vm(&config.name).await
    }

    async fn clone_vm(&self, source_vm: &str, new_name: &str) -> VMResult<VMInfo> {
        let output = Command::new("virt-clone")
            .args([
                "--original",
                source_vm,
                "--name",
                new_name,
                "--auto-clone",
            ])
            .output()
            .await
            .map_err(|e| VMError::HypervisorNotAvailable(format!("virt-clone: {}", e)))?;

        if !output.status.success() {
            return Err(VMError::hypervisor_command_failed(
                "virt-clone failed",
                Some(String::from_utf8_lossy(&output.stderr).to_string()),
                output.status.code(),
            ));
        }

        self.get_vm(new_name).await
    }

    async fn delete_vm(&self, vm_name: &str, delete_files: bool) -> VMResult<()> {
        // Stop if running
        let _ = self.force_stop_vm(vm_name).await;

        if delete_files {
            self.run_virsh_ok(&["undefine", vm_name, "--remove-all-storage"])
                .await?;
        } else {
            self.run_virsh_ok(&["undefine", vm_name]).await?;
        }
        Ok(())
    }

    async fn list_snapshots(&self, vm_name: &str) -> VMResult<Vec<SnapshotInfo>> {
        let output = self.run_virsh_ok(&["snapshot-list", vm_name]).await?;

        let mut snapshots = Vec::new();
        for line in output.lines().skip(2) {
            // Skip header
            let parts: Vec<&str> = line.split_whitespace().collect();
            if !parts.is_empty() {
                let name = parts[0].to_string();
                let mut snapshot = SnapshotInfo::new(&name, &name);

                if parts.len() >= 2 {
                    snapshot.created_at = Some(parts[1..].join(" "));
                }

                snapshots.push(snapshot);
            }
        }

        Ok(snapshots)
    }

    async fn create_snapshot(
        &self,
        vm_name: &str,
        snapshot_name: &str,
        description: Option<&str>,
    ) -> VMResult<SnapshotInfo> {
        let mut args = vec![
            "snapshot-create-as",
            vm_name,
            "--name",
            snapshot_name,
        ];

        if let Some(desc) = description {
            args.push("--description");
            args.push(desc);
        }

        self.run_virsh_ok(&args).await?;
        Ok(SnapshotInfo::new(snapshot_name, snapshot_name))
    }

    async fn restore_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        self.run_virsh_ok(&["snapshot-revert", vm_name, snapshot_name])
            .await?;
        Ok(())
    }

    async fn delete_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        self.run_virsh_ok(&["snapshot-delete", vm_name, snapshot_name])
            .await?;
        Ok(())
    }

    async fn update_resources(
        &self,
        vm_name: &str,
        cpu_count: Option<u32>,
        memory_mb: Option<u64>,
    ) -> VMResult<()> {
        if let Some(cpus) = cpu_count {
            let cpu_str = cpus.to_string();
            self.run_virsh_ok(&["setvcpus", vm_name, &cpu_str, "--config"])
                .await?;
        }

        if let Some(mem) = memory_mb {
            let mem_kb = (mem * 1024).to_string();
            self.run_virsh_ok(&["setmaxmem", vm_name, &mem_kb, "--config"])
                .await?;
            self.run_virsh_ok(&["setmem", vm_name, &mem_kb, "--config"])
                .await?;
        }

        Ok(())
    }

    async fn execute_command(
        &self,
        vm_name: &str,
        command: &str,
        timeout_ms: u64,
    ) -> VMResult<CommandResult> {
        let vm = self.get_vm(vm_name).await?;
        let ip = vm
            .ip_address
            .ok_or_else(|| VMError::GuestAgentNotRunning(vm_name.to_string()))?;

        self.ssh_execute(&ip, command, timeout_ms).await
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
            .ok_or_else(|| VMError::GuestAgentNotRunning(vm_name.to_string()))?;

        let output = Command::new("scp")
            .args([
                "-o",
                "StrictHostKeyChecking=no",
                local_path,
                &format!("root@{}:{}", ip, remote_path),
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
            .ok_or_else(|| VMError::GuestAgentNotRunning(vm_name.to_string()))?;

        let output = Command::new("scp")
            .args([
                "-o",
                "StrictHostKeyChecking=no",
                &format!("root@{}:{}", ip, remote_path),
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
        let temp_path = format!("/tmp/libvirt_screenshot_{}.ppm", vm_name);

        self.run_virsh_ok(&["screenshot", vm_name, &temp_path]).await?;

        // Convert PPM to PNG if ImageMagick is available
        let png_path = format!("/tmp/libvirt_screenshot_{}.png", vm_name);
        if let Ok(output) = Command::new("convert")
            .args([&temp_path, &png_path])
            .output()
            .await
        {
            if output.status.success() {
                let data = tokio::fs::read(&png_path).await?;
                let _ = tokio::fs::remove_file(&temp_path).await;
                let _ = tokio::fs::remove_file(&png_path).await;
                return Ok(data);
            }
        }

        // Return PPM if conversion failed
        let data = tokio::fs::read(&temp_path).await?;
        let _ = tokio::fs::remove_file(&temp_path).await;
        Ok(data)
    }
}
