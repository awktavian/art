//! Kagami Mesh SDK
//!
//! A cross-platform SDK for building mesh-networked applications with UniFFI bindings
//! for iOS, Android, and Desktop clients.
//!
//! # Features
//!
//! - **Authentication**: Ed25519-based identity management and challenge-response authentication
//! - **Synchronization**: CRDT implementations (LWW-Register, G-Counter, OR-Set) with vector clocks
//! - **Encryption**: XChaCha20-Poly1305 authenticated encryption with X25519 key exchange
//! - **Transport**: WebSocket client with automatic reconnection and circuit breaker
//! - **Voice Streaming**: Cross-platform voice capture, WebSocket streaming, and playback
//!
//! # Platform Support
//!
//! Via UniFFI bindings:
//! - iOS/visionOS/watchOS (Swift)
//! - Android (Kotlin)
//! - Desktop (Rust native)
//!
//! # Example
//!
//! ```rust,no_run
//! use kagami_mesh_sdk::{Identity, ChallengeProtocol};
//!
//! // Generate a new identity
//! let identity = Identity::generate();
//! println!("Peer ID: {}", identity.peer_id());
//!
//! // Create challenge protocol for authentication
//! let protocol = ChallengeProtocol::new(identity);
//! ```
//!
//! # Voice Streaming Example
//!
//! ```rust,ignore
//! use kagami_mesh_sdk::streaming::{VoiceStreamClient, VoiceConfig};
//!
//! // Create voice streaming client
//! let config = VoiceConfig::with_endpoint("wss://api.kagami.io/ws/voice");
//! let (mut client, events) = VoiceStreamClient::new(config);
//!
//! // Connect and start streaming
//! client.connect().await?;
//! client.start_session().await?;
//! client.send_samples(&audio_samples).await?;
//! client.end_session().await?;
//! ```
//!
//! # Safety
//!
//! ```text
//! h(x) >= 0 always
//! ```
//!
//! All operations maintain the safety invariant.

pub mod api;
pub mod auth;
pub mod circuit_breaker;
pub mod crypto;
pub mod discovery;
pub mod storage;
pub mod streaming;
pub mod sync;
pub mod transport;

// Re-export main types for convenience
pub use auth::{
    AuthChallenge, AuthResponse, ChallengeError, ChallengeProtocol, ChallengeState, Identity,
    IdentityError, PublicKey, SecretKey, Signature,
};
pub use crypto::{
    decrypt, encrypt, CipherError, EphemeralSecret, Nonce, SecretKey as CipherKey, SharedSecret,
    StaticSecret, X25519Error, X25519PublicKey,
};
pub use sync::{CrdtError, GCounter, LwwRegister, OrSet, VectorClock, VectorClockOrdering};
pub use transport::{
    ConnectionConfig, ConnectionEvent, ConnectionState, ConnectionStateMachine, WebSocketClient,
    WebSocketError, WebSocketEvent, WebSocketMessage,
    // New transport abstractions
    TransportState, TransportEvent, TransportConfig, RetryStrategy,
    ConnectionStateObserver, NoOpStateObserver,
    CommandResult, CommandRetryService, FibonacciBackoff, RetryStats,
};
pub use circuit_breaker::{CircuitBreaker, CircuitState, get_circuit_breaker};

// Re-export storage types
pub use storage::{
    IdentityStorage, IdentityStorageConfig, IdentityStorageError, IdentityLoadResult,
    StoredIdentity, StorageAccessibility, InMemoryIdentityStorage,
    keys as storage_keys,
};

// Re-export discovery types
pub use discovery::{
    DiscoveredHub, DiscoveryConfig, DiscoveryEvent, DiscoveryMethod, DiscoveryState,
    HubDiscoveryDelegate, HubDiscoveryService, NoOpDiscoveryDelegate,
    KAGAMI_HUB_SERVICE_TYPE, DEFAULT_HUB_PORT,
};

// Re-export voice streaming types
pub use streaming::{
    // Types
    AudioChunk, AudioChunkData, AudioEncoding, AudioFormat, EarconType, TranscriptionResult,
    TtsResponse, TtsResponseData, VoiceConfig, VoiceMessage, VoiceStreamState,
    // Voice capture
    VoiceCapture, VoiceCaptureError, VoiceCaptureParams, StubVoiceCapture,
    // Voice streaming
    VoiceStreamClient, VoiceStreamError, VoiceStreamEvent, MeshVoiceStream,
    // Voice playback
    VoicePlayback, VoicePlaybackError, PlaybackState, PlaybackProgress, EarconCache,
    VolumeSettings,
    // Utilities
    calculate_rms_db, detect_silence, f32_to_i16, i16_to_f32, bytes_to_i16, i16_to_bytes,
};

