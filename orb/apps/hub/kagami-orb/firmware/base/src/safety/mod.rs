//! Unified Safety Coordinator
//!
//! Coordinates safety across levitation and PTZ systems.
//! Ensures h(x) >= 0 for the entire system, not just individual subsystems.
//!
//! # Philosophy
//!
//! h_unified(x) = min(h_levitation(x), h_ptz(x))
//!
//! If EITHER subsystem violates its barrier, BOTH subsystems go to emergency.
//! This prevents scenarios where one system continues operating while the other
//! is in an unsafe state.

use crate::levitation::{LevitationState, LevitationSafetyVerifier, SafetyInterlockManager};
use crate::ptz::{PtzSafetyResult, PtzSafetyVerifier, PtzSafetyState, SensorFault};

/// Unified safety result
#[derive(Debug, Clone)]
pub enum UnifiedSafetyResult {
    /// All systems safe
    Safe {
        h_levitation: f32,
        h_ptz: f32,
        h_unified: f32,
    },
    /// Sensor validation failed - cannot compute barriers
    SensorFault(SensorFault),
    /// One or more barriers violated - emergency mode active
    Emergency {
        levitation_safe: bool,
        ptz_safe: bool,
        trigger: EmergencyTrigger,
    },
}

/// What triggered the emergency
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum EmergencyTrigger {
    /// Levitation barrier violated
    LevitationUnsafe,
    /// PTZ barrier violated
    PtzUnsafe,
    /// Both barriers violated
    BothUnsafe,
    /// Sensor fault detected
    SensorFault,
    /// Manual emergency trigger
    Manual,
}

/// Unified Safety Coordinator
///
/// Single source of truth for emergency state across all subsystems.
pub struct UnifiedSafetyCoordinator {
    /// Levitation safety verifier
    levitation_safety: LevitationSafetyVerifier,
    /// PTZ safety verifier
    ptz_safety: PtzSafetyVerifier,
    /// Safety interlock manager (shared)
    interlock: SafetyInterlockManager,
    /// Emergency state
    emergency_active: bool,
    /// What triggered emergency (if any)
    emergency_trigger: Option<EmergencyTrigger>,
    /// Last computed barrier values
    last_h_levitation: f32,
    last_h_ptz: f32,
    /// Control loop dt for sensor validation
    dt: f32,
}

impl UnifiedSafetyCoordinator {
    /// Create a new unified safety coordinator
    pub fn new() -> Self {
        Self {
            levitation_safety: LevitationSafetyVerifier::new(),
            ptz_safety: PtzSafetyVerifier::new(),
            interlock: SafetyInterlockManager::new(),
            emergency_active: false,
            emergency_trigger: None,
            last_h_levitation: 1.0,
            last_h_ptz: 1.0,
            dt: 0.002, // 500Hz default
        }
    }

    /// Set control loop period
    pub fn set_dt(&mut self, dt: f32) {
        self.dt = dt;
    }

    /// Check all safety barriers
    ///
    /// This is the main entry point - call at control loop rate.
    pub fn check_all(
        &mut self,
        lev_state: &LevitationState,
        ptz_state: &PtzSafetyState,
    ) -> UnifiedSafetyResult {
        // If already in emergency, stay in emergency until reset
        if self.emergency_active {
            return UnifiedSafetyResult::Emergency {
                levitation_safe: false,
                ptz_safe: false,
                trigger: self.emergency_trigger.unwrap_or(EmergencyTrigger::Manual),
            };
        }

        // Validate sensors first
        if let Err(fault) = self.ptz_safety.validate_sensors(ptz_state, self.dt) {
            self.trigger_emergency(EmergencyTrigger::SensorFault);
            return UnifiedSafetyResult::SensorFault(fault);
        }

        // Compute individual barriers
        let lev_result = self.levitation_safety.compute_barrier(lev_state);
        let ptz_result = self.ptz_safety.compute_barrier(ptz_state);

        // Extract barrier values
        let h_lev = if lev_result.safe { lev_result.h_combined } else { -1.0 };
        let h_ptz = ptz_result.h_ptz;

        // Store for diagnostics
        self.last_h_levitation = h_lev;
        self.last_h_ptz = h_ptz;

        // Unified barrier
        let h_unified = h_lev.min(h_ptz);

        // Check for violations
        let lev_safe = h_lev >= 0.0;
        let ptz_safe = h_ptz >= 0.0;

        if !lev_safe && !ptz_safe {
            self.trigger_emergency(EmergencyTrigger::BothUnsafe);
            return UnifiedSafetyResult::Emergency {
                levitation_safe: false,
                ptz_safe: false,
                trigger: EmergencyTrigger::BothUnsafe,
            };
        }

        if !lev_safe {
            self.trigger_emergency(EmergencyTrigger::LevitationUnsafe);
            return UnifiedSafetyResult::Emergency {
                levitation_safe: false,
                ptz_safe: true,
                trigger: EmergencyTrigger::LevitationUnsafe,
            };
        }

        if !ptz_safe {
            self.trigger_emergency(EmergencyTrigger::PtzUnsafe);
            return UnifiedSafetyResult::Emergency {
                levitation_safe: true,
                ptz_safe: false,
                trigger: EmergencyTrigger::PtzUnsafe,
            };
        }

        // All safe
        UnifiedSafetyResult::Safe {
            h_levitation: h_lev,
            h_ptz,
            h_unified,
        }
    }

