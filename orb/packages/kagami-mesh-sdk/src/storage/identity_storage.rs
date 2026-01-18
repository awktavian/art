//! Identity storage abstraction for secure credential management.
//!
//! Platforms implement this trait using:
//! - iOS: Keychain Services
//! - Android: EncryptedSharedPreferences / Keystore
//! - Desktop: system keyring or secure file storage
//!
//! h(x) >= 0. Always.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors that can occur during identity storage operations.
#[derive(Debug, Error, Clone, Serialize, Deserialize)]
pub enum IdentityStorageError {
    #[error("Key not found: {key}")]
    KeyNotFound { key: String },

    #[error("Storage unavailable: {reason}")]
    StorageUnavailable { reason: String },

    #[error("Access denied: {reason}")]
    AccessDenied { reason: String },

    #[error("Serialization failed: {reason}")]
    SerializationFailed { reason: String },

    #[error("Corruption detected: {reason}")]
    CorruptionDetected { reason: String },

    #[error("Platform error: {code} - {message}")]
    PlatformError { code: i32, message: String },
}

/// Storage accessibility requirements.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum StorageAccessibility {
    /// Available only when device is unlocked.
    WhenUnlocked,
    /// Available after first unlock until device restart.
    AfterFirstUnlock,
    /// Always available (not recommended for sensitive data).
    Always,
    /// Available when unlocked, does not migrate to new device.
    WhenUnlockedThisDeviceOnly,
    /// Available after first unlock, does not migrate.
    AfterFirstUnlockThisDeviceOnly,
}

impl Default for StorageAccessibility {
    fn default() -> Self {
        Self::AfterFirstUnlock
    }
}

/// Stored identity data.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoredIdentity {
    /// Ed25519 identity as base64-encoded secret key.
    pub ed25519_identity: String,
    /// X25519 secret key as hex for key exchange.
    pub x25519_secret_key: Option<String>,
    /// X25519 public key as hex.
    pub x25519_public_key: Option<String>,
    /// Peer ID (derived from Ed25519 public key).
    pub peer_id: String,
    /// Human-readable device name.
    pub device_name: Option<String>,
    /// Creation timestamp (Unix epoch seconds).
    pub created_at: i64,
    /// Last used timestamp.
    pub last_used_at: Option<i64>,
}

/// Storage key constants for consistent naming across platforms.
pub mod keys {
    /// Primary Ed25519 identity.
    pub const MESH_IDENTITY: &str = "kagami.mesh.identity";
    /// X25519 keypair for encryption.
    pub const X25519_KEYPAIR: &str = "kagami.mesh.x25519";
    /// Hub shared secret for local communication.
    pub const HUB_SHARED_SECRET: &str = "kagami.mesh.hub_secret";
    /// Cloud API authentication token.
    pub const CLOUD_AUTH_TOKEN: &str = "kagami.cloud.auth_token";
    /// Device registration info.
    pub const DEVICE_REGISTRATION: &str = "kagami.device.registration";
}

/// Configuration for identity storage.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IdentityStorageConfig {
    /// Service name for keychain/keystore (iOS) or file prefix (Android).
    pub service_name: String,
    /// Accessibility level for stored credentials.
    pub accessibility: StorageAccessibility,
    /// Whether to sync to iCloud Keychain (iOS only).
    pub sync_to_cloud: bool,
    /// Access group for keychain sharing (iOS only).
    pub access_group: Option<String>,
}

impl Default for IdentityStorageConfig {
    fn default() -> Self {
        Self {
            service_name: "com.kagami.mesh".to_string(),
            accessibility: StorageAccessibility::AfterFirstUnlock,
            sync_to_cloud: false,
            access_group: None,
        }
    }
}

/// Result of an identity load operation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum IdentityLoadResult {
    /// Identity loaded successfully.
    Loaded(StoredIdentity),
    /// No identity exists yet.
    NotFound,
    /// Identity exists but is inaccessible (device locked, etc).
    Inaccessible { reason: String },
    /// Identity data is corrupted.
    Corrupted { reason: String },
}

/// Trait for identity storage implementations.
///
/// Platforms implement this trait to provide secure credential storage.
/// The Rust SDK uses this abstraction rather than platform-specific APIs.
pub trait IdentityStorage: Send + Sync {
    /// Store an identity securely.
    fn store_identity(&self, identity: &StoredIdentity) -> Result<(), IdentityStorageError>;

    /// Load the stored identity.
    fn load_identity(&self) -> IdentityLoadResult;

    /// Delete the stored identity.
    fn delete_identity(&self) -> Result<(), IdentityStorageError>;

    /// Check if an identity exists.
    fn identity_exists(&self) -> bool;

    /// Store a raw string value.
    fn store_string(&self, key: &str, value: &str) -> Result<(), IdentityStorageError>;

    /// Load a raw string value.
    fn load_string(&self, key: &str) -> Result<Option<String>, IdentityStorageError>;

    /// Delete a specific key.
    fn delete_key(&self, key: &str) -> Result<(), IdentityStorageError>;

    /// Store binary data.
    fn store_data(&self, key: &str, data: &[u8]) -> Result<(), IdentityStorageError>;

    /// Load binary data.
    fn load_data(&self, key: &str) -> Result<Option<Vec<u8>>, IdentityStorageError>;

