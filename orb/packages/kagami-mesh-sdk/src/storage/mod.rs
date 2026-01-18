//! Identity and credential storage abstraction.
//!
//! Provides platform-agnostic interfaces for secure credential storage.
//! iOS implements via Keychain, Android via EncryptedSharedPreferences.
//!
//! The Rust SDK defines the interface; platforms provide implementations.
//!
//! h(x) >= 0. Always.

mod identity_storage;

pub use identity_storage::*;
