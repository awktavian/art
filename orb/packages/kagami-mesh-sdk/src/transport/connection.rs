//! Connection state machine for managing WebSocket connections.
//!
//! Implements a proper state machine with:
//! - Disconnected → Connecting → Connected → Disconnected
//! - Automatic reconnection with exponential backoff
//! - Circuit breaker pattern for failure detection

use std::time::Duration;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Connection state errors.
#[derive(Debug, Error)]
pub enum ConnectionStateError {
    #[error("Invalid state transition from {from:?} to {to:?}")]
    InvalidTransition {
        from: ConnectionState,
        to: ConnectionState,
    },

    #[error("Circuit breaker is open")]
    CircuitBreakerOpen,

    #[error("Connection timeout")]
    Timeout,
}

/// The state of a connection.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConnectionState {
    /// Not connected and not trying to connect.
    Disconnected,

    /// Attempting to establish a connection.
    Connecting,

    /// Successfully connected.
    Connected,

    /// Connection was lost, will attempt to reconnect.
    Reconnecting,

    /// Circuit breaker is open due to repeated failures.
    CircuitBreakerOpen,
}

impl Default for ConnectionState {
    fn default() -> Self {
        Self::Disconnected
    }
}

/// Events that can trigger state transitions.
#[derive(Debug, Clone)]
pub enum ConnectionEvent {
    /// User requested to connect.
    Connect,

    /// Connection established successfully.
    Connected,

    /// Connection attempt failed.
    ConnectionFailed(String),

    /// Connection was lost.
    Disconnected(String),

    /// User requested to disconnect.
    Disconnect,

    /// Circuit breaker timeout expired.
    CircuitBreakerRecovery,

    /// Ping response received.
    PongReceived,

    /// Ping timeout (no pong received).
    PingTimeout,
}

/// Configuration for connection behavior.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConnectionConfig {
    /// Initial reconnection delay.
    pub initial_backoff: Duration,

    /// Maximum reconnection delay.
    pub max_backoff: Duration,

    /// Backoff multiplier.
    pub backoff_multiplier: f64,

    /// Number of failures before opening circuit breaker.
    pub failure_threshold: u32,

    /// Time to wait before attempting recovery from circuit breaker.
    pub circuit_breaker_timeout: Duration,

    /// Ping interval for keepalive.
    pub ping_interval: Duration,

    /// Timeout for ping responses.
    pub ping_timeout: Duration,

    /// Maximum number of reconnection attempts (None = unlimited).
    pub max_reconnect_attempts: Option<u32>,
}

impl Default for ConnectionConfig {
    fn default() -> Self {
        Self {
            initial_backoff: Duration::from_millis(500),
            max_backoff: Duration::from_secs(30),
            backoff_multiplier: 2.0,
            failure_threshold: 5,
            circuit_breaker_timeout: Duration::from_secs(30),
            ping_interval: Duration::from_secs(30),
            ping_timeout: Duration::from_secs(10),
            max_reconnect_attempts: None,
        }
    }
}

/// The connection state machine.
#[derive(Debug)]
pub struct ConnectionStateMachine {
    /// Current state.
    state: ConnectionState,

    /// Configuration.
    config: ConnectionConfig,

    /// Number of consecutive failures.
    failure_count: u32,

    /// Number of reconnection attempts.
    reconnect_attempts: u32,

    /// Current backoff duration.
    current_backoff: Duration,

    /// Time of last state change.
    last_state_change: DateTime<Utc>,

    /// Time circuit breaker opened (if applicable).
    circuit_breaker_opened_at: Option<DateTime<Utc>>,

    /// Time of last successful ping.
    last_ping_success: Option<DateTime<Utc>>,
}

impl ConnectionStateMachine {
    /// Create a new connection state machine.
    pub fn new(config: ConnectionConfig) -> Self {
        Self {
            state: ConnectionState::Disconnected,
            config: config.clone(),
            failure_count: 0,
            reconnect_attempts: 0,
            current_backoff: config.initial_backoff,
            last_state_change: Utc::now(),
            circuit_breaker_opened_at: None,
            last_ping_success: None,
        }
    }

    /// Create with default configuration.
    pub fn with_defaults() -> Self {
        Self::new(ConnectionConfig::default())
    }

    /// Get the current state.
    pub fn state(&self) -> ConnectionState {
        self.state
    }

