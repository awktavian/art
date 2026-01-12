//! Main height controller for the levitation system
//!
//! Implements the 100Hz outer control loop that manages height setpoints
//! for the HCNT maglev module.

use super::{
    LevitationMode, LevitationModeSimple, LevitationState,
    trajectory::{HeightTrajectory, BobbleAnimation, HeightMotionGenerator},
    safety::{LevitationSafetyVerifier, SafetyInterlockManager, SafetyResult},
    calibration::{CalibrationData, WptCalibrationData},
    constants,
};
use crate::error::{BaseError, BaseResult};

/// Height controller for the levitation system
///
/// This controller runs at 100Hz and provides height setpoints to the
/// HCNT maglev module's internal PID controller via DAC.
pub struct HeightController {
    // Calibration data
    height_cal: CalibrationData,
    wpt_cal: WptCalibrationData,

    // Motion generation
    motion: HeightMotionGenerator,

    // State tracking
    state: LevitationState,
    mode: LevitationMode,

    // Safety
    safety_verifier: LevitationSafetyVerifier,
    interlock: SafetyInterlockManager,

    // Timing
    last_adc_value: u16,
    last_dac_voltage: f32,

    // Velocity estimation (for safety checks)
    velocity_filter: VelocityFilter,

    // Oscillation detection
    oscillation_detector: OscillationDetector,
}

impl HeightController {
    /// Create a new height controller with default calibration
    pub fn new() -> Self {
        Self {
            height_cal: CalibrationData::default(),
            wpt_cal: WptCalibrationData::default(),
            motion: HeightMotionGenerator::new(),
            state: LevitationState::default(),
            mode: LevitationMode::Lifted,
            safety_verifier: LevitationSafetyVerifier::new(),
            interlock: SafetyInterlockManager::new(),
            last_adc_value: 0,
            last_dac_voltage: 1.5,
            velocity_filter: VelocityFilter::new(),
            oscillation_detector: OscillationDetector::new(),
        }
    }

    /// Load calibration data
    pub fn set_calibration(&mut self, height: CalibrationData, wpt: WptCalibrationData) {
        self.height_cal = height;
        self.wpt_cal = wpt;
    }

    /// Main update loop - call at 100Hz
    ///
    /// Returns (dac_voltage, wpt_frequency) to set
    pub fn update(&mut self, adc_value: u16, power_ok: bool, coil_temp: f32) -> BaseResult<(f32, f32)> {
        let dt = 1.0 / constants::CONTROL_RATE_HZ as f32;

        // Convert ADC to height
        let height_mm = self.height_cal.adc_to_height(adc_value);

        // Update velocity estimate
        self.velocity_filter.update(height_mm, dt);
        let velocity = self.velocity_filter.velocity();

        // Update oscillation detection
        self.oscillation_detector.update(height_mm);
        let oscillation = self.oscillation_detector.amplitude();

        // Update state
        self.state.height_mm = height_mm;
        self.state.velocity_mm_s = velocity;
        self.state.oscillation_amplitude_mm = oscillation;
        self.state.electromagnet_temp_c = coil_temp;
        self.state.power_supply_ok = power_ok;
        self.state.stable = oscillation < constants::MAX_OSCILLATION_MM * 0.7;
        self.state.mode = self.mode;

        // Safety check
        let safety_result = self.safety_verifier.compute_barrier(&self.state);
        let emergency = self.interlock.update(&safety_result);

        if emergency {
            // Emergency landing - set DAC to minimum (maximum gap)
            self.mode = LevitationMode::EmergencyLanding;
            return Ok((0.0, 0.0)); // Let gravity + eddy damping do the work
        }

        // Get target height from motion generator
        let (target_height, _target_velocity) = self.motion.update(dt);

        // Apply safety corrections if needed
        let corrected_height = if !safety_result.safe {
            let correction = self.safety_verifier.corrective_action(&safety_result);
            (target_height + correction * dt).clamp(
                constants::HEIGHT_MIN_MM,
                constants::HEIGHT_MAX_MM,
            )
        } else {
            target_height
        };

        // Convert to DAC voltage
        let dac_voltage = self.height_cal.height_to_dac(corrected_height);

        // Get optimal WPT frequency
        let wpt_freq = self.wpt_cal.optimal_frequency(corrected_height);

        // Store for next iteration
        self.last_adc_value = adc_value;
        self.last_dac_voltage = dac_voltage;

        Ok((dac_voltage, wpt_freq))
    }

