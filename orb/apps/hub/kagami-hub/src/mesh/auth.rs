//! Mesh Authentication
//!
//! Peer authentication using Ed25519 signatures with hardened security:
//! - Challenge binding: Sign(challenge || peer_id || timestamp || nonce)
//! - Challenge expiry tracking with bloom filter for replay prevention
//! - Public key registry with first-use pinning + rotation protocol
//! - Rate limiting with exponential backoff
//! - Mutual authentication (both sides verify)
//!
//! Colony: Crystal (e₇) — Verification and trust
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::RwLock;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tracing::{debug, error, info, warn};

/// Challenge expiry time in seconds (60 seconds)
const CHALLENGE_EXPIRY_SECS: u64 = 60;

/// Maximum consecutive auth failures before blocking a peer
const MAX_AUTH_FAILURES: u32 = 5;

/// Block duration after max failures (5 minutes)
const BLOCK_DURATION_SECS: u64 = 300;

/// Maximum backoff delay in seconds
const MAX_BACKOFF_SECS: u64 = 32;

/// Bloom filter expected insertions (per time window)
const BLOOM_EXPECTED_INSERTIONS: usize = 10_000;

/// Bloom filter false positive rate
const BLOOM_FALSE_POSITIVE_RATE: f64 = 0.001;

/// Key rotation grace period in seconds (allows overlap during rotation)
const KEY_ROTATION_GRACE_SECS: u64 = 3600; // 1 hour

/// Maximum age for accepting a challenge timestamp (clock skew tolerance)
const MAX_TIMESTAMP_SKEW_SECS: u64 = 30;

// ============================================================================
// Bloom Filter for Challenge Tracking
// ============================================================================

/// Simple bloom filter implementation for tracking used challenges.
/// This prevents replay attacks by marking challenges as used.
#[derive(Debug)]
struct BloomFilter {
    /// Bit array
    bits: Vec<bool>,
    /// Number of hash functions
    num_hashes: usize,
    /// Creation time for time-based expiry
    created_at: Instant,
    /// Expiry duration
    expiry: Duration,
}

impl BloomFilter {
    /// Create a new bloom filter with optimal parameters
    fn new(expected_insertions: usize, false_positive_rate: f64, expiry: Duration) -> Self {
        // Optimal number of bits: m = -n*ln(p) / (ln(2)^2)
        let ln2_sq = std::f64::consts::LN_2 * std::f64::consts::LN_2;
        let m = (-(expected_insertions as f64) * false_positive_rate.ln() / ln2_sq).ceil() as usize;
        let m = m.max(64); // Minimum size

        // Optimal number of hash functions: k = (m/n) * ln(2)
        let k = ((m as f64 / expected_insertions as f64) * std::f64::consts::LN_2).ceil() as usize;
        let k = k.clamp(1, 16); // Reasonable bounds

        Self {
            bits: vec![false; m],
            num_hashes: k,
            created_at: Instant::now(),
            expiry,
        }
    }

    /// Check if the bloom filter has expired
    fn is_expired(&self) -> bool {
        self.created_at.elapsed() > self.expiry
    }

    /// Insert an item into the bloom filter
    fn insert(&mut self, item: &[u8]) {
        for i in 0..self.num_hashes {
            let idx = self.hash(item, i);
            self.bits[idx] = true;
        }
    }

    /// Check if an item might be in the filter (may have false positives)
    fn might_contain(&self, item: &[u8]) -> bool {
        for i in 0..self.num_hashes {
            let idx = self.hash(item, i);
            if !self.bits[idx] {
                return false;
            }
        }
        true
    }

    /// Simple hash function using FNV-1a with seed variation
    fn hash(&self, item: &[u8], seed: usize) -> usize {
        // FNV-1a with seed mixing
        let mut hash: u64 = 14695981039346656037u64.wrapping_add(seed as u64 * 0x100000001b3);
        for byte in item {
            hash ^= *byte as u64;
            hash = hash.wrapping_mul(0x100000001b3);
        }
        (hash as usize) % self.bits.len()
    }
}

// ============================================================================
// Rate Limiting
// ============================================================================

/// Tracks authentication failures for rate limiting
#[derive(Debug)]
struct AuthFailureTracker {
    /// Number of consecutive failures
    failure_count: u32,
    /// Time of last failure
    last_failure: Instant,
    /// If blocked, when the block started
    blocked_since: Option<Instant>,
    /// Last successful auth time
    last_success: Option<Instant>,
}

impl AuthFailureTracker {
    fn new() -> Self {
        Self {
            failure_count: 0,
            last_failure: Instant::now(),
            blocked_since: None,
            last_success: None,
        }
    }

    /// Get the backoff duration based on failure count (exponential: 1s, 2s, 4s, 8s, 16s, 32s cap)
    fn backoff_duration(&self) -> Duration {
        if self.failure_count == 0 {
            return Duration::ZERO;
        }
        let secs = (1u64 << (self.failure_count - 1).min(5)).min(MAX_BACKOFF_SECS);
        Duration::from_secs(secs)
    }

    /// Check if the peer is currently blocked
    fn is_blocked(&self) -> bool {
        if let Some(blocked_since) = self.blocked_since {
            blocked_since.elapsed() < Duration::from_secs(BLOCK_DURATION_SECS)
        } else {
            false
        }
    }

    /// Check if we need to wait for backoff
    fn needs_backoff(&self) -> bool {
        if self.is_blocked() {
            return true;
        }
        self.last_failure.elapsed() < self.backoff_duration()
    }

    /// Record an auth failure
    fn record_failure(&mut self) {
        self.failure_count += 1;
        self.last_failure = Instant::now();

        if self.failure_count >= MAX_AUTH_FAILURES {
            self.blocked_since = Some(Instant::now());
            warn!(
                "Peer blocked after {} consecutive auth failures",
                self.failure_count
            );
        }
    }

    /// Reset on successful auth
    fn reset(&mut self) {
        self.failure_count = 0;
        self.blocked_since = None;
        self.last_success = Some(Instant::now());
    }

    /// Get remaining block time if blocked
    fn remaining_block_time(&self) -> Option<Duration> {
        if let Some(blocked_since) = self.blocked_since {
            let elapsed = blocked_since.elapsed();
            let block_duration = Duration::from_secs(BLOCK_DURATION_SECS);
            if elapsed < block_duration {
                return Some(block_duration - elapsed);
            }
        }
        None
    }
}

