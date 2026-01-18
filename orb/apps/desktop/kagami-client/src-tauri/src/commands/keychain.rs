//! Keychain Commands
//!
//! Tauri commands for secure credential storage via the system keychain.
//! Provides a frontend-accessible API for credential management.
//!
//! Colony: Forge (e2) — Implementation, construction
//!
//! h(x) ≥ 0. Always.

use crate::keychain as keychain_core;
use crate::keychain::KeychainError;
use serde::{Deserialize, Serialize};
use tracing::{debug, info, warn};

/// Response for keychain operations
#[derive(Debug, Serialize, Deserialize)]
pub struct KeychainResponse {
    /// Whether the operation succeeded
    pub success: bool,
    /// Optional value (for get operations)
    pub value: Option<String>,
    /// Error message if operation failed
    pub error: Option<String>,
}

impl KeychainResponse {
    /// Create a successful response with a value
    fn success_with_value(value: String) -> Self {
        Self {
            success: true,
            value: Some(value),
            error: None,
        }
    }

    /// Create a successful response without a value
    fn success() -> Self {
        Self {
            success: true,
            value: None,
            error: None,
        }
    }

    /// Create an error response
    fn error(message: String) -> Self {
        Self {
            success: false,
            value: None,
            error: Some(message),
        }
    }
}

/// Retrieve a credential from the system keychain.
///
/// # Arguments
/// * `key` - The key name for the credential
///
/// # Returns
/// A `KeychainResponse` with the credential value or an error message.
#[tauri::command]
pub async fn keychain_get(key: String) -> Result<KeychainResponse, String> {
    debug!("Tauri command: keychain_get({})", key);

    match keychain_core::get_credential(&key) {
        Ok(value) => {
            info!("Successfully retrieved credential: {}", key);
            Ok(KeychainResponse::success_with_value(value))
        }
        Err(KeychainError::NotFound(_)) => {
            warn!("Credential not found: {}", key);
            Ok(KeychainResponse::error(format!(
                "Credential '{}' not found",
                key
            )))
        }
        Err(e @ KeychainError::AccessDenied(_))
        | Err(e @ KeychainError::OperationFailed(_))
        | Err(e @ KeychainError::InvalidKey(_)) => {
            warn!("Failed to get credential {}: {}", key, e);
            Ok(KeychainResponse::error(e.to_string()))
        }
    }
}

/// Store a credential in the system keychain.
///
/// # Arguments
/// * `key` - The key name for the credential
/// * `value` - The credential value to store
///
/// # Returns
/// A `KeychainResponse` indicating success or failure.
#[tauri::command]
pub async fn keychain_set(key: String, value: String) -> Result<KeychainResponse, String> {
    debug!("Tauri command: keychain_set({})", key);

    match keychain_core::set_credential(&key, &value) {
        Ok(()) => {
            info!("Successfully stored credential: {}", key);
            Ok(KeychainResponse::success())
        }
        Err(e @ KeychainError::NotFound(_))
        | Err(e @ KeychainError::AccessDenied(_))
        | Err(e @ KeychainError::OperationFailed(_))
        | Err(e @ KeychainError::InvalidKey(_)) => {
            warn!("Failed to set credential {}: {}", key, e);
            Ok(KeychainResponse::error(e.to_string()))
        }
    }
}

/// Delete a credential from the system keychain.
///
/// # Arguments
/// * `key` - The key name for the credential to delete
///
/// # Returns
/// A `KeychainResponse` indicating success or failure.
#[tauri::command]
pub async fn keychain_delete(key: String) -> Result<KeychainResponse, String> {
    debug!("Tauri command: keychain_delete({})", key);

    match keychain_core::delete_credential(&key) {
        Ok(()) => {
            info!("Successfully deleted credential: {}", key);
            Ok(KeychainResponse::success())
        }
        Err(KeychainError::NotFound(_)) => {
            warn!("Credential not found for deletion: {}", key);
            Ok(KeychainResponse::error(format!(
                "Credential '{}' not found",
                key
            )))
        }
        Err(e @ KeychainError::AccessDenied(_))
        | Err(e @ KeychainError::OperationFailed(_))
        | Err(e @ KeychainError::InvalidKey(_)) => {
            warn!("Failed to delete credential {}: {}", key, e);
            Ok(KeychainResponse::error(e.to_string()))
        }
    }
}

/// Check if a credential exists in the system keychain.
///
/// # Arguments
/// * `key` - The key name to check
///
/// # Returns
/// A boolean indicating whether the credential exists.
#[tauri::command]
pub async fn keychain_exists(key: String) -> Result<bool, String> {
    debug!("Tauri command: keychain_exists({})", key);
    Ok(keychain_core::credential_exists(&key))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_keychain_response_success_with_value() {
        let response = KeychainResponse::success_with_value("secret".to_string());
        assert!(response.success);
        assert_eq!(response.value, Some("secret".to_string()));
        assert!(response.error.is_none());
    }

    #[test]
    fn test_keychain_response_success() {
        let response = KeychainResponse::success();
        assert!(response.success);
        assert!(response.value.is_none());
        assert!(response.error.is_none());
    }

    #[test]
    fn test_keychain_response_error() {
        let response = KeychainResponse::error("Something went wrong".to_string());
        assert!(!response.success);
        assert!(response.value.is_none());
        assert_eq!(response.error, Some("Something went wrong".to_string()));
    }

    #[test]
    fn test_keychain_response_serialization() {
        let response = KeychainResponse::success_with_value("test".to_string());
        let json = serde_json::to_string(&response).unwrap();
        assert!(json.contains("\"success\":true"));
        assert!(json.contains("\"value\":\"test\""));
    }

    #[test]
    fn test_keychain_response_deserialization() {
        let json = r#"{"success":false,"value":null,"error":"test error"}"#;
        let response: KeychainResponse = serde_json::from_str(json).unwrap();
        assert!(!response.success);
        assert!(response.value.is_none());
        assert_eq!(response.error, Some("test error".to_string()));
    }
}
