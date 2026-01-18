//! Lume Backend
//!
//! Control CUA (Computer Use Agent) sandboxed macOS VMs via Lume CLI.
//!
//! Lume provides:
//! - 97% native performance on Apple Silicon
//! - Full VM isolation for untrusted operations
//! - SSH-based command execution
//! - Pre-built macOS images with CUA support

use async_trait::async_trait;
use std::process::Stdio;
use tokio::process::Command;
use tracing::{debug, info, warn};

use super::HypervisorBackend;
use crate::vm::error::{VMError, VMResult};
use crate::vm::types::{CommandResult, OSType, SnapshotInfo, VMConfig, VMInfo, VMState};

/// Default SSH credentials for Lume VMs
const LUME_SSH_USER: &str = "lume";
const LUME_SSH_PASSWORD: &str = "lume";

/// Lume backend for CUA VMs
pub struct LumeBackend {
    ssh_user: String,
    ssh_password: String,
}

impl LumeBackend {
    /// Create a new Lume backend
    pub fn new() -> Self {
        Self {
            ssh_user: LUME_SSH_USER.to_string(),
            ssh_password: LUME_SSH_PASSWORD.to_string(),
        }
    }

    /// Create with custom SSH credentials
    pub fn with_credentials(user: impl Into<String>, password: impl Into<String>) -> Self {
        Self {
            ssh_user: user.into(),
            ssh_password: password.into(),
        }
    }

    /// Find lume executable
    async fn find_lume() -> Option<String> {
        let paths = [
            "/opt/homebrew/bin/lume",
            "/usr/local/bin/lume",
            "lume",
        ];

        for path in paths {
            if let Ok(output) = Command::new(path).arg("--version").output().await {
                if output.status.success() {
                    return Some(path.to_string());
                }
            }
        }

        None
    }

    /// Find sshpass for SSH automation
    async fn find_sshpass() -> Option<String> {
        if let Ok(output) = Command::new("which").arg("sshpass").output().await {
            if output.status.success() {
                let path = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !path.is_empty() {
                    return Some(path);
                }
            }
        }
        None
    }