    /// Command: Start charging mode (sink to 5mm)
    pub fn start_charging(&mut self) -> BaseResult<()> {
        if self.interlock.is_emergency() {
            return Err(BaseError::EmergencyLanding);
        }

        let trajectory = HeightTrajectory::to_charging(self.state.height_mm);
        self.motion.start_trajectory(trajectory);

        self.mode = LevitationMode::Charging {
            target_height_mm: constants::HEIGHT_CHARGE_MM,
            charge_rate_w: 0.0,
        };

        Ok(())
    }

    /// Command: Stop charging, return to float mode
    pub fn stop_charging(&mut self) -> BaseResult<()> {
        if self.interlock.is_emergency() {
            return Err(BaseError::EmergencyLanding);
        }

        let trajectory = HeightTrajectory::to_float(self.state.height_mm);
        self.motion.start_trajectory(trajectory);

        self.mode = LevitationMode::Float {
            height_mm: constants::HEIGHT_FLOAT_MM,
        };

        Ok(())
    }

    /// Command: Set specific height
    pub fn set_height(&mut self, target_mm: f32, duration_ms: u32) -> BaseResult<()> {
        if self.interlock.is_emergency() {
            return Err(BaseError::EmergencyLanding);
        }

        if target_mm < constants::HEIGHT_MIN_MM || target_mm > constants::HEIGHT_MAX_MM {
            return Err(BaseError::HeightOutOfRange);
        }

        let duration_s = duration_ms as f32 / 1000.0;
        let trajectory = HeightTrajectory::new(self.state.height_mm, target_mm, duration_s);
        self.motion.start_trajectory(trajectory);

        self.mode = LevitationMode::Float { height_mm: target_mm };

        Ok(())
    }

    /// Command: Start bobble animation
    pub fn start_bobble(&mut self, amplitude_mm: f32, frequency_hz: f32) -> BaseResult<()> {
        if self.interlock.is_emergency() {
            return Err(BaseError::EmergencyLanding);
        }

        if amplitude_mm < 1.0 || amplitude_mm > constants::MAX_BOBBLE_AMPLITUDE_MM {
            return Err(BaseError::InvalidAmplitude);
        }

        if frequency_hz < constants::MIN_BOBBLE_FREQ_HZ || frequency_hz > constants::MAX_BOBBLE_FREQ_HZ {
            return Err(BaseError::InvalidFrequency);
        }

        // Check if we have enough headroom for the bobble
        let center = self.state.height_mm;
        if center - amplitude_mm < constants::HEIGHT_MIN_MM
            || center + amplitude_mm > constants::HEIGHT_MAX_MM
        {
            return Err(BaseError::HeightOutOfRange);
        }

        let animation = BobbleAnimation::new(center, amplitude_mm, frequency_hz);
        self.motion.start_animation(animation);

        self.mode = LevitationMode::Bobble {
            center_mm: center,
            amplitude_mm,
            frequency_hz,
        };

        Ok(())
    }

    /// Command: Stop bobble animation
    pub fn stop_bobble(&mut self) -> BaseResult<()> {
        self.motion.stop(self.state.height_mm);
        self.mode = LevitationMode::Float {
            height_mm: self.state.height_mm,
        };
        Ok(())
    }

    /// Command: Controlled landing
    pub fn land(&mut self) -> BaseResult<()> {
        let trajectory = HeightTrajectory::new(
            self.state.height_mm,
            constants::HEIGHT_MIN_MM,
            3.0, // 3 second gentle landing
        );
        self.motion.start_trajectory(trajectory);

        self.mode = LevitationMode::Landing {
            current_height_mm: self.state.height_mm,
            descent_rate_mm_s: 5.0,
        };

        Ok(())
    }

    /// Command: Emergency land (bypasses normal trajectory)
    pub fn emergency_land(&mut self) {
        self.interlock.trigger_lockout();
        self.mode = LevitationMode::EmergencyLanding;
    }

    /// Reset after manual intervention
    pub fn reset(&mut self) -> BaseResult<()> {
        self.interlock.reset();
        self.motion.stop(self.state.height_mm);
        self.mode = LevitationMode::Float {
            height_mm: constants::HEIGHT_FLOAT_MM,
        };
        Ok(())
    }

    /// Get current state
    pub fn state(&self) -> &LevitationState {
        &self.state
    }

    /// Get current mode
    pub fn mode(&self) -> LevitationMode {
        self.mode
    }

