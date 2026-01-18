//! Wake Word Detection for Kagami Hub
//!
//! Listens for the wake phrase "Hey Kagami" or "Mirror, mirror" using
//! local Levenshtein-based matching on continuous audio.
//!
//! Colony: Flow (e₃) — Sensing, adaptation
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use std::collections::VecDeque;
use tracing::{debug, info};

/// Wake word detector configuration
#[derive(Debug, Clone)]
pub struct WakeWordConfig {
    /// Primary wake phrase (e.g., "hey kagami")
    pub primary_phrase: String,
    /// Alternative wake phrase (e.g., "mirror mirror")
    pub alt_phrase: Option<String>,
    /// Detection sensitivity (0.0 - 1.0)
    pub sensitivity: f32,
    /// Maximum edit distance allowed (derived from sensitivity)
    pub max_edit_distance: usize,
    /// Sample rate for audio
    pub sample_rate: u32,
    /// Buffer duration in milliseconds
    pub buffer_duration_ms: u32,
}

impl Default for WakeWordConfig {
    fn default() -> Self {
        Self {
            primary_phrase: "hey kagami".to_string(),
            alt_phrase: Some("mirror mirror".to_string()),
            sensitivity: 0.8,
            max_edit_distance: 2,
            sample_rate: 16000,
            buffer_duration_ms: 500,
        }
    }
}

/// Wake word detection result
#[derive(Debug, Clone)]
pub struct WakeWordResult {
    /// Whether a wake word was detected
    pub detected: bool,
    /// The phrase that was detected (if any)
    pub matched_phrase: Option<String>,
    /// Confidence score (0.0 - 1.0)
    pub confidence: f32,
    /// Timestamp of detection
    pub timestamp_ms: u64,
}

/// Wake word detector trait
pub trait WakeWordDetector: Send + Sync {
    /// Process audio samples and check for wake word
    fn process(&mut self, samples: &[i16]) -> WakeWordResult;

    /// Reset the detector state
    fn reset(&mut self);

    /// Get the configured wake phrase
    fn wake_phrase(&self) -> &str;
}

/// Levenshtein-based wake word detector
pub struct LevenshteinDetector {
    config: WakeWordConfig,
    buffer: VecDeque<i16>,
    last_transcript: String,
}

impl LevenshteinDetector {
    /// Create a new Levenshtein detector
    pub fn new(config: WakeWordConfig) -> Self {
        let buffer_size = (config.sample_rate * config.buffer_duration_ms / 1000) as usize;
        Self {
            config,
            buffer: VecDeque::with_capacity(buffer_size),
            last_transcript: String::new(),
        }
    }

    /// Compute Levenshtein edit distance between two strings
    fn levenshtein(a: &str, b: &str) -> usize {
        let a_chars: Vec<char> = a.chars().collect();
        let b_chars: Vec<char> = b.chars().collect();

        if a_chars.is_empty() {
            return b_chars.len();
        }
        if b_chars.is_empty() {
            return a_chars.len();
        }

        let mut matrix = vec![vec![0usize; b_chars.len() + 1]; a_chars.len() + 1];

        for i in 0..=a_chars.len() {
            matrix[i][0] = i;
        }
        for j in 0..=b_chars.len() {
            matrix[0][j] = j;
        }

        for i in 1..=a_chars.len() {
            for j in 1..=b_chars.len() {
                let cost = if a_chars[i - 1] == b_chars[j - 1] {
                    0
                } else {
                    1
                };
                matrix[i][j] = (matrix[i - 1][j] + 1)
                    .min(matrix[i][j - 1] + 1)
                    .min(matrix[i - 1][j - 1] + cost);
            }
        }

        matrix[a_chars.len()][b_chars.len()]
    }

    /// Check if transcript matches wake phrase
    ///
    /// Note: Currently unused - will be called when STT integration is complete.
    /// The process() method currently returns a stub result; when real STT is
    /// integrated, it will call this method to check the transcript.
    #[allow(dead_code)]
    fn matches_wake_phrase(&self, transcript: &str) -> Option<(String, f32)> {
        let normalized = transcript.to_lowercase();

        // Check primary phrase
        let primary_distance = Self::levenshtein(&normalized, &self.config.primary_phrase);
        let primary_max_len = self.config.primary_phrase.len().max(normalized.len());
        let primary_confidence = 1.0 - (primary_distance as f32 / primary_max_len as f32);

        if primary_distance <= self.config.max_edit_distance {
            info!(
                phrase = %self.config.primary_phrase,
                distance = primary_distance,
                confidence = primary_confidence,
                "Wake word detected (primary)"
            );
            return Some((self.config.primary_phrase.clone(), primary_confidence));
        }

        // Check alternative phrase
        if let Some(alt) = &self.config.alt_phrase {
            let alt_distance = Self::levenshtein(&normalized, alt);
            let alt_max_len = alt.len().max(normalized.len());
            let alt_confidence = 1.0 - (alt_distance as f32 / alt_max_len as f32);

            if alt_distance <= self.config.max_edit_distance {
                info!(
                    phrase = %alt,
                    distance = alt_distance,
                    confidence = alt_confidence,
                    "Wake word detected (alternative)"
                );
                return Some((alt.clone(), alt_confidence));
            }
        }

        None
    }
}

