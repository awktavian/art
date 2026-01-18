//! Circuit Breaker Pattern — Network Resilience
//!
//! Implements the circuit breaker pattern for API calls to prevent
//! cascading failures when the backend is unavailable.
//!
//! States:
//! - Closed: Normal operation, requests pass through
//! - Open: Failing fast, requests rejected immediately
//! - HalfOpen: Testing if service recovered
//!
//! Colony: Nexus (e4) - Connection, coordination
//!
//! h(x) >= 0. Always.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::RwLock;
use std::time::{Duration, Instant};
use tracing::{debug, info, warn};

use crate::telemetry;

// ============================================================================
// Circuit Breaker State
// ============================================================================

/// Circuit breaker states
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CircuitState {
    /// Normal operation - requests pass through
    Closed,
    /// Service failure detected - requests fail fast
    Open,
    /// Testing if service has recovered
    HalfOpen,
}

impl std::fmt::Display for CircuitState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CircuitState::Closed => write!(f, "closed"),
            CircuitState::Open => write!(f, "open"),
            CircuitState::HalfOpen => write!(f, "half-open"),
        }
    }
}

// ============================================================================
// Configuration
// ============================================================================

/// Circuit breaker configuration
#[derive(Debug, Clone)]
pub struct CircuitBreakerConfig {
    /// Number of consecutive failures before opening circuit
    pub failure_threshold: u32,
    /// Duration to wait before attempting to close circuit
    pub reset_timeout: Duration,
    /// Number of successful requests needed to close from half-open
    pub success_threshold: u32,
    /// Maximum number of requests to allow in half-open state
    pub half_open_max_requests: u32,
}

impl Default for CircuitBreakerConfig {
    fn default() -> Self {
        Self {
            failure_threshold: 5,
            reset_timeout: Duration::from_secs(30),
            success_threshold: 3,
            half_open_max_requests: 3,
        }
    }
}

// ============================================================================
// Circuit Breaker Implementation
// ============================================================================

/// Thread-safe circuit breaker for network resilience
pub struct CircuitBreaker {
    config: CircuitBreakerConfig,
    /// @GuardedBy("state lock") - Current circuit state
    state: RwLock<CircuitState>,
    /// @GuardedBy("atomic") - Consecutive failure count
    failure_count: AtomicU64,
    /// @GuardedBy("atomic") - Consecutive success count (for half-open)
    success_count: AtomicU64,
    /// @GuardedBy("atomic") - Requests in half-open state
    half_open_requests: AtomicU64,
    /// @GuardedBy("last_failure_time lock") - Time of last failure
    last_failure_time: RwLock<Option<Instant>>,
    /// Name for logging
    name: String,
}

impl CircuitBreaker {
    /// Create a new circuit breaker with default config
    pub fn new(name: &str) -> Self {
        Self::with_config(name, CircuitBreakerConfig::default())
    }

    /// Create a new circuit breaker with custom config
    pub fn with_config(name: &str, config: CircuitBreakerConfig) -> Self {
        info!(
            circuit = name,
            failure_threshold = config.failure_threshold,
            reset_timeout_secs = config.reset_timeout.as_secs(),
            "Circuit breaker initialized"
        );

        Self {
            config,
            state: RwLock::new(CircuitState::Closed),
            failure_count: AtomicU64::new(0),
            success_count: AtomicU64::new(0),
            half_open_requests: AtomicU64::new(0),
            last_failure_time: RwLock::new(None),
            name: name.to_string(),
        }
    }

    /// Get current circuit state
    pub fn state(&self) -> CircuitState {
        // First check if we should transition from Open to HalfOpen
        if let Ok(state) = self.state.read() {
            if *state == CircuitState::Open {
                if self.should_attempt_reset() {
                    drop(state); // Release read lock
                    self.transition_to_half_open();
                    return CircuitState::HalfOpen;
                }
            }
            *state
        } else {
            CircuitState::Closed // Safe default if lock poisoned
        }
    }

    /// Check if a request should be allowed
    pub fn allow_request(&self) -> bool {
        match self.state() {
            CircuitState::Closed => true,
            CircuitState::Open => false,
            CircuitState::HalfOpen => {
                // Allow limited requests in half-open state
                let current = self.half_open_requests.fetch_add(1, Ordering::SeqCst);
                if current < self.config.half_open_max_requests as u64 {
                    debug!(circuit = %self.name, "Allowing half-open request {}/{}",
                           current + 1, self.config.half_open_max_requests);
                    true
                } else {
                    self.half_open_requests.fetch_sub(1, Ordering::SeqCst);
                    false
                }
            }
        }
    }

