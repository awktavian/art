//! Speaker Identification Module
//!
//! Per plan: Implement speaker identification in Hub voice pipeline.
//! Uses speaker embeddings to identify household members.
//!
//! Colony: Nexus (e₄) — Integration
//!
//! h(x) ≥ 0. Always.

use anyhow::Result;
use std::collections::HashMap;
use tracing::{debug, info, warn};

/// Speaker profile for voice recognition
#[derive(Debug, Clone)]
pub struct SpeakerProfile {
    /// Unique identifier for the speaker
    pub id: String,
    /// Display name
    pub name: String,
    /// Voice embedding vector (from speaker recognition model)
    pub embedding: Vec<f32>,
    /// Confidence threshold for matching
    pub threshold: f32,
}

/// Result of speaker identification
#[derive(Debug, Clone)]
pub struct SpeakerMatch {
    /// Identified speaker profile
    pub speaker: Option<SpeakerProfile>,
    /// Confidence score (0.0 - 1.0)
    pub confidence: f32,
    /// Was identification successful?
    pub is_identified: bool,
}

/// Speaker identification service
pub struct SpeakerIdentifier {
    /// Registered speaker profiles
    profiles: HashMap<String, SpeakerProfile>,
    /// Default speaker (owner)
    default_speaker: Option<String>,
    /// Minimum confidence threshold (used in identification logic)
    #[allow(dead_code)]
    min_confidence: f32,
}

impl SpeakerIdentifier {
    /// Create a new speaker identifier
    pub fn new() -> Self {
        Self {
            profiles: HashMap::new(),
            default_speaker: None,
            min_confidence: 0.7,
        }
    }

    /// Register a speaker profile
    pub fn register_speaker(&mut self, profile: SpeakerProfile) {
        info!("📣 Registered speaker profile: {}", profile.name);
        if self.default_speaker.is_none() {
            self.default_speaker = Some(profile.id.clone());
        }
        self.profiles.insert(profile.id.clone(), profile);
    }

    /// Load profiles from Kagami API
    pub async fn load_profiles(&mut self, api_url: &str) -> Result<()> {
        let url = format!("{}/api/users/voice-profiles", api_url);
        debug!("Loading speaker profiles from {}", url);

        match reqwest::get(&url).await {
            Ok(response) => {
                if response.status().is_success() {
                    let profiles: Vec<ApiSpeakerProfile> = response.json().await?;
                    for api_profile in profiles {
                        let profile = SpeakerProfile {
                            id: api_profile.id,
                            name: api_profile.name,
                            embedding: api_profile.embedding,
                            threshold: api_profile.threshold.unwrap_or(0.7),
                        };
                        self.register_speaker(profile);
                    }
                    info!("✅ Loaded {} speaker profiles", self.profiles.len());
                } else {
                    warn!("Failed to load profiles: {}", response.status());
                }
            }
            Err(e) => {
                warn!("Failed to connect to API: {}", e);
            }
        }

        Ok(())
    }

    /// Identify speaker from audio embedding
    pub fn identify(&self, audio_embedding: &[f32]) -> SpeakerMatch {
        if self.profiles.is_empty() {
            debug!("No profiles registered, returning default");
            return SpeakerMatch {
                speaker: self
                    .default_speaker
                    .as_ref()
                    .and_then(|id| self.profiles.get(id).cloned()),
                confidence: 0.0,
                is_identified: false,
            };
        }

        let mut best_match: Option<(&SpeakerProfile, f32)> = None;

        for profile in self.profiles.values() {
            let similarity = cosine_similarity(audio_embedding, &profile.embedding);

            debug!(
                "Speaker {} similarity: {:.3} (threshold: {:.3})",
                profile.name, similarity, profile.threshold
            );

            if similarity >= profile.threshold {
                if let Some((_, best_sim)) = best_match {
                    if similarity > best_sim {
                        best_match = Some((profile, similarity));
                    }
                } else {
                    best_match = Some((profile, similarity));
                }
            }
        }

        match best_match {
            Some((profile, confidence)) => {
                info!(
                    "🎤 Identified speaker: {} (confidence: {:.2})",
                    profile.name, confidence
                );
                SpeakerMatch {
                    speaker: Some(profile.clone()),
                    confidence,
                    is_identified: true,
                }
            }
            None => {
                debug!("No speaker match found");
                SpeakerMatch {
                    speaker: self
                        .default_speaker
                        .as_ref()
                        .and_then(|id| self.profiles.get(id).cloned()),
                    confidence: 0.0,
                    is_identified: false,
                }
            }
        }
    }

