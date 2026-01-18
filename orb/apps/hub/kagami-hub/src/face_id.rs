//! Face Identification Module for Hub
//!
//! Local face identification using cached embeddings from the Kagami API.
//! Works with UniFi Protect face detection events and cached embeddings.
//!
//! Features:
//! - Embedding-based face recognition
//! - Profile management and caching
//! - Signed face events for mesh propagation
//! - Real-time event streaming
//! - Enrollment via web UI
//!
//! Colony: Nexus (e₄) — Integration
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::Result;
use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::{broadcast, RwLock};
use tracing::{debug, info, warn, error};

// ============================================================================
// Configuration
// ============================================================================

/// Face identification configuration
#[derive(Debug, Clone)]
pub struct FaceIdConfig {
    /// Minimum confidence threshold for identification
    pub min_confidence: f32,
    /// Profile refresh interval (seconds)
    pub refresh_interval_secs: u64,
    /// Kagami API URL for profile loading
    pub api_url: Option<String>,
    /// API key for authentication
    pub api_key: Option<String>,
    /// Maximum profiles to cache
    pub max_profiles: usize,
    /// Enable signed events for mesh
    pub sign_events: bool,
}

impl Default for FaceIdConfig {
    fn default() -> Self {
        Self {
            min_confidence: 0.6,
            refresh_interval_secs: 3600, // 1 hour
            api_url: None,
            api_key: None,
            max_profiles: 100,
            sign_events: true,
        }
    }
}

// ============================================================================
// Face Profile
// ============================================================================

/// Face profile for visual recognition
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct FaceProfile {
    /// Unique identifier for the identity
    pub identity_id: String,
    /// Display name
    pub name: Option<String>,
    /// Face embedding vector (typically 512-dim from InsightFace/FaceNet)
    pub embedding: Vec<f32>,
    /// Confidence threshold for matching this profile
    pub threshold: f32,
    /// Quality score of the reference embedding (0.0 - 1.0)
    pub quality: f32,
    /// When the profile was last updated
    pub updated_at: u64,
    /// Optional metadata
    pub metadata: Option<serde_json::Value>,
}

impl FaceProfile {
    /// Create a new face profile
    pub fn new(identity_id: String, embedding: Vec<f32>) -> Self {
        Self {
            identity_id,
            name: None,
            embedding,
            threshold: 0.6,
            quality: 0.0,
            updated_at: current_timestamp(),
            metadata: None,
        }
    }

    /// Set the display name
    pub fn with_name(mut self, name: impl Into<String>) -> Self {
        self.name = Some(name.into());
        self
    }

    /// Set the confidence threshold
    pub fn with_threshold(mut self, threshold: f32) -> Self {
        self.threshold = threshold;
        self
    }

    /// Get display name or identity_id
    pub fn display_name(&self) -> &str {
        self.name.as_deref().unwrap_or(&self.identity_id)
    }
}

// ============================================================================
// Face Match Result
// ============================================================================

/// Result of face identification
#[derive(Debug, Clone)]
pub struct FaceMatch {
    /// Matched face profile (if any)
    pub profile: Option<FaceProfile>,
    /// Confidence score (0.0 - 1.0)
    pub confidence: f32,
    /// Was identification successful?
    pub is_identified: bool,
    /// Processing time in milliseconds
    pub processing_time_ms: u64,
    /// All candidate matches above threshold
    pub candidates: Vec<(String, f32)>,
}

impl FaceMatch {
    /// Create a successful match
    pub fn identified(profile: FaceProfile, confidence: f32, processing_time_ms: u64) -> Self {
        Self {
            profile: Some(profile),
            confidence,
            is_identified: true,
            processing_time_ms,
            candidates: vec![],
        }
    }

    /// Create an unidentified result
    pub fn unknown(processing_time_ms: u64) -> Self {
        Self {
            profile: None,
            confidence: 0.0,
            is_identified: false,
            processing_time_ms,
            candidates: vec![],
        }
    }

    /// Get identity ID if identified
    pub fn identity_id(&self) -> Option<&str> {
        self.profile.as_ref().map(|p| p.identity_id.as_str())
    }

    /// Get display name if identified
    pub fn display_name(&self) -> Option<&str> {
        self.profile.as_ref().map(|p| p.display_name())
    }
}