    /// Check if currently connected.
    pub fn is_connected(&self) -> bool {
        self.state == ConnectionState::Connected
    }

    /// Check if should attempt connection.
    pub fn should_connect(&self) -> bool {
        matches!(
            self.state,
            ConnectionState::Disconnected | ConnectionState::Reconnecting
        )
    }

    /// Get the current backoff duration.
    pub fn backoff_duration(&self) -> Duration {
        self.current_backoff
    }

    /// Get the failure count.
    pub fn failure_count(&self) -> u32 {
        self.failure_count
    }

    /// Get the reconnect attempts.
    pub fn reconnect_attempts(&self) -> u32 {
        self.reconnect_attempts
    }

    /// Process an event and return the new state.
    pub fn process_event(&mut self, event: ConnectionEvent) -> Result<ConnectionState, ConnectionStateError> {
        let new_state = self.compute_next_state(&event)?;
        self.transition_to(new_state, &event);
        Ok(new_state)
    }

    /// Compute the next state based on current state and event.
    fn compute_next_state(
        &self,
        event: &ConnectionEvent,
    ) -> Result<ConnectionState, ConnectionStateError> {
        match (&self.state, event) {
            // From Disconnected
            (ConnectionState::Disconnected, ConnectionEvent::Connect) => {
                Ok(ConnectionState::Connecting)
            }

            // From Connecting
            (ConnectionState::Connecting, ConnectionEvent::Connected) => {
                Ok(ConnectionState::Connected)
            }
            (ConnectionState::Connecting, ConnectionEvent::ConnectionFailed(_)) => {
                if self.failure_count + 1 >= self.config.failure_threshold {
                    Ok(ConnectionState::CircuitBreakerOpen)
                } else if self.should_give_up() {
                    Ok(ConnectionState::Disconnected)
                } else {
                    Ok(ConnectionState::Reconnecting)
                }
            }
            (ConnectionState::Connecting, ConnectionEvent::Disconnect) => {
                Ok(ConnectionState::Disconnected)
            }

            // From Connected
            (ConnectionState::Connected, ConnectionEvent::Disconnected(_)) => {
                Ok(ConnectionState::Reconnecting)
            }
            (ConnectionState::Connected, ConnectionEvent::Disconnect) => {
                Ok(ConnectionState::Disconnected)
            }
            (ConnectionState::Connected, ConnectionEvent::PingTimeout) => {
                Ok(ConnectionState::Reconnecting)
            }
            (ConnectionState::Connected, ConnectionEvent::PongReceived) => {
                Ok(ConnectionState::Connected)
            }

            // From Reconnecting
            (ConnectionState::Reconnecting, ConnectionEvent::Connect) => {
                Ok(ConnectionState::Connecting)
            }
            (ConnectionState::Reconnecting, ConnectionEvent::Connected) => {
                Ok(ConnectionState::Connected)
            }
            (ConnectionState::Reconnecting, ConnectionEvent::ConnectionFailed(_)) => {
                if self.failure_count + 1 >= self.config.failure_threshold {
                    Ok(ConnectionState::CircuitBreakerOpen)
                } else if self.should_give_up() {
                    Ok(ConnectionState::Disconnected)
                } else {
                    Ok(ConnectionState::Reconnecting)
                }
            }
            (ConnectionState::Reconnecting, ConnectionEvent::Disconnect) => {
                Ok(ConnectionState::Disconnected)
            }

            // From CircuitBreakerOpen
            (ConnectionState::CircuitBreakerOpen, ConnectionEvent::CircuitBreakerRecovery) => {
                Ok(ConnectionState::Reconnecting)
            }
            (ConnectionState::CircuitBreakerOpen, ConnectionEvent::Disconnect) => {
                Ok(ConnectionState::Disconnected)
            }

            // Invalid transitions
            _ => Err(ConnectionStateError::InvalidTransition {
                from: self.state,
                to: ConnectionState::Disconnected,
            }),
        }
    }

    /// Check if we should give up reconnecting.
    fn should_give_up(&self) -> bool {
        if let Some(max_attempts) = self.config.max_reconnect_attempts {
            self.reconnect_attempts + 1 >= max_attempts
        } else {
            false
        }
    }