    /// Get speaker by ID
    pub fn get_speaker(&self, id: &str) -> Option<&SpeakerProfile> {
        self.profiles.get(id)
    }

    /// Get default speaker
    pub fn get_default_speaker(&self) -> Option<&SpeakerProfile> {
        self.default_speaker
            .as_ref()
            .and_then(|id| self.profiles.get(id))
    }

    /// Get all registered speakers
    pub fn get_all_speakers(&self) -> Vec<&SpeakerProfile> {
        self.profiles.values().collect()
    }
}

impl Default for SpeakerIdentifier {
    fn default() -> Self {
        Self::new()
    }
}

/// API response format for speaker profiles
#[derive(Debug, serde::Deserialize)]
struct ApiSpeakerProfile {
    id: String,
    name: String,
    embedding: Vec<f32>,
    threshold: Option<f32>,
}

/// Calculate cosine similarity between two vectors
fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() || a.is_empty() {
        return 0.0;
    }

    let mut dot = 0.0;
    let mut norm_a = 0.0;
    let mut norm_b = 0.0;

    for (ai, bi) in a.iter().zip(b.iter()) {
        dot += ai * bi;
        norm_a += ai * ai;
        norm_b += bi * bi;
    }

    if norm_a == 0.0 || norm_b == 0.0 {
        return 0.0;
    }

    dot / (norm_a.sqrt() * norm_b.sqrt())
}

/// Generate greeting based on speaker, time, and context
pub fn generate_personalized_greeting(speaker: &SpeakerMatch, hour: u32) -> String {
    let name = speaker
        .speaker
        .as_ref()
        .map(|s| s.name.as_str())
        .unwrap_or("there");

    let time_greeting = if hour < 12 {
        "Good morning"
    } else if hour < 17 {
        "Good afternoon"
    } else if hour < 21 {
        "Good evening"
    } else {
        "Hey"
    };

    if speaker.is_identified {
        format!("{}, {}", time_greeting, name)
    } else {
        time_greeting.to_string()
    }
}

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
    }

    #[test]
    fn test_speaker_identification() {
        let mut identifier = SpeakerIdentifier::new();

        identifier.register_speaker(SpeakerProfile {
            id: "tim".to_string(),
            name: "Tim".to_string(),
            embedding: vec![0.8, 0.2, 0.1, 0.5],
            threshold: 0.7,
        });

        let result = identifier.identify(&[0.8, 0.2, 0.1, 0.5]);
        assert!(result.is_identified);
        assert_eq!(result.speaker.unwrap().name, "Tim");
    }

    #[test]
    fn test_personalized_greeting() {
        let match_result = SpeakerMatch {
            speaker: Some(SpeakerProfile {
                id: "tim".to_string(),
                name: "Tim".to_string(),
                embedding: vec![],
                threshold: 0.7,
            }),
            confidence: 0.95,
            is_identified: true,
        };

        assert_eq!(
            generate_personalized_greeting(&match_result, 9),
            "Good morning, Tim"
        );
        assert_eq!(
            generate_personalized_greeting(&match_result, 14),
            "Good afternoon, Tim"
        );
        assert_eq!(
            generate_personalized_greeting(&match_result, 19),
            "Good evening, Tim"
        );
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 *
 * Voice is identity.
 */
