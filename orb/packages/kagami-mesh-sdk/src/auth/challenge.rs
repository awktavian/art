//! Challenge-response authentication protocol.
//!
//! This module implements a secure challenge-response protocol for authenticating
//! peers in the Kagami mesh network. The protocol works as follows:
//!
//! 1. Server generates a random challenge and sends it to the client
//! 2. Client signs the challenge with their private key and sends back the response
//! 3. Server verifies the signature using the client's public key
//!
//! This proves the client possesses the private key without revealing it.

use super::{Identity, IdentityError, PublicKey, Signature};
use chrono::{DateTime, Duration, Utc};
use rand::RngCore;
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// The size of a challenge nonce in bytes (256 bits).
const CHALLENGE_SIZE: usize = 32;

/// Default challenge validity period in seconds.
const DEFAULT_CHALLENGE_VALIDITY_SECS: i64 = 30;

/// Errors that can occur during challenge-response authentication.
#[derive(Debug, Error)]
pub enum ChallengeError {
    #[error("Challenge has expired")]
    ChallengeExpired,

    #[error("Challenge nonce mismatch")]
    NonceMismatch,

    #[error("Invalid signature: {0}")]
    InvalidSignature(#[from] IdentityError),

    #[error("Unexpected peer: expected {expected}, got {got}")]
    UnexpectedPeer { expected: String, got: String },

    #[error("Invalid challenge state: {0}")]
    InvalidState(String),

    #[error("Challenge not found")]
    ChallengeNotFound,

    #[error("Protocol error: {0}")]
    ProtocolError(String),
}

/// A challenge sent to a peer for authentication.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthChallenge {
    /// Random nonce for this challenge.
    pub nonce: Vec<u8>,

    /// The peer's public key we're challenging.
    pub peer_public_key: PublicKey,

    /// When this challenge was created.
    pub created_at: DateTime<Utc>,

    /// When this challenge expires.
    pub expires_at: DateTime<Utc>,

    /// Optional additional data to include in the signature.
    pub context: Option<Vec<u8>>,
}

impl AuthChallenge {
    /// Create a new challenge for a peer.
    pub fn new(peer_public_key: PublicKey) -> Self {
        Self::with_validity(peer_public_key, DEFAULT_CHALLENGE_VALIDITY_SECS)
    }

    /// Create a new challenge with a custom validity period.
    pub fn with_validity(peer_public_key: PublicKey, validity_secs: i64) -> Self {
        let mut nonce = vec![0u8; CHALLENGE_SIZE];
        rand::thread_rng().fill_bytes(&mut nonce);

        let created_at = Utc::now();
        let expires_at = created_at + Duration::seconds(validity_secs);

        Self {
            nonce,
            peer_public_key,
            created_at,
            expires_at,
            context: None,
        }
    }

    /// Create a challenge with additional context data.
    pub fn with_context(mut self, context: Vec<u8>) -> Self {
        self.context = Some(context);
        self
    }

    /// Check if this challenge has expired.
    pub fn is_expired(&self) -> bool {
        Utc::now() > self.expires_at
    }

    /// Get the data that should be signed for this challenge.
    pub fn data_to_sign(&self) -> Vec<u8> {
        let mut data = Vec::new();
        data.extend_from_slice(&self.nonce);
        data.extend_from_slice(&self.peer_public_key.to_bytes());
        if let Some(ctx) = &self.context {
            data.extend_from_slice(ctx);
        }
        data
    }

    /// Sign this challenge using the given identity.
    pub fn sign(&self, identity: &Identity) -> Result<AuthResponse, ChallengeError> {
        // Verify the challenge is for this identity
        if identity.public_key() != &self.peer_public_key {
            return Err(ChallengeError::UnexpectedPeer {
                expected: self.peer_public_key.to_hex(),
                got: identity.peer_id(),
            });
        }

        let data = self.data_to_sign();
        let signature = identity.sign(&data);

        Ok(AuthResponse {
            nonce: self.nonce.clone(),
            public_key: identity.public_key().clone(),
            signature,
            timestamp: Utc::now(),
        })
    }
}

/// A response to an authentication challenge.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthResponse {
    /// The nonce from the challenge.
    pub nonce: Vec<u8>,

    /// The responder's public key.
    pub public_key: PublicKey,

    /// The signature over the challenge data.
    pub signature: Signature,

    /// When this response was created.
    pub timestamp: DateTime<Utc>,
}

impl AuthResponse {
    /// Verify this response against the original challenge.
    pub fn verify(&self, challenge: &AuthChallenge) -> Result<(), ChallengeError> {
        // Check expiration
        if challenge.is_expired() {
            return Err(ChallengeError::ChallengeExpired);
        }

        // Check nonce matches
        if self.nonce != challenge.nonce {
            return Err(ChallengeError::NonceMismatch);
        }

        // Check public key matches
        if self.public_key != challenge.peer_public_key {
            return Err(ChallengeError::UnexpectedPeer {
                expected: challenge.peer_public_key.to_hex(),
                got: self.public_key.to_hex(),
            });
        }

        // Verify the signature
        let data = challenge.data_to_sign();
        self.public_key.verify(&data, &self.signature)?;

        Ok(())
    }
}