    /// Perform the state transition.
    fn transition_to(&mut self, new_state: ConnectionState, event: &ConnectionEvent) {
        let old_state = self.state;
        self.state = new_state;
        self.last_state_change = Utc::now();

        // Handle state-specific logic
        match (old_state, new_state, event) {
            // Successful connection - reset counters
            (_, ConnectionState::Connected, ConnectionEvent::Connected) => {
                self.failure_count = 0;
                self.reconnect_attempts = 0;
                self.current_backoff = self.config.initial_backoff;
                self.circuit_breaker_opened_at = None;
                self.last_ping_success = Some(Utc::now());
            }

            // Connection failed leading to circuit breaker - increment counters AND set timestamp
            (_, ConnectionState::CircuitBreakerOpen, ConnectionEvent::ConnectionFailed(_)) => {
                self.failure_count += 1;
                self.reconnect_attempts += 1;
                self.increase_backoff();
                self.circuit_breaker_opened_at = Some(Utc::now());
            }

            // Connection failed - increment counters and backoff
            (_, _, ConnectionEvent::ConnectionFailed(_)) => {
                self.failure_count += 1;
                self.reconnect_attempts += 1;
                self.increase_backoff();
            }

            // Circuit breaker recovery
            (ConnectionState::CircuitBreakerOpen, _, ConnectionEvent::CircuitBreakerRecovery) => {
                // Reset failure count but keep backoff
                self.failure_count = 0;
            }

            // Manual disconnect - reset everything
            (_, ConnectionState::Disconnected, ConnectionEvent::Disconnect) => {
                self.failure_count = 0;
                self.reconnect_attempts = 0;
                self.current_backoff = self.config.initial_backoff;
                self.circuit_breaker_opened_at = None;
            }

            // Ping success
            (
                ConnectionState::Connected,
                ConnectionState::Connected,
                ConnectionEvent::PongReceived,
            ) => {
                self.last_ping_success = Some(Utc::now());
            }

            _ => {}
        }
    }

    /// Increase backoff using exponential backoff with jitter.
    fn increase_backoff(&mut self) {
        let new_backoff = self.current_backoff.as_secs_f64() * self.config.backoff_multiplier;
        let jitter = rand::random::<f64>() * 0.3; // 0-30% jitter
        let with_jitter = new_backoff * (1.0 + jitter);
        let clamped = with_jitter.min(self.config.max_backoff.as_secs_f64());
        self.current_backoff = Duration::from_secs_f64(clamped);
    }

    /// Check if circuit breaker recovery is due.
    pub fn should_attempt_recovery(&self) -> bool {
        if self.state != ConnectionState::CircuitBreakerOpen {
            return false;
        }

        if let Some(opened_at) = self.circuit_breaker_opened_at {
            let elapsed = Utc::now() - opened_at;
            elapsed.to_std().unwrap_or(Duration::ZERO) >= self.config.circuit_breaker_timeout
        } else {
            false
        }
    }

    /// Check if ping is overdue.
    pub fn is_ping_overdue(&self) -> bool {
        if self.state != ConnectionState::Connected {
            return false;
        }

        if let Some(last_ping) = self.last_ping_success {
            let elapsed = Utc::now() - last_ping;
            elapsed.to_std().unwrap_or(Duration::ZERO) >= self.config.ping_timeout
        } else {
            false
        }
    }

