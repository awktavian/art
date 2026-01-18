//! Voice capture abstraction for cross-platform audio input.
//!
//! This module provides platform-agnostic traits for voice capture that
//! can be implemented by iOS (AVAudioEngine), Android (AudioRecord),
//! and desktop (cpal) platforms.
//!
//! Colony: Flow (e3) -- Sensing, adaptation
//!
//! h(x) >= 0. Always.

use super::types::{AudioChunk, AudioFormat};
use thiserror::Error;
use tokio::sync::mpsc;

// ============================================================================
// Error Categories
// ============================================================================

/// Error source category for diagnostic and recovery purposes.
///
/// This categorization helps identify:
/// - **HW**: Hardware-related issues (permission, device availability)
/// - **Encoding**: Audio format/encoding issues (can often be recovered by resampling)
/// - **Protocol**: State machine violations (e.g., stop when not running)
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorCategory {
    /// Hardware-related errors (microphone, speaker, device access)
    Hardware,
    /// Audio encoding/format errors (sample rate, channels, codec)
    Encoding,
    /// Protocol/state machine errors (invalid state transitions)
    Protocol,
}

// ============================================================================
// Voice Capture Errors
// ============================================================================

/// Errors that can occur during voice capture.
///
/// Each variant is categorized for easier error handling and recovery:
/// - Hardware errors may require user intervention (permissions, device check)
/// - Encoding errors can often be recovered by format conversion
/// - Protocol errors indicate logic bugs or invalid usage
#[derive(Debug, Error, Clone, uniffi::Error)]
pub enum VoiceCaptureError {
    /// Microphone access not authorized.
    /// Category: Hardware - requires user to grant permission.
    #[error("[HW] Microphone access not authorized")]
    NotAuthorized,

    /// No audio input device available.
    /// Category: Hardware - no microphone connected or accessible.
    #[error("[HW] No audio input device available")]
    NoInputDevice,

    /// Audio engine failed to initialize.
    /// Category: Hardware - typically driver or system audio service issues.
    #[error("[HW] Audio engine initialization failed: {message}")]
    InitializationFailed { message: String },

    /// Audio engine failed to start.
    /// Category: Hardware - device may be in use by another application.
    #[error("[HW] Audio engine start failed: {message}")]
    StartFailed { message: String },

    /// Audio capture is already running.
    /// Category: Protocol - invalid state transition, capture must be stopped first.
    #[error("[Protocol] Capture already running")]
    AlreadyRunning,

    /// Audio capture is not running.
    /// Category: Protocol - cannot stop what isn't started.
    #[error("[Protocol] Capture not running")]
    NotRunning,

    /// Buffer overflow (consumer too slow).
    /// Category: Protocol - consumer must read faster or buffer must be larger.
    #[error("[Protocol] Audio buffer overflow")]
    BufferOverflow,

    /// Invalid audio format.
    /// Category: Encoding - format not supported, try resampling.
    #[error("[Encoding] Invalid audio format: {message}")]
    InvalidFormat { message: String },

    /// Platform-specific error.
    /// Category: Hardware - platform-specific driver or API error.
    #[error("[HW] Platform error: {message}")]
    PlatformError { message: String },
}

impl VoiceCaptureError {
    /// Returns the error category for this error.
    ///
    /// Use this for programmatic error handling and recovery decisions.
    pub fn category(&self) -> ErrorCategory {
        match self {
            Self::NotAuthorized => ErrorCategory::Hardware,
            Self::NoInputDevice => ErrorCategory::Hardware,
            Self::InitializationFailed { .. } => ErrorCategory::Hardware,
            Self::StartFailed { .. } => ErrorCategory::Hardware,
            Self::AlreadyRunning => ErrorCategory::Protocol,
            Self::NotRunning => ErrorCategory::Protocol,
            Self::BufferOverflow => ErrorCategory::Protocol,
            Self::InvalidFormat { .. } => ErrorCategory::Encoding,
            Self::PlatformError { .. } => ErrorCategory::Hardware,
        }
    }

    /// Returns true if this error might be recoverable by retrying.
    pub fn is_recoverable(&self) -> bool {
        matches!(
            self,
            Self::BufferOverflow | Self::StartFailed { .. } | Self::InvalidFormat { .. }
        )
    }
}

// ============================================================================
// Voice Capture Callback
// ============================================================================

