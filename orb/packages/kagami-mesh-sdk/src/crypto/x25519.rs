//! X25519 Diffie-Hellman key exchange.
//!
//! X25519 is an elliptic curve Diffie-Hellman (ECDH) function using Curve25519.
//! It allows two parties to establish a shared secret over an insecure channel.

use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use thiserror::Error;
use x25519_dalek::{
    EphemeralSecret as DalekEphemeralSecret, PublicKey as DalekPublicKey,
    StaticSecret as DalekStaticSecret,
};

/// The size of an X25519 public key in bytes.
pub const PUBLIC_KEY_SIZE: usize = 32;

/// The size of an X25519 secret key in bytes.
pub const SECRET_KEY_SIZE: usize = 32;

/// The size of the shared secret in bytes.
pub const SHARED_SECRET_SIZE: usize = 32;

/// Errors that can occur during X25519 operations.
#[derive(Debug, Error)]
pub enum X25519Error {
    #[error("Invalid public key length: expected {expected}, got {got}")]
    InvalidPublicKeyLength { expected: usize, got: usize },

    #[error("Invalid secret key length: expected {expected}, got {got}")]
    InvalidSecretKeyLength { expected: usize, got: usize },

    #[error("Invalid hex string")]
    InvalidHex,

    #[error("Key derivation failed")]
    KeyDerivationFailed,
}

/// An X25519 public key.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct X25519PublicKey {
    bytes: [u8; PUBLIC_KEY_SIZE],
}

impl X25519PublicKey {
    /// Create a public key from raw bytes.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, X25519Error> {
        if bytes.len() != PUBLIC_KEY_SIZE {
            return Err(X25519Error::InvalidPublicKeyLength {
                expected: PUBLIC_KEY_SIZE,
                got: bytes.len(),
            });
        }

        let mut key_bytes = [0u8; PUBLIC_KEY_SIZE];
        key_bytes.copy_from_slice(bytes);
        Ok(Self { bytes: key_bytes })
    }

    /// Create a public key from a hex-encoded string.
    pub fn from_hex(hex_str: &str) -> Result<Self, X25519Error> {
        let bytes = hex::decode(hex_str).map_err(|_| X25519Error::InvalidHex)?;
        Self::from_bytes(&bytes)
    }

    /// Export the public key as raw bytes.
    pub fn as_bytes(&self) -> &[u8; PUBLIC_KEY_SIZE] {
        &self.bytes
    }

    /// Export the public key as a hex-encoded string.
    pub fn to_hex(&self) -> String {
        hex::encode(self.bytes)
    }

    /// Convert to the internal dalek type.
    fn to_dalek(&self) -> DalekPublicKey {
        DalekPublicKey::from(self.bytes)
    }
}

/// A static (long-term) X25519 secret key.
///
/// Use this for keys that are stored and reused across sessions.
///
/// SECURITY: The inner DalekStaticSecret is automatically zeroed on drop
/// via x25519-dalek's zeroize feature, ensuring h(x) >= 0 for secret key material.
#[derive(Clone)]
pub struct StaticSecret {
    inner: DalekStaticSecret,
}

impl StaticSecret {
    /// Generate a new random static secret.
    pub fn generate() -> Self {
        Self {
            inner: DalekStaticSecret::random_from_rng(OsRng),
        }
    }

    /// Create a static secret from raw bytes.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, X25519Error> {
        if bytes.len() != SECRET_KEY_SIZE {
            return Err(X25519Error::InvalidSecretKeyLength {
                expected: SECRET_KEY_SIZE,
                got: bytes.len(),
            });
        }

