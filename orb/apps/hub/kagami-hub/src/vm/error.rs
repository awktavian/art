//! VM Error Types
//!
//! Error definitions for virtual machine operations.

use std::fmt;
use thiserror::Error;

/// Result type for VM operations
pub type VMResult<T> = Result<T, VMError>;

/// Errors that can occur during VM operations
#[derive(Error, Debug)]
pub enum VMError {
    /// VM not found
    #[error("VM not found: {0}")]
    NotFound(String),

    /// VM already exists
    #[error("VM already exists: {0}")]
    AlreadyExists(String),

    /// VM is in wrong state for operation
    #[error("VM '{vm_name}' is in state '{current_state}', cannot {operation}")]
    InvalidState {
        vm_name: String,
        current_state: String,
        operation: String,
    },

    /// Hypervisor not available
    #[error("Hypervisor not available: {0}")]
    HypervisorNotAvailable(String),

    /// Hypervisor command failed
    #[error("Hypervisor command failed: {message}")]
    HypervisorError {
        message: String,
        stderr: Option<String>,
        exit_code: Option<i32>,
    },

    /// Snapshot not found
    #[error("Snapshot not found: {snapshot_name} for VM {vm_name}")]
    SnapshotNotFound { vm_name: String, snapshot_name: String },

    /// Guest agent not running
    #[error("Guest agent not running in VM: {0}")]
    GuestAgentNotRunning(String),

    /// Command execution failed
    #[error("Command execution failed in VM '{vm_name}': {message}")]
    CommandFailed {
        vm_name: String,
        message: String,
        exit_code: i32,
    },

    /// Timeout waiting for operation
    #[error("Timeout waiting for {operation} on VM '{vm_name}'")]
    Timeout { vm_name: String, operation: String },

    /// Network error
    #[error("Network error for VM '{vm_name}': {message}")]
    NetworkError { vm_name: String, message: String },

    /// Permission denied
    #[error("Permission denied: {0}")]
    PermissionDenied(String),

    /// Resource allocation failed
    #[error("Resource allocation failed: {0}")]
    ResourceError(String),

    /// Configuration error
    #[error("Configuration error: {0}")]
    ConfigError(String),

    /// I/O error
    #[error("I/O error: {0}")]
    IoError(#[from] std::io::Error),

    /// JSON parsing error
    #[error("JSON parsing error: {0}")]
    JsonError(#[from] serde_json::Error),

    /// Generic internal error
    #[error("Internal error: {0}")]
    Internal(String),
}

impl VMError {
    /// Create a hypervisor error from command output
    pub fn hypervisor_command_failed(
        message: impl Into<String>,
        stderr: Option<String>,
        exit_code: Option<i32>,
    ) -> Self {
        VMError::HypervisorError {
            message: message.into(),
            stderr,
            exit_code,
        }
    }

    /// Create an invalid state error
    pub fn invalid_state(
        vm_name: impl Into<String>,
        current_state: impl Into<String>,
        operation: impl Into<String>,
    ) -> Self {
        VMError::InvalidState {
            vm_name: vm_name.into(),
            current_state: current_state.into(),
            operation: operation.into(),
        }
    }

    /// Create a command failed error
    pub fn command_failed(
        vm_name: impl Into<String>,
        message: impl Into<String>,
        exit_code: i32,
    ) -> Self {
        VMError::CommandFailed {
            vm_name: vm_name.into(),
            message: message.into(),
            exit_code,
        }
    }

    /// Create a timeout error
    pub fn timeout(vm_name: impl Into<String>, operation: impl Into<String>) -> Self {
        VMError::Timeout {
            vm_name: vm_name.into(),
            operation: operation.into(),
        }
    }

    /// Create a network error
    pub fn network_error(vm_name: impl Into<String>, message: impl Into<String>) -> Self {
        VMError::NetworkError {
            vm_name: vm_name.into(),
            message: message.into(),
        }
    }

    /// Check if this is a retryable error
    pub fn is_retryable(&self) -> bool {
        matches!(
            self,
            VMError::Timeout { .. }
                | VMError::GuestAgentNotRunning(_)
                | VMError::NetworkError { .. }
        )
    }

    /// Get the HTTP status code for this error
    pub fn status_code(&self) -> u16 {
        match self {
            VMError::NotFound(_) => 404,
            VMError::SnapshotNotFound { .. } => 404,
            VMError::AlreadyExists(_) => 409,
            VMError::InvalidState { .. } => 409,
            VMError::PermissionDenied(_) => 403,
            VMError::HypervisorNotAvailable(_) => 503,
            VMError::Timeout { .. } => 504,
            VMError::ConfigError(_) => 400,
            VMError::ResourceError(_) => 507,
            _ => 500,
        }
    }
}

/// Extension trait for converting Results to VMResult
pub trait IntoVMResult<T> {
    /// Convert to VMResult with a custom error message
    fn vm_err(self, msg: impl fmt::Display) -> VMResult<T>;
}

impl<T, E: fmt::Display> IntoVMResult<T> for Result<T, E> {
    fn vm_err(self, msg: impl fmt::Display) -> VMResult<T> {
        self.map_err(|e| VMError::Internal(format!("{}: {}", msg, e)))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_creation() {
        let err = VMError::NotFound("test-vm".to_string());
        assert!(err.to_string().contains("test-vm"));
        assert_eq!(err.status_code(), 404);
    }

    #[test]
    fn test_retryable_errors() {
        let timeout = VMError::timeout("vm", "start");
        assert!(timeout.is_retryable());

        let not_found = VMError::NotFound("vm".to_string());
        assert!(!not_found.is_retryable());
    }

    #[test]
    fn test_hypervisor_error() {
        let err = VMError::hypervisor_command_failed(
            "prlctl failed",
            Some("error output".to_string()),
            Some(1),
        );
        assert!(err.to_string().contains("prlctl failed"));
    }
}
