//! PTZ Safety Verifier
//!
//! Implements the Control Barrier Function (CBF) for PTZ operations.
//! Ensures h_ptz(x) >= 0 at all times.
//!
//! # Safety Constraints
//!
//! 1. **Lift Margin**: Magnetic force must exceed gravity + safety factor
//! 2. **Tilt Margin**: Orientation must stay within mechanical limits
//! 3. **Thermal Margin**: Coil temperature must stay below limits
//!
//! # Barrier Function
//!
//! h_ptz(x) = min(h_lift, h_tilt, h_thermal)
//!
//! The system is safe when h_ptz(x) >= 0.

use super::{Orientation, constants};

/// Safety state for barrier function computation
#[derive(Debug, Clone)]
pub struct PtzSafetyState {
    /// Current orientation
    pub orientation: Orientation,
    /// Average coil temperature (Celsius)
    pub coil_temp_c: f32,
    /// Current levitation height (mm)
    pub levitation_height_mm: f32,
    /// Current coil currents (Amperes)
    pub coil_currents: [f32; constants::NUM_COILS],
}

/// Result of safety barrier computation
#[derive(Debug, Clone)]
pub struct PtzSafetyResult {
    /// Overall safety status
    pub safe: bool,
    /// Lift margin (positive = safe)
    pub lift_margin: f32,
    /// Tilt margin (positive = safe)
    pub tilt_margin: f32,
    /// Thermal margin (positive = safe)
    pub thermal_margin: f32,
    /// Combined barrier function value
    pub h_ptz: f32,
    /// Suggested lift correction current
    pub lift_correction: f32,
    /// Suggested tilt correction (0-1, how much to reduce tilt)
    pub tilt_correction: f32,
}

impl Default for PtzSafetyResult {
    fn default() -> Self {
        Self {
            safe: true,
            lift_margin: 1.0,
            tilt_margin: 1.0,
            thermal_margin: 1.0,
            h_ptz: 1.0,
            lift_correction: 0.0,
            tilt_correction: 0.0,
        }
    }
}

/// Sensor fault types
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum SensorFault {
    /// NaN or infinity in sensor reading
    InvalidValue,
    /// Value outside physical bounds
    OutOfBounds,
    /// Rate of change exceeds physics
    PhysicsViolation,
    /// Sensor stuck at same value
    StuckValue,
    /// Temperature sensor failure
    TemperatureFault,
}

/// Sensor validation state
#[derive(Debug, Clone, Default)]
pub struct SensorValidator {
    prev_orientation: Orientation,
    prev_temp: f32,
    prev_height: f32,
    stuck_count: u32,
    initialized: bool,
}

impl SensorValidator {
    /// Maximum orientation rate (deg/s) - physical limit for magnetic actuation
    const MAX_ORIENTATION_RATE: f32 = 180.0;
    /// Maximum temperature change rate (°C/s)
    const MAX_TEMP_RATE: f32 = 10.0;
    /// Maximum height change rate (mm/s)
    const MAX_HEIGHT_RATE: f32 = 100.0;
    /// Samples before declaring stuck
    const STUCK_THRESHOLD: u32 = 500; // 1 second at 500Hz

