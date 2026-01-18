//! Circuit Breaker Pattern — Graceful Network Degradation
//!
//! Provides a simple, thread-safe circuit breaker for API request flow control.
//! This is a lightweight implementation designed for HTTP/API clients.
//!
//! Pattern: Closed → (failures ≥ threshold) → Open → (timeout) → HalfOpen → (success) → Closed
//!
//! For full connection lifecycle management (WebSocket, reconnection with backoff),
//! see the `transport::ConnectionStateMachine` instead.
//!
//! h(x) ≥ 0. Always.

use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use std::sync::RwLock;
use std::time::{Duration, Instant};
use tracing::{info, warn};

/// Circuit breaker states
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CircuitState {
    /// Normal operation — requests flow through
    Closed,
    /// Circuit tripped — requests rejected immediately
    Open,
    /// Testing recovery — one request allowed to test
    HalfOpen,
}

impl std::fmt::Display for CircuitState {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CircuitState::Closed => write!(f, "CLOSED"),
            CircuitState::Open => write!(f, "OPEN"),
            CircuitState::HalfOpen => write!(f, "HALF_OPEN"),
        }
    }
}

/// Circuit breaker for graceful network degradation.
///
/// Prevents cascade failures by:
/// 1. Tracking consecutive failures
/// 2. Opening circuit when threshold exceeded
/// 3. Allowing recovery attempts after timeout
///
/// # Example
///
/// ```rust,no_run
/// use kagami_mesh_sdk::circuit_breaker::CircuitBreaker;
///
/// let breaker = CircuitBreaker::new();
///
/// // Before making a request
/// if !breaker.allow_request() {
///     // Circuit is open, fail fast
///     panic!("Service unavailable");
/// }
///
/// // After request completes (simulate success)
/// let request_succeeded = true;
/// if request_succeeded {
///     breaker.record_success();
/// } else {
///     breaker.record_failure();
/// }
/// ```
pub struct CircuitBreaker {
    /// Current state (stored as u32 for atomic operations)
    state: AtomicU32,
    /// Number of consecutive failures
    failure_count: AtomicU32,
    /// Timestamp of last failure (millis since start)
    last_failure_ms: AtomicU64,
    /// Reference instant for timing
    start_instant: Instant,
    /// Lock for state transitions
    transition_lock: RwLock<()>,
}

impl Default for CircuitBreaker {
    fn default() -> Self {
        Self::new()
    }
}

impl CircuitBreaker {
    /// Number of consecutive failures before opening circuit
    pub const FAILURE_THRESHOLD: u32 = 3;

    /// Time to wait before attempting recovery
    pub const RESET_TIMEOUT: Duration = Duration::from_secs(30);

    /// Create a new circuit breaker in closed state.
    pub fn new() -> Self {
        Self {
            state: AtomicU32::new(0), // Closed
            failure_count: AtomicU32::new(0),
            last_failure_ms: AtomicU64::new(0),
            start_instant: Instant::now(),
            transition_lock: RwLock::new(()),
        }
    }

    /// Get current state.
    pub fn state(&self) -> CircuitState {
        match self.state.load(Ordering::SeqCst) {
            0 => CircuitState::Closed,
            1 => CircuitState::Open,
            2 => CircuitState::HalfOpen,
            _ => CircuitState::Closed,
        }
    }

    fn set_state(&self, state: CircuitState) {
        let value = match state {
            CircuitState::Closed => 0,
            CircuitState::Open => 1,
            CircuitState::HalfOpen => 2,
        };
        self.state.store(value, Ordering::SeqCst);
    }

    /// Check if a request should be allowed.
    ///
    /// Returns true if request can proceed, false if circuit is open.
    pub fn allow_request(&self) -> bool {
        let _guard = self.transition_lock.read().unwrap();

        match self.state() {
            CircuitState::Closed => true,

            CircuitState::Open => {
                // Check if reset timeout has elapsed
                let last_failure = self.last_failure_ms.load(Ordering::SeqCst);
                let elapsed_ms = self.start_instant.elapsed().as_millis() as u64;
                let since_failure = elapsed_ms.saturating_sub(last_failure);

                if since_failure > Self::RESET_TIMEOUT.as_millis() as u64 {
                    // Upgrade lock for state transition
                    drop(_guard);
                    let _write_guard = self.transition_lock.write().unwrap();

                    // Double-check after acquiring write lock
                    if self.state() == CircuitState::Open {
                        self.set_state(CircuitState::HalfOpen);
                        info!("Circuit breaker: HALF_OPEN (testing recovery)");
                    }
                    true
                } else {
                    false
                }
            }

            CircuitState::HalfOpen => true,
        }
    }

    /// Record a successful request. Resets the circuit breaker.
    pub fn record_success(&self) {
        let _guard = self.transition_lock.write().unwrap();

        self.failure_count.store(0, Ordering::SeqCst);

        if self.state() != CircuitState::Closed {
            self.set_state(CircuitState::Closed);
            info!("Circuit breaker: CLOSED (recovered)");
        }
    }

