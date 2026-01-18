//! PTZ Controller
//!
//! Main controller for Pan-Tilt-Zoom operations. Implements PID control
//! with sensor fusion for precise orientation tracking.

use super::{
    Orientation, PtzMode, PtzState, TrackingMode,
    coils::{CoilArray, CoilCurrents},
    safety::{PtzSafetyVerifier, PtzSafetyResult, PtzSafetyState},
    constants,
};

/// PID controller state for a single axis
#[derive(Debug, Clone, Default)]
struct PidState {
    /// Integrated error
    integral: f32,
    /// Previous error (for derivative)
    prev_error: f32,
    /// Output value
    output: f32,
}

impl PidState {
    fn new() -> Self {
        Self::default()
    }

    /// Update PID and return control output
    fn update(&mut self, error: f32, dt: f32, kp: f32, ki: f32, kd: f32) -> f32 {
        // Proportional term
        let p = kp * error;

        // Integral term with anti-windup
        self.integral += error * dt;
        self.integral = self.integral.clamp(-constants::MAX_INTEGRAL, constants::MAX_INTEGRAL);
        let i = ki * self.integral;

        // Derivative term
        let derivative = if dt > 0.0 {
            (error - self.prev_error) / dt
        } else {
            0.0
        };
        let d = kd * derivative;

        self.prev_error = error;
        self.output = p + i + d;
        self.output
    }

    /// Reset integral windup
    fn reset(&mut self) {
        self.integral = 0.0;
        self.prev_error = 0.0;
        self.output = 0.0;
    }
}

/// Sensor fusion filter for orientation estimation
#[derive(Debug, Clone)]
struct OrientationFilter {
    /// Estimated orientation
    estimate: Orientation,
    /// Complementary filter coefficient (0-1, higher = trust gyro more)
    alpha: f32,
}

impl OrientationFilter {
    fn new() -> Self {
        Self {
            estimate: Orientation::default(),
            alpha: constants::COMPLEMENTARY_ALPHA,
        }
    }

    /// Fuse IMU and Hall sensor data
    ///
    /// Complementary filter: orientation = α × (gyro_integral) + (1-α) × (hall_estimate)
    fn update(
        &mut self,
        gyro_rates: Orientation,      // degrees/second from IMU
        hall_estimate: Orientation,    // absolute estimate from Hall sensors
        dt: f32,
    ) -> Orientation {
        // Integrate gyroscope
        let gyro_pitch = self.estimate.pitch + gyro_rates.pitch * dt;
        let gyro_roll = self.estimate.roll + gyro_rates.roll * dt;
        let gyro_yaw = self.estimate.yaw + gyro_rates.yaw * dt;

        // Complementary filter fusion
        self.estimate.pitch = self.alpha * gyro_pitch + (1.0 - self.alpha) * hall_estimate.pitch;
        self.estimate.roll = self.alpha * gyro_roll + (1.0 - self.alpha) * hall_estimate.roll;
        self.estimate.yaw = self.alpha * gyro_yaw + (1.0 - self.alpha) * hall_estimate.yaw;

        // Normalize yaw to 0-360
        self.estimate.yaw = self.estimate.yaw.rem_euclid(360.0);

        self.estimate
    }

    /// Reset filter to a known state
    fn reset(&mut self, orientation: Orientation) {
        self.estimate = orientation;
    }
}

/// Main PTZ controller
pub struct PtzController {
    /// Current state
    state: PtzState,

    /// Coil array driver
    coils: CoilArray,

    /// Safety verifier
    safety: PtzSafetyVerifier,

    /// PID controller for pitch axis
    pitch_pid: PidState,

    /// PID controller for roll axis
    roll_pid: PidState,

    /// PID controller for yaw axis
    yaw_pid: PidState,

    /// Sensor fusion filter
    orientation_filter: OrientationFilter,

    /// Pan rate for continuous pan mode (deg/s)
    pan_rate: f32,

    /// Levitation height feedback (for safety coordination)
    levitation_height_mm: f32,
}

impl PtzController {
    /// Create a new PTZ controller
    pub fn new() -> Self {
        Self {
            state: PtzState::default(),
            coils: CoilArray::new(),
            safety: PtzSafetyVerifier::new(),
            pitch_pid: PidState::new(),
            roll_pid: PidState::new(),
            yaw_pid: PidState::new(),
            orientation_filter: OrientationFilter::new(),
            pan_rate: 0.0,
            levitation_height_mm: 15.0, // Default float height
        }
    }

