//! Coil Array Driver
//!
//! Controls the 8 electromagnetic coils that create the magnetic field
//! for PTZ orientation control. Each coil's current is modulated to
//! create torque on the orb's permanent magnets.
//!
//! # Coil Layout (Top View)
//!
//! ```text
//!                    0° (North)
//!                       [0]
//!              [7]             [1]
//!           315°   ╲         ╱   45°
//!                    ╲     ╱
//!      270° [6] ──────  ⬡  ────── [2] 90°
//!                    ╱     ╲
//!           225°   ╱         ╲   135°
//!              [5]             [3]
//!                       [4]
//!                    180° (South)
//! ```
//!
//! Coil positions: θ[i] = i × 45° for i = 0..7
//!
//! # Current Calculation
//!
//! For a desired pitch (p), roll (r), and yaw rate (ω):
//!
//! I[i] = I_base + K_pitch × p × cos(θ[i]) + K_roll × r × sin(θ[i]) + K_yaw × ω × sin(θ[i] - φ)
//!
//! where θ[i] = i × 45° is the coil angle

use super::constants;
use core::f32::consts::PI;

/// Current settings for all 8 coils
#[derive(Debug, Clone, Copy)]
pub struct CoilCurrents {
    /// Current for each coil (Amperes)
    pub currents: [f32; constants::NUM_COILS],
}

impl CoilCurrents {
    /// Create zero currents
    pub fn zero() -> Self {
        Self {
            currents: [0.0; constants::NUM_COILS],
        }
    }

    /// Create level (base lift) currents
    pub fn level() -> Self {
        Self {
            currents: [constants::BASE_LIFT_CURRENT_A; constants::NUM_COILS],
        }
    }

    /// Get currents as array reference
    pub fn as_array(&self) -> [f32; constants::NUM_COILS] {
        self.currents
    }

    /// Get total power dissipation estimate (watts)
    ///
    /// P = I²R where R = 2.5Ω per coil (measured for AWG 24, 200 turns, 25mm core)
    /// Wire length: 200 turns × π × 25mm ≈ 15.7m, AWG 24 = 84.2mΩ/m → ~1.32Ω
    /// Plus core losses and connection resistance → 2.5Ω total measured
    pub fn total_power_watts(&self) -> f32 {
        const COIL_RESISTANCE: f32 = 2.5; // Measured ohms (canonical value from SPECS.md)
        self.currents.iter().map(|i| i * i * COIL_RESISTANCE).sum()
    }

    /// Get average current
    pub fn average_current(&self) -> f32 {
        self.currents.iter().sum::<f32>() / constants::NUM_COILS as f32
    }

    /// Get maximum current
    pub fn max_current(&self) -> f32 {
        self.currents.iter().cloned().fold(0.0, f32::max)
    }
}

impl Default for CoilCurrents {
    fn default() -> Self {
        Self::level()
    }
}

/// Coil array controller
pub struct CoilArray {
    /// Coil angles in radians
    coil_angles: [f32; constants::NUM_COILS],

    /// Gain for pitch control (A/deg)
    k_pitch: f32,

    /// Gain for roll control (A/deg)
    k_roll: f32,

    /// Gain for yaw control (A/(deg/s))
    k_yaw: f32,

    /// Phase offset for yaw torque generation (radians)
    yaw_phase: f32,
}

impl CoilArray {
    /// Create a new coil array controller
    pub fn new() -> Self {
        // Pre-compute coil angles
        let mut angles = [0.0f32; constants::NUM_COILS];
        for i in 0..constants::NUM_COILS {
            angles[i] = (i as f32) * 2.0 * PI / (constants::NUM_COILS as f32);
        }

        Self {
            coil_angles: angles,
            k_pitch: 0.05,  // 50mA per degree of pitch
            k_roll: 0.05,   // 50mA per degree of roll
            k_yaw: 0.03,    // 30mA per deg/s of yaw rate
            yaw_phase: 0.0, // Updated based on current yaw
        }
    }

    /// Calculate coil currents for level (no tilt) operation
    pub fn calculate_level_currents(&self) -> CoilCurrents {
        CoilCurrents::level()
    }

