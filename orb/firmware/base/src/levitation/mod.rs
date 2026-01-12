//! Magnetic Levitation Control System
//!
//! This module implements the outer-loop height controller for the HCNT
//! maglev module. It provides dynamic height control for:
//!
//! - **Float mode**: Normal operation at 20mm for full PTZ range
//! - **Charging mode**: Sink to 5mm for maximum WPT efficiency (~90%)
//! - **Bobble mode**: Animated oscillation for expressive effects
//! - **Emergency landing**: Controlled descent with passive soft landing
//!
//! # Architecture
//!
//! The HCNT module has its own internal PID controller running at 20kHz.
//! This outer loop runs at 100Hz and provides setpoint commands via DAC.
//!
//! ```text
//! ┌─────────────────────────────────────────────────────────────┐
//! │                    HEIGHT CONTROL LOOP                       │
//! │                                                              │
//! │   ┌─────────┐    ┌─────────────┐    ┌─────────┐             │
//! │   │ Command │───>│  Trajectory │───>│   DAC   │──> HCNT     │
//! │   │         │    │  Generator  │    │ MCP4725 │   Setpoint  │
//! │   └─────────┘    └─────────────┘    └─────────┘             │
//! │                                                              │
//! │   ┌─────────┐    ┌─────────────┐    ┌─────────┐             │
//! │   │ Height  │<───│  Calibration│<───│   ADC   │<── Hall     │
//! │   │  (mm)   │    │   Curve     │    │         │   Sensor    │
//! │   └─────────┘    └─────────────┘    └─────────┘             │
//! │                                                              │
//! └─────────────────────────────────────────────────────────────┘
//! ```

mod controller;
mod trajectory;
mod safety;
mod calibration;

pub use controller::HeightController;
pub use trajectory::{HeightTrajectory, BobbleAnimation};
pub use safety::{LevitationSafetyVerifier, SafetyResult, SafetyCode};
pub use calibration::CalibrationData;

use core::f32::consts::PI;

/// Levitation operating modes
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum LevitationMode {
    /// Normal operation: Orb floats at specified height for full PTZ range
    Float {
        height_mm: f32,  // 18-22mm typical
    },

    /// Charging mode: Orb sinks for maximum WPT efficiency
    Charging {
        target_height_mm: f32,  // 5-8mm
        charge_rate_w: f32,     // Actual power delivered
    },

    /// Animation mode: Orb oscillates for expressive effects
    Bobble {
        center_mm: f32,     // 15-20mm
        amplitude_mm: f32,  // 3-8mm
        frequency_hz: f32,  // 0.3-1.5Hz
    },

    /// Controlled descent to base
    Landing {
        current_height_mm: f32,
        descent_rate_mm_s: f32,  // ~10mm/s max
    },

    /// Power failure: Passive soft landing via eddy current damping
    EmergencyLanding,

    /// Orb removed from base
    Lifted,

    /// Transitioning between modes
    Transitioning {
        from: LevitationModeSimple,
        to: LevitationModeSimple,
        progress: f32,  // 0.0 to 1.0
    },
}

/// Simplified mode for transition tracking
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LevitationModeSimple {
    Float,
    Charging,
    Bobble,
    Landing,
    Lifted,
}

impl Default for LevitationMode {
    fn default() -> Self {
        Self::Lifted
    }
}

/// Current state of the levitation system
#[derive(Debug, Clone, Copy, Default)]
pub struct LevitationState {
    /// Current height above base (mm)
    pub height_mm: f32,

    /// Vertical velocity (mm/s, positive = rising)
    pub velocity_mm_s: f32,

    /// Peak-to-peak oscillation amplitude (mm)
    pub oscillation_amplitude_mm: f32,

    /// Electromagnet coil temperature (Celsius)
    pub electromagnet_temp_c: f32,

    /// WPT coil temperature (Celsius)
    pub wpt_coil_temp_c: f32,

    /// Power supply status
    pub power_supply_ok: bool,

    /// Current operating mode
    pub mode: LevitationMode,

    /// Orb detected on base
    pub orb_present: bool,

    /// System stable (no excessive oscillation)
    pub stable: bool,
}

/// Height control constants
pub mod constants {
    /// Minimum safe height (mm)
    pub const HEIGHT_MIN_MM: f32 = 5.0;

