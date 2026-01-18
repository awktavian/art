//! HID Rate Limiter
//!
//! Prevents DoS and abuse by limiting the rate of HID reports.
//! This is a safety mechanism (h(x) >= 0).

use std::collections::HashMap;
use std::time::{Duration, Instant};

/// Rate limiter for HID operations
pub struct RateLimiter {
    /// Maximum keystrokes per second
    max_keys_per_sec: u32,
    /// Maximum mouse reports per second
    max_mouse_per_sec: u32,
    /// Maximum payloads per minute
    max_payloads_per_min: u32,
    /// Cooldown between payloads
    payload_cooldown: Duration,

    /// Tracking state
    key_count: u32,
    mouse_count: u32,
    payload_count: u32,
    last_key_reset: Instant,
    last_mouse_reset: Instant,
    last_payload_reset: Instant,
    last_payload_time: Option<Instant>,
}

impl RateLimiter {
    /// Create a new rate limiter
    pub fn new(max_keys_per_sec: u32, max_mouse_per_sec: u32, max_payloads_per_min: u32) -> Self {
        let now = Instant::now();
        Self {
            max_keys_per_sec,
            max_mouse_per_sec,
            max_payloads_per_min,
            payload_cooldown: Duration::from_millis(1000),
            key_count: 0,
            mouse_count: 0,
            payload_count: 0,
            last_key_reset: now,
            last_mouse_reset: now,
            last_payload_reset: now,
            last_payload_time: None,
        }
    }

    /// Check if an action is allowed
    pub fn allow(&mut self, action_type: &str) -> bool {
        let now = Instant::now();

        match action_type {
            "keyboard" => {
                // Reset counter if a second has passed
                if now.duration_since(self.last_key_reset) >= Duration::from_secs(1) {
                    self.key_count = 0;
                    self.last_key_reset = now;
                }

                if self.key_count < self.max_keys_per_sec {
                    self.key_count += 1;
                    true
                } else {
                    false
                }
            }

            "mouse" => {
                if now.duration_since(self.last_mouse_reset) >= Duration::from_secs(1) {
                    self.mouse_count = 0;
                    self.last_mouse_reset = now;
                }

                if self.mouse_count < self.max_mouse_per_sec {
                    self.mouse_count += 1;
                    true
                } else {
                    false
                }
            }

            "payload" => {
                // Check cooldown
                if let Some(last) = self.last_payload_time {
                    if now.duration_since(last) < self.payload_cooldown {
                        return false;
                    }
                }

                // Reset counter if a minute has passed
                if now.duration_since(self.last_payload_reset) >= Duration::from_secs(60) {
                    self.payload_count = 0;
                    self.last_payload_reset = now;
                }

                if self.payload_count < self.max_payloads_per_min {
                    self.payload_count += 1;
                    self.last_payload_time = Some(now);
                    true
                } else {
                    false
                }
            }

            // Consumer and gamepad reports use mouse limits
            "consumer" | "gamepad" => {
                if now.duration_since(self.last_mouse_reset) >= Duration::from_secs(1) {
                    self.mouse_count = 0;
                    self.last_mouse_reset = now;
                }

                if self.mouse_count < self.max_mouse_per_sec {
                    self.mouse_count += 1;
                    true
                } else {
                    false
                }
            }

            _ => true, // Unknown types are allowed (fail-open)
        }
    }

    /// Get current statistics
    pub fn stats(&self) -> RateLimiterStats {
        RateLimiterStats {
            keys_this_second: self.key_count,
            mouse_this_second: self.mouse_count,
            payloads_this_minute: self.payload_count,
        }
    }
}

/// Rate limiter statistics
#[derive(Debug, Clone)]
pub struct RateLimiterStats {
    pub keys_this_second: u32,
    pub mouse_this_second: u32,
    pub payloads_this_minute: u32,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_keyboard_rate_limit() {
        let mut limiter = RateLimiter::new(5, 10, 2);

        // First 5 should be allowed
        for _ in 0..5 {
            assert!(limiter.allow("keyboard"));
        }

        // 6th should be blocked
        assert!(!limiter.allow("keyboard"));
    }

    #[test]
    fn test_payload_cooldown() {
        let mut limiter = RateLimiter::new(50, 125, 10);

        // First payload allowed
        assert!(limiter.allow("payload"));

        // Second payload blocked (cooldown)
        assert!(!limiter.allow("payload"));
    }
}