/// Callback for receiving audio chunks during capture.
pub type AudioChunkCallback = Box<dyn Fn(AudioChunk) + Send + Sync>;

/// Callback for audio level updates (for UI visualization).
pub type AudioLevelCallback = Box<dyn Fn(f32) + Send + Sync>;

// ============================================================================
// Voice Capture Trait
// ============================================================================

/// Platform-agnostic voice capture interface.
///
/// This trait defines the contract for voice capture implementations.
/// Each platform (iOS, Android, Desktop) provides its own implementation.
///
/// # Example Implementation (pseudocode)
///
/// ```ignore
/// struct IOSVoiceCapture {
///     audio_engine: AVAudioEngine,
///     format: AudioFormat,
///     is_recording: bool,
/// }
///
/// impl VoiceCapture for IOSVoiceCapture {
///     fn start_capture(&mut self) -> Result<(), VoiceCaptureError> {
///         self.audio_engine.start()
///     }
///     // ... other methods
/// }
/// ```
pub trait VoiceCapture: Send + Sync {
    /// Get the audio format being used for capture.
    fn format(&self) -> &AudioFormat;

    /// Check if capture is currently active.
    fn is_capturing(&self) -> bool;

    /// Request microphone authorization (platform-specific).
    ///
    /// Returns `true` if authorized, `false` otherwise.
    /// On platforms where authorization is automatic, this returns `true`.
    fn request_authorization(&self) -> bool;

    /// Check if microphone authorization is granted.
    fn is_authorized(&self) -> bool;

    /// Start audio capture.
    ///
    /// Audio chunks will be sent to the provided callback.
    fn start_capture(&mut self) -> Result<(), VoiceCaptureError>;

    /// Stop audio capture.
    fn stop_capture(&mut self) -> Result<(), VoiceCaptureError>;

    /// Get the current audio chunk if available.
    ///
    /// This is useful for pull-based capture where the caller
    /// periodically requests audio data.
    fn get_audio_chunk(&mut self) -> Option<AudioChunk>;

    /// Get the current audio level in dB.
    ///
    /// Returns a value typically in the range -60.0 to 0.0 dB.
    fn current_audio_level(&self) -> f32;

    /// Get the accumulated audio data since last call.
    ///
    /// This returns all audio captured since the last call to this method
    /// and clears the internal buffer.
    fn take_audio_data(&mut self) -> Vec<i16>;

    /// Get a copy of the current audio buffer without clearing it.
    ///
    /// Useful for wake word detection while continuing to capture.
    fn peek_audio_data(&self) -> Vec<i16>;

    /// Get the current buffer length in samples.
    fn buffer_length(&self) -> usize;
}

// ============================================================================
// Voice Capture Configuration
// ============================================================================

/// Configuration for voice capture.
#[derive(Debug, Clone)]
pub struct VoiceCaptureConfig {
    /// Audio format for capture
    pub format: AudioFormat,
    /// Buffer size in samples
    pub buffer_size: usize,
    /// Enable voice activity detection
    pub enable_vad: bool,
    /// Voice activity detection threshold in dB
    pub vad_threshold_db: f32,
}

impl Default for VoiceCaptureConfig {
    fn default() -> Self {
        Self {
            format: AudioFormat::speech_recognition(),
            buffer_size: 1024,
            enable_vad: true,
            vad_threshold_db: -40.0,
        }
    }
}

// ============================================================================
// Voice Capture Builder (for UniFFI)
// ============================================================================

/// Builder for creating platform voice capture instances.
///
/// Since traits cannot be directly exported via UniFFI, this builder
/// provides a way to create concrete implementations.
#[derive(Debug, Clone, uniffi::Record)]
pub struct VoiceCaptureParams {
    /// Sample rate in Hz
    pub sample_rate: u32,
    /// Number of channels
    pub channels: u8,
    /// Buffer size in samples
    pub buffer_size: u32,
    /// Voice activity detection threshold in dB
    pub vad_threshold_db: f32,
}

impl Default for VoiceCaptureParams {
    fn default() -> Self {
        Self {
            sample_rate: 16000,
            channels: 1,
            buffer_size: 1024,
            vad_threshold_db: -40.0,
        }
    }
}

impl VoiceCaptureParams {
    /// Create parameters for speech recognition.
    pub fn speech_recognition() -> Self {
        Self::default()
    }

