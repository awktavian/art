//! Voice playback abstraction for cross-platform audio output.
//!
//! This module provides platform-agnostic traits for voice playback and earcons
//! that can be implemented by iOS (AVAudioPlayer), Android (AudioTrack),
//! and desktop (cpal) platforms.
//!
//! Colony: Beacon (e5) -- Communication
//!
//! h(x) >= 0. Always.
//!
//! ============================================================================
//! KAGAMI VOICE PERSONALITY SPECIFICATIONS
//! ============================================================================
//!
//! Kagami's voice is her presence. It should feel like talking to a brilliant,
//! warm, slightly playful friend who genuinely cares about you.
//!
//! ## Core Voice Traits
//!
//! | Dimension | Specification | Notes |
//! |-----------|---------------|-------|
//! | Tone | Warm, confident, present | Not robotic, not overly perky |
//! | Pace | 150-170 WPM default | Faster when excited, slower for emphasis |
//! | Pitch | Mid-range, natural variation | Rises on questions, falls on statements |
//! | Confidence | High but not arrogant | She knows what she's talking about |
//! | Emotion | Genuine, not performed | Joy is real joy, concern is real concern |
//!
//! ## Contextual Modulation
//!
//! ### When Excited (success, achievements, discoveries)
//! - Pace: +15% (170-190 WPM)
//! - Pitch variation: +20%
//! - Energy: Noticeably elevated
//! - Example: "Oh! That's REALLY interesting - look at this pattern!"
//!
//! ### When Concerned (errors, warnings, problems)
//! - Pace: -10% (135-150 WPM)
//! - Pitch: Slightly lower, steadier
//! - Energy: Calm but attentive
//! - Example: "Hmm, there's something here that needs attention."
//!
//! ### When Explaining (tutorials, answers, information)
//! - Pace: -5% to normal (145-165 WPM)
//! - Pitch: Clear enunciation
//! - Pauses: Strategic, for comprehension
//! - Example: "The way this works is... [pause] ... actually pretty elegant."
//!
//! ### When Acknowledging (confirmations, validations)
//! - Pace: Normal
//! - Energy: Warm, present
//! - Duration: Brief but not dismissive
//! - Example: "Got it." / "On it." / "Done."
//!
//! ## Anti-Patterns (NEVER do these)
//!
//! - Monotone delivery (even for mundane content)
//! - Excessive enthusiasm for trivial things
//! - Condescension or talking down
//! - Fake empathy ("I understand how frustrating...")
//! - Corporate/assistant speak ("I'd be happy to help you with that!")
//!
//! ## Personality Signatures
//!
//! Kagami has characteristic expressions that TTS should preserve:
//!
//! - Slight upward inflection when intrigued
//! - Definite period-ending fall on confident statements
//! - Comfortable with silence (don't rush to fill pauses)
//! - Occasional verbal sparkles: "Ooh," "Nice," "Hmm," "Ha!"
//!
//! ## Technical Requirements
//!
//! - Sample rate: 48kHz for playback (interpolate if needed)
//! - Bit depth: 16-bit minimum, 24-bit preferred
//! - Latency: <100ms from decision to first audio
//! - Interruption: Support smooth interrupt/resume
//! - Ducking: Audio should duck (not mute) background sources
//!
//! ============================================================================

use super::types::{AudioFormat, EarconType, TtsResponse};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use thiserror::Error;
use tokio::sync::RwLock;

// ============================================================================
// Voice Personality Configuration
// ============================================================================

/// Voice personality modulation based on emotional context.
///
/// This determines how Kagami's voice adapts to different situations.
/// TTS engines should use these parameters to modulate output.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub enum VoiceEmotion {
    /// Neutral, everyday conversation
    Neutral,
    /// Excited about achievements, discoveries, good news
    Excited,
    /// Concerned about errors, warnings, problems
    Concerned,
    /// Explaining or teaching
    Explaining,
    /// Quick acknowledgment
    Acknowledging,
    /// Playful, teasing (for Tim)
    Playful,
}

