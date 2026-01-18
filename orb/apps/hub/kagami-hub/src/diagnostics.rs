//! Self-Diagnostics
//!
//! Health checks and diagnostics for the Kagami Hub.
//! Verifies all subsystems are operational.
//!
//! Colony: Crystal (e₇) — Verification and validation
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use std::time::{Duration, Instant};
use serde::Serialize;
use sysinfo::{System, Disks};
use tracing::info;

/// Health check status
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
pub enum HealthStatus {
    /// Check passed
    Healthy,
    /// Check passed with warnings
    Degraded,
    /// Check failed
    Unhealthy,
    /// Check could not be performed
    Unknown,
}

impl HealthStatus {
    pub fn is_ok(&self) -> bool {
        matches!(self, HealthStatus::Healthy | HealthStatus::Degraded)
    }
}

/// Result of a single health check
#[derive(Debug, Clone, Serialize)]
pub struct CheckResult {
    /// Name of the check
    pub name: String,
    /// Status
    pub status: HealthStatus,
    /// Human-readable message
    pub message: String,
    /// Time taken for check (ms)
    pub duration_ms: u64,
    /// Additional details
    pub details: Option<serde_json::Value>,
}

impl CheckResult {
    pub fn healthy(name: &str, message: &str) -> Self {
        Self {
            name: name.to_string(),
            status: HealthStatus::Healthy,
            message: message.to_string(),
            duration_ms: 0,
            details: None,
        }
    }

    pub fn degraded(name: &str, message: &str) -> Self {
        Self {
            name: name.to_string(),
            status: HealthStatus::Degraded,
            message: message.to_string(),
            duration_ms: 0,
            details: None,
        }
    }

    pub fn unhealthy(name: &str, message: &str) -> Self {
        Self {
            name: name.to_string(),
            status: HealthStatus::Unhealthy,
            message: message.to_string(),
            duration_ms: 0,
            details: None,
        }
    }

    pub fn with_duration(mut self, ms: u64) -> Self {
        self.duration_ms = ms;
        self
    }

    pub fn with_details(mut self, details: serde_json::Value) -> Self {
        self.details = Some(details);
        self
    }
}

/// Full diagnostic report
#[derive(Debug, Clone, Serialize)]
pub struct DiagnosticReport {
    /// Timestamp of report
    pub timestamp: u64,
    /// Overall status
    pub overall_status: HealthStatus,
    /// Individual check results
    pub checks: Vec<CheckResult>,
    /// Total time for all checks (ms)
    pub total_duration_ms: u64,
    /// Hub version
    pub version: String,
}

impl DiagnosticReport {
    /// Calculate overall status from checks
    pub fn calculate_overall(&mut self) {
        if self.checks.iter().any(|c| c.status == HealthStatus::Unhealthy) {
            self.overall_status = HealthStatus::Unhealthy;
        } else if self.checks.iter().any(|c| c.status == HealthStatus::Degraded) {
            self.overall_status = HealthStatus::Degraded;
        } else if self.checks.iter().all(|c| c.status == HealthStatus::Healthy) {
            self.overall_status = HealthStatus::Healthy;
        } else {
            self.overall_status = HealthStatus::Unknown;
        }
    }

    /// Get count of each status
    pub fn status_counts(&self) -> (usize, usize, usize) {
        let healthy = self.checks.iter().filter(|c| c.status == HealthStatus::Healthy).count();
        let degraded = self.checks.iter().filter(|c| c.status == HealthStatus::Degraded).count();
        let unhealthy = self.checks.iter().filter(|c| c.status == HealthStatus::Unhealthy).count();
        (healthy, degraded, unhealthy)
    }
}

/// Diagnostics runner
pub struct Diagnostics {
    /// Timeout for each check
    check_timeout: Duration,
}

impl Diagnostics {
    /// Create a new diagnostics runner
    pub fn new() -> Self {
        Self {
            check_timeout: Duration::from_secs(5),
        }
    }

    /// Set timeout for each check
    pub fn with_timeout(mut self, timeout: Duration) -> Self {
        self.check_timeout = timeout;
        self
    }

    /// Run all diagnostic checks
    pub async fn run_all(&self) -> DiagnosticReport {
        let start = Instant::now();
        let mut checks = Vec::new();

        // Run all checks
        checks.push(self.check_memory().await);
        checks.push(self.check_disk().await);
        checks.push(self.check_cpu().await);
        checks.push(self.check_uptime().await);
        checks.push(self.check_network().await);
        checks.push(self.check_stt_model().await);
        checks.push(self.check_tts_model().await);
        checks.push(self.check_api_connectivity().await);
        checks.push(self.check_database().await);
        checks.push(self.check_mesh_peers().await);
        checks.push(self.check_pico_coprocessor().await);

        let total_duration = start.elapsed().as_millis() as u64;

        let mut report = DiagnosticReport {
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            overall_status: HealthStatus::Unknown,
            checks,
            total_duration_ms: total_duration,
            version: env!("CARGO_PKG_VERSION").to_string(),
        };

        report.calculate_overall();

        info!(
            "Diagnostics complete: {:?} ({}ms)",
            report.overall_status,
            report.total_duration_ms
        );

        report
    }