    /// Run lume command
    async fn run_lume(&self, args: &[&str]) -> VMResult<(i32, String, String)> {
        let lume = Self::find_lume().await.ok_or_else(|| {
            VMError::HypervisorNotAvailable(
                "lume not found - install via: brew install trycua/tap/lume".to_string(),
            )
        })?;

        debug!("Running: lume {}", args.join(" "));

        let output = Command::new(&lume)
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

    /// Run lume and expect success
    async fn run_lume_ok(&self, args: &[&str]) -> VMResult<String> {
        let (exit_code, stdout, stderr) = self.run_lume(args).await?;
        if exit_code != 0 {
            return Err(VMError::hypervisor_command_failed(
                format!("lume {} failed", args.join(" ")),
                Some(stderr),
                Some(exit_code),
            ));
        }
        Ok(stdout)
    }

    /// Parse VM list from lume ls output
    fn parse_vm_list(&self, output: &str) -> VMResult<Vec<VMInfo>> {
        let mut vms = Vec::new();

        // lume ls format: NAME    STATUS    IP    VNC
        for line in output.lines() {
            if line.contains("NAME") || line.trim().is_empty() {
                continue; // Skip header
            }

            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.is_empty() {
                continue;
            }

            let name = parts[0].to_string();
            let status = parts.get(1).unwrap_or(&"stopped").to_lowercase();
            let ip = parts.get(2).and_then(|s| {
                if s.contains('.') {
                    Some(s.to_string())
                } else {
                    None
                }
            });

            let state = match status.as_str() {
                "running" => VMState::Running,
                "stopped" => VMState::Stopped,
                "paused" | "suspended" => VMState::Paused,
                _ => VMState::Stopped,
            };

            let mut vm_info = VMInfo::new(&name, &name, "lume");
            vm_info.state = state;
            vm_info.os_type = OSType::MacOS; // Lume is macOS-only
            vm_info.ip_address = ip;

            vms.push(vm_info);
        }

        Ok(vms)
    }

    /// Execute command via SSH
    async fn ssh_execute(
        &self,
        ip: &str,
        command: &str,
        timeout_ms: u64,
    ) -> VMResult<CommandResult> {
        let sshpass = Self::find_sshpass().await.ok_or_else(|| {
            VMError::HypervisorNotAvailable(
                "sshpass not found - install via: brew install hudochenkov/sshpass/sshpass"
                    .to_string(),
            )
        })?;

        let start = std::time::Instant::now();

        let output = tokio::time::timeout(
            std::time::Duration::from_millis(timeout_ms),
            Command::new(&sshpass)
                .args([
                    "-p",
                    &self.ssh_password,
                    "ssh",
                    "-o",
                    "StrictHostKeyChecking=no",
                    "-o",
                    "UserKnownHostsFile=/dev/null",
                    "-o",
                    "LogLevel=ERROR",
                    &format!("{}@{}", self.ssh_user, ip),
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

    /// Copy file via SCP
    async fn scp_copy(
        &self,
        ip: &str,
        from: &str,
        to: &str,
        to_vm: bool,
    ) -> VMResult<()> {
        let sshpass = Self::find_sshpass().await.ok_or_else(|| {
            VMError::HypervisorNotAvailable("sshpass not found".to_string())
        })?;

        let (src, dst) = if to_vm {
            (from.to_string(), format!("{}@{}:{}", self.ssh_user, ip, to))
        } else {
            (format!("{}@{}:{}", self.ssh_user, ip, from), to.to_string())
        };

        let output = Command::new(&sshpass)
            .args([
                "-p",
                &self.ssh_password,
                "scp",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                &src,
                &dst,
            ])
            .output()
            .await?;

        if !output.status.success() {
            return Err(VMError::command_failed(
                "scp",
                String::from_utf8_lossy(&output.stderr),
                output.status.code().unwrap_or(-1),
            ));
        }

        Ok(())
    }
}

impl Default for LumeBackend {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl HypervisorBackend for LumeBackend {
    fn name(&self) -> &'static str {
        "lume"
    }

    async fn is_available(&self) -> bool {
        Self::find_lume().await.is_some()
    }

    async fn list_vms(&self) -> VMResult<Vec<VMInfo>> {
        let output = self.run_lume_ok(&["ls"]).await?;
        self.parse_vm_list(&output)
    }

    async fn get_vm(&self, vm_name: &str) -> VMResult<VMInfo> {
        let vms = self.list_vms().await?;
        vms.into_iter()
            .find(|vm| vm.name == vm_name || vm.id == vm_name)
            .ok_or_else(|| VMError::NotFound(vm_name.to_string()))
    }

    async fn start_vm(&self, vm_name: &str, headless: bool) -> VMResult<()> {
        let mut args = vec!["run", vm_name];
        if headless {
            args.push("--no-display");
        }

        // Start in background (lume run blocks)
        let lume = Self::find_lume().await.ok_or_else(|| {
            VMError::HypervisorNotAvailable("lume not found".to_string())
        })?;

        let _child = Command::new(&lume)
            .args(&args)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()?;

        // Wait for VM to start
        for _ in 0..30 {
            tokio::time::sleep(std::time::Duration::from_secs(2)).await;
            if let Ok(vm) = self.get_vm(vm_name).await {
                if vm.state == VMState::Running {
                    info!("VM started: {} (IP: {:?})", vm_name, vm.ip_address);
                    return Ok(());
                }
            }
        }

        Err(VMError::timeout(vm_name, "start"))
    }

    async fn stop_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_lume_ok(&["stop", vm_name]).await?;
        Ok(())
    }

    async fn force_stop_vm(&self, vm_name: &str) -> VMResult<()> {
        // Lume stop is already forceful
        self.stop_vm(vm_name).await
    }

    async fn pause_vm(&self, vm_name: &str) -> VMResult<()> {
        // Lume doesn't have native pause - stop instead
        warn!("Lume doesn't support pause, using stop");
        self.stop_vm(vm_name).await
    }

    async fn resume_vm(&self, vm_name: &str) -> VMResult<()> {
        self.start_vm(vm_name, false).await
    }

    async fn restart_vm(&self, vm_name: &str) -> VMResult<()> {
        self.stop_vm(vm_name).await?;
        tokio::time::sleep(std::time::Duration::from_secs(2)).await;
        self.start_vm(vm_name, false).await
    }

    async fn create_vm(&self, config: &VMConfig) -> VMResult<VMInfo> {
        // Lume uses pre-built images - pull instead of create
        if let Some(ref base) = config.base_image {
            self.run_lume_ok(&["pull", base]).await?;
            self.get_vm(&config.name).await
        } else {
            Err(VMError::ConfigError(
                "Lume requires a base_image (e.g., 'macos-sequoia-cua:latest')".to_string(),
            ))
        }
    }

    async fn clone_vm(&self, source_vm: &str, new_name: &str) -> VMResult<VMInfo> {
        self.run_lume_ok(&["clone", source_vm, new_name]).await?;
        self.get_vm(new_name).await
    }

    async fn delete_vm(&self, vm_name: &str, _delete_files: bool) -> VMResult<()> {
        self.run_lume_ok(&["delete", vm_name]).await?;
        Ok(())
    }

    async fn list_snapshots(&self, vm_name: &str) -> VMResult<Vec<SnapshotInfo>> {
        let output = self.run_lume_ok(&["snapshot", "list", vm_name]).await?;
        let snapshots: Vec<SnapshotInfo> = output
            .lines()
            .filter(|l| !l.is_empty())
            .map(|name| SnapshotInfo::new(name, name))
            .collect();
        Ok(snapshots)
    }

    async fn create_snapshot(
        &self,
        vm_name: &str,
        snapshot_name: &str,
        _description: Option<&str>,
    ) -> VMResult<SnapshotInfo> {
        self.run_lume_ok(&["snapshot", vm_name, snapshot_name]).await?;
        Ok(SnapshotInfo::new(snapshot_name, snapshot_name))
    }

    async fn restore_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        self.run_lume_ok(&["restore", vm_name, snapshot_name]).await?;
        Ok(())
    }

    async fn delete_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        self.run_lume_ok(&["snapshot", "delete", vm_name, snapshot_name])
            .await?;
        Ok(())
    }

    async fn update_resources(
        &self,
        _vm_name: &str,
        _cpu_count: Option<u32>,
        _memory_mb: Option<u64>,
    ) -> VMResult<()> {
        // Lume VMs have fixed resources from the image
        Err(VMError::Internal(
            "Lume VM resources are defined by the base image".to_string(),
        ))
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

        self.scp_copy(&ip, local_path, remote_path, true).await
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

        self.scp_copy(&ip, remote_path, local_path, false).await
    }

    async fn screenshot(&self, vm_name: &str) -> VMResult<Vec<u8>> {
        let vm = self.get_vm(vm_name).await?;
        let ip = vm
            .ip_address
            .ok_or_else(|| VMError::GuestAgentNotRunning(vm_name.to_string()))?;

        // Use screencapture on macOS guest
        let result = self
            .ssh_execute(&ip, "screencapture -x /tmp/kagami_screenshot.png", 10000)
            .await?;

        if !result.is_success() {
            return Err(VMError::command_failed(vm_name, result.stderr, result.exit_code));
        }

        // Copy the file
        let temp_path = format!("/tmp/lume_screenshot_{}.png", vm_name);
        self.scp_copy(&ip, "/tmp/kagami_screenshot.png", &temp_path, false)
            .await?;

        // Read and cleanup
        let data = tokio::fs::read(&temp_path).await?;
        let _ = tokio::fs::remove_file(&temp_path).await;

        // Cleanup in VM
        let _ = self.ssh_execute(&ip, "rm -f /tmp/kagami_screenshot.png", 5000).await;

        Ok(data)
    }
}
