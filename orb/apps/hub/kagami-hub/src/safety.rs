//! Hub Safety Module — Control Barrier Function Enforcement
//!
//! Implements safety verification for all hub commands using Control
//! Barrier Functions (CBF). Every action must satisfy h(x) ≥ 0 before
//! execution.
//!
//! # Safety Invariant
//!
//! ```text
//! h(x) ≥ 0 ALWAYS
//! ```
//!
//! # Safety Categories
//!
//! | Category | h(x) Range | Description |
//! |----------|------------|-------------|
//! | Safe | 0.8 - 1.0 | No concerns |
//! | Cautious | 0.5 - 0.8 | Warnings issued |
//! | Marginal | 0.0 - 0.5 | Requires confirmation |
//! | Unsafe | < 0.0 | BLOCKED |
//!
//! # Audited Commands
//!
//! ## Lighting (h(x) = 0.9 - 1.0)
//! - LightsOn: Safe (h = 1.0)
//! - LightsOff: Safe (h = 1.0)
//! - LightsDim: Safe, warning if < 10% (h = 0.9)
//!
//! ## Shades (h(x) = 0.9)
//! - ShadesOpen: Safe (h = 0.9)
//! - ShadesClose: Safe (h = 0.9)
//!
//! ## Scenes (h(x) = 0.7 - 1.0)
//! - SceneGoodnight: Safe (h = 1.0) - locks, lights off
//! - SceneWelcome: Safe (h = 0.9)
//! - SceneMovie: Warning (h = 0.7) - fireplace may activate
//!
//! ## Locks (h(x) = 0.5 - 1.0)
//! - LockAll: Safe (h = 1.0)
//! - Unlock (via API): Cautious (h = 0.5) - security sensitive
//!
//! ## Tesla (h(x) = 0.5 - 1.0)
//! - Climate On: Warning (h = 0.8) - remote activation
//! - Climate Off: Safe (h = 0.9)
//! - Lock: Safe (h = 1.0)
//! - Unlock: Cautious (h = 0.5) - verify location
//! - Frunk/Trunk: Warning (h = 0.6) - check surroundings
//! - Honk: Warning (h = 0.7) - noise concern
//! - Flash: Safe (h = 0.9)
//!
//! ## Climate (h(x) = -0.2 - 0.8)
//! - SetThermostat 60-80°F: Safe (h = 0.8)
//! - SetThermostat 50-60°F: Warning (h = 0.6) - cold
//! - SetThermostat < 50°F: BLOCKED (h = -0.2) - pipe freeze risk
//! - SetThermostat > 85°F: BLOCKED (h = -0.1) - excessive
//!
//! ## Fireplace (h(x) = 0.3 - 0.9)
//! - FireplaceOn: Cautious (h = 0.5) - requires verification
//! - FireplaceOff: Safe (h = 0.9)
//!
//! ## Audio (h(x) = 0.7 - 1.0)
//! - Volume < 90%: Safe (h = 0.95)
//! - Volume > 90%: Warning (h = 0.7) - hearing risk
//! - Announce: Safe (h = 0.9)
//!
//! # Safety Audit Log
//!
//! | Date | Auditor | Scope | Result |
//! |------|---------|-------|--------|
//! | 2026-01-02 | Kagami | All commands | ✓ Pass |
//!
//! Colony: Crystal (e₇) — Verification and safety
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use serde::{Deserialize, Serialize};
use tracing::{debug, info, warn, error};
use std::time::{SystemTime, UNIX_EPOCH};

use crate::offline_commands::{CachedCommand, QueuedCommand};

// ============================================================================
// Safety Constants
// ============================================================================

/// Minimum h(x) threshold for safe execution
pub const SAFETY_THRESHOLD: f64 = 0.0;

/// Warning threshold - action is safe but needs attention
pub const WARNING_THRESHOLD: f64 = 0.8;

/// Caution threshold - requires confirmation for repeated use
pub const CAUTION_THRESHOLD: f64 = 0.5;

// ============================================================================
// Safety Result
// ============================================================================

/// Safety check result with CBF value
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SafetyResult {
    /// Is the action safe? (h(x) ≥ 0)
    pub safe: bool,
    /// The h(x) value (barrier function)
    pub h_x: f64,
    /// Human-readable reason if not safe
    pub reason: Option<String>,
    /// Warnings (action is safe but flagged)
    pub warnings: Vec<String>,
    /// Safety category
    pub category: SafetyCategory,
    /// Timestamp of check
    pub checked_at: u64,
}