// ============================================================================
// Public Key Registry with Pinning
// ============================================================================

/// Entry in the public key registry
#[derive(Debug, Clone)]
pub struct PinnedKey {
    /// The pinned public key bytes
    pub public_key: Vec<u8>,
    /// When this key was first seen/pinned
    pub pinned_at: u64,
    /// When this key was last used successfully
    pub last_used: u64,
    /// Optional rotation key (new key being rotated to)
    pub rotation_key: Option<Vec<u8>>,
    /// When rotation was initiated
    pub rotation_started: Option<u64>,
}

impl PinnedKey {
    fn new(public_key: Vec<u8>) -> Self {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        Self {
            public_key,
            pinned_at: now,
            last_used: now,
            rotation_key: None,
            rotation_started: None,
        }
    }

    /// Check if a given key matches (including rotation key during grace period)
    fn matches(&self, key: &[u8]) -> bool {
        if self.public_key == key {
            return true;
        }

        // Check rotation key during grace period
        if let (Some(rotation_key), Some(rotation_started)) =
            (&self.rotation_key, self.rotation_started)
        {
            let now = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs();

            // Allow both keys during grace period
            if now - rotation_started <= KEY_ROTATION_GRACE_SECS && rotation_key == key {
                return true;
            }
        }

        false
    }

    /// Update last used timestamp
    fn touch(&mut self) {
        self.last_used = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
    }
}

// ============================================================================
// Enhanced Challenge/Response Types
// ============================================================================

/// Authentication challenge for peer verification with enhanced binding
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthChallenge {
    /// Random challenge bytes (32 bytes)
    pub challenge: Vec<u8>,
    /// Random nonce for uniqueness (16 bytes)
    pub nonce: Vec<u8>,
    /// Timestamp of challenge creation
    pub timestamp: u64,
    /// Hub ID of challenger
    pub challenger_hub_id: String,
    /// Hub ID of expected responder (binding)
    pub responder_hub_id: String,
}

impl AuthChallenge {
    /// Create the canonical byte representation for signing
    pub fn to_signing_bytes(&self) -> Vec<u8> {
        let mut bytes = Vec::with_capacity(32 + 16 + 8 + 64 + 64);
        bytes.extend_from_slice(&self.challenge);
        bytes.extend_from_slice(&self.nonce);
        bytes.extend_from_slice(&self.timestamp.to_be_bytes());
        bytes.extend_from_slice(self.challenger_hub_id.as_bytes());
        bytes.extend_from_slice(self.responder_hub_id.as_bytes());
        bytes
    }
}

/// Response to authentication challenge
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthResponse {
    /// Original challenge (for verification)
    pub challenge: Vec<u8>,
    /// Original nonce
    pub nonce: Vec<u8>,
    /// Original timestamp
    pub timestamp: u64,
    /// Signature over bound challenge data
    pub signature: Vec<u8>,
    /// Public key of responder
    pub public_key: Vec<u8>,
    /// Hub ID of responder
    pub responder_hub_id: String,
    /// Hub ID of challenger (for binding verification)
    pub challenger_hub_id: String,
}

/// Request to initiate key rotation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KeyRotationRequest {
    /// Hub ID requesting rotation
    pub hub_id: String,
    /// New public key
    pub new_public_key: Vec<u8>,
    /// Timestamp
    pub timestamp: u64,
    /// Signature over (hub_id || new_public_key || timestamp) with OLD key
    pub signature_old_key: Vec<u8>,
    /// Signature over same data with NEW key (proves possession)
    pub signature_new_key: Vec<u8>,
}

/// Result of authentication attempt
#[derive(Debug, Clone)]
pub enum AuthResult {
    /// Authentication succeeded
    Success {
        hub_id: String,
        is_new_peer: bool,
    },
    /// Peer is rate-limited
    RateLimited {
        remaining_secs: u64,
    },
    /// Challenge has already been used (replay attack)
    ChallengeReused,
    /// Challenge has expired
    ChallengeExpired,
    /// Invalid signature
    InvalidSignature,
    /// Public key mismatch with pinned key
    KeyMismatch {
        hub_id: String,
    },
    /// Peer is blocked due to too many failures
    Blocked {
        remaining_secs: u64,
    },
    /// Challenge binding mismatch (wrong peer_id in challenge)
    BindingMismatch,
    /// Timestamp out of acceptable range
    TimestampInvalid,
}

// ============================================================================
// Mutual Authentication State Machine
// ============================================================================

/// State of mutual authentication handshake
#[derive(Debug, Clone)]
pub enum MutualAuthState {
    /// Initial state - no auth in progress
    Idle,
    /// We sent a challenge, waiting for response
    ChallengeSent {
        challenge: AuthChallenge,
        sent_at: Instant,
    },
    /// We received and verified their response, now they verify us
    TheirResponseVerified {
        their_hub_id: String,
    },
    /// Both sides verified
    MutuallyAuthenticated {
        peer_hub_id: String,
        completed_at: Instant,
    },
    /// Auth failed
    Failed {
        reason: String,
    },
}

/// Tracks mutual auth state per peer
#[derive(Debug)]
struct MutualAuthSession {
    state: MutualAuthState,
    started_at: Instant,
}

impl MutualAuthSession {
    fn new() -> Self {
        Self {
            state: MutualAuthState::Idle,
            started_at: Instant::now(),
        }
    }

    fn is_expired(&self) -> bool {
        // Sessions expire after 30 seconds
        self.started_at.elapsed() > Duration::from_secs(30)
    }
}

// ============================================================================
// Main Authentication Handler
// ============================================================================

/// Mesh authentication handler with hardened security
pub struct MeshAuth {
    #[cfg(feature = "mesh")]
    signing_key: ed25519_dalek::SigningKey,
    #[cfg(feature = "mesh")]
    verifying_key: ed25519_dalek::VerifyingKey,

    /// This hub's ID
    hub_id: RwLock<Option<String>>,

    /// Pinned public keys (hub_id -> PinnedKey)
    /// Uses TOFU (Trust On First Use) with pinning
    pinned_keys: RwLock<HashMap<String, PinnedKey>>,

    /// Pending challenges we've issued (challenge_hash -> challenge)
    pending_challenges: RwLock<HashMap<Vec<u8>, AuthChallenge>>,

