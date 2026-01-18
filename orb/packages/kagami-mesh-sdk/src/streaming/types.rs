//! Voice streaming types for cross-platform audio communication.
//!
//! This module provides unified types for voice capture, streaming, and playback
//! across iOS, Android, watchOS, visionOS, and Desktop platforms.
//!
//! Colony: Beacon (e5) -- Communication
//!
//! h(x) >= 0. Always.

use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use serde::{Deserialize, Serialize};
use std::time::Duration;

// ============================================================================
// Audio Format Types
// ============================================================================

/// Audio encoding format for voice data.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, uniffi::Enum)]
pub enum AudioEncoding {
    /// 16-bit signed PCM (standard for speech processing)
    Pcm16,
    /// 32-bit floating point PCM
    Pcm32Float,
    /// Opus encoded (for efficient streaming)
    Opus,
    /// AAC encoded
    Aac,
}

impl Default for AudioEncoding {
    fn default() -> Self {
        Self::Pcm16
    }
}

/// Audio format specification for voice data.
///
/// Defines the sample rate, channel count, and encoding for audio data.
/// Default values are optimized for speech recognition (16kHz mono PCM16).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize, uniffi::Record)]
pub struct AudioFormat {
    /// Sample rate in Hz (e.g., 16000 for Whisper STT)
    pub sample_rate: u32,
    /// Number of audio channels (1 = mono, 2 = stereo)
    pub channels: u8,
    /// Audio encoding format
    pub encoding: AudioEncoding,
    /// Bits per sample (typically 16 for PCM16)
    pub bits_per_sample: u8,
}

impl Default for AudioFormat {
    fn default() -> Self {
        Self {
            sample_rate: 16000,     // Whisper STT optimal
            channels: 1,           // Mono for speech
            bits_per_sample: 16,   // Standard PCM
            encoding: AudioEncoding::Pcm16,
        }
    }
}

impl AudioFormat {
    /// Create a format optimized for speech recognition (16kHz mono PCM16).
    pub fn speech_recognition() -> Self {
        Self::default()
    }

    /// Create a high-quality format for TTS playback (48kHz stereo).
    pub fn tts_playback() -> Self {
        Self {
            sample_rate: 48000,
            channels: 2,
            bits_per_sample: 16,
            encoding: AudioEncoding::Pcm16,
        }
    }

    /// Create a watch-optimized format (16kHz mono, smaller buffer).
    pub fn watch_optimized() -> Self {
        Self {
            sample_rate: 16000,
            channels: 1,
            bits_per_sample: 16,
            encoding: AudioEncoding::Pcm16,
        }
    }

    /// Validate the audio format parameters.
    ///
    /// Returns an error string if the format is invalid.
    /// Valid formats require:
    /// - sample_rate > 0
    /// - channels > 0
    /// - bits_per_sample divisible by 8 (8, 16, 24, 32)
    pub fn validate(&self) -> Result<(), &'static str> {
        if self.sample_rate == 0 {
            return Err("sample_rate must be non-zero");
        }
        if self.channels == 0 {
            return Err("channels must be non-zero");
        }
        if self.bits_per_sample == 0 {
            return Err("bits_per_sample must be non-zero");
        }
        if self.bits_per_sample % 8 != 0 {
            return Err("bits_per_sample must be divisible by 8 (e.g., 8, 16, 24, 32)");
        }
        Ok(())
    }

    /// Check if this format is valid.
    pub fn is_valid(&self) -> bool {
        self.validate().is_ok()
    }

    /// Calculate bytes per sample (channels * bits_per_sample / 8).
    ///
    /// Returns 0 if bits_per_sample is 0 or not divisible by 8 to prevent
    /// division by zero in callers. Use `validate()` to check format validity.
    pub fn bytes_per_sample(&self) -> usize {
        if self.bits_per_sample == 0 || self.bits_per_sample % 8 != 0 {
            return 0;
        }
        (self.channels as usize) * (self.bits_per_sample as usize) / 8
    }

    /// Calculate bytes per second for this format.
    ///
    /// Returns 0 if format parameters are invalid.
    pub fn bytes_per_second(&self) -> usize {
        let bps = self.bytes_per_sample();
        if bps == 0 {
            return 0;
        }
        (self.sample_rate as usize) * bps
    }

    /// Calculate the duration represented by a given number of bytes.
    ///
    /// Returns Duration::ZERO if format parameters are invalid.
    pub fn duration_for_bytes(&self, bytes: usize) -> Duration {
        let bps = self.bytes_per_sample();
        if bps == 0 || self.sample_rate == 0 {
            return Duration::ZERO;
        }
        let samples = bytes / bps;
        Duration::from_secs_f64(samples as f64 / self.sample_rate as f64)
    }

    /// Calculate the number of bytes for a given duration.
    ///
    /// Returns 0 if format parameters are invalid.
    pub fn bytes_for_duration(&self, duration: Duration) -> usize {
        let bps = self.bytes_per_second();
        if bps == 0 {
            return 0;
        }
        let seconds = duration.as_secs_f64();
        (seconds * bps as f64) as usize
    }
}