    /// Clear all stored data for this service.
    fn clear_all(&self) -> Result<(), IdentityStorageError>;
}

/// In-memory storage for testing.
#[derive(Default)]
pub struct InMemoryIdentityStorage {
    data: std::sync::RwLock<std::collections::HashMap<String, Vec<u8>>>,
}

impl InMemoryIdentityStorage {
    pub fn new() -> Self {
        Self::default()
    }
}

impl IdentityStorage for InMemoryIdentityStorage {
    fn store_identity(&self, identity: &StoredIdentity) -> Result<(), IdentityStorageError> {
        let json = serde_json::to_vec(identity).map_err(|e| IdentityStorageError::SerializationFailed {
            reason: e.to_string(),
        })?;
        self.store_data(keys::MESH_IDENTITY, &json)
    }

    fn load_identity(&self) -> IdentityLoadResult {
        match self.load_data(keys::MESH_IDENTITY) {
            Ok(Some(data)) => {
                match serde_json::from_slice(&data) {
                    Ok(identity) => IdentityLoadResult::Loaded(identity),
                    Err(e) => IdentityLoadResult::Corrupted { reason: e.to_string() },
                }
            }
            Ok(None) => IdentityLoadResult::NotFound,
            Err(e) => IdentityLoadResult::Inaccessible { reason: e.to_string() },
        }
    }

    fn delete_identity(&self) -> Result<(), IdentityStorageError> {
        self.delete_key(keys::MESH_IDENTITY)
    }

    fn identity_exists(&self) -> bool {
        self.data.read().unwrap().contains_key(keys::MESH_IDENTITY)
    }

    fn store_string(&self, key: &str, value: &str) -> Result<(), IdentityStorageError> {
        self.store_data(key, value.as_bytes())
    }

    fn load_string(&self, key: &str) -> Result<Option<String>, IdentityStorageError> {
        match self.load_data(key)? {
            Some(data) => {
                String::from_utf8(data)
                    .map(Some)
                    .map_err(|e| IdentityStorageError::CorruptionDetected {
                        reason: e.to_string(),
                    })
            }
            None => Ok(None),
        }
    }

    fn delete_key(&self, key: &str) -> Result<(), IdentityStorageError> {
        self.data.write().unwrap().remove(key);
        Ok(())
    }

    fn store_data(&self, key: &str, data: &[u8]) -> Result<(), IdentityStorageError> {
        self.data.write().unwrap().insert(key.to_string(), data.to_vec());
        Ok(())
    }

    fn load_data(&self, key: &str) -> Result<Option<Vec<u8>>, IdentityStorageError> {
        Ok(self.data.read().unwrap().get(key).cloned())
    }

    fn clear_all(&self) -> Result<(), IdentityStorageError> {
        self.data.write().unwrap().clear();
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_identity() -> StoredIdentity {
        StoredIdentity {
            ed25519_identity: "test_identity_base64".to_string(),
            x25519_secret_key: Some("test_x25519_secret".to_string()),
            x25519_public_key: Some("test_x25519_public".to_string()),
            peer_id: "test_peer_id".to_string(),
            device_name: Some("Test Device".to_string()),
            created_at: 1704067200, // 2024-01-01
            last_used_at: None,
        }
    }

    #[test]
    fn test_in_memory_storage_identity() {
        let storage = InMemoryIdentityStorage::new();

        // Initially no identity
        assert!(!storage.identity_exists());
        assert!(matches!(storage.load_identity(), IdentityLoadResult::NotFound));

        // Store identity
        let identity = create_test_identity();
        storage.store_identity(&identity).unwrap();

        // Now exists
        assert!(storage.identity_exists());

        // Load it back
        if let IdentityLoadResult::Loaded(loaded) = storage.load_identity() {
            assert_eq!(loaded.peer_id, identity.peer_id);
            assert_eq!(loaded.device_name, identity.device_name);
        } else {
            panic!("Expected Loaded result");
        }

        // Delete
        storage.delete_identity().unwrap();
        assert!(!storage.identity_exists());
    }

    #[test]
    fn test_in_memory_storage_strings() {
        let storage = InMemoryIdentityStorage::new();

        // Store string
        storage.store_string("test_key", "test_value").unwrap();

        // Load string
        let loaded = storage.load_string("test_key").unwrap();
        assert_eq!(loaded, Some("test_value".to_string()));

        // Non-existent key
        let missing = storage.load_string("missing").unwrap();
        assert!(missing.is_none());
    }

    #[test]
    fn test_clear_all() {
        let storage = InMemoryIdentityStorage::new();

        storage.store_string("key1", "value1").unwrap();
        storage.store_string("key2", "value2").unwrap();
        storage.store_identity(&create_test_identity()).unwrap();

        storage.clear_all().unwrap();

        assert!(storage.load_string("key1").unwrap().is_none());
        assert!(storage.load_string("key2").unwrap().is_none());
        assert!(!storage.identity_exists());
    }

    #[test]
    fn test_storage_config_defaults() {
        let config = IdentityStorageConfig::default();
        assert_eq!(config.service_name, "com.kagami.mesh");
        assert!(!config.sync_to_cloud);
        assert_eq!(config.accessibility, StorageAccessibility::AfterFirstUnlock);
    }
}
