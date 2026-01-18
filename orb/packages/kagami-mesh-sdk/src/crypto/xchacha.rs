//! XChaCha20-Poly1305 authenticated encryption.
//!
//! XChaCha20-Poly1305 is an AEAD (Authenticated Encryption with Associated Data)
//! cipher that combines the ChaCha20 stream cipher with the Poly1305 MAC.
//!
//! The "X" variant uses a 192-bit nonce, which is large enough to be randomly
//! generated without significant risk of collision.

use chacha20poly1305::{
    aead::{Aead, KeyInit, Payload},
    XChaCha20Poly1305, XNonce,
};
use rand::rngs::OsRng;
use rand::RngCore;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// The size of an XChaCha20-Poly1305 key in bytes.
pub const KEY_SIZE: usize = 32;

/// The size of an XChaCha20-Poly1305 nonce in bytes.
pub const NONCE_SIZE: usize = 24;

/// The size of the authentication tag in bytes.
pub const TAG_SIZE: usize = 16;

/// Errors that can occur during encryption/decryption.
#[derive(Debug, Error)]
pub enum CipherError {
    #[error("Invalid key length: expected {expected}, got {got}")]
    InvalidKeyLength { expected: usize, got: usize },

    #[error("Invalid nonce length: expected {expected}, got {got}")]
    InvalidNonceLength { expected: usize, got: usize },

    #[error("Encryption failed")]
    EncryptionFailed,

    #[error("Decryption failed: authentication tag mismatch")]
    DecryptionFailed,

    #[error("Invalid ciphertext: too short")]
    CiphertextTooShort,
}

/// A 256-bit secret key for XChaCha20-Poly1305.
#[derive(Clone)]
pub struct SecretKey {
    bytes: [u8; KEY_SIZE],
}

impl SecretKey {
    /// Generate a new random secret key using cryptographically secure RNG.
    pub fn generate() -> Self {
        let mut bytes = [0u8; KEY_SIZE];
        OsRng.fill_bytes(&mut bytes);
        Self { bytes }
    }

    /// Create a secret key from raw bytes.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, CipherError> {
        if bytes.len() != KEY_SIZE {
            return Err(CipherError::InvalidKeyLength {
                expected: KEY_SIZE,
                got: bytes.len(),
            });
        }

        let mut key_bytes = [0u8; KEY_SIZE];
        key_bytes.copy_from_slice(bytes);
        Ok(Self { bytes: key_bytes })
    }

    /// Create a secret key from a hex-encoded string.
    pub fn from_hex(hex_str: &str) -> Result<Self, CipherError> {
        let bytes =
            hex::decode(hex_str).map_err(|_| CipherError::InvalidKeyLength { expected: KEY_SIZE, got: 0 })?;
        Self::from_bytes(&bytes)
    }

    /// Export the key as raw bytes.
    pub fn as_bytes(&self) -> &[u8] {
        &self.bytes
    }

    /// Export the key as a hex-encoded string.
    pub fn to_hex(&self) -> String {
        hex::encode(&self.bytes)
    }
}

impl std::fmt::Debug for SecretKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SecretKey").finish_non_exhaustive()
    }
}

impl Drop for SecretKey {
    fn drop(&mut self) {
        // Zero out the key on drop for security
        self.bytes.fill(0);
    }
}

/// A 192-bit nonce for XChaCha20-Poly1305.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Nonce {
    bytes: [u8; NONCE_SIZE],
}

impl Nonce {
    /// Generate a new random nonce using cryptographically secure RNG.
    ///
    /// SECURITY: Uses OsRng to prevent nonce reuse attacks which would
    /// completely break XChaCha20-Poly1305 security guarantees.
    pub fn generate() -> Self {
        let mut bytes = [0u8; NONCE_SIZE];
        OsRng.fill_bytes(&mut bytes);
        Self { bytes }
    }

    /// Create a nonce from raw bytes.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, CipherError> {
        if bytes.len() != NONCE_SIZE {
            return Err(CipherError::InvalidNonceLength {
                expected: NONCE_SIZE,
                got: bytes.len(),
            });
        }

        let mut nonce_bytes = [0u8; NONCE_SIZE];
        nonce_bytes.copy_from_slice(bytes);
        Ok(Self { bytes: nonce_bytes })
    }

    /// Create a nonce from a hex-encoded string.
    pub fn from_hex(hex_str: &str) -> Result<Self, CipherError> {
        let bytes = hex::decode(hex_str)
            .map_err(|_| CipherError::InvalidNonceLength { expected: NONCE_SIZE, got: 0 })?;
        Self::from_bytes(&bytes)
    }

    /// Export the nonce as raw bytes.
    pub fn as_bytes(&self) -> &[u8] {
        &self.bytes
    }

    /// Export the nonce as a hex-encoded string.
    pub fn to_hex(&self) -> String {
        hex::encode(&self.bytes)
    }
}

/// Encrypt plaintext with XChaCha20-Poly1305.
///
/// Returns the ciphertext with the nonce prepended (nonce || ciphertext || tag).
pub fn encrypt(key: &SecretKey, plaintext: &[u8]) -> Result<Vec<u8>, CipherError> {
    encrypt_with_aad(key, plaintext, &[])
}

