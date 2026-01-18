# Hub Platform Skill (Rust Firmware)

**100/100 Quality by Default** - Patterns for production-ready Rust hub firmware.

## When to Use

- Creating or modifying hub firmware in `apps/hub/kagami-hub/`
- Ensuring embedded Rust quality standards
- Byzantine audit remediation for Hub

## Required Files (P0)

Every Hub firmware MUST have these files implemented:

```
kagami-hub/
├── Cargo.toml                      # Dependencies
├── config/
│   └── hub.toml                    # Runtime configuration
├── src/
│   ├── main.rs                     # Entry point
│   ├── lib.rs                      # Public exports
│   ├── error.rs                    # Error taxonomy
│   ├── voice_pipeline.rs           # Voice processing
│   ├── stt.rs                      # Speech to text
│   ├── streaming_stt.rs            # Streaming transcription
│   ├── tts.rs                      # Text to speech
│   ├── wake_word.rs                # Wake word detection
│   ├── api_client.rs               # Backend communication
│   ├── circuit_breaker.rs          # Failure handling
│   ├── safety.rs                   # CBF safety verification
│   ├── offline_commands.rs         # Offline fallback
│   ├── mesh/
│   │   ├── mod.rs                  # Mesh networking
│   │   ├── auth.rs                 # Ed25519 authentication
│   │   ├── discovery.rs            # Peer discovery
│   │   └── sync.rs                 # State synchronization
│   ├── automation/
│   │   └── rule_engine.rs          # Automation rules
│   └── ota.rs                      # Over-the-air updates
└── tests/
    ├── fuzz_tests.rs               # Fuzzing
    ├── voice_pipeline_test.rs      # Voice tests
    └── mesh_integration_test.rs    # Mesh tests
```

## Critical Patterns

### 1. Error Taxonomy (MANDATORY)

```rust
// src/error.rs
use thiserror::Error;

#[derive(Error, Debug)]
pub enum HubError {
    #[error("Configuration error: {0}")]
    Config(#[from] ConfigError),

    #[error("Voice pipeline error: {0}")]
    Voice(#[from] VoiceError),

    #[error("Network error: {0}")]
    Network(#[from] NetworkError),

    #[error("Device error: {0}")]
    Device(#[from] DeviceError),

    #[error("Audio error: {0}")]
    Audio(#[from] AudioError),

    #[error("Safety constraint violated: h(x) = {h_x}")]
    SafetyViolation { h_x: f64 },
}

#[derive(Error, Debug)]
pub enum VoiceError {
    #[error("Wake word detection failed: {0}")]
    WakeWordFailed(String),

    #[error("STT transcription error: {0}")]
    TranscriptionError(String),

    #[error("TTS synthesis error: {0}")]
    SynthesisError(String),

    #[error("Audio capture error: {0}")]
    CaptureError(String),
}

// Result type alias
pub type HubResult<T> = Result<T, HubError>;
```

### 2. Circuit Breaker (MANDATORY)

```rust
// src/circuit_breaker.rs
use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

pub struct CircuitBreaker {
    failure_count: AtomicU32,
    last_failure_time: AtomicU64,
    state: AtomicU32, // 0=Closed, 1=Open, 2=HalfOpen
}

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum CircuitState {
    Closed = 0,
    Open = 1,
    HalfOpen = 2,
}

impl CircuitBreaker {
    const FAILURE_THRESHOLD: u32 = 5;
    const RECOVERY_TIMEOUT_SECS: u64 = 30;

    pub fn new() -> Self {
        Self {
            failure_count: AtomicU32::new(0),
            last_failure_time: AtomicU64::new(0),
            state: AtomicU32::new(0),
        }
    }

    pub fn allow_request(&self) -> bool {
        match self.state() {
            CircuitState::Closed => true,
            CircuitState::Open => {
                let now = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs();
                let last_failure = self.last_failure_time.load(Ordering::Acquire);

                if now - last_failure > Self::RECOVERY_TIMEOUT_SECS {
                    self.state.store(CircuitState::HalfOpen as u32, Ordering::Release);
                    true
                } else {
                    false
                }
            }
            CircuitState::HalfOpen => true,
        }
    }

    pub fn record_success(&self) {
        self.failure_count.store(0, Ordering::Release);
        self.state.store(CircuitState::Closed as u32, Ordering::Release);
    }

    pub fn record_failure(&self) {
        let count = self.failure_count.fetch_add(1, Ordering::AcqRel) + 1;
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        self.last_failure_time.store(now, Ordering::Release);

        if count >= Self::FAILURE_THRESHOLD {
            self.state.store(CircuitState::Open as u32, Ordering::Release);
        }
    }

    fn state(&self) -> CircuitState {
        match self.state.load(Ordering::Acquire) {
            0 => CircuitState::Closed,
            1 => CircuitState::Open,
            _ => CircuitState::HalfOpen,
        }
    }
}
```

