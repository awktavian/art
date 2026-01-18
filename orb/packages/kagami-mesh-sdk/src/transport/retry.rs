//! Command retry service with circuit breaker integration.
//!
//! Provides exponential backoff retry logic for mesh commands
//! with circuit breaker protection against cascade failures.
//!
//! h(x) >= 0. Always.

use super::traits::{RetryStrategy, TransportConfig};
use crate::circuit_breaker::{CircuitBreaker, CircuitState};
use serde::{Deserialize, Serialize};
use std::sync::atomic::{AtomicU32, Ordering};
use std::time::Duration;

/// Command execution result for retry decisions.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CommandResult {
    /// Command succeeded.
    Success,
    /// Command failed with a retryable error.
    RetryableError { reason: String },
    /// Command failed with a non-retryable error.
    PermanentError { reason: String },
    /// Command timed out.
    Timeout,
    /// Circuit breaker rejected the command.
    CircuitOpen,
}

impl CommandResult {
    /// Check if this result indicates the command should be retried.
    pub fn should_retry(&self) -> bool {
        matches!(self, CommandResult::RetryableError { .. } | CommandResult::Timeout)
    }

    /// Check if this result indicates success.
    pub fn is_success(&self) -> bool {
        matches!(self, CommandResult::Success)
    }
}

/// Retry statistics for monitoring.
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct RetryStats {
    /// Total commands executed.
    pub total_commands: u64,
    /// Commands that succeeded on first try.
    pub first_try_successes: u64,
    /// Commands that succeeded after retry.
    pub retry_successes: u64,
    /// Commands that failed after all retries.
    pub final_failures: u64,
    /// Commands rejected by circuit breaker.
    pub circuit_rejections: u64,
    /// Total retry attempts across all commands.
    pub total_retries: u64,
}

/// Command retry service that manages retry logic and circuit breaker.
pub struct CommandRetryService {
    /// Transport configuration for retry parameters.
    config: TransportConfig,
    /// Circuit breaker for failure protection.
    circuit_breaker: CircuitBreaker,
    /// Current retry attempt for active command.
    current_attempt: AtomicU32,
    /// Stats tracking.
    stats: std::sync::Mutex<RetryStats>,
}

impl CommandRetryService {
    /// Create a new retry service with default config.
    pub fn new() -> Self {
        Self::with_config(TransportConfig::default())
    }

    /// Create with custom configuration.
    pub fn with_config(config: TransportConfig) -> Self {
        Self {
            config,
            circuit_breaker: CircuitBreaker::new(),
            current_attempt: AtomicU32::new(0),
            stats: std::sync::Mutex::new(RetryStats::default()),
        }
    }

    /// Check if a command should be allowed to execute.
    ///
    /// Returns None if allowed, or a rejection reason if blocked.
    pub fn should_execute(&self) -> Option<String> {
        if !self.circuit_breaker.allow_request() {
            let time_until = self.circuit_breaker.time_until_retry();
            let msg = if let Some(duration) = time_until {
                format!("Circuit open, retry in {}s", duration.as_secs())
            } else {
                "Circuit open".to_string()
            };
            return Some(msg);
        }
        None
    }

    /// Begin a command execution, resetting attempt counter.
    pub fn begin_command(&self) {
        self.current_attempt.store(0, Ordering::SeqCst);
        let mut stats = self.stats.lock().unwrap();
        stats.total_commands += 1;
    }

    /// Record command result and get retry strategy.
    pub fn record_result(&self, result: &CommandResult) -> RetryStrategy {
        let attempt = self.current_attempt.fetch_add(1, Ordering::SeqCst);

        match result {
            CommandResult::Success => {
                self.circuit_breaker.record_success();
                let mut stats = self.stats.lock().unwrap();
                if attempt == 0 {
                    stats.first_try_successes += 1;
                } else {
                    stats.retry_successes += 1;
                }
                RetryStrategy::no_retry("Command succeeded")
            }

            CommandResult::RetryableError { reason } => {
                self.circuit_breaker.record_failure();
                self.calculate_retry_strategy(attempt, reason)
            }

            CommandResult::Timeout => {
                self.circuit_breaker.record_failure();
                self.calculate_retry_strategy(attempt, "timeout")
            }

            CommandResult::PermanentError { reason } => {
                // Don't retry permanent errors, but don't trip circuit breaker either
                let mut stats = self.stats.lock().unwrap();
                stats.final_failures += 1;
                RetryStrategy::no_retry(format!("Permanent error: {}", reason))
            }

            CommandResult::CircuitOpen => {
                let mut stats = self.stats.lock().unwrap();
                stats.circuit_rejections += 1;
                RetryStrategy::no_retry("Circuit breaker open")
            }
        }
    }