    /// Maximum safe height (mm)
    pub const HEIGHT_MAX_MM: f32 = 25.0;

    /// Default float height (mm)
    pub const HEIGHT_FLOAT_MM: f32 = 20.0;

    /// Optimal charging height (mm)
    pub const HEIGHT_CHARGE_MM: f32 = 5.0;

    /// Maximum descent rate (mm/s)
    pub const MAX_DESCENT_RATE_MM_S: f32 = 15.0;

    /// Maximum bobble amplitude (mm)
    pub const MAX_BOBBLE_AMPLITUDE_MM: f32 = 8.0;

    /// Minimum bobble frequency (Hz)
    pub const MIN_BOBBLE_FREQ_HZ: f32 = 0.1;

    /// Maximum bobble frequency (Hz)
    pub const MAX_BOBBLE_FREQ_HZ: f32 = 2.0;

    /// Control loop rate (Hz)
    pub const CONTROL_RATE_HZ: u32 = 100;

    /// Control loop period (ms)
    pub const CONTROL_PERIOD_MS: u64 = 1000 / CONTROL_RATE_HZ as u64;

    /// DAC voltage at 5mm height
    pub const DAC_V_AT_5MM: f32 = 2.5;

    /// DAC voltage at 25mm height
    pub const DAC_V_AT_25MM: f32 = 0.5;

    /// Maximum oscillation before instability (mm)
    pub const MAX_OSCILLATION_MM: f32 = 5.0;

    /// Electromagnet max temperature (Celsius)
    pub const MAX_COIL_TEMP_C: f32 = 80.0;

    /// Temperature warning threshold (Celsius)
    pub const WARN_COIL_TEMP_C: f32 = 65.0;
}

/// Estimate coupling coefficient from height
///
/// Uses empirical fit for 80mm TX/RX coil pair:
/// k ≈ 0.9 * exp(-height / 15)
pub fn estimate_coupling(height_mm: f32) -> f32 {
    0.9 * libm::expf(-height_mm / 15.0)
}

/// Estimate WPT efficiency from coupling coefficient
///
/// η = k² × Q_tx × Q_rx / (1 + k² × Q_tx × Q_rx)
///
/// With Q_tx ≈ 200, Q_rx ≈ 150
pub fn estimate_efficiency(k: f32) -> f32 {
    const Q_TX: f32 = 200.0;
    const Q_RX: f32 = 150.0;

    let k_sq = k * k;
    let q_product = Q_TX * Q_RX;

    k_sq * q_product / (1.0 + k_sq * q_product)
}

/// Calculate optimal WPT frequency for given coupling
///
/// f_resonant = f_0 * sqrt(1 - k) for undercoupled operation
///
/// Returns frequency in Hz
pub fn optimal_wpt_frequency(k: f32) -> f32 {
    const F_BASE_HZ: f32 = 140_000.0;

    F_BASE_HZ * libm::sqrtf(1.0 - k.min(0.9))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_coupling_estimation() {
        // At 5mm, k should be ~0.63
        let k_5mm = estimate_coupling(5.0);
        assert!(k_5mm > 0.6 && k_5mm < 0.75);

        // At 15mm, k should be ~0.33
        let k_15mm = estimate_coupling(15.0);
        assert!(k_15mm > 0.3 && k_15mm < 0.4);

        // At 25mm, k should be ~0.17
        let k_25mm = estimate_coupling(25.0);
        assert!(k_25mm > 0.15 && k_25mm < 0.25);
    }

    #[test]
    fn test_efficiency_estimation() {
        // High coupling should give high efficiency
        let eta_high = estimate_efficiency(0.7);
        assert!(eta_high > 0.95);

        // Low coupling should give lower efficiency
        let eta_low = estimate_efficiency(0.2);
        assert!(eta_low > 0.5 && eta_low < 0.9);
    }

    #[test]
    fn test_wpt_frequency() {
        // At k=0, frequency should be f_base
        let f_0 = optimal_wpt_frequency(0.0);
        assert!((f_0 - 140_000.0).abs() < 100.0);

        // At k=0.5, frequency should be lower
        let f_half = optimal_wpt_frequency(0.5);
        assert!(f_half < 140_000.0);
        assert!(f_half > 90_000.0);
    }
}