    /// Bloom filter for used challenges (prevents replay)
    used_challenges: RwLock<BloomFilter>,

    /// Second bloom filter (for rotation when first expires)
    used_challenges_next: RwLock<BloomFilter>,

    /// Failed auth attempt tracking per peer (hub_id -> tracker)
    auth_failures: RwLock<HashMap<String, AuthFailureTracker>>,

    /// Mutual auth sessions per peer
    mutual_auth_sessions: RwLock<HashMap<String, MutualAuthSession>>,
}

impl MeshAuth {
    /// Create a new mesh authentication handler with a fresh keypair
    #[cfg(feature = "mesh")]
    pub fn new() -> Self {
        use ed25519_dalek::SigningKey;
        use rand::rngs::OsRng;
        use rand::RngCore;

        // Generate random bytes for the secret key
        let mut secret_bytes = [0u8; 32];
        OsRng.fill_bytes(&mut secret_bytes);
        let signing_key = SigningKey::from_bytes(&secret_bytes);
        let verifying_key = signing_key.verifying_key();

        info!("Generated new mesh authentication keypair");

        let expiry = Duration::from_secs(CHALLENGE_EXPIRY_SECS * 2);

        Self {
            signing_key,
            verifying_key,
            hub_id: RwLock::new(None),
            pinned_keys: RwLock::new(HashMap::new()),
            pending_challenges: RwLock::new(HashMap::new()),
            used_challenges: RwLock::new(BloomFilter::new(
                BLOOM_EXPECTED_INSERTIONS,
                BLOOM_FALSE_POSITIVE_RATE,
                expiry,
            )),
            used_challenges_next: RwLock::new(BloomFilter::new(
                BLOOM_EXPECTED_INSERTIONS,
                BLOOM_FALSE_POSITIVE_RATE,
                expiry,
            )),
            auth_failures: RwLock::new(HashMap::new()),
            mutual_auth_sessions: RwLock::new(HashMap::new()),
        }
    }

    #[cfg(not(feature = "mesh"))]
    pub fn new() -> Self {
        warn!("Mesh authentication disabled (compile with --features mesh)");
        let expiry = Duration::from_secs(CHALLENGE_EXPIRY_SECS * 2);

        Self {
            hub_id: RwLock::new(None),
            pinned_keys: RwLock::new(HashMap::new()),
            pending_challenges: RwLock::new(HashMap::new()),
            used_challenges: RwLock::new(BloomFilter::new(
                BLOOM_EXPECTED_INSERTIONS,
                BLOOM_FALSE_POSITIVE_RATE,
                expiry,
            )),
            used_challenges_next: RwLock::new(BloomFilter::new(
                BLOOM_EXPECTED_INSERTIONS,
                BLOOM_FALSE_POSITIVE_RATE,
                expiry,
            )),
            auth_failures: RwLock::new(HashMap::new()),
            mutual_auth_sessions: RwLock::new(HashMap::new()),
        }
    }

    /// Set this hub's ID (required for challenge binding)
    pub fn set_hub_id(&self, hub_id: &str) {
        *self.hub_id.write().unwrap() = Some(hub_id.to_string());
    }

    /// Get this hub's ID
    fn get_hub_id(&self) -> String {
        self.hub_id
            .read()
            .unwrap()
            .clone()
            .unwrap_or_else(|| "unknown".to_string())
    }

    /// Load keypair from bytes
    #[cfg(feature = "mesh")]
    pub fn from_bytes(secret_key_bytes: &[u8; 32]) -> Result<Self> {
        use ed25519_dalek::SigningKey;

        let signing_key = SigningKey::from_bytes(secret_key_bytes);
        let verifying_key = signing_key.verifying_key();

        let expiry = Duration::from_secs(CHALLENGE_EXPIRY_SECS * 2);

        Ok(Self {
            signing_key,
            verifying_key,
            hub_id: RwLock::new(None),
            pinned_keys: RwLock::new(HashMap::new()),
            pending_challenges: RwLock::new(HashMap::new()),
            used_challenges: RwLock::new(BloomFilter::new(
                BLOOM_EXPECTED_INSERTIONS,
                BLOOM_FALSE_POSITIVE_RATE,
                expiry,
            )),
            used_challenges_next: RwLock::new(BloomFilter::new(
                BLOOM_EXPECTED_INSERTIONS,
                BLOOM_FALSE_POSITIVE_RATE,
                expiry,
            )),
            auth_failures: RwLock::new(HashMap::new()),
            mutual_auth_sessions: RwLock::new(HashMap::new()),
        })
    }

    /// Get public key bytes
    #[cfg(feature = "mesh")]
    pub fn public_key_bytes(&self) -> Vec<u8> {
        self.verifying_key.to_bytes().to_vec()
    }

    #[cfg(not(feature = "mesh"))]
    pub fn public_key_bytes(&self) -> Vec<u8> {
        Vec::new()
    }

    // ========================================================================
    // Bloom Filter Management
    // ========================================================================

    /// Rotate bloom filters if needed
    fn maybe_rotate_bloom_filters(&self) {
        let needs_rotation = {
            let current = self.used_challenges.read().unwrap();
            current.is_expired()
        };

        if needs_rotation {
            // Swap current with next, create new next
            let expiry = Duration::from_secs(CHALLENGE_EXPIRY_SECS * 2);
            let new_filter = BloomFilter::new(
                BLOOM_EXPECTED_INSERTIONS,
                BLOOM_FALSE_POSITIVE_RATE,
                expiry,
            );

            let mut current = self.used_challenges.write().unwrap();
            let mut next = self.used_challenges_next.write().unwrap();

            // Next becomes current, new becomes next
            std::mem::swap(&mut *current, &mut *next);
            *next = new_filter;

            debug!("Rotated challenge bloom filters");
        }
    }

    /// Check if a challenge has been used (with rotation)
    fn is_challenge_used(&self, challenge_hash: &[u8]) -> bool {
        self.maybe_rotate_bloom_filters();

        // Check both filters to handle rotation edge case
        let current = self.used_challenges.read().unwrap();
        let next = self.used_challenges_next.read().unwrap();

        current.might_contain(challenge_hash) || next.might_contain(challenge_hash)
    }

    /// Mark a challenge as used
    fn mark_challenge_used(&self, challenge_hash: &[u8]) {
        self.maybe_rotate_bloom_filters();

        let mut current = self.used_challenges.write().unwrap();
        current.insert(challenge_hash);
    }