    /// Main update loop - call at 500Hz
    ///
    /// # Arguments
    /// * `imu_rates` - Angular rates from IMU (deg/s)
    /// * `hall_orientation` - Absolute orientation estimate from Hall sensors
    /// * `coil_temp` - Average coil temperature (Celsius)
    /// * `dt` - Time step (seconds)
    ///
    /// # Returns
    /// Coil currents to apply
    pub fn update(
        &mut self,
        imu_rates: Orientation,
        hall_orientation: Orientation,
        coil_temp: f32,
        dt: f32,
    ) -> CoilCurrents {
        // 1. Sensor fusion - estimate current orientation
        let current = self.orientation_filter.update(imu_rates, hall_orientation, dt);
        self.state.current = current;
        self.state.coil_temp_c = coil_temp;

        // 2. Safety check
        let safety_state = PtzSafetyState {
            orientation: current,
            coil_temp_c: coil_temp,
            levitation_height_mm: self.levitation_height_mm,
            coil_currents: self.state.currents,
        };
        let safety_result = self.safety.compute_barrier(&safety_state);

        if !safety_result.safe {
            // Apply corrective action
            return self.apply_safety_correction(&safety_result);
        }

        // 3. Mode-specific control
        let currents = match self.state.mode {
            PtzMode::Disabled => {
                // Zero differential, maintain base lift only
                self.coils.calculate_level_currents()
            }

            PtzMode::Hold { target } => {
                self.state.target = target;
                self.control_to_target(dt)
            }

            PtzMode::Track { target, tracking_mode: _ } => {
                self.state.target = target;
                self.control_to_target(dt)
            }

            PtzMode::Pan { rate_deg_s } => {
                // Update yaw target continuously
                self.state.target.yaw = (self.state.target.yaw + rate_deg_s * dt).rem_euclid(360.0);
                self.state.target.pitch = 0.0;
                self.state.target.roll = 0.0;
                self.control_to_target(dt)
            }

            PtzMode::Center => {
                self.state.target = Orientation::level();
                let currents = self.control_to_target(dt);

                // Check if centered
                if self.state.error.pitch.abs() < 1.0
                    && self.state.error.roll.abs() < 1.0
                {
                    self.state.mode = PtzMode::Hold {
                        target: Orientation::level(),
                    };
                }
                currents
            }

            PtzMode::Emergency => {
                // Emergency - go to level with no feedback
                self.pitch_pid.reset();
                self.roll_pid.reset();
                self.yaw_pid.reset();
                self.coils.calculate_level_currents()
            }
        };

        // 4. Store currents
        self.state.currents = currents.as_array();
        self.state.lift_margin = safety_result.lift_margin;
        self.state.stable = safety_result.safe && self.is_stable();

        currents
    }

    /// Control to target orientation using PID
    fn control_to_target(&mut self, dt: f32) -> CoilCurrents {
        // Calculate error
        self.state.error.pitch = self.state.target.pitch - self.state.current.pitch;
        self.state.error.roll = self.state.target.roll - self.state.current.roll;

        // Yaw error needs special handling for wraparound
        let mut yaw_error = self.state.target.yaw - self.state.current.yaw;
        if yaw_error > 180.0 {
            yaw_error -= 360.0;
        } else if yaw_error < -180.0 {
            yaw_error += 360.0;
        }
        self.state.error.yaw = yaw_error;

        // PID control
        let pitch_cmd = self.pitch_pid.update(
            self.state.error.pitch,
            dt,
            constants::KP,
            constants::KI,
            constants::KD,
        );
        let roll_cmd = self.roll_pid.update(
            self.state.error.roll,
            dt,
            constants::KP,
            constants::KI,
            constants::KD,
        );
        let yaw_cmd = self.yaw_pid.update(
            self.state.error.yaw,
            dt,
            constants::KP * 0.5, // Yaw is less aggressive
            constants::KI * 0.3,
            constants::KD * 0.5,
        );

        // Convert PID outputs to coil currents
        self.coils.calculate_currents(pitch_cmd, roll_cmd, yaw_cmd)
    }

    /// Apply safety correction
    fn apply_safety_correction(&mut self, result: &PtzSafetyResult) -> CoilCurrents {
        // Reset PIDs to prevent windup
        if result.lift_margin < 0.0 {
            self.pitch_pid.reset();
            self.roll_pid.reset();
        }

        // Return corrective currents
        self.coils.calculate_corrective_currents(
            result.lift_correction,
            result.tilt_correction,
        )
    }

    /// Check if system is stable (low error)
    fn is_stable(&self) -> bool {
        self.state.error.pitch.abs() < 2.0
            && self.state.error.roll.abs() < 2.0
            && self.state.error.yaw.abs() < 5.0
    }

    /// Set PTZ mode
    pub fn set_mode(&mut self, mode: PtzMode) {
        // Reset PIDs when mode changes
        if self.state.mode != mode {
            self.pitch_pid.reset();
            self.roll_pid.reset();
            self.yaw_pid.reset();
        }
        self.state.mode = mode;
    }