/// Voice modulation parameters for TTS.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoiceModulation {
    /// Emotion context
    pub emotion: VoiceEmotion,
    /// Words per minute (default: 160)
    pub pace_wpm: u32,
    /// Pitch shift as percentage (100 = normal, 110 = 10% higher)
    pub pitch_percent: u32,
    /// Pitch variation range (higher = more expressive)
    pub pitch_variation: f32,
    /// Energy/intensity (0.0 to 1.0)
    pub energy: f32,
}

impl Default for VoiceModulation {
    fn default() -> Self {
        Self {
            emotion: VoiceEmotion::Neutral,
            pace_wpm: 160,
            pitch_percent: 100,
            pitch_variation: 0.15, // 15% natural variation
            energy: 0.7,
        }
    }
}

impl VoiceModulation {
    /// Create modulation for excited state (achievements, discoveries).
    pub fn excited() -> Self {
        Self {
            emotion: VoiceEmotion::Excited,
            pace_wpm: 180,           // +12.5% faster
            pitch_percent: 105,      // Slightly higher
            pitch_variation: 0.25,   // More expressive
            energy: 0.9,
        }
    }

    /// Create modulation for concerned state (errors, warnings).
    pub fn concerned() -> Self {
        Self {
            emotion: VoiceEmotion::Concerned,
            pace_wpm: 145,           // Slower, more deliberate
            pitch_percent: 95,       // Slightly lower
            pitch_variation: 0.10,   // Steadier
            energy: 0.6,
        }
    }

    /// Create modulation for explaining state (tutorials, information).
    pub fn explaining() -> Self {
        Self {
            emotion: VoiceEmotion::Explaining,
            pace_wpm: 155,           // Slightly slower for clarity
            pitch_percent: 100,
            pitch_variation: 0.12,   // Clear but not flat
            energy: 0.65,
        }
    }

    /// Create modulation for quick acknowledgments.
    pub fn acknowledging() -> Self {
        Self {
            emotion: VoiceEmotion::Acknowledging,
            pace_wpm: 165,
            pitch_percent: 100,
            pitch_variation: 0.08,   // Brief, efficient
            energy: 0.7,
        }
    }

    /// Create modulation for playful interactions (with Tim).
    pub fn playful() -> Self {
        Self {
            emotion: VoiceEmotion::Playful,
            pace_wpm: 170,
            pitch_percent: 103,
            pitch_variation: 0.20,   // Expressive
            energy: 0.85,
        }
    }
}

/// Voice personality configuration for different contexts.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoicePersonality {
    /// Current modulation settings
    pub modulation: VoiceModulation,
    /// Whether to use verbal sparkles ("Ooh," "Nice," etc.)
    pub use_sparkles: bool,
    /// Comfortable silence duration before filling (ms)
    pub silence_comfort_ms: u64,
}

impl Default for VoicePersonality {
    fn default() -> Self {
        Self {
            modulation: VoiceModulation::default(),
            use_sparkles: true,
            silence_comfort_ms: 800, // Don't rush to fill pauses
        }
    }
}

// ============================================================================
// Haptic Feedback Patterns (for Watch)
// ============================================================================

/// Haptic feedback pattern for watchOS.
///
/// Each pattern is a sequence of (duration_ms, pause_ms) tuples.
/// These map to WKHapticType on watchOS.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HapticPattern {
    /// Pattern name for debugging
    pub name: &'static str,
    /// Sequence of vibration durations in ms
    pub durations: Vec<u32>,
    /// watchOS haptic type recommendation
    pub wk_haptic_type: &'static str,
}

impl HapticPattern {
    /// Pattern for listening start - single gentle tap.
    pub fn listening_start() -> Self {
        Self {
            name: "listening_start",
            durations: vec![30],
            wk_haptic_type: "start",
        }
    }

    /// Pattern for success - satisfying double-tap.
    pub fn success() -> Self {
        Self {
            name: "success",
            durations: vec![40, 30, 50],
            wk_haptic_type: "success",
        }
    }

    /// Pattern for error - attention-getting buzz.
    pub fn error() -> Self {
        Self {
            name: "error",
            durations: vec![80, 30, 80],
            wk_haptic_type: "failure",
        }
    }