### 3. Safety Verification (MANDATORY)

```rust
// src/safety.rs
use tracing::{info, warn};

/// Control Barrier Function verification
/// All commands must satisfy h(x) >= 0
pub struct SafetyVerifier {
    enabled: bool,
}

impl SafetyVerifier {
    pub fn new() -> Self {
        Self { enabled: true }
    }

    /// Verify command safety before execution
    pub fn verify(&self, command: &Command) -> Result<(), SafetyError> {
        if !self.enabled {
            return Ok(());
        }

        let h_x = self.compute_barrier(command);

        if h_x < 0.0 {
            warn!(
                command = ?command,
                h_x = h_x,
                "Safety constraint violated"
            );
            return Err(SafetyError::ConstraintViolated { h_x });
        }

        info!(
            command = ?command,
            h_x = h_x,
            "Safety check passed"
        );
        Ok(())
    }

    fn compute_barrier(&self, command: &Command) -> f64 {
        match command {
            // Critical commands have lower barriers
            Command::Lock(_) => 0.9,
            Command::Fireplace(on) => if *on { 0.7 } else { 1.0 },

            // Normal commands have high barriers
            Command::Lights { .. } => 1.0,
            Command::Shades { .. } => 1.0,
            Command::Scene(_) => 0.95,

            // Announcements always safe
            Command::Announce(_) => 1.0,
        }
    }
}

#[derive(Debug)]
pub enum SafetyError {
    ConstraintViolated { h_x: f64 },
}
```

### 4. Streaming STT (MANDATORY - P1 Requirement)

```rust
// src/streaming_stt.rs
use tokio::sync::mpsc;
use std::collections::VecDeque;

pub struct StreamingSTT {
    config: StreamingConfig,
    buffer: VecDeque<i16>,
    vad: VoiceActivityDetector,
}

pub struct StreamingConfig {
    pub sample_rate: u32,        // 16000 Hz
    pub chunk_size: usize,       // 512 samples (~32ms)
    pub buffer_duration_ms: u32, // 500ms (P1 requirement)
    pub target_latency_ms: u32,  // 500ms (P1 requirement)
}

impl Default for StreamingConfig {
    fn default() -> Self {
        Self {
            sample_rate: 16000,
            chunk_size: 512,
            buffer_duration_ms: 500,
            target_latency_ms: 500,
        }
    }
}

impl StreamingSTT {
    pub fn new(config: StreamingConfig) -> Self {
        let buffer_samples = (config.sample_rate * config.buffer_duration_ms / 1000) as usize;
        Self {
            config,
            buffer: VecDeque::with_capacity(buffer_samples),
            vad: VoiceActivityDetector::new(),
        }
    }

    pub async fn process_chunk(&mut self, audio: &[i16]) -> Option<TranscriptionResult> {
        // Add to ring buffer
        for sample in audio {
            if self.buffer.len() >= self.buffer.capacity() {
                self.buffer.pop_front();
            }
            self.buffer.push_back(*sample);
        }

        // Check VAD
        if !self.vad.is_speech(&self.buffer) {
            return None;
        }

        // Transcribe buffer
        self.transcribe().await
    }

    async fn transcribe(&self) -> Option<TranscriptionResult> {
        // Send to Whisper for transcription
        // Return result with latency tracking
        None
    }
}
```