    /// Reset the state machine.
    pub fn reset(&mut self) {
        self.state = ConnectionState::Disconnected;
        self.failure_count = 0;
        self.reconnect_attempts = 0;
        self.current_backoff = self.config.initial_backoff;
        self.circuit_breaker_opened_at = None;
        self.last_ping_success = None;
        self.last_state_change = Utc::now();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_initial_state() {
        let sm = ConnectionStateMachine::with_defaults();
        assert_eq!(sm.state(), ConnectionState::Disconnected);
    }

    #[test]
    fn test_connect_flow() {
        let mut sm = ConnectionStateMachine::with_defaults();

        sm.process_event(ConnectionEvent::Connect).unwrap();
        assert_eq!(sm.state(), ConnectionState::Connecting);

        sm.process_event(ConnectionEvent::Connected).unwrap();
        assert_eq!(sm.state(), ConnectionState::Connected);
    }

    #[test]
    fn test_disconnect_from_connected() {
        let mut sm = ConnectionStateMachine::with_defaults();

        sm.process_event(ConnectionEvent::Connect).unwrap();
        sm.process_event(ConnectionEvent::Connected).unwrap();
        sm.process_event(ConnectionEvent::Disconnect).unwrap();

        assert_eq!(sm.state(), ConnectionState::Disconnected);
    }

    #[test]
    fn test_reconnect_on_failure() {
        let mut sm = ConnectionStateMachine::with_defaults();

        sm.process_event(ConnectionEvent::Connect).unwrap();
        sm.process_event(ConnectionEvent::ConnectionFailed("test".to_string()))
            .unwrap();

        assert_eq!(sm.state(), ConnectionState::Reconnecting);
        assert_eq!(sm.failure_count(), 1);
    }

    #[test]
    fn test_circuit_breaker_opens() {
        let config = ConnectionConfig {
            failure_threshold: 3,
            ..Default::default()
        };
        let mut sm = ConnectionStateMachine::new(config);

        sm.process_event(ConnectionEvent::Connect).unwrap();

        for _ in 0..3 {
            sm.process_event(ConnectionEvent::ConnectionFailed("test".to_string()))
                .unwrap();
        }

        assert_eq!(sm.state(), ConnectionState::CircuitBreakerOpen);
    }

    #[test]
    fn test_circuit_breaker_recovery() {
        let config = ConnectionConfig {
            failure_threshold: 1,
            circuit_breaker_timeout: Duration::from_millis(5),
            ..Default::default()
        };
        let mut sm = ConnectionStateMachine::new(config);

        sm.process_event(ConnectionEvent::Connect).unwrap();
        sm.process_event(ConnectionEvent::ConnectionFailed("test".to_string()))
            .unwrap();

        assert_eq!(sm.state(), ConnectionState::CircuitBreakerOpen);
        // Immediately after failure, should not be ready for recovery
        // (Note: with very short timeouts, this may already be true)

        // Sleep well past the timeout to guarantee recovery is ready
        std::thread::sleep(Duration::from_millis(100));
        assert!(
            sm.should_attempt_recovery(),
            "Recovery should be allowed after timeout"
        );

        sm.process_event(ConnectionEvent::CircuitBreakerRecovery)
            .unwrap();
        assert_eq!(sm.state(), ConnectionState::Reconnecting);
    }

    #[test]
    fn test_backoff_increases() {
        let mut sm = ConnectionStateMachine::with_defaults();
        let initial_backoff = sm.backoff_duration();

        sm.process_event(ConnectionEvent::Connect).unwrap();
        sm.process_event(ConnectionEvent::ConnectionFailed("test".to_string()))
            .unwrap();

        let new_backoff = sm.backoff_duration();
        assert!(new_backoff > initial_backoff);
    }

    #[test]
    fn test_counters_reset_on_success() {
        let mut sm = ConnectionStateMachine::with_defaults();

        sm.process_event(ConnectionEvent::Connect).unwrap();
        sm.process_event(ConnectionEvent::ConnectionFailed("test".to_string()))
            .unwrap();
        sm.process_event(ConnectionEvent::Connect).unwrap();
        sm.process_event(ConnectionEvent::Connected).unwrap();

        assert_eq!(sm.failure_count(), 0);
        assert_eq!(sm.reconnect_attempts(), 0);
    }

    #[test]
    fn test_max_reconnect_attempts() {
        let config = ConnectionConfig {
            max_reconnect_attempts: Some(3),
            failure_threshold: 10, // High enough to not trigger circuit breaker
            ..Default::default()
        };
        let mut sm = ConnectionStateMachine::new(config);

        sm.process_event(ConnectionEvent::Connect).unwrap();

        for _ in 0..2 {
            sm.process_event(ConnectionEvent::ConnectionFailed("test".to_string()))
                .unwrap();
        }

        assert_eq!(sm.state(), ConnectionState::Reconnecting);

        sm.process_event(ConnectionEvent::ConnectionFailed("test".to_string()))
            .unwrap();

        assert_eq!(sm.state(), ConnectionState::Disconnected);
    }

    #[test]
    fn test_lost_connection_triggers_reconnect() {
        let mut sm = ConnectionStateMachine::with_defaults();

        sm.process_event(ConnectionEvent::Connect).unwrap();
        sm.process_event(ConnectionEvent::Connected).unwrap();
        sm.process_event(ConnectionEvent::Disconnected("lost".to_string()))
            .unwrap();

        assert_eq!(sm.state(), ConnectionState::Reconnecting);
    }
}
