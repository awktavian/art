//! Control Barrier Function safety verification for levitation
//!
//! Implements h(x) >= 0 constraint enforcement for the levitation system.
//! The barrier function ensures the orb remains within safe operating bounds.
//!
//! # Safety Constraints
//!
//! - Height bounds: 5mm <= h <= 25mm
//! - Descent rate: <= 15 mm/s
//! - Oscillation: <= 5mm peak-to-peak
//! - Coil temperature: <= 80C
//! - Power supply: must be OK
//!
//! When h(x) approaches 0, the system takes corrective action.
//! When h(x) < 0, emergency procedures are triggered.

use super::{LevitationState, constants};

/// Safety verification result
#[derive(Debug, Clone, Copy)]
pub struct SafetyResult {
    /// Overall safety: h(x) > 0 means safe
    pub safe: bool,

    /// Safety margin (minimum h value across all constraints)
    pub margin: f32,

    /// The constraint that is most limiting
    pub limiting_constraint: SafetyCode,

    /// Individual constraint values
    pub constraints: SafetyConstraints,
}

/// Individual safety constraint values
#[derive(Debug, Clone, Copy, Default)]
pub struct SafetyConstraints {
    pub h_height_upper: f32,
    pub h_height_lower: f32,
    pub h_descent_rate: f32,
    pub h_oscillation: f32,
    pub h_thermal: f32,
    pub h_power: f32,
}

/// Safety violation codes
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SafetyCode {
    /// No violation
    None,
    /// Height too high
    HeightUpperBound,
    /// Height too low
    HeightLowerBound,
    /// Descending too fast
    DescentRate,
    /// Excessive oscillation
    Oscillation,
    /// Coil overtemperature
    Thermal,
    /// Power supply failure
    PowerFailure,
}

impl Default for SafetyCode {
    fn default() -> Self {
        Self::None
    }
}

/// Levitation safety verifier
///
/// Computes the control barrier function h(x) for the levitation state.
#[derive(Debug, Clone)]
pub struct LevitationSafetyVerifier {
    // Height bounds
    max_height_mm: f32,
    min_height_mm: f32,

    // Rate limits
    max_descent_rate_mm_s: f32,

    // Stability limits
    max_oscillation_mm: f32,

    // Thermal limits
    max_coil_temp_c: f32,
    warn_coil_temp_c: f32,
}

impl Default for LevitationSafetyVerifier {
    fn default() -> Self {
        Self {
            max_height_mm: constants::HEIGHT_MAX_MM + 5.0, // Some margin
            min_height_mm: constants::HEIGHT_MIN_MM - 2.0, // Contact threshold
            max_descent_rate_mm_s: constants::MAX_DESCENT_RATE_MM_S,
            max_oscillation_mm: constants::MAX_OSCILLATION_MM,
            max_coil_temp_c: constants::MAX_COIL_TEMP_C,
            warn_coil_temp_c: constants::WARN_COIL_TEMP_C,
        }
    }
}

impl LevitationSafetyVerifier {
    /// Create a new safety verifier with default thresholds
    pub fn new() -> Self {
        Self::default()
    }

    /// Create with custom thresholds
    pub fn with_thresholds(
        max_height: f32,
        min_height: f32,
        max_descent_rate: f32,
        max_oscillation: f32,
        max_temp: f32,
    ) -> Self {
        Self {
            max_height_mm: max_height,
            min_height_mm: min_height,
            max_descent_rate_mm_s: max_descent_rate,
            max_oscillation_mm: max_oscillation,
            max_coil_temp_c: max_temp,
            warn_coil_temp_c: max_temp - 15.0,
        }
    }

    /// Compute the control barrier function h(x) for the current state
    ///
    /// h(x) > 0: Safe operation
    /// h(x) = 0: At boundary
    /// h(x) < 0: Violation (emergency action required)
    pub fn compute_barrier(&self, state: &LevitationState) -> SafetyResult {
        let constraints = SafetyConstraints {
            h_height_upper: self.h_height_upper(state),
            h_height_lower: self.h_height_lower(state),
            h_descent_rate: self.h_descent_rate(state),
            h_oscillation: self.h_oscillation(state),
            h_thermal: self.h_thermal(state),
            h_power: self.h_power(state),
        };

        // Find minimum constraint (most limiting)
        let h_values = [
            (constraints.h_height_upper, SafetyCode::HeightUpperBound),
            (constraints.h_height_lower, SafetyCode::HeightLowerBound),
            (constraints.h_descent_rate, SafetyCode::DescentRate),
            (constraints.h_oscillation, SafetyCode::Oscillation),
            (constraints.h_thermal, SafetyCode::Thermal),
            (constraints.h_power, SafetyCode::PowerFailure),
        ];

        let (h_min, limiting) = h_values
            .iter()
            .fold((f32::MAX, SafetyCode::None), |(min_h, min_code), &(h, code)| {
                if h < min_h {
                    (h, code)
                } else {
                    (min_h, min_code)
                }
            });

        SafetyResult {
            safe: h_min > 0.0,
            margin: h_min,
            limiting_constraint: limiting,
            constraints,
        }
    }