        let mut key_bytes = [0u8; SECRET_KEY_SIZE];
        key_bytes.copy_from_slice(bytes);
        Ok(Self {
            inner: DalekStaticSecret::from(key_bytes),
        })
    }

    /// Create a static secret from a hex-encoded string.
    pub fn from_hex(hex_str: &str) -> Result<Self, X25519Error> {
        let bytes = hex::decode(hex_str).map_err(|_| X25519Error::InvalidHex)?;
        Self::from_bytes(&bytes)
    }

    /// Export the secret key as raw bytes.
    pub fn to_bytes(&self) -> [u8; SECRET_KEY_SIZE] {
        self.inner.to_bytes()
    }

    /// Export the secret key as a hex-encoded string.
    pub fn to_hex(&self) -> String {
        hex::encode(self.to_bytes())
    }

    /// Get the corresponding public key.
    pub fn public_key(&self) -> X25519PublicKey {
        let pk = DalekPublicKey::from(&self.inner);
        X25519PublicKey {
            bytes: pk.to_bytes(),
        }
    }

    /// Perform Diffie-Hellman key exchange with a peer's public key.
    pub fn diffie_hellman(&self, peer_public: &X25519PublicKey) -> SharedSecret {
        let shared = self.inner.diffie_hellman(&peer_public.to_dalek());
        SharedSecret {
            bytes: shared.to_bytes(),
        }
    }
}

impl std::fmt::Debug for StaticSecret {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("StaticSecret")
            .field("public_key", &self.public_key().to_hex())
            .finish()
    }
}

/// An ephemeral (single-use) X25519 secret key.
///
/// Use this for keys that should only be used once (e.g., for forward secrecy).
/// Note: This type cannot be cloned or serialized by design.
pub struct EphemeralSecret {
    inner: DalekEphemeralSecret,
    public_key: X25519PublicKey,
}

impl EphemeralSecret {
    /// Generate a new random ephemeral secret.
    pub fn generate() -> Self {
        let inner = DalekEphemeralSecret::random_from_rng(OsRng);
        let pk = DalekPublicKey::from(&inner);
        Self {
            inner,
            public_key: X25519PublicKey {
                bytes: pk.to_bytes(),
            },
        }
    }

    /// Get the corresponding public key.
    pub fn public_key(&self) -> &X25519PublicKey {
        &self.public_key
    }

    /// Perform Diffie-Hellman key exchange with a peer's public key.
    ///
    /// This consumes the ephemeral secret (by design - it should only be used once).
    pub fn diffie_hellman(self, peer_public: &X25519PublicKey) -> SharedSecret {
        let shared = self.inner.diffie_hellman(&peer_public.to_dalek());
        SharedSecret {
            bytes: shared.to_bytes(),
        }
    }
}

impl std::fmt::Debug for EphemeralSecret {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("EphemeralSecret")
            .field("public_key", &self.public_key.to_hex())
            .finish()
    }
}

/// A shared secret derived from X25519 key exchange.
///
/// This should be used as input to a KDF (Key Derivation Function) to derive
/// symmetric encryption keys, not used directly as an encryption key.
#[derive(Clone)]
pub struct SharedSecret {
    bytes: [u8; SHARED_SECRET_SIZE],
}

impl SharedSecret {
    /// Get the raw shared secret bytes.
    ///
    /// WARNING: Use a KDF to derive keys from this, don't use directly.
    pub fn as_bytes(&self) -> &[u8; SHARED_SECRET_SIZE] {
        &self.bytes
    }

    /// Derive an encryption key from this shared secret.
    ///
    /// This uses HKDF with SHA-256 to derive a key of the requested length.
    /// The info parameter can be used for domain separation.
    ///
    /// SECURITY: Uses a fixed salt per RFC 5869 for proper Extract phase.
    /// The salt provides domain separation and randomness expansion.
    pub fn derive_key(&self, info: &[u8], output_length: usize) -> Vec<u8> {
        use sha2::Sha256;
        use hkdf::Hkdf;

        // RFC 5869: Use salt for HKDF-Extract domain separation
        const HKDF_SALT: &[u8] = b"kagami-mesh-sdk-v1";
        let hk = Hkdf::<Sha256>::new(Some(HKDF_SALT), &self.bytes);
        let mut output = vec![0u8; output_length];
        hk.expand(info, &mut output)
            .expect("output length should be valid for HKDF");
        output
    }

    /// Convert to an XChaCha20-Poly1305 secret key.
    pub fn to_cipher_key(&self) -> super::SecretKey {
        let key_bytes = self.derive_key(b"kagami-mesh-xchacha", 32);
        super::SecretKey::from_bytes(&key_bytes).expect("derived key should be 32 bytes")
    }
}

impl std::fmt::Debug for SharedSecret {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SharedSecret").finish_non_exhaustive()
    }
}