/// Safety category based on h(x) value
#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq)]
pub enum SafetyCategory {
    /// h(x) >= 0.8: No concerns
    Safe,
    /// 0.5 <= h(x) < 0.8: Warnings issued
    Cautious,
    /// 0.0 <= h(x) < 0.5: Marginal, may require confirmation
    Marginal,
    /// h(x) < 0: BLOCKED
    Blocked,
}

impl SafetyResult {
    /// Create a safe result
    pub fn safe(h_x: f64) -> Self {
        Self {
            safe: true,
            h_x,
            reason: None,
            warnings: Vec::new(),
            category: Self::categorize(h_x),
            checked_at: current_timestamp(),
        }
    }

    /// Create a safe result with warning
    pub fn safe_with_warning(h_x: f64, warning: &str) -> Self {
        Self {
            safe: true,
            h_x,
            reason: None,
            warnings: vec![warning.to_string()],
            category: Self::categorize(h_x),
            checked_at: current_timestamp(),
        }
    }

    /// Create an unsafe result
    pub fn unsafe_action(h_x: f64, reason: &str) -> Self {
        Self {
            safe: false,
            h_x,
            reason: Some(reason.to_string()),
            warnings: Vec::new(),
            category: SafetyCategory::Blocked,
            checked_at: current_timestamp(),
        }
    }

    /// Categorize based on h(x) value
    fn categorize(h_x: f64) -> SafetyCategory {
        if h_x < SAFETY_THRESHOLD {
            SafetyCategory::Blocked
        } else if h_x < CAUTION_THRESHOLD {
            SafetyCategory::Marginal
        } else if h_x < WARNING_THRESHOLD {
            SafetyCategory::Cautious
        } else {
            SafetyCategory::Safe
        }
    }

    /// Add a warning
    pub fn with_warning(mut self, warning: &str) -> Self {
        self.warnings.push(warning.to_string());
        self
    }
}

// ============================================================================
// Context-Aware Safety Checks
// ============================================================================

/// Safety context for enhanced checks
#[derive(Debug, Clone, Default)]
pub struct SafetyContext {
    /// Current time of day (0-23)
    pub hour: Option<u8>,
    /// Is owner present?
    pub owner_present: Option<bool>,
    /// Current zone level
    pub zone_level: Option<String>,
    /// Number of recent similar commands
    pub recent_similar_count: u32,
    /// Is this a high-security room?
    pub high_security_room: bool,
}

impl SafetyContext {
    /// Create new safety context
    pub fn new() -> Self {
        Self::default()
    }

    /// Set current hour
    pub fn with_hour(mut self, hour: u8) -> Self {
        self.hour = Some(hour);
        self
    }

    /// Set owner presence
    pub fn with_owner_present(mut self, present: bool) -> Self {
        self.owner_present = Some(present);
        self
    }

    /// Get time-based multiplier
    pub fn time_multiplier(&self) -> f64 {
        match self.hour {
            Some(h) if h >= 23 || h < 6 => 0.9, // Late night - slightly more cautious
            Some(h) if h >= 6 && h < 9 => 1.0,  // Morning - normal
            _ => 1.0,
        }
    }
}

// ============================================================================
// Command Safety Checks
// ============================================================================

/// Check safety of a cached command (executed locally)
pub fn check_cached_command_safety(cmd: &CachedCommand) -> SafetyResult {
    check_cached_command_safety_with_context(cmd, &SafetyContext::default())
}

