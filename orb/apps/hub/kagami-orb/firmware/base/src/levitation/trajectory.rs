//! Smooth trajectory generation for height control
//!
//! Provides S-curve trajectories for smooth height transitions and
//! periodic animations for bobble effects.

use core::f32::consts::PI;
use libm::{sinf, cosf};

/// Trajectory generator for smooth height transitions
///
/// Uses an S-curve (smoothstep) profile for natural motion:
/// - Zero velocity at start and end
/// - Maximum velocity at midpoint
/// - No jerky accelerations
#[derive(Debug, Clone, Copy)]
pub struct HeightTrajectory {
    /// Starting height (mm)
    pub start_height: f32,

    /// Target height (mm)
    pub target_height: f32,

    /// Total duration (seconds)
    pub duration: f32,

    /// Elapsed time (seconds)
    pub elapsed: f32,
}

impl HeightTrajectory {
    /// Create a new trajectory
    pub fn new(start: f32, target: f32, duration_s: f32) -> Self {
        Self {
            start_height: start,
            target_height: target,
            duration: duration_s.max(0.1), // Minimum 100ms
            elapsed: 0.0,
        }
    }

    /// Create a trajectory from current height to charging position
    pub fn to_charging(current_height: f32) -> Self {
        Self::new(current_height, super::constants::HEIGHT_CHARGE_MM, 2.0)
    }

    /// Create a trajectory from current height to float position
    pub fn to_float(current_height: f32) -> Self {
        Self::new(current_height, super::constants::HEIGHT_FLOAT_MM, 1.5)
    }

    /// Sample the trajectory at time t
    ///
    /// Returns the target height at the given time.
    pub fn sample(&self, t: f32) -> f32 {
        if t >= self.duration {
            return self.target_height;
        }
        if t <= 0.0 {
            return self.start_height;
        }

        // Normalized time [0, 1]
        let s = t / self.duration;

        // S-curve: 3s² - 2s³ (smoothstep)
        let blend = s * s * (3.0 - 2.0 * s);

        self.start_height + blend * (self.target_height - self.start_height)
    }

    /// Sample velocity at time t (mm/s)
    pub fn sample_velocity(&self, t: f32) -> f32 {
        if t <= 0.0 || t >= self.duration {
            return 0.0;
        }

        let s = t / self.duration;

        // Derivative of smoothstep: 6s(1-s)
        let blend_deriv = 6.0 * s * (1.0 - s);

        blend_deriv * (self.target_height - self.start_height) / self.duration
    }

    /// Update elapsed time, returns true if complete
    pub fn update(&mut self, dt: f32) -> bool {
        self.elapsed += dt;
        self.elapsed >= self.duration
    }

    /// Get current position based on elapsed time
    pub fn current(&self) -> f32 {
        self.sample(self.elapsed)
    }

    /// Get current velocity based on elapsed time
    pub fn current_velocity(&self) -> f32 {
        self.sample_velocity(self.elapsed)
    }

    /// Check if trajectory is complete
    pub fn is_complete(&self) -> bool {
        self.elapsed >= self.duration
    }

    /// Get progress as fraction [0, 1]
    pub fn progress(&self) -> f32 {
        (self.elapsed / self.duration).min(1.0)
    }
}

/// Bobble animation generator
///
/// Creates a smooth sinusoidal oscillation for expressive "breathing"
/// or "nodding" animations while floating.
#[derive(Debug, Clone, Copy)]
pub struct BobbleAnimation {
    /// Center height (mm)
    pub center_height: f32,

    /// Oscillation amplitude (mm)
    pub amplitude: f32,

    /// Oscillation frequency (Hz)
    pub frequency: f32,

    /// Phase offset (radians)
    pub phase: f32,

    /// Optional duration limit (seconds)
    pub duration: Option<f32>,

    /// Elapsed time (seconds)
    pub elapsed: f32,
}

impl BobbleAnimation {
    /// Create a new bobble animation
    pub fn new(center: f32, amplitude: f32, frequency: f32) -> Self {
        Self {
            center_height: center,
            amplitude,
            frequency,
            phase: 0.0,
            duration: None,
            elapsed: 0.0,
        }
    }

    /// Set animation duration (None = infinite)
    pub fn with_duration(mut self, seconds: f32) -> Self {
        self.duration = Some(seconds);
        self
    }

    /// Set initial phase (radians)
    pub fn with_phase(mut self, phase: f32) -> Self {
        self.phase = phase;
        self
    }

    /// Create a gentle breathing animation
    pub fn breathing(center: f32) -> Self {
        Self::new(center, 3.0, 0.3)
    }

    /// Create an excited/alert animation
    pub fn excited(center: f32) -> Self {
        Self::new(center, 5.0, 0.8)
    }

    /// Create a nodding/acknowledgment animation
    pub fn nod(center: f32) -> Self {
        Self::new(center, 4.0, 1.2)
            .with_duration(2.0)
    }

    /// Sample the animation at time t
    pub fn sample(&self, t: f32) -> f32 {
        // Check duration limit
        if let Some(dur) = self.duration {
            if t >= dur {
                return self.center_height;
            }
        }

        let omega = 2.0 * PI * self.frequency;
        self.center_height + self.amplitude * sinf(omega * t + self.phase)
    }

