//! Speech-to-Text module using Whisper.cpp
//!
//! Transcribes audio to text using local Whisper model.
//!
//! Colony: Flow (e₃) → Nexus (e₄)
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use anyhow::Result;
#[cfg(feature = "whisper")]
use tracing::debug;
use tracing::{info, warn};

/// STT engine configuration
#[derive(Debug, Clone)]
pub struct STTConfig {
    /// Path to Whisper model (e.g., "models/ggml-base.en.bin")
    pub model_path: String,
    /// Language code (e.g., "en")
    pub language: String,
    /// Enable translation to English
    pub translate: bool,
    /// Number of threads for inference
    pub n_threads: i32,
}

impl Default for STTConfig {
    fn default() -> Self {
        Self {
            model_path: "models/ggml-base.en.bin".to_string(),
            language: "en".to_string(),
            translate: false,
            n_threads: 4,
        }
    }
}

/// Speech-to-Text engine
pub struct STTEngine {
    /// Configuration (kept for reconfiguration/serialization)
    #[allow(dead_code)]
    config: STTConfig,
    #[cfg(feature = "whisper")]
    ctx: Option<whisper_rs::WhisperContext>,
}

impl STTEngine {
    /// Create a new STT engine
    pub fn new(config: STTConfig) -> Result<Self> {
        info!("Initializing STT engine with model: {}", config.model_path);

        #[cfg(feature = "whisper")]
        {
            use whisper_rs::{WhisperContext, WhisperContextParameters};

            let ctx = WhisperContext::new_with_params(
                &config.model_path,
                WhisperContextParameters::default(),
            )
            .map_err(|e| anyhow::anyhow!("Failed to load Whisper model: {}", e))?;

            info!("✓ Whisper model loaded");

            Ok(Self {
                config,
                ctx: Some(ctx),
            })
        }

        #[cfg(not(feature = "whisper"))]
        {
            warn!("Whisper STT not available (whisper feature disabled)");
            Ok(Self { config })
        }
    }

    /// Transcribe audio samples to text
    #[cfg(feature = "whisper")]
    pub fn transcribe(&self, samples: &[i16]) -> Result<String> {
        let ctx = self
            .ctx
            .as_ref()
            .ok_or_else(|| anyhow::anyhow!("Whisper context not initialized"))?;

        // Convert i16 to f32 normalized samples
        let samples_f32: Vec<f32> = samples.iter().map(|&s| s as f32 / 32768.0).collect();

        debug!(
            "Transcribing {} samples ({:.2}s of audio)",
            samples.len(),
            samples.len() as f32 / 16000.0
        );

        // Create whisper state
        let mut state = ctx
            .create_state()
            .map_err(|e| anyhow::anyhow!("Failed to create state: {}", e))?;

        // Set up parameters
        let mut params =
            whisper_rs::FullParams::new(whisper_rs::SamplingStrategy::Greedy { best_of: 1 });

        params.set_n_threads(self.config.n_threads);
        params.set_language(Some(&self.config.language));
        params.set_translate(self.config.translate);
        params.set_print_progress(false);
        params.set_print_timestamps(false);
        params.set_print_special(false);
        params.set_suppress_blank(true);
        params.set_suppress_non_speech_tokens(true);

        // Run inference
        state
            .full(params, &samples_f32)
            .map_err(|e| anyhow::anyhow!("Transcription failed: {}", e))?;

        // Collect results
        let mut transcript = String::new();
        let num_segments = state
            .full_n_segments()
            .map_err(|e| anyhow::anyhow!("Failed to get segments: {}", e))?;

        for i in 0..num_segments {
            if let Ok(text) = state.full_get_segment_text(i) {
                transcript.push_str(&text);
            }
        }

        let transcript = transcript.trim().to_string();
        info!("📝 Transcribed: \"{}\"", transcript);

        Ok(transcript)
    }

    #[cfg(not(feature = "whisper"))]
    pub fn transcribe(&self, _samples: &[i16]) -> Result<String> {
        warn!("Whisper STT not available, returning mock transcription");
        Ok("lights on".to_string())
    }

    /// Check if engine is available
    pub fn is_available(&self) -> bool {
        #[cfg(feature = "whisper")]
        return self.ctx.is_some();

        #[cfg(not(feature = "whisper"))]
        false
    }
}

/*
 * 鏡
 * Whisper turns sound into words.
 */