    /// Check if state is safe (h(x) > 0)
    pub fn is_safe(&self, state: &LevitationState) -> bool {
        self.compute_barrier(state).safe
    }

    /// Get safety margin (minimum h value)
    pub fn safety_margin(&self, state: &LevitationState) -> f32 {
        self.compute_barrier(state).margin
    }

    // Individual constraint functions
    // All return values where:
    //   h > 1.0: Well within safe zone
    //   0 < h < 1.0: Approaching limit
    //   h <= 0: Violation

    fn h_height_upper(&self, state: &LevitationState) -> f32 {
        // Normalized distance from upper bound
        // h = 1.0 at 10mm below max, h = 0 at max
        (self.max_height_mm - state.height_mm) / 10.0
    }

    fn h_height_lower(&self, state: &LevitationState) -> f32 {
        // Normalized distance from lower bound
        // h = 1.0 at 5mm above min, h = 0 at min
        (state.height_mm - self.min_height_mm) / 5.0
    }

    fn h_descent_rate(&self, state: &LevitationState) -> f32 {
        if state.velocity_mm_s >= 0.0 {
            // Rising or stationary: safe
            1.0
        } else {
            // Descending: check rate
            let descent = -state.velocity_mm_s;
            (self.max_descent_rate_mm_s - descent) / self.max_descent_rate_mm_s
        }
    }

    fn h_oscillation(&self, state: &LevitationState) -> f32 {
        (self.max_oscillation_mm - state.oscillation_amplitude_mm) / self.max_oscillation_mm
    }

    fn h_thermal(&self, state: &LevitationState) -> f32 {
        let temp = state.electromagnet_temp_c.max(state.wpt_coil_temp_c);

        if temp < self.warn_coil_temp_c {
            // Below warning: fully safe
            1.0
        } else if temp >= self.max_coil_temp_c {
            // At or above max: violation
            -1.0
        } else {
            // Linear interpolation in warning zone
            (self.max_coil_temp_c - temp) / (self.max_coil_temp_c - self.warn_coil_temp_c)
        }
    }

    fn h_power(&self, state: &LevitationState) -> f32 {
        if state.power_supply_ok {
            1.0
        } else {
            -1.0 // Immediate violation
        }
    }

    /// Compute corrective action based on safety state
    ///
    /// Returns a recommended height adjustment rate (mm/s)
    /// Positive = rise, Negative = controlled descent
    pub fn corrective_action(&self, result: &SafetyResult) -> f32 {
        if result.safe && result.margin > 0.5 {
            // Well within safe zone: no correction needed
            return 0.0;
        }

        match result.limiting_constraint {
            SafetyCode::HeightUpperBound => {
                // Too high: descend
                -5.0 * (1.0 - result.margin.max(0.0))
            }
            SafetyCode::HeightLowerBound => {
                // Too low: rise
                5.0 * (1.0 - result.margin.max(0.0))
            }
            SafetyCode::DescentRate => {
                // Descending too fast: slow down
                3.0 // Add upward correction
            }
            SafetyCode::Oscillation => {
                // Unstable: try to dampen (complex, may need mode change)
                0.0
            }
            SafetyCode::Thermal => {
                // Hot: rise to reduce WPT coupling
                if result.margin < 0.0 {
                    10.0 // Emergency rise
                } else {
                    3.0 * (1.0 - result.margin)
                }
            }
            SafetyCode::PowerFailure => {
                // Power failure: passive landing (no active control possible)
                0.0
            }
            SafetyCode::None => 0.0,
        }
    }
}

/// Safety interlock manager
///
/// Maintains state across multiple control cycles to detect trends
/// and prevent oscillation in safety response.
#[derive(Debug, Default)]
pub struct SafetyInterlockManager {
    /// Number of consecutive safe cycles
    safe_cycles: u32,

    /// Number of consecutive violation cycles
    violation_cycles: u32,

