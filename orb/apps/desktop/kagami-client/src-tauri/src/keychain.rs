//! Keychain Integration
//!
//! Secure credential storage using the system keychain.
//! On macOS, uses the Keychain Access; on Windows, uses Credential Manager;
//! on Linux, uses Secret Service (libsecret).
//!
//! Colony: Nexus (e₄) — Coordination, secure integration
//!
//! h(x) ≥ 0. Always.

use keyring::Entry;
use thiserror::Error;
use tracing::{debug, error, warn};

/// Service name for all Kagami credentials
pub const SERVICE_NAME: &str = "com.kagami.client";

/// Keychain-specific errors
#[derive(Error, Debug)]
pub enum KeychainError {
    #[error("Credential not found: {0}")]
    NotFound(String),

    #[error("Failed to access keychain: {0}")]
    AccessDenied(String),

    #[error("Keychain operation failed: {0}")]
    OperationFailed(String),

    #[error("Invalid key name: {0}")]
    InvalidKey(String),
}

impl From<keyring::Error> for KeychainError {
    fn from(err: keyring::Error) -> Self {
        match err {
            keyring::Error::NoEntry => KeychainError::NotFound("No entry found".to_string()),
            keyring::Error::Ambiguous(_) => {
                KeychainError::OperationFailed("Ambiguous entry".to_string())
            }
            keyring::Error::TooLong(field, len) => {
                KeychainError::InvalidKey(format!("{} too long: {} bytes", field, len))
            }
            keyring::Error::Invalid(field, reason) => {
                KeychainError::InvalidKey(format!("{}: {}", field, reason))
            }
            keyring::Error::NoStorageAccess(details) => {
                KeychainError::AccessDenied(details.to_string())
            }
            _ => KeychainError::OperationFailed(err.to_string()),
        }
    }
}

/// Result type for keychain operations
pub type KeychainResult<T> = Result<T, KeychainError>;

/// Retrieve a credential from the keychain.
///
/// # Arguments
/// * `key` - The key name for the credential
///
/// # Returns
/// * `Ok(String)` - The credential value
/// * `Err(KeychainError)` - If the credential doesn't exist or access is denied
///
/// # Example
/// ```ignore
/// let token = get_credential("tesla_access_token")?;
/// ```
pub fn get_credential(key: &str) -> KeychainResult<String> {
    validate_key(key)?;

    debug!("Getting credential: {}", key);

    let entry = Entry::new(SERVICE_NAME, key).map_err(KeychainError::from)?;

    match entry.get_password() {
        Ok(password) => {
            debug!("Successfully retrieved credential: {}", key);
            Ok(password)
        }
        Err(keyring::Error::NoEntry) => {
            warn!("Credential not found: {}", key);
            Err(KeychainError::NotFound(key.to_string()))
        }
        Err(e) => {
            error!("Failed to get credential {}: {}", key, e);
            Err(KeychainError::from(e))
        }
    }
}

/// Store a credential in the keychain.
///
/// # Arguments
/// * `key` - The key name for the credential
/// * `value` - The credential value to store
///
/// # Returns
/// * `Ok(())` - If the credential was stored successfully
/// * `Err(KeychainError)` - If storage failed
///
/// # Example
/// ```ignore
/// set_credential("tesla_access_token", "abc123")?;
/// ```
pub fn set_credential(key: &str, value: &str) -> KeychainResult<()> {
    validate_key(key)?;

    debug!("Setting credential: {}", key);

    let entry = Entry::new(SERVICE_NAME, key).map_err(KeychainError::from)?;

    match entry.set_password(value) {
        Ok(()) => {
            debug!("Successfully stored credential: {}", key);
            Ok(())
        }
        Err(e) => {
            error!("Failed to store credential {}: {}", key, e);
            Err(KeychainError::from(e))
        }
    }
}

/// Delete a credential from the keychain.
///
/// # Arguments
/// * `key` - The key name for the credential to delete
///
/// # Returns
/// * `Ok(())` - If the credential was deleted successfully
/// * `Err(KeychainError)` - If deletion failed or credential didn't exist
///
/// # Example
/// ```ignore
/// delete_credential("old_token")?;
/// ```
pub fn delete_credential(key: &str) -> KeychainResult<()> {
    validate_key(key)?;

    debug!("Deleting credential: {}", key);

    let entry = Entry::new(SERVICE_NAME, key).map_err(KeychainError::from)?;

    match entry.delete_credential() {
        Ok(()) => {
            debug!("Successfully deleted credential: {}", key);
            Ok(())
        }
        Err(keyring::Error::NoEntry) => {
            warn!("Credential not found for deletion: {}", key);
            Err(KeychainError::NotFound(key.to_string()))
        }
        Err(e) => {
            error!("Failed to delete credential {}: {}", key, e);
            Err(KeychainError::from(e))
        }
    }
}