// Re-export unified API types
pub use api::{
    // Types
    Light, Shade, AudioZone, HvacState, LockState, FireplaceState, TvMountState,
    RoomModel, HomeStatus, DevicesResponse, RoomsResponse,
    HealthResponse, ClientRegistrationRequest, SceneInfo, ScenesResponse,
    LightsRequest, ShadesRequest, FireplaceRequest, ClimateRequest, AnnounceRequest,
    WebSocketMessageType, ContextUpdateMessage, SuggestedAction, HomeUpdateMessage,
    ApiError, ApiErrorKind, ClientType, ColonyColor, ColonyColors,
    // Client
    KagamiApiClient, ApiClientConfig, ApiConnectionState,
    // Functions
    safety_color, validate_light_level, validate_shade_position,
    validate_volume, validate_temperature, generate_client_id,
    scene_endpoint, tv_endpoint, locks_endpoint,
    // Constants
    DEFAULT_API_URL, LOCAL_MDNS_URL, DISCOVERY_CANDIDATES, endpoints,
};

/// SDK version
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Protocol version for compatibility checking
pub const PROTOCOL_VERSION: u32 = 1;

// UniFFI scaffolding
uniffi::setup_scaffolding!();

// ============================================================================
// UniFFI error type
// ============================================================================

/// Error type for UniFFI exports.
#[derive(Debug, thiserror::Error, uniffi::Error)]
pub enum MeshSdkError {
    #[error("Invalid input: {message}")]
    InvalidInput { message: String },

    #[error("Crypto error: {message}")]
    CryptoError { message: String },

    #[error("Parse error: {message}")]
    ParseError { message: String },
}

// ============================================================================
// UniFFI-exported types and functions
// ============================================================================

/// Generate a new random Ed25519 identity.
///
/// Returns the identity as a base64-encoded secret key string.
#[uniffi::export]
pub fn generate_identity() -> String {
    let identity = Identity::generate();
    identity.to_base64()
}

/// Get the peer ID (hex-encoded public key) from a base64-encoded identity.
#[uniffi::export]
pub fn get_peer_id(identity_base64: &str) -> Result<String, MeshSdkError> {
    let identity = Identity::from_base64(identity_base64).map_err(|e| MeshSdkError::InvalidInput {
        message: e.to_string(),
    })?;
    Ok(identity.peer_id())
}

/// Sign a message with an identity.
///
/// Returns the signature as a hex-encoded string.
#[uniffi::export]
pub fn sign_message(identity_base64: &str, message: &[u8]) -> Result<String, MeshSdkError> {
    let identity = Identity::from_base64(identity_base64).map_err(|e| MeshSdkError::InvalidInput {
        message: e.to_string(),
    })?;
    let signature = identity.sign(message);
    Ok(signature.to_hex())
}

/// Verify a signature on a message.
#[uniffi::export]
pub fn verify_signature(
    public_key_hex: &str,
    message: &[u8],
    signature_hex: &str,
) -> Result<bool, MeshSdkError> {
    let public_key = PublicKey::from_hex(public_key_hex).map_err(|e| MeshSdkError::InvalidInput {
        message: e.to_string(),
    })?;
    let signature = Signature::from_hex(signature_hex).map_err(|e| MeshSdkError::InvalidInput {
        message: e.to_string(),
    })?;

    match public_key.verify(message, &signature) {
        Ok(()) => Ok(true),
        Err(_) => Ok(false),
    }
}

/// Generate a new random XChaCha20-Poly1305 encryption key.
///
/// Returns the key as a hex-encoded string.
#[uniffi::export]
pub fn generate_cipher_key() -> String {
    let key = crypto::SecretKey::generate();
    key.to_hex()
}

/// Encrypt data with XChaCha20-Poly1305.
///
/// Returns the ciphertext as a hex-encoded string (includes nonce).
#[uniffi::export]
pub fn encrypt_data(key_hex: &str, plaintext: &[u8]) -> Result<String, MeshSdkError> {
    let key = crypto::SecretKey::from_hex(key_hex).map_err(|e| MeshSdkError::CryptoError {
        message: e.to_string(),
    })?;
    let ciphertext = encrypt(&key, plaintext).map_err(|e| MeshSdkError::CryptoError {
        message: e.to_string(),
    })?;
    Ok(hex::encode(ciphertext))
}

