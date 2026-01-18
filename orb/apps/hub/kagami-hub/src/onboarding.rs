//! Voice Onboarding Module
//!
//! Welcome message and first-boot experience for Kagami Hub.
//! Announces greeting, explains usage, and waits for first command.
//!
//! Colony: Beacon (e5) - Guidance, signaling
//!
//! h(x) >= 0. Always.

use std::path::Path;
use std::time::{Duration, Instant};
use tracing::{debug, info, warn};

#[cfg(feature = "rpi")]
use crate::led_ring;

/// Onboarding configuration
#[derive(Debug, Clone)]
pub struct OnboardingConfig {
    /// Welcome message to announce
    pub welcome_message: String,
    /// Duration to wait for first command (seconds)
    pub wait_duration_secs: u32,
    /// Path to onboarding completion marker file
    pub marker_path: String,
}

impl Default for OnboardingConfig {
    fn default() -> Self {
        Self {
            welcome_message: "Welcome to Kagami Hub. Say 'Hey Kagami' followed by a command.".to_string(),
            wait_duration_secs: 30,
            marker_path: "/var/lib/kagami-hub/onboarding_complete".to_string(),
        }
    }
}

/// Onboarding state machine
pub struct OnboardingManager {
    config: OnboardingConfig,
    completed: bool,
}

impl OnboardingManager {
    /// Create a new onboarding manager
    pub fn new(config: OnboardingConfig) -> Self {
        let completed = Path::new(&config.marker_path).exists();

        if completed {
            debug!("Onboarding already completed (marker found)");
        }

        Self { config, completed }
    }

    /// Create with default config
    pub fn new_default() -> Self {
        Self::new(OnboardingConfig::default())
    }

    /// Check if onboarding has been completed
    pub fn is_completed(&self) -> bool {
        self.completed
    }

    /// Run the onboarding sequence
    /// Returns true if a voice command was detected during the wait period
    pub async fn run_onboarding<F, Fut>(
        &mut self,
        speak_fn: F,
        mut check_command_fn: impl FnMut() -> bool,
    ) -> bool
    where
        F: FnOnce(&str) -> Fut,
        Fut: std::future::Future<Output = ()>,
    {
        if self.completed {
            debug!("Skipping onboarding - already completed");
            return false;
        }

        info!("Starting voice onboarding sequence");

        // Light up LED ring during announcement
        #[cfg(feature = "rpi")]
        {
            led_ring::show_spectral_sweep();
        }

        // Announce welcome message
        info!("Announcing: {}", self.config.welcome_message);
        speak_fn(&self.config.welcome_message).await;

        // Wait for first command with pulsing LED
        #[cfg(feature = "rpi")]
        {
            led_ring::show_listening();
        }

        let start = Instant::now();
        let wait_duration = Duration::from_secs(self.config.wait_duration_secs as u64);
        let mut command_detected = false;

        info!("Waiting {} seconds for first command...", self.config.wait_duration_secs);

        while start.elapsed() < wait_duration {
            if check_command_fn() {
                info!("First command detected during onboarding!");
                command_detected = true;
                break;
            }

            // Short sleep to avoid busy-loop
            tokio::time::sleep(Duration::from_millis(100)).await;
        }

        // Mark onboarding as complete
        self.mark_complete();

        // Return to idle state
        #[cfg(feature = "rpi")]
        {
            led_ring::show_idle();
        }

        command_detected
    }

    /// Run simplified onboarding (just speak and mark complete)
    pub async fn run_simple<F, Fut>(&mut self, speak_fn: F)
    where
        F: FnOnce(&str) -> Fut,
        Fut: std::future::Future<Output = ()>,
    {
        if self.completed {
            debug!("Skipping onboarding - already completed");
            return;
        }

        info!("Running simplified onboarding");

        // Light up LED ring during announcement
        #[cfg(feature = "rpi")]
        {
            led_ring::show_boot_indicator();
        }

        // Announce welcome message
        speak_fn(&self.config.welcome_message).await;

        // Mark complete
        self.mark_complete();

        // Return to idle
        #[cfg(feature = "rpi")]
        {
            led_ring::show_idle();
        }
    }

    /// Mark onboarding as complete
    fn mark_complete(&mut self) {
        self.completed = true;

        // Create marker file
        if let Some(parent) = Path::new(&self.config.marker_path).parent() {
            if !parent.exists() {
                if let Err(e) = std::fs::create_dir_all(parent) {
                    warn!("Failed to create onboarding marker directory: {}", e);
                    return;
                }
            }
        }

        if let Err(e) = std::fs::write(&self.config.marker_path, "1") {
            warn!("Failed to write onboarding marker: {}", e);
        } else {
            info!("Onboarding complete, marker written to {}", self.config.marker_path);
        }
    }

    /// Reset onboarding (for testing or re-setup)
    pub fn reset(&mut self) {
        self.completed = false;
        if Path::new(&self.config.marker_path).exists() {
            if let Err(e) = std::fs::remove_file(&self.config.marker_path) {
                warn!("Failed to remove onboarding marker: {}", e);
            }
        }
        info!("Onboarding reset");
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_config() {
        let config = OnboardingConfig::default();
        assert!(config.welcome_message.contains("Hey Kagami"));
        assert_eq!(config.wait_duration_secs, 30);
    }

    #[test]
    fn test_manager_not_completed_initially() {
        // Use a temp path that doesn't exist
        let config = OnboardingConfig {
            marker_path: "/tmp/nonexistent_kagami_test_marker".to_string(),
            ..Default::default()
        };
        let manager = OnboardingManager::new(config);
        assert!(!manager.is_completed());
    }
}

/*
 * Welcome to Kagami.
 * Beacon (e5) - Guidance, signaling
 * h(x) >= 0. Always.
 */