// ============================================================================
// Audio Chunk Types
// ============================================================================

/// A chunk of audio data with metadata for streaming.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AudioChunk {
    /// Raw audio data (PCM samples as bytes)
    pub data: Vec<u8>,
    /// Timestamp in milliseconds from stream start
    pub timestamp_ms: u64,
    /// Sequence number for ordering
    pub sequence: u64,
    /// Whether this is the final chunk in a stream
    pub is_final: bool,
    /// Audio format for this chunk (if different from stream default)
    pub format: Option<AudioFormat>,
}

impl AudioChunk {
    /// Create a new audio chunk.
    pub fn new(data: Vec<u8>, timestamp_ms: u64, sequence: u64) -> Self {
        Self {
            data,
            timestamp_ms,
            sequence,
            is_final: false,
            format: None,
        }
    }

    /// Create a final chunk (marks end of stream).
    pub fn final_chunk(timestamp_ms: u64, sequence: u64) -> Self {
        Self {
            data: Vec::new(),
            timestamp_ms,
            sequence,
            is_final: true,
            format: None,
        }
    }

    /// Mark this chunk as final.
    pub fn with_final(mut self) -> Self {
        self.is_final = true;
        self
    }

    /// Set the format for this chunk.
    pub fn with_format(mut self, format: AudioFormat) -> Self {
        self.format = Some(format);
        self
    }

    /// Calculate duration of audio in this chunk.
    pub fn duration(&self, default_format: &AudioFormat) -> Duration {
        let format = self.format.as_ref().unwrap_or(default_format);
        format.duration_for_bytes(self.data.len())
    }

    /// Get the sample count in this chunk.
    pub fn sample_count(&self, default_format: &AudioFormat) -> usize {
        let format = self.format.as_ref().unwrap_or(default_format);
        self.data.len() / format.bytes_per_sample()
    }
}

/// UniFFI-compatible audio chunk (uses base64-encoded data).
#[derive(Debug, Clone, Serialize, Deserialize, uniffi::Record)]
pub struct AudioChunkData {
    /// Base64-encoded audio data
    pub data_base64: String,
    /// Timestamp in milliseconds from stream start
    pub timestamp_ms: u64,
    /// Sequence number for ordering
    pub sequence: u64,
    /// Whether this is the final chunk in a stream
    pub is_final: bool,
}

impl From<AudioChunk> for AudioChunkData {
    fn from(chunk: AudioChunk) -> Self {
        Self {
            data_base64: BASE64.encode(&chunk.data),
            timestamp_ms: chunk.timestamp_ms,
            sequence: chunk.sequence,
            is_final: chunk.is_final,
        }
    }
}

impl AudioChunkData {
    /// Decode to AudioChunk.
    pub fn to_audio_chunk(&self) -> Result<AudioChunk, base64::DecodeError> {
        Ok(AudioChunk {
            data: BASE64.decode(&self.data_base64)?,
            timestamp_ms: self.timestamp_ms,
            sequence: self.sequence,
            is_final: self.is_final,
            format: None,
        })
    }
}

// ============================================================================
// Voice Configuration
// ============================================================================

