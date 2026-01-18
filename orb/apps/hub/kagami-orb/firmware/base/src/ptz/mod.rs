//! PTZ (Pan-Tilt-Zoom) Control System
//!
//! Magnetic orientation control for the Kagami Orb using 8 differential coils.
//! The PTZ system enables the orb to point in any direction while levitating.
//!
//! # Physics Model
//!
//! The orb contains permanent magnets in a Halbach array. The base has 8 coils
//! arranged at 45° intervals around the center. By varying current through each
//! coil, we create torque that rotates the orb.
//!
//! Force equation: F = k × I² / d²
//! where k ≈ 2.5×10⁻⁴ N·m²/A² for our geometry
//!
//! # Degrees of Freedom
//!
//! - Pan: 360° continuous rotation (azimuth)
//! - Tilt: ±20° from vertical (pitch)
//! - Roll: ±20° from horizontal (roll)
//!
//! # Safety
//!
//! h_ptz(x) >= 0 always. The barrier function monitors:
//! - Lift margin (must maintain levitation)
//! - Tilt margin (don't exceed mechanical limits)
//! - Thermal margin (coils must not overheat)

pub mod controller;
pub mod coils;
pub mod safety;

pub use controller::PtzController;
pub use coils::{CoilArray, CoilCurrents};
pub use safety::{
    PtzSafetyVerifier,
    PtzSafetyResult,
    PtzSafetyState,
    SensorFault,
    ThermalAccumulator,
    ThermalState,
};

/// Constants for PTZ control
pub mod constants {
    /// Number of coils in the array
    pub const NUM_COILS: usize = 8;

    /// Maximum current per coil (Amperes)
    /// Reduced from 2.5A to 1.5A for thermal management (8 × 1.5² × 2.5Ω = 45W peak)
    pub const MAX_COIL_CURRENT_A: f32 = 1.5;

    /// Minimum current to maintain contribution to lift (Amperes)
    pub const MIN_COIL_CURRENT_A: f32 = 0.2;

    /// Base current for stable lift without tilt (Amperes)
    pub const BASE_LIFT_CURRENT_A: f32 = 1.0;

    /// Coil radius from center (millimeters)
    pub const COIL_RADIUS_MM: f32 = 40.0;

    /// Wire gauge for coils (AWG)
    pub const COIL_WIRE_AWG: u8 = 24;

    /// Number of turns per coil
    pub const COIL_TURNS: u16 = 200;

    /// Coil resistance (Ohms) - measured value
    pub const COIL_RESISTANCE_OHMS: f32 = 2.5;

    /// Coil tilt angle (degrees) - coils tilted outward for yaw torque generation
    pub const COIL_TILT_DEG: f32 = 15.0;

    /// Maximum tilt angle (degrees)
    pub const MAX_TILT_DEG: f32 = 20.0;

    /// Maximum roll angle (degrees)
    pub const MAX_ROLL_DEG: f32 = 20.0;

    /// PTZ control rate (Hz)
    pub const CONTROL_RATE_HZ: u32 = 500;

    /// PTZ control period (milliseconds)
    pub const CONTROL_PERIOD_MS: u64 = 2; // 500Hz

    /// Orientation broadcast rate (Hz)
    pub const ORIENTATION_BROADCAST_HZ: u32 = 100;

    /// Maximum coil temperature (Celsius)
    pub const MAX_COIL_TEMP_C: f32 = 80.0;

    /// Warning coil temperature (Celsius)
    pub const WARN_COIL_TEMP_C: f32 = 65.0;

    /// Force constant k (N·m²/A²)
    /// Derived from coil geometry: N=200 turns, Ø25mm core
    /// k = μ₀ × N² × A / (2 × l) where A = core area, l = magnetic path length
    pub const FORCE_CONSTANT_K: f32 = 2.5e-4;

    /// Magnetic air gap at neutral levitation (millimeters)
    /// The orb floats 18-25mm above the base. PTZ coils act across this gap.
    /// At neutral: 20mm (midpoint of 18-25mm range)
    /// Force scales as 1/d², so closer = stronger control authority
    pub const MAGNETIC_GAP_MM: f32 = 20.0;

    // PID gains (Ziegler-Nichols tuned)

    /// Proportional gain
    pub const KP: f32 = 2.0;

    /// Integral gain
    pub const KI: f32 = 0.5;

    /// Derivative gain
    pub const KD: f32 = 0.8;

