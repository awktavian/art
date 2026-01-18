//! Ed25519 key generation, signing, and verification.
//!
//! This module wraps ed25519-dalek to provide a clean API for identity
//! management in the Kagami mesh network.

use ed25519_dalek::{
    Signature as DalekSignature, Signer, SigningKey, Verifier, VerifyingKey,
    SECRET_KEY_LENGTH, SIGNATURE_LENGTH,
};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Errors that can occur during identity operations.
#[derive(Debug, Error)]
pub enum IdentityError {
    #[error("Invalid secret key length: expected {expected}, got {got}")]
    InvalidSecretKeyLength { expected: usize, got: usize },

    #[error("Invalid public key length: expected {expected}, got {got}")]
    InvalidPublicKeyLength { expected: usize, got: usize },

    #[error("Invalid signature length: expected {expected}, got {got}")]
    InvalidSignatureLength { expected: usize, got: usize },

    #[error("Signature verification failed")]
    SignatureVerificationFailed,

    #[error("Invalid key bytes: {0}")]
    InvalidKeyBytes(String),

    #[error("Base64 decode error: {0}")]
    Base64DecodeError(String),
}

/// A secret key for signing messages.
#[derive(Clone)]
pub struct SecretKey {
    inner: SigningKey,
}

impl SecretKey {
    /// Generate a new random secret key.
    pub fn generate() -> Self {
        let signing_key = SigningKey::generate(&mut OsRng);
        Self { inner: signing_key }
    }

    /// Create a secret key from raw bytes.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, IdentityError> {
        if bytes.len() != SECRET_KEY_LENGTH {
            return Err(IdentityError::InvalidSecretKeyLength {
                expected: SECRET_KEY_LENGTH,
                got: bytes.len(),
            });
        }

        let mut key_bytes = [0u8; SECRET_KEY_LENGTH];
        key_bytes.copy_from_slice(bytes);

        let signing_key = SigningKey::from_bytes(&key_bytes);
        Ok(Self { inner: signing_key })
    }

    /// Create a secret key from a base64-encoded string.
    pub fn from_base64(encoded: &str) -> Result<Self, IdentityError> {
        let bytes = base64::Engine::decode(&base64::engine::general_purpose::STANDARD, encoded)
            .map_err(|e| IdentityError::Base64DecodeError(e.to_string()))?;
        Self::from_bytes(&bytes)
    }

    /// Export the secret key as raw bytes.
    pub fn to_bytes(&self) -> Vec<u8> {
        self.inner.to_bytes().to_vec()
    }

    /// Export the secret key as a base64-encoded string.
    pub fn to_base64(&self) -> String {
        base64::Engine::encode(&base64::engine::general_purpose::STANDARD, self.to_bytes())
    }

    /// Get the corresponding public key.
    pub fn public_key(&self) -> PublicKey {
        PublicKey {
            inner: self.inner.verifying_key(),
        }
    }

    /// Sign a message.
    pub fn sign(&self, message: &[u8]) -> Signature {
        let sig = self.inner.sign(message);
        Signature { inner: sig }
    }
}

impl std::fmt::Debug for SecretKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("SecretKey")
            .field("public_key", &self.public_key().to_hex())
            .finish()
    }
}

// SECURITY: SigningKey is automatically zeroed on drop via ed25519-dalek's zeroize feature.
// The "zeroize" feature is enabled in Cargo.toml, ensuring h(x) >= 0 for secret key material.

/// A public key for verifying signatures.
#[derive(Clone, Serialize, Deserialize)]
pub struct PublicKey {
    #[serde(
        serialize_with = "serialize_verifying_key",
        deserialize_with = "deserialize_verifying_key"
    )]
    inner: VerifyingKey,
}

fn serialize_verifying_key<S>(key: &VerifyingKey, serializer: S) -> Result<S::Ok, S::Error>
where
    S: serde::Serializer,
{
    let bytes = key.to_bytes();
    let hex_str = hex::encode(bytes);
    serializer.serialize_str(&hex_str)
}

fn deserialize_verifying_key<'de, D>(deserializer: D) -> Result<VerifyingKey, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let hex_str = String::deserialize(deserializer)?;
    let bytes = hex::decode(&hex_str).map_err(serde::de::Error::custom)?;
    let bytes_array: [u8; 32] = bytes
        .try_into()
        .map_err(|_| serde::de::Error::custom("Invalid public key length"))?;
    VerifyingKey::from_bytes(&bytes_array).map_err(serde::de::Error::custom)
}

