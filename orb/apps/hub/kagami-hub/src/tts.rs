//! Text-to-Speech module using Piper TTS
//!
//! Synthesizes natural speech from text for voice responses.
//!
//! Colony: Crystal (e₇) — Output, verification
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::Result;
#[cfg(feature = "piper")]
use tracing::debug;
use tracing::{info, warn};

/// TTS engine configuration
#[derive(Debug, Clone)]
pub struct TTSConfig {
    /// Path to Piper model
    pub model_path: String,
    /// Speaker ID (for multi-speaker models)
    pub speaker_id: Option<i64>,
    /// Speech rate (1.0 = normal)
    pub rate: f32,
    /// Output sample rate
    pub sample_rate: u32,
}

impl Default for TTSConfig {
    fn default() -> Self {
        Self {
            model_path: "models/en_US-amy-medium.onnx".to_string(),
            speaker_id: None,
            rate: 1.0,
            sample_rate: 22050,
        }
    }
}

/// Text-to-Speech engine
pub struct TTSEngine {
    /// Configuration (kept for reconfiguration/serialization)
    #[allow(dead_code)]
    config: TTSConfig,
    #[cfg(feature = "piper")]
    piper: Option<piper_rs::Piper>,
}

impl TTSEngine {
    /// Create a new TTS engine
    pub fn new(config: TTSConfig) -> Result<Self> {
        info!("Initializing TTS engine with model: {}", config.model_path);

        #[cfg(feature = "piper")]
        {
            let piper = piper_rs::Piper::new(&config.model_path)
                .map_err(|e| anyhow::anyhow!("Failed to load Piper model: {}", e))?;

            info!("✓ Piper TTS model loaded");

            Ok(Self {
                config,
                piper: Some(piper),
            })
        }

        #[cfg(not(feature = "piper"))]
        {
            warn!("Piper TTS not available (piper feature disabled)");
            Ok(Self { config })
        }
    }

    /// Synthesize speech from text
    #[cfg(feature = "piper")]
    pub fn synthesize(&self, text: &str) -> Result<Vec<i16>> {
        let piper = self
            .piper
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("Piper not initialized"))?;

        debug!("Synthesizing: \"{}\"", text);

        let audio = piper
            .synthesize(text)
            .map_err(|e| anyhow::anyhow!("TTS synthesis failed: {}", e))?;

        info!(
            "🔊 Synthesized {} samples ({:.2}s)",
            audio.len(),
            audio.len() as f32 / self.config.sample_rate as f32
        );

        Ok(audio)
    }

    #[cfg(not(feature = "piper"))]
    pub fn synthesize(&self, _text: &str) -> Result<Vec<i16>> {
        warn!("Piper TTS not available, returning empty audio");
        Ok(Vec::new())
    }

    /// Check if engine is available
    pub fn is_available(&self) -> bool {
        #[cfg(feature = "piper")]
        return self.piper.is_some();

        #[cfg(not(feature = "piper"))]
        false
    }
}

/// Generate a simple confirmation tone (when TTS unavailable)
pub fn generate_confirmation_tone(sample_rate: u32, duration_ms: u32) -> Vec<i16> {
    let num_samples = (sample_rate * duration_ms / 1000) as usize;
    let frequency = 880.0; // A5 note
    let amplitude = 16000.0;

    (0..num_samples)
        .map(|i| {
            let t = i as f32 / sample_rate as f32;
            let envelope = (1.0 - (t * 1000.0 / duration_ms as f32)).max(0.0);
            (amplitude * envelope * (2.0 * std::f32::consts::PI * frequency * t).sin()) as i16
        })
        .collect()
}

/// Generate an error tone
pub fn generate_error_tone(sample_rate: u32, duration_ms: u32) -> Vec<i16> {
    let num_samples = (sample_rate * duration_ms / 1000) as usize;
    let frequency = 220.0; // A3 note (lower, indicating error)
    let amplitude = 12000.0;

    (0..num_samples)
        .map(|i| {
            let t = i as f32 / sample_rate as f32;
            let envelope = (1.0 - (t * 1000.0 / duration_ms as f32)).max(0.0);
            (amplitude * envelope * (2.0 * std::f32::consts::PI * frequency * t).sin()) as i16
        })
        .collect()
}

/*
 * 鏡
 * The voice of the home.
 */