    /// Record a failed request. May trip the circuit breaker.
    pub fn record_failure(&self) {
        let _guard = self.transition_lock.write().unwrap();

        let failures = self.failure_count.fetch_add(1, Ordering::SeqCst) + 1;
        let now_ms = self.start_instant.elapsed().as_millis() as u64;
        self.last_failure_ms.store(now_ms, Ordering::SeqCst);

        match self.state() {
            CircuitState::Closed => {
                if failures >= Self::FAILURE_THRESHOLD {
                    self.set_state(CircuitState::Open);
                    warn!(
                        "Circuit breaker: OPEN (threshold reached after {} failures)",
                        failures
                    );
                }
            }
            CircuitState::HalfOpen => {
                self.set_state(CircuitState::Open);
                warn!("Circuit breaker: OPEN (half-open test failed)");
            }
            CircuitState::Open => {}
        }
    }

    /// Reset the circuit breaker to closed state.
    /// Use carefully — this bypasses normal recovery flow.
    pub fn reset(&self) {
        let _guard = self.transition_lock.write().unwrap();

        self.failure_count.store(0, Ordering::SeqCst);
        self.last_failure_ms.store(0, Ordering::SeqCst);
        self.set_state(CircuitState::Closed);
        info!("Circuit breaker: RESET to CLOSED");
    }

    /// Get current failure count (for debugging/UI).
    pub fn failure_count(&self) -> u32 {
        self.failure_count.load(Ordering::SeqCst)
    }

    /// Check if circuit is currently open.
    pub fn is_open(&self) -> bool {
        self.state() == CircuitState::Open
    }

    /// Time remaining until circuit can attempt recovery (if open).
    pub fn time_until_retry(&self) -> Option<Duration> {
        if self.state() != CircuitState::Open {
            return None;
        }

        let last_failure = self.last_failure_ms.load(Ordering::SeqCst);
        let elapsed_ms = self.start_instant.elapsed().as_millis() as u64;
        let since_failure = elapsed_ms.saturating_sub(last_failure);
        let reset_ms = Self::RESET_TIMEOUT.as_millis() as u64;

        if since_failure >= reset_ms {
            Some(Duration::ZERO)
        } else {
            Some(Duration::from_millis(reset_ms - since_failure))
        }
    }

    /// Get current backoff duration based on failure count.
    /// Uses exponential backoff: 2^(failures) seconds, capped at 60 seconds.
    pub fn current_backoff(&self) -> Duration {
        let failures = self.failure_count.load(Ordering::SeqCst);
        let backoff_secs = (2u64.pow(failures.min(6))).min(60);
        Duration::from_secs(backoff_secs)
    }
}

/// Global circuit breaker instance.
static CIRCUIT_BREAKER: std::sync::OnceLock<CircuitBreaker> = std::sync::OnceLock::new();

/// Get the global circuit breaker.
pub fn get_circuit_breaker() -> &'static CircuitBreaker {
    CIRCUIT_BREAKER.get_or_init(CircuitBreaker::new)
}

/*
 * 鏡
 * Circuit breaker: Fail fast, recover gracefully.
 * h(x) ≥ 0. Always.
 */

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_initial_state() {
        let breaker = CircuitBreaker::new();
        assert_eq!(breaker.state(), CircuitState::Closed);
        assert!(breaker.allow_request());
    }

    #[test]
    fn test_failure_threshold() {
        let breaker = CircuitBreaker::new();

        // Record failures up to threshold
        for _ in 0..CircuitBreaker::FAILURE_THRESHOLD {
            breaker.record_failure();
        }

        assert_eq!(breaker.state(), CircuitState::Open);
        assert!(!breaker.allow_request());
    }

    #[test]
    fn test_success_resets() {
        let breaker = CircuitBreaker::new();

        breaker.record_failure();
        breaker.record_failure();
        assert_eq!(breaker.failure_count(), 2);

        breaker.record_success();
        assert_eq!(breaker.failure_count(), 0);
        assert_eq!(breaker.state(), CircuitState::Closed);
    }

    #[test]
    fn test_reset() {
        let breaker = CircuitBreaker::new();

        for _ in 0..CircuitBreaker::FAILURE_THRESHOLD {
            breaker.record_failure();
        }
        assert_eq!(breaker.state(), CircuitState::Open);

        breaker.reset();
        assert_eq!(breaker.state(), CircuitState::Closed);
        assert_eq!(breaker.failure_count(), 0);
    }

    #[test]
    fn test_display() {
        assert_eq!(CircuitState::Closed.to_string(), "CLOSED");
        assert_eq!(CircuitState::Open.to_string(), "OPEN");
        assert_eq!(CircuitState::HalfOpen.to_string(), "HALF_OPEN");
    }
}
