//! Cryptographic primitives for secure communication.
//!
//! This module provides:
//! - XChaCha20-Poly1305 authenticated encryption
//! - X25519 Diffie-Hellman key exchange

mod x25519;
mod xchacha;

pub use x25519::{EphemeralSecret, SharedSecret, StaticSecret, X25519Error, X25519PublicKey};
pub use xchacha::{decrypt, encrypt, CipherError, Nonce, SecretKey};
