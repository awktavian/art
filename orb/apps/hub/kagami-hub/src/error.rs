//! Kagami Hub Error Types
//!
//! Provides domain-specific error types for the Hub, complementing anyhow
//! for cases where programmatic error handling is needed.
//!
//! Colony: Crystal (e7) - Verification, error handling
//!
//! h(x) >= 0. Always.

use std::fmt;

// ============================================================================
// Hub Error - Top-Level Error Type
// ============================================================================

/// Top-level error type for Kagami Hub operations
#[derive(Debug)]
pub enum HubError {
    /// Configuration errors
    Config(ConfigError),
    /// Voice pipeline errors
    Voice(VoiceError),
    /// Network/API errors
    Network(NetworkError),
    /// Device/automation errors
    Device(DeviceError),
    /// Audio hardware errors
    Audio(AudioError),
    /// Generic error with context
    Other(anyhow::Error),
}

impl fmt::Display for HubError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            HubError::Config(e) => write!(f, "configuration error: {}", e),
            HubError::Voice(e) => write!(f, "voice pipeline error: {}", e),
            HubError::Network(e) => write!(f, "network error: {}", e),
            HubError::Device(e) => write!(f, "device error: {}", e),
            HubError::Audio(e) => write!(f, "audio error: {}", e),
            HubError::Other(e) => write!(f, "{}", e),
        }
    }
}

impl std::error::Error for HubError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            HubError::Config(e) => Some(e),
            HubError::Voice(e) => Some(e),
            HubError::Network(e) => Some(e),
            HubError::Device(e) => Some(e),
            HubError::Audio(e) => Some(e),
            HubError::Other(e) => e.source(),
        }
    }
}

impl From<anyhow::Error> for HubError {
    fn from(err: anyhow::Error) -> Self {
        HubError::Other(err)
    }
}

impl From<ConfigError> for HubError {
    fn from(err: ConfigError) -> Self {
        HubError::Config(err)
    }
}

impl From<VoiceError> for HubError {
    fn from(err: VoiceError) -> Self {
        HubError::Voice(err)
    }
}

impl From<NetworkError> for HubError {
    fn from(err: NetworkError) -> Self {
        HubError::Network(err)
    }
}

impl From<DeviceError> for HubError {
    fn from(err: DeviceError) -> Self {
        HubError::Device(err)
    }
}

impl From<AudioError> for HubError {
    fn from(err: AudioError) -> Self {
        HubError::Audio(err)
    }
}

// ============================================================================
// Configuration Errors
// ============================================================================

/// Configuration-related errors
#[derive(Debug)]
pub enum ConfigError {
    /// Configuration file not found
    NotFound(String),
    /// Invalid configuration format
    InvalidFormat(String),
    /// Missing required field
    MissingField(String),
    /// Invalid value for field
    InvalidValue { field: String, value: String, reason: String },
    /// IO error reading/writing config
    Io(std::io::Error),
}

impl fmt::Display for ConfigError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ConfigError::NotFound(path) => write!(f, "configuration file not found: {}", path),
            ConfigError::InvalidFormat(msg) => write!(f, "invalid configuration format: {}", msg),
            ConfigError::MissingField(field) => write!(f, "missing required field: {}", field),
            ConfigError::InvalidValue { field, value, reason } => {
                write!(f, "invalid value '{}' for {}: {}", value, field, reason)
            }
            ConfigError::Io(e) => write!(f, "configuration I/O error: {}", e),
        }
    }
}

impl std::error::Error for ConfigError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            ConfigError::Io(e) => Some(e),
            _ => None,
        }
    }
}

impl From<std::io::Error> for ConfigError {
    fn from(err: std::io::Error) -> Self {
        ConfigError::Io(err)
    }
}

// ============================================================================
// Voice Pipeline Errors
// ============================================================================

/// Voice pipeline errors
#[derive(Debug)]
pub enum VoiceError {
    /// Wake word detection failed
    WakeWordFailed(String),
    /// Speech-to-text failed
    SttFailed(String),
    /// Natural language understanding failed
    NluFailed { text: String, reason: String },
    /// Text-to-speech failed
    TtsFailed(String),
    /// Speaker identification failed
    SpeakerIdFailed(String),
    /// Model not loaded
    ModelNotLoaded(String),
    /// Confidence below threshold
    LowConfidence { confidence: f32, threshold: f32 },
}

impl fmt::Display for VoiceError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            VoiceError::WakeWordFailed(msg) => write!(f, "wake word detection failed: {}", msg),
            VoiceError::SttFailed(msg) => write!(f, "speech-to-text failed: {}", msg),
            VoiceError::NluFailed { text, reason } => {
                write!(f, "NLU failed for '{}': {}", text, reason)
            }
            VoiceError::TtsFailed(msg) => write!(f, "text-to-speech failed: {}", msg),
            VoiceError::SpeakerIdFailed(msg) => write!(f, "speaker identification failed: {}", msg),
            VoiceError::ModelNotLoaded(model) => write!(f, "model not loaded: {}", model),
            VoiceError::LowConfidence { confidence, threshold } => {
                write!(f, "confidence {:.0}% below threshold {:.0}%", confidence * 100.0, threshold * 100.0)
            }
        }
    }
}