    /// Calculate coil currents for desired orientation command
    ///
    /// # Arguments
    /// * `pitch_cmd` - PID output for pitch control (positive = tilt forward)
    /// * `roll_cmd` - PID output for roll control (positive = tilt right)
    /// * `yaw_cmd` - PID output for yaw control (positive = rotate clockwise)
    pub fn calculate_currents(
        &mut self,
        pitch_cmd: f32,
        roll_cmd: f32,
        yaw_cmd: f32,
    ) -> CoilCurrents {
        let mut currents = CoilCurrents::zero();

        for i in 0..constants::NUM_COILS {
            let theta = self.coil_angles[i];

            // Base current for lift
            let mut current = constants::BASE_LIFT_CURRENT_A;

            // Pitch component: cos(θ) distribution
            // Coils at 0° and 180° (front/back) contribute most to pitch
            current += pitch_cmd * self.k_pitch * libm::cosf(theta);

            // Roll component: sin(θ) distribution
            // Coils at 90° and 270° (left/right) contribute most to roll
            current += roll_cmd * self.k_roll * libm::sinf(theta);

            // Yaw component: tangential force for rotation
            // Phase-shifted sin to create torque around vertical axis
            let yaw_angle = theta - self.yaw_phase;
            current += yaw_cmd * self.k_yaw * libm::sinf(yaw_angle);

            // Clamp to safe range
            currents.currents[i] = current.clamp(
                constants::MIN_COIL_CURRENT_A,
                constants::MAX_COIL_CURRENT_A,
            );
        }

        currents
    }

    /// Calculate corrective currents for safety
    ///
    /// # Arguments
    /// * `lift_correction` - Additional lift current needed (all coils)
    /// * `tilt_correction` - Orientation toward level (pitch, roll reduction)
    pub fn calculate_corrective_currents(
        &self,
        lift_correction: f32,
        tilt_correction: f32,
    ) -> CoilCurrents {
        let mut currents = CoilCurrents::zero();

        for i in 0..constants::NUM_COILS {
            let theta = self.coil_angles[i];

            // Base current plus lift correction
            let mut current = constants::BASE_LIFT_CURRENT_A + lift_correction;

            // Tilt correction reduces differential (toward level)
            // This scales down the pitch/roll components
            let tilt_factor = 1.0 - tilt_correction.clamp(0.0, 1.0);
            current *= tilt_factor;

            // Ensure minimum for all coils
            currents.currents[i] = current.max(constants::MIN_COIL_CURRENT_A);
        }

        currents
    }

    /// Update yaw phase based on current orientation
    pub fn set_yaw_phase(&mut self, yaw_rad: f32) {
        self.yaw_phase = yaw_rad;
    }

    /// Set control gains
    pub fn set_gains(&mut self, k_pitch: f32, k_roll: f32, k_yaw: f32) {
        self.k_pitch = k_pitch;
        self.k_roll = k_roll;
        self.k_yaw = k_yaw;
    }

    /// Calculate the magnetic force at current configuration
    ///
    /// F = k × I² / d² for each coil
    pub fn calculate_total_force(&self, currents: &CoilCurrents, gap_mm: f32) -> f32 {
        let gap_m = gap_mm / 1000.0;
        let mut total_force = 0.0;

        for &current in &currents.currents {
            let force = constants::FORCE_CONSTANT_K * current * current / (gap_m * gap_m);
            total_force += force;
        }

        total_force
    }

    /// Calculate torque vector from current distribution
    ///
    /// Returns (torque_x, torque_y, torque_z) in N·m
    ///
    /// # Physics
    ///
    /// For pitch/roll: τ = r × F where F is the vertical magnetic force difference
    /// For yaw: The coils are tilted 15° outward, creating a tangential force component
    /// that generates yaw torque when current differentials are applied around the ring.
    ///
    /// Yaw torque equation:
    /// τ_z = Σ F_tangential[i] × r = Σ F[i] × sin(15°) × sin(θ[i] - φ) × r
    pub fn calculate_torque(
        &self,
        currents: &CoilCurrents,
        gap_mm: f32,
    ) -> (f32, f32, f32) {
        let gap_m = gap_mm / 1000.0;
        let r_m = constants::COIL_RADIUS_MM / 1000.0;

        // Coil tilt angle creates tangential force component for yaw
        let coil_tilt_rad = constants::COIL_TILT_DEG * core::f32::consts::PI / 180.0;
        let sin_tilt = libm::sinf(coil_tilt_rad);

        let mut tau_x = 0.0; // Roll torque (about x-axis)
        let mut tau_y = 0.0; // Pitch torque (about y-axis)
        let mut tau_z = 0.0; // Yaw torque (about z-axis)

        // Calculate mean current for differential analysis
        let mean_current = currents.average_current();

        for i in 0..constants::NUM_COILS {
            let theta = self.coil_angles[i];
            let current = currents.currents[i];

            // Force magnitude from this coil (F = k × I² / d²)
            let force = constants::FORCE_CONSTANT_K * current * current / (gap_m * gap_m);

            // Position of coil (x, y) from center
            let x = r_m * libm::cosf(theta);
            let y = r_m * libm::sinf(theta);

            // Pitch/Roll torque from differential vertical forces
            // τ = r × F_vertical
            tau_x += -y * force; // Roll (about x-axis): F at +y creates -τ_x
            tau_y += x * force;  // Pitch (about y-axis): F at +x creates +τ_y

            // Yaw torque from tangential force component
            // The tilted coils create a tangential force = F × sin(tilt)
            // This tangential force at radius r creates yaw torque
            // The direction depends on current differential from mean
            let current_diff = current - mean_current;
            let tangential_force = force * sin_tilt * current_diff.signum();

            // Tangential force at angle θ creates torque about z
            // τ_z = F_tangential × r (perpendicular to radius)
            tau_z += tangential_force * r_m;
        }

        (tau_x, tau_y, tau_z)
    }
}