    /// Sample velocity at time t (mm/s)
    pub fn sample_velocity(&self, t: f32) -> f32 {
        if let Some(dur) = self.duration {
            if t >= dur {
                return 0.0;
            }
        }

        let omega = 2.0 * PI * self.frequency;
        self.amplitude * omega * cosf(omega * t + self.phase)
    }

    /// Update elapsed time, returns true if complete
    pub fn update(&mut self, dt: f32) -> bool {
        self.elapsed += dt;
        if let Some(dur) = self.duration {
            self.elapsed >= dur
        } else {
            false // Infinite animation never completes
        }
    }

    /// Get current position based on elapsed time
    pub fn current(&self) -> f32 {
        self.sample(self.elapsed)
    }

    /// Get current velocity based on elapsed time
    pub fn current_velocity(&self) -> f32 {
        self.sample_velocity(self.elapsed)
    }

    /// Check if animation is complete
    pub fn is_complete(&self) -> bool {
        if let Some(dur) = self.duration {
            self.elapsed >= dur
        } else {
            false
        }
    }
}

/// Combined height motion generator
///
/// Manages both trajectories and animations, providing a unified
/// interface for height control.
#[derive(Debug, Default)]
pub struct HeightMotionGenerator {
    trajectory: Option<HeightTrajectory>,
    animation: Option<BobbleAnimation>,
    baseline_height: f32,
}

impl HeightMotionGenerator {
    /// Create a new motion generator with default float height
    pub fn new() -> Self {
        Self {
            trajectory: None,
            animation: None,
            baseline_height: super::constants::HEIGHT_FLOAT_MM,
        }
    }

    /// Start a new trajectory (cancels any existing animation)
    pub fn start_trajectory(&mut self, traj: HeightTrajectory) {
        self.animation = None;
        self.trajectory = Some(traj);
    }

    /// Start a new animation at current baseline
    pub fn start_animation(&mut self, anim: BobbleAnimation) {
        self.trajectory = None;
        self.animation = Some(anim);
    }

    /// Stop all motion, hold at current height
    pub fn stop(&mut self, current_height: f32) {
        self.trajectory = None;
        self.animation = None;
        self.baseline_height = current_height;
    }

    /// Update the motion generator
    ///
    /// Returns (target_height, target_velocity)
    pub fn update(&mut self, dt: f32) -> (f32, f32) {
        // Priority: trajectory > animation > baseline

        if let Some(ref mut traj) = self.trajectory {
            if traj.update(dt) {
                // Trajectory complete
                self.baseline_height = traj.target_height;
                self.trajectory = None;
                return (self.baseline_height, 0.0);
            }
            return (traj.current(), traj.current_velocity());
        }

        if let Some(ref mut anim) = self.animation {
            if anim.update(dt) {
                // Animation complete
                self.animation = None;
                return (self.baseline_height, 0.0);
            }
            return (anim.current(), anim.current_velocity());
        }

        (self.baseline_height, 0.0)
    }

    /// Check if any motion is active
    pub fn is_active(&self) -> bool {
        self.trajectory.is_some() || self.animation.is_some()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_trajectory_smoothstep() {
        let traj = HeightTrajectory::new(20.0, 5.0, 2.0);

        // At t=0, should be at start
        assert!((traj.sample(0.0) - 20.0).abs() < 0.01);

        // At t=duration, should be at target
        assert!((traj.sample(2.0) - 5.0).abs() < 0.01);

        // At t=duration/2, should be at midpoint
        assert!((traj.sample(1.0) - 12.5).abs() < 0.5);

        // Velocity should be zero at endpoints
        assert!(traj.sample_velocity(0.0).abs() < 0.01);
        assert!(traj.sample_velocity(2.0).abs() < 0.01);

        // Velocity should be maximum at midpoint
        let v_mid = traj.sample_velocity(1.0);
        assert!(v_mid.abs() > 5.0); // Should be moving fast
    }

    #[test]
    fn test_bobble_animation() {
        let anim = BobbleAnimation::new(20.0, 5.0, 1.0);

        // At t=0, should be at center (sin(0) = 0)
        assert!((anim.sample(0.0) - 20.0).abs() < 0.01);

        // At t=0.25 (quarter period), should be at max
        assert!((anim.sample(0.25) - 25.0).abs() < 0.5);

        // At t=0.75 (3/4 period), should be at min
        assert!((anim.sample(0.75) - 15.0).abs() < 0.5);

        // At t=1.0 (full period), should be back at center
        assert!((anim.sample(1.0) - 20.0).abs() < 0.5);
    }

    #[test]
    fn test_motion_generator() {
        let mut gen = HeightMotionGenerator::new();

        // Start a trajectory
        gen.start_trajectory(HeightTrajectory::new(20.0, 5.0, 1.0));
        assert!(gen.is_active());

        // Update halfway
        let (h, v) = gen.update(0.5);
        assert!(h > 5.0 && h < 20.0);
        assert!(v.abs() > 0.0);

        // Complete the trajectory
        gen.update(0.6);
        assert!(!gen.is_active());
    }
}