/// State of a challenge-response authentication session.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ChallengeState {
    /// Initial state, no challenge sent yet.
    Idle,

    /// Challenge sent, waiting for response.
    Challenged,

    /// Authentication successful.
    Authenticated,

    /// Authentication failed.
    Failed(String),
}

/// Manager for the challenge-response protocol.
///
/// Tracks pending challenges and their states.
/// SECURITY: Includes replay protection to prevent response reuse.
pub struct ChallengeProtocol {
    /// Our identity for authentication.
    identity: Identity,

    /// Map of peer public key hex -> pending challenge.
    pending_challenges: parking_lot::RwLock<std::collections::HashMap<String, AuthChallenge>>,

    /// Challenge validity in seconds.
    challenge_validity_secs: i64,

    /// SECURITY: Track used response nonces to prevent replay attacks.
    /// Stores (peer_id, nonce_hash) pairs with timestamp for cleanup.
    used_responses: parking_lot::RwLock<std::collections::HashMap<(String, Vec<u8>), i64>>,

    /// Maximum number of used responses to track (prevents memory exhaustion).
    max_used_responses: usize,
}

impl ChallengeProtocol {
    /// Create a new challenge protocol manager.
    pub fn new(identity: Identity) -> Self {
        Self {
            identity,
            pending_challenges: parking_lot::RwLock::new(std::collections::HashMap::new()),
            challenge_validity_secs: DEFAULT_CHALLENGE_VALIDITY_SECS,
            used_responses: parking_lot::RwLock::new(std::collections::HashMap::new()),
            max_used_responses: 10000, // Prevent memory exhaustion
        }
    }

    /// Create with a custom challenge validity period.
    pub fn with_validity(mut self, secs: i64) -> Self {
        self.challenge_validity_secs = secs;
        self
    }

    /// Create with custom max used responses limit.
    pub fn with_max_used_responses(mut self, max: usize) -> Self {
        self.max_used_responses = max;
        self
    }

    /// Get our identity.
    pub fn identity(&self) -> &Identity {
        &self.identity
    }

    /// Generate a challenge for a peer.
    pub fn create_challenge(&self, peer_public_key: PublicKey) -> AuthChallenge {
        let challenge =
            AuthChallenge::with_validity(peer_public_key.clone(), self.challenge_validity_secs);

        let peer_id = peer_public_key.to_hex();
        self.pending_challenges
            .write()
            .insert(peer_id, challenge.clone());

        challenge
    }

    /// Generate a challenge with context.
    pub fn create_challenge_with_context(
        &self,
        peer_public_key: PublicKey,
        context: Vec<u8>,
    ) -> AuthChallenge {
        let challenge =
            AuthChallenge::with_validity(peer_public_key.clone(), self.challenge_validity_secs)
                .with_context(context);

        let peer_id = peer_public_key.to_hex();
        self.pending_challenges
            .write()
            .insert(peer_id, challenge.clone());

        challenge
    }

    /// Respond to a challenge we received.
    pub fn respond_to_challenge(
        &self,
        challenge: &AuthChallenge,
    ) -> Result<AuthResponse, ChallengeError> {
        challenge.sign(&self.identity)
    }

    /// Verify a response to one of our challenges.
    ///
    /// SECURITY: Includes replay protection - each response can only be used once.
    pub fn verify_response(&self, response: &AuthResponse) -> Result<(), ChallengeError> {
        let peer_id = response.public_key.to_hex();

        // SECURITY: Check for replay attack - has this exact response been used before?
        let response_key = (peer_id.clone(), response.nonce.clone());
        {
            let used = self.used_responses.read();
            if used.contains_key(&response_key) {
                return Err(ChallengeError::ProtocolError(
                    "Replay attack detected: Response has already been used".to_string()
                ));
            }
        }

        let challenge = {
            let challenges = self.pending_challenges.read();
            challenges
                .get(&peer_id)
                .cloned()
                .ok_or(ChallengeError::ChallengeNotFound)?
        };

        // Verify the response
        response.verify(&challenge)?;

        // SECURITY: Mark this response as used to prevent replay
        {
            let mut used = self.used_responses.write();

            // Enforce max size to prevent memory exhaustion
            if used.len() >= self.max_used_responses {
                // Remove oldest 10% of entries
                let mut entries: Vec<_> = used.iter().map(|(k, &v)| (k.clone(), v)).collect();
                entries.sort_by_key(|(_, ts)| *ts);
                let remove_count = entries.len() / 10 + 1;
                for (key, _) in entries.into_iter().take(remove_count) {
                    used.remove(&key);
                }
            }

            used.insert(response_key, Utc::now().timestamp());
        }

        // Remove the challenge on success
        self.pending_challenges.write().remove(&peer_id);

        Ok(())
    }