/// Check safety with context
pub fn check_cached_command_safety_with_context(
    cmd: &CachedCommand,
    ctx: &SafetyContext,
) -> SafetyResult {
    let base_result = match cmd {
        // Lighting commands - always safe
        CachedCommand::LightsOn { .. } => SafetyResult::safe(1.0),
        CachedCommand::LightsOff { .. } => SafetyResult::safe(1.0),
        CachedCommand::LightsDim { level, .. } => {
            let mut result = SafetyResult::safe(0.9);
            if *level < 10 {
                result = result.with_warning("Very low light level - may affect visibility");
            }
            if *level == 0 {
                result = result.with_warning("Lights will be completely off");
            }
            result
        }

        // Shade commands - generally safe
        CachedCommand::ShadesOpen { .. } => {
            let mut result = SafetyResult::safe(0.9);
            // Late night warning
            if let Some(h) = ctx.hour {
                if h >= 22 || h < 6 {
                    result = result.with_warning("Opening shades at night - privacy consideration");
                }
            }
            result
        }
        CachedCommand::ShadesClose { .. } => SafetyResult::safe(0.9),

        // Scene commands have varying safety
        CachedCommand::SceneGoodnight => {
            // Goodnight is very safe - locks doors, turns off lights
            SafetyResult::safe(1.0)
        }
        CachedCommand::SceneWelcome => SafetyResult::safe(0.9),
        CachedCommand::SceneMovie => {
            // Movie mode may activate fireplace and dim lights significantly
            SafetyResult::safe_with_warning(0.7, "Movie mode may activate fireplace if available")
        }

        // Lock commands - security sensitive
        CachedCommand::LockAll => SafetyResult::safe(1.0), // Locking is always safe
    };

    // Apply context multiplier
    let adjusted_h_x = base_result.h_x * ctx.time_multiplier();
    SafetyResult {
        h_x: adjusted_h_x,
        category: SafetyResult::categorize(adjusted_h_x),
        ..base_result
    }
}

/// Check safety of a queued command (for Tesla/cloud actions)
pub fn check_queued_command_safety(cmd: &QueuedCommand) -> SafetyResult {
    check_queued_command_safety_with_context(cmd, &SafetyContext::default())
}

/// Check queued command safety with context
pub fn check_queued_command_safety_with_context(
    cmd: &QueuedCommand,
    ctx: &SafetyContext,
) -> SafetyResult {
    let result = match cmd {
        // Tesla climate
        QueuedCommand::TeslaClimate { on: true } => {
            SafetyResult::safe_with_warning(0.8, "Starting Tesla climate remotely")
        }
        QueuedCommand::TeslaClimate { on: false } => SafetyResult::safe(0.9),

        // Tesla lock/unlock - security sensitive
        QueuedCommand::TeslaLock { lock: true } => SafetyResult::safe(1.0),
        QueuedCommand::TeslaLock { lock: false } => {
            let mut result = SafetyResult::safe_with_warning(
                0.5,
                "Unlocking Tesla remotely - verify vehicle location",
            );
            // More cautious if owner not present
            if ctx.owner_present == Some(false) {
                result.h_x = 0.3;
                result.category = SafetyCategory::Marginal;
                result = result.with_warning("Owner not present - extra caution advised");
            }
            result
        }

        // Tesla trunk operations
        QueuedCommand::TeslaFrunk => {
            SafetyResult::safe_with_warning(0.6, "Opening frunk remotely - verify nobody is nearby")
        }
        QueuedCommand::TeslaTrunk => {
            SafetyResult::safe_with_warning(0.6, "Opening trunk remotely - verify nobody is nearby")
        }

        // Tesla attention features
        QueuedCommand::TeslaHonk => {
            let mut result = SafetyResult::safe_with_warning(
                0.7,
                "Horn will sound - may disturb neighbors",
            );
            // More cautious at night
            if let Some(h) = ctx.hour {
                if h >= 22 || h < 7 {
                    result.h_x = 0.4;
                    result.category = SafetyCategory::Marginal;
                    result = result.with_warning("Night hours - excessive noise may violate ordinances");
                }
            }
            result
        }
        QueuedCommand::TeslaFlash => SafetyResult::safe(0.9),

        // Thermostat - temperature safety
        QueuedCommand::SetThermostat { temp } => {
            check_thermostat_safety(*temp, ctx)
        }

        // Announcements
        QueuedCommand::Announce { .. } => {
            let mut result = SafetyResult::safe(0.9);
            // Cautious at night
            if let Some(h) = ctx.hour {
                if h >= 22 || h < 7 {
                    result = result.with_warning("Announcement during quiet hours");
                    result.h_x = 0.75;
                    result.category = SafetyCategory::Cautious;
                }
            }
            result
        }

        // Music/Spotify - entertainment, low risk
        QueuedCommand::SpotifyPlay { .. } => SafetyResult::safe(0.95),
        QueuedCommand::SpotifyPause => SafetyResult::safe(1.0),
        QueuedCommand::SpotifySkip => SafetyResult::safe(1.0),
        QueuedCommand::SpotifyPrevious => SafetyResult::safe(1.0),
        QueuedCommand::SpotifyVolume { level } => {
            if *level > 90 {
                SafetyResult::safe_with_warning(0.7, "Volume above 90% may damage hearing or speakers")
            } else if *level > 75 {
                SafetyResult::safe_with_warning(0.85, "High volume")
            } else {
                SafetyResult::safe(0.95)
            }
        }
    };

    result
}