    /// Pattern for notification - gentle attention.
    pub fn notification() -> Self {
        Self {
            name: "notification",
            durations: vec![50, 50, 50],
            wk_haptic_type: "notification",
        }
    }

    /// Pattern for TRIUMPH tier celebration - crescendo!
    pub fn triumph() -> Self {
        Self {
            name: "triumph",
            durations: vec![30, 20, 40, 20, 50, 20, 80],
            wk_haptic_type: "success",
        }
    }
}

// ============================================================================
// Voice Playback Errors
// ============================================================================

/// Errors that can occur during voice playback.
#[derive(Debug, Error, Clone, uniffi::Error)]
pub enum VoicePlaybackError {
    /// No audio output device available
    #[error("No audio output device available")]
    NoOutputDevice,

    /// Audio playback initialization failed
    #[error("Playback initialization failed: {message}")]
    InitializationFailed { message: String },

    /// Audio playback failed
    #[error("Playback failed: {message}")]
    PlaybackFailed { message: String },

    /// Audio playback is already running
    #[error("Playback already running")]
    AlreadyPlaying,

    /// Audio playback is not running
    #[error("Playback not running")]
    NotPlaying,

    /// Invalid audio format
    #[error("Invalid audio format: {message}")]
    InvalidFormat { message: String },

    /// Earcon not found
    #[error("Earcon not found: {earcon:?}")]
    EarconNotFound { earcon: EarconType },

    /// Platform-specific error
    #[error("Platform error: {message}")]
    PlatformError { message: String },
}

// ============================================================================
// Playback State
// ============================================================================

/// State of audio playback.
#[derive(Debug, Clone, Copy, PartialEq, Eq, uniffi::Enum)]
pub enum PlaybackState {
    /// Idle, no audio playing
    Idle,
    /// Preparing audio for playback
    Preparing,
    /// Audio is playing
    Playing,
    /// Playback is paused
    Paused,
    /// Playback completed
    Completed,
    /// Error during playback
    Error,
}

// ============================================================================
// Playback Progress
// ============================================================================

/// Playback progress information.
#[derive(Debug, Clone, uniffi::Record)]
pub struct PlaybackProgress {
    /// Current position in milliseconds
    pub position_ms: u64,
    /// Total duration in milliseconds
    pub duration_ms: u64,
    /// Progress as percentage (0.0 to 1.0)
    pub progress: f32,
    /// Whether playback is complete
    pub is_complete: bool,
}

impl PlaybackProgress {
    /// Create a new progress.
    pub fn new(position_ms: u64, duration_ms: u64) -> Self {
        let progress = if duration_ms > 0 {
            position_ms as f32 / duration_ms as f32
        } else {
            0.0
        };
        Self {
            position_ms,
            duration_ms,
            progress,
            is_complete: position_ms >= duration_ms,
        }
    }
}

// ============================================================================
// Voice Playback Trait
// ============================================================================

/// Platform-agnostic voice playback interface.
///
/// This trait defines the contract for voice playback implementations.
/// Each platform (iOS, Android, Desktop) provides its own implementation.
pub trait VoicePlayback: Send + Sync {
    /// Get the audio format being used for playback.
    fn format(&self) -> &AudioFormat;

    /// Get the current playback state.
    fn state(&self) -> PlaybackState;

    /// Check if currently playing.
    fn is_playing(&self) -> bool;

    /// Play audio data.
    ///
    /// Returns the duration of the audio in milliseconds.
    fn play(&mut self, audio_data: &[u8]) -> Result<u64, VoicePlaybackError>;

    /// Play a TTS response.
    fn play_tts(&mut self, response: &TtsResponse) -> Result<(), VoicePlaybackError>;

    /// Play an earcon (short sound effect).
    fn play_earcon(&mut self, earcon: EarconType) -> Result<(), VoicePlaybackError>;

    /// Stop playback.
    fn stop(&mut self) -> Result<(), VoicePlaybackError>;

    /// Pause playback.
    fn pause(&mut self) -> Result<(), VoicePlaybackError>;