    /// Last recorded margin
    last_margin: f32,

    /// Emergency landing in progress
    emergency_active: bool,

    /// Lockout until manual reset
    lockout: bool,
}

impl SafetyInterlockManager {
    /// Create a new interlock manager
    pub fn new() -> Self {
        Self::default()
    }

    /// Update with new safety result
    ///
    /// Returns true if emergency action should be taken
    pub fn update(&mut self, result: &SafetyResult) -> bool {
        if result.safe {
            self.safe_cycles += 1;
            self.violation_cycles = 0;

            // Clear emergency after 100 safe cycles (1 second at 100Hz)
            if self.safe_cycles > 100 && !self.lockout {
                self.emergency_active = false;
            }
        } else {
            self.violation_cycles += 1;
            self.safe_cycles = 0;

            // Trigger emergency after 5 consecutive violations (50ms)
            if self.violation_cycles >= 5 {
                self.emergency_active = true;
            }
        }

        self.last_margin = result.margin;
        self.emergency_active
    }

    /// Check if emergency landing is active
    pub fn is_emergency(&self) -> bool {
        self.emergency_active
    }

    /// Check if system is locked out
    pub fn is_locked_out(&self) -> bool {
        self.lockout
    }

    /// Trigger lockout (requires manual reset)
    pub fn trigger_lockout(&mut self) {
        self.lockout = true;
        self.emergency_active = true;
    }

    /// Manual reset (for maintenance)
    pub fn reset(&mut self) {
        self.lockout = false;
        self.emergency_active = false;
        self.safe_cycles = 0;
        self.violation_cycles = 0;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_safe_state() -> LevitationState {
        LevitationState {
            height_mm: 15.0,
            velocity_mm_s: 0.0,
            oscillation_amplitude_mm: 1.0,
            electromagnet_temp_c: 50.0,
            wpt_coil_temp_c: 45.0,
            power_supply_ok: true,
            mode: super::super::LevitationMode::Float { height_mm: 15.0 },
            orb_present: true,
            stable: true,
        }
    }

    #[test]
    fn test_safe_state() {
        let verifier = LevitationSafetyVerifier::new();
        let state = make_safe_state();

        let result = verifier.compute_barrier(&state);
        assert!(result.safe);
        assert!(result.margin > 0.5);
    }

    #[test]
    fn test_height_violation() {
        let verifier = LevitationSafetyVerifier::new();
        let mut state = make_safe_state();

        // Too high
        state.height_mm = 32.0;
        let result = verifier.compute_barrier(&state);
        assert!(!result.safe);
        assert_eq!(result.limiting_constraint, SafetyCode::HeightUpperBound);

        // Too low
        state.height_mm = 2.0;
        let result = verifier.compute_barrier(&state);
        assert!(!result.safe);
        assert_eq!(result.limiting_constraint, SafetyCode::HeightLowerBound);
    }

    #[test]
    fn test_thermal_warning() {
        let verifier = LevitationSafetyVerifier::new();
        let mut state = make_safe_state();

        // In warning zone
        state.electromagnet_temp_c = 70.0;
        let result = verifier.compute_barrier(&state);
        assert!(result.safe);
        assert!(result.margin < 1.0);

        // Over limit
        state.electromagnet_temp_c = 85.0;
        let result = verifier.compute_barrier(&state);
        assert!(!result.safe);
        assert_eq!(result.limiting_constraint, SafetyCode::Thermal);
    }

    #[test]
    fn test_power_failure() {
        let verifier = LevitationSafetyVerifier::new();
        let mut state = make_safe_state();

        state.power_supply_ok = false;
        let result = verifier.compute_barrier(&state);
        assert!(!result.safe);
        assert_eq!(result.limiting_constraint, SafetyCode::PowerFailure);
    }

    #[test]
    fn test_interlock_manager() {
        let mut manager = SafetyInterlockManager::new();
        let verifier = LevitationSafetyVerifier::new();
        let mut state = make_safe_state();

        // Safe state should not trigger emergency
        for _ in 0..10 {
            let result = verifier.compute_barrier(&state);
            assert!(!manager.update(&result));
        }
        assert!(!manager.is_emergency());

        // Violation should trigger after 5 cycles
        state.height_mm = 35.0;
        for i in 0..10 {
            let result = verifier.compute_barrier(&state);
            let emergency = manager.update(&result);
            if i >= 4 {
                assert!(emergency);
            }
        }
        assert!(manager.is_emergency());
    }
}