/// Decrypt data with XChaCha20-Poly1305.
#[uniffi::export]
pub fn decrypt_data(key_hex: &str, ciphertext_hex: &str) -> Result<Vec<u8>, MeshSdkError> {
    let key = crypto::SecretKey::from_hex(key_hex).map_err(|e| MeshSdkError::CryptoError {
        message: e.to_string(),
    })?;
    let ciphertext = hex::decode(ciphertext_hex).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })?;
    decrypt(&key, &ciphertext).map_err(|e| MeshSdkError::CryptoError {
        message: e.to_string(),
    })
}

/// X25519 key pair result for UniFFI.
#[derive(uniffi::Record)]
pub struct X25519KeyPair {
    pub secret_key_hex: String,
    pub public_key_hex: String,
}

/// Generate an X25519 key pair.
///
/// Returns the secret and public keys as hex-encoded strings.
#[uniffi::export]
pub fn generate_x25519_keypair() -> X25519KeyPair {
    let secret = StaticSecret::generate();
    let public = secret.public_key();
    X25519KeyPair {
        secret_key_hex: secret.to_hex(),
        public_key_hex: public.to_hex(),
    }
}

/// Perform X25519 Diffie-Hellman key exchange.
///
/// Returns the derived encryption key as a hex string.
#[uniffi::export]
pub fn x25519_derive_key(
    secret_key_hex: &str,
    peer_public_key_hex: &str,
) -> Result<String, MeshSdkError> {
    let secret = StaticSecret::from_hex(secret_key_hex).map_err(|e| MeshSdkError::CryptoError {
        message: e.to_string(),
    })?;
    let peer_public = X25519PublicKey::from_hex(peer_public_key_hex).map_err(|e| MeshSdkError::CryptoError {
        message: e.to_string(),
    })?;
    let shared = secret.diffie_hellman(&peer_public);
    let cipher_key = shared.to_cipher_key();
    Ok(cipher_key.to_hex())
}

/// Create a new vector clock for a node.
#[uniffi::export]
pub fn vector_clock_new(node_id: &str) -> String {
    let vc = VectorClock::with_node(node_id);
    serde_json::to_string(&vc).unwrap_or_default()
}

/// Increment a vector clock for a node.
#[uniffi::export]
pub fn vector_clock_increment(clock_json: &str, node_id: &str) -> Result<String, MeshSdkError> {
    let mut vc: VectorClock = serde_json::from_str(clock_json).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })?;
    vc.increment(node_id);
    serde_json::to_string(&vc).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })
}

/// Merge two vector clocks.
#[uniffi::export]
pub fn vector_clock_merge(clock1_json: &str, clock2_json: &str) -> Result<String, MeshSdkError> {
    let mut vc1: VectorClock = serde_json::from_str(clock1_json).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })?;
    let vc2: VectorClock = serde_json::from_str(clock2_json).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })?;
    vc1.merge(&vc2);
    serde_json::to_string(&vc1).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })
}

/// Compare two vector clocks.
///
/// Returns: "before", "after", "concurrent", or "equal".
#[uniffi::export]
pub fn vector_clock_compare(clock1_json: &str, clock2_json: &str) -> Result<String, MeshSdkError> {
    let vc1: VectorClock = serde_json::from_str(clock1_json).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })?;
    let vc2: VectorClock = serde_json::from_str(clock2_json).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })?;

    let result = match vc1.compare(&vc2) {
        VectorClockOrdering::HappensBefore => "before",
        VectorClockOrdering::HappensAfter => "after",
        VectorClockOrdering::Concurrent => "concurrent",
        VectorClockOrdering::Equal => "equal",
    };

    Ok(result.to_string())
}

/// Create a new G-Counter.
#[uniffi::export]
pub fn g_counter_new() -> String {
    let counter = GCounter::new();
    serde_json::to_string(&counter).unwrap_or_default()
}

/// Increment a G-Counter.
#[uniffi::export]
pub fn g_counter_increment(counter_json: &str, node_id: &str) -> Result<String, MeshSdkError> {
    let mut counter: GCounter = serde_json::from_str(counter_json).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })?;
    counter.increment(node_id);
    serde_json::to_string(&counter).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })
}

/// Get the value of a G-Counter.
#[uniffi::export]
pub fn g_counter_value(counter_json: &str) -> Result<u64, MeshSdkError> {
    let counter: GCounter = serde_json::from_str(counter_json).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })?;
    Ok(counter.value())
}