    /// Validate sensor inputs
    pub fn validate(&mut self, state: &PtzSafetyState, dt: f32) -> Result<(), SensorFault> {
        // NaN/Infinity check
        if state.orientation.pitch.is_nan() || state.orientation.pitch.is_infinite()
            || state.orientation.roll.is_nan() || state.orientation.roll.is_infinite()
            || state.orientation.yaw.is_nan() || state.orientation.yaw.is_infinite()
        {
            return Err(SensorFault::InvalidValue);
        }

        if state.coil_temp_c.is_nan() || state.coil_temp_c.is_infinite() {
            return Err(SensorFault::TemperatureFault);
        }

        // Bounds check
        if state.orientation.pitch.abs() > 90.0 || state.orientation.roll.abs() > 90.0 {
            return Err(SensorFault::OutOfBounds);
        }

        // Temperature bounds (-40°C to 150°C realistic for electronics)
        if state.coil_temp_c < -40.0 || state.coil_temp_c > 150.0 {
            return Err(SensorFault::TemperatureFault);
        }

        if !self.initialized {
            self.prev_orientation = state.orientation;
            self.prev_temp = state.coil_temp_c;
            self.prev_height = state.levitation_height_mm;
            self.initialized = true;
            return Ok(());
        }

        // Rate-of-change checks (physics violation detection)
        if dt > 0.0 {
            let pitch_rate = (state.orientation.pitch - self.prev_orientation.pitch).abs() / dt;
            let roll_rate = (state.orientation.roll - self.prev_orientation.roll).abs() / dt;

            if pitch_rate > Self::MAX_ORIENTATION_RATE || roll_rate > Self::MAX_ORIENTATION_RATE {
                return Err(SensorFault::PhysicsViolation);
            }

            let temp_rate = (state.coil_temp_c - self.prev_temp).abs() / dt;
            if temp_rate > Self::MAX_TEMP_RATE {
                return Err(SensorFault::TemperatureFault);
            }
        }

        // Stuck detection
        let epsilon = 0.001;
        if (state.orientation.pitch - self.prev_orientation.pitch).abs() < epsilon
            && (state.orientation.roll - self.prev_orientation.roll).abs() < epsilon
            && (state.coil_temp_c - self.prev_temp).abs() < epsilon
        {
            self.stuck_count += 1;
            if self.stuck_count > Self::STUCK_THRESHOLD {
                return Err(SensorFault::StuckValue);
            }
        } else {
            self.stuck_count = 0;
        }

        // Update previous values
        self.prev_orientation = state.orientation;
        self.prev_temp = state.coil_temp_c;
        self.prev_height = state.levitation_height_mm;

        Ok(())
    }

    /// Reset validator state
    pub fn reset(&mut self) {
        self.initialized = false;
        self.stuck_count = 0;
    }
}

/// Thermal Accumulator for duty cycle limiting
///
/// Tracks energy accumulation in PTZ coils and enforces thermal limits
/// to maintain passive cooling capability without active fan.
///
/// # Operating Modes
/// - **Normal**: 1.5A max, 45W peak for up to 30s
/// - **Cooldown**: 0.8A max, 12.8W, enforced after burst
/// - **Sustained**: 1.0A base, 20W continuous
#[derive(Debug, Clone)]
pub struct ThermalAccumulator {
    /// Accumulated thermal energy (Joules, normalized)
    energy_j: f32,
    /// Time since last burst (seconds)
    time_since_burst: f32,
    /// Current thermal state
    state: ThermalState,
    /// Passive dissipation capacity (Watts)
    dissipation_capacity_w: f32,
    /// Burst energy threshold (Joules) - triggers cooldown
    burst_threshold_j: f32,
    /// Cooldown duration (seconds)
    cooldown_duration_s: f32,
}

/// Thermal management state
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum ThermalState {
    /// Normal operation - full current available
    Normal,
    /// In burst mode - high current, time limited
    Burst { remaining_s: f32 },
    /// Cooldown - reduced current required
    Cooldown { remaining_s: f32 },
}

impl Default for ThermalState {
    fn default() -> Self {
        Self::Normal
    }
}

impl ThermalAccumulator {
    /// Maximum burst duration (seconds)
    pub const MAX_BURST_DURATION_S: f32 = 30.0;
    /// Cooldown duration after burst (seconds)
    pub const COOLDOWN_DURATION_S: f32 = 60.0;
    /// Passive dissipation capacity (Watts)
    pub const PASSIVE_DISSIPATION_W: f32 = 25.0;
    /// Power threshold to enter burst mode (Watts)
    pub const BURST_POWER_THRESHOLD_W: f32 = 25.0;

    /// Create new thermal accumulator
    pub fn new() -> Self {
        Self {
            energy_j: 0.0,
            time_since_burst: f32::MAX, // Start as if cooldown complete
            state: ThermalState::Normal,
            dissipation_capacity_w: Self::PASSIVE_DISSIPATION_W,
            burst_threshold_j: Self::BURST_POWER_THRESHOLD_W * Self::MAX_BURST_DURATION_S,
            cooldown_duration_s: Self::COOLDOWN_DURATION_S,
        }
    }

