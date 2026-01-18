//! Hyper-V Backend
//!
//! Control VMs via PowerShell/WMI (Windows).
//!
//! Hyper-V provides:
//! - Native Windows virtualization
//! - Full lifecycle management
//! - Checkpoints (snapshots)
//! - Enhanced session mode

use async_trait::async_trait;
use std::process::Stdio;
use tokio::process::Command;
use tracing::{debug, warn};

use super::HypervisorBackend;
use crate::vm::error::{VMError, VMResult};
use crate::vm::types::{CommandResult, SnapshotInfo, VMConfig, VMInfo, VMState};

/// Hyper-V backend
pub struct HyperVBackend {
    /// PowerShell executable path
    powershell_path: String,
}

impl HyperVBackend {
    /// Create a new Hyper-V backend
    pub fn new() -> Self {
        Self {
            powershell_path: "powershell.exe".to_string(),
        }
    }

    /// Run PowerShell command
    async fn run_ps(&self, script: &str) -> VMResult<(i32, String, String)> {
        debug!("Running PowerShell: {}", script);

        let output = Command::new(&self.powershell_path)
            .args([
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .output()
            .await
            .map_err(|e| {
                VMError::HypervisorNotAvailable(format!("PowerShell not available: {}", e))
            })?;

        let stdout = String::from_utf8_lossy(&output.stdout).to_string();
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        let exit_code = output.status.code().unwrap_or(-1);

        Ok((exit_code, stdout, stderr))
    }

    /// Run PowerShell and expect success
    async fn run_ps_ok(&self, script: &str) -> VMResult<String> {
        let (exit_code, stdout, stderr) = self.run_ps(script).await?;
        if exit_code != 0 {
            return Err(VMError::hypervisor_command_failed(
                format!("PowerShell command failed: {}", script),
                Some(stderr),
                Some(exit_code),
            ));
        }
        Ok(stdout)
    }

    /// Parse VM list from Get-VM output
    fn parse_vm_list(&self, json_str: &str) -> VMResult<Vec<VMInfo>> {
        let vms: Vec<serde_json::Value> = serde_json::from_str(json_str)?;
        let mut result = Vec::new();

        for vm in vms {
            let id = vm["VMId"]
                .as_str()
                .unwrap_or_default()
                .to_string();
            let name = vm["VMName"]
                .as_str()
                .unwrap_or_default()
                .to_string();
            let state_num = vm["State"].as_u64().unwrap_or(0);

            let state = match state_num {
                2 => VMState::Running,
                3 => VMState::Stopped,
                6 => VMState::Paused,
                9 => VMState::Suspended,
                _ => VMState::Unknown,
            };

            let mut vm_info = VMInfo::new(id, name, "hyperv");
            vm_info.state = state;

            // Parse resources
            if let Some(cpus) = vm["ProcessorCount"].as_u64() {
                vm_info.cpu_count = cpus as u32;
            }
            if let Some(mem) = vm["MemoryStartup"].as_u64() {
                vm_info.memory_mb = mem / 1024 / 1024; // Convert bytes to MB
            }

            result.push(vm_info);
        }

        Ok(result)
    }

    /// Get VM IP address
    async fn get_vm_ip(&self, vm_name: &str) -> Option<String> {
        let script = format!(
            r#"(Get-VMNetworkAdapter -VMName '{}' | Select-Object -ExpandProperty IPAddresses | Where-Object {{ $_ -match '^\d+\.\d+\.\d+\.\d+$' }}) -join ','"#,
            vm_name.replace("'", "''")
        );

        if let Ok(output) = self.run_ps(&script).await {
            let ip = output.1.trim().to_string();
            if !ip.is_empty() && ip.contains('.') {
                return Some(ip.split(',').next().unwrap_or(&ip).to_string());
            }
        }

        None
    }

    /// Execute command via PowerShell Direct
    async fn ps_direct_execute(
        &self,
        vm_name: &str,
        command: &str,
        timeout_ms: u64,
    ) -> VMResult<CommandResult> {
        let start = std::time::Instant::now();

        // Use Invoke-Command with VMName (PowerShell Direct)
        let script = format!(
            r#"
            $output = Invoke-Command -VMName '{}' -ScriptBlock {{ {} }} -ErrorAction Stop
            $output | ConvertTo-Json
            "#,
            vm_name.replace("'", "''"),
            command.replace("'", "''")
        );

        let result = tokio::time::timeout(
            std::time::Duration::from_millis(timeout_ms),
            self.run_ps(&script),
        )
        .await
        .map_err(|_| VMError::timeout(vm_name, "ps_direct_execute"))?;

        let (exit_code, stdout, stderr) = result?;
        let duration_ms = start.elapsed().as_millis() as u64;

        Ok(CommandResult {
            exit_code,
            stdout,
            stderr,
            duration_ms,
        })
    }
}

impl Default for HyperVBackend {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl HypervisorBackend for HyperVBackend {
    fn name(&self) -> &'static str {
        "hyperv"
    }

    async fn is_available(&self) -> bool {
        // Check if running on Windows and Hyper-V is available
        if !cfg!(target_os = "windows") {
            return false;
        }

        matches!(
            self.run_ps("Get-VMHost | Select-Object -Property Name | ConvertTo-Json").await,
            Ok((0, _, _))
        )
    }

    async fn list_vms(&self) -> VMResult<Vec<VMInfo>> {
        let script = "Get-VM | Select-Object VMId, VMName, State, ProcessorCount, MemoryStartup | ConvertTo-Json";
        let output = self.run_ps_ok(script).await?;

        // Handle single VM (not array) vs multiple VMs (array)
        let json_str = if output.trim().starts_with('[') {
            output
        } else {
            format!("[{}]", output)
        };

        self.parse_vm_list(&json_str)
    }

    async fn get_vm(&self, vm_name: &str) -> VMResult<VMInfo> {
        let script = format!(
            "Get-VM -Name '{}' | Select-Object VMId, VMName, State, ProcessorCount, MemoryStartup | ConvertTo-Json",
            vm_name.replace("'", "''")
        );

        let output = self.run_ps_ok(&script).await?;
        let json_str = format!("[{}]", output);

        let mut vms = self.parse_vm_list(&json_str)?;

        if vms.is_empty() {
            return Err(VMError::NotFound(vm_name.to_string()));
        }

        let mut vm = vms.remove(0);
        vm.ip_address = self.get_vm_ip(vm_name).await;

        Ok(vm)
    }

    async fn start_vm(&self, vm_name: &str, _headless: bool) -> VMResult<()> {
        let script = format!("Start-VM -Name '{}'", vm_name.replace("'", "''"));
        self.run_ps_ok(&script).await?;
        Ok(())
    }

    async fn stop_vm(&self, vm_name: &str) -> VMResult<()> {
        let script = format!("Stop-VM -Name '{}' -Force", vm_name.replace("'", "''"));
        self.run_ps_ok(&script).await?;
        Ok(())
    }

    async fn force_stop_vm(&self, vm_name: &str) -> VMResult<()> {
        let script = format!(
            "Stop-VM -Name '{}' -TurnOff -Force",
            vm_name.replace("'", "''")
        );
        self.run_ps_ok(&script).await?;
        Ok(())
    }

    async fn pause_vm(&self, vm_name: &str) -> VMResult<()> {
        let script = format!("Suspend-VM -Name '{}'", vm_name.replace("'", "''"));
        self.run_ps_ok(&script).await?;
        Ok(())
    }

    async fn resume_vm(&self, vm_name: &str) -> VMResult<()> {
        let script = format!("Resume-VM -Name '{}'", vm_name.replace("'", "''"));
        self.run_ps_ok(&script).await?;
        Ok(())
    }

    async fn restart_vm(&self, vm_name: &str) -> VMResult<()> {
        let script = format!("Restart-VM -Name '{}' -Force", vm_name.replace("'", "''"));
        self.run_ps_ok(&script).await?;
        Ok(())
    }

    async fn create_vm(&self, config: &VMConfig) -> VMResult<VMInfo> {
        let script = format!(
            r#"
            New-VM -Name '{}' `
                -MemoryStartupBytes {}MB `
                -Generation 2 `
                -NewVHDPath 'C:\Hyper-V\{}\{}.vhdx' `
                -NewVHDSizeBytes {}GB

            Set-VMProcessor -VMName '{}' -Count {}
            "#,
            config.name.replace("'", "''"),
            config.resources.memory_mb,
            config.name.replace("'", "''"),
            config.name.replace("'", "''"),
            config.resources.disk_gb,
            config.name.replace("'", "''"),
            config.resources.cpu_count
        );

        self.run_ps_ok(&script).await?;

        // Attach ISO if provided
        if let Some(ref iso) = config.iso_path {
            let iso_script = format!(
                "Add-VMDvdDrive -VMName '{}' -Path '{}'",
                config.name.replace("'", "''"),
                iso.replace("'", "''")
            );
            self.run_ps_ok(&iso_script).await?;
        }

        self.get_vm(&config.name).await
    }

    async fn clone_vm(&self, source_vm: &str, new_name: &str) -> VMResult<VMInfo> {
        // Hyper-V doesn't have native clone - export/import
        let script = format!(
            r#"
            $vm = Get-VM -Name '{}'
            $exportPath = "C:\Hyper-V\Export\$($vm.Name)"
            Export-VM -VM $vm -Path $exportPath
            Import-VM -Path "$exportPath\$($vm.Name)\Virtual Machines\*.vmcx" -Copy -GenerateNewId -VirtualMachinePath "C:\Hyper-V\{}" -VhdDestinationPath "C:\Hyper-V\{}"
            Rename-VM -VM (Get-VM | Where-Object Name -eq $vm.Name | Select-Object -Last 1) -NewName '{}'
            Remove-Item -Path $exportPath -Recurse -Force
            "#,
            source_vm.replace("'", "''"),
            new_name.replace("'", "''"),
            new_name.replace("'", "''"),
            new_name.replace("'", "''")
        );

        self.run_ps_ok(&script).await?;
        self.get_vm(new_name).await
    }

    async fn delete_vm(&self, vm_name: &str, delete_files: bool) -> VMResult<()> {
        // Stop if running
        let _ = self.force_stop_vm(vm_name).await;

        if delete_files {
            let script = format!(
                r#"
                $vm = Get-VM -Name '{}'
                $vhds = $vm | Get-VMHardDiskDrive | Select-Object -ExpandProperty Path
                Remove-VM -Name '{}' -Force
                $vhds | ForEach-Object {{ Remove-Item -Path $_ -Force }}
                "#,
                vm_name.replace("'", "''"),
                vm_name.replace("'", "''")
            );
            self.run_ps_ok(&script).await?;
        } else {
            let script = format!("Remove-VM -Name '{}' -Force", vm_name.replace("'", "''"));
            self.run_ps_ok(&script).await?;
        }

        Ok(())
    }

    async fn list_snapshots(&self, vm_name: &str) -> VMResult<Vec<SnapshotInfo>> {
        let script = format!(
            "Get-VMSnapshot -VMName '{}' | Select-Object Id, Name, CreationTime, ParentSnapshotId | ConvertTo-Json",
            vm_name.replace("'", "''")
        );

        let output = self.run_ps_ok(&script).await?;
        if output.trim().is_empty() {
            return Ok(Vec::new());
        }

        let json_str = if output.trim().starts_with('[') {
            output
        } else {
            format!("[{}]", output)
        };

        let snapshots: Vec<serde_json::Value> = serde_json::from_str(&json_str)?;
        let result: Vec<SnapshotInfo> = snapshots
            .into_iter()
            .map(|s| {
                let mut snapshot = SnapshotInfo::new(
                    s["Id"].as_str().unwrap_or_default(),
                    s["Name"].as_str().unwrap_or_default(),
                );
                if let Some(created) = s["CreationTime"].as_str() {
                    snapshot.created_at = Some(created.to_string());
                }
                if let Some(parent) = s["ParentSnapshotId"].as_str() {
                    snapshot.parent = Some(parent.to_string());
                }
                snapshot
            })
            .collect();

        Ok(result)
    }

    async fn create_snapshot(
        &self,
        vm_name: &str,
        snapshot_name: &str,
        _description: Option<&str>,
    ) -> VMResult<SnapshotInfo> {
        let script = format!(
            "Checkpoint-VM -Name '{}' -SnapshotName '{}'",
            vm_name.replace("'", "''"),
            snapshot_name.replace("'", "''")
        );

        self.run_ps_ok(&script).await?;

        // Get the created snapshot
        let snapshots = self.list_snapshots(vm_name).await?;
        snapshots
            .into_iter()
            .find(|s| s.name == snapshot_name)
            .ok_or_else(|| VMError::Internal("Snapshot created but not found".to_string()))
    }

    async fn restore_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        let script = format!(
            "Restore-VMSnapshot -VMName '{}' -Name '{}' -Confirm:$false",
            vm_name.replace("'", "''"),
            snapshot_name.replace("'", "''")
        );
        self.run_ps_ok(&script).await?;
        Ok(())
    }

    async fn delete_snapshot(&self, vm_name: &str, snapshot_name: &str) -> VMResult<()> {
        let script = format!(
            "Remove-VMSnapshot -VMName '{}' -Name '{}' -Confirm:$false",
            vm_name.replace("'", "''"),
            snapshot_name.replace("'", "''")
        );
        self.run_ps_ok(&script).await?;
        Ok(())
    }

    async fn update_resources(
        &self,
        vm_name: &str,
        cpu_count: Option<u32>,
        memory_mb: Option<u64>,
    ) -> VMResult<()> {
        if let Some(cpus) = cpu_count {
            let script = format!(
                "Set-VMProcessor -VMName '{}' -Count {}",
                vm_name.replace("'", "''"),
                cpus
            );
            self.run_ps_ok(&script).await?;
        }

        if let Some(mem) = memory_mb {
            let script = format!(
                "Set-VMMemory -VMName '{}' -StartupBytes {}MB",
                vm_name.replace("'", "''"),
                mem
            );
            self.run_ps_ok(&script).await?;
        }

        Ok(())
    }

    async fn execute_command(
        &self,
        vm_name: &str,
        command: &str,
        timeout_ms: u64,
    ) -> VMResult<CommandResult> {
        self.ps_direct_execute(vm_name, command, timeout_ms).await
    }

    async fn copy_to_vm(
        &self,
        vm_name: &str,
        local_path: &str,
        remote_path: &str,
    ) -> VMResult<()> {
        let script = format!(
            "Copy-VMFile -Name '{}' -SourcePath '{}' -DestinationPath '{}' -FileSource Host -Force",
            vm_name.replace("'", "''"),
            local_path.replace("'", "''"),
            remote_path.replace("'", "''")
        );
        self.run_ps_ok(&script).await?;
        Ok(())
    }

    async fn copy_from_vm(
        &self,
        vm_name: &str,
        remote_path: &str,
        local_path: &str,
    ) -> VMResult<()> {
        // Use PowerShell Direct to read file and write locally
        let script = format!(
            r#"
            $content = Invoke-Command -VMName '{}' -ScriptBlock {{ Get-Content -Path '{}' -Raw -Encoding Byte }}
            [System.IO.File]::WriteAllBytes('{}', $content)
            "#,
            vm_name.replace("'", "''"),
            remote_path.replace("'", "''"),
            local_path.replace("'", "''")
        );
        self.run_ps_ok(&script).await?;
        Ok(())
    }

    async fn screenshot(&self, vm_name: &str) -> VMResult<Vec<u8>> {
        // Hyper-V doesn't have direct screenshot - use RDP capture or guest tools
        warn!("Hyper-V screenshot requires Integration Services in guest");

        // Try using PrintScreen via PowerShell Direct
        let result = self
            .ps_direct_execute(
                vm_name,
                r#"
                Add-Type -AssemblyName System.Windows.Forms
                $bitmap = [System.Windows.Forms.Screen]::PrimaryScreen | ForEach-Object {
                    $bmp = New-Object System.Drawing.Bitmap($_.Bounds.Width, $_.Bounds.Height)
                    $graphics = [System.Drawing.Graphics]::FromImage($bmp)
                    $graphics.CopyFromScreen($_.Bounds.Location, [System.Drawing.Point]::Empty, $_.Bounds.Size)
                    $bmp
                }
                $ms = New-Object System.IO.MemoryStream
                $bitmap.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
                [Convert]::ToBase64String($ms.ToArray())
                "#,
                30000,
            )
            .await?;

        if result.is_success() && !result.stdout.is_empty() {
            use base64::Engine;
            let decoded = base64::engine::general_purpose::STANDARD
                .decode(result.stdout.trim())
                .map_err(|e| VMError::Internal(format!("Base64 decode failed: {}", e)))?;
            return Ok(decoded);
        }

        Err(VMError::Internal("Screenshot capture failed".to_string()))
    }
}