impl Drop for SharedSecret {
    fn drop(&mut self) {
        // Zero out the secret on drop
        self.bytes.fill(0);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_static_key_generation() {
        let secret = StaticSecret::generate();
        let public = secret.public_key();

        assert_eq!(public.as_bytes().len(), PUBLIC_KEY_SIZE);
    }

    #[test]
    fn test_ephemeral_key_generation() {
        let secret = EphemeralSecret::generate();
        let public = secret.public_key();

        assert_eq!(public.as_bytes().len(), PUBLIC_KEY_SIZE);
    }

    #[test]
    fn test_diffie_hellman_static() {
        let alice = StaticSecret::generate();
        let bob = StaticSecret::generate();

        let alice_public = alice.public_key();
        let bob_public = bob.public_key();

        let alice_shared = alice.diffie_hellman(&bob_public);
        let bob_shared = bob.diffie_hellman(&alice_public);

        assert_eq!(alice_shared.as_bytes(), bob_shared.as_bytes());
    }

    #[test]
    fn test_diffie_hellman_ephemeral() {
        let alice = EphemeralSecret::generate();
        let bob = EphemeralSecret::generate();

        let alice_public = alice.public_key().clone();
        let bob_public = bob.public_key().clone();

        let alice_shared = alice.diffie_hellman(&bob_public);
        let bob_shared = bob.diffie_hellman(&alice_public);

        assert_eq!(alice_shared.as_bytes(), bob_shared.as_bytes());
    }

    #[test]
    fn test_key_derivation() {
        let alice = StaticSecret::generate();
        let bob = StaticSecret::generate();

        let shared = alice.diffie_hellman(&bob.public_key());

        let key1 = shared.derive_key(b"test-purpose-1", 32);
        let key2 = shared.derive_key(b"test-purpose-2", 32);

        // Different info should produce different keys
        assert_ne!(key1, key2);

        // Same info should produce same key
        let key1_again = shared.derive_key(b"test-purpose-1", 32);
        assert_eq!(key1, key1_again);
    }

    #[test]
    fn test_to_cipher_key() {
        let alice = StaticSecret::generate();
        let bob = StaticSecret::generate();

        let alice_shared = alice.diffie_hellman(&bob.public_key());
        let bob_shared = bob.diffie_hellman(&alice.public_key());

        let alice_cipher_key = alice_shared.to_cipher_key();
        let bob_cipher_key = bob_shared.to_cipher_key();

        // Both should derive the same encryption key
        assert_eq!(alice_cipher_key.to_hex(), bob_cipher_key.to_hex());
    }

    #[test]
    fn test_encrypt_decrypt_with_dh() {
        let alice = StaticSecret::generate();
        let bob = StaticSecret::generate();

        // Alice encrypts for Bob
        let shared = alice.diffie_hellman(&bob.public_key());
        let cipher_key = shared.to_cipher_key();

        let plaintext = b"Secret message from Alice to Bob";
        let ciphertext = super::super::encrypt(&cipher_key, plaintext).unwrap();

        // Bob decrypts
        let bob_shared = bob.diffie_hellman(&alice.public_key());
        let bob_cipher_key = bob_shared.to_cipher_key();

        let decrypted = super::super::decrypt(&bob_cipher_key, &ciphertext).unwrap();
        assert_eq!(plaintext.as_slice(), decrypted.as_slice());
    }

    #[test]
    fn test_static_secret_roundtrip() {
        let secret = StaticSecret::generate();
        let bytes = secret.to_bytes();
        let recovered = StaticSecret::from_bytes(&bytes).unwrap();

        // Verify they produce the same public key
        assert_eq!(secret.public_key(), recovered.public_key());
    }

    #[test]
    fn test_hex_roundtrip() {
        let secret = StaticSecret::generate();
        let hex_str = secret.to_hex();
        let recovered = StaticSecret::from_hex(&hex_str).unwrap();

        assert_eq!(secret.public_key(), recovered.public_key());
    }

    #[test]
    fn test_public_key_hex_roundtrip() {
        let secret = StaticSecret::generate();
        let public = secret.public_key();
        let hex_str = public.to_hex();
        let recovered = X25519PublicKey::from_hex(&hex_str).unwrap();

        assert_eq!(public, recovered);
    }
}
