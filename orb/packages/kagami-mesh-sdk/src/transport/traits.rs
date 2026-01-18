//! Transport abstraction traits for mesh network communication.
//!
//! These traits define platform-agnostic interfaces that iOS and Android
//! implement using native WebSocket libraries (URLSession/OkHttp).
//!
//! The Rust SDK provides the state machine, retry logic, and circuit breaker.
//! Platforms provide the actual WebSocket transport.
//!
//! h(x) >= 0. Always.

use serde::{Deserialize, Serialize};

/// Connection state enumeration exposed to FFI.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum TransportState {
    /// Not connected to any peer.
    Disconnected = 0,
    /// Attempting to establish connection.
    Connecting = 1,
    /// Connected and ready for communication.
    Connected = 2,
    /// Connection lost, attempting to reconnect.
    Reconnecting = 3,
    /// Circuit breaker is open due to repeated failures.
    CircuitOpen = 4,
    /// Half-open state, testing recovery.
    HalfOpen = 5,
}

impl Default for TransportState {
    fn default() -> Self {
        Self::Disconnected
    }
}

impl std::fmt::Display for TransportState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            TransportState::Disconnected => write!(f, "disconnected"),
            TransportState::Connecting => write!(f, "connecting"),
            TransportState::Connected => write!(f, "connected"),
            TransportState::Reconnecting => write!(f, "reconnecting"),
            TransportState::CircuitOpen => write!(f, "circuit_open"),
            TransportState::HalfOpen => write!(f, "half_open"),
        }
    }
}

/// Transport events that trigger state transitions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransportEvent {
    /// Connection attempt initiated.
    Connecting,
    /// Connection established successfully.
    Connected,
    /// Connection attempt failed.
    ConnectionFailed { reason: String },
    /// Connection was lost.
    Disconnected { reason: String },
    /// Manual disconnect requested.
    DisconnectRequested,
    /// Circuit breaker recovery period elapsed.
    RecoveryAttempt,
    /// Message received from peer.
    MessageReceived { data: Vec<u8> },
    /// Ping timeout occurred.
    PingTimeout,
    /// Pong received.
    PongReceived,
}

/// Configuration for transport behavior.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TransportConfig {
    /// Initial retry delay in milliseconds.
    pub initial_retry_ms: u64,
    /// Maximum retry delay in milliseconds.
    pub max_retry_ms: u64,
    /// Retry delay multiplier for exponential backoff.
    pub retry_multiplier: f64,
    /// Number of failures before opening circuit breaker.
    pub failure_threshold: u32,
    /// Circuit breaker recovery timeout in milliseconds.
    pub circuit_breaker_timeout_ms: u64,
    /// Ping interval in milliseconds.
    pub ping_interval_ms: u64,
    /// Ping timeout in milliseconds.
    pub ping_timeout_ms: u64,
    /// Maximum number of retry attempts (0 = unlimited).
    pub max_retry_attempts: u32,
}

impl Default for TransportConfig {
    fn default() -> Self {
        Self {
            initial_retry_ms: 500,
            max_retry_ms: 30_000,
            retry_multiplier: 2.0,
            failure_threshold: 5,
            circuit_breaker_timeout_ms: 30_000,
            ping_interval_ms: 30_000,
            ping_timeout_ms: 10_000,
            max_retry_attempts: 0, // Unlimited
        }
    }
}

impl TransportConfig {
    /// Create config with aggressive retry for local network.
    pub fn local_network() -> Self {
        Self {
            initial_retry_ms: 200,
            max_retry_ms: 5_000,
            retry_multiplier: 1.5,
            failure_threshold: 3,
            circuit_breaker_timeout_ms: 10_000,
            ping_interval_ms: 15_000,
            ping_timeout_ms: 5_000,
            max_retry_attempts: 10,
        }
    }