/// Encrypt plaintext with associated data (AEAD).
///
/// The associated data is authenticated but not encrypted.
/// Returns the ciphertext with the nonce prepended (nonce || ciphertext || tag).
pub fn encrypt_with_aad(
    key: &SecretKey,
    plaintext: &[u8],
    aad: &[u8],
) -> Result<Vec<u8>, CipherError> {
    let cipher =
        XChaCha20Poly1305::new_from_slice(&key.bytes).map_err(|_| CipherError::EncryptionFailed)?;

    let nonce = Nonce::generate();
    let xnonce = XNonce::from_slice(&nonce.bytes);

    let payload = Payload {
        msg: plaintext,
        aad,
    };

    let ciphertext = cipher
        .encrypt(xnonce, payload)
        .map_err(|_| CipherError::EncryptionFailed)?;

    // Prepend nonce to ciphertext
    let mut result = Vec::with_capacity(NONCE_SIZE + ciphertext.len());
    result.extend_from_slice(&nonce.bytes);
    result.extend_from_slice(&ciphertext);

    Ok(result)
}

/// Decrypt ciphertext with XChaCha20-Poly1305.
///
/// Expects the nonce to be prepended to the ciphertext (nonce || ciphertext || tag).
pub fn decrypt(key: &SecretKey, ciphertext: &[u8]) -> Result<Vec<u8>, CipherError> {
    decrypt_with_aad(key, ciphertext, &[])
}

/// Decrypt ciphertext with associated data (AEAD).
///
/// The associated data must match what was used during encryption.
/// Expects the nonce to be prepended to the ciphertext (nonce || ciphertext || tag).
pub fn decrypt_with_aad(
    key: &SecretKey,
    ciphertext: &[u8],
    aad: &[u8],
) -> Result<Vec<u8>, CipherError> {
    if ciphertext.len() < NONCE_SIZE + TAG_SIZE {
        return Err(CipherError::CiphertextTooShort);
    }

    let cipher =
        XChaCha20Poly1305::new_from_slice(&key.bytes).map_err(|_| CipherError::DecryptionFailed)?;

    let (nonce_bytes, encrypted) = ciphertext.split_at(NONCE_SIZE);
    let xnonce = XNonce::from_slice(nonce_bytes);

    let payload = Payload {
        msg: encrypted,
        aad,
    };

    cipher
        .decrypt(xnonce, payload)
        .map_err(|_| CipherError::DecryptionFailed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_roundtrip() {
        let key = SecretKey::generate();
        let plaintext = b"Hello, Kagami mesh!";

        let ciphertext = encrypt(&key, plaintext).unwrap();
        let decrypted = decrypt(&key, &ciphertext).unwrap();

        assert_eq!(plaintext.as_slice(), decrypted.as_slice());
    }

    #[test]
    fn test_roundtrip_with_aad() {
        let key = SecretKey::generate();
        let plaintext = b"Secret message";
        let aad = b"public metadata";

        let ciphertext = encrypt_with_aad(&key, plaintext, aad).unwrap();
        let decrypted = decrypt_with_aad(&key, &ciphertext, aad).unwrap();

        assert_eq!(plaintext.as_slice(), decrypted.as_slice());
    }

    #[test]
    fn test_wrong_aad_fails() {
        let key = SecretKey::generate();
        let plaintext = b"Secret message";
        let aad = b"public metadata";
        let wrong_aad = b"wrong metadata";

        let ciphertext = encrypt_with_aad(&key, plaintext, aad).unwrap();
        let result = decrypt_with_aad(&key, &ciphertext, wrong_aad);

        assert!(matches!(result, Err(CipherError::DecryptionFailed)));
    }

    #[test]
    fn test_wrong_key_fails() {
        let key1 = SecretKey::generate();
        let key2 = SecretKey::generate();
        let plaintext = b"Hello, Kagami mesh!";

        let ciphertext = encrypt(&key1, plaintext).unwrap();
        let result = decrypt(&key2, &ciphertext);

        assert!(matches!(result, Err(CipherError::DecryptionFailed)));
    }

    #[test]
    fn test_tampered_ciphertext_fails() {
        let key = SecretKey::generate();
        let plaintext = b"Hello, Kagami mesh!";

        let mut ciphertext = encrypt(&key, plaintext).unwrap();
        // Tamper with the ciphertext
        if let Some(byte) = ciphertext.last_mut() {
            *byte ^= 0xFF;
        }

        let result = decrypt(&key, &ciphertext);
        assert!(matches!(result, Err(CipherError::DecryptionFailed)));
    }

    #[test]
    fn test_key_hex_roundtrip() {
        let key = SecretKey::generate();
        let hex_str = key.to_hex();
        let recovered = SecretKey::from_hex(&hex_str).unwrap();

        let plaintext = b"Test";
        let ciphertext = encrypt(&key, plaintext).unwrap();
        let decrypted = decrypt(&recovered, &ciphertext).unwrap();

        assert_eq!(plaintext.as_slice(), decrypted.as_slice());
    }

    #[test]
    fn test_nonce_uniqueness() {
        let nonce1 = Nonce::generate();
        let nonce2 = Nonce::generate();

        // Extremely unlikely to be equal
        assert_ne!(nonce1.as_bytes(), nonce2.as_bytes());
    }

    #[test]
    fn test_empty_plaintext() {
        let key = SecretKey::generate();
        let plaintext = b"";

        let ciphertext = encrypt(&key, plaintext).unwrap();
        let decrypted = decrypt(&key, &ciphertext).unwrap();

        assert!(decrypted.is_empty());
    }

    #[test]
    fn test_large_plaintext() {
        let key = SecretKey::generate();
        let plaintext = vec![0xAB; 1024 * 1024]; // 1 MB

        let ciphertext = encrypt(&key, &plaintext).unwrap();
        let decrypted = decrypt(&key, &ciphertext).unwrap();

        assert_eq!(plaintext, decrypted);
    }
}
