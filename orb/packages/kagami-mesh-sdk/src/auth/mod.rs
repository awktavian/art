//! Authentication module for mesh network identity and challenge-response.
//!
//! This module provides Ed25519-based identity management and a secure
//! challenge-response protocol for peer authentication.

mod challenge;
mod ed25519;

pub use challenge::{
    AuthChallenge, AuthResponse, ChallengeError, ChallengeProtocol, ChallengeState,
};
pub use ed25519::{Identity, IdentityError, PublicKey, SecretKey, Signature};