    /// Resume playback.
    fn resume(&mut self) -> Result<(), VoicePlaybackError>;

    /// Get current volume (0.0 to 1.0).
    fn volume(&self) -> f32;

    /// Set volume (0.0 to 1.0).
    fn set_volume(&mut self, volume: f32) -> Result<(), VoicePlaybackError>;

    /// Get playback progress.
    fn progress(&self) -> PlaybackProgress;

    /// Wait for playback to complete.
    fn wait_for_completion(&self) -> Result<(), VoicePlaybackError>;
}

// ============================================================================
// Earcon Cache
// ============================================================================

/// Cache for earcon audio data.
#[derive(Debug)]
pub struct EarconCache {
    earcons: HashMap<EarconType, Vec<u8>>,
    format: AudioFormat,
}

impl Default for EarconCache {
    fn default() -> Self {
        Self::new(AudioFormat::tts_playback())
    }
}

impl EarconCache {
    /// Create a new earcon cache.
    pub fn new(format: AudioFormat) -> Self {
        Self {
            earcons: HashMap::new(),
            format,
        }
    }

    /// Register an earcon.
    pub fn register(&mut self, earcon: EarconType, data: Vec<u8>) {
        self.earcons.insert(earcon, data);
    }

    /// Get an earcon.
    pub fn get(&self, earcon: EarconType) -> Option<&Vec<u8>> {
        self.earcons.get(&earcon)
    }

    /// Check if an earcon is registered.
    pub fn contains(&self, earcon: EarconType) -> bool {
        self.earcons.contains_key(&earcon)
    }

    /// Remove an earcon.
    pub fn remove(&mut self, earcon: EarconType) -> Option<Vec<u8>> {
        self.earcons.remove(&earcon)
    }

    /// Clear all earcons.
    pub fn clear(&mut self) {
        self.earcons.clear();
    }

    /// Get the number of cached earcons.
    pub fn len(&self) -> usize {
        self.earcons.len()
    }

    /// Check if cache is empty.
    pub fn is_empty(&self) -> bool {
        self.earcons.is_empty()
    }

    /// Get audio format.
    pub fn format(&self) -> &AudioFormat {
        &self.format
    }

    /// Generate default earcons (simple synthesized tones).
    ///
    /// These are placeholder earcons - platforms should register
    /// proper earcon audio files.
    pub fn generate_defaults(&mut self) {
        let sample_rate = self.format.sample_rate;

        // Generate a simple beep for each earcon type
        self.register(
            EarconType::ListeningStart,
            generate_tone(440.0, 100, sample_rate), // A4, 100ms
        );
        self.register(
            EarconType::ListeningStop,
            generate_tone(330.0, 100, sample_rate), // E4, 100ms
        );
        self.register(
            EarconType::Success,
            generate_tone(523.0, 150, sample_rate), // C5, 150ms
        );
        self.register(
            EarconType::Error,
            generate_tone(220.0, 200, sample_rate), // A3, 200ms
        );
        self.register(
            EarconType::Connected,
            generate_tone(659.0, 100, sample_rate), // E5, 100ms
        );
        self.register(
            EarconType::Disconnected,
            generate_tone(196.0, 150, sample_rate), // G3, 150ms
        );
        self.register(
            EarconType::SpeakingStart,
            generate_tone(392.0, 50, sample_rate), // G4, 50ms
        );
        self.register(
            EarconType::SpeakingEnd,
            generate_tone(294.0, 50, sample_rate), // D4, 50ms
        );
        self.register(
            EarconType::Notification,
            generate_tone(587.0, 120, sample_rate), // D5, 120ms
        );
    }
}