    /// Create parameters optimized for watch.
    pub fn watch_optimized() -> Self {
        Self {
            sample_rate: 16000,
            channels: 1,
            buffer_size: 512,
            vad_threshold_db: -35.0,
        }
    }
}

// ============================================================================
// Stub Voice Capture (for testing and UniFFI)
// ============================================================================

/// A stub implementation of VoiceCapture for testing and as a reference.
///
/// This does not actually capture audio but provides the interface
/// that platform implementations should follow.
pub struct StubVoiceCapture {
    format: AudioFormat,
    is_capturing: bool,
    is_authorized: bool,
    buffer: Vec<i16>,
    sequence: u64,
    audio_level: f32,
}

impl Default for StubVoiceCapture {
    fn default() -> Self {
        Self::new(AudioFormat::speech_recognition())
    }
}

impl StubVoiceCapture {
    /// Create a new stub capture.
    pub fn new(format: AudioFormat) -> Self {
        Self {
            format,
            is_capturing: false,
            is_authorized: true,
            buffer: Vec::new(),
            sequence: 0,
            audio_level: -60.0,
        }
    }

    /// Set authorization status (for testing).
    pub fn set_authorized(&mut self, authorized: bool) {
        self.is_authorized = authorized;
    }

    /// Push test audio data.
    pub fn push_test_data(&mut self, samples: &[i16]) {
        self.buffer.extend_from_slice(samples);
        // Calculate RMS level
        if !samples.is_empty() {
            let sum_squares: f64 = samples.iter().map(|&s| (s as f64).powi(2)).sum();
            let rms = (sum_squares / samples.len() as f64).sqrt();
            self.audio_level = 20.0 * (rms / i16::MAX as f64).log10() as f32;
        }
    }
}

impl VoiceCapture for StubVoiceCapture {
    fn format(&self) -> &AudioFormat {
        &self.format
    }

    fn is_capturing(&self) -> bool {
        self.is_capturing
    }

    fn request_authorization(&self) -> bool {
        self.is_authorized
    }

    fn is_authorized(&self) -> bool {
        self.is_authorized
    }

    fn start_capture(&mut self) -> Result<(), VoiceCaptureError> {
        if !self.is_authorized {
            return Err(VoiceCaptureError::NotAuthorized);
        }
        if self.is_capturing {
            return Err(VoiceCaptureError::AlreadyRunning);
        }
        self.is_capturing = true;
        self.sequence = 0;
        Ok(())
    }

    fn stop_capture(&mut self) -> Result<(), VoiceCaptureError> {
        if !self.is_capturing {
            return Err(VoiceCaptureError::NotRunning);
        }
        self.is_capturing = false;
        Ok(())
    }

    fn get_audio_chunk(&mut self) -> Option<AudioChunk> {
        if !self.is_capturing || self.buffer.is_empty() {
            return None;
        }

        // Convert i16 samples to bytes
        let bytes: Vec<u8> = self
            .buffer
            .iter()
            .flat_map(|&s| s.to_le_bytes())
            .collect();

        self.buffer.clear();
        self.sequence += 1;

        Some(AudioChunk::new(
            bytes,
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_millis() as u64)
                .unwrap_or(0),
            self.sequence,
        ))
    }

    fn current_audio_level(&self) -> f32 {
        self.audio_level
    }

    fn take_audio_data(&mut self) -> Vec<i16> {
        std::mem::take(&mut self.buffer)
    }

    fn peek_audio_data(&self) -> Vec<i16> {
        self.buffer.clone()
    }

    fn buffer_length(&self) -> usize {
        self.buffer.len()
    }
}

// ============================================================================
// Async Voice Capture Wrapper
// ============================================================================

/// Async wrapper for voice capture with channel-based audio delivery.
pub struct AsyncVoiceCapture<C: VoiceCapture> {
    capture: C,
    chunk_tx: Option<mpsc::Sender<AudioChunk>>,
}

impl<C: VoiceCapture> AsyncVoiceCapture<C> {
    /// Create a new async wrapper.
    pub fn new(capture: C) -> Self {
        Self {
            capture,
            chunk_tx: None,
        }
    }