/// Check if a credential exists in the keychain.
///
/// # Arguments
/// * `key` - The key name to check
///
/// # Returns
/// * `true` if the credential exists, `false` otherwise
pub fn credential_exists(key: &str) -> bool {
    if validate_key(key).is_err() {
        return false;
    }

    match Entry::new(SERVICE_NAME, key) {
        Ok(entry) => entry.get_password().is_ok(),
        Err(_) => false,
    }
}

/// Validate that a key name is acceptable.
///
/// Keys must:
/// - Not be empty
/// - Not contain null bytes
/// - Be reasonable length (< 256 chars)
fn validate_key(key: &str) -> KeychainResult<()> {
    if key.is_empty() {
        return Err(KeychainError::InvalidKey("Key cannot be empty".to_string()));
    }

    if key.contains('\0') {
        return Err(KeychainError::InvalidKey(
            "Key cannot contain null bytes".to_string(),
        ));
    }

    if key.len() > 255 {
        return Err(KeychainError::InvalidKey(format!(
            "Key too long: {} chars (max 255)",
            key.len()
        )));
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    const TEST_KEY: &str = "kagami_test_credential";
    const TEST_VALUE: &str = "test_secret_value_12345";

    /// Clean up test credential if it exists
    fn cleanup_test_credential() {
        let _ = delete_credential(TEST_KEY);
    }

    #[test]
    fn test_validate_key_empty() {
        let result = validate_key("");
        assert!(matches!(result, Err(KeychainError::InvalidKey(_))));
    }

    #[test]
    fn test_validate_key_null_byte() {
        let result = validate_key("key\0with\0nulls");
        assert!(matches!(result, Err(KeychainError::InvalidKey(_))));
    }

    #[test]
    fn test_validate_key_too_long() {
        let long_key = "a".repeat(300);
        let result = validate_key(&long_key);
        assert!(matches!(result, Err(KeychainError::InvalidKey(_))));
    }

    #[test]
    fn test_validate_key_valid() {
        let result = validate_key("valid_key_name");
        assert!(result.is_ok());
    }

    #[test]
    fn test_service_name() {
        assert_eq!(SERVICE_NAME, "com.kagami.client");
    }

    #[test]
    fn test_keychain_error_display() {
        let err = KeychainError::NotFound("test_key".to_string());
        assert!(err.to_string().contains("not found"));

        let err = KeychainError::AccessDenied("permission denied".to_string());
        assert!(err.to_string().contains("access keychain"));

        let err = KeychainError::InvalidKey("bad key".to_string());
        assert!(err.to_string().contains("Invalid key"));
    }

    // Integration tests that actually use the keychain
    // These tests require keychain access and modify system state
    #[test]
    #[ignore = "Requires keychain access - run with --ignored"]
    fn test_set_get_delete_credential() {
        cleanup_test_credential();

        // Set credential
        let set_result = set_credential(TEST_KEY, TEST_VALUE);
        assert!(set_result.is_ok(), "Failed to set credential: {:?}", set_result);

        // Get credential
        let get_result = get_credential(TEST_KEY);
        assert!(get_result.is_ok(), "Failed to get credential: {:?}", get_result);
        assert_eq!(get_result.unwrap(), TEST_VALUE);

        // Check exists
        assert!(credential_exists(TEST_KEY));

        // Delete credential
        let delete_result = delete_credential(TEST_KEY);
        assert!(
            delete_result.is_ok(),
            "Failed to delete credential: {:?}",
            delete_result
        );

        // Verify deleted
        assert!(!credential_exists(TEST_KEY));
    }

    #[test]
    #[ignore = "Requires keychain access - run with --ignored"]
    fn test_get_nonexistent_credential() {
        let result = get_credential("nonexistent_key_xyz_12345");
        assert!(matches!(result, Err(KeychainError::NotFound(_))));
    }

    #[test]
    #[ignore = "Requires keychain access - run with --ignored"]
    fn test_delete_nonexistent_credential() {
        let result = delete_credential("nonexistent_key_xyz_12345");
        assert!(matches!(result, Err(KeychainError::NotFound(_))));
    }

    #[test]
    #[ignore = "Requires keychain access - run with --ignored"]
    fn test_update_existing_credential() {
        cleanup_test_credential();

        // Set initial value
        set_credential(TEST_KEY, "initial_value").unwrap();

        // Update to new value
        set_credential(TEST_KEY, "updated_value").unwrap();

        // Verify updated
        let result = get_credential(TEST_KEY).unwrap();
        assert_eq!(result, "updated_value");

        cleanup_test_credential();
    }

    #[test]
    fn test_credential_exists_with_invalid_key() {
        assert!(!credential_exists(""));
        assert!(!credential_exists("key\0with\0null"));
    }
}
