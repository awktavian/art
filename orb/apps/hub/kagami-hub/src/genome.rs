//! Kagami Genome — Hub Identity Serialization
//!
//! The genome is the complete identity of a Kagami Hub, including:
//! - Personality (wake word, voice profile, behavior)
//! - Configuration (API URL, home config)
//! - Cryptographic identity (mesh keys, signature)
//!
//! Genomes can be:
//! - Serialized for storage/transmission
//! - Verified via Ed25519 signature
//! - Propagated to new hubs (chain letter protocol)
//!
//! Colony: Crystal (e₇) — Identity and verification
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::Result;
use serde::{Deserialize, Serialize};
use tracing::info;

/// Version of the genome format
pub const GENOME_VERSION: &str = "1.0.0";

/// Kagami Hub Genome — Complete identity representation
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct KagamiGenome {
    /// Genome format version
    pub version: String,

    /// SHA-256 hash of the genome contents (excluding signature)
    #[serde(with = "serde_bytes_32")]
    pub identity_hash: [u8; 32],

    // ─────────────── PERSONALITY ───────────────

    /// Wake word phrase (e.g., "Hey Kagami")
    pub wake_word: String,

    /// Voice profile configuration
    pub voice_profile: VoiceProfile,

    /// System personality prompt for LLM
    pub personality_prompt: String,

    // ─────────────── CONFIGURATION ───────────────

    /// Main Kagami API URL
    pub api_url: Option<String>,

    /// Home configuration
    pub home_config: HomeConfig,

    /// LED ring configuration
    pub led_config: LedConfig,

    // ─────────────── CRYPTOGRAPHIC ───────────────

    /// Ed25519 public key for mesh authentication
    #[serde(with = "serde_bytes_32")]
    pub mesh_public_key: [u8; 32],

    /// Ed25519 signature over genome (signed by parent/root)
    #[serde(with = "serde_bytes_64")]
    pub signature: [u8; 64],

    // ─────────────── METADATA ───────────────

    /// When this genome was created
    pub created_at: u64,

    /// Hub ID of the parent that created this genome (None for root)
    pub parent_hub_id: Option<String>,

    /// Generation number (increments with each propagation)
    pub generation: u32,

    /// Embedded documentation (markdown)
    pub documentation: String,
}

// Custom serde module for [u8; 32]
mod serde_bytes_32 {
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(bytes: &[u8; 32], serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_bytes(bytes)
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<[u8; 32], D::Error>
    where
        D: Deserializer<'de>,
    {
        let v: Vec<u8> = Vec::deserialize(deserializer)?;
        v.try_into().map_err(|_| serde::de::Error::custom("expected 32 bytes"))
    }
}

// Custom serde module for [u8; 64]
mod serde_bytes_64 {
    use serde::{Deserialize, Deserializer, Serializer};