// ============================================================================
// Face Events
// ============================================================================

/// Events emitted by face identification system
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum FaceEvent {
    /// A face was detected and identified
    Identified {
        identity_id: String,
        name: Option<String>,
        confidence: f32,
        camera_id: Option<String>,
        timestamp: u64,
    },
    /// A face was detected but not identified
    Unknown {
        camera_id: Option<String>,
        timestamp: u64,
    },
    /// Profiles were loaded/refreshed
    ProfilesLoaded {
        count: usize,
        timestamp: u64,
    },
    /// Face enrollment started
    EnrollmentStarted {
        identity_id: String,
        timestamp: u64,
    },
    /// Face enrollment completed
    EnrollmentComplete {
        identity_id: String,
        success: bool,
        timestamp: u64,
    },
}

/// Signed face detection event for mesh propagation
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct SignedFaceEvent {
    /// Identity ID that was detected
    pub identity_id: String,
    /// Camera ID where detection occurred
    pub camera_id: String,
    /// Camera name
    pub camera_name: String,
    /// Match confidence (0-1)
    pub confidence: f32,
    /// Detection timestamp (Unix epoch seconds)
    pub timestamp: u64,
    /// Optional identity name
    pub name: Option<String>,
    /// Ed25519 signature (base64)
    pub signature: Option<String>,
    /// Hub ID that signed this event
    pub signer_hub_id: Option<String>,
}

// ============================================================================
// Face Identifier Service
// ============================================================================

/// Face identification service with async support
pub struct FaceIdentifier {
    config: FaceIdConfig,
    /// Registered face profiles by identity_id
    profiles: RwLock<HashMap<String, FaceProfile>>,
    /// Last profile update timestamp
    last_update: RwLock<Instant>,
    /// Event broadcaster
    event_tx: broadcast::Sender<FaceEvent>,
}

impl FaceIdentifier {
    /// Create a new face identifier
    pub fn new(config: FaceIdConfig) -> Self {
        let (event_tx, _) = broadcast::channel(100);
        Self {
            config,
            profiles: RwLock::new(HashMap::new()),
            last_update: RwLock::new(Instant::now()),
            event_tx,
        }
    }

    /// Create with default config
    pub fn default_service() -> Self {
        Self::new(FaceIdConfig::default())
    }

    /// Subscribe to face events
    pub fn subscribe(&self) -> broadcast::Receiver<FaceEvent> {
        self.event_tx.subscribe()
    }

    /// Register a face profile
    pub async fn register_profile(&self, profile: FaceProfile) {
        info!(
            "👤 Registered face profile: {} ({})",
            profile.display_name(),
            profile.identity_id
        );

        let mut profiles = self.profiles.write().await;

        // Enforce max profiles
        if profiles.len() >= self.config.max_profiles && !profiles.contains_key(&profile.identity_id) {
            // Remove oldest profile
            if let Some(oldest_id) = profiles.values()
                .min_by_key(|p| p.updated_at)
                .map(|p| p.identity_id.clone())
            {
                profiles.remove(&oldest_id);
            }
        }

        profiles.insert(profile.identity_id.clone(), profile);
    }

    /// Load profiles from Kagami API
    pub async fn load_profiles(&self) -> Result<usize> {
        let (api_url, api_key) = {
            let url = self.config.api_url.as_ref()
                .ok_or_else(|| anyhow::anyhow!("API URL not configured"))?;
            let key = self.config.api_key.as_ref()
                .ok_or_else(|| anyhow::anyhow!("API key not configured"))?;
            (url.clone(), key.clone())
        };

        let url = format!("{}/api/identities/face-profiles", api_url);
        debug!("Loading face profiles from {}", url);

        let client = reqwest::Client::new();
        let response = client
            .get(&url)
            .header("Authorization", format!("Bearer {}", api_key))
            .timeout(Duration::from_secs(30))
            .send()
            .await?;

        if !response.status().is_success() {
            return Err(anyhow::anyhow!(
                "Failed to load face profiles: {}",
                response.status()
            ));
        }

        let api_profiles: Vec<ApiFaceProfile> = response.json().await?;
        let count = api_profiles.len();

        let mut profiles = self.profiles.write().await;
        profiles.clear();

        for api_profile in api_profiles {
            let profile = FaceProfile {
                identity_id: api_profile.identity_id,
                name: api_profile.name,
                embedding: api_profile.face_embedding,
                threshold: api_profile.face_threshold.unwrap_or(self.config.min_confidence),
                quality: api_profile.face_quality.unwrap_or(0.0),
                updated_at: current_timestamp(),
                metadata: None,
            };
            profiles.insert(profile.identity_id.clone(), profile);
        }

        *self.last_update.write().await = Instant::now();

        info!("✅ Loaded {} face profiles", count);

        let _ = self.event_tx.send(FaceEvent::ProfilesLoaded {
            count,
            timestamp: current_timestamp(),
        });

        Ok(count)
    }