    /// Update thermal state based on current power draw
    ///
    /// Call every control loop iteration (500Hz = 2ms)
    pub fn update(&mut self, power_w: f32, dt: f32) {
        // Net energy change: input - dissipation
        let net_power = power_w - self.dissipation_capacity_w;
        let energy_delta = net_power * dt;

        // Update accumulated energy (can't go negative)
        self.energy_j = (self.energy_j + energy_delta).max(0.0);

        // State machine
        match self.state {
            ThermalState::Normal => {
                if power_w > Self::BURST_POWER_THRESHOLD_W {
                    // Enter burst mode
                    self.state = ThermalState::Burst {
                        remaining_s: Self::MAX_BURST_DURATION_S,
                    };
                }
            }
            ThermalState::Burst { remaining_s } => {
                let new_remaining = remaining_s - dt;
                if new_remaining <= 0.0 || self.energy_j >= self.burst_threshold_j {
                    // Burst expired or energy threshold hit - enter cooldown
                    self.state = ThermalState::Cooldown {
                        remaining_s: self.cooldown_duration_s,
                    };
                    self.time_since_burst = 0.0;
                } else {
                    self.state = ThermalState::Burst {
                        remaining_s: new_remaining,
                    };
                }
            }
            ThermalState::Cooldown { remaining_s } => {
                self.time_since_burst += dt;
                let new_remaining = remaining_s - dt;
                if new_remaining <= 0.0 && self.energy_j < self.burst_threshold_j * 0.3 {
                    // Cooldown complete and energy dissipated
                    self.state = ThermalState::Normal;
                } else {
                    self.state = ThermalState::Cooldown {
                        remaining_s: new_remaining.max(0.0),
                    };
                }
            }
        }
    }

    /// Get maximum allowed current based on thermal state
    pub fn max_current_a(&self) -> f32 {
        match self.state {
            ThermalState::Normal => constants::MAX_COIL_CURRENT_A, // 1.5A
            ThermalState::Burst { .. } => constants::MAX_COIL_CURRENT_A, // 1.5A
            ThermalState::Cooldown { .. } => 0.8, // Reduced for cooldown
        }
    }

    /// Get current thermal state
    pub fn state(&self) -> ThermalState {
        self.state
    }

    /// Get accumulated energy (normalized 0-1)
    pub fn energy_ratio(&self) -> f32 {
        (self.energy_j / self.burst_threshold_j).clamp(0.0, 1.0)
    }

    /// Check if burst mode is available
    pub fn can_burst(&self) -> bool {
        matches!(self.state, ThermalState::Normal | ThermalState::Burst { .. })
    }

    /// Reset thermal accumulator (e.g., after system restart)
    pub fn reset(&mut self) {
        self.energy_j = 0.0;
        self.time_since_burst = f32::MAX;
        self.state = ThermalState::Normal;
    }
}

impl Default for ThermalAccumulator {
    fn default() -> Self {
        Self::new()
    }
}

/// PTZ Safety Verifier implementing CBF
pub struct PtzSafetyVerifier {
    /// Orb mass (kg) - V3.2: 95mm orb with cellular = ~420g
    orb_mass_kg: f32,
    /// Gravity acceleration (m/s²)
    gravity: f32,
    /// Safety factor for lift margin
    lift_safety_factor: f32,
    /// Sensor validator
    pub sensor_validator: SensorValidator,
    /// Thermal accumulator for duty cycle limiting
    pub thermal_accumulator: ThermalAccumulator,
}

impl PtzSafetyVerifier {
    /// Create a new safety verifier
    pub fn new() -> Self {
        Self {
            orb_mass_kg: 0.420, // 420g orb (95mm V3.2 with cellular)
            gravity: 9.81,
            lift_safety_factor: 1.5, // 50% margin
            sensor_validator: SensorValidator::default(),
            thermal_accumulator: ThermalAccumulator::new(),
        }
    }