    /// Clean up expired challenges and old used responses.
    pub fn cleanup_expired(&self) -> usize {
        let mut challenges = self.pending_challenges.write();
        let before = challenges.len();
        challenges.retain(|_, c| !c.is_expired());
        let challenges_cleaned = before - challenges.len();
        drop(challenges);

        // SECURITY: Also cleanup old used responses (older than challenge validity * 2)
        let cutoff = Utc::now().timestamp() - (self.challenge_validity_secs * 2);
        let mut used = self.used_responses.write();
        let before_used = used.len();
        used.retain(|_, &mut ts| ts > cutoff);
        let used_cleaned = before_used - used.len();

        challenges_cleaned + used_cleaned
    }

    /// Get the number of pending challenges.
    pub fn pending_count(&self) -> usize {
        self.pending_challenges.read().len()
    }

    /// Check if we have a pending challenge for a peer.
    pub fn has_pending_challenge(&self, peer_public_key: &PublicKey) -> bool {
        let peer_id = peer_public_key.to_hex();
        self.pending_challenges.read().contains_key(&peer_id)
    }
}

impl std::fmt::Debug for ChallengeProtocol {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("ChallengeProtocol")
            .field("identity", &self.identity.peer_id())
            .field("pending_challenges", &self.pending_count())
            .finish()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_challenge_response_flow() {
        // Server and client identities
        let server_identity = Identity::generate();
        let client_identity = Identity::generate();

        // Server creates challenge protocol
        let server_protocol = ChallengeProtocol::new(server_identity);

        // Server creates challenge for client
        let challenge = server_protocol.create_challenge(client_identity.public_key().clone());

        // Client receives challenge and signs it
        let response = challenge.sign(&client_identity).unwrap();

        // Server verifies the response
        assert!(server_protocol.verify_response(&response).is_ok());
    }

    #[test]
    fn test_challenge_response_with_context() {
        let server_identity = Identity::generate();
        let client_identity = Identity::generate();

        let server_protocol = ChallengeProtocol::new(server_identity);
        let context = b"session:12345".to_vec();

        let challenge = server_protocol
            .create_challenge_with_context(client_identity.public_key().clone(), context);

        let response = challenge.sign(&client_identity).unwrap();
        assert!(server_protocol.verify_response(&response).is_ok());
    }

    #[test]
    fn test_expired_challenge() {
        let _server_identity = Identity::generate();
        let client_identity = Identity::generate();

        // Create challenge with 0 validity
        let challenge = AuthChallenge::with_validity(client_identity.public_key().clone(), 0);

        // Wait for it to expire
        std::thread::sleep(std::time::Duration::from_millis(10));

        assert!(challenge.is_expired());

        let response = challenge.sign(&client_identity).unwrap();
        assert!(matches!(
            response.verify(&challenge),
            Err(ChallengeError::ChallengeExpired)
        ));
    }

    #[test]
    fn test_wrong_identity_response() {
        let server_identity = Identity::generate();
        let client_identity = Identity::generate();
        let other_identity = Identity::generate();

        let server_protocol = ChallengeProtocol::new(server_identity);
        let challenge = server_protocol.create_challenge(client_identity.public_key().clone());

        // Other identity tries to sign (wrong peer)
        let result = challenge.sign(&other_identity);
        assert!(matches!(result, Err(ChallengeError::UnexpectedPeer { .. })));
    }

    #[test]
    fn test_mutual_authentication() {
        // Both peers authenticate each other
        let alice = ChallengeProtocol::new(Identity::generate());
        let bob = ChallengeProtocol::new(Identity::generate());

        // Alice challenges Bob
        let alice_challenge = alice.create_challenge(bob.identity().public_key().clone());
        let bob_response = bob.respond_to_challenge(&alice_challenge).unwrap();
        assert!(alice.verify_response(&bob_response).is_ok());

        // Bob challenges Alice
        let bob_challenge = bob.create_challenge(alice.identity().public_key().clone());
        let alice_response = alice.respond_to_challenge(&bob_challenge).unwrap();
        assert!(bob.verify_response(&alice_response).is_ok());
    }

    #[test]
    fn test_cleanup_expired() {
        let protocol = ChallengeProtocol::new(Identity::generate()).with_validity(0);

        let peer1 = Identity::generate();
        let peer2 = Identity::generate();

        protocol.create_challenge(peer1.public_key().clone());
        protocol.create_challenge(peer2.public_key().clone());

        assert_eq!(protocol.pending_count(), 2);

        std::thread::sleep(std::time::Duration::from_millis(10));

        let cleaned = protocol.cleanup_expired();
        assert_eq!(cleaned, 2);
        assert_eq!(protocol.pending_count(), 0);
    }
}