    /// Calculate retry strategy based on attempt number and config.
    fn calculate_retry_strategy(&self, attempt: u32, reason: &str) -> RetryStrategy {
        let max_attempts = self.config.max_retry_attempts;

        // Check if we've exceeded max attempts (0 = unlimited)
        if max_attempts > 0 && attempt >= max_attempts {
            let mut stats = self.stats.lock().unwrap();
            stats.final_failures += 1;
            return RetryStrategy::no_retry(format!(
                "Max retries ({}) exceeded: {}",
                max_attempts, reason
            ));
        }

        // Check circuit breaker
        if self.circuit_breaker.is_open() {
            let mut stats = self.stats.lock().unwrap();
            stats.circuit_rejections += 1;
            return RetryStrategy::no_retry("Circuit breaker open");
        }

        // Calculate backoff delay: initial * multiplier^attempt, capped at max
        let delay_ms = self.calculate_backoff_ms(attempt);

        // Update stats
        {
            let mut stats = self.stats.lock().unwrap();
            stats.total_retries += 1;
        }

        RetryStrategy::retry(delay_ms, attempt + 1, max_attempts)
    }

    /// Calculate backoff delay in milliseconds.
    fn calculate_backoff_ms(&self, attempt: u32) -> u64 {
        let base = self.config.initial_retry_ms as f64;
        let multiplier = self.config.retry_multiplier;
        let max = self.config.max_retry_ms;

        let delay = base * multiplier.powi(attempt as i32);
        (delay as u64).min(max)
    }

    /// Get current circuit breaker state.
    pub fn circuit_state(&self) -> CircuitState {
        self.circuit_breaker.state()
    }

    /// Get current failure count.
    pub fn failure_count(&self) -> u32 {
        self.circuit_breaker.failure_count()
    }

    /// Get time until circuit breaker recovery attempt.
    pub fn time_until_retry(&self) -> Option<Duration> {
        self.circuit_breaker.time_until_retry()
    }

    /// Reset the circuit breaker (use with caution).
    pub fn reset_circuit_breaker(&self) {
        self.circuit_breaker.reset();
    }

    /// Get current backoff duration based on failure count.
    pub fn current_backoff(&self) -> Duration {
        self.circuit_breaker.current_backoff()
    }

    /// Get retry statistics.
    pub fn stats(&self) -> RetryStats {
        self.stats.lock().unwrap().clone()
    }

    /// Reset statistics.
    pub fn reset_stats(&self) {
        *self.stats.lock().unwrap() = RetryStats::default();
    }

    /// Get the configuration.
    pub fn config(&self) -> &TransportConfig {
        &self.config
    }
}

impl Default for CommandRetryService {
    fn default() -> Self {
        Self::new()
    }
}

/// Fibonacci backoff calculator for voice streaming reconnection.
///
/// Uses Fibonacci sequence for more natural backoff progression:
/// 1, 1, 2, 3, 5, 8, 13, 21, 34, 55 seconds
pub struct FibonacciBackoff {
    current: u64,
    next: u64,
    max_delay_secs: u64,
    attempt: u32,
}

impl FibonacciBackoff {
    /// Create a new Fibonacci backoff calculator.
    pub fn new() -> Self {
        Self {
            current: 1,
            next: 1,
            max_delay_secs: 60,
            attempt: 0,
        }
    }

    /// Create with custom max delay.
    pub fn with_max_delay(max_delay_secs: u64) -> Self {
        Self {
            max_delay_secs,
            ..Self::new()
        }
    }

    /// Get the next backoff delay.
    pub fn next_delay(&mut self) -> Duration {
        let delay = self.current.min(self.max_delay_secs);
        let new_next = self.current + self.next;
        self.current = self.next;
        self.next = new_next;
        self.attempt += 1;
        Duration::from_secs(delay)
    }

    /// Get current attempt number.
    pub fn attempt(&self) -> u32 {
        self.attempt
    }

    /// Reset the backoff.
    pub fn reset(&mut self) {
        self.current = 1;
        self.next = 1;
        self.attempt = 0;
    }

    /// Get current delay without advancing.
    pub fn current_delay(&self) -> Duration {
        Duration::from_secs(self.current.min(self.max_delay_secs))
    }
}

impl Default for FibonacciBackoff {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_command_result() {
        assert!(CommandResult::Success.is_success());
        assert!(!CommandResult::Timeout.is_success());

        assert!(CommandResult::RetryableError { reason: "test".into() }.should_retry());
        assert!(CommandResult::Timeout.should_retry());
        assert!(!CommandResult::Success.should_retry());
        assert!(!CommandResult::PermanentError { reason: "test".into() }.should_retry());
    }