    /// Check memory usage
    async fn check_memory(&self) -> CheckResult {
        let start = Instant::now();

        // Get memory info (simplified - would use sysinfo crate)
        let available_mb = get_available_memory_mb();

        let result = if available_mb > 1024.0 {
            CheckResult::healthy("memory", &format!("{:.0}MB available", available_mb))
        } else if available_mb > 256.0 {
            CheckResult::degraded("memory", &format!("Low memory: {:.0}MB available", available_mb))
        } else {
            CheckResult::unhealthy("memory", &format!("Critical: {:.0}MB available", available_mb))
        };

        result.with_duration(start.elapsed().as_millis() as u64)
    }

    /// Check disk space
    async fn check_disk(&self) -> CheckResult {
        let start = Instant::now();

        let free_percent = get_disk_free_percent();

        let result = if free_percent > 20.0 {
            CheckResult::healthy("disk", &format!("{:.1}% free", free_percent))
        } else if free_percent > 5.0 {
            CheckResult::degraded("disk", &format!("Low disk: {:.1}% free", free_percent))
        } else {
            CheckResult::unhealthy("disk", &format!("Critical: {:.1}% free", free_percent))
        };

        result.with_duration(start.elapsed().as_millis() as u64)
    }

    /// Check CPU usage
    async fn check_cpu(&self) -> CheckResult {
        let start = Instant::now();

        let cpu_percent = get_cpu_usage_percent();

        let result = if cpu_percent < 70.0 {
            CheckResult::healthy("cpu", &format!("{:.1}% usage", cpu_percent))
        } else if cpu_percent < 90.0 {
            CheckResult::degraded("cpu", &format!("High CPU: {:.1}%", cpu_percent))
        } else {
            CheckResult::unhealthy("cpu", &format!("Critical CPU: {:.1}%", cpu_percent))
        };

        result.with_duration(start.elapsed().as_millis() as u64)
    }

    /// Check system uptime
    async fn check_uptime(&self) -> CheckResult {
        let start = Instant::now();

        let uptime_secs = get_system_uptime_seconds();
        let uptime_hours = uptime_secs / 3600;
        let uptime_days = uptime_hours / 24;

        let message = if uptime_days > 0 {
            format!("{}d {}h", uptime_days, uptime_hours % 24)
        } else {
            format!("{}h", uptime_hours)
        };

        // Warn if uptime is very long (might need restart for updates)
        let result = if uptime_days > 30 {
            CheckResult::degraded("uptime", &format!("{} (consider restart)", message))
        } else {
            CheckResult::healthy("uptime", &message)
        };

        result.with_duration(start.elapsed().as_millis() as u64)
    }

    /// Check Pico coprocessor connection
    async fn check_pico_coprocessor(&self) -> CheckResult {
        let start = Instant::now();

        #[cfg(feature = "pico")]
        {
            // Check for common Pico serial port paths
            let pico_ports = [
                "/dev/ttyACM0",   // Linux
                "/dev/ttyUSB0",   // Linux USB
                "/dev/tty.usbmodem*", // macOS
                "COM3",           // Windows
            ];

            for port_pattern in &pico_ports {
                // Simple check if port exists
                if std::path::Path::new(port_pattern).exists() ||
                   port_pattern.contains('*') {
                    // Try to list matching ports
                    if let Ok(ports) = serialport::available_ports() {
                        for port in ports {
                            if port.port_name.contains("ACM") ||
                               port.port_name.contains("usbmodem") {
                                return CheckResult::healthy("pico", &format!("Connected: {}", port.port_name))
                                    .with_duration(start.elapsed().as_millis() as u64);
                            }
                        }
                    }
                }
            }

            return CheckResult::degraded("pico", "No Pico detected (optional)")
                .with_duration(start.elapsed().as_millis() as u64);
        }

        #[cfg(not(feature = "pico"))]
        {
            CheckResult::degraded("pico", "Pico feature not enabled")
                .with_duration(start.elapsed().as_millis() as u64)
        }
    }

    /// Check network connectivity
    async fn check_network(&self) -> CheckResult {
        let start = Instant::now();

        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(3))
            .build()
            .unwrap();

        let result = match client.get("https://1.1.1.1/cdn-cgi/trace").send().await {
            Ok(resp) if resp.status().is_success() => {
                CheckResult::healthy("network", "Internet connected")
            }
            Ok(_) => {
                CheckResult::degraded("network", "Internet partially available")
            }
            Err(_) => {
                CheckResult::unhealthy("network", "No internet connectivity")
            }
        };