impl PublicKey {
    /// Create a public key from raw bytes.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, IdentityError> {
        if bytes.len() != 32 {
            return Err(IdentityError::InvalidPublicKeyLength {
                expected: 32,
                got: bytes.len(),
            });
        }

        let mut key_bytes = [0u8; 32];
        key_bytes.copy_from_slice(bytes);

        let verifying_key = VerifyingKey::from_bytes(&key_bytes)
            .map_err(|e| IdentityError::InvalidKeyBytes(e.to_string()))?;

        Ok(Self {
            inner: verifying_key,
        })
    }

    /// Create a public key from a hex-encoded string.
    pub fn from_hex(hex_str: &str) -> Result<Self, IdentityError> {
        let bytes =
            hex::decode(hex_str).map_err(|e| IdentityError::InvalidKeyBytes(e.to_string()))?;
        Self::from_bytes(&bytes)
    }

    /// Create a public key from a base64-encoded string.
    pub fn from_base64(encoded: &str) -> Result<Self, IdentityError> {
        let bytes = base64::Engine::decode(&base64::engine::general_purpose::STANDARD, encoded)
            .map_err(|e| IdentityError::Base64DecodeError(e.to_string()))?;
        Self::from_bytes(&bytes)
    }

    /// Export the public key as raw bytes.
    pub fn to_bytes(&self) -> Vec<u8> {
        self.inner.to_bytes().to_vec()
    }

    /// Export the public key as a hex-encoded string.
    pub fn to_hex(&self) -> String {
        hex::encode(self.to_bytes())
    }

    /// Export the public key as a base64-encoded string.
    pub fn to_base64(&self) -> String {
        base64::Engine::encode(&base64::engine::general_purpose::STANDARD, self.to_bytes())
    }

    /// Verify a signature on a message.
    pub fn verify(&self, message: &[u8], signature: &Signature) -> Result<(), IdentityError> {
        self.inner
            .verify(message, &signature.inner)
            .map_err(|_| IdentityError::SignatureVerificationFailed)
    }
}

impl std::fmt::Debug for PublicKey {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("PublicKey")
            .field("hex", &self.to_hex())
            .finish()
    }
}

impl PartialEq for PublicKey {
    fn eq(&self, other: &Self) -> bool {
        self.to_bytes() == other.to_bytes()
    }
}

impl Eq for PublicKey {}

impl std::hash::Hash for PublicKey {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        self.to_bytes().hash(state);
    }
}

/// A signature over a message.
#[derive(Clone, Serialize, Deserialize)]
pub struct Signature {
    #[serde(
        serialize_with = "serialize_signature",
        deserialize_with = "deserialize_signature"
    )]
    inner: DalekSignature,
}

fn serialize_signature<S>(sig: &DalekSignature, serializer: S) -> Result<S::Ok, S::Error>
where
    S: serde::Serializer,
{
    let bytes = sig.to_bytes();
    let hex_str = hex::encode(bytes);
    serializer.serialize_str(&hex_str)
}

fn deserialize_signature<'de, D>(deserializer: D) -> Result<DalekSignature, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let hex_str = String::deserialize(deserializer)?;
    let bytes = hex::decode(&hex_str).map_err(serde::de::Error::custom)?;
    let bytes_array: [u8; SIGNATURE_LENGTH] = bytes
        .try_into()
        .map_err(|_| serde::de::Error::custom("Invalid signature length"))?;
    Ok(DalekSignature::from_bytes(&bytes_array))
}

impl Signature {
    /// Create a signature from raw bytes.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, IdentityError> {
        if bytes.len() != SIGNATURE_LENGTH {
            return Err(IdentityError::InvalidSignatureLength {
                expected: SIGNATURE_LENGTH,
                got: bytes.len(),
            });
        }

        let mut sig_bytes = [0u8; SIGNATURE_LENGTH];
        sig_bytes.copy_from_slice(bytes);

        let sig = DalekSignature::from_bytes(&sig_bytes);
        Ok(Self { inner: sig })
    }

    /// Create a signature from a hex-encoded string.
    pub fn from_hex(hex_str: &str) -> Result<Self, IdentityError> {
        let bytes =
            hex::decode(hex_str).map_err(|e| IdentityError::InvalidKeyBytes(e.to_string()))?;
        Self::from_bytes(&bytes)
    }

    /// Export the signature as raw bytes.
    pub fn to_bytes(&self) -> Vec<u8> {
        self.inner.to_bytes().to_vec()
    }

    /// Export the signature as a hex-encoded string.
    pub fn to_hex(&self) -> String {
        hex::encode(self.to_bytes())
    }
}

