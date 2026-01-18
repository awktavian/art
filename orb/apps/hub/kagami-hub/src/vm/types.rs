//! VM Type Definitions
//!
//! Core types for virtual machine management across all hypervisors.

use serde::{Deserialize, Serialize};

// ============================================================================
// Operating System Types
// ============================================================================

/// Operating system type running in the VM
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum OSType {
    /// macOS (Parallels, UTM, Lume)
    MacOS,
    /// Microsoft Windows
    Windows,
    /// Linux distributions
    Linux,
    /// Unknown/Other OS
    #[default]
    Unknown,
}

impl std::fmt::Display for OSType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            OSType::MacOS => write!(f, "macos"),
            OSType::Windows => write!(f, "windows"),
            OSType::Linux => write!(f, "linux"),
            OSType::Unknown => write!(f, "unknown"),
        }
    }
}

impl std::str::FromStr for OSType {
    type Err = String;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "macos" | "mac" | "darwin" => Ok(OSType::MacOS),
            "windows" | "win" | "win32" | "win64" => Ok(OSType::Windows),
            "linux" | "ubuntu" | "debian" | "fedora" | "centos" | "arch" => Ok(OSType::Linux),
            _ => Ok(OSType::Unknown),
        }
    }
}

// ============================================================================
// VM State
// ============================================================================

/// Virtual machine state
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum VMState {
    /// VM is stopped (not running)
    #[default]
    Stopped,
    /// VM is starting up
    Starting,
    /// VM is running
    Running,
    /// VM is paused (memory preserved)
    Paused,
    /// VM is suspended (state saved to disk)
    Suspended,
    /// VM is shutting down
    Stopping,
    /// VM is in error state
    Error,
    /// Unknown state
    Unknown,
}

impl std::fmt::Display for VMState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            VMState::Stopped => write!(f, "stopped"),
            VMState::Starting => write!(f, "starting"),
            VMState::Running => write!(f, "running"),
            VMState::Paused => write!(f, "paused"),
            VMState::Suspended => write!(f, "suspended"),
            VMState::Stopping => write!(f, "stopping"),
            VMState::Error => write!(f, "error"),
            VMState::Unknown => write!(f, "unknown"),
        }
    }
}

// ============================================================================
// VM Information
// ============================================================================

/// Information about a virtual machine
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VMInfo {
    /// Unique identifier (hypervisor-specific)
    pub id: String,
    /// Human-readable name
    pub name: String,
    /// Current state
    pub state: VMState,
    /// Operating system type
    pub os_type: OSType,
    /// Hypervisor backend type
    pub hypervisor: String,
    /// CPU count
    #[serde(default)]
    pub cpu_count: u32,
    /// Memory in megabytes
    #[serde(default)]
    pub memory_mb: u64,
    /// Disk size in gigabytes
    #[serde(default)]
    pub disk_gb: u64,
    /// IP address (if known)
    pub ip_address: Option<String>,
    /// Uptime in seconds (if running)
    pub uptime_seconds: Option<u64>,
    /// Available snapshots
    #[serde(default)]
    pub snapshots: Vec<String>,
    /// Error message (if in error state)
    pub error_message: Option<String>,
}

impl VMInfo {
    /// Create a new VMInfo with minimal required fields
    pub fn new(id: impl Into<String>, name: impl Into<String>, hypervisor: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            name: name.into(),
            state: VMState::default(),
            os_type: OSType::default(),
            hypervisor: hypervisor.into(),
            cpu_count: 0,
            memory_mb: 0,
            disk_gb: 0,
            ip_address: None,
            uptime_seconds: None,
            snapshots: Vec::new(),
            error_message: None,
        }
    }

    /// Check if VM is running
    pub fn is_running(&self) -> bool {
        self.state == VMState::Running
    }

    /// Check if VM can be started
    pub fn can_start(&self) -> bool {
        matches!(self.state, VMState::Stopped | VMState::Suspended)
    }

    /// Check if VM can be stopped
    pub fn can_stop(&self) -> bool {
        matches!(self.state, VMState::Running | VMState::Paused)
    }
}

// ============================================================================
// VM Configuration
// ============================================================================

/// Configuration for creating or modifying a VM
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VMConfig {
    /// VM name
    pub name: String,
    /// Operating system type
    #[serde(default)]
    pub os_type: OSType,
    /// Resource configuration
    #[serde(default)]
    pub resources: ResourceConfig,
    /// Network configuration
    #[serde(default)]
    pub network: NetworkConfig,
    /// Base image/template to clone from
    pub base_image: Option<String>,
    /// ISO file for installation
    pub iso_path: Option<String>,
    /// Headless mode (no display)
    #[serde(default)]
    pub headless: bool,
}

impl VMConfig {
    /// Create a new VM config with just a name
    pub fn new(name: impl Into<String>) -> Self {
        Self {
            name: name.into(),
            os_type: OSType::default(),
            resources: ResourceConfig::default(),
            network: NetworkConfig::default(),
            base_image: None,
            iso_path: None,
            headless: false,
        }
    }

    /// Set the OS type
    pub fn with_os(mut self, os_type: OSType) -> Self {
        self.os_type = os_type;
        self
    }

    /// Set CPU count
    pub fn with_cpus(mut self, count: u32) -> Self {
        self.resources.cpu_count = count;
        self
    }

    /// Set memory in MB
    pub fn with_memory_mb(mut self, mb: u64) -> Self {
        self.resources.memory_mb = mb;
        self
    }

    /// Set disk size in GB
    pub fn with_disk_gb(mut self, gb: u64) -> Self {
        self.resources.disk_gb = gb;
        self
    }