    /// Record a successful request
    pub fn record_success(&self) {
        self.failure_count.store(0, Ordering::SeqCst);

        match self.state() {
            CircuitState::HalfOpen => {
                let successes = self.success_count.fetch_add(1, Ordering::SeqCst) + 1;
                debug!(circuit = %self.name, successes, threshold = self.config.success_threshold,
                       "Half-open success recorded");

                if successes >= self.config.success_threshold as u64 {
                    self.transition_to_closed();
                }
            }
            _ => {
                // Reset success count if not in half-open
                self.success_count.store(0, Ordering::SeqCst);
            }
        }
    }

    /// Record a failed request
    pub fn record_failure(&self) {
        let failures = self.failure_count.fetch_add(1, Ordering::SeqCst) + 1;

        // Update last failure time
        if let Ok(mut last_failure) = self.last_failure_time.write() {
            *last_failure = Some(Instant::now());
        }

        match self.state() {
            CircuitState::Closed => {
                if failures >= self.config.failure_threshold as u64 {
                    self.transition_to_open();
                } else {
                    debug!(circuit = %self.name, failures, threshold = self.config.failure_threshold,
                           "Failure recorded");
                }
            }
            CircuitState::HalfOpen => {
                // Any failure in half-open immediately opens
                self.transition_to_open();
            }
            CircuitState::Open => {
                // Already open, just track
                debug!(circuit = %self.name, "Failure while open");
            }
        }
    }

    /// Execute a fallible operation with circuit breaker protection
    pub async fn call<F, T, E>(&self, operation: F) -> Result<T, CircuitBreakerError<E>>
    where
        F: std::future::Future<Output = Result<T, E>>,
    {
        if !self.allow_request() {
            return Err(CircuitBreakerError::CircuitOpen);
        }

        match operation.await {
            Ok(result) => {
                self.record_success();
                Ok(result)
            }
            Err(e) => {
                self.record_failure();
                Err(CircuitBreakerError::Inner(e))
            }
        }
    }

    /// Force the circuit to a specific state (for testing/admin)
    pub fn force_state(&self, state: CircuitState) {
        if let Ok(mut current) = self.state.write() {
            warn!(circuit = %self.name, from = %*current, to = %state, "Force state change");
            *current = state;
        }
        self.update_telemetry();
    }

    /// Reset the circuit breaker to initial state
    pub fn reset(&self) {
        self.failure_count.store(0, Ordering::SeqCst);
        self.success_count.store(0, Ordering::SeqCst);
        self.half_open_requests.store(0, Ordering::SeqCst);
        if let Ok(mut state) = self.state.write() {
            *state = CircuitState::Closed;
        }
        if let Ok(mut last_failure) = self.last_failure_time.write() {
            *last_failure = None;
        }
        info!(circuit = %self.name, "Circuit breaker reset");
        self.update_telemetry();
    }

    /// Get failure count
    pub fn failure_count(&self) -> u64 {
        self.failure_count.load(Ordering::SeqCst)
    }

    /// Get success count (for half-open tracking)
    pub fn success_count(&self) -> u64 {
        self.success_count.load(Ordering::SeqCst)
    }

    // ========================================================================
    // Private Methods
    // ========================================================================

    fn should_attempt_reset(&self) -> bool {
        if let Ok(last_failure) = self.last_failure_time.read() {
            if let Some(time) = *last_failure {
                return time.elapsed() >= self.config.reset_timeout;
            }
        }
        false
    }

    fn transition_to_open(&self) {
        if let Ok(mut state) = self.state.write() {
            if *state != CircuitState::Open {
                warn!(circuit = %self.name, failures = self.failure_count.load(Ordering::SeqCst),
                      "Circuit opened - failing fast");
                *state = CircuitState::Open;
            }
        }
        self.success_count.store(0, Ordering::SeqCst);
        self.half_open_requests.store(0, Ordering::SeqCst);
        self.update_telemetry();
    }

    fn transition_to_half_open(&self) {
        if let Ok(mut state) = self.state.write() {
            if *state == CircuitState::Open {
                info!(circuit = %self.name, "Circuit half-open - testing recovery");
                *state = CircuitState::HalfOpen;
            }
        }
        self.success_count.store(0, Ordering::SeqCst);
        self.half_open_requests.store(0, Ordering::SeqCst);
        self.update_telemetry();
    }

    fn transition_to_closed(&self) {
        if let Ok(mut state) = self.state.write() {
            info!(circuit = %self.name, "Circuit closed - service recovered");
            *state = CircuitState::Closed;
        }
        self.failure_count.store(0, Ordering::SeqCst);
        self.success_count.store(0, Ordering::SeqCst);
        self.half_open_requests.store(0, Ordering::SeqCst);
        self.update_telemetry();
    }