    /// Try to load profiles (returns Ok even if it fails, for graceful degradation)
    pub async fn try_load_profiles(&self) -> usize {
        match self.load_profiles().await {
            Ok(count) => count,
            Err(e) => {
                warn!("Failed to load face profiles: {}", e);
                0
            }
        }
    }

    /// Identify face from embedding vector
    pub async fn identify(&self, face_embedding: &[f32]) -> FaceMatch {
        let start = Instant::now();
        let profiles = self.profiles.read().await;

        if profiles.is_empty() {
            debug!("No face profiles registered");
            return FaceMatch::unknown(start.elapsed().as_millis() as u64);
        }

        let mut best_match: Option<(&FaceProfile, f32)> = None;
        let mut candidates = Vec::new();

        for profile in profiles.values() {
            let similarity = cosine_similarity(face_embedding, &profile.embedding);

            debug!(
                "Face {} similarity: {:.3} (threshold: {:.3})",
                profile.display_name(),
                similarity,
                profile.threshold
            );

            if similarity >= profile.threshold && similarity >= self.config.min_confidence {
                candidates.push((profile.identity_id.clone(), similarity));

                if let Some((_, best_sim)) = best_match {
                    if similarity > best_sim {
                        best_match = Some((profile, similarity));
                    }
                } else {
                    best_match = Some((profile, similarity));
                }
            }
        }

        let processing_time_ms = start.elapsed().as_millis() as u64;

        match best_match {
            Some((profile, confidence)) => {
                info!(
                    "🎯 Identified face: {} (confidence: {:.2}, {:.0}ms)",
                    profile.display_name(),
                    confidence,
                    processing_time_ms
                );

                let _ = self.event_tx.send(FaceEvent::Identified {
                    identity_id: profile.identity_id.clone(),
                    name: profile.name.clone(),
                    confidence,
                    camera_id: None,
                    timestamp: current_timestamp(),
                });

                let mut result = FaceMatch::identified(profile.clone(), confidence, processing_time_ms);
                result.candidates = candidates;
                result
            }
            None => {
                debug!("No face match found ({:.0}ms)", processing_time_ms);

                let _ = self.event_tx.send(FaceEvent::Unknown {
                    camera_id: None,
                    timestamp: current_timestamp(),
                });

                FaceMatch::unknown(processing_time_ms)
            }
        }
    }

    /// Identify with camera context
    pub async fn identify_from_camera(
        &self,
        face_embedding: &[f32],
        camera_id: &str,
    ) -> FaceMatch {
        let mut result = self.identify(face_embedding).await;

        // Re-emit event with camera ID
        if result.is_identified {
            let profile = result.profile.as_ref().unwrap();
            let _ = self.event_tx.send(FaceEvent::Identified {
                identity_id: profile.identity_id.clone(),
                name: profile.name.clone(),
                confidence: result.confidence,
                camera_id: Some(camera_id.to_string()),
                timestamp: current_timestamp(),
            });
        } else {
            let _ = self.event_tx.send(FaceEvent::Unknown {
                camera_id: Some(camera_id.to_string()),
                timestamp: current_timestamp(),
            });
        }

        result
    }

    /// Get profile by identity ID
    pub async fn get_profile(&self, identity_id: &str) -> Option<FaceProfile> {
        self.profiles.read().await.get(identity_id).cloned()
    }

    /// Get all registered profiles
    pub async fn get_all_profiles(&self) -> Vec<FaceProfile> {
        self.profiles.read().await.values().cloned().collect()
    }