/// Merge two G-Counters.
#[uniffi::export]
pub fn g_counter_merge(counter1_json: &str, counter2_json: &str) -> Result<String, MeshSdkError> {
    let mut counter1: GCounter = serde_json::from_str(counter1_json).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })?;
    let counter2: GCounter = serde_json::from_str(counter2_json).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })?;
    counter1.merge(&counter2);
    serde_json::to_string(&counter1).map_err(|e| MeshSdkError::ParseError {
        message: e.to_string(),
    })
}

// ============================================================================
// UniFFI Object types
// ============================================================================

/// A mesh network identity for UniFFI.
#[derive(uniffi::Object)]
pub struct MeshIdentity {
    inner: Identity,
}

#[uniffi::export]
impl MeshIdentity {
    /// Create a new random identity.
    #[uniffi::constructor]
    pub fn new() -> Self {
        Self {
            inner: Identity::generate(),
        }
    }

    /// Create an identity from a base64-encoded secret key.
    #[uniffi::constructor]
    pub fn from_base64(encoded: &str) -> Result<Self, MeshSdkError> {
        let inner = Identity::from_base64(encoded).map_err(|e| MeshSdkError::InvalidInput {
            message: e.to_string(),
        })?;
        Ok(Self { inner })
    }

    /// Get the peer ID (hex-encoded public key).
    pub fn peer_id(&self) -> String {
        self.inner.peer_id()
    }

    /// Get the public key as hex.
    pub fn public_key_hex(&self) -> String {
        self.inner.public_key().to_hex()
    }

    /// Export as base64-encoded secret key.
    pub fn to_base64(&self) -> String {
        self.inner.to_base64()
    }

    /// Sign a message.
    pub fn sign(&self, message: &[u8]) -> String {
        self.inner.sign(message).to_hex()
    }

    /// Verify a signature.
    pub fn verify(&self, message: &[u8], signature_hex: &str) -> Result<bool, MeshSdkError> {
        let signature = Signature::from_hex(signature_hex).map_err(|e| MeshSdkError::InvalidInput {
            message: e.to_string(),
        })?;
        match self.inner.verify(message, &signature) {
            Ok(()) => Ok(true),
            Err(_) => Ok(false),
        }
    }
}

impl Default for MeshIdentity {
    fn default() -> Self {
        Self::new()
    }
}

/// A connection state tracker for UniFFI.
#[derive(uniffi::Object)]
pub struct MeshConnection {
    state_machine: std::sync::Mutex<ConnectionStateMachine>,
}

#[uniffi::export]
impl MeshConnection {
    /// Create a new connection tracker with default config.
    #[uniffi::constructor]
    pub fn new() -> Self {
        Self {
            state_machine: std::sync::Mutex::new(ConnectionStateMachine::with_defaults()),
        }
    }

    /// Create with custom failure threshold.
    #[uniffi::constructor]
    pub fn with_failure_threshold(threshold: u32) -> Self {
        let config = ConnectionConfig {
            failure_threshold: threshold,
            ..Default::default()
        };
        Self {
            state_machine: std::sync::Mutex::new(ConnectionStateMachine::new(config)),
        }
    }

    /// Get the current state as a string.
    pub fn state(&self) -> String {
        let sm = self.state_machine.lock().unwrap();
        format!("{:?}", sm.state())
    }

    /// Check if connected.
    pub fn is_connected(&self) -> bool {
        let sm = self.state_machine.lock().unwrap();
        sm.is_connected()
    }

    /// Signal a connection attempt.
    pub fn on_connect(&self) -> Result<String, MeshSdkError> {
        let mut sm = self.state_machine.lock().unwrap();
        sm.process_event(ConnectionEvent::Connect)
            .map(|s| format!("{:?}", s))
            .map_err(|e| MeshSdkError::InvalidInput {
                message: e.to_string(),
            })
    }

    /// Signal a successful connection.
    pub fn on_connected(&self) -> Result<String, MeshSdkError> {
        let mut sm = self.state_machine.lock().unwrap();
        sm.process_event(ConnectionEvent::Connected)
            .map(|s| format!("{:?}", s))
            .map_err(|e| MeshSdkError::InvalidInput {
                message: e.to_string(),
            })
    }

    /// Signal a connection failure.
    pub fn on_failure(&self, reason: &str) -> Result<String, MeshSdkError> {
        let mut sm = self.state_machine.lock().unwrap();
        sm.process_event(ConnectionEvent::ConnectionFailed(reason.to_string()))
            .map(|s| format!("{:?}", s))
            .map_err(|e| MeshSdkError::InvalidInput {
                message: e.to_string(),
            })
    }