impl std::fmt::Debug for Signature {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Signature")
            .field("hex", &self.to_hex())
            .finish()
    }
}

/// A complete identity consisting of a secret key and public key pair.
#[derive(Clone)]
pub struct Identity {
    secret_key: SecretKey,
    public_key: PublicKey,
}

impl Identity {
    /// Generate a new random identity.
    pub fn generate() -> Self {
        let secret_key = SecretKey::generate();
        let public_key = secret_key.public_key();
        Self {
            secret_key,
            public_key,
        }
    }

    /// Create an identity from a secret key.
    pub fn from_secret_key(secret_key: SecretKey) -> Self {
        let public_key = secret_key.public_key();
        Self {
            secret_key,
            public_key,
        }
    }

    /// Create an identity from raw secret key bytes.
    pub fn from_bytes(bytes: &[u8]) -> Result<Self, IdentityError> {
        let secret_key = SecretKey::from_bytes(bytes)?;
        Ok(Self::from_secret_key(secret_key))
    }

    /// Create an identity from a base64-encoded secret key.
    pub fn from_base64(encoded: &str) -> Result<Self, IdentityError> {
        let secret_key = SecretKey::from_base64(encoded)?;
        Ok(Self::from_secret_key(secret_key))
    }

    /// Get the secret key.
    pub fn secret_key(&self) -> &SecretKey {
        &self.secret_key
    }

    /// Get the public key.
    pub fn public_key(&self) -> &PublicKey {
        &self.public_key
    }

    /// Get the peer ID (hex-encoded public key).
    pub fn peer_id(&self) -> String {
        self.public_key.to_hex()
    }

    /// Sign a message.
    pub fn sign(&self, message: &[u8]) -> Signature {
        self.secret_key.sign(message)
    }

    /// Verify a signature on a message.
    pub fn verify(&self, message: &[u8], signature: &Signature) -> Result<(), IdentityError> {
        self.public_key.verify(message, signature)
    }

    /// Export the identity as base64-encoded secret key.
    pub fn to_base64(&self) -> String {
        self.secret_key.to_base64()
    }

    /// Export the secret key as raw bytes.
    pub fn to_bytes(&self) -> Vec<u8> {
        self.secret_key.to_bytes()
    }
}

impl std::fmt::Debug for Identity {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Identity")
            .field("peer_id", &self.peer_id())
            .finish()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_identity_generation() {
        let identity = Identity::generate();
        assert_eq!(identity.public_key().to_bytes().len(), 32);
        assert_eq!(identity.secret_key().to_bytes().len(), 32);
    }

    #[test]
    fn test_sign_and_verify() {
        let identity = Identity::generate();
        let message = b"Hello, Kagami mesh!";
        let signature = identity.sign(message);

        assert!(identity.verify(message, &signature).is_ok());
    }

    #[test]
    fn test_verify_wrong_message() {
        let identity = Identity::generate();
        let message = b"Hello, Kagami mesh!";
        let wrong_message = b"Wrong message";
        let signature = identity.sign(message);

        assert!(identity.verify(wrong_message, &signature).is_err());
    }

    #[test]
    fn test_verify_wrong_key() {
        let identity1 = Identity::generate();
        let identity2 = Identity::generate();
        let message = b"Hello, Kagami mesh!";
        let signature = identity1.sign(message);

        assert!(identity2.verify(message, &signature).is_err());
    }

    #[test]
    fn test_roundtrip_bytes() {
        let identity = Identity::generate();
        let bytes = identity.to_bytes();
        let recovered = Identity::from_bytes(&bytes).unwrap();

        assert_eq!(identity.peer_id(), recovered.peer_id());
    }

    #[test]
    fn test_roundtrip_base64() {
        let identity = Identity::generate();
        let encoded = identity.to_base64();
        let recovered = Identity::from_base64(&encoded).unwrap();

        assert_eq!(identity.peer_id(), recovered.peer_id());
    }

    #[test]
    fn test_public_key_hex_roundtrip() {
        let identity = Identity::generate();
        let hex = identity.public_key().to_hex();
        let recovered = PublicKey::from_hex(&hex).unwrap();

        assert_eq!(identity.public_key(), &recovered);
    }

    #[test]
    fn test_signature_hex_roundtrip() {
        let identity = Identity::generate();
        let message = b"Test message";
        let signature = identity.sign(message);
        let hex = signature.to_hex();
        let recovered = Signature::from_hex(&hex).unwrap();

        assert!(identity.verify(message, &recovered).is_ok());
    }
}