    /// Set base image for cloning
    pub fn with_base_image(mut self, image: impl Into<String>) -> Self {
        self.base_image = Some(image.into());
        self
    }

    /// Set headless mode
    pub fn headless(mut self) -> Self {
        self.headless = true;
        self
    }
}

/// Resource allocation configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceConfig {
    /// Number of CPU cores
    #[serde(default = "default_cpu_count")]
    pub cpu_count: u32,
    /// Memory in megabytes
    #[serde(default = "default_memory_mb")]
    pub memory_mb: u64,
    /// Disk size in gigabytes
    #[serde(default = "default_disk_gb")]
    pub disk_gb: u64,
}

fn default_cpu_count() -> u32 {
    2
}
fn default_memory_mb() -> u64 {
    4096
}
fn default_disk_gb() -> u64 {
    64
}

impl Default for ResourceConfig {
    fn default() -> Self {
        Self {
            cpu_count: default_cpu_count(),
            memory_mb: default_memory_mb(),
            disk_gb: default_disk_gb(),
        }
    }
}

/// Network configuration
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct NetworkConfig {
    /// Network mode (nat, bridged, host-only)
    #[serde(default)]
    pub mode: NetworkMode,
    /// Port forwarding rules
    #[serde(default)]
    pub port_forwards: Vec<PortForward>,
    /// Static IP (if applicable)
    pub static_ip: Option<String>,
}

/// Network mode
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "lowercase")]
pub enum NetworkMode {
    /// NAT (shared IP with host)
    #[default]
    NAT,
    /// Bridged (own IP on network)
    Bridged,
    /// Host-only (isolated network)
    HostOnly,
    /// No network
    None,
}

/// Port forwarding rule
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PortForward {
    /// Protocol (tcp, udp)
    #[serde(default = "default_protocol")]
    pub protocol: String,
    /// Host port
    pub host_port: u16,
    /// Guest port
    pub guest_port: u16,
    /// Optional name/description
    pub name: Option<String>,
}

fn default_protocol() -> String {
    "tcp".to_string()
}

impl PortForward {
    /// Create a TCP port forward
    pub fn tcp(host_port: u16, guest_port: u16) -> Self {
        Self {
            protocol: "tcp".to_string(),
            host_port,
            guest_port,
            name: None,
        }
    }

    /// Create a UDP port forward
    pub fn udp(host_port: u16, guest_port: u16) -> Self {
        Self {
            protocol: "udp".to_string(),
            host_port,
            guest_port,
            name: None,
        }
    }
}

// ============================================================================
// Snapshot Information
// ============================================================================

/// Information about a VM snapshot
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SnapshotInfo {
    /// Snapshot identifier
    pub id: String,
    /// Snapshot name
    pub name: String,
    /// Description
    pub description: Option<String>,
    /// Creation timestamp (RFC 3339)
    pub created_at: Option<String>,
    /// Parent snapshot (for tree structure)
    pub parent: Option<String>,
    /// Whether this is the current snapshot
    #[serde(default)]
    pub is_current: bool,
}

impl SnapshotInfo {
    /// Create a new snapshot info
    pub fn new(id: impl Into<String>, name: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            name: name.into(),
            description: None,
            created_at: None,
            parent: None,
            is_current: false,
        }
    }
}

// ============================================================================
// Command Execution Result
// ============================================================================

/// Result of executing a command inside a VM
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommandResult {
    /// Exit code
    pub exit_code: i32,
    /// Standard output
    pub stdout: String,
    /// Standard error
    pub stderr: String,
    /// Execution duration in milliseconds
    #[serde(default)]
    pub duration_ms: u64,
}

impl CommandResult {
    /// Create a successful result
    pub fn success(stdout: impl Into<String>) -> Self {
        Self {
            exit_code: 0,
            stdout: stdout.into(),
            stderr: String::new(),
            duration_ms: 0,
        }
    }

    /// Create a failure result
    pub fn failure(exit_code: i32, stderr: impl Into<String>) -> Self {
        Self {
            exit_code,
            stdout: String::new(),
            stderr: stderr.into(),
            duration_ms: 0,
        }
    }

    /// Check if command succeeded
    pub fn is_success(&self) -> bool {
        self.exit_code == 0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_os_type_parsing() {
        assert_eq!("macos".parse::<OSType>().unwrap(), OSType::MacOS);
        assert_eq!("windows".parse::<OSType>().unwrap(), OSType::Windows);
        assert_eq!("ubuntu".parse::<OSType>().unwrap(), OSType::Linux);
        assert_eq!("unknown".parse::<OSType>().unwrap(), OSType::Unknown);
    }

    #[test]
    fn test_vm_info_states() {
        let mut vm = VMInfo::new("test-id", "Test VM", "parallels");

        vm.state = VMState::Stopped;
        assert!(vm.can_start());
        assert!(!vm.can_stop());

        vm.state = VMState::Running;
        assert!(!vm.can_start());
        assert!(vm.can_stop());
        assert!(vm.is_running());
    }

    #[test]
    fn test_vm_config_builder() {
        let config = VMConfig::new("my-vm")
            .with_os(OSType::Linux)
            .with_cpus(4)
            .with_memory_mb(8192)
            .headless();

        assert_eq!(config.name, "my-vm");
        assert_eq!(config.os_type, OSType::Linux);
        assert_eq!(config.resources.cpu_count, 4);
        assert_eq!(config.resources.memory_mb, 8192);
        assert!(config.headless);
    }

    #[test]
    fn test_port_forward() {
        let tcp = PortForward::tcp(8080, 80);
        assert_eq!(tcp.protocol, "tcp");
        assert_eq!(tcp.host_port, 8080);
        assert_eq!(tcp.guest_port, 80);
    }
}