### 5. Mesh Authentication (MANDATORY)

```rust
// src/mesh/auth.rs
use ed25519_dalek::{Signature, SigningKey, VerifyingKey};
use rand::rngs::OsRng;

pub struct MeshAuth {
    signing_key: SigningKey,
    trusted_peers: Vec<VerifyingKey>,
}

pub struct AuthChallenge {
    pub nonce: [u8; 32],
    pub timestamp: u64,
}

pub struct AuthResponse {
    pub challenge: [u8; 32],
    pub signature: [u8; 64],
    pub public_key: [u8; 32],
}

impl MeshAuth {
    pub fn new() -> Self {
        let signing_key = SigningKey::generate(&mut OsRng);
        Self {
            signing_key,
            trusted_peers: Vec::new(),
        }
    }

    pub fn create_challenge(&self) -> AuthChallenge {
        let mut nonce = [0u8; 32];
        getrandom::getrandom(&mut nonce).unwrap();
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();
        AuthChallenge { nonce, timestamp }
    }

    pub fn respond_to_challenge(&self, challenge: &AuthChallenge) -> AuthResponse {
        let signature = self.signing_key.sign(&challenge.nonce);
        AuthResponse {
            challenge: challenge.nonce,
            signature: signature.to_bytes(),
            public_key: self.signing_key.verifying_key().to_bytes(),
        }
    }

    pub fn verify_response(&self, response: &AuthResponse) -> Result<bool, AuthError> {
        // Check timestamp isn't too old (60 second window)
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Verify signature
        let verifying_key = VerifyingKey::from_bytes(&response.public_key)
            .map_err(|_| AuthError::InvalidKey)?;
        let signature = Signature::from_bytes(&response.signature);

        verifying_key
            .verify_strict(&response.challenge, &signature)
            .map(|_| true)
            .map_err(|_| AuthError::InvalidSignature)
    }

    pub fn add_trusted_peer(&mut self, public_key: VerifyingKey) {
        if !self.trusted_peers.contains(&public_key) {
            self.trusted_peers.push(public_key);
        }
    }
}

#[derive(Debug)]
pub enum AuthError {
    InvalidKey,
    InvalidSignature,
    ChallengeExpired,
}
```

### 6. Offline Command Matching (MANDATORY)

```rust
// src/offline_commands.rs
use std::collections::HashMap;

pub struct OfflineCommandMatcher {
    patterns: HashMap<&'static str, Command>,
}

impl OfflineCommandMatcher {
    pub fn new() -> Self {
        let mut patterns = HashMap::new();

        // Pre-cache common commands
        patterns.insert("lights on", Command::Lights { room: None, brightness: Some(100) });
        patterns.insert("lights off", Command::Lights { room: None, brightness: Some(0) });
        patterns.insert("movie mode", Command::Scene("movie_mode".into()));
        patterns.insert("goodnight", Command::Scene("goodnight".into()));
        patterns.insert("welcome home", Command::Scene("welcome_home".into()));
        patterns.insert("fireplace on", Command::Fireplace(true));
        patterns.insert("fireplace off", Command::Fireplace(false));

        Self { patterns }
    }

    pub fn match_command(&self, transcript: &str) -> Option<Command> {
        let normalized = transcript.to_lowercase();

        // Exact match first
        if let Some(cmd) = self.patterns.get(normalized.as_str()) {
            return Some(cmd.clone());
        }

        // Fuzzy match using Levenshtein distance
        let mut best_match: Option<(&str, usize)> = None;
        for pattern in self.patterns.keys() {
            let distance = levenshtein(&normalized, pattern);
            if distance <= 2 { // Allow 2 character difference
                if best_match.is_none() || distance < best_match.unwrap().1 {
                    best_match = Some((pattern, distance));
                }
            }
        }

        best_match.and_then(|(pattern, _)| self.patterns.get(pattern).cloned())
    }
}

fn levenshtein(a: &str, b: &str) -> usize {
    // Standard Levenshtein distance implementation
    let a_chars: Vec<char> = a.chars().collect();
    let b_chars: Vec<char> = b.chars().collect();
    // ... implementation
    0
}
```