    /// Trigger emergency mode
    fn trigger_emergency(&mut self, trigger: EmergencyTrigger) {
        self.emergency_active = true;
        self.emergency_trigger = Some(trigger);
        self.interlock.trigger_lockout();
    }

    /// Manual emergency trigger
    pub fn emergency_stop(&mut self) {
        self.trigger_emergency(EmergencyTrigger::Manual);
    }

    /// Check if emergency is active
    pub fn is_emergency(&self) -> bool {
        self.emergency_active
    }

    /// Get emergency trigger reason
    pub fn emergency_trigger(&self) -> Option<EmergencyTrigger> {
        self.emergency_trigger
    }

    /// Reset from emergency (requires manual intervention)
    pub fn reset(&mut self) -> bool {
        // Only allow reset if interlock allows it
        if self.interlock.can_reset() {
            self.emergency_active = false;
            self.emergency_trigger = None;
            self.interlock.reset();
            self.ptz_safety.sensor_validator.reset();
            true
        } else {
            false
        }
    }

    /// Get last computed levitation barrier
    pub fn h_levitation(&self) -> f32 {
        self.last_h_levitation
    }

    /// Get last computed PTZ barrier
    pub fn h_ptz(&self) -> f32 {
        self.last_h_ptz
    }

    /// Get unified barrier (minimum of all)
    pub fn h_unified(&self) -> f32 {
        self.last_h_levitation.min(self.last_h_ptz)
    }

    /// Get reference to levitation safety verifier
    pub fn levitation_safety(&self) -> &LevitationSafetyVerifier {
        &self.levitation_safety
    }

    /// Get mutable reference to levitation safety verifier
    pub fn levitation_safety_mut(&mut self) -> &mut LevitationSafetyVerifier {
        &mut self.levitation_safety
    }

    /// Get reference to PTZ safety verifier
    pub fn ptz_safety(&self) -> &PtzSafetyVerifier {
        &self.ptz_safety
    }

    /// Get mutable reference to PTZ safety verifier
    pub fn ptz_safety_mut(&mut self) -> &mut PtzSafetyVerifier {
        &mut self.ptz_safety
    }
}

impl Default for UnifiedSafetyCoordinator {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::ptz::Orientation;

    fn make_safe_lev_state() -> LevitationState {
        LevitationState {
            height_mm: 15.0,
            velocity_mm_s: 0.0,
            oscillation_amplitude_mm: 0.5,
            electromagnet_temp_c: 45.0,
            wpt_coil_temp_c: 35.0,
            power_supply_ok: true,
            stable: true,
            mode: crate::levitation::LevitationMode::Float { height_mm: 15.0 },
        }
    }

    fn make_safe_ptz_state() -> PtzSafetyState {
        PtzSafetyState {
            orientation: Orientation::level(),
            coil_temp_c: 45.0,
            levitation_height_mm: 15.0,
            coil_currents: [1.0; 8],
        }
    }

    #[test]
    fn test_all_safe() {
        let mut coordinator = UnifiedSafetyCoordinator::new();
        let lev = make_safe_lev_state();
        let ptz = make_safe_ptz_state();

        match coordinator.check_all(&lev, &ptz) {
            UnifiedSafetyResult::Safe { h_unified, .. } => {
                assert!(h_unified >= 0.0);
            }
            _ => panic!("Expected safe result"),
        }

        assert!(!coordinator.is_emergency());
    }

    #[test]
    fn test_ptz_unsafe_triggers_emergency() {
        let mut coordinator = UnifiedSafetyCoordinator::new();
        let lev = make_safe_lev_state();
        let mut ptz = make_safe_ptz_state();

        // Over tilt limit
        ptz.orientation.pitch = 25.0;

        match coordinator.check_all(&lev, &ptz) {
            UnifiedSafetyResult::Emergency { trigger, .. } => {
                assert_eq!(trigger, EmergencyTrigger::PtzUnsafe);
            }
            _ => panic!("Expected emergency"),
        }

        assert!(coordinator.is_emergency());
    }

    #[test]
    fn test_sensor_fault_triggers_emergency() {
        let mut coordinator = UnifiedSafetyCoordinator::new();
        let lev = make_safe_lev_state();
        let mut ptz = make_safe_ptz_state();

        // NaN in sensor reading
        ptz.orientation.pitch = f32::NAN;

        match coordinator.check_all(&lev, &ptz) {
            UnifiedSafetyResult::SensorFault(SensorFault::InvalidValue) => {}
            _ => panic!("Expected sensor fault"),
        }

        assert!(coordinator.is_emergency());
    }

    #[test]
    fn test_emergency_persists_until_reset() {
        let mut coordinator = UnifiedSafetyCoordinator::new();
        let lev = make_safe_lev_state();
        let ptz = make_safe_ptz_state();

        // Trigger emergency manually
        coordinator.emergency_stop();

        // Even with safe state, remains in emergency
        match coordinator.check_all(&lev, &ptz) {
            UnifiedSafetyResult::Emergency { trigger, .. } => {
                assert_eq!(trigger, EmergencyTrigger::Manual);
            }
            _ => panic!("Should remain in emergency"),
        }
    }
}