    /// Start capture and return a receiver for audio chunks.
    pub fn start(&mut self) -> Result<mpsc::Receiver<AudioChunk>, VoiceCaptureError> {
        let (tx, rx) = mpsc::channel(64);
        self.chunk_tx = Some(tx);
        self.capture.start_capture()?;
        Ok(rx)
    }

    /// Stop capture.
    pub fn stop(&mut self) -> Result<(), VoiceCaptureError> {
        self.chunk_tx = None;
        self.capture.stop_capture()
    }

    /// Poll for audio and send to channel.
    pub async fn poll_and_send(&mut self) {
        if let Some(chunk) = self.capture.get_audio_chunk() {
            if let Some(tx) = &self.chunk_tx {
                let _ = tx.send(chunk).await;
            }
        }
    }

    /// Get inner capture reference.
    pub fn inner(&self) -> &C {
        &self.capture
    }

    /// Get inner capture mutable reference.
    pub fn inner_mut(&mut self) -> &mut C {
        &mut self.capture
    }
}

// ============================================================================
// Voice Activity Detection
// ============================================================================

/// Simple voice activity detection.
pub struct VoiceActivityDetector {
    threshold_db: f32,
    last_voice_time: Option<std::time::Instant>,
    silence_duration: std::time::Duration,
}

impl VoiceActivityDetector {
    /// Create a new VAD with threshold in dB.
    pub fn new(threshold_db: f32, silence_duration: std::time::Duration) -> Self {
        Self {
            threshold_db,
            last_voice_time: None,
            silence_duration,
        }
    }

    /// Update with audio samples and return if voice is detected.
    pub fn update(&mut self, samples: &[i16]) -> bool {
        let level_db = calculate_rms_db(samples);
        let is_voice = level_db > self.threshold_db;

        if is_voice {
            self.last_voice_time = Some(std::time::Instant::now());
        }

        is_voice
    }

    /// Check if silence has been detected for longer than the threshold.
    pub fn is_silence_timeout(&self) -> bool {
        if let Some(last_voice) = self.last_voice_time {
            last_voice.elapsed() > self.silence_duration
        } else {
            true
        }
    }

    /// Reset the detector.
    pub fn reset(&mut self) {
        self.last_voice_time = None;
    }
}

// ============================================================================
// Audio Utility Functions
// ============================================================================

/// Calculate RMS (root mean square) level in dB from i16 samples.
pub fn calculate_rms_db(samples: &[i16]) -> f32 {
    if samples.is_empty() {
        return -100.0;
    }

    let sum_squares: f64 = samples.iter().map(|&s| (s as f64).powi(2)).sum();
    let rms = (sum_squares / samples.len() as f64).sqrt();
    let max_amplitude = i16::MAX as f64;

    if rms > 0.0 {
        20.0 * (rms / max_amplitude).log10() as f32
    } else {
        -100.0
    }
}

/// Calculate RMS level in dB from f32 samples.
pub fn calculate_rms_db_f32(samples: &[f32]) -> f32 {
    if samples.is_empty() {
        return -100.0;
    }

    let sum_squares: f64 = samples.iter().map(|&s| (s as f64).powi(2)).sum();
    let rms = (sum_squares / samples.len() as f64).sqrt();

    if rms > 0.0 {
        20.0 * rms.log10() as f32
    } else {
        -100.0
    }
}

/// Detect silence in samples.
pub fn detect_silence(samples: &[i16], threshold_db: f32) -> bool {
    calculate_rms_db(samples) < threshold_db
}

/// Convert f32 samples to i16.
pub fn f32_to_i16(samples: &[f32]) -> Vec<i16> {
    samples
        .iter()
        .map(|&s| {
            let clamped = s.clamp(-1.0, 1.0);
            (clamped * i16::MAX as f32) as i16
        })
        .collect()
}

/// Convert i16 samples to f32.
pub fn i16_to_f32(samples: &[i16]) -> Vec<f32> {
    samples.iter().map(|&s| s as f32 / i16::MAX as f32).collect()
}

/// Convert i16 samples to bytes (little-endian).
pub fn i16_to_bytes(samples: &[i16]) -> Vec<u8> {
    samples.iter().flat_map(|&s| s.to_le_bytes()).collect()
}

/// Convert bytes to i16 samples (little-endian).
pub fn bytes_to_i16(bytes: &[u8]) -> Vec<i16> {
    bytes
        .chunks_exact(2)
        .map(|chunk| i16::from_le_bytes([chunk[0], chunk[1]]))
        .collect()
}