impl std::error::Error for VoiceError {}

// ============================================================================
// Network Errors
// ============================================================================

/// Network and API errors
#[derive(Debug)]
pub enum NetworkError {
    /// Connection failed
    ConnectionFailed(String),
    /// Request timeout
    Timeout { operation: String, timeout_ms: u64 },
    /// Authentication failed
    AuthFailed(String),
    /// API returned error status
    ApiError { status: u16, message: String },
    /// WebSocket error
    WebSocket(String),
    /// Circuit breaker open
    CircuitOpen(String),
    /// DNS resolution failed
    DnsResolutionFailed(String),
}

impl fmt::Display for NetworkError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            NetworkError::ConnectionFailed(msg) => write!(f, "connection failed: {}", msg),
            NetworkError::Timeout { operation, timeout_ms } => {
                write!(f, "{} timed out after {}ms", operation, timeout_ms)
            }
            NetworkError::AuthFailed(msg) => write!(f, "authentication failed: {}", msg),
            NetworkError::ApiError { status, message } => {
                write!(f, "API error {}: {}", status, message)
            }
            NetworkError::WebSocket(msg) => write!(f, "WebSocket error: {}", msg),
            NetworkError::CircuitOpen(name) => write!(f, "circuit breaker '{}' is open", name),
            NetworkError::DnsResolutionFailed(host) => write!(f, "DNS resolution failed for: {}", host),
        }
    }
}

impl std::error::Error for NetworkError {}

// ============================================================================
// Device Errors
// ============================================================================

/// Device and automation errors
#[derive(Debug)]
pub enum DeviceError {
    /// Device not found
    NotFound { device_type: String, id: String },
    /// Device offline
    Offline { device_type: String, id: String },
    /// Command not supported
    UnsupportedCommand { device: String, command: String },
    /// Device busy
    Busy { device: String, reason: String },
    /// Permission denied
    PermissionDenied { device: String, action: String },
    /// Discovery failed
    DiscoveryFailed(String),
    /// Pairing failed
    PairingFailed { device: String, reason: String },
}

impl fmt::Display for DeviceError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DeviceError::NotFound { device_type, id } => {
                write!(f, "{} '{}' not found", device_type, id)
            }
            DeviceError::Offline { device_type, id } => {
                write!(f, "{} '{}' is offline", device_type, id)
            }
            DeviceError::UnsupportedCommand { device, command } => {
                write!(f, "device '{}' does not support command '{}'", device, command)
            }
            DeviceError::Busy { device, reason } => {
                write!(f, "device '{}' is busy: {}", device, reason)
            }
            DeviceError::PermissionDenied { device, action } => {
                write!(f, "permission denied: {} on '{}'", action, device)
            }
            DeviceError::DiscoveryFailed(msg) => write!(f, "device discovery failed: {}", msg),
            DeviceError::PairingFailed { device, reason } => {
                write!(f, "pairing failed for '{}': {}", device, reason)
            }
        }
    }
}

impl std::error::Error for DeviceError {}

// ============================================================================
// Audio Errors
// ============================================================================

/// Audio hardware and processing errors
#[derive(Debug)]
pub enum AudioError {
    /// No audio input device
    NoInputDevice,
    /// No audio output device
    NoOutputDevice,
    /// Sample rate not supported
    UnsupportedSampleRate(u32),
    /// Buffer overflow
    BufferOverflow { size: usize, max: usize },
    /// Format conversion failed
    FormatConversion(String),
    /// Hardware error
    Hardware(String),
}

impl fmt::Display for AudioError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            AudioError::NoInputDevice => write!(f, "no audio input device found"),
            AudioError::NoOutputDevice => write!(f, "no audio output device found"),
            AudioError::UnsupportedSampleRate(rate) => {
                write!(f, "sample rate {}Hz not supported", rate)
            }
            AudioError::BufferOverflow { size, max } => {
                write!(f, "audio buffer overflow: {} bytes exceeds max {}", size, max)
            }
            AudioError::FormatConversion(msg) => write!(f, "audio format conversion failed: {}", msg),
            AudioError::Hardware(msg) => write!(f, "audio hardware error: {}", msg),
        }
    }
}

impl std::error::Error for AudioError {}

// ============================================================================
// Result Type Alias
// ============================================================================

/// Result type alias for Hub operations
pub type HubResult<T> = Result<T, HubError>;

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_error_display() {
        let err = ConfigError::MissingField("api_url".to_string());
        assert!(err.to_string().contains("api_url"));

        let err = VoiceError::LowConfidence { confidence: 0.3, threshold: 0.7 };
        assert!(err.to_string().contains("30%"));

        let err = NetworkError::Timeout { operation: "API call".to_string(), timeout_ms: 5000 };
        assert!(err.to_string().contains("5000ms"));
    }

    #[test]
    fn test_error_conversion() {
        let config_err = ConfigError::NotFound("config.toml".to_string());
        let hub_err: HubError = config_err.into();
        assert!(matches!(hub_err, HubError::Config(_)));
    }
}

/*
 * Kagami Hub Error Types
 * Crystal (e7) - Verification, error handling
 *
 * Errors are data, not exceptions.
 * h(x) >= 0. Always.
 */