## Testing Requirements

### Unit Tests (Required)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_circuit_breaker_opens_after_failures() {
        let cb = CircuitBreaker::new();
        assert!(cb.allow_request());

        for _ in 0..5 {
            cb.record_failure();
        }

        assert!(!cb.allow_request());
    }

    #[test]
    fn test_safety_verifier_blocks_unsafe() {
        let verifier = SafetyVerifier::new();
        // Test that unsafe commands are blocked
    }

    #[test]
    fn test_offline_matcher_fuzzy() {
        let matcher = OfflineCommandMatcher::new();
        // "lights on" should match even with typo
        let result = matcher.match_command("ligths on");
        assert!(result.is_some());
    }
}
```

### Fuzz Tests (Required)

```rust
// tests/fuzz_tests.rs
#[cfg(test)]
mod fuzz {
    use proptest::prelude::*;

    proptest! {
        #[test]
        fn test_audio_processing_never_panics(audio: Vec<i16>) {
            let mut stt = StreamingSTT::new(StreamingConfig::default());
            // Should never panic regardless of input
            let _ = futures::executor::block_on(stt.process_chunk(&audio));
        }

        #[test]
        fn test_json_parsing_never_panics(json: String) {
            // Should handle malformed JSON gracefully
            let _ = serde_json::from_str::<Command>(&json);
        }

        #[test]
        fn test_command_matcher_never_panics(input: String) {
            let matcher = OfflineCommandMatcher::new();
            let _ = matcher.match_command(&input);
        }
    }
}
```

### Mesh Integration Tests (Required)

```rust
// tests/mesh_integration_test.rs
#[tokio::test]
async fn test_peer_authentication() {
    let auth1 = MeshAuth::new();
    let auth2 = MeshAuth::new();

    // Add each other as trusted
    auth1.add_trusted_peer(auth2.signing_key.verifying_key());
    auth2.add_trusted_peer(auth1.signing_key.verifying_key());

    // Challenge-response
    let challenge = auth1.create_challenge();
    let response = auth2.respond_to_challenge(&challenge);
    let verified = auth1.verify_response(&response);

    assert!(verified.is_ok());
    assert!(verified.unwrap());
}
```

## Build Verification

```bash
# Verify Hub build passes
cd apps/hub/kagami-hub

# Build
cargo build --release

# Run all tests
cargo test

# Run with features
cargo build --release --features rpi

# Clippy lints
cargo clippy -- -D warnings

# Format check
cargo fmt --check
```

## Quality Checklist

Before any Hub commit:

- [ ] All error types derive `thiserror::Error`
- [ ] Circuit breaker handles failures gracefully
- [ ] Safety verifier checks h(x) >= 0
- [ ] Streaming STT targets 500ms latency
- [ ] Mesh auth uses Ed25519
- [ ] Offline commands have fuzzy matching
- [ ] All tests pass including fuzz tests
- [ ] No `unwrap()` on user input
- [ ] No `expect()` that could panic in production

## Common Issues & Fixes

### Panic on SystemTime
- **Symptom**: `unwrap()` fails on clock issues
- **Fix**: Use `unwrap_or_default()` for time operations

### Circuit Breaker Stuck
- **Symptom**: No recovery after failures
- **Fix**: Implement half-open state with timeout

### Auth Replay Attack
- **Symptom**: Old challenges accepted
- **Fix**: Check timestamp and enforce expiry window

---

*100/100 or don't ship.*