    // ========================================================================
    // Challenge Generation
    // ========================================================================

    /// Generate an authentication challenge bound to a specific peer
    #[cfg(feature = "mesh")]
    pub fn generate_challenge(&self, target_hub_id: &str) -> AuthChallenge {
        use rand::rngs::OsRng;
        use rand::RngCore;

        let mut challenge = vec![0u8; 32];
        let mut nonce = vec![0u8; 16];
        OsRng.fill_bytes(&mut challenge);
        OsRng.fill_bytes(&mut nonce);

        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let auth_challenge = AuthChallenge {
            challenge,
            nonce,
            timestamp,
            challenger_hub_id: self.get_hub_id(),
            responder_hub_id: target_hub_id.to_string(),
        };

        // Store pending challenge (keyed by hash of challenge bytes)
        let challenge_hash = self.hash_challenge(&auth_challenge);
        {
            let mut pending = self.pending_challenges.write().unwrap();
            pending.insert(challenge_hash, auth_challenge.clone());
        }

        // Clean up old pending challenges
        self.cleanup_pending_challenges();

        auth_challenge
    }

    #[cfg(not(feature = "mesh"))]
    pub fn generate_challenge(&self, target_hub_id: &str) -> AuthChallenge {
        AuthChallenge {
            challenge: vec![0u8; 32],
            nonce: vec![0u8; 16],
            timestamp: 0,
            challenger_hub_id: self.get_hub_id(),
            responder_hub_id: target_hub_id.to_string(),
        }
    }

    /// Create a hash of challenge for tracking
    fn hash_challenge(&self, challenge: &AuthChallenge) -> Vec<u8> {
        // Simple hash combining all challenge fields
        let bytes = challenge.to_signing_bytes();
        // Use FNV-1a for simplicity (not cryptographic, just for HashMap key)
        let mut hash: u64 = 14695981039346656037;
        for byte in &bytes {
            hash ^= *byte as u64;
            hash = hash.wrapping_mul(0x100000001b3);
        }
        hash.to_be_bytes().to_vec()
    }

    /// Clean up expired pending challenges
    fn cleanup_pending_challenges(&self) {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let mut pending = self.pending_challenges.write().unwrap();
        pending.retain(|_, challenge| {
            now.saturating_sub(challenge.timestamp) < CHALLENGE_EXPIRY_SECS
        });
    }

    // ========================================================================
    // Challenge Response (Signing)
    // ========================================================================

    /// Sign a challenge to create a response (with full binding)
    #[cfg(feature = "mesh")]
    pub fn sign_challenge(&self, challenge: &AuthChallenge) -> AuthResponse {
        use ed25519_dalek::Signer;

        // Sign the full bound challenge data
        let signing_bytes = challenge.to_signing_bytes();
        let signature = self.signing_key.sign(&signing_bytes);

        AuthResponse {
            challenge: challenge.challenge.clone(),
            nonce: challenge.nonce.clone(),
            timestamp: challenge.timestamp,
            signature: signature.to_bytes().to_vec(),
            public_key: self.public_key_bytes(),
            responder_hub_id: self.get_hub_id(),
            challenger_hub_id: challenge.challenger_hub_id.clone(),
        }
    }

    #[cfg(not(feature = "mesh"))]
    pub fn sign_challenge(&self, challenge: &AuthChallenge) -> AuthResponse {
        AuthResponse {
            challenge: challenge.challenge.clone(),
            nonce: challenge.nonce.clone(),
            timestamp: challenge.timestamp,
            signature: Vec::new(),
            public_key: Vec::new(),
            responder_hub_id: self.get_hub_id(),
            challenger_hub_id: challenge.challenger_hub_id.clone(),
        }
    }

    // ========================================================================
    // Response Verification (with all security checks)
    // ========================================================================

    /// Verify an authentication response with full security checks
    #[cfg(feature = "mesh")]
    pub fn verify_response(&self, response: &AuthResponse) -> AuthResult {
        use ed25519_dalek::{Signature, Verifier, VerifyingKey};

        let responder_id = &response.responder_hub_id;

        // 1. Check rate limiting
        if let Some(result) = self.check_rate_limit(responder_id) {
            return result;
        }

        // 2. Verify this response is for us (binding check)
        if response.challenger_hub_id != self.get_hub_id() {
            warn!(
                "Challenge binding mismatch: expected {}, got {}",
                self.get_hub_id(),
                response.challenger_hub_id
            );
            self.record_failure(responder_id);
            return AuthResult::BindingMismatch;
        }

        // 3. Check timestamp validity (prevent old challenges)
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        if now.saturating_sub(response.timestamp) > CHALLENGE_EXPIRY_SECS {
            warn!("Challenge expired for {}", responder_id);
            self.record_failure(responder_id);
            return AuthResult::ChallengeExpired;
        }

        if response.timestamp > now + MAX_TIMESTAMP_SKEW_SECS {
            warn!("Challenge timestamp in future from {}", responder_id);
            self.record_failure(responder_id);
            return AuthResult::TimestampInvalid;
        }

        // 4. Reconstruct challenge and check if it's pending/valid
        let reconstructed = AuthChallenge {
            challenge: response.challenge.clone(),
            nonce: response.nonce.clone(),
            timestamp: response.timestamp,
            challenger_hub_id: response.challenger_hub_id.clone(),
            responder_hub_id: response.responder_hub_id.clone(),
        };
        let challenge_hash = self.hash_challenge(&reconstructed);

        // Verify we actually issued this challenge
        {
            let pending = self.pending_challenges.read().unwrap();
            if !pending.contains_key(&challenge_hash) {
                warn!("Unknown challenge from {}", responder_id);
                self.record_failure(responder_id);
                return AuthResult::ChallengeExpired;
            }
        }

        // 5. Check if challenge was already used (replay attack)
        let replay_check_key = {
            let mut key = response.challenge.clone();
            key.extend_from_slice(&response.nonce);
            key
        };
        if self.is_challenge_used(&replay_check_key) {
            error!(
                "🔴 REPLAY ATTACK DETECTED: Challenge reuse from {}",
                responder_id
            );
            self.record_failure(responder_id);
            return AuthResult::ChallengeReused;
        }

        // 6. Verify public key against pinned keys (TOFU)
        let is_new_peer = self.verify_or_pin_key(responder_id, &response.public_key);
        if let Err(result) = is_new_peer {
            self.record_failure(responder_id);
            return result;
        }
        let is_new_peer = is_new_peer.unwrap();

        // 7. Parse and verify signature
        let public_key_bytes: [u8; 32] = match response.public_key.clone().try_into() {
            Ok(bytes) => bytes,
            Err(_) => {
                warn!("Invalid public key length from {}", responder_id);
                self.record_failure(responder_id);
                return AuthResult::InvalidSignature;
            }
        };

        let verifying_key = match VerifyingKey::from_bytes(&public_key_bytes) {
            Ok(key) => key,
            Err(e) => {
                warn!("Invalid public key from {}: {}", responder_id, e);
                self.record_failure(responder_id);
                return AuthResult::InvalidSignature;
            }
        };

        let signature_bytes: [u8; 64] = match response.signature.clone().try_into() {
            Ok(bytes) => bytes,
            Err(_) => {
                warn!("Invalid signature length from {}", responder_id);
                self.record_failure(responder_id);
                return AuthResult::InvalidSignature;
            }
        };

        let signature = Signature::from_bytes(&signature_bytes);

        // Verify signature over the bound challenge data
        let signing_bytes = reconstructed.to_signing_bytes();
        match verifying_key.verify(&signing_bytes, &signature) {
            Ok(()) => {
                // Success! Mark challenge as used and clear failure count
                self.mark_challenge_used(&replay_check_key);
                self.reset_failures(responder_id);

                // Remove from pending
                {
                    let mut pending = self.pending_challenges.write().unwrap();
                    pending.remove(&challenge_hash);
                }

                // Update last used on pinned key
                {
                    let mut pinned = self.pinned_keys.write().unwrap();
                    if let Some(key) = pinned.get_mut(responder_id) {
                        key.touch();
                    }
                }

                info!(
                    "✓ Peer {} authenticated successfully{}",
                    responder_id,
                    if is_new_peer { " (new peer pinned)" } else { "" }
                );

                AuthResult::Success {
                    hub_id: responder_id.clone(),
                    is_new_peer,
                }
            }
            Err(e) => {
                warn!(
                    "✗ Peer {} authentication failed: {}",
                    responder_id, e
                );
                self.record_failure(responder_id);
                AuthResult::InvalidSignature
            }
        }
    }