impl WakeWordDetector for LevenshteinDetector {
    fn process(&mut self, samples: &[i16]) -> WakeWordResult {
        // Add samples to buffer
        for &sample in samples {
            if self.buffer.len() >= self.buffer.capacity() {
                self.buffer.pop_front();
            }
            self.buffer.push_back(sample);
        }

        // In a real implementation, this would:
        // 1. Run VAD to detect speech
        // 2. Run local STT (e.g., Whisper tiny) on the buffer
        // 3. Compare result to wake phrases

        // For now, return no detection (will be implemented with actual STT)
        debug!(
            "Processing {} samples, buffer has {} samples",
            samples.len(),
            self.buffer.len()
        );

        WakeWordResult {
            detected: false,
            matched_phrase: None,
            confidence: 0.0,
            timestamp_ms: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis() as u64,
        }
    }

    fn reset(&mut self) {
        self.buffer.clear();
        self.last_transcript.clear();
        debug!("Wake word detector reset");
    }

    fn wake_phrase(&self) -> &str {
        &self.config.primary_phrase
    }
}

/// Create a wake word detector with the given parameters
///
/// # Arguments
/// * `engine` - The engine type ("levenshtein" or other)
/// * `wake_phrase` - The wake phrase to detect
/// * `sensitivity` - Detection sensitivity (0.0 - 1.0)
pub fn create_detector(
    engine: &str,
    wake_phrase: &str,
    sensitivity: f32,
) -> anyhow::Result<Box<dyn WakeWordDetector>> {
    let config = WakeWordConfig {
        primary_phrase: wake_phrase.to_string(),
        sensitivity,
        max_edit_distance: ((1.0 - sensitivity) * 4.0) as usize,
        ..Default::default()
    };

    match engine.to_lowercase().as_str() {
        "levenshtein" | "local" | "" => Ok(Box::new(LevenshteinDetector::new(config))),
        _ => {
            tracing::warn!(
                engine = engine,
                "Unknown wake word engine, using Levenshtein"
            );
            Ok(Box::new(LevenshteinDetector::new(config)))
        }
    }
}

/// Check transcript against wake phrases (for external STT)
pub fn check_transcript(transcript: &str, config: &WakeWordConfig) -> WakeWordResult {
    let normalized = transcript.to_lowercase();

    // Check primary phrase
    let primary_distance = LevenshteinDetector::levenshtein(&normalized, &config.primary_phrase);
    let primary_max_len = config.primary_phrase.len().max(normalized.len());
    let primary_confidence = 1.0 - (primary_distance as f32 / primary_max_len as f32);

    if primary_distance <= config.max_edit_distance {
        return WakeWordResult {
            detected: true,
            matched_phrase: Some(config.primary_phrase.clone()),
            confidence: primary_confidence,
            timestamp_ms: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_millis() as u64,
        };
    }

    // Check alternative phrase
    if let Some(alt) = &config.alt_phrase {
        let alt_distance = LevenshteinDetector::levenshtein(&normalized, alt);
        let alt_max_len = alt.len().max(normalized.len());
        let alt_confidence = 1.0 - (alt_distance as f32 / alt_max_len as f32);

        if alt_distance <= config.max_edit_distance {
            return WakeWordResult {
                detected: true,
                matched_phrase: Some(alt.clone()),
                confidence: alt_confidence,
                timestamp_ms: std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_millis() as u64,
            };
        }
    }

    WakeWordResult {
        detected: false,
        matched_phrase: None,
        confidence: 0.0,
        timestamp_ms: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_levenshtein_exact_match() {
        assert_eq!(LevenshteinDetector::levenshtein("hello", "hello"), 0);
    }

    #[test]
    fn test_levenshtein_one_edit() {
        assert_eq!(LevenshteinDetector::levenshtein("hello", "hallo"), 1);
        assert_eq!(LevenshteinDetector::levenshtein("hello", "hell"), 1);
        assert_eq!(LevenshteinDetector::levenshtein("hello", "helloo"), 1);
    }

    #[test]
    fn test_levenshtein_two_edits() {
        assert_eq!(LevenshteinDetector::levenshtein("hello", "hxllo"), 1);
        assert_eq!(
            LevenshteinDetector::levenshtein("hey kagami", "hay kagami"),
            1
        );
        assert_eq!(
            LevenshteinDetector::levenshtein("hey kagami", "hey kagemi"),
            1
        );
    }

    #[test]
    fn test_wake_phrase_detection() {
        let config = WakeWordConfig::default();
        let result = check_transcript("hey kagami", &config);
        assert!(result.detected);
        assert_eq!(result.matched_phrase, Some("hey kagami".to_string()));

        let result = check_transcript("hay kagami", &config);
        assert!(result.detected); // 1 edit distance

        let result = check_transcript("hello world", &config);
        assert!(!result.detected);
    }

    #[test]
    fn test_alt_phrase_detection() {
        let config = WakeWordConfig::default();
        let result = check_transcript("mirror mirror", &config);
        assert!(result.detected);
        assert_eq!(result.matched_phrase, Some("mirror mirror".to_string()));
    }
}