    /// Get latest safety result
    pub fn safety_status(&self) -> SafetyResult {
        self.safety_verifier.compute_barrier(&self.state)
    }

    /// Check if system is in emergency state
    pub fn is_emergency(&self) -> bool {
        self.interlock.is_emergency()
    }

    /// Notify that orb has been lifted off base
    pub fn on_orb_lifted(&mut self) {
        self.mode = LevitationMode::Lifted;
        self.motion.stop(0.0);
    }

    /// Notify that orb has been placed on base
    pub fn on_orb_placed(&mut self) {
        if !self.interlock.is_locked_out() {
            self.mode = LevitationMode::Float {
                height_mm: constants::HEIGHT_FLOAT_MM,
            };
            let trajectory = HeightTrajectory::new(
                constants::HEIGHT_MIN_MM,
                constants::HEIGHT_FLOAT_MM,
                1.5,
            );
            self.motion.start_trajectory(trajectory);
        }
    }

    /// Update charging power (from WPT subsystem)
    pub fn set_charge_power(&mut self, power_w: f32) {
        if let LevitationMode::Charging { charge_rate_w, .. } = &mut self.mode {
            *charge_rate_w = power_w;
        }
        self.state.wpt_coil_temp_c = self.state.wpt_coil_temp_c; // Placeholder
    }
}

impl Default for HeightController {
    fn default() -> Self {
        Self::new()
    }
}

/// Simple velocity estimator using finite difference with filtering
struct VelocityFilter {
    last_height: f32,
    velocity: f32,
    alpha: f32, // Low-pass filter coefficient
}

impl VelocityFilter {
    fn new() -> Self {
        Self {
            last_height: 0.0,
            velocity: 0.0,
            alpha: 0.3, // More responsive
        }
    }

    fn update(&mut self, height: f32, dt: f32) {
        if dt > 0.0 {
            let raw_velocity = (height - self.last_height) / dt;
            // Exponential moving average filter
            self.velocity = self.alpha * raw_velocity + (1.0 - self.alpha) * self.velocity;
            self.last_height = height;
        }
    }

    fn velocity(&self) -> f32 {
        self.velocity
    }
}

/// Oscillation amplitude detector
struct OscillationDetector {
    samples: [f32; 32],
    index: usize,
    filled: bool,
}

impl OscillationDetector {
    fn new() -> Self {
        Self {
            samples: [0.0; 32],
            index: 0,
            filled: false,
        }
    }

    fn update(&mut self, height: f32) {
        self.samples[self.index] = height;
        self.index = (self.index + 1) % 32;
        if self.index == 0 {
            self.filled = true;
        }
    }

    fn amplitude(&self) -> f32 {
        if !self.filled {
            return 0.0;
        }

        let mut min = f32::MAX;
        let mut max = f32::MIN;

        for &s in &self.samples {
            if s < min {
                min = s;
            }
            if s > max {
                max = s;
            }
        }

        max - min
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_controller_initialization() {
        let controller = HeightController::new();
        assert_eq!(controller.mode(), LevitationMode::Lifted);
        assert!(!controller.is_emergency());
    }

    #[test]
    fn test_bobble_validation() {
        let mut controller = HeightController::new();

        // Set up a valid state
        controller.state.height_mm = 15.0;
        controller.state.power_supply_ok = true;

        // Valid bobble should succeed
        assert!(controller.start_bobble(3.0, 0.5).is_ok());

        // Invalid amplitude should fail
        controller.stop_bobble().unwrap();
        assert!(controller.start_bobble(15.0, 0.5).is_err());

        // Invalid frequency should fail
        assert!(controller.start_bobble(3.0, 5.0).is_err());
    }

    #[test]
    fn test_velocity_filter() {
        let mut filter = VelocityFilter::new();

        // Simulate rising at 10mm/s
        for i in 0..10 {
            let height = 10.0 + (i as f32) * 0.1; // 0.1mm per step
            filter.update(height, 0.01); // 100Hz = 0.01s period
        }

        // Velocity should converge to ~10mm/s
        let v = filter.velocity();
        assert!(v > 5.0 && v < 15.0);
    }

    #[test]
    fn test_oscillation_detector() {
        let mut detector = OscillationDetector::new();

        // Simulate 2mm oscillation
        for i in 0..40 {
            let phase = (i as f32) * 0.2;
            let height = 15.0 + libm::sinf(phase);
            detector.update(height);
        }

        let amp = detector.amplitude();
        assert!(amp > 1.5 && amp < 2.5);
    }
}