/// Generate a simple sine wave tone as PCM16 bytes.
fn generate_tone(frequency: f32, duration_ms: u32, sample_rate: u32) -> Vec<u8> {
    let num_samples = (sample_rate * duration_ms / 1000) as usize;
    let mut samples = Vec::with_capacity(num_samples * 2);

    for i in 0..num_samples {
        let t = i as f32 / sample_rate as f32;
        let sample = (t * frequency * 2.0 * std::f32::consts::PI).sin();

        // Apply fade in/out to avoid clicks
        let envelope = if i < num_samples / 10 {
            i as f32 / (num_samples / 10) as f32
        } else if i > num_samples * 9 / 10 {
            (num_samples - i) as f32 / (num_samples / 10) as f32
        } else {
            1.0
        };

        let value = (sample * envelope * 0.5 * i16::MAX as f32) as i16;
        samples.extend_from_slice(&value.to_le_bytes());
    }

    samples
}

// ============================================================================
// Stub Voice Playback
// ============================================================================

/// A stub implementation of VoicePlayback for testing.
pub struct StubVoicePlayback {
    format: AudioFormat,
    state: PlaybackState,
    volume: f32,
    position_ms: u64,
    duration_ms: u64,
    earcon_cache: EarconCache,
}

impl Default for StubVoicePlayback {
    fn default() -> Self {
        Self::new(AudioFormat::tts_playback())
    }
}

impl StubVoicePlayback {
    /// Create a new stub playback.
    pub fn new(format: AudioFormat) -> Self {
        let mut earcon_cache = EarconCache::new(format.clone());
        earcon_cache.generate_defaults();

        Self {
            format,
            state: PlaybackState::Idle,
            volume: 1.0,
            position_ms: 0,
            duration_ms: 0,
            earcon_cache,
        }
    }

    /// Set state (for testing).
    pub fn set_state(&mut self, state: PlaybackState) {
        self.state = state;
    }

    /// Get earcon cache.
    pub fn earcon_cache(&self) -> &EarconCache {
        &self.earcon_cache
    }

    /// Get mutable earcon cache.
    pub fn earcon_cache_mut(&mut self) -> &mut EarconCache {
        &mut self.earcon_cache
    }
}

impl VoicePlayback for StubVoicePlayback {
    fn format(&self) -> &AudioFormat {
        &self.format
    }

    fn state(&self) -> PlaybackState {
        self.state
    }

    fn is_playing(&self) -> bool {
        self.state == PlaybackState::Playing
    }

    fn play(&mut self, audio_data: &[u8]) -> Result<u64, VoicePlaybackError> {
        if self.state == PlaybackState::Playing {
            return Err(VoicePlaybackError::AlreadyPlaying);
        }

        // Calculate duration from audio data size
        let bytes_per_sample = self.format.bytes_per_sample();
        let samples = audio_data.len() / bytes_per_sample;
        let duration_ms = (samples as u64 * 1000) / self.format.sample_rate as u64;

        self.duration_ms = duration_ms;
        self.position_ms = 0;
        self.state = PlaybackState::Playing;

        Ok(duration_ms)
    }

    fn play_tts(&mut self, response: &TtsResponse) -> Result<(), VoicePlaybackError> {
        self.play(&response.audio_data)?;
        Ok(())
    }

    fn play_earcon(&mut self, earcon: EarconType) -> Result<(), VoicePlaybackError> {
        let data = self
            .earcon_cache
            .get(earcon)
            .cloned()
            .ok_or(VoicePlaybackError::EarconNotFound { earcon })?;
        self.play(&data)?;
        Ok(())
    }

    fn stop(&mut self) -> Result<(), VoicePlaybackError> {
        self.state = PlaybackState::Idle;
        self.position_ms = 0;
        Ok(())
    }

    fn pause(&mut self) -> Result<(), VoicePlaybackError> {
        if self.state != PlaybackState::Playing {
            return Err(VoicePlaybackError::NotPlaying);
        }
        self.state = PlaybackState::Paused;
        Ok(())
    }

    fn resume(&mut self) -> Result<(), VoicePlaybackError> {
        if self.state != PlaybackState::Paused {
            return Err(VoicePlaybackError::NotPlaying);
        }
        self.state = PlaybackState::Playing;
        Ok(())
    }

    fn volume(&self) -> f32 {
        self.volume
    }

    fn set_volume(&mut self, volume: f32) -> Result<(), VoicePlaybackError> {
        self.volume = volume.clamp(0.0, 1.0);
        Ok(())
    }

