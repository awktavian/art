//! Command Error Types
//!
//! Unified error handling for all Tauri commands.
//! Provides proper error types instead of String.

use thiserror::Error;

/// Command errors with proper types
#[derive(Error, Debug)]
pub enum CommandError {
    #[error("Window not found: {0}")]
    WindowNotFound(String),

    #[error("Invalid action: {0}")]
    InvalidAction(String),

    #[error("Kagami root not found. Set KAGAMI_ROOT environment variable or install to ~/kagami")]
    KagamiRootNotFound,

    #[error("Script not found: {0}")]
    ScriptNotFound(String),

    #[error("Process spawn failed: {0}")]
    ProcessSpawnFailed(String),

    #[error("Process timeout after {0} seconds")]
    ProcessTimeout(u64),

    #[error("API error: {0}")]
    ApiError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("Validation error: {0}")]
    ValidationError(String),
}

impl From<CommandError> for String {
    fn from(err: CommandError) -> String {
        err.to_string()
    }
}

/// Result type for commands
pub type CommandResult<T> = Result<T, CommandError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_command_error_display_window_not_found() {
        let err = CommandError::WindowNotFound("quick-entry".to_string());
        assert_eq!(err.to_string(), "Window not found: quick-entry");
    }

    #[test]
    fn test_command_error_display_invalid_action() {
        let err = CommandError::InvalidAction("bad/action".to_string());
        assert_eq!(err.to_string(), "Invalid action: bad/action");
    }

    #[test]
    fn test_command_error_display_kagami_root_not_found() {
        let err = CommandError::KagamiRootNotFound;
        assert!(err.to_string().contains("KAGAMI_ROOT"));
    }

    #[test]
    fn test_command_error_display_script_not_found() {
        let err = CommandError::ScriptNotFound("/path/to/script.py".to_string());
        assert_eq!(err.to_string(), "Script not found: /path/to/script.py");
    }

    #[test]
    fn test_command_error_display_process_timeout() {
        let err = CommandError::ProcessTimeout(30);
        assert_eq!(err.to_string(), "Process timeout after 30 seconds");
    }

    #[test]
    fn test_command_error_display_api_error() {
        let err = CommandError::ApiError("connection refused".to_string());
        assert_eq!(err.to_string(), "API error: connection refused");
    }

    #[test]
    fn test_command_error_display_validation_error() {
        let err = CommandError::ValidationError("invalid input".to_string());
        assert_eq!(err.to_string(), "Validation error: invalid input");
    }

    #[test]
    fn test_command_error_conversion_to_string() {
        let err = CommandError::WindowNotFound("test".to_string());
        let s: String = err.into();
        assert!(s.contains("Window not found"));
    }
}