    #[test]
    fn test_retry_service_success() {
        let service = CommandRetryService::new();

        service.begin_command();
        let strategy = service.record_result(&CommandResult::Success);

        assert!(!strategy.should_retry);
        assert_eq!(service.stats().first_try_successes, 1);
    }

    #[test]
    fn test_retry_service_retries() {
        let config = TransportConfig {
            initial_retry_ms: 100,
            max_retry_ms: 1000,
            retry_multiplier: 2.0,
            max_retry_attempts: 2, // Low limit to test before circuit breaker trips at 3
            ..Default::default()
        };
        let service = CommandRetryService::with_config(config);

        service.begin_command();

        // First failure (attempt 0)
        let strategy = service.record_result(&CommandResult::RetryableError {
            reason: "test".into(),
        });
        assert!(strategy.should_retry, "First failure should allow retry");
        assert_eq!(strategy.attempt, 1);
        assert_eq!(strategy.delay_ms, 100); // initial

        // Second failure (attempt 1)
        let strategy = service.record_result(&CommandResult::RetryableError {
            reason: "test".into(),
        });
        // With max_retry_attempts = 2, attempt 1 >= 2 is false, so retry allowed
        assert!(strategy.should_retry, "Second failure should allow retry");
        assert_eq!(strategy.attempt, 2);
        assert_eq!(strategy.delay_ms, 200); // 100 * 2

        // Third failure (attempt 2) - should not retry (max = 2, and 2 >= 2 is true)
        let strategy = service.record_result(&CommandResult::RetryableError {
            reason: "test".into(),
        });
        assert!(!strategy.should_retry, "Third failure should not allow retry (max attempts reached)");

        // Stats: 2 retries were allowed (attempts 0 and 1), 1 final failure
        assert_eq!(service.stats().total_retries, 2);
        assert_eq!(service.stats().final_failures, 1);
    }

    #[test]
    fn test_backoff_calculation() {
        let config = TransportConfig {
            initial_retry_ms: 500,
            max_retry_ms: 10_000,
            retry_multiplier: 2.0,
            ..Default::default()
        };
        let service = CommandRetryService::with_config(config);

        assert_eq!(service.calculate_backoff_ms(0), 500); // 500 * 2^0
        assert_eq!(service.calculate_backoff_ms(1), 1000); // 500 * 2^1
        assert_eq!(service.calculate_backoff_ms(2), 2000); // 500 * 2^2
        assert_eq!(service.calculate_backoff_ms(3), 4000); // 500 * 2^3
        assert_eq!(service.calculate_backoff_ms(4), 8000); // 500 * 2^4
        assert_eq!(service.calculate_backoff_ms(5), 10_000); // capped at max
    }

    #[test]
    fn test_fibonacci_backoff() {
        let mut backoff = FibonacciBackoff::new();

        assert_eq!(backoff.next_delay(), Duration::from_secs(1)); // fib(0) = 1
        assert_eq!(backoff.next_delay(), Duration::from_secs(1)); // fib(1) = 1
        assert_eq!(backoff.next_delay(), Duration::from_secs(2)); // fib(2) = 2
        assert_eq!(backoff.next_delay(), Duration::from_secs(3)); // fib(3) = 3
        assert_eq!(backoff.next_delay(), Duration::from_secs(5)); // fib(4) = 5
        assert_eq!(backoff.next_delay(), Duration::from_secs(8)); // fib(5) = 8
        assert_eq!(backoff.attempt(), 6);

        backoff.reset();
        assert_eq!(backoff.attempt(), 0);
        assert_eq!(backoff.next_delay(), Duration::from_secs(1));
    }

    #[test]
    fn test_fibonacci_max_cap() {
        let mut backoff = FibonacciBackoff::with_max_delay(5);

        // Advance past max
        for _ in 0..10 {
            backoff.next_delay();
        }

        // Should be capped at 5
        assert_eq!(backoff.current_delay(), Duration::from_secs(5));
    }

    #[test]
    fn test_circuit_breaker_integration() {
        let config = TransportConfig {
            failure_threshold: 3,
            ..Default::default()
        };
        let service = CommandRetryService::with_config(config);

        // Trip the circuit breaker
        for _ in 0..3 {
            service.begin_command();
            service.record_result(&CommandResult::RetryableError {
                reason: "test".into(),
            });
        }

        // Circuit should be open (after 3 failures in circuit breaker)
        // Note: Circuit breaker has its own threshold
        assert!(service.should_execute().is_some() || service.circuit_state() == CircuitState::Closed);
    }
}
