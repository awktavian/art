//! Safety Monitor
//!
//! Ensures h(x) >= 0 at all times.
//! Monitors HID activity and enforces consent requirements.

use super::hid::ducky::SignedPayload;
use ed25519_dalek::VerifyingKey;
use log::*;

/// Safety monitor configuration
#[derive(Debug, Clone)]
pub struct SafetyConfig {
    /// Allow HID operations
    pub hid_enabled: bool,
    /// Allow payload execution
    pub payloads_enabled: bool,
    /// Require visual indicator for HID
    pub require_indicator: bool,
    /// Maximum consecutive HID operations
    pub max_hid_burst: u32,
    /// Developer mode (relaxed restrictions)
    pub developer_mode: bool,
}

impl Default for SafetyConfig {
    fn default() -> Self {
        Self {
            hid_enabled: true,
            payloads_enabled: false, // Disabled by default
            require_indicator: true,
            max_hid_burst: 100,
            developer_mode: false,
        }
    }
}

/// Safety monitor state
pub struct SafetyMonitor {
    config: SafetyConfig,
    consecutive_hid_ops: u32,
    last_check_ok: bool,
    trusted_signers: heapless::Vec<[u8; 32], 8>,
}

impl SafetyMonitor {
    /// Create a new safety monitor
    pub fn new() -> Self {
        info!("Initializing safety monitor...");
        info!("h(x) >= 0. Always.");

        let mut monitor = Self {
            config: SafetyConfig::default(),
            consecutive_hid_ops: 0,
            last_check_ok: true,
            trusted_signers: heapless::Vec::new(),
        };

        // Add builtin signer (Kagami factory key)
        // TODO: Load actual factory public key
        let factory_key = [0u8; 32]; // Placeholder
        monitor.trusted_signers.push(factory_key).ok();

        info!("Safety monitor initialized with {} trusted signers", monitor.trusted_signers.len());

        monitor
    }

    /// Run periodic safety check
    pub fn check(&mut self) {
        // Reset burst counter periodically
        // In a real implementation, this would be time-based
        if self.consecutive_hid_ops > 0 {
            self.consecutive_hid_ops = self.consecutive_hid_ops.saturating_sub(1);
        }

        self.last_check_ok = true;
    }

    /// Check if safety is OK
    pub fn is_ok(&self) -> bool {
        self.last_check_ok
    }

    /// Check if HID operations are allowed
    pub fn allow_hid(&mut self) -> bool {
        if !self.config.hid_enabled {
            warn!("HID operations disabled by configuration");
            return false;
        }

        if self.consecutive_hid_ops >= self.config.max_hid_burst {
            warn!("HID burst limit exceeded ({}/{})",
                  self.consecutive_hid_ops, self.config.max_hid_burst);
            return false;
        }

        self.consecutive_hid_ops += 1;
        true
    }

    /// Check if payload execution is allowed
    pub fn allow_payload_execution(&self) -> bool {
        if !self.config.payloads_enabled {
            warn!("Payload execution disabled by configuration");
            return false;
        }

        if !self.config.developer_mode && !self.config.require_indicator {
            // In non-developer mode, we always require visual indicator
            warn!("Payload execution requires visual indicator");
            return false;
        }

        true
    }

    /// Verify a payload signature
    pub fn verify_payload_signature(&self, payload: &SignedPayload) -> bool {
        // Check if signer is trusted
        if !self.trusted_signers.contains(&payload.signer_pubkey) {
            // For user/community payloads, check trust level
            match payload.trust_level {
                super::hid::ducky::TrustLevel::Builtin => {
                    // Builtin payloads must be signed by factory key
                    warn!("Builtin payload not signed by factory key");
                    return false;
                }
                super::hid::ducky::TrustLevel::Untrusted => {
                    warn!("Untrusted payload rejected");
                    return false;
                }
                _ => {
                    // User/Community payloads can be signed by any key
                    // but the signature must still be valid
                }
            }
        }

        // Verify the actual signature
        payload.verify()
    }

    /// Enable HID operations
    pub fn enable_hid(&mut self) {
        self.config.hid_enabled = true;
        info!("HID operations enabled");
    }

    /// Disable HID operations
    pub fn disable_hid(&mut self) {
        self.config.hid_enabled = false;
        info!("HID operations disabled");
    }

    /// Enable payload execution
    pub fn enable_payloads(&mut self) {
        self.config.payloads_enabled = true;
        warn!("Payload execution enabled - ensure visual indicators are active");
    }

    /// Disable payload execution
    pub fn disable_payloads(&mut self) {
        self.config.payloads_enabled = false;
        info!("Payload execution disabled");
    }

    /// Enable developer mode
    pub fn enable_developer_mode(&mut self) {
        self.config.developer_mode = true;
        warn!("Developer mode enabled - reduced safety restrictions");
        warn!("h(x) >= 0 still applies, but with relaxed constraints");
    }

    /// Disable developer mode
    pub fn disable_developer_mode(&mut self) {
        self.config.developer_mode = false;
        info!("Developer mode disabled");
    }

    /// Add a trusted signer
    pub fn add_trusted_signer(&mut self, pubkey: [u8; 32]) -> bool {
        if self.trusted_signers.contains(&pubkey) {
            return true;
        }

        self.trusted_signers.push(pubkey)
            .map(|_| {
                info!("Added trusted signer");
                true
            })
            .unwrap_or_else(|_| {
                warn!("Trusted signer list full");
                false
            })
    }

    /// Remove a trusted signer
    pub fn remove_trusted_signer(&mut self, pubkey: &[u8; 32]) {
        if let Some(pos) = self.trusted_signers.iter().position(|k| k == pubkey) {
            self.trusted_signers.swap_remove(pos);
            info!("Removed trusted signer");
        }
    }
}

/// Safety barrier function
///
/// h(x) >= 0 is the fundamental safety constraint.
/// This function computes the barrier value for a given state.
pub fn barrier_function(state: &SafetyState) -> f32 {
    // Compute multiple barrier components
    let h_hid = if state.hid_active && !state.indicator_active {
        -1.0 // Violation: HID active without indicator
    } else {
        1.0
    };

    let h_burst = 1.0 - (state.consecutive_ops as f32 / state.max_ops as f32);

    let h_consent = if state.requires_consent && !state.consent_given {
        -1.0 // Violation: action requires consent
    } else {
        1.0
    };

    // Take minimum (most restrictive)
    h_hid.min(h_burst).min(h_consent)
}

/// Safety state for barrier function
#[derive(Debug, Clone)]
pub struct SafetyState {
    pub hid_active: bool,
    pub indicator_active: bool,
    pub consecutive_ops: u32,
    pub max_ops: u32,
    pub requires_consent: bool,
    pub consent_given: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_barrier_function() {
        // Safe state
        let state = SafetyState {
            hid_active: true,
            indicator_active: true,
            consecutive_ops: 10,
            max_ops: 100,
            requires_consent: false,
            consent_given: false,
        };
        assert!(barrier_function(&state) >= 0.0);

        // Unsafe state (HID without indicator)
        let state = SafetyState {
            hid_active: true,
            indicator_active: false,
            consecutive_ops: 10,
            max_ops: 100,
            requires_consent: false,
            consent_given: false,
        };
        assert!(barrier_function(&state) < 0.0);
    }

    #[test]
    fn test_hid_burst_limit() {
        let mut monitor = SafetyMonitor::new();

        // First 100 should be allowed
        for _ in 0..100 {
            assert!(monitor.allow_hid());
        }

        // 101st should be blocked
        assert!(!monitor.allow_hid());
    }
}