/// Configuration for voice streaming.
#[derive(Debug, Clone, Serialize, Deserialize, uniffi::Record)]
pub struct VoiceConfig {
    /// WebSocket endpoint URL for voice streaming
    pub endpoint: String,
    /// Connection timeout in milliseconds
    pub timeout_ms: u64,
    /// Audio buffer size in samples
    pub buffer_size: u32,
    /// Maximum listening duration in seconds
    pub max_listening_duration_secs: u32,
    /// Silence threshold in dB (typically -40 to -30)
    pub silence_threshold_db: f32,
    /// Silence duration to trigger auto-stop (milliseconds)
    pub silence_auto_stop_ms: u64,
    /// Enable automatic reconnection
    pub auto_reconnect: bool,
    /// Maximum reconnection attempts (0 = unlimited)
    pub max_reconnect_attempts: u32,
    /// Audio format for capture
    pub capture_format: AudioFormat,
    /// Audio format for playback
    pub playback_format: AudioFormat,
}

impl Default for VoiceConfig {
    fn default() -> Self {
        Self {
            endpoint: String::new(),
            timeout_ms: 30000,              // 30 seconds
            buffer_size: 1024,              // ~64ms at 16kHz
            max_listening_duration_secs: 30,
            silence_threshold_db: -40.0,
            silence_auto_stop_ms: 2000,     // 2 seconds of silence
            auto_reconnect: true,
            max_reconnect_attempts: 5,
            capture_format: AudioFormat::speech_recognition(),
            playback_format: AudioFormat::tts_playback(),
        }
    }
}

impl VoiceConfig {
    /// Create a config with the specified endpoint.
    pub fn with_endpoint(endpoint: impl Into<String>) -> Self {
        Self {
            endpoint: endpoint.into(),
            ..Default::default()
        }
    }

    /// Create a watch-optimized config.
    pub fn watch_optimized(endpoint: impl Into<String>) -> Self {
        Self {
            endpoint: endpoint.into(),
            timeout_ms: 10000,             // Shorter timeout for watch
            buffer_size: 512,              // Smaller buffer for watch
            max_listening_duration_secs: 15, // Shorter max duration
            capture_format: AudioFormat::watch_optimized(),
            playback_format: AudioFormat::watch_optimized(),
            ..Default::default()
        }
    }

    /// Convert HTTP endpoint to WebSocket endpoint.
    pub fn websocket_url(&self) -> String {
        let url = &self.endpoint;
        if url.starts_with("ws://") || url.starts_with("wss://") {
            url.clone()
        } else if url.starts_with("https://") {
            url.replace("https://", "wss://")
        } else if url.starts_with("http://") {
            url.replace("http://", "ws://")
        } else {
            format!("wss://{}", url)
        }
    }

    /// Get buffer duration in milliseconds.
    pub fn buffer_duration_ms(&self) -> u64 {
        let samples_per_ms = self.capture_format.sample_rate as u64 / 1000;
        if samples_per_ms > 0 {
            self.buffer_size as u64 / samples_per_ms
        } else {
            0
        }
    }
}

// ============================================================================
// Voice Streaming State
// ============================================================================

/// State of the voice streaming session.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, uniffi::Enum)]
pub enum VoiceStreamState {
    /// Not connected, idle
    Idle,
    /// Establishing connection
    Connecting,
    /// Connected, ready to stream
    Ready,
    /// Actively capturing audio
    Listening,
    /// Processing captured audio (STT)
    Processing,
    /// Playing back TTS response
    Speaking,
    /// Error state
    Error,
    /// Disconnected, may reconnect
    Disconnected,
}

impl VoiceStreamState {
    /// Check if currently active (capturing or playing).
    pub fn is_active(&self) -> bool {
        matches!(self, Self::Listening | Self::Processing | Self::Speaking)
    }

    /// Check if connected to server.
    pub fn is_connected(&self) -> bool {
        matches!(self, Self::Ready | Self::Listening | Self::Processing | Self::Speaking)
    }

    /// Check if in an error state.
    pub fn is_error(&self) -> bool {
        matches!(self, Self::Error)
    }
}

// ============================================================================
// Message Types for WebSocket Protocol
// ============================================================================