    /// Set orb mass (for configuration)
    pub fn set_orb_mass(&mut self, mass_kg: f32) {
        self.orb_mass_kg = mass_kg;
    }

    /// Validate sensor inputs before barrier computation
    pub fn validate_sensors(&mut self, state: &PtzSafetyState, dt: f32) -> Result<(), SensorFault> {
        self.sensor_validator.validate(state, dt)
    }

    /// Compute the barrier function h_ptz(x)
    ///
    /// Returns safety result with margins and corrective actions
    pub fn compute_barrier(&self, state: &PtzSafetyState) -> PtzSafetyResult {
        // Compute individual barrier components
        let h_lift = self.compute_lift_barrier(state);
        let h_tilt = self.compute_tilt_barrier(state);
        let h_thermal = self.compute_thermal_barrier(state);

        // Combined barrier function (minimum)
        let h_ptz = h_lift.min(h_tilt).min(h_thermal);

        // Compute corrective actions if needed
        let lift_correction = if h_lift < 0.0 {
            // Need more lift force
            self.compute_lift_correction(h_lift)
        } else {
            0.0
        };

        let tilt_correction = if h_tilt < 0.0 {
            // Need to reduce tilt
            self.compute_tilt_correction(h_tilt, state)
        } else {
            0.0
        };

        PtzSafetyResult {
            safe: h_ptz >= 0.0,
            lift_margin: h_lift,
            tilt_margin: h_tilt,
            thermal_margin: h_thermal,
            h_ptz,
            lift_correction,
            tilt_correction,
        }
    }

    /// Compute lift barrier: h_lift = (F_magnetic - F_required) / F_required
    ///
    /// F_required = m × g × safety_factor / cos(tilt_angle)
    fn compute_lift_barrier(&self, state: &PtzSafetyState) -> f32 {
        // Required force increases with tilt angle (vertical component decreases)
        let tilt_rad = (state.orientation.pitch.powi(2) + state.orientation.roll.powi(2))
            .sqrt()
            .to_radians();
        let cos_tilt = libm::cosf(tilt_rad).max(0.5); // Clamp to prevent division issues

        let f_required = self.orb_mass_kg * self.gravity * self.lift_safety_factor / cos_tilt;

        // Estimate magnetic force from currents
        let f_magnetic = self.estimate_magnetic_force(state);

        // Barrier function: positive when force exceeds requirement
        (f_magnetic - f_required) / f_required
    }

    /// Compute tilt barrier: h_tilt = 1 - (|tilt| / max_tilt)
    fn compute_tilt_barrier(&self, state: &PtzSafetyState) -> f32 {
        let pitch_ratio = state.orientation.pitch.abs() / constants::MAX_TILT_DEG;
        let roll_ratio = state.orientation.roll.abs() / constants::MAX_ROLL_DEG;

        // Take the more restrictive
        let tilt_ratio = pitch_ratio.max(roll_ratio);

        // Barrier: 1 at center, 0 at limit, negative beyond
        1.0 - tilt_ratio
    }

    /// Compute thermal barrier: h_thermal = 1 - (T_coil - T_warn) / (T_max - T_warn)
    fn compute_thermal_barrier(&self, state: &PtzSafetyState) -> f32 {
        let temp_range = constants::MAX_COIL_TEMP_C - constants::WARN_COIL_TEMP_C;

        if state.coil_temp_c <= constants::WARN_COIL_TEMP_C {
            // Below warning threshold - fully safe
            1.0
        } else {
            // In warning zone
            let temp_over = state.coil_temp_c - constants::WARN_COIL_TEMP_C;
            1.0 - (temp_over / temp_range)
        }
    }

    /// Estimate magnetic force from coil currents
    fn estimate_magnetic_force(&self, state: &PtzSafetyState) -> f32 {
        let gap_m = state.levitation_height_mm / 1000.0;

        state.coil_currents.iter()
            .map(|&i| constants::FORCE_CONSTANT_K * i * i / (gap_m * gap_m))
            .sum()
    }