    /// Maximum integral windup
    pub const MAX_INTEGRAL: f32 = 50.0;

    /// Complementary filter coefficient for sensor fusion
    pub const COMPLEMENTARY_ALPHA: f32 = 0.98;
}

/// Orientation in Euler angles (degrees)
#[derive(Debug, Clone, Copy, Default)]
pub struct Orientation {
    /// Pitch (tilt forward/back) in degrees, -20 to +20
    pub pitch: f32,
    /// Roll (tilt left/right) in degrees, -20 to +20
    pub roll: f32,
    /// Yaw (pan rotation) in degrees, 0 to 360
    pub yaw: f32,
}

impl Orientation {
    /// Create a new orientation
    pub fn new(pitch: f32, roll: f32, yaw: f32) -> Self {
        Self { pitch, roll, yaw }
    }

    /// Level orientation (looking straight up)
    pub fn level() -> Self {
        Self::default()
    }

    /// Convert pitch to radians
    pub fn pitch_rad(&self) -> f32 {
        self.pitch * core::f32::consts::PI / 180.0
    }

    /// Convert roll to radians
    pub fn roll_rad(&self) -> f32 {
        self.roll * core::f32::consts::PI / 180.0
    }

    /// Convert yaw to radians
    pub fn yaw_rad(&self) -> f32 {
        self.yaw * core::f32::consts::PI / 180.0
    }

    /// Check if orientation is within safe limits
    pub fn is_within_limits(&self) -> bool {
        self.pitch.abs() <= constants::MAX_TILT_DEG
            && self.roll.abs() <= constants::MAX_ROLL_DEG
    }

    /// Clamp orientation to safe limits
    pub fn clamped(&self) -> Self {
        Self {
            pitch: self.pitch.clamp(-constants::MAX_TILT_DEG, constants::MAX_TILT_DEG),
            roll: self.roll.clamp(-constants::MAX_ROLL_DEG, constants::MAX_ROLL_DEG),
            yaw: self.yaw.rem_euclid(360.0),
        }
    }
}

/// PTZ operating mode
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum PtzMode {
    /// Disabled - no orientation control
    Disabled,

    /// Hold current orientation
    Hold {
        target: Orientation,
    },

    /// Track a target direction
    Track {
        target: Orientation,
        tracking_mode: TrackingMode,
    },

    /// Smooth pan at constant rate
    Pan {
        rate_deg_s: f32,
    },

    /// Return to level (neutral) position
    Center,

    /// Emergency - disable all control
    Emergency,
}

impl Default for PtzMode {
    fn default() -> Self {
        Self::Disabled
    }
}

/// Tracking mode for target following
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum TrackingMode {
    /// Track detected face
    Face,
    /// Track sound source
    Sound,
    /// Track motion
    Motion,
    /// Track explicit coordinates
    Manual,
}

/// PTZ system state
#[derive(Debug, Clone, Default)]
pub struct PtzState {
    /// Current measured orientation
    pub current: Orientation,
    /// Target orientation
    pub target: Orientation,
    /// Orientation error (target - current)
    pub error: Orientation,
    /// Current mode
    pub mode: PtzMode,
    /// Coil currents
    pub currents: [f32; constants::NUM_COILS],
    /// Average coil temperature (Celsius)
    pub coil_temp_c: f32,
    /// Lift margin (positive = safe)
    pub lift_margin: f32,
    /// System stable flag
    pub stable: bool,
}

impl PtzState {
    /// Check if PTZ is active (controlling orientation)
    pub fn is_active(&self) -> bool {
        !matches!(self.mode, PtzMode::Disabled | PtzMode::Emergency)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_orientation_limits() {
        let o = Orientation::new(15.0, -10.0, 45.0);
        assert!(o.is_within_limits());

        let o = Orientation::new(25.0, 0.0, 0.0);
        assert!(!o.is_within_limits());

        let clamped = o.clamped();
        assert!(clamped.is_within_limits());
        assert!((clamped.pitch - 20.0).abs() < 0.001);
    }

    #[test]
    fn test_yaw_wrap() {
        let o = Orientation::new(0.0, 0.0, 370.0);
        let clamped = o.clamped();
        assert!((clamped.yaw - 10.0).abs() < 0.001);

        let o = Orientation::new(0.0, 0.0, -30.0);
        let clamped = o.clamped();
        assert!((clamped.yaw - 330.0).abs() < 0.001);
    }
}