    /// Create config for cloud connections.
    pub fn cloud() -> Self {
        Self {
            initial_retry_ms: 1_000,
            max_retry_ms: 60_000,
            retry_multiplier: 2.0,
            failure_threshold: 5,
            circuit_breaker_timeout_ms: 60_000,
            ping_interval_ms: 30_000,
            ping_timeout_ms: 10_000,
            max_retry_attempts: 0, // Unlimited
        }
    }
}

/// Retry strategy configuration returned to platform transport.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RetryStrategy {
    /// Whether a retry should be attempted.
    pub should_retry: bool,
    /// Delay before retry in milliseconds.
    pub delay_ms: u64,
    /// Current retry attempt number.
    pub attempt: u32,
    /// Maximum attempts (0 = unlimited).
    pub max_attempts: u32,
    /// Reason for the retry decision.
    pub reason: String,
}

impl RetryStrategy {
    /// Create a strategy indicating no retry.
    pub fn no_retry(reason: impl Into<String>) -> Self {
        Self {
            should_retry: false,
            delay_ms: 0,
            attempt: 0,
            max_attempts: 0,
            reason: reason.into(),
        }
    }

    /// Create a strategy indicating retry should proceed.
    pub fn retry(delay_ms: u64, attempt: u32, max_attempts: u32) -> Self {
        Self {
            should_retry: true,
            delay_ms,
            attempt,
            max_attempts,
            reason: format!("Retry attempt {} after {}ms", attempt, delay_ms),
        }
    }
}

/// State observer trait for receiving transport state changes.
///
/// Platforms implement this to receive state updates from the Rust state machine.
pub trait ConnectionStateObserver: Send + Sync {
    /// Called when transport state changes.
    fn on_state_changed(&self, old_state: TransportState, new_state: TransportState);

    /// Called when a retry should be attempted.
    fn on_retry_scheduled(&self, strategy: &RetryStrategy);

    /// Called when connection is established.
    fn on_connected(&self, peer_id: &str);

    /// Called when disconnected.
    fn on_disconnected(&self, reason: &str);

    /// Called when circuit breaker opens.
    fn on_circuit_breaker_opened(&self, failure_count: u32);

    /// Called when circuit breaker begins recovery.
    fn on_circuit_breaker_recovery(&self);
}

/// Default no-op implementation for platforms that don't need callbacks.
pub struct NoOpStateObserver;

impl ConnectionStateObserver for NoOpStateObserver {
    fn on_state_changed(&self, _old_state: TransportState, _new_state: TransportState) {}
    fn on_retry_scheduled(&self, _strategy: &RetryStrategy) {}
    fn on_connected(&self, _peer_id: &str) {}
    fn on_disconnected(&self, _reason: &str) {}
    fn on_circuit_breaker_opened(&self, _failure_count: u32) {}
    fn on_circuit_breaker_recovery(&self) {}
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_transport_state_display() {
        assert_eq!(TransportState::Disconnected.to_string(), "disconnected");
        assert_eq!(TransportState::Connecting.to_string(), "connecting");
        assert_eq!(TransportState::Connected.to_string(), "connected");
        assert_eq!(TransportState::CircuitOpen.to_string(), "circuit_open");
    }

    #[test]
    fn test_transport_config_defaults() {
        let config = TransportConfig::default();
        assert_eq!(config.initial_retry_ms, 500);
        assert_eq!(config.failure_threshold, 5);
    }

    #[test]
    fn test_local_network_config() {
        let config = TransportConfig::local_network();
        assert!(config.initial_retry_ms < TransportConfig::default().initial_retry_ms);
        assert!(config.circuit_breaker_timeout_ms < TransportConfig::default().circuit_breaker_timeout_ms);
    }

    #[test]
    fn test_retry_strategy() {
        let no_retry = RetryStrategy::no_retry("max attempts reached");
        assert!(!no_retry.should_retry);

        let retry = RetryStrategy::retry(1000, 3, 5);
        assert!(retry.should_retry);
        assert_eq!(retry.delay_ms, 1000);
        assert_eq!(retry.attempt, 3);
    }
}