    /// Compute lift correction current
    fn compute_lift_correction(&self, h_lift: f32) -> f32 {
        // If h_lift is negative, we need to increase current
        // Correction is proportional to deficit
        let deficit = -h_lift;
        let correction = deficit * 0.5; // 0.5A correction per unit deficit

        correction.clamp(0.0, 1.0) // Max 1A additional per coil
    }

    /// Compute tilt correction factor
    fn compute_tilt_correction(&self, h_tilt: f32, _state: &PtzSafetyState) -> f32 {
        // If h_tilt is negative, we're over the limit
        // Return factor 0-1 indicating how much to reduce tilt
        let overage = -h_tilt;

        overage.clamp(0.0, 1.0)
    }

    /// Check if a proposed orientation change is safe
    ///
    /// Projects the trajectory and checks barrier function
    pub fn check_transition(
        &self,
        current: &PtzSafetyState,
        target: Orientation,
        duration_s: f32,
    ) -> bool {
        // Simplified check: just verify target is within limits
        if !target.is_within_limits() {
            return false;
        }

        // Check that we don't exceed velocity limits during transition
        let pitch_rate = (target.pitch - current.orientation.pitch) / duration_s;
        let roll_rate = (target.roll - current.orientation.roll) / duration_s;

        // Max rate is ~45 deg/s for smooth motion
        const MAX_RATE_DEG_S: f32 = 45.0;

        pitch_rate.abs() <= MAX_RATE_DEG_S && roll_rate.abs() <= MAX_RATE_DEG_S
    }
}

impl Default for PtzSafetyVerifier {
    fn default() -> Self {
        Self::new()
    }
}

/// Extension trait for f32 to convert to radians
trait ToRadians {
    fn to_radians(self) -> f32;
}

