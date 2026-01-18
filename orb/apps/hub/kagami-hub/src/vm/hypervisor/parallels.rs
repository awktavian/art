//! Parallels Desktop Backend
//!
//! Control VMs via prlctl CLI (macOS).
//!
//! Supports:
//! - Windows, Linux, macOS VMs
//! - Full lifecycle management
//! - Snapshots
//! - Guest tools integration for command execution

use async_trait::async_trait;
use std::process::Stdio;
use tokio::process::Command;
use tracing::debug;

use super::HypervisorBackend;
use crate::vm::error::{VMError, VMResult};
use crate::vm::types::{CommandResult, OSType, SnapshotInfo, VMConfig, VMInfo, VMState};

/// Parallels Desktop backend
pub struct ParallelsBackend {
    prlctl_path: Option<String>,
}

impl ParallelsBackend {
    /// Create a new Parallels backend
    pub fn new() -> Self {
        Self { prlctl_path: None }
    }

    /// Find prlctl executable
    async fn find_prlctl(&self) -> Option<String> {
        if let Some(ref path) = self.prlctl_path {
            return Some(path.clone());
        }

        // Try common locations
        let paths = [
            "/usr/local/bin/prlctl",
            "/opt/homebrew/bin/prlctl",
            "prlctl",
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

    /// Run prlctl command
    async fn run_prlctl(&self, args: &[&str]) -> VMResult<(i32, String, String)> {
        let prlctl = self.find_prlctl().await.ok_or_else(|| {
            VMError::HypervisorNotAvailable("prlctl not found".to_string())
        })?;

        debug!("Running: prlctl {}", args.join(" "));

        let output = Command::new(&prlctl)
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

    /// Run prlctl and expect success
    async fn run_prlctl_ok(&self, args: &[&str]) -> VMResult<String> {
        let (exit_code, stdout, stderr) = self.run_prlctl(args).await?;
        if exit_code != 0 {
            return Err(VMError::hypervisor_command_failed(
                format!("prlctl {} failed", args.join(" ")),
                Some(stderr),
                Some(exit_code),
            ));
        }
        Ok(stdout)
    }

    /// Parse VM list from prlctl output
    fn parse_vm_list(&self, json_str: &str) -> VMResult<Vec<VMInfo>> {
        let vms: Vec<serde_json::Value> = serde_json::from_str(json_str)?;
        let mut result = Vec::new();

        for vm in vms {
            let id = vm["uuid"].as_str().unwrap_or("").to_string();
            let name = vm["name"].as_str().unwrap_or("").to_string();
            let status = vm["status"].as_str().unwrap_or("stopped").to_lowercase();

            let state = match status.as_str() {
                "running" => VMState::Running,
                "stopped" => VMState::Stopped,
                "paused" => VMState::Paused,
                "suspended" => VMState::Suspended,
                _ => VMState::Unknown,
            };

            // Parse OS type
            let os_str = vm["os"].as_str().unwrap_or("").to_lowercase();
            let os_type = if os_str.contains("windows") {
                OSType::Windows
            } else if os_str.contains("macos") || os_str.contains("mac") {
                OSType::MacOS
            } else if os_str.contains("linux") || os_str.contains("ubuntu") || os_str.contains("debian") {
                OSType::Linux
            } else {
                OSType::Unknown
            };

            let mut vm_info = VMInfo::new(id, name, "parallels");
            vm_info.state = state;
            vm_info.os_type = os_type;

            // Parse resources if available
            if let Some(hw) = vm.get("Hardware") {
                if let Some(cpu) = hw.get("cpu") {
                    if let Some(count) = cpu["cpus"].as_u64() {
                        vm_info.cpu_count = count as u32;
                    }
                }
                if let Some(mem) = hw.get("memory") {
                    if let Some(size) = mem["size"].as_u64() {
                        vm_info.memory_mb = size;
                    }
                }
            }

            // Get IP if running
            if let Some(ip) = vm["ip_configured"].as_str() {
                if !ip.is_empty() {
                    vm_info.ip_address = Some(ip.to_string());
                }
            }

            result.push(vm_info);
        }

        Ok(result)
    }

    /// Parse snapshot list
    fn parse_snapshots(&self, output: &str) -> VMResult<Vec<SnapshotInfo>> {
        let mut snapshots = Vec::new();

        // Parse the tree output from prlctl snapshot-list
        for line in output.lines() {
            let line = line.trim();
            if line.is_empty() || line.starts_with("ID") {
                continue;
            }

            // Format: {uuid} name *? (current marker)
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 2 {
                let id = parts[0].trim_matches(|c| c == '{' || c == '}').to_string();
                let name = parts[1..].join(" ").trim_end_matches(" *").to_string();
                let is_current = line.ends_with(" *");

                let mut snapshot = SnapshotInfo::new(&id, &name);
                snapshot.is_current = is_current;
                snapshots.push(snapshot);
            }
        }

        Ok(snapshots)
    }
}

impl Default for ParallelsBackend {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl HypervisorBackend for ParallelsBackend {
    fn name(&self) -> &'static str {
        "parallels"
    }

    async fn is_available(&self) -> bool {
        self.find_prlctl().await.is_some()
    }

    async fn list_vms(&self) -> VMResult<Vec<VMInfo>> {
        let output = self.run_prlctl_ok(&["list", "-a", "--json"]).await?;
        self.parse_vm_list(&output)
    }

    async fn get_vm(&self, vm_name: &str) -> VMResult<VMInfo> {
        let output = self.run_prlctl_ok(&["list", "-i", vm_name, "--json"]).await?;
        let vms = self.parse_vm_list(&output)?;
        vms.into_iter()
            .next()
            .ok_or_else(|| VMError::NotFound(vm_name.to_string()))
    }

    async fn start_vm(&self, vm_name: &str, _headless: bool) -> VMResult<()> {
        // Parallels doesn't have a headless option - use suspend to close window
        self.run_prlctl_ok(&["start", vm_name]).await?;
        Ok(())
    }

    async fn stop_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_prlctl_ok(&["stop", vm_name]).await?;
        Ok(())
    }

    async fn force_stop_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_prlctl_ok(&["stop", vm_name, "--kill"]).await?;
        Ok(())
    }

    async fn pause_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_prlctl_ok(&["pause", vm_name]).await?;
        Ok(())
    }