// ============================================================================
// UniFFI Exports
// ============================================================================

/// Create default voice capture parameters.
#[uniffi::export]
pub fn voice_capture_params_new() -> VoiceCaptureParams {
    VoiceCaptureParams::default()
}

/// Create voice capture parameters for speech recognition.
#[uniffi::export]
pub fn voice_capture_params_speech() -> VoiceCaptureParams {
    VoiceCaptureParams::speech_recognition()
}

/// Create voice capture parameters for watch.
#[uniffi::export]
pub fn voice_capture_params_watch() -> VoiceCaptureParams {
    VoiceCaptureParams::watch_optimized()
}

/// Calculate audio level in dB from raw samples.
#[uniffi::export]
pub fn calculate_audio_level_db(samples: Vec<i16>) -> f32 {
    calculate_rms_db(&samples)
}

/// Check if audio samples are silent.
#[uniffi::export]
pub fn is_audio_silent(samples: Vec<i16>, threshold_db: f32) -> bool {
    detect_silence(&samples, threshold_db)
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_stub_capture_lifecycle() {
        let mut capture = StubVoiceCapture::default();

        assert!(!capture.is_capturing());
        assert!(capture.is_authorized());

        capture.start_capture().unwrap();
        assert!(capture.is_capturing());

        capture.stop_capture().unwrap();
        assert!(!capture.is_capturing());
    }

    #[test]
    fn test_stub_capture_not_authorized() {
        let mut capture = StubVoiceCapture::default();
        capture.set_authorized(false);

        let result = capture.start_capture();
        assert!(matches!(result, Err(VoiceCaptureError::NotAuthorized)));
    }

    #[test]
    fn test_stub_capture_already_running() {
        let mut capture = StubVoiceCapture::default();
        capture.start_capture().unwrap();

        let result = capture.start_capture();
        assert!(matches!(result, Err(VoiceCaptureError::AlreadyRunning)));
    }

    #[test]
    fn test_stub_capture_audio_chunk() {
        let mut capture = StubVoiceCapture::default();
        capture.start_capture().unwrap();

        // Push test data
        capture.push_test_data(&[100, 200, 300, 400]);

        let chunk = capture.get_audio_chunk().unwrap();
        assert_eq!(chunk.sequence, 1);
        assert!(!chunk.is_final);
        assert_eq!(chunk.data.len(), 8); // 4 samples * 2 bytes
    }

    #[test]
    fn test_calculate_rms_db() {
        // Silence
        let silence = vec![0i16; 1000];
        assert_eq!(calculate_rms_db(&silence), -100.0);

        // Max amplitude
        let max = vec![i16::MAX; 1000];
        let level = calculate_rms_db(&max);
        assert!(level > -1.0 && level <= 0.0);
    }

    #[test]
    fn test_detect_silence() {
        let silence = vec![0i16; 1000];
        assert!(detect_silence(&silence, -40.0));

        let loud = vec![10000i16; 1000];
        assert!(!detect_silence(&loud, -40.0));
    }

    #[test]
    fn test_f32_i16_conversion() {
        let f32_samples = vec![0.5f32, -0.5, 0.0, 1.0, -1.0];
        let i16_samples = f32_to_i16(&f32_samples);

        assert_eq!(i16_samples[0], 16383); // ~0.5 * 32767
        assert_eq!(i16_samples[2], 0);
        assert_eq!(i16_samples[3], 32767);
        assert_eq!(i16_samples[4], -32767);
    }

    #[test]
    fn test_bytes_i16_conversion() {
        let samples = vec![1000i16, -2000, 32767, -32768];
        let bytes = i16_to_bytes(&samples);
        let recovered = bytes_to_i16(&bytes);

        assert_eq!(samples, recovered);
    }

    #[test]
    fn test_voice_activity_detector() {
        let mut vad = VoiceActivityDetector::new(-30.0, std::time::Duration::from_secs(2));

        // Silent samples
        let silence = vec![0i16; 1000];
        assert!(!vad.update(&silence));

        // Loud samples
        let loud = vec![10000i16; 1000];
        assert!(vad.update(&loud));
    }
}

/*
 * kagami
 * The ears of the mesh.
 * h(x) >= 0. Always.
 */