    #[cfg(not(feature = "mesh"))]
    pub fn verify_response(&self, response: &AuthResponse) -> AuthResult {
        // Always pass when mesh auth is disabled
        AuthResult::Success {
            hub_id: response.responder_hub_id.clone(),
            is_new_peer: false,
        }
    }

    // ========================================================================
    // Public Key Pinning (TOFU)
    // ========================================================================

    /// Verify key against pinned keys, or pin if new peer (TOFU)
    /// Returns Ok(true) if new peer was pinned, Ok(false) if existing match,
    /// Err(AuthResult) if key mismatch
    fn verify_or_pin_key(&self, hub_id: &str, public_key: &[u8]) -> Result<bool, AuthResult> {
        let mut pinned = self.pinned_keys.write().unwrap();

        match pinned.get(hub_id) {
            Some(existing) => {
                if existing.matches(public_key) {
                    Ok(false) // Existing key matches
                } else {
                    warn!(
                        "🔴 KEY MISMATCH: Hub {} presented different key than pinned!",
                        hub_id
                    );
                    warn!(
                        "   This could indicate: MITM attack, key compromise, or unauthorized rotation"
                    );
                    Err(AuthResult::KeyMismatch {
                        hub_id: hub_id.to_string(),
                    })
                }
            }
            None => {
                // First time seeing this peer - pin their key (TOFU)
                info!(
                    "📌 Pinning public key for new peer: {} (TOFU)",
                    hub_id
                );
                pinned.insert(hub_id.to_string(), PinnedKey::new(public_key.to_vec()));
                Ok(true)
            }
        }
    }

    /// Manually pin a peer's public key (for pre-shared keys)
    pub fn pin_peer_key(&self, hub_id: &str, public_key: &[u8]) {
        let mut pinned = self.pinned_keys.write().unwrap();
        pinned.insert(hub_id.to_string(), PinnedKey::new(public_key.to_vec()));
        info!("Manually pinned public key for peer: {}", hub_id);
    }

    /// Remove a pinned key
    pub fn unpin_peer_key(&self, hub_id: &str) {
        let mut pinned = self.pinned_keys.write().unwrap();
        pinned.remove(hub_id);
        debug!("Removed pinned key for peer: {}", hub_id);
    }

    /// Initiate key rotation for a peer
    #[cfg(feature = "mesh")]
    pub fn handle_key_rotation(&self, request: &KeyRotationRequest) -> Result<()> {
        use ed25519_dalek::{Signature, Verifier, VerifyingKey};

        let mut pinned = self.pinned_keys.write().unwrap();

        let existing = pinned.get(&request.hub_id).ok_or_else(|| {
            anyhow::anyhow!("Cannot rotate key for unknown peer: {}", request.hub_id)
        })?;

        // Verify signature with old key
        let signing_data = format!(
            "{}:{}:{}",
            request.hub_id,
            base64::Engine::encode(&base64::engine::general_purpose::STANDARD, &request.new_public_key),
            request.timestamp
        );

        let old_key_bytes: [u8; 32] = existing
            .public_key
            .clone()
            .try_into()
            .map_err(|_| anyhow::anyhow!("Invalid existing key length"))?;
        let old_verifying_key = VerifyingKey::from_bytes(&old_key_bytes)?;

        let old_sig_bytes: [u8; 64] = request
            .signature_old_key
            .clone()
            .try_into()
            .map_err(|_| anyhow::anyhow!("Invalid old signature length"))?;
        let old_signature = Signature::from_bytes(&old_sig_bytes);

        old_verifying_key.verify(signing_data.as_bytes(), &old_signature)?;

        // Verify signature with new key (proves possession)
        let new_key_bytes: [u8; 32] = request
            .new_public_key
            .clone()
            .try_into()
            .map_err(|_| anyhow::anyhow!("Invalid new key length"))?;
        let new_verifying_key = VerifyingKey::from_bytes(&new_key_bytes)?;

        let new_sig_bytes: [u8; 64] = request
            .signature_new_key
            .clone()
            .try_into()
            .map_err(|_| anyhow::anyhow!("Invalid new signature length"))?;
        let new_signature = Signature::from_bytes(&new_sig_bytes);

        new_verifying_key.verify(signing_data.as_bytes(), &new_signature)?;

        // Start rotation
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let pinned_key = pinned.get_mut(&request.hub_id).unwrap();
        pinned_key.rotation_key = Some(request.new_public_key.clone());
        pinned_key.rotation_started = Some(now);

        info!(
            "✓ Key rotation initiated for {}: grace period {}s",
            request.hub_id, KEY_ROTATION_GRACE_SECS
        );

        Ok(())
    }