    /// Get profile count
    pub async fn profile_count(&self) -> usize {
        self.profiles.read().await.len()
    }

    /// Check if profiles need refresh
    pub async fn needs_refresh(&self) -> bool {
        let elapsed = self.last_update.read().await.elapsed();
        elapsed > Duration::from_secs(self.config.refresh_interval_secs)
    }

    /// Refresh profiles if needed
    pub async fn refresh_if_needed(&self) -> Result<()> {
        if self.needs_refresh().await {
            self.load_profiles().await?;
        }
        Ok(())
    }

    /// Clear all profiles
    pub async fn clear(&self) {
        self.profiles.write().await.clear();
    }

    /// Remove a specific profile
    pub async fn remove_profile(&self, identity_id: &str) -> Option<FaceProfile> {
        self.profiles.write().await.remove(identity_id)
    }
}

// ============================================================================
// API Response Types
// ============================================================================

/// API response format for face profiles
#[derive(Debug, serde::Deserialize)]
struct ApiFaceProfile {
    identity_id: String,
    name: Option<String>,
    face_embedding: Vec<f32>,
    face_threshold: Option<f32>,
    face_quality: Option<f32>,
}

// ============================================================================
// Utility Functions
// ============================================================================

/// Calculate cosine similarity between two vectors
pub fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() || a.is_empty() {
        return 0.0;
    }

    let mut dot = 0.0f64;
    let mut norm_a = 0.0f64;
    let mut norm_b = 0.0f64;

    for (ai, bi) in a.iter().zip(b.iter()) {
        let ai = *ai as f64;
        let bi = *bi as f64;
        dot += ai * bi;
        norm_a += ai * ai;
        norm_b += bi * bi;
    }

    if norm_a == 0.0 || norm_b == 0.0 {
        return 0.0;
    }

    (dot / (norm_a.sqrt() * norm_b.sqrt())) as f32
}

/// Calculate Euclidean distance between two vectors
pub fn euclidean_distance(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() {
        return f32::MAX;
    }

    a.iter()
        .zip(b.iter())
        .map(|(ai, bi)| (ai - bi).powi(2))
        .sum::<f32>()
        .sqrt()
}

/// Get current Unix timestamp
fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

// ============================================================================
// Signed Event Functions
// ============================================================================

/// Create signed face detection event
#[cfg(feature = "mesh")]
pub fn create_signed_event(
    identity_id: &str,
    camera_id: &str,
    camera_name: &str,
    confidence: f32,
    name: Option<String>,
    signing_key: &ed25519_dalek::SigningKey,
    hub_id: &str,
) -> SignedFaceEvent {
    use ed25519_dalek::Signer;

    let timestamp = current_timestamp();

    let mut event = SignedFaceEvent {
        identity_id: identity_id.to_string(),
        camera_id: camera_id.to_string(),
        camera_name: camera_name.to_string(),
        confidence,
        timestamp,
        name,
        signature: None,
        signer_hub_id: Some(hub_id.to_string()),
    };

    // Sign the event
    let signable = format!(
        "{}:{}:{}:{:.4}:{}",
        event.identity_id, event.camera_id, event.camera_name, event.confidence, event.timestamp
    );
    let signature = signing_key.sign(signable.as_bytes());
    event.signature = Some(base64::Engine::encode(
        &base64::engine::general_purpose::STANDARD,
        signature.to_bytes(),
    ));

    event
}

#[cfg(not(feature = "mesh"))]
pub fn create_signed_event(
    identity_id: &str,
    camera_id: &str,
    camera_name: &str,
    confidence: f32,
    name: Option<String>,
    _signing_key: &[u8; 32],
    hub_id: &str,
) -> SignedFaceEvent {
    SignedFaceEvent {
        identity_id: identity_id.to_string(),
        camera_id: camera_id.to_string(),
        camera_name: camera_name.to_string(),
        confidence,
        timestamp: current_timestamp(),
        name,
        signature: None,
        signer_hub_id: Some(hub_id.to_string()),
    }
}

