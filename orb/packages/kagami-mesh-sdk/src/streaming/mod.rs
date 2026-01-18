//! Voice streaming module for cross-platform audio communication.
//!
//! This module provides a unified abstraction for voice capture, streaming,
//! and playback across iOS, Android, watchOS, visionOS, and Desktop platforms.
//!
//! # Architecture
//!
//! ```text
//! Platform Layer (iOS/Android/Desktop)
//!        │
//!        ▼
//! ┌─────────────────────────────────────────────────────┐
//! │              Voice Streaming Module                  │
//! │                                                      │
//! │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
//! │  │  voice   │  │  stream  │  │     playback     │  │
//! │  │ (capture)│  │(websocket│  │ (TTS + earcons)  │  │
//! │  │          │  │  client) │  │                  │  │
//! │  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
//! │       │             │                 │            │
//! │       └─────────────┼─────────────────┘            │
//! │                     │                              │
//! │              ┌──────┴──────┐                       │
//! │              │    types    │                       │
//! │              │  (unified)  │                       │
//! │              └─────────────┘                       │
//! └─────────────────────────────────────────────────────┘
//!        │
//!        ▼
//! Backend (Whisper STT / ElevenLabs TTS / Kagami)
//! ```
//!
//! # Usage
//!
//! ## From Swift (iOS/watchOS/visionOS)
//!
//! ```swift
//! import KagamiMeshSDK
//!
//! // Create voice stream
//! let stream = MeshVoiceStream(endpoint: "wss://api.kagami.io/ws/voice")
//!
//! // Create capture parameters
//! let params = voiceCaptureParamsSpeech()
//!
//! // Start streaming
//! // (Platform implements VoiceCapture trait natively)
//! ```
//!
//! ## From Kotlin (Android)
//!
//! ```kotlin
//! import com.kagami.mesh.sdk.*
//!
//! // Create voice stream
//! val stream = MeshVoiceStream("wss://api.kagami.io/ws/voice")
//!
//! // Create capture parameters
//! val params = voiceCaptureParamsSpeech()
//! ```
//!
//! ## From Rust (Desktop)
//!
//! ```rust,ignore
//! use kagami_mesh_sdk::streaming::{
//!     VoiceStreamClient, VoiceConfig, VoiceCapture, StubVoiceCapture
//! };
//!
//! // Create client
//! let config = VoiceConfig::with_endpoint("wss://api.kagami.io/ws/voice");
//! let (mut client, event_rx) = VoiceStreamClient::new(config);
//!
//! // Connect
//! client.connect().await?;
//!
//! // Start session
//! client.start_session().await?;
//!
//! // Send audio chunks
//! client.send_samples(&samples).await?;
//!
//! // End session
//! client.end_session().await?;
//! ```
//!
//! # Colony
//!
//! Beacon (e5) -- Communication
//!
//! h(x) >= 0. Always.

pub mod playback;
pub mod stream;
pub mod types;
pub mod voice;

// Re-export main types for convenience
pub use playback::{
    EarconCache, PlaybackItem, PlaybackProgress, PlaybackQueue, PlaybackState, StubVoicePlayback,
    VoicePlayback, VoicePlaybackError, VolumeSettings,
};
pub use stream::{
    AudioBuffer, FibonacciBackoff, MeshVoiceStream, StreamErrorCategory, VoiceStreamClient,
    VoiceStreamError, VoiceStreamEvent,
};
pub use types::{
    AudioChunk, AudioChunkData, AudioEncoding, AudioFormat, EarconType, TranscriptionResult,
    TtsResponse, TtsResponseData, VoiceConfig, VoiceMessage, VoiceStreamState,
};
pub use voice::{
    AsyncVoiceCapture, ErrorCategory, StubVoiceCapture, VoiceActivityDetector, VoiceCapture,
    VoiceCaptureConfig, VoiceCaptureError, VoiceCaptureParams,
};

// Re-export utility functions
pub use voice::{
    bytes_to_i16, calculate_rms_db, calculate_rms_db_f32, detect_silence, f32_to_i16, i16_to_bytes,
    i16_to_f32,
};

/// Voice streaming SDK version.
pub const STREAMING_VERSION: &str = "0.1.0";

/// Default voice WebSocket path.
pub const DEFAULT_VOICE_PATH: &str = "/ws/voice";

/// Create a voice config from a base HTTP/HTTPS URL.
///
/// Automatically converts to WebSocket URL and appends the voice path.
pub fn voice_config_from_base_url(base_url: &str) -> VoiceConfig {
    let ws_url = if base_url.starts_with("https://") {
        base_url.replace("https://", "wss://")
    } else if base_url.starts_with("http://") {
        base_url.replace("http://", "ws://")
    } else {
        format!("wss://{}", base_url)
    };

    let endpoint = if ws_url.ends_with('/') {
        format!("{}{}", ws_url.trim_end_matches('/'), DEFAULT_VOICE_PATH)
    } else {
        format!("{}{}", ws_url, DEFAULT_VOICE_PATH)
    };

    VoiceConfig::with_endpoint(endpoint)
}

/// Create a watch-optimized voice config from a base URL.
pub fn voice_config_watch_from_base_url(base_url: &str) -> VoiceConfig {
    let ws_url = if base_url.starts_with("https://") {
        base_url.replace("https://", "wss://")
    } else if base_url.starts_with("http://") {
        base_url.replace("http://", "ws://")
    } else {
        format!("wss://{}", base_url)
    };

    let endpoint = if ws_url.ends_with('/') {
        format!("{}{}", ws_url.trim_end_matches('/'), DEFAULT_VOICE_PATH)
    } else {
        format!("{}{}", ws_url, DEFAULT_VOICE_PATH)
    };

    VoiceConfig::watch_optimized(endpoint)
}

// ============================================================================
// UniFFI Exports
// ============================================================================

/// Create a voice config from a base URL.
#[uniffi::export]
pub fn voice_config_from_url(base_url: String) -> VoiceConfig {
    voice_config_from_base_url(&base_url)
}

/// Create a watch-optimized voice config from a base URL.
#[uniffi::export]
pub fn voice_config_watch_from_url(base_url: String) -> VoiceConfig {
    voice_config_watch_from_base_url(&base_url)
}

/// Get the streaming module version.
#[uniffi::export]
pub fn streaming_version() -> String {
    STREAMING_VERSION.to_string()
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_voice_config_from_base_url() {
        let config = voice_config_from_base_url("https://api.kagami.io");
        assert_eq!(config.endpoint, "wss://api.kagami.io/ws/voice");

        let config = voice_config_from_base_url("http://localhost:8080");
        assert_eq!(config.endpoint, "ws://localhost:8080/ws/voice");

        let config = voice_config_from_base_url("api.kagami.io");
        assert_eq!(config.endpoint, "wss://api.kagami.io/ws/voice");
    }

    #[test]
    fn test_voice_config_watch_from_base_url() {
        let config = voice_config_watch_from_base_url("https://api.kagami.io");
        assert_eq!(config.endpoint, "wss://api.kagami.io/ws/voice");
        assert_eq!(config.buffer_size, 512); // Watch-optimized
    }

    #[test]
    fn test_streaming_version() {
        assert_eq!(streaming_version(), STREAMING_VERSION);
    }
}

/*
 * kagami
 * Voice flows through the mesh, connecting all.
 * h(x) >= 0. Always.
 */