    /// Command: Point to specific orientation
    pub fn point_to(&mut self, orientation: Orientation) {
        let clamped = orientation.clamped();
        self.set_mode(PtzMode::Track {
            target: clamped,
            tracking_mode: TrackingMode::Manual,
        });
    }

    /// Command: Track face at given coordinates
    pub fn track_face(&mut self, pitch: f32, yaw: f32) {
        let target = Orientation::new(pitch, 0.0, yaw).clamped();
        self.set_mode(PtzMode::Track {
            target,
            tracking_mode: TrackingMode::Face,
        });
    }

    /// Command: Track sound source
    pub fn track_sound(&mut self, azimuth_deg: f32, elevation_deg: f32) {
        let target = Orientation::new(elevation_deg, 0.0, azimuth_deg).clamped();
        self.set_mode(PtzMode::Track {
            target,
            tracking_mode: TrackingMode::Sound,
        });
    }

    /// Command: Start continuous pan
    pub fn start_pan(&mut self, rate_deg_s: f32) {
        self.pan_rate = rate_deg_s.clamp(-45.0, 45.0); // Max 45°/s
        self.set_mode(PtzMode::Pan {
            rate_deg_s: self.pan_rate,
        });
    }

    /// Command: Stop and hold current orientation
    pub fn stop(&mut self) {
        self.set_mode(PtzMode::Hold {
            target: self.state.current,
        });
    }

    /// Command: Return to center (level)
    pub fn center(&mut self) {
        self.set_mode(PtzMode::Center);
    }

    /// Command: Disable PTZ control
    pub fn disable(&mut self) {
        self.set_mode(PtzMode::Disabled);
    }

    /// Command: Emergency stop
    pub fn emergency_stop(&mut self) {
        self.set_mode(PtzMode::Emergency);
    }

    /// Update levitation height (for safety coordination)
    pub fn set_levitation_height(&mut self, height_mm: f32) {
        self.levitation_height_mm = height_mm;
    }

    /// Get current state
    pub fn state(&self) -> &PtzState {
        &self.state
    }

    /// Get current orientation
    pub fn orientation(&self) -> Orientation {
        self.state.current
    }

    /// Get current mode
    pub fn mode(&self) -> PtzMode {
        self.state.mode
    }

    /// Check if system is stable
    pub fn is_system_stable(&self) -> bool {
        self.state.stable
    }

    /// Get safety status
    pub fn safety_status(&self) -> PtzSafetyResult {
        let safety_state = PtzSafetyState {
            orientation: self.state.current,
            coil_temp_c: self.state.coil_temp_c,
            levitation_height_mm: self.levitation_height_mm,
            coil_currents: self.state.currents,
        };
        self.safety.compute_barrier(&safety_state)
    }
}

impl Default for PtzController {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_controller_initialization() {
        let controller = PtzController::new();
        assert_eq!(controller.mode(), PtzMode::Disabled);
        assert!(!controller.state().is_active());
    }

    #[test]
    fn test_pid_control() {
        let mut pid = PidState::new();

        // Simulate error converging to zero
        let mut error = 10.0;
        for _ in 0..100 {
            let output = pid.update(error, 0.002, 2.0, 0.5, 0.8);
            error -= output * 0.1; // Simulated response
        }

        // Error should be small after 100 iterations
        assert!(error.abs() < 1.0);
    }

    #[test]
    fn test_yaw_wraparound() {
        let mut controller = PtzController::new();
        controller.set_mode(PtzMode::Hold {
            target: Orientation::new(0.0, 0.0, 350.0),
        });

        // Simulate being at yaw=10 (should take short path)
        controller.state.current.yaw = 10.0;
        controller.control_to_target(0.002);

        // Error should be -20 (not +340)
        assert!((controller.state.error.yaw - (-20.0)).abs() < 0.001);
    }

    #[test]
    fn test_mode_transitions() {
        let mut controller = PtzController::new();

        controller.point_to(Orientation::new(10.0, 5.0, 45.0));
        assert!(matches!(controller.mode(), PtzMode::Track { .. }));

        controller.start_pan(30.0);
        assert!(matches!(controller.mode(), PtzMode::Pan { .. }));

        controller.stop();
        assert!(matches!(controller.mode(), PtzMode::Hold { .. }));

        controller.center();
        assert!(matches!(controller.mode(), PtzMode::Center));

        controller.disable();
        assert!(matches!(controller.mode(), PtzMode::Disabled));

        controller.emergency_stop();
        assert!(matches!(controller.mode(), PtzMode::Emergency));
    }
}