/// Verify signed face event
#[cfg(feature = "mesh")]
pub fn verify_signed_event(
    event: &SignedFaceEvent,
    public_key: &ed25519_dalek::VerifyingKey,
) -> bool {
    use ed25519_dalek::{Signature, Verifier};

    let Some(signature_b64) = &event.signature else {
        return false;
    };

    let Ok(signature_bytes) = base64::Engine::decode(
        &base64::engine::general_purpose::STANDARD,
        signature_b64,
    ) else {
        return false;
    };

    let Ok(signature_arr): Result<[u8; 64], _> = signature_bytes.try_into() else {
        return false;
    };

    let signature = Signature::from_bytes(&signature_arr);

    let signable = format!(
        "{}:{}:{}:{:.4}:{}",
        event.identity_id, event.camera_id, event.camera_name, event.confidence, event.timestamp
    );

    public_key.verify(signable.as_bytes(), &signature).is_ok()
}

#[cfg(not(feature = "mesh"))]
pub fn verify_signed_event(_event: &SignedFaceEvent, _public_key: &[u8; 32]) -> bool {
    true // Always pass when mesh is disabled
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cosine_similarity() {
        let a = vec![1.0, 0.0, 0.0];
        let b = vec![1.0, 0.0, 0.0];
        assert!((cosine_similarity(&a, &b) - 1.0).abs() < 0.001);

        let c = vec![0.0, 1.0, 0.0];
        assert!(cosine_similarity(&a, &c).abs() < 0.001);

        // Orthogonal vectors
        let d = vec![1.0, 1.0, 0.0];
        let e = vec![1.0, -1.0, 0.0];
        assert!(cosine_similarity(&d, &e).abs() < 0.001);
    }

    #[test]
    fn test_euclidean_distance() {
        let a = vec![0.0, 0.0, 0.0];
        let b = vec![1.0, 0.0, 0.0];
        assert!((euclidean_distance(&a, &b) - 1.0).abs() < 0.001);

        let c = vec![0.0, 0.0, 0.0];
        assert!(euclidean_distance(&a, &c) < 0.001);
    }

    #[tokio::test]
    async fn test_face_identification() {
        let identifier = FaceIdentifier::default_service();

        identifier.register_profile(
            FaceProfile::new("tim".to_string(), vec![0.8, 0.2, 0.1, 0.5])
                .with_name("Tim")
                .with_threshold(0.7)
        ).await;

        // Exact match
        let result = identifier.identify(&[0.8, 0.2, 0.1, 0.5]).await;
        assert!(result.is_identified);
        assert_eq!(result.display_name(), Some("Tim"));

        // Similar embedding
        let result2 = identifier.identify(&[0.79, 0.21, 0.09, 0.51]).await;
        assert!(result2.is_identified);
        assert!(result2.confidence > 0.9);

        // Different embedding - should not match
        let result3 = identifier.identify(&[0.1, 0.9, 0.0, 0.0]).await;
        assert!(!result3.is_identified);
    }

    #[tokio::test]
    async fn test_multiple_profiles() {
        let identifier = FaceIdentifier::default_service();

        identifier.register_profile(
            FaceProfile::new("tim".to_string(), vec![1.0, 0.0, 0.0, 0.0])
                .with_name("Tim")
                .with_threshold(0.7)
        ).await;

        identifier.register_profile(
            FaceProfile::new("jill".to_string(), vec![0.0, 1.0, 0.0, 0.0])
                .with_name("Jill")
                .with_threshold(0.7)
        ).await;

        // Match Tim
        let result1 = identifier.identify(&[0.95, 0.05, 0.0, 0.0]).await;
        assert!(result1.is_identified);
        assert_eq!(result1.identity_id(), Some("tim"));

        // Match Jill
        let result2 = identifier.identify(&[0.05, 0.95, 0.0, 0.0]).await;
        assert!(result2.is_identified);
        assert_eq!(result2.identity_id(), Some("jill"));
    }

    #[tokio::test]
    async fn test_profile_count() {
        let identifier = FaceIdentifier::default_service();
        assert_eq!(identifier.profile_count().await, 0);

        identifier.register_profile(
            FaceProfile::new("test".to_string(), vec![1.0, 0.0])
        ).await;
        assert_eq!(identifier.profile_count().await, 1);
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * A face is a window to identity.
 * We recognize those we know. We welcome those we don't.
 */