    fn update_telemetry(&self) {
        let state = match self.state() {
            CircuitState::Closed => telemetry::CircuitBreakerState::Closed,
            CircuitState::Open => telemetry::CircuitBreakerState::Open,
            CircuitState::HalfOpen => telemetry::CircuitBreakerState::HalfOpen,
        };
        telemetry::set_circuit_breaker_state(state);
    }
}

impl Default for CircuitBreaker {
    fn default() -> Self {
        Self::new("default")
    }
}

// ============================================================================
// Error Type
// ============================================================================

/// Circuit breaker error wrapper
#[derive(Debug)]
pub enum CircuitBreakerError<E> {
    /// Circuit is open, request rejected
    CircuitOpen,
    /// Inner operation error
    Inner(E),
}

impl<E: std::fmt::Display> std::fmt::Display for CircuitBreakerError<E> {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CircuitBreakerError::CircuitOpen => write!(f, "Circuit breaker is open"),
            CircuitBreakerError::Inner(e) => write!(f, "{}", e),
        }
    }
}

impl<E: std::error::Error> std::error::Error for CircuitBreakerError<E> {}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_initial_state() {
        let cb = CircuitBreaker::new("test");
        assert_eq!(cb.state(), CircuitState::Closed);
        assert!(cb.allow_request());
    }

    #[test]
    fn test_opens_after_failures() {
        let config = CircuitBreakerConfig {
            failure_threshold: 3,
            ..Default::default()
        };
        let cb = CircuitBreaker::with_config("test", config);

        // Record failures up to threshold
        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Closed);
        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Closed);
        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Open);

        // Requests should be rejected
        assert!(!cb.allow_request());
    }

    #[test]
    fn test_success_resets_failure_count() {
        let config = CircuitBreakerConfig {
            failure_threshold: 3,
            ..Default::default()
        };
        let cb = CircuitBreaker::with_config("test", config);

        cb.record_failure();
        cb.record_failure();
        assert_eq!(cb.failure_count(), 2);

        cb.record_success();
        assert_eq!(cb.failure_count(), 0);
        assert_eq!(cb.state(), CircuitState::Closed);
    }

    #[test]
    fn test_half_open_limits_requests() {
        let config = CircuitBreakerConfig {
            failure_threshold: 1,
            half_open_max_requests: 2,
            ..Default::default()
        };
        let cb = CircuitBreaker::with_config("test", config);

        // Open the circuit
        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Open);

        // Transition to half-open
        cb.force_state(CircuitState::HalfOpen);

        // Should allow limited requests
        assert!(cb.allow_request());
        assert!(cb.allow_request());
        assert!(!cb.allow_request()); // Exceeds limit
    }

    #[test]
    fn test_half_open_closes_on_success() {
        let config = CircuitBreakerConfig {
            failure_threshold: 1,
            success_threshold: 2,
            ..Default::default()
        };
        let cb = CircuitBreaker::with_config("test", config);

        cb.force_state(CircuitState::HalfOpen);

        cb.record_success();
        assert_eq!(cb.state(), CircuitState::HalfOpen);

        cb.record_success();
        assert_eq!(cb.state(), CircuitState::Closed);
    }

    #[test]
    fn test_half_open_opens_on_failure() {
        let cb = CircuitBreaker::new("test");
        cb.force_state(CircuitState::HalfOpen);

        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Open);
    }

    #[test]
    fn test_reset() {
        let config = CircuitBreakerConfig {
            failure_threshold: 1,
            ..Default::default()
        };
        let cb = CircuitBreaker::with_config("test", config);

        cb.record_failure();
        assert_eq!(cb.state(), CircuitState::Open);

        cb.reset();
        assert_eq!(cb.state(), CircuitState::Closed);
        assert_eq!(cb.failure_count(), 0);
    }

    #[test]
    fn test_force_state() {
        let cb = CircuitBreaker::new("test");

        cb.force_state(CircuitState::Open);
        assert_eq!(cb.state(), CircuitState::Open);

        cb.force_state(CircuitState::HalfOpen);
        assert_eq!(cb.state(), CircuitState::HalfOpen);

        cb.force_state(CircuitState::Closed);
        assert_eq!(cb.state(), CircuitState::Closed);
    }
}

/*
 * Kagami Circuit Breaker
 * Nexus (e4) - Connection, coordination
 *
 * Fail fast, recover gracefully.
 * h(x) >= 0. Always.
 */