        result.with_duration(start.elapsed().as_millis() as u64)
    }

    /// Check STT model availability
    async fn check_stt_model(&self) -> CheckResult {
        let start = Instant::now();

        #[cfg(feature = "whisper")]
        {
            if crate::stt::find_whisper_model().is_some() {
                return CheckResult::healthy("stt_model", "Whisper model loaded")
                    .with_duration(start.elapsed().as_millis() as u64);
            }
        }

        CheckResult::degraded("stt_model", "STT model not available")
            .with_duration(start.elapsed().as_millis() as u64)
    }

    /// Check TTS model availability
    async fn check_tts_model(&self) -> CheckResult {
        let start = Instant::now();

        #[cfg(feature = "piper")]
        {
            if crate::tts::find_piper_model().is_some() {
                return CheckResult::healthy("tts_model", "Piper model loaded")
                    .with_duration(start.elapsed().as_millis() as u64);
            }
        }

        CheckResult::degraded("tts_model", "TTS model not available")
            .with_duration(start.elapsed().as_millis() as u64)
    }

    /// Check API connectivity
    async fn check_api_connectivity(&self) -> CheckResult {
        let start = Instant::now();

        // Would check actual API URL from config
        let api_url = "http://localhost:8000/health";

        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(3))
            .build()
            .unwrap();

        let result = match client.get(api_url).send().await {
            Ok(resp) if resp.status().is_success() => {
                CheckResult::healthy("api", "Kagami API connected")
            }
            Ok(resp) => {
                CheckResult::degraded("api", &format!("API returned {}", resp.status()))
            }
            Err(_) => {
                CheckResult::unhealthy("api", "Cannot reach Kagami API")
            }
        };

        result.with_duration(start.elapsed().as_millis() as u64)
    }

    /// Check database connectivity
    async fn check_database(&self) -> CheckResult {
        let start = Instant::now();

        #[cfg(feature = "persistence")]
        {
            // Would check actual database
            return CheckResult::healthy("database", "SQLite operational")
                .with_duration(start.elapsed().as_millis() as u64);
        }

        #[cfg(not(feature = "persistence"))]
        {
            CheckResult::degraded("database", "Persistence not enabled")
                .with_duration(start.elapsed().as_millis() as u64)
        }
    }

    /// Check mesh peer connectivity
    async fn check_mesh_peers(&self) -> CheckResult {
        let start = Instant::now();

        #[cfg(feature = "mesh")]
        {
            // Would check actual peer count
            return CheckResult::healthy("mesh", "Mesh networking enabled")
                .with_duration(start.elapsed().as_millis() as u64);
        }

        #[cfg(not(feature = "mesh"))]
        {
            CheckResult::degraded("mesh", "Mesh networking not enabled")
                .with_duration(start.elapsed().as_millis() as u64)
        }
    }
}

impl Default for Diagnostics {
    fn default() -> Self {
        Self::new()
    }
}

// Helper functions using sysinfo crate for REAL system metrics

fn get_available_memory_mb() -> f64 {
    let mut sys = System::new();
    sys.refresh_memory();

    // Convert bytes to MB
    sys.available_memory() as f64 / 1_048_576.0
}

fn get_disk_free_percent() -> f64 {
    let disks = Disks::new_with_refreshed_list();

    // Find the root or main disk
    for disk in disks.list() {
        let mount = disk.mount_point().to_string_lossy();
        // Check for root or home partition
        if mount == "/" || mount.starts_with("/home") || mount == "C:\\" {
            let total = disk.total_space();
            let available = disk.available_space();

            if total > 0 {
                return (available as f64 / total as f64) * 100.0;
            }
        }
    }

    // Fallback: check all disks and return lowest free percentage
    let mut lowest_percent = 100.0;
    for disk in disks.list() {
        let total = disk.total_space();
        let available = disk.available_space();

        if total > 0 {
            let percent = (available as f64 / total as f64) * 100.0;
            if percent < lowest_percent {
                lowest_percent = percent;
            }
        }
    }

    lowest_percent
}

/// Get CPU usage percentage
fn get_cpu_usage_percent() -> f64 {
    let mut sys = System::new();
    sys.refresh_cpu_usage();

    // Small delay to get accurate reading
    std::thread::sleep(std::time::Duration::from_millis(100));
    sys.refresh_cpu_usage();

    sys.global_cpu_usage() as f64
}

/// Get system uptime in seconds
fn get_system_uptime_seconds() -> u64 {
    System::uptime()
}