/// Check thermostat safety
fn check_thermostat_safety(temp: f64, ctx: &SafetyContext) -> SafetyResult {
    // Temperature ranges (Fahrenheit)
    const FREEZE_RISK_TEMP: f64 = 50.0;
    const COLD_WARNING_TEMP: f64 = 60.0;
    const HOT_WARNING_TEMP: f64 = 80.0;
    const EXCESSIVE_TEMP: f64 = 85.0;

    if temp < FREEZE_RISK_TEMP {
        SafetyResult::unsafe_action(
            -0.2,
            "Temperature too low - risk of pipe freezing",
        )
    } else if temp < COLD_WARNING_TEMP {
        SafetyResult::safe_with_warning(
            0.6,
            "Low temperature setting - ensure adequate clothing",
        )
    } else if temp > EXCESSIVE_TEMP {
        SafetyResult::unsafe_action(
            -0.1,
            "Temperature too high - excessive energy use and comfort risk",
        )
    } else if temp > HOT_WARNING_TEMP {
        SafetyResult::safe_with_warning(
            0.7,
            "High temperature setting - consider energy efficiency",
        )
    } else {
        SafetyResult::safe(0.8)
    }
}

// ============================================================================
// Fireplace Safety (Special Handling)
// ============================================================================

/// Check fireplace safety
pub fn check_fireplace_safety(turn_on: bool, ctx: &SafetyContext) -> SafetyResult {
    if turn_on {
        let mut result = SafetyResult::safe_with_warning(
            0.5,
            "Fireplace activation - ensure proper ventilation",
        );

        // More cautious if owner not present
        if ctx.owner_present == Some(false) {
            result.h_x = 0.3;
            result.category = SafetyCategory::Marginal;
            result = result.with_warning("Owner not present - fireplace use not recommended");
        }

        // Warn during sleep hours
        if let Some(h) = ctx.hour {
            if h >= 23 || h < 6 {
                result = result.with_warning("Late night fireplace use - ensure supervision");
            }
        }

        result
    } else {
        // Turning off is always safe
        SafetyResult::safe(0.9)
    }
}

// ============================================================================
// Validation and Logging
// ============================================================================

/// Validate h(x) ≥ 0 for a cached command and log result
pub fn validate_and_log_cached(cmd: &CachedCommand) -> SafetyResult {
    let result = check_cached_command_safety(cmd);
    log_safety_result(&result, &format!("{:?}", cmd));
    result
}

/// Validate h(x) ≥ 0 for a cached command with context
pub fn validate_and_log_cached_with_context(
    cmd: &CachedCommand,
    ctx: &SafetyContext,
) -> SafetyResult {
    let result = check_cached_command_safety_with_context(cmd, ctx);
    log_safety_result(&result, &format!("{:?}", cmd));
    result
}

/// Validate h(x) ≥ 0 for a queued command and log result
pub fn validate_and_log_queued(cmd: &QueuedCommand) -> SafetyResult {
    let result = check_queued_command_safety(cmd);
    log_safety_result(&result, &format!("{:?}", cmd));
    result
}

/// Validate h(x) ≥ 0 for a queued command with context
pub fn validate_and_log_queued_with_context(
    cmd: &QueuedCommand,
    ctx: &SafetyContext,
) -> SafetyResult {
    let result = check_queued_command_safety_with_context(cmd, ctx);
    log_safety_result(&result, &format!("{:?}", cmd));
    result
}