    /// Signal disconnection.
    pub fn on_disconnect(&self, reason: &str) -> Result<String, MeshSdkError> {
        let mut sm = self.state_machine.lock().unwrap();
        sm.process_event(ConnectionEvent::Disconnected(reason.to_string()))
            .map(|s| format!("{:?}", s))
            .map_err(|e| MeshSdkError::InvalidInput {
                message: e.to_string(),
            })
    }

    /// Get the current backoff in milliseconds.
    pub fn backoff_ms(&self) -> u64 {
        let sm = self.state_machine.lock().unwrap();
        sm.backoff_duration().as_millis() as u64
    }

    /// Get the failure count.
    pub fn failure_count(&self) -> u32 {
        let sm = self.state_machine.lock().unwrap();
        sm.failure_count()
    }

    /// Check if circuit breaker recovery is due.
    pub fn should_attempt_recovery(&self) -> bool {
        let sm = self.state_machine.lock().unwrap();
        sm.should_attempt_recovery()
    }

    /// Reset the state machine.
    pub fn reset(&self) {
        let mut sm = self.state_machine.lock().unwrap();
        sm.reset();
    }
}

impl Default for MeshConnection {
    fn default() -> Self {
        Self::new()
    }
}

/*
 * 鏡
 * Mesh SDK: Secure. Consistent. Connected.
 * h(x) ≥ 0. Always.
 */

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_identity() {
        let identity_b64 = generate_identity();
        assert!(!identity_b64.is_empty());

        let peer_id = get_peer_id(&identity_b64).unwrap();
        assert_eq!(peer_id.len(), 64); // 32 bytes = 64 hex chars
    }

    #[test]
    fn test_sign_verify() {
        let identity_b64 = generate_identity();
        let peer_id = get_peer_id(&identity_b64).unwrap();
        let message = b"test message";

        let signature = sign_message(&identity_b64, message).unwrap();
        let valid = verify_signature(&peer_id, message, &signature).unwrap();

        assert!(valid);
    }

    #[test]
    fn test_encrypt_decrypt() {
        let key = generate_cipher_key();
        let plaintext = b"secret data";

        let ciphertext = encrypt_data(&key, plaintext).unwrap();
        let decrypted = decrypt_data(&key, &ciphertext).unwrap();

        assert_eq!(plaintext.as_slice(), decrypted.as_slice());
    }

    #[test]
    fn test_x25519_key_exchange() {
        let alice = generate_x25519_keypair();
        let bob = generate_x25519_keypair();

        let alice_key = x25519_derive_key(&alice.secret_key_hex, &bob.public_key_hex).unwrap();
        let bob_key = x25519_derive_key(&bob.secret_key_hex, &alice.public_key_hex).unwrap();

        assert_eq!(alice_key, bob_key);
    }

    #[test]
    fn test_vector_clock_operations() {
        let clock1 = vector_clock_new("node1");
        let clock1 = vector_clock_increment(&clock1, "node1").unwrap();

        let clock2 = vector_clock_new("node2");
        let clock2 = vector_clock_increment(&clock2, "node2").unwrap();

        let comparison = vector_clock_compare(&clock1, &clock2).unwrap();
        assert_eq!(comparison, "concurrent");

        let merged = vector_clock_merge(&clock1, &clock2).unwrap();
        let vc: VectorClock = serde_json::from_str(&merged).unwrap();
        assert_eq!(vc.get("node1"), 1);
        assert_eq!(vc.get("node2"), 1);
    }

    #[test]
    fn test_g_counter_operations() {
        let counter = g_counter_new();
        let counter = g_counter_increment(&counter, "node1").unwrap();
        let counter = g_counter_increment(&counter, "node1").unwrap();

        let value = g_counter_value(&counter).unwrap();
        assert_eq!(value, 2);
    }

    #[test]
    fn test_mesh_identity_object() {
        let identity = MeshIdentity::new();
        let peer_id = identity.peer_id();
        assert_eq!(peer_id.len(), 64);

        let message = b"test";
        let signature = identity.sign(message);
        let valid = identity.verify(message, &signature).unwrap();
        assert!(valid);
    }

    #[test]
    fn test_mesh_connection_object() {
        let conn = MeshConnection::new();
        assert_eq!(conn.state(), "Disconnected");
        assert!(!conn.is_connected());

        conn.on_connect().unwrap();
        assert_eq!(conn.state(), "Connecting");

        conn.on_connected().unwrap();
        assert_eq!(conn.state(), "Connected");
        assert!(conn.is_connected());
    }
}