    #[cfg(not(feature = "mesh"))]
    pub fn handle_key_rotation(&self, _request: &KeyRotationRequest) -> Result<()> {
        Ok(())
    }

    /// Complete key rotation after grace period
    pub fn complete_key_rotation(&self, hub_id: &str) -> Result<()> {
        let mut pinned = self.pinned_keys.write().unwrap();

        let key = pinned
            .get_mut(hub_id)
            .ok_or_else(|| anyhow::anyhow!("No pinned key for {}", hub_id))?;

        let rotation_key = key
            .rotation_key
            .take()
            .ok_or_else(|| anyhow::anyhow!("No rotation in progress for {}", hub_id))?;

        let rotation_started = key.rotation_started.take().unwrap_or(0);
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        if now - rotation_started < KEY_ROTATION_GRACE_SECS {
            // Put it back - not ready yet
            key.rotation_key = Some(rotation_key);
            key.rotation_started = Some(rotation_started);
            return Err(anyhow::anyhow!(
                "Rotation grace period not elapsed ({}s remaining)",
                KEY_ROTATION_GRACE_SECS - (now - rotation_started)
            ));
        }

        key.public_key = rotation_key;
        key.pinned_at = now;

        info!("✓ Key rotation completed for {}", hub_id);
        Ok(())
    }

    // ========================================================================
    // Rate Limiting
    // ========================================================================

    /// Check rate limiting for a peer
    fn check_rate_limit(&self, hub_id: &str) -> Option<AuthResult> {
        let failures = self.auth_failures.read().unwrap();
        if let Some(tracker) = failures.get(hub_id) {
            if tracker.is_blocked() {
                if let Some(remaining) = tracker.remaining_block_time() {
                    return Some(AuthResult::Blocked {
                        remaining_secs: remaining.as_secs(),
                    });
                }
            }
            if tracker.needs_backoff() {
                let backoff = tracker.backoff_duration();
                let elapsed = tracker.last_failure.elapsed();
                if elapsed < backoff {
                    return Some(AuthResult::RateLimited {
                        remaining_secs: (backoff - elapsed).as_secs(),
                    });
                }
            }
        }
        None
    }

    /// Record an authentication failure
    fn record_failure(&self, hub_id: &str) {
        let mut failures = self.auth_failures.write().unwrap();
        let tracker = failures
            .entry(hub_id.to_string())
            .or_insert_with(AuthFailureTracker::new);
        tracker.record_failure();
    }

    /// Reset failure count on success
    fn reset_failures(&self, hub_id: &str) {
        let mut failures = self.auth_failures.write().unwrap();
        if let Some(tracker) = failures.get_mut(hub_id) {
            tracker.reset();
        }
    }

    // ========================================================================
    // Mutual Authentication
    // ========================================================================

    /// Start mutual authentication with a peer
    pub fn start_mutual_auth(&self, peer_hub_id: &str) -> AuthChallenge {
        let challenge = self.generate_challenge(peer_hub_id);

        let mut sessions = self.mutual_auth_sessions.write().unwrap();
        let session = sessions
            .entry(peer_hub_id.to_string())
            .or_insert_with(MutualAuthSession::new);

        session.state = MutualAuthState::ChallengeSent {
            challenge: challenge.clone(),
            sent_at: Instant::now(),
        };
        session.started_at = Instant::now();

        challenge
    }

    /// Process their response and prepare for reverse verification
    pub fn process_mutual_auth_response(
        &self,
        response: &AuthResponse,
    ) -> (AuthResult, Option<AuthChallenge>) {
        let result = self.verify_response(response);

        match &result {
            AuthResult::Success { hub_id, .. } => {
                // Update session state
                let mut sessions = self.mutual_auth_sessions.write().unwrap();
                if let Some(session) = sessions.get_mut(hub_id) {
                    session.state = MutualAuthState::TheirResponseVerified {
                        their_hub_id: hub_id.clone(),
                    };
                }

                // They should now challenge us - this is handled by respond_to_challenge
                (result, None)
            }
            _ => {
                // Failed - update session
                let mut sessions = self.mutual_auth_sessions.write().unwrap();
                if let Some(session) = sessions.get_mut(&response.responder_hub_id) {
                    session.state = MutualAuthState::Failed {
                        reason: format!("{:?}", result),
                    };
                }
                (result, None)
            }
        }
    }

    /// Respond to a challenge from a peer (for mutual auth)
    pub fn respond_to_challenge(&self, challenge: &AuthChallenge) -> Result<AuthResponse> {
        // Verify the challenge is addressed to us
        if challenge.responder_hub_id != self.get_hub_id() {
            return Err(anyhow::anyhow!(
                "Challenge not addressed to us: expected {}, got {}",
                self.get_hub_id(),
                challenge.responder_hub_id
            ));
        }

        // Check timestamp validity
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        if now.saturating_sub(challenge.timestamp) > CHALLENGE_EXPIRY_SECS {
            return Err(anyhow::anyhow!("Challenge expired"));
        }

        if challenge.timestamp > now + MAX_TIMESTAMP_SKEW_SECS {
            return Err(anyhow::anyhow!("Challenge timestamp in future"));
        }

        Ok(self.sign_challenge(challenge))
    }

    /// Complete mutual authentication after verifying their response
    pub fn complete_mutual_auth(&self, peer_hub_id: &str) -> bool {
        let mut sessions = self.mutual_auth_sessions.write().unwrap();
        if let Some(session) = sessions.get_mut(peer_hub_id) {
            match &session.state {
                MutualAuthState::TheirResponseVerified { their_hub_id } => {
                    session.state = MutualAuthState::MutuallyAuthenticated {
                        peer_hub_id: their_hub_id.clone(),
                        completed_at: Instant::now(),
                    };
                    info!(
                        "🤝 Mutual authentication complete with {}",
                        peer_hub_id
                    );
                    return true;
                }
                _ => {}
            }
        }
        false
    }