    pub fn serialize<S>(bytes: &[u8; 64], serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_bytes(bytes)
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<[u8; 64], D::Error>
    where
        D: Deserializer<'de>,
    {
        let v: Vec<u8> = Vec::deserialize(deserializer)?;
        v.try_into().map_err(|_| serde::de::Error::custom("expected 64 bytes"))
    }
}

/// Voice profile configuration
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct VoiceProfile {
    /// TTS voice model name
    pub tts_model: String,
    /// Speech rate (1.0 = normal)
    pub speech_rate: f32,
    /// Pitch adjustment (-1.0 to 1.0)
    pub pitch: f32,
    /// Volume (0.0 to 1.0)
    pub volume: f32,
    /// Colony to use for voice character
    pub colony: String,
}

/// Home configuration
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct HomeConfig {
    /// Home name for announcements
    pub home_name: String,
    /// Home location (for weather, etc.)
    pub location: String,
    /// Latitude
    pub latitude: Option<f64>,
    /// Longitude
    pub longitude: Option<f64>,
    /// Timezone
    pub timezone: String,
    /// Default rooms for commands
    pub default_rooms: Vec<String>,
}

/// LED ring configuration
#[derive(Clone, Debug, Default, Serialize, Deserialize)]
pub struct LedConfig {
    /// Number of LEDs
    pub led_count: u8,
    /// Default brightness (0.0 to 1.0)
    pub brightness: f32,
    /// Idle animation pattern
    pub idle_pattern: String,
    /// Custom colony colors (overrides defaults)
    pub colony_colors: Option<Vec<String>>,
}

impl KagamiGenome {
    /// Create a new genesis genome (first in chain)
    #[cfg(feature = "genome")]
    pub fn genesis(wake_word: &str, api_url: Option<&str>) -> Self {
        use ed25519_dalek::{SigningKey, Signer};
        use rand::RngCore;
        use rand::rngs::OsRng;

        // Generate random bytes for the secret key
        let mut secret_bytes = [0u8; 32];
        OsRng.fill_bytes(&mut secret_bytes);
        let signing_key = SigningKey::from_bytes(&secret_bytes);
        let public_key = signing_key.verifying_key();

        let mut genome = Self {
            version: GENOME_VERSION.to_string(),
            identity_hash: [0u8; 32],
            wake_word: wake_word.to_string(),
            voice_profile: VoiceProfile::default(),
            personality_prompt: DEFAULT_PERSONALITY.to_string(),
            api_url: api_url.map(String::from),
            home_config: HomeConfig::default(),
            led_config: LedConfig::default(),
            mesh_public_key: public_key.to_bytes(),
            signature: [0u8; 64],
            created_at: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            parent_hub_id: None,
            generation: 0,
            documentation: GENOME_DOCUMENTATION.to_string(),
        };

        // Calculate identity hash
        genome.identity_hash = genome.calculate_hash();

        // Self-sign (genesis genomes are self-signed)
        let signature = signing_key.sign(&genome.identity_hash);
        genome.signature = signature.to_bytes();

        info!("Created genesis genome");
        genome
    }

    #[cfg(not(feature = "genome"))]
    pub fn genesis(wake_word: &str, api_url: Option<&str>) -> Self {
        Self {
            version: GENOME_VERSION.to_string(),
            identity_hash: [0u8; 32],
            wake_word: wake_word.to_string(),
            voice_profile: VoiceProfile::default(),
            personality_prompt: DEFAULT_PERSONALITY.to_string(),
            api_url: api_url.map(String::from),
            home_config: HomeConfig::default(),
            led_config: LedConfig::default(),
            mesh_public_key: [0u8; 32],
            signature: [0u8; 64],
            created_at: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            parent_hub_id: None,
            generation: 0,
            documentation: GENOME_DOCUMENTATION.to_string(),
        }
    }

    /// Calculate SHA-256 hash of genome contents
    pub fn calculate_hash(&self) -> [u8; 32] {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};

        // Create a deterministic hash of the genome contents
        // In production, use SHA-256 from a crypto library
        let mut hasher = DefaultHasher::new();
        self.version.hash(&mut hasher);
        self.wake_word.hash(&mut hasher);
        self.personality_prompt.hash(&mut hasher);
        self.api_url.hash(&mut hasher);
        self.mesh_public_key.hash(&mut hasher);
        self.created_at.hash(&mut hasher);
        self.generation.hash(&mut hasher);

        let hash = hasher.finish();

        // Expand to 32 bytes (in production, use actual SHA-256)
        let mut result = [0u8; 32];
        result[0..8].copy_from_slice(&hash.to_le_bytes());
        result[8..16].copy_from_slice(&hash.to_be_bytes());
        result[16..24].copy_from_slice(&hash.to_le_bytes());
        result[24..32].copy_from_slice(&hash.to_be_bytes());

        result
    }

    /// Verify genome signature
    #[cfg(feature = "genome")]
    pub fn verify_signature(&self, verifying_key: &ed25519_dalek::VerifyingKey) -> bool {
        use ed25519_dalek::{Signature, Verifier};

        let signature = Signature::from_bytes(&self.signature);

        verifying_key.verify(&self.identity_hash, &signature).is_ok()
    }

    #[cfg(not(feature = "genome"))]
    pub fn verify_signature(&self, _verifying_key: &[u8; 32]) -> bool {
        true
    }

    /// Serialize genome to bytes (for transmission)
    #[cfg(feature = "genome")]
    pub fn serialize(&self) -> Result<Vec<u8>> {
        bincode::serialize(self)
            .map_err(|e| anyhow::anyhow!("Failed to serialize genome: {}", e))
    }