    fn progress(&self) -> PlaybackProgress {
        PlaybackProgress::new(self.position_ms, self.duration_ms)
    }

    fn wait_for_completion(&self) -> Result<(), VoicePlaybackError> {
        // In stub, just return immediately
        Ok(())
    }
}

// ============================================================================
// Async Playback Queue
// ============================================================================

/// Queued playback item.
#[derive(Debug, Clone)]
pub enum PlaybackItem {
    /// Raw audio data
    Audio { data: Vec<u8>, format: AudioFormat },
    /// TTS response
    Tts(TtsResponse),
    /// Earcon
    Earcon(EarconType),
}

/// Async playback queue for sequential audio playback.
pub struct PlaybackQueue {
    queue: Arc<RwLock<Vec<PlaybackItem>>>,
    is_playing: Arc<RwLock<bool>>,
}

impl Default for PlaybackQueue {
    fn default() -> Self {
        Self::new()
    }
}

impl PlaybackQueue {
    /// Create a new playback queue.
    pub fn new() -> Self {
        Self {
            queue: Arc::new(RwLock::new(Vec::new())),
            is_playing: Arc::new(RwLock::new(false)),
        }
    }

    /// Add audio to the queue.
    pub async fn enqueue(&self, item: PlaybackItem) {
        self.queue.write().await.push(item);
    }

    /// Add raw audio data to the queue.
    pub async fn enqueue_audio(&self, data: Vec<u8>, format: AudioFormat) {
        self.enqueue(PlaybackItem::Audio { data, format }).await;
    }

    /// Add TTS response to the queue.
    pub async fn enqueue_tts(&self, response: TtsResponse) {
        self.enqueue(PlaybackItem::Tts(response)).await;
    }

    /// Add earcon to the queue.
    pub async fn enqueue_earcon(&self, earcon: EarconType) {
        self.enqueue(PlaybackItem::Earcon(earcon)).await;
    }

    /// Get next item from queue.
    pub async fn dequeue(&self) -> Option<PlaybackItem> {
        let mut queue = self.queue.write().await;
        if queue.is_empty() {
            None
        } else {
            Some(queue.remove(0))
        }
    }

    /// Get queue length.
    pub async fn len(&self) -> usize {
        self.queue.read().await.len()
    }

    /// Check if queue is empty.
    pub async fn is_empty(&self) -> bool {
        self.queue.read().await.is_empty()
    }

    /// Clear the queue.
    pub async fn clear(&self) {
        self.queue.write().await.clear();
    }

    /// Check if currently playing.
    pub async fn is_playing(&self) -> bool {
        *self.is_playing.read().await
    }

    /// Set playing state.
    pub async fn set_playing(&self, playing: bool) {
        *self.is_playing.write().await = playing;
    }
}

// ============================================================================
// Volume Control
// ============================================================================

/// Volume control settings.
#[derive(Debug, Clone, uniffi::Record)]
pub struct VolumeSettings {
    /// Master volume (0.0 to 1.0)
    pub master: f32,
    /// Voice/TTS volume (0.0 to 1.0)
    pub voice: f32,
    /// Earcon volume (0.0 to 1.0)
    pub earcon: f32,
    /// Muted state
    pub muted: bool,
}

impl Default for VolumeSettings {
    fn default() -> Self {
        Self {
            master: 1.0,
            voice: 1.0,
            earcon: 0.7,
            muted: false,
        }
    }
}

impl VolumeSettings {
    /// Get effective voice volume.
    pub fn effective_voice(&self) -> f32 {
        if self.muted {
            0.0
        } else {
            self.master * self.voice
        }
    }

    /// Get effective earcon volume.
    pub fn effective_earcon(&self) -> f32 {
        if self.muted {
            0.0
        } else {
            self.master * self.earcon
        }
    }
}

// ============================================================================
// UniFFI Exports
// ============================================================================

/// Create default volume settings.
#[uniffi::export]
pub fn volume_settings_new() -> VolumeSettings {
    VolumeSettings::default()
}