    /// Check if we have mutual auth with a peer
    pub fn is_mutually_authenticated(&self, peer_hub_id: &str) -> bool {
        let sessions = self.mutual_auth_sessions.read().unwrap();
        if let Some(session) = sessions.get(peer_hub_id) {
            matches!(
                session.state,
                MutualAuthState::MutuallyAuthenticated { .. }
            )
        } else {
            false
        }
    }

    /// Clean up expired mutual auth sessions
    pub fn cleanup_mutual_auth_sessions(&self) {
        let mut sessions = self.mutual_auth_sessions.write().unwrap();
        sessions.retain(|_, session| !session.is_expired());
    }

    // ========================================================================
    // Message Signing (for non-challenge messages)
    // ========================================================================

    /// Sign arbitrary message
    #[cfg(feature = "mesh")]
    pub fn sign_message(&self, message: &[u8]) -> Vec<u8> {
        use ed25519_dalek::Signer;
        self.signing_key.sign(message).to_bytes().to_vec()
    }

    #[cfg(not(feature = "mesh"))]
    pub fn sign_message(&self, _message: &[u8]) -> Vec<u8> {
        Vec::new()
    }

    /// Verify a message signature from a peer
    #[cfg(feature = "mesh")]
    pub fn verify_peer_signature(
        &self,
        message: &[u8],
        signature: &[u8],
        peer_public_key: &[u8],
    ) -> bool {
        use ed25519_dalek::{Signature, Verifier, VerifyingKey};

        let Ok(public_key_bytes): Result<[u8; 32], _> = peer_public_key.try_into() else {
            return false;
        };

        let Ok(verifying_key) = VerifyingKey::from_bytes(&public_key_bytes) else {
            return false;
        };

        let Ok(signature_bytes): Result<[u8; 64], _> = signature.try_into() else {
            return false;
        };

        let signature = Signature::from_bytes(&signature_bytes);

        verifying_key.verify(message, &signature).is_ok()
    }

    #[cfg(not(feature = "mesh"))]
    pub fn verify_peer_signature(
        &self,
        _message: &[u8],
        _signature: &[u8],
        _peer_public_key: &[u8],
    ) -> bool {
        true
    }

    // ========================================================================
    // Statistics and Diagnostics
    // ========================================================================

    /// Get authentication statistics
    pub fn get_auth_stats(&self) -> AuthStats {
        let pinned = self.pinned_keys.read().unwrap();
        let failures = self.auth_failures.read().unwrap();
        let pending = self.pending_challenges.read().unwrap();
        let sessions = self.mutual_auth_sessions.read().unwrap();

        let blocked_peers: Vec<String> = failures
            .iter()
            .filter(|(_, t)| t.is_blocked())
            .map(|(id, _)| id.clone())
            .collect();

        let mutually_authenticated: Vec<String> = sessions
            .iter()
            .filter(|(_, s)| {
                matches!(
                    s.state,
                    MutualAuthState::MutuallyAuthenticated { .. }
                )
            })
            .map(|(id, _)| id.clone())
            .collect();

        AuthStats {
            pinned_peers: pinned.len(),
            pending_challenges: pending.len(),
            blocked_peers,
            mutually_authenticated,
        }
    }
}

/// Authentication statistics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthStats {
    pub pinned_peers: usize,
    pub pending_challenges: usize,
    pub blocked_peers: Vec<String>,
    pub mutually_authenticated: Vec<String>,
}

impl Default for MeshAuth {
    fn default() -> Self {
        Self::new()
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(all(test, feature = "mesh"))]
mod tests {
    use super::*;

    #[test]
    fn test_challenge_response_with_binding() {
        let auth = MeshAuth::new();
        auth.set_hub_id("challenger-hub");

        let challenge = auth.generate_challenge("responder-hub");

        // Verify challenge is bound correctly
        assert_eq!(challenge.challenger_hub_id, "challenger-hub");
        assert_eq!(challenge.responder_hub_id, "responder-hub");
        assert_eq!(challenge.challenge.len(), 32);
        assert_eq!(challenge.nonce.len(), 16);

        // Create response
        let responder_auth = MeshAuth::new();
        responder_auth.set_hub_id("responder-hub");

        let response = responder_auth.sign_challenge(&challenge);

        // Verify response has correct binding
        assert_eq!(response.responder_hub_id, "responder-hub");
        assert_eq!(response.challenger_hub_id, "challenger-hub");

        // Pin the responder's key before verification (simulating TOFU)
        auth.pin_peer_key("responder-hub", &responder_auth.public_key_bytes());

        // Verify
        let result = auth.verify_response(&response);
        assert!(
            matches!(result, AuthResult::Success { hub_id, .. } if hub_id == "responder-hub"),
            "Expected success, got {:?}",
            result
        );
    }

    #[test]
    fn test_challenge_reuse_blocked() {
        let auth = MeshAuth::new();
        auth.set_hub_id("challenger-hub");

        let responder_auth = MeshAuth::new();
        responder_auth.set_hub_id("responder-hub");
        auth.pin_peer_key("responder-hub", &responder_auth.public_key_bytes());

        let challenge = auth.generate_challenge("responder-hub");
        let response = responder_auth.sign_challenge(&challenge);

        // First verification should succeed
        let result = auth.verify_response(&response);
        assert!(matches!(result, AuthResult::Success { .. }));

        // Need to regenerate the challenge since it was removed from pending
        let challenge2 = auth.generate_challenge("responder-hub");
        let response2 = responder_auth.sign_challenge(&challenge2);

        // Use the same nonce/challenge in a crafted response (simulate replay)
        let replay_response = AuthResponse {
            challenge: response.challenge.clone(),
            nonce: response.nonce.clone(),
            timestamp: response.timestamp,
            signature: response.signature.clone(),
            public_key: response.public_key.clone(),
            responder_hub_id: response.responder_hub_id.clone(),
            challenger_hub_id: response.challenger_hub_id.clone(),
        };

        // Re-add to pending to simulate the attack
        let fake_challenge = AuthChallenge {
            challenge: replay_response.challenge.clone(),
            nonce: replay_response.nonce.clone(),
            timestamp: replay_response.timestamp,
            challenger_hub_id: replay_response.challenger_hub_id.clone(),
            responder_hub_id: replay_response.responder_hub_id.clone(),
        };
        {
            let hash = auth.hash_challenge(&fake_challenge);
            let mut pending = auth.pending_challenges.write().unwrap();
            pending.insert(hash, fake_challenge);
        }

        // Replay should be blocked by bloom filter
        let result = auth.verify_response(&replay_response);
        assert!(
            matches!(result, AuthResult::ChallengeReused),
            "Expected ChallengeReused, got {:?}",
            result
        );
    }