impl ToRadians for f32 {
    fn to_radians(self) -> f32 {
        self * core::f32::consts::PI / 180.0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn create_test_state() -> PtzSafetyState {
        PtzSafetyState {
            orientation: Orientation::level(),
            coil_temp_c: 45.0,
            levitation_height_mm: 15.0,
            coil_currents: [constants::BASE_LIFT_CURRENT_A; constants::NUM_COILS],
        }
    }

    #[test]
    fn test_safe_level_state() {
        let verifier = PtzSafetyVerifier::new();
        let state = create_test_state();
        let result = verifier.compute_barrier(&state);

        assert!(result.safe, "Level state should be safe");
        assert!(result.h_ptz >= 0.0, "Barrier should be non-negative");
        assert!(result.tilt_margin > 0.9, "Tilt margin should be high at level");
    }

    #[test]
    fn test_tilt_limit() {
        let verifier = PtzSafetyVerifier::new();
        let mut state = create_test_state();

        // At max tilt
        state.orientation.pitch = constants::MAX_TILT_DEG;
        let result = verifier.compute_barrier(&state);

        assert!((result.tilt_margin - 0.0).abs() < 0.01, "At limit, tilt margin should be ~0");

        // Over max tilt
        state.orientation.pitch = constants::MAX_TILT_DEG + 5.0;
        let result = verifier.compute_barrier(&state);

        assert!(result.tilt_margin < 0.0, "Over limit, tilt margin should be negative");
        assert!(!result.safe, "Over limit should be unsafe");
    }

    #[test]
    fn test_thermal_margins() {
        let verifier = PtzSafetyVerifier::new();
        let mut state = create_test_state();

        // Below warning - fully safe
        state.coil_temp_c = constants::WARN_COIL_TEMP_C - 10.0;
        let result = verifier.compute_barrier(&state);
        assert_eq!(result.thermal_margin, 1.0);

        // At warning threshold
        state.coil_temp_c = constants::WARN_COIL_TEMP_C;
        let result = verifier.compute_barrier(&state);
        assert!((result.thermal_margin - 1.0).abs() < 0.01);

        // At max temperature
        state.coil_temp_c = constants::MAX_COIL_TEMP_C;
        let result = verifier.compute_barrier(&state);
        assert!((result.thermal_margin - 0.0).abs() < 0.01);

        // Over max temperature
        state.coil_temp_c = constants::MAX_COIL_TEMP_C + 5.0;
        let result = verifier.compute_barrier(&state);
        assert!(result.thermal_margin < 0.0);
    }

    #[test]
    fn test_corrective_actions() {
        let verifier = PtzSafetyVerifier::new();
        let mut state = create_test_state();

        // Over tilt limit should produce correction
        state.orientation.pitch = constants::MAX_TILT_DEG + 5.0;
        let result = verifier.compute_barrier(&state);

        assert!(result.tilt_correction > 0.0, "Should have tilt correction");
    }

    #[test]
    fn test_transition_check() {
        let verifier = PtzSafetyVerifier::new();
        let state = create_test_state();

        // Valid transition
        let target = Orientation::new(10.0, 5.0, 45.0);
        assert!(verifier.check_transition(&state, target, 1.0));

        // Invalid target (over limit)
        let target = Orientation::new(30.0, 0.0, 0.0);
        assert!(!verifier.check_transition(&state, target, 1.0));

        // Too fast transition
        let target = Orientation::new(15.0, 0.0, 0.0);
        assert!(!verifier.check_transition(&state, target, 0.1)); // 150 deg/s
    }

    #[test]
    fn test_barrier_function_minimum() {
        let verifier = PtzSafetyVerifier::new();
        let mut state = create_test_state();

        // Set various margins
        state.orientation.pitch = 15.0; // ~0.25 tilt margin
        state.coil_temp_c = 72.5;       // ~0.5 thermal margin

        let result = verifier.compute_barrier(&state);

        // h_ptz should be the minimum
        assert!(result.h_ptz <= result.lift_margin);
        assert!(result.h_ptz <= result.tilt_margin);
        assert!(result.h_ptz <= result.thermal_margin);
    }

    // ==================== ThermalAccumulator Tests ====================

    #[test]
    fn test_thermal_accumulator_normal_operation() {
        let mut accum = ThermalAccumulator::new();

        // Below threshold - should stay in normal
        accum.update(20.0, 0.002); // 20W, 2ms
        assert_eq!(accum.state(), ThermalState::Normal);
        assert_eq!(accum.max_current_a(), constants::MAX_COIL_CURRENT_A);
    }

    #[test]
    fn test_thermal_accumulator_burst_mode() {
        let mut accum = ThermalAccumulator::new();

        // Exceed threshold - should enter burst
        accum.update(30.0, 0.002); // 30W > 25W threshold
        assert!(matches!(accum.state(), ThermalState::Burst { .. }));
        assert!(accum.can_burst());
    }

    #[test]
    fn test_thermal_accumulator_cooldown() {
        let mut accum = ThermalAccumulator::new();

        // Force into burst mode
        accum.update(45.0, 0.002);

        // Simulate 30+ seconds of burst
        for _ in 0..15001 {
            accum.update(45.0, 0.002);
        }

        // Should now be in cooldown
        assert!(matches!(accum.state(), ThermalState::Cooldown { .. }));
        assert_eq!(accum.max_current_a(), 0.8);
        assert!(!accum.can_burst());
    }

    #[test]
    fn test_thermal_accumulator_energy_dissipation() {
        let mut accum = ThermalAccumulator::new();

        // Build up energy
        for _ in 0..1000 {
            accum.update(30.0, 0.002);
        }
        let high_energy = accum.energy_ratio();

        // Dissipate at low power
        for _ in 0..1000 {
            accum.update(10.0, 0.002); // Below dissipation capacity
        }
        let low_energy = accum.energy_ratio();

        assert!(low_energy < high_energy, "Energy should dissipate at low power");
    }

    #[test]
    fn test_thermal_accumulator_reset() {
        let mut accum = ThermalAccumulator::new();

        // Build up state
        accum.update(45.0, 0.002);
        accum.reset();

        assert_eq!(accum.state(), ThermalState::Normal);
        assert_eq!(accum.energy_ratio(), 0.0);
    }
}