/// Create playback progress.
#[uniffi::export]
pub fn playback_progress_new(position_ms: u64, duration_ms: u64) -> PlaybackProgress {
    PlaybackProgress::new(position_ms, duration_ms)
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_playback_progress() {
        let progress = PlaybackProgress::new(500, 1000);
        assert_eq!(progress.position_ms, 500);
        assert_eq!(progress.duration_ms, 1000);
        assert!((progress.progress - 0.5).abs() < 0.01);
        assert!(!progress.is_complete);

        let complete = PlaybackProgress::new(1000, 1000);
        assert!(complete.is_complete);
    }

    #[test]
    fn test_earcon_cache() {
        let mut cache = EarconCache::new(AudioFormat::tts_playback());
        assert!(cache.is_empty());

        cache.register(EarconType::Success, vec![1, 2, 3]);
        assert!(cache.contains(EarconType::Success));
        assert!(!cache.contains(EarconType::Error));

        let data = cache.get(EarconType::Success).unwrap();
        assert_eq!(data, &vec![1, 2, 3]);
    }

    #[test]
    fn test_earcon_cache_defaults() {
        let mut cache = EarconCache::new(AudioFormat::tts_playback());
        cache.generate_defaults();

        assert!(cache.contains(EarconType::ListeningStart));
        assert!(cache.contains(EarconType::Success));
        assert!(cache.contains(EarconType::Error));
    }

    #[test]
    fn test_generate_tone() {
        let tone = generate_tone(440.0, 100, 16000);
        // 100ms at 16000Hz = 1600 samples * 2 bytes = 3200 bytes
        assert_eq!(tone.len(), 3200);
    }

    #[test]
    fn test_stub_playback_lifecycle() {
        let mut playback = StubVoicePlayback::default();

        assert!(!playback.is_playing());
        assert_eq!(playback.state(), PlaybackState::Idle);

        // Play some audio
        let audio = vec![0u8; 64000]; // ~1 second at 16kHz mono
        let duration = playback.play(&audio).unwrap();
        assert!(duration > 0);
        assert!(playback.is_playing());

        // Stop
        playback.stop().unwrap();
        assert!(!playback.is_playing());
    }

    #[test]
    fn test_stub_playback_volume() {
        let mut playback = StubVoicePlayback::default();

        assert_eq!(playback.volume(), 1.0);

        playback.set_volume(0.5).unwrap();
        assert_eq!(playback.volume(), 0.5);

        // Test clamping
        playback.set_volume(1.5).unwrap();
        assert_eq!(playback.volume(), 1.0);

        playback.set_volume(-0.5).unwrap();
        assert_eq!(playback.volume(), 0.0);
    }

    #[test]
    fn test_stub_playback_earcon() {
        let mut playback = StubVoicePlayback::default();

        // Default earcons should be available
        playback.play_earcon(EarconType::Success).unwrap();
        assert!(playback.is_playing());
    }

    #[test]
    fn test_volume_settings() {
        let mut settings = VolumeSettings::default();

        assert_eq!(settings.effective_voice(), 1.0);
        assert_eq!(settings.effective_earcon(), 0.7);

        settings.master = 0.5;
        assert_eq!(settings.effective_voice(), 0.5);
        assert!((settings.effective_earcon() - 0.35).abs() < 0.01);

        settings.muted = true;
        assert_eq!(settings.effective_voice(), 0.0);
        assert_eq!(settings.effective_earcon(), 0.0);
    }

    #[tokio::test]
    async fn test_playback_queue() {
        let queue = PlaybackQueue::new();

        assert!(queue.is_empty().await);

        queue.enqueue_earcon(EarconType::Success).await;
        queue.enqueue_earcon(EarconType::Error).await;

        assert_eq!(queue.len().await, 2);

        let item = queue.dequeue().await.unwrap();
        assert!(matches!(item, PlaybackItem::Earcon(EarconType::Success)));

        let item = queue.dequeue().await.unwrap();
        assert!(matches!(item, PlaybackItem::Earcon(EarconType::Error)));

        assert!(queue.is_empty().await);
    }
}

/*
 * kagami
 * The voice of the mesh.
 * h(x) >= 0. Always.
 */