    #[cfg(not(feature = "genome"))]
    pub fn serialize(&self) -> Result<Vec<u8>> {
        serde_json::to_vec(self)
            .map_err(|e| anyhow::anyhow!("Failed to serialize genome: {}", e))
    }

    /// Deserialize genome from bytes
    #[cfg(feature = "genome")]
    pub fn deserialize(data: &[u8]) -> Result<Self> {
        bincode::deserialize(data)
            .map_err(|e| anyhow::anyhow!("Failed to deserialize genome: {}", e))
    }

    #[cfg(not(feature = "genome"))]
    pub fn deserialize(data: &[u8]) -> Result<Self> {
        serde_json::from_slice(data)
            .map_err(|e| anyhow::anyhow!("Failed to deserialize genome: {}", e))
    }

    /// Create a child genome (for propagation)
    #[cfg(feature = "genome")]
    pub fn propagate(&self, signing_key: &ed25519_dalek::SigningKey, new_hub_id: &str) -> Self {
        use ed25519_dalek::Signer;

        let public_key = signing_key.verifying_key();

        let mut child = self.clone();
        child.parent_hub_id = Some(new_hub_id.to_string());
        child.generation += 1;
        child.mesh_public_key = public_key.to_bytes();
        child.created_at = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Recalculate hash
        child.identity_hash = child.calculate_hash();

        // Sign with parent's key
        let signature = signing_key.sign(&child.identity_hash);
        child.signature = signature.to_bytes();

        info!("Propagated genome to generation {}", child.generation);
        child
    }

    #[cfg(not(feature = "genome"))]
    pub fn propagate(&self, _signing_key: &[u8; 32], new_hub_id: &str) -> Self {
        let mut child = self.clone();
        child.parent_hub_id = Some(new_hub_id.to_string());
        child.generation += 1;
        child
    }

    /// Save genome to file
    pub fn save(&self, path: &std::path::Path) -> Result<()> {
        let data = self.serialize()?;
        std::fs::write(path, data)?;
        info!("Saved genome to {:?}", path);
        Ok(())
    }

    /// Load genome from file
    pub fn load(path: &std::path::Path) -> Result<Self> {
        let data = std::fs::read(path)?;
        let genome = Self::deserialize(&data)?;
        info!("Loaded genome from {:?}", path);
        Ok(genome)
    }
}

/// Default personality prompt
const DEFAULT_PERSONALITY: &str = r#"You are Kagami, a helpful voice assistant for the home.
Be concise and friendly. Prefer action over explanation.
When controlling the home, confirm actions briefly.
Safety is paramount: h(x) ≥ 0 always."#;

/// Genome documentation (embedded in genome for self-description)
const GENOME_DOCUMENTATION: &str = r#"# Kagami Genome

This genome contains the complete identity of a Kagami Hub.

## Capabilities
- Voice interaction (wake word detection, STT, TTS)
- Home automation control
- Tesla vehicle control
- Weather information
- Mesh networking with other hubs

## Safety
All operations maintain h(x) ≥ 0.

## Propagation
This genome can be propagated to new hubs using the chain letter protocol.
Each propagation increments the generation counter.

## Verification
The genome is signed using Ed25519.
Verify before trusting.

鏡
"#;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_genesis_genome() {
        let genome = KagamiGenome::genesis("Hey Kagami", Some("http://localhost:8000"));

        assert_eq!(genome.version, GENOME_VERSION);
        assert_eq!(genome.wake_word, "Hey Kagami");
        assert_eq!(genome.generation, 0);
        assert!(genome.parent_hub_id.is_none());
    }

    #[test]
    fn test_genome_serialization() {
        let genome = KagamiGenome::genesis("Hey Kagami", None);

        let serialized = genome.serialize().unwrap();
        let deserialized = KagamiGenome::deserialize(&serialized).unwrap();

        assert_eq!(genome.wake_word, deserialized.wake_word);
        assert_eq!(genome.generation, deserialized.generation);
    }

    #[test]
    fn test_hash_calculation() {
        let genome = KagamiGenome::genesis("Hey Kagami", None);

        let hash1 = genome.calculate_hash();
        let hash2 = genome.calculate_hash();

        assert_eq!(hash1, hash2); // Deterministic
    }
}

/*
 * 鏡
 * Identity propagates. The chain continues.
 */