impl Default for CoilArray {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_level_currents() {
        let array = CoilArray::new();
        let currents = array.calculate_level_currents();

        // All currents should be equal to base lift
        for &c in &currents.currents {
            assert!((c - constants::BASE_LIFT_CURRENT_A).abs() < 0.001);
        }
    }

    #[test]
    fn test_pitch_currents() {
        let mut array = CoilArray::new();

        // Positive pitch command (tilt forward)
        let currents = array.calculate_currents(10.0, 0.0, 0.0);

        // Coil 0 (front) should have higher current than coil 4 (back)
        // cos(0) = 1, cos(π) = -1
        assert!(currents.currents[0] > currents.currents[4]);
    }

    #[test]
    fn test_roll_currents() {
        let mut array = CoilArray::new();

        // Positive roll command (tilt right)
        let currents = array.calculate_currents(0.0, 10.0, 0.0);

        // Coil 2 (right) should have higher current than coil 6 (left)
        // sin(π/2) = 1, sin(3π/2) = -1
        assert!(currents.currents[2] > currents.currents[6]);
    }

    #[test]
    fn test_current_limits() {
        let mut array = CoilArray::new();

        // Large command should be clamped
        let currents = array.calculate_currents(100.0, 100.0, 100.0);

        for &c in &currents.currents {
            assert!(c >= constants::MIN_COIL_CURRENT_A);
            assert!(c <= constants::MAX_COIL_CURRENT_A);
        }
    }

    #[test]
    fn test_force_calculation() {
        let array = CoilArray::new();
        let currents = CoilCurrents::level();

        let force = array.calculate_total_force(&currents, constants::MAGNETIC_GAP_MM);

        // At 20mm gap with 1A per coil:
        // F_per_coil = k × I² / d² = 2.5e-4 × 1 / (0.020)² = 0.625 N
        // F_total = 8 × 0.625 = 5.0 N
        // This exceeds required 4.12 N (420g × 9.81 m/s²)
        let expected = 8.0 * constants::FORCE_CONSTANT_K
            * constants::BASE_LIFT_CURRENT_A.powi(2)
            / (constants::MAGNETIC_GAP_MM / 1000.0).powi(2);

        assert!(force > 0.0);
        assert!((force - expected).abs() < 0.5, "Expected ~{}N, got {}N", expected, force);
    }

    #[test]
    fn test_torque_calculation() {
        let array = CoilArray::new();

        // Create asymmetric currents: front higher than back (pitch torque)
        let mut currents = CoilCurrents::level();
        currents.currents[0] = 1.3; // North (front) - higher
        currents.currents[4] = 0.7; // South (back) - lower

        let (tau_x, tau_y, tau_z) = array.calculate_torque(&currents, constants::MAGNETIC_GAP_MM);

        // Pitch torque should be positive (tilts forward)
        assert!(tau_y > 0.0, "Expected positive pitch torque, got {}", tau_y);

        // Roll and yaw should be near zero for this symmetric case
        assert!(tau_x.abs() < tau_y.abs() * 0.1, "Roll should be small: {}", tau_x);
    }

    #[test]
    fn test_yaw_torque() {
        let array = CoilArray::new();

        // Create a current pattern that should generate yaw torque
        // Higher current on one side, lower on the opposite
        let mut currents = CoilCurrents::level();
        currents.currents[1] = 1.3; // NE - higher
        currents.currents[2] = 1.3; // E - higher
        currents.currents[5] = 0.7; // SW - lower
        currents.currents[6] = 0.7; // W - lower

        let (_, _, tau_z) = array.calculate_torque(&currents, constants::MAGNETIC_GAP_MM);

        // Yaw torque should be non-zero due to coil tilt
        // The 15° tilt creates tangential force components
        assert!(tau_z.abs() > 1e-6, "Yaw torque should be non-zero: {}", tau_z);
    }

    #[test]
    fn test_power_dissipation() {
        let currents = CoilCurrents::level();
        let power = currents.total_power_watts();

        // 8 coils × 1A² × 2.5Ω = 20W (BASE_LIFT_CURRENT = 1.0A, COIL_RESISTANCE = 2.5Ω)
        let expected = 8.0 * constants::BASE_LIFT_CURRENT_A.powi(2) * 2.5;
        assert!((power - expected).abs() < 0.1, "Expected {}W, got {}W", expected, power);
    }
}
