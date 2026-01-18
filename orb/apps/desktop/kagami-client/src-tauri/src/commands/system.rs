//! System Information Commands
//!
//! CPU, memory, GPU status, and API health.
//! Colony: Forge (e2)

use crate::api_client::{get_api, ApiHealth};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use sysinfo::{CpuRefreshKind, MemoryRefreshKind, RefreshKind, System};
use tracing::debug;

#[cfg(target_os = "windows")]
use std::process::Command;

#[derive(Debug, Serialize, Deserialize)]
pub struct ApiStatus {
    pub running: bool,
    pub health: Option<ApiHealth>,
    pub uptime_formatted: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SystemInfo {
    pub cpu_percent: f32,
    pub memory_gb: f32,
    pub memory_percent: f32,
    pub python_processes: i32,
    pub gpu_status: String,
}

/// Get the current API status.
#[tauri::command]
pub async fn get_api_status() -> Result<ApiStatus, String> {
    let api = get_api();

    match api.health().await {
        Ok(health) => {
            let uptime = health.uptime_ms.map(|ms| {
                let seconds = ms / 1000;
                let minutes = seconds / 60;
                let hours = minutes / 60;
                if hours > 0 {
                    format!("{}h {}m", hours, minutes % 60)
                } else if minutes > 0 {
                    format!("{}m {}s", minutes, seconds % 60)
                } else {
                    format!("{}s", seconds)
                }
            });

            Ok(ApiStatus {
                running: true,
                health: Some(health),
                uptime_formatted: uptime,
            })
        }
        Err(e) => {
            debug!("API not running: {}", e);
            Ok(ApiStatus {
                running: false,
                health: None,
                uptime_formatted: None,
            })
        }
    }
}

/// Get system information.
#[tauri::command]
pub async fn get_system_info() -> Result<SystemInfo, String> {
    // Create a new System instance with specific refresh configuration
    let mut sys = System::new_with_specifics(
        RefreshKind::new()
            .with_cpu(CpuRefreshKind::everything())
            .with_memory(MemoryRefreshKind::everything()),
    );

    // Refresh CPU info twice with a small delay for accurate readings
    // Use tokio::time::sleep instead of std::thread::sleep to avoid blocking
    tokio::time::sleep(Duration::from_millis(100)).await;
    sys.refresh_cpu_usage();

    // Calculate CPU usage (average across all cores)
    let cpu_percent = if sys.cpus().is_empty() {
        0.0
    } else {
        sys.cpus().iter().map(|cpu| cpu.cpu_usage()).sum::<f32>() / sys.cpus().len() as f32
    };

    // Calculate memory usage
    let total_memory = sys.total_memory();
    let used_memory = sys.used_memory();
    let memory_gb = used_memory as f32 / (1024.0 * 1024.0 * 1024.0);
    let memory_percent = if total_memory > 0 {
        (used_memory as f32 / total_memory as f32) * 100.0
    } else {
        0.0
    };

    // Count Python processes
    sys.refresh_processes(sysinfo::ProcessesToUpdate::All, true);
    let python_processes = sys
        .processes()
        .values()
        .filter(|p| {
            let name = p.name().to_string_lossy().to_lowercase();
            name.contains("python") || name.contains("kagami")
        })
        .count() as i32;

    // Detect GPU status
    let gpu_status = detect_gpu_status();

    Ok(SystemInfo {
        cpu_percent,
        memory_gb,
        memory_percent,
        python_processes,
        gpu_status,
    })
}

/// Detect GPU status (MPS on Apple Silicon, CUDA on NVIDIA, etc.)
fn detect_gpu_status() -> String {
    #[cfg(target_os = "macos")]
    {
        // Check if running on Apple Silicon by looking for arm64
        let arch = std::env::consts::ARCH;
        if arch == "aarch64" {
            return "MPS (Apple Silicon)".to_string();
        } else {
            return "CPU Only (Intel Mac)".to_string();
        }
    }

    #[cfg(target_os = "linux")]
    {
        // Check for NVIDIA GPU
        if std::path::Path::new("/dev/nvidia0").exists() {
            return "CUDA (NVIDIA)".to_string();
        } else {
            return "CPU Only".to_string();
        }
    }

    #[cfg(target_os = "windows")]
    {
        // Check for NVIDIA GPU via nvidia-smi
        if let Ok(output) = Command::new("nvidia-smi")
            .arg("--query-gpu=name")
            .arg("--format=csv,noheader")
            .output()
        {
            if output.status.success() {
                let gpu_name = String::from_utf8_lossy(&output.stdout).trim().to_string();
                if !gpu_name.is_empty() {
                    return format!("CUDA ({})", gpu_name);
                }
            }
        }
        return "CPU Only".to_string();
    }

    // Fallback for other platforms (wasm, other BSDs, etc.)
    #[cfg(not(any(target_os = "macos", target_os = "linux", target_os = "windows")))]
    {
        "Unknown".to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_get_system_info_returns_valid_data() {
        let result = get_system_info().await;
        assert!(result.is_ok());
        let info = result.unwrap();
        assert!(!format!("{:?}", info).is_empty());
    }

    #[tokio::test]
    async fn test_get_system_info_cpu_bounds() {
        let result = get_system_info().await;
        assert!(result.is_ok());
        let info = result.unwrap();
        assert!(info.cpu_percent >= 0.0);
        assert!(info.cpu_percent <= 100.0);
    }

    #[tokio::test]
    async fn test_get_system_info_memory_positive() {
        let result = get_system_info().await;
        assert!(result.is_ok());
        let info = result.unwrap();
        assert!(info.memory_gb >= 0.0);
        assert!(info.memory_percent >= 0.0);
        assert!(info.memory_percent <= 100.0);
    }

    #[tokio::test]
    async fn test_get_system_info_gpu_status_not_empty() {
        let result = get_system_info().await;
        assert!(result.is_ok());
        let info = result.unwrap();
        assert!(!info.gpu_status.is_empty());
    }

    #[test]
    fn test_api_status_serialization() {
        let status = ApiStatus {
            running: true,
            health: None,
            uptime_formatted: Some("1h 30m".to_string()),
        };

        let json = serde_json::to_string(&status).unwrap();
        assert!(json.contains("\"running\":true"));
        assert!(json.contains("\"uptime_formatted\":\"1h 30m\""));
    }

    #[test]
    fn test_api_status_deserialization() {
        let json = r#"{"running":false,"health":null,"uptime_formatted":null}"#;
        let status: ApiStatus = serde_json::from_str(json).unwrap();
        assert!(!status.running);
        assert!(status.health.is_none());
        assert!(status.uptime_formatted.is_none());
    }

    #[test]
    fn test_system_info_serialization() {
        let info = SystemInfo {
            cpu_percent: 25.5,
            memory_gb: 8.0,
            memory_percent: 50.0,
            python_processes: 3,
            gpu_status: "MPS (Apple Silicon)".to_string(),
        };

        let json = serde_json::to_string(&info).unwrap();
        assert!(json.contains("\"cpu_percent\":25.5"));
        assert!(json.contains("\"memory_gb\":8.0"));
        assert!(json.contains("\"python_processes\":3"));
    }
}