/// Message types for voice WebSocket protocol.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum VoiceMessage {
    /// Audio data chunk from client
    AudioChunk {
        data: String,  // Base64 encoded
        timestamp_ms: u64,
        sequence: u64,
    },

    /// End of speech signal from client
    EndOfSpeech {
        timestamp: String,  // ISO8601
    },

    /// Partial transcript update from server
    Transcript {
        text: String,
        is_final: bool,
    },

    /// Final transcript from server
    FinalTranscript {
        text: String,
    },

    /// Response text from server (Kagami's reply)
    Response {
        text: String,
        intent: Option<String>,
    },

    /// TTS audio response from server
    TtsAudio {
        data: String,  // Base64 encoded
        format: Option<AudioFormat>,
    },

    /// Error message from server
    Error {
        message: String,
        code: Option<String>,
    },

    /// Session start acknowledgement
    SessionStart {
        session_id: String,
    },

    /// Session end acknowledgement
    SessionEnd {
        session_id: String,
        duration_ms: u64,
    },

    /// Ping/pong for keepalive
    Ping {
        timestamp_ms: u64,
    },

    /// Pong response
    Pong {
        timestamp_ms: u64,
    },
}

impl VoiceMessage {
    /// Create an audio chunk message.
    pub fn audio_chunk(chunk: &AudioChunk) -> Self {
        Self::AudioChunk {
            data: BASE64.encode(&chunk.data),
            timestamp_ms: chunk.timestamp_ms,
            sequence: chunk.sequence,
        }
    }

    /// Create an end of speech message.
    pub fn end_of_speech() -> Self {
        Self::EndOfSpeech {
            timestamp: chrono::Utc::now().to_rfc3339(),
        }
    }

    /// Create an error message.
    pub fn error(message: impl Into<String>, code: Option<String>) -> Self {
        Self::Error {
            message: message.into(),
            code,
        }
    }

    /// Serialize to JSON string.
    pub fn to_json(&self) -> Result<String, serde_json::Error> {
        serde_json::to_string(self)
    }

    /// Deserialize from JSON string.
    pub fn from_json(json: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(json)
    }
}

// ============================================================================
// Transcription Result
// ============================================================================

/// Result of speech-to-text transcription.
#[derive(Debug, Clone, Serialize, Deserialize, uniffi::Record)]
pub struct TranscriptionResult {
    /// Transcribed text
    pub text: String,
    /// Whether this is the final transcription
    pub is_final: bool,
    /// Confidence score (0.0 to 1.0)
    pub confidence: Option<f32>,
    /// Language detected
    pub language: Option<String>,
    /// Duration of audio processed in milliseconds
    pub duration_ms: u64,
}

// ============================================================================
// TTS Response
// ============================================================================

/// Response containing text-to-speech audio.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TtsResponse {
    /// Raw audio data
    pub audio_data: Vec<u8>,
    /// Audio format
    pub format: AudioFormat,
    /// Text that was spoken
    pub text: String,
    /// Duration in milliseconds
    pub duration_ms: u64,
}

/// UniFFI-compatible TTS response.
#[derive(Debug, Clone, Serialize, Deserialize, uniffi::Record)]
pub struct TtsResponseData {
    /// Base64-encoded audio data
    pub audio_data_base64: String,
    /// Sample rate
    pub sample_rate: u32,
    /// Number of channels
    pub channels: u8,
    /// Text that was spoken
    pub text: String,
    /// Duration in milliseconds
    pub duration_ms: u64,
}

impl From<TtsResponse> for TtsResponseData {
    fn from(response: TtsResponse) -> Self {
        Self {
            audio_data_base64: BASE64.encode(&response.audio_data),
            sample_rate: response.format.sample_rate,
            channels: response.format.channels,
            text: response.text,
            duration_ms: response.duration_ms,
        }
    }
}

// ============================================================================
// Earcon Types
// ============================================================================

/// Earcon identifier for sound effects.
///
/// Each earcon has specific audio characteristics designed to convey meaning
/// through sound. These are NOT just alerts - they're part of Kagami's voice.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize, uniffi::Enum)]
pub enum EarconType {
    /// Sound played when starting to listen
    ListeningStart,
    /// Sound played when listening stops
    ListeningStop,
    /// Sound played on successful processing
    Success,
    /// Sound played on error
    Error,
    /// Sound played when connection is established
    Connected,
    /// Sound played when connection is lost
    Disconnected,
    /// Sound played when Kagami starts speaking
    SpeakingStart,
    /// Sound played when Kagami finishes speaking
    SpeakingEnd,
    /// Notification sound
    Notification,
}

// ============================================================================
// Earcon Audio Specifications
// ============================================================================