    #[test]
    fn test_key_pinning_tofu() {
        let auth = MeshAuth::new();
        auth.set_hub_id("challenger-hub");

        let responder_auth = MeshAuth::new();
        responder_auth.set_hub_id("responder-hub");

        let challenge = auth.generate_challenge("responder-hub");
        let response = responder_auth.sign_challenge(&challenge);

        // First auth should pin the key (TOFU)
        let result = auth.verify_response(&response);
        assert!(
            matches!(result, AuthResult::Success { is_new_peer: true, .. }),
            "Expected success with new peer, got {:?}",
            result
        );

        // Key should now be pinned
        assert!(auth.is_peer_key_pinned("responder-hub"));
    }

    #[test]
    fn test_key_mismatch_blocked() {
        let auth = MeshAuth::new();
        auth.set_hub_id("challenger-hub");

        let responder_auth1 = MeshAuth::new();
        responder_auth1.set_hub_id("responder-hub");

        // Pin first key
        auth.pin_peer_key("responder-hub", &responder_auth1.public_key_bytes());

        // Try to auth with different key
        let responder_auth2 = MeshAuth::new();
        responder_auth2.set_hub_id("responder-hub");

        let challenge = auth.generate_challenge("responder-hub");
        let response = responder_auth2.sign_challenge(&challenge);

        // Should fail due to key mismatch
        let result = auth.verify_response(&response);
        assert!(
            matches!(result, AuthResult::KeyMismatch { .. }),
            "Expected KeyMismatch, got {:?}",
            result
        );
    }

    #[test]
    fn test_binding_mismatch() {
        let auth = MeshAuth::new();
        auth.set_hub_id("challenger-hub");

        let responder_auth = MeshAuth::new();
        responder_auth.set_hub_id("responder-hub");
        auth.pin_peer_key("responder-hub", &responder_auth.public_key_bytes());

        let challenge = auth.generate_challenge("responder-hub");

        // Create response but tamper with challenger_hub_id
        let mut response = responder_auth.sign_challenge(&challenge);
        response.challenger_hub_id = "different-hub".to_string();

        let result = auth.verify_response(&response);
        assert!(
            matches!(result, AuthResult::BindingMismatch),
            "Expected BindingMismatch, got {:?}",
            result
        );
    }

    #[test]
    fn test_rate_limiting() {
        let auth = MeshAuth::new();
        auth.set_hub_id("challenger-hub");

        // Record failures
        for _ in 0..MAX_AUTH_FAILURES {
            auth.record_failure("bad-peer");
        }

        // Should now be blocked
        let result = auth.check_rate_limit("bad-peer");
        assert!(
            matches!(result, Some(AuthResult::Blocked { .. })),
            "Expected Blocked, got {:?}",
            result
        );
    }

    #[test]
    fn test_bloom_filter_basic() {
        let mut bloom = BloomFilter::new(1000, 0.01, Duration::from_secs(60));

        let item1 = b"challenge1";
        let item2 = b"challenge2";

        // Initially not in filter
        assert!(!bloom.might_contain(item1));
        assert!(!bloom.might_contain(item2));

        // Add item1
        bloom.insert(item1);

        // item1 should be found, item2 should not
        assert!(bloom.might_contain(item1));
        assert!(!bloom.might_contain(item2));
    }

    #[test]
    fn test_mutual_auth_flow() {
        let hub_a = MeshAuth::new();
        hub_a.set_hub_id("hub-a");

        let hub_b = MeshAuth::new();
        hub_b.set_hub_id("hub-b");

        // Exchange keys (pre-shared or from previous auth)
        hub_a.pin_peer_key("hub-b", &hub_b.public_key_bytes());
        hub_b.pin_peer_key("hub-a", &hub_a.public_key_bytes());

        // Hub A starts mutual auth with Hub B
        let challenge_to_b = hub_a.start_mutual_auth("hub-b");

        // Hub B responds
        let response_from_b = hub_b.respond_to_challenge(&challenge_to_b).unwrap();

        // Hub A verifies B's response
        let (result, _) = hub_a.process_mutual_auth_response(&response_from_b);
        assert!(matches!(result, AuthResult::Success { .. }));

        // Now Hub B challenges Hub A (reverse direction)
        let challenge_to_a = hub_b.generate_challenge("hub-a");
        let response_from_a = hub_a.respond_to_challenge(&challenge_to_a).unwrap();

        // Hub B verifies A's response
        hub_b.pin_peer_key("hub-a", &hub_a.public_key_bytes());
        let result = hub_b.verify_response(&response_from_a);
        assert!(matches!(result, AuthResult::Success { .. }));

        // Complete mutual auth on both sides
        hub_a.complete_mutual_auth("hub-b");
        hub_b.complete_mutual_auth("hub-a");

        assert!(hub_a.is_mutually_authenticated("hub-b"));
        assert!(hub_b.is_mutually_authenticated("hub-a"));
    }

    #[test]
    fn test_key_pinning() {
        let auth = MeshAuth::new();
        let public_key = auth.public_key_bytes();

        auth.pin_peer_key("peer-1", &public_key);

        assert!(auth.is_peer_key_pinned("peer-1"));
        assert!(!auth.is_peer_key_pinned("peer-2"));

        auth.unpin_peer_key("peer-1");
        assert!(!auth.is_peer_key_pinned("peer-1"));
    }

    #[test]
    fn test_message_signing() {
        let auth = MeshAuth::new();
        let message = b"Hello, mesh!";

        let signature = auth.sign_message(message);
        let public_key = auth.public_key_bytes();

        assert!(auth.verify_peer_signature(message, &signature, &public_key));

        // Tampered message should fail
        assert!(!auth.verify_peer_signature(b"tampered", &signature, &public_key));
    }
}

/*
 * 鏡
 * Trust is earned. Verification is required.
 * h(x) ≥ 0. Always.
 */