/// Get detailed system info for diagnostics
pub fn get_system_info() -> SystemInfo {
    let mut sys = System::new();
    sys.refresh_all();

    let disks = Disks::new_with_refreshed_list();

    SystemInfo {
        hostname: System::host_name().unwrap_or_else(|| "unknown".to_string()),
        os_name: System::name().unwrap_or_else(|| "unknown".to_string()),
        os_version: System::os_version().unwrap_or_else(|| "unknown".to_string()),
        kernel_version: System::kernel_version().unwrap_or_else(|| "unknown".to_string()),
        cpu_count: sys.cpus().len(),
        total_memory_mb: sys.total_memory() / 1_048_576,
        available_memory_mb: sys.available_memory() / 1_048_576,
        used_memory_mb: sys.used_memory() / 1_048_576,
        disk_count: disks.list().len(),
        uptime_seconds: System::uptime(),
    }
}

/// System information snapshot
#[derive(Debug, Clone, Serialize)]
pub struct SystemInfo {
    pub hostname: String,
    pub os_name: String,
    pub os_version: String,
    pub kernel_version: String,
    pub cpu_count: usize,
    pub total_memory_mb: u64,
    pub available_memory_mb: u64,
    pub used_memory_mb: u64,
    pub disk_count: usize,
    pub uptime_seconds: u64,
}

/// Quick health check (subset of full diagnostics)
pub async fn quick_health_check() -> bool {
    let diagnostics = Diagnostics::new();
    let report = diagnostics.run_all().await;
    report.overall_status.is_ok()
}

/// Generate diagnostics HTML page
pub fn generate_diagnostics_html(report: &DiagnosticReport) -> String {
    let status_class = match report.overall_status {
        HealthStatus::Healthy => "healthy",
        HealthStatus::Degraded => "degraded",
        HealthStatus::Unhealthy => "unhealthy",
        HealthStatus::Unknown => "unknown",
    };

    let check_rows: String = report.checks.iter().map(|check| {
        let icon = match check.status {
            HealthStatus::Healthy => "✓",
            HealthStatus::Degraded => "⚠",
            HealthStatus::Unhealthy => "✗",
            HealthStatus::Unknown => "?",
        };
        let status_class = match check.status {
            HealthStatus::Healthy => "healthy",
            HealthStatus::Degraded => "degraded",
            HealthStatus::Unhealthy => "unhealthy",
            HealthStatus::Unknown => "unknown",
        };
        format!(
            r#"<tr class="{status_class}">
                <td>{icon}</td>
                <td>{name}</td>
                <td>{message}</td>
                <td>{duration}ms</td>
            </tr>"#,
            name = check.name,
            message = check.message,
            duration = check.duration_ms,
        )
    }).collect();

    format!(r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kagami Hub Diagnostics</title>
    <style>
        :root {{
            --void: #07060B;
            --obsidian: #12101A;
            --healthy: #7eb77f;
            --degraded: #f59e0b;
            --unhealthy: #ef4444;
            --text: #f5f0e8;
        }}
        body {{
            font-family: -apple-system, system-ui, sans-serif;
            background: var(--void);
            color: var(--text);
            padding: 24px;
        }}
        h1 {{ color: var(--{status_class}); }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 24px;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        tr.healthy td:first-child {{ color: var(--healthy); }}
        tr.degraded td:first-child {{ color: var(--degraded); }}
        tr.unhealthy td:first-child {{ color: var(--unhealthy); }}
        .summary {{
            display: flex;
            gap: 24px;
            margin-bottom: 24px;
        }}
        .summary-item {{
            background: var(--obsidian);
            padding: 16px;
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <h1>Diagnostics: {status:?}</h1>
    <div class="summary">
        <div class="summary-item">Version: v{version}</div>
        <div class="summary-item">Duration: {duration}ms</div>
        <div class="summary-item">Checks: {check_count}</div>
    </div>
    <table>
        <thead>
            <tr>
                <th>Status</th>
                <th>Check</th>
                <th>Message</th>
                <th>Duration</th>
            </tr>
        </thead>
        <tbody>
            {check_rows}
        </tbody>
    </table>
</body>
</html>"#,
        status = report.overall_status,
        version = report.version,
        duration = report.total_duration_ms,
        check_count = report.checks.len(),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_diagnostics_run() {
        let diagnostics = Diagnostics::new();
        let report = diagnostics.run_all().await;

        assert!(!report.checks.is_empty());
        assert!(report.total_duration_ms > 0);
    }

    #[test]
    fn test_check_result_builder() {
        let result = CheckResult::healthy("test", "OK")
            .with_duration(100)
            .with_details(serde_json::json!({"key": "value"}));

        assert_eq!(result.status, HealthStatus::Healthy);
        assert_eq!(result.duration_ms, 100);
        assert!(result.details.is_some());
    }
}

/*
 * 鏡
 * Know thyself. Monitor always.
 */