/// Detailed audio specifications for an earcon.
///
/// These specs ensure consistent, high-quality earcons across all platforms.
/// Audio engineers: follow these specs when creating earcon assets.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EarconSpec {
    /// Fundamental frequency in Hz (the "note")
    pub frequency_hz: f32,
    /// Secondary frequency for harmonics/chords (optional)
    pub secondary_hz: Option<f32>,
    /// Duration in milliseconds
    pub duration_ms: u32,
    /// Attack time (fade in) in milliseconds
    pub attack_ms: u32,
    /// Release time (fade out) in milliseconds
    pub release_ms: u32,
    /// Peak amplitude (0.0 to 1.0)
    pub amplitude: f32,
    /// Waveform type
    pub waveform: WaveformType,
    /// Emotional intent / design notes
    pub design_notes: &'static str,
}

/// Waveform type for synthesized earcons.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum WaveformType {
    /// Pure sine wave (soft, organic)
    Sine,
    /// Triangle wave (warm, slightly brighter)
    Triangle,
    /// Square wave (digital, assertive)
    Square,
    /// Complex/layered (use audio file)
    Complex,
}

impl EarconType {
    /// Get the audio specification for this earcon type.
    ///
    /// These specifications are tuned for:
    /// - Clarity without being jarring
    /// - Emotional resonance
    /// - Accessibility (not too high/low frequency)
    /// - Kagami's personality (warm, competent, joyful)
    pub fn spec(&self) -> EarconSpec {
        match self {
            // -------------------------------------------------------------
            // LISTENING START: "I'm here, I'm listening"
            // Ascending tone, inviting, warm
            // Musical: C5 to E5 glide (major third = optimism)
            // -------------------------------------------------------------
            EarconType::ListeningStart => EarconSpec {
                frequency_hz: 523.25,      // C5
                secondary_hz: Some(659.25), // E5 (major third)
                duration_ms: 150,
                attack_ms: 10,
                release_ms: 50,
                amplitude: 0.4,
                waveform: WaveformType::Sine,
                design_notes: "Ascending major third. Warm, inviting. Says 'I'm ready for you.'",
            },

            // -------------------------------------------------------------
            // LISTENING STOP: "Got it, processing"
            // Soft descending acknowledgment
            // Musical: E5 to C5 (inverse of start)
            // -------------------------------------------------------------
            EarconType::ListeningStop => EarconSpec {
                frequency_hz: 659.25,      // E5
                secondary_hz: Some(523.25), // C5
                duration_ms: 120,
                attack_ms: 5,
                release_ms: 60,
                amplitude: 0.35,
                waveform: WaveformType::Sine,
                design_notes: "Descending mirror of ListeningStart. Gentle closure.",
            },

            // -------------------------------------------------------------
            // SUCCESS: "Yes! Nailed it!"
            // Bright, celebratory, satisfying
            // Musical: C5-E5-G5 major chord arpeggio
            // -------------------------------------------------------------
            EarconType::Success => EarconSpec {
                frequency_hz: 523.25,      // C5 (root)
                secondary_hz: Some(783.99), // G5 (fifth)
                duration_ms: 200,
                attack_ms: 5,
                release_ms: 80,
                amplitude: 0.5,
                waveform: WaveformType::Triangle,
                design_notes: "Major chord arpeggio. Triumphant but not obnoxious. Pure joy.",
            },

            // -------------------------------------------------------------
            // ERROR: "Oops, something went wrong"
            // Not alarming, just informative
            // Musical: Minor second (tension without panic)
            // -------------------------------------------------------------
            EarconType::Error => EarconSpec {
                frequency_hz: 329.63,      // E4
                secondary_hz: Some(349.23), // F4 (minor second)
                duration_ms: 180,
                attack_ms: 10,
                release_ms: 70,
                amplitude: 0.4,
                waveform: WaveformType::Triangle,
                design_notes: "Minor second for tension. Not scary - just 'attention needed.'",
            },

            // -------------------------------------------------------------
            // CONNECTED: "We're linked!"
            // Crisp, confident, establishing
            // Musical: Perfect fifth (stability)
            // -------------------------------------------------------------
            EarconType::Connected => EarconSpec {
                frequency_hz: 440.0,       // A4
                secondary_hz: Some(659.25), // E5 (perfect fifth)
                duration_ms: 100,
                attack_ms: 5,
                release_ms: 40,
                amplitude: 0.45,
                waveform: WaveformType::Sine,
                design_notes: "Perfect fifth = stability. Clean, confident. 'Connection established.'",
            },

            // -------------------------------------------------------------
            // DISCONNECTED: "Lost connection"
            // Fading, descending, but not alarming
            // Musical: Descending minor third
            // -------------------------------------------------------------
            EarconType::Disconnected => EarconSpec {
                frequency_hz: 392.0,       // G4
                secondary_hz: Some(329.63), // E4
                duration_ms: 200,
                attack_ms: 10,
                release_ms: 100,
                amplitude: 0.35,
                waveform: WaveformType::Sine,
                design_notes: "Gentle fade-out. Not alarming - just 'I'll be back.'",
            },

            // -------------------------------------------------------------
            // SPEAKING START: "Here comes my response"
            // Quick, subtle attention-getter
            // Musical: Single soft note
            // -------------------------------------------------------------
            EarconType::SpeakingStart => EarconSpec {
                frequency_hz: 440.0,       // A4
                secondary_hz: None,
                duration_ms: 50,
                attack_ms: 5,
                release_ms: 20,
                amplitude: 0.3,
                waveform: WaveformType::Sine,
                design_notes: "Subtle 'ahem.' Draws attention without interrupting.",
            },

            // -------------------------------------------------------------
            // SPEAKING END: "That's all I had to say"
            // Soft closure
            // Musical: Gentle descending tone
            // -------------------------------------------------------------
            EarconType::SpeakingEnd => EarconSpec {
                frequency_hz: 392.0,       // G4
                secondary_hz: None,
                duration_ms: 60,
                attack_ms: 5,
                release_ms: 30,
                amplitude: 0.25,
                waveform: WaveformType::Sine,
                design_notes: "Soft period at end of sentence. 'Your turn.'",
            },

            // -------------------------------------------------------------
            // NOTIFICATION: "Something needs your attention"
            // Distinctive but not jarring
            // Musical: Major second (attention without urgency)
            // -------------------------------------------------------------
            EarconType::Notification => EarconSpec {
                frequency_hz: 523.25,      // C5
                secondary_hz: Some(587.33), // D5
                duration_ms: 150,
                attack_ms: 10,
                release_ms: 60,
                amplitude: 0.45,
                waveform: WaveformType::Triangle,
                design_notes: "Two-note 'ding-dong.' Friendly, clear, not annoying.",
            },
        }
    }
}