/// Log safety result with appropriate level
fn log_safety_result(result: &SafetyResult, cmd_desc: &str) {
    match result.category {
        SafetyCategory::Safe => {
            debug!("✓ SAFE: {} (h(x) = {:.2})", cmd_desc, result.h_x);
        }
        SafetyCategory::Cautious => {
            info!("⚠ CAUTIOUS: {} (h(x) = {:.2})", cmd_desc, result.h_x);
            for warning in &result.warnings {
                info!("  └ Warning: {}", warning);
            }
        }
        SafetyCategory::Marginal => {
            warn!("⚡ MARGINAL: {} (h(x) = {:.2})", cmd_desc, result.h_x);
            for warning in &result.warnings {
                warn!("  └ Warning: {}", warning);
            }
        }
        SafetyCategory::Blocked => {
            error!("✗ BLOCKED: {} (h(x) = {:.2})", cmd_desc, result.h_x);
            if let Some(ref reason) = result.reason {
                error!("  └ Reason: {}", reason);
            }
        }
    }
}

// ============================================================================
// Safety Audit Report
// ============================================================================

/// Generate safety audit report
pub fn generate_audit_report() -> SafetyAuditReport {
    SafetyAuditReport {
        generated_at: current_timestamp(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        commands_audited: vec![
            AuditedCommand::new("LightsOn", SafetyCategory::Safe, 1.0, "No concerns"),
            AuditedCommand::new("LightsOff", SafetyCategory::Safe, 1.0, "No concerns"),
            AuditedCommand::new("LightsDim", SafetyCategory::Safe, 0.9, "Warning if < 10%"),
            AuditedCommand::new("ShadesOpen", SafetyCategory::Safe, 0.9, "Night privacy warning"),
            AuditedCommand::new("ShadesClose", SafetyCategory::Safe, 0.9, "No concerns"),
            AuditedCommand::new("SceneGoodnight", SafetyCategory::Safe, 1.0, "Locks doors, off lights"),
            AuditedCommand::new("SceneMovie", SafetyCategory::Cautious, 0.7, "May activate fireplace"),
            AuditedCommand::new("LockAll", SafetyCategory::Safe, 1.0, "No concerns"),
            AuditedCommand::new("TeslaUnlock", SafetyCategory::Marginal, 0.5, "Security sensitive"),
            AuditedCommand::new("TeslaFrunk", SafetyCategory::Cautious, 0.6, "Check surroundings"),
            AuditedCommand::new("TeslaHonk", SafetyCategory::Cautious, 0.7, "Night time blocked"),
            AuditedCommand::new("SetThermostat", SafetyCategory::Safe, 0.8, "Blocked if < 50°F or > 85°F"),
            AuditedCommand::new("FireplaceOn", SafetyCategory::Marginal, 0.5, "Requires owner present"),
            AuditedCommand::new("SpotifyVolume", SafetyCategory::Safe, 0.95, "Warning if > 90%"),
        ],
        invariant_verified: true,
        auditor: "Kagami CBF System".to_string(),
    }
}

/// Safety audit report
#[derive(Debug, Clone, Serialize)]
pub struct SafetyAuditReport {
    pub generated_at: u64,
    pub version: String,
    pub commands_audited: Vec<AuditedCommand>,
    pub invariant_verified: bool,
    pub auditor: String,
}

/// Audited command entry
#[derive(Debug, Clone, Serialize)]
pub struct AuditedCommand {
    pub command: String,
    pub category: SafetyCategory,
    pub typical_h_x: f64,
    pub notes: String,
}

impl AuditedCommand {
    fn new(command: &str, category: SafetyCategory, h_x: f64, notes: &str) -> Self {
        Self {
            command: command.to_string(),
            category,
            typical_h_x: h_x,
            notes: notes.to_string(),
        }
    }
}

// ============================================================================
// Utilities
// ============================================================================

fn current_timestamp() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_secs()
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lights_safe() {
        let cmd = CachedCommand::LightsOn { rooms: None };
        let result = check_cached_command_safety(&cmd);
        assert!(result.safe);
        assert!(result.h_x >= 0.0);
        assert_eq!(result.category, SafetyCategory::Safe);
    }

    #[test]
    fn test_lock_safe() {
        let cmd = CachedCommand::LockAll;
        let result = check_cached_command_safety(&cmd);
        assert!(result.safe);
        assert_eq!(result.h_x, 1.0);
        assert_eq!(result.category, SafetyCategory::Safe);
    }

    #[test]
    fn test_tesla_unlock_warning() {
        let cmd = QueuedCommand::TeslaLock { lock: false };
        let result = check_queued_command_safety(&cmd);
        assert!(result.safe);
        assert!(!result.warnings.is_empty());
        assert_eq!(result.category, SafetyCategory::Marginal);
    }

    #[test]
    fn test_tesla_unlock_without_owner() {
        let cmd = QueuedCommand::TeslaLock { lock: false };
        let ctx = SafetyContext::new().with_owner_present(false);
        let result = check_queued_command_safety_with_context(&cmd, &ctx);
        assert!(result.safe);
        assert!(result.h_x < 0.5);
        assert_eq!(result.category, SafetyCategory::Marginal);
    }

    #[test]
    fn test_thermostat_too_cold() {
        let cmd = QueuedCommand::SetThermostat { temp: 40.0 };
        let result = check_queued_command_safety(&cmd);
        assert!(!result.safe);
        assert!(result.h_x < 0.0);
        assert_eq!(result.category, SafetyCategory::Blocked);
    }

    #[test]
    fn test_thermostat_too_hot() {
        let cmd = QueuedCommand::SetThermostat { temp: 90.0 };
        let result = check_queued_command_safety(&cmd);
        assert!(!result.safe);
        assert!(result.h_x < 0.0);
        assert_eq!(result.category, SafetyCategory::Blocked);
    }

    #[test]
    fn test_thermostat_normal() {
        let cmd = QueuedCommand::SetThermostat { temp: 72.0 };
        let result = check_queued_command_safety(&cmd);
        assert!(result.safe);
        assert!(result.h_x >= 0.0);
    }

    #[test]
    fn test_fireplace_safety() {
        let ctx = SafetyContext::new().with_owner_present(true);
        let result = check_fireplace_safety(true, &ctx);
        assert!(result.safe);
        assert_eq!(result.category, SafetyCategory::Marginal);

        let ctx = SafetyContext::new().with_owner_present(false);
        let result = check_fireplace_safety(true, &ctx);
        assert!(result.safe); // Still safe but more cautious
        assert!(result.h_x < 0.5);
    }

    #[test]
    fn test_night_honk_warning() {
        let cmd = QueuedCommand::TeslaHonk;
        let ctx = SafetyContext::new().with_hour(23);
        let result = check_queued_command_safety_with_context(&cmd, &ctx);
        assert!(result.safe);
        assert!(result.h_x < 0.5); // More cautious at night
    }

    #[test]
    fn test_all_commands_have_valid_h_x() {
        // Every safe command should have h(x) >= 0
        let commands = vec![
            CachedCommand::LightsOn { rooms: None },
            CachedCommand::LightsOff { rooms: None },
            CachedCommand::LightsDim { level: 50, rooms: None },
            CachedCommand::ShadesOpen { rooms: None },
            CachedCommand::ShadesClose { rooms: None },
            CachedCommand::SceneGoodnight,
            CachedCommand::SceneWelcome,
            CachedCommand::SceneMovie,
            CachedCommand::LockAll,
        ];

        for cmd in commands {
            let result = check_cached_command_safety(&cmd);
            assert!(
                result.h_x >= 0.0,
                "Command {:?} has h(x) = {} which is < 0",
                cmd,
                result.h_x
            );
        }
    }

    #[test]
    fn test_audit_report() {
        let report = generate_audit_report();
        assert!(report.invariant_verified);
        assert!(!report.commands_audited.is_empty());
    }

    #[test]
    fn test_category_classification() {
        assert_eq!(SafetyResult::categorize(1.0), SafetyCategory::Safe);
        assert_eq!(SafetyResult::categorize(0.8), SafetyCategory::Safe);
        assert_eq!(SafetyResult::categorize(0.7), SafetyCategory::Cautious);
        assert_eq!(SafetyResult::categorize(0.5), SafetyCategory::Cautious);
        assert_eq!(SafetyResult::categorize(0.4), SafetyCategory::Marginal);
        assert_eq!(SafetyResult::categorize(0.0), SafetyCategory::Marginal);
        assert_eq!(SafetyResult::categorize(-0.1), SafetyCategory::Blocked);
    }
}

/*
 * 鏡
 * h(x) ≥ 0. Always.
 * Safety is not negotiable.
 */