    async fn resume_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_prlctl_ok(&["resume", vm_name]).await?;
        Ok(())
    }

    async fn restart_vm(&self, vm_name: &str) -> VMResult<()> {
        self.run_prlctl_ok(&["restart", vm_name]).await?;
        Ok(())
    }

    async fn create_vm(&self, config: &VMConfig) -> VMResult<VMInfo> {
        let mut args = vec!["create", &config.name];

        // OS type
        let os_type = match config.os_type {
            OSType::MacOS => "macosx",
            OSType::Windows => "win-11",
            OSType::Linux => "ubuntu",
            OSType::Unknown => "other",
        };
        args.push("-o");
        args.push(os_type);

        // Create VM
        self.run_prlctl_ok(&args).await?;

        // Set resources
        if config.resources.cpu_count > 0 {
            let cpu_str = config.resources.cpu_count.to_string();
            self.run_prlctl_ok(&["set", &config.name, "--cpus", &cpu_str]).await?;
        }

        if config.resources.memory_mb > 0 {
            let mem_str = config.resources.memory_mb.to_string();
            self.run_prlctl_ok(&["set", &config.name, "--memsize", &mem_str]).await?;
        }

        // Get created VM info
        self.get_vm(&config.name).await
    }

    async fn clone_vm(&self, source_vm: &str, new_name: &str) -> VMResult<VMInfo> {
        self.run_prlctl_ok(&["clone", source_vm, "--name", new_name]).await?;
        self.get_vm(new_name).await
    }

    async fn delete_vm(&self, vm_name: &str, _delete_files: bool) -> VMResult<()> {
        self.run_prlctl_ok(&["delete", vm_name]).await?;
        Ok(())
    }

    async fn list_snapshots(&self, vm_name: &str) -> VMResult<Vec<SnapshotInfo>> {
        let output = self.run_prlctl_ok(&["snapshot-list", vm_name]).await?;
        self.parse_snapshots(&output)
    }

    async fn create_snapshot(
        &self,
        vm_name: &str,
        snapshot_name: &str,
        description: Option<&str>,
    ) -> VMResult<SnapshotInfo> {
        let mut args = vec!["snapshot", vm_name, "-n", snapshot_name];
        if let Some(desc) = description {
            args.push("-d");
            args.push(desc);
        }
        self.run_prlctl_ok(&args).await?;

        // Return the created snapshot info
        let snapshots = self.list_snapshots(vm_name).await?;
        snapshots
            .into_iter()
            .find(|s| s.name == snapshot_name)
            .ok_or_else(|| VMError::Internal("Snapshot created but not found".to_string()))
    }

    async fn restore_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        self.run_prlctl_ok(&["snapshot-switch", vm_name, "-n", snapshot_name]).await?;
        Ok(())
    }

    async fn delete_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        self.run_prlctl_ok(&["snapshot-delete", vm_name, "-n", snapshot_name]).await?;
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
            self.run_prlctl_ok(&["set", vm_name, "--cpus", &cpu_str]).await?;
        }
        if let Some(mem) = memory_mb {
            let mem_str = mem.to_string();
            self.run_prlctl_ok(&["set", vm_name, "--memsize", &mem_str]).await?;
        }
        Ok(())
    }

    async fn execute_command(
        &self,
        vm_name: &str,
        command: &str,
        timeout_ms: u64,
    ) -> VMResult<CommandResult> {
        let start = std::time::Instant::now();

        let (exit_code, stdout, stderr) = tokio::time::timeout(
            std::time::Duration::from_millis(timeout_ms),
            self.run_prlctl(&["exec", vm_name, command]),
        )
        .await
        .map_err(|_| VMError::timeout(vm_name, "execute_command"))??;

        let duration_ms = start.elapsed().as_millis() as u64;

        Ok(CommandResult {
            exit_code,
            stdout,
            stderr,
            duration_ms,
        })
    }

    async fn copy_to_vm(
        &self,
        vm_name: &str,
        local_path: &str,
        remote_path: &str,
    ) -> VMResult<()> {
        self.run_prlctl_ok(&["copy", vm_name, local_path, remote_path]).await?;
        Ok(())
    }

    async fn copy_from_vm(
        &self,
        vm_name: &str,
        remote_path: &str,
        local_path: &str,
    ) -> VMResult<()> {
        // Get OS type to determine command
        let vm = self.get_vm(vm_name).await?;
        let cat_cmd = if vm.os_type == OSType::Windows {
            format!("type \"{}\"", remote_path)
        } else {
            format!("cat \"{}\"", remote_path)
        };

        let result = self.execute_command(vm_name, &cat_cmd, 30000).await?;
        if result.exit_code != 0 {
            return Err(VMError::command_failed(vm_name, result.stderr, result.exit_code));
        }

        tokio::fs::write(local_path, result.stdout).await?;
        Ok(())
    }

    async fn screenshot(&self, vm_name: &str) -> VMResult<Vec<u8>> {
        let temp_path = format!("/tmp/kagami_vm_screenshot_{}.png", vm_name);

        self.run_prlctl_ok(&["capture", vm_name, "--file", &temp_path]).await?;

        let data = tokio::fs::read(&temp_path).await?;
        let _ = tokio::fs::remove_file(&temp_path).await;

        Ok(data)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_snapshots() {
        let backend = ParallelsBackend::new();
        let output = r#"
ID                                       Name
{12345678-1234-1234-1234-123456789012}  clean-install *
{87654321-4321-4321-4321-210987654321}  pre-update
"#;
        let snapshots = backend.parse_snapshots(output).unwrap();
        assert_eq!(snapshots.len(), 2);
        assert!(snapshots[0].is_current);
        assert!(!snapshots[1].is_current);
    }
}