// ============================================================================
// UniFFI Exports
// ============================================================================

/// Create default audio format for speech recognition.
#[uniffi::export]
pub fn audio_format_speech() -> AudioFormat {
    AudioFormat::speech_recognition()
}

/// Create audio format for TTS playback.
#[uniffi::export]
pub fn audio_format_tts() -> AudioFormat {
    AudioFormat::tts_playback()
}

/// Create watch-optimized audio format.
#[uniffi::export]
pub fn audio_format_watch() -> AudioFormat {
    AudioFormat::watch_optimized()
}

/// Create default voice config with endpoint.
#[uniffi::export]
pub fn voice_config_new(endpoint: String) -> VoiceConfig {
    VoiceConfig::with_endpoint(endpoint)
}

/// Create watch-optimized voice config.
#[uniffi::export]
pub fn voice_config_watch(endpoint: String) -> VoiceConfig {
    VoiceConfig::watch_optimized(endpoint)
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_audio_format_defaults() {
        let format = AudioFormat::default();
        assert_eq!(format.sample_rate, 16000);
        assert_eq!(format.channels, 1);
        assert_eq!(format.bits_per_sample, 16);
    }

    #[test]
    fn test_audio_format_bytes_per_sample() {
        let mono = AudioFormat::speech_recognition();
        assert_eq!(mono.bytes_per_sample(), 2); // 1 channel * 16 bits / 8

        let stereo = AudioFormat::tts_playback();
        assert_eq!(stereo.bytes_per_sample(), 4); // 2 channels * 16 bits / 8
    }

    #[test]
    fn test_audio_format_bytes_per_second() {
        let format = AudioFormat::speech_recognition();
        assert_eq!(format.bytes_per_second(), 32000); // 16000 * 2
    }

    #[test]
    fn test_audio_chunk_duration() {
        let format = AudioFormat::speech_recognition();
        let chunk = AudioChunk::new(vec![0; 3200], 0, 0); // 100ms at 16kHz mono 16-bit
        let duration = chunk.duration(&format);
        assert_eq!(duration.as_millis(), 100);
    }

    #[test]
    fn test_voice_config_websocket_url() {
        let config = VoiceConfig::with_endpoint("https://api.example.com/ws/voice");
        assert_eq!(config.websocket_url(), "wss://api.example.com/ws/voice");

        let config2 = VoiceConfig::with_endpoint("http://localhost:8080");
        assert_eq!(config2.websocket_url(), "ws://localhost:8080");

        let config3 = VoiceConfig::with_endpoint("wss://already.websocket.com");
        assert_eq!(config3.websocket_url(), "wss://already.websocket.com");
    }

    #[test]
    fn test_voice_message_serialization() {
        let msg = VoiceMessage::Transcript {
            text: "Hello world".to_string(),
            is_final: false,
        };

        let json = msg.to_json().unwrap();
        let parsed = VoiceMessage::from_json(&json).unwrap();

        if let VoiceMessage::Transcript { text, is_final } = parsed {
            assert_eq!(text, "Hello world");
            assert!(!is_final);
        } else {
            panic!("Wrong message type");
        }
    }

    #[test]
    fn test_voice_stream_state() {
        assert!(!VoiceStreamState::Idle.is_active());
        assert!(VoiceStreamState::Listening.is_active());
        assert!(VoiceStreamState::Processing.is_active());
        assert!(VoiceStreamState::Speaking.is_active());
        assert!(!VoiceStreamState::Ready.is_active());

        assert!(!VoiceStreamState::Idle.is_connected());
        assert!(VoiceStreamState::Ready.is_connected());
        assert!(VoiceStreamState::Listening.is_connected());
    }

    #[test]
    fn test_earcon_types() {
        let earcon = EarconType::ListeningStart;
        let json = serde_json::to_string(&earcon).unwrap();
        assert!(json.contains("ListeningStart"));
    }

    #[test]
    fn test_audio_format_validation() {
        // Valid format
        let valid = AudioFormat::default();
        assert!(valid.validate().is_ok());
        assert!(valid.is_valid());

        // Invalid: sample_rate = 0
        let invalid_sample_rate = AudioFormat {
            sample_rate: 0,
            ..Default::default()
        };
        assert!(invalid_sample_rate.validate().is_err());
        assert!(!invalid_sample_rate.is_valid());

        // Invalid: channels = 0
        let invalid_channels = AudioFormat {
            channels: 0,
            ..Default::default()
        };
        assert!(invalid_channels.validate().is_err());

        // Invalid: bits_per_sample = 0
        let invalid_bits_zero = AudioFormat {
            bits_per_sample: 0,
            ..Default::default()
        };
        assert!(invalid_bits_zero.validate().is_err());

        // Invalid: bits_per_sample not divisible by 8
        let invalid_bits_7 = AudioFormat {
            bits_per_sample: 7,
            ..Default::default()
        };
        assert!(invalid_bits_7.validate().is_err());
        assert_eq!(
            invalid_bits_7.validate().unwrap_err(),
            "bits_per_sample must be divisible by 8 (e.g., 8, 16, 24, 32)"
        );

        // Valid odd values divisible by 8: 8, 24
        let valid_8bit = AudioFormat {
            bits_per_sample: 8,
            ..Default::default()
        };
        assert!(valid_8bit.validate().is_ok());

        let valid_24bit = AudioFormat {
            bits_per_sample: 24,
            ..Default::default()
        };
        assert!(valid_24bit.validate().is_ok());
    }

    #[test]
    fn test_audio_format_invalid_returns_zero() {
        // bytes_per_sample returns 0 for invalid formats
        let invalid = AudioFormat {
            bits_per_sample: 0,
            ..Default::default()
        };
        assert_eq!(invalid.bytes_per_sample(), 0);
        assert_eq!(invalid.bytes_per_second(), 0);
        assert_eq!(invalid.bytes_for_duration(Duration::from_secs(1)), 0);
        assert_eq!(invalid.duration_for_bytes(1000), Duration::ZERO);

        // bits_per_sample not divisible by 8
        let invalid_7bit = AudioFormat {
            bits_per_sample: 7,
            ..Default::default()
        };
        assert_eq!(invalid_7bit.bytes_per_sample(), 0);
    }
}

/*
 * kagami
 * Voice is presence. Sound is connection.
 * h(x) >= 0. Always.
 */
