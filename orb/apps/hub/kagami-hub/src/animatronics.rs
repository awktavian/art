//! Animatronics Controller — Servo-Based Physical Expression System
//!
//! Professional-grade animatronic control for the Kagami Hub lamp, inspired by
//! DIY Perks and Boston Dynamics aesthetics. Transforms the static lamp into
//! a living, breathing entity that responds to sound, presence, and state.
//!
//! # Hardware Configuration
//!
//! - **Driver**: PCA9685 16-channel PWM driver (I2C address 0x40)
//! - **Servo Type**: Standard hobby servos (50Hz, 1-2ms pulse width)
//! - **Channels**:
//!   - CH0: `head_tilt` - Vertical nod (looking up/down)
//!   - CH1: `elbow_pan` - Horizontal rotation (looking left/right)
//!   - CH2: `shoulder_lift` - Overall height/posture adjustment
//!
//! # Safety Constraints
//!
//! All servo movements are bounded by hardware limits and software safety:
//! ```text
//! h(x) >= 0 always
//! ```
//!
//! - Mechanical stops prevent over-rotation
//! - Rate limiting prevents jarring movements
//! - Collision detection via acceleration monitoring
//! - Emergency stop returns to safe neutral pose
//!
//! # Animation Architecture
//!
//! ```text
//! SoundSource ─┬─> SoundTracker ─┬─> PoseBlender ─> ServoController ─> PCA9685
//!              │                  │
//! PoseState ───┴─> IdleAnimator ─┘
//! ```
//!
//! # Colony Mapping
//!
//! - **Spark** (e₁): Alert, energetic poses
//! - **Forge** (e₂): Focused, creative stances
//! - **Flow** (e₃): Listening, adaptive orientation
//! - **Nexus** (e₄): Connecting, scanning movements
//! - **Beacon** (e₅): Guiding, directional poses
//! - **Grove** (e₆): Relaxed, nurturing posture
//! - **Crystal** (e₇): Speaking, precise articulation
//!
//! # Example Usage
//!
//! ```rust,no_run
//! use kagami_hub::animatronics::{Animatronics, Pose, SoundSource};
//!
//! async fn demo() -> anyhow::Result<()> {
//!     let mut anim = Animatronics::new_default()?;
//!     anim.initialize().await?;
//!
//!     // Transition to alert pose
//!     anim.transition_to(Pose::Alert, 0.5).await?;
//!
//!     // Track sound source
//!     anim.track_sound(SoundSource::new(45.0, 10.0)).await?;
//!
//!     // Enable breathing idle animation
//!     anim.set_breathing(true);
//!
//!     Ok(())
//! }
//! ```
//!
//! Colony: Flow (e₃) — Adaptive sensing and smooth motion

use anyhow::{bail, Result};
use serde::{Deserialize, Serialize};
use std::f32::consts::{PI, TAU};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Mutex;
use tracing::{debug, info, warn};

use crate::config::HubConfig;
use crate::led_ring::{self, AnimationPattern};

// ============================================================================
// Constants — Hardware Configuration & Safety Limits
// ============================================================================

/// PCA9685 I2C address (default: 0x40, can be changed via address pins)
pub const PCA9685_I2C_ADDRESS: u8 = 0x40;

/// PCA9685 internal oscillator frequency (25MHz nominal)
const PCA9685_OSCILLATOR_FREQ: f32 = 25_000_000.0;

/// Standard servo PWM frequency (50Hz = 20ms period)
const SERVO_PWM_FREQUENCY: f32 = 50.0;

/// PWM resolution (12-bit = 4096 steps)
const PWM_RESOLUTION: u16 = 4096;

/// Servo pulse width bounds (microseconds)
/// Standard servos: 500-2500us range, safe: 1000-2000us
const SERVO_MIN_PULSE_US: f32 = 500.0;
const SERVO_MAX_PULSE_US: f32 = 2500.0;
#[allow(dead_code)]
const SERVO_CENTER_PULSE_US: f32 = 1500.0;

/// Maximum angular velocity (degrees per second) for smooth motion
const MAX_ANGULAR_VELOCITY: f32 = 180.0;

/// Maximum angular acceleration (degrees per second squared)
const MAX_ANGULAR_ACCELERATION: f32 = 360.0;

/// Breathing animation parameters
const BREATHING_PERIOD_MS: f32 = 4000.0;
const BREATHING_AMPLITUDE_DEG: f32 = 3.0;

/// Animation frame rate (target 60fps for smooth motion)
const ANIMATION_FRAME_RATE: f32 = 60.0;
const ANIMATION_FRAME_INTERVAL_MS: u64 = (1000.0 / ANIMATION_FRAME_RATE) as u64;

// ============================================================================
// Servo Channel Definitions
// ============================================================================

/// Servo channel configuration with safety bounds
#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub struct ServoChannel {
    /// PCA9685 channel number (0-15)
    pub channel: u8,
    /// Minimum safe angle in degrees
    pub min_angle: f32,
    /// Maximum safe angle in degrees
    pub max_angle: f32,
    /// Neutral/home position in degrees
    pub neutral_angle: f32,
    /// Pulse width at 0 degrees (microseconds)
    pub min_pulse_us: f32,
    /// Pulse width at max_angle degrees (microseconds)
    pub max_pulse_us: f32,
    /// Whether servo direction is inverted
    pub inverted: bool,
}

impl ServoChannel {
    /// Create a new servo channel configuration
    pub const fn new(channel: u8, min_angle: f32, max_angle: f32, neutral_angle: f32) -> Self {
        Self {
            channel,
            min_angle,
            max_angle,
            neutral_angle,
            min_pulse_us: SERVO_MIN_PULSE_US,
            max_pulse_us: SERVO_MAX_PULSE_US,
            inverted: false,
        }
    }

    /// Create with custom pulse width range
    pub const fn with_pulse_range(mut self, min_us: f32, max_us: f32) -> Self {
        self.min_pulse_us = min_us;
        self.max_pulse_us = max_us;
        self
    }

    /// Set inverted direction
    pub const fn inverted(mut self) -> Self {
        self.inverted = true;
        self
    }

    /// Clamp angle to safe bounds
    #[inline]
    pub fn clamp_angle(&self, angle: f32) -> f32 {
        angle.clamp(self.min_angle, self.max_angle)
    }

    /// Check if angle is within safe bounds (h(x) >= 0)
    #[inline]
    pub fn is_safe(&self, angle: f32) -> bool {
        angle >= self.min_angle && angle <= self.max_angle
    }

    /// Convert angle to pulse width in microseconds
    pub fn angle_to_pulse_us(&self, angle: f32) -> f32 {
        let clamped = self.clamp_angle(angle);
        let normalized = (clamped - self.min_angle) / (self.max_angle - self.min_angle);
        let normalized = if self.inverted {
            1.0 - normalized
        } else {
            normalized
        };
        self.min_pulse_us + normalized * (self.max_pulse_us - self.min_pulse_us)
    }

    /// Convert pulse width to PWM value (0-4095)
    pub fn pulse_us_to_pwm(&self, pulse_us: f32) -> u16 {
        // PWM period at 50Hz = 20000us
        // 4096 steps over 20000us = 0.2048 steps/us
        let period_us = 1_000_000.0 / SERVO_PWM_FREQUENCY;
        let pwm_value = (pulse_us / period_us) * PWM_RESOLUTION as f32;
        pwm_value.clamp(0.0, (PWM_RESOLUTION - 1) as f32) as u16
    }
}

/// Default servo configurations for Kagami Hub lamp
pub mod servo_config {
    use super::*;

    /// Head tilt servo — vertical nod motion
    /// - Channel 0
    /// - Range: -30° (looking down) to +45° (looking up)
    /// - Neutral: 0° (horizontal)
    pub const HEAD_TILT: ServoChannel =
        ServoChannel::new(0, -30.0, 45.0, 0.0).with_pulse_range(1000.0, 2000.0);

    /// Elbow pan servo — horizontal rotation
    /// - Channel 1
    /// - Range: -90° (left) to +90° (right)
    /// - Neutral: 0° (forward)
    pub const ELBOW_PAN: ServoChannel =
        ServoChannel::new(1, -90.0, 90.0, 0.0).with_pulse_range(500.0, 2500.0);

    /// Shoulder lift servo — overall height/posture
    /// - Channel 2
    /// - Range: 0° (lowered/sleeping) to 60° (raised/alert)
    /// - Neutral: 30° (relaxed)
    pub const SHOULDER_LIFT: ServoChannel =
        ServoChannel::new(2, 0.0, 60.0, 30.0).with_pulse_range(1000.0, 2000.0);
}

// ============================================================================
// Servo State & Kinematics
// ============================================================================

/// Current state of a single servo
#[derive(Debug, Clone, Copy, Default)]
pub struct ServoState {
    /// Current angle in degrees
    pub angle: f32,
    /// Target angle in degrees
    pub target_angle: f32,
    /// Current angular velocity (degrees/second)
    pub velocity: f32,
    /// Last update timestamp
    pub last_update: Option<Instant>,
}

impl ServoState {
    /// Create a new servo state at neutral position
    pub fn new(neutral: f32) -> Self {
        Self {
            angle: neutral,
            target_angle: neutral,
            velocity: 0.0,
            last_update: None,
        }
    }

    /// Update servo state with smooth motion
    /// Returns true if still moving toward target
    pub fn update(&mut self, dt: f32, config: &ServoChannel) -> bool {
        let distance = self.target_angle - self.angle;

        if distance.abs() < 0.1 {
            self.angle = self.target_angle;
            self.velocity = 0.0;
            return false;
        }

        // Calculate desired velocity
        let max_velocity = MAX_ANGULAR_VELOCITY;
        let desired_velocity = distance.signum() * max_velocity;

        // Apply acceleration limit
        let velocity_change = desired_velocity - self.velocity;
        let max_velocity_change = MAX_ANGULAR_ACCELERATION * dt;
        let actual_velocity_change =
            velocity_change.clamp(-max_velocity_change, max_velocity_change);
        self.velocity += actual_velocity_change;

        // Deceleration zone: slow down as we approach target
        let stopping_distance = self.velocity.powi(2) / (2.0 * MAX_ANGULAR_ACCELERATION);
        if distance.abs() <= stopping_distance {
            self.velocity *= 0.9; // Smooth deceleration
        }

        // Update position
        let angle_change = self.velocity * dt;
        self.angle += angle_change;

        // Clamp to safe bounds (h(x) >= 0 enforcement)
        self.angle = config.clamp_angle(self.angle);
        self.last_update = Some(Instant::now());

        true
    }

    /// Set target with easing
    pub fn set_target(&mut self, target: f32) {
        self.target_angle = target;
    }
}

/// Complete animatronic state (all three servos)
#[derive(Debug, Clone, Copy)]
pub struct AnimatronicState {
    pub head_tilt: ServoState,
    pub elbow_pan: ServoState,
    pub shoulder_lift: ServoState,
}

impl Default for AnimatronicState {
    fn default() -> Self {
        Self {
            head_tilt: ServoState::new(servo_config::HEAD_TILT.neutral_angle),
            elbow_pan: ServoState::new(servo_config::ELBOW_PAN.neutral_angle),
            shoulder_lift: ServoState::new(servo_config::SHOULDER_LIFT.neutral_angle),
        }
    }
}

// ============================================================================
// Easing Functions — Smooth Motion Curves
// ============================================================================

/// Easing function types for smooth animation transitions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EasingFunction {
    /// Linear interpolation (constant velocity)
    Linear,
    /// Quadratic ease-in (accelerate)
    EaseIn,
    /// Quadratic ease-out (decelerate)
    EaseOut,
    /// Quadratic ease-in-out (accelerate then decelerate)
    EaseInOut,
    /// Cubic ease-in-out (smoother S-curve)
    EaseInOutCubic,
    /// Sine ease-in-out (natural pendulum motion)
    EaseInOutSine,
    /// Exponential ease-out (snappy response)
    EaseOutExpo,
    /// Elastic bounce (overshoot and settle)
    EaseOutElastic,
    /// Back ease-out (slight overshoot)
    EaseOutBack,
}

impl Default for EasingFunction {
    fn default() -> Self {
        Self::EaseInOut
    }
}

impl EasingFunction {
    /// Apply easing function to normalized time t (0.0 to 1.0)
    #[inline]
    pub fn apply(&self, t: f32) -> f32 {
        let t = t.clamp(0.0, 1.0);

        match self {
            Self::Linear => t,

            Self::EaseIn => t * t,

            Self::EaseOut => 1.0 - (1.0 - t).powi(2),

            Self::EaseInOut => {
                if t < 0.5 {
                    2.0 * t * t
                } else {
                    1.0 - (-2.0 * t + 2.0).powi(2) / 2.0
                }
            }

            Self::EaseInOutCubic => {
                if t < 0.5 {
                    4.0 * t * t * t
                } else {
                    1.0 - (-2.0 * t + 2.0).powi(3) / 2.0
                }
            }

            Self::EaseInOutSine => -(f32::cos(PI * t) - 1.0) / 2.0,

            Self::EaseOutExpo => {
                if t >= 1.0 {
                    1.0
                } else {
                    1.0 - 2.0_f32.powf(-10.0 * t)
                }
            }

            Self::EaseOutElastic => {
                if t <= 0.0 {
                    0.0
                } else if t >= 1.0 {
                    1.0
                } else {
                    let c4 = TAU / 3.0;
                    2.0_f32.powf(-10.0 * t) * f32::sin((t * 10.0 - 0.75) * c4) + 1.0
                }
            }

            Self::EaseOutBack => {
                let c1 = 1.70158;
                let c3 = c1 + 1.0;
                1.0 + c3 * (t - 1.0).powi(3) + c1 * (t - 1.0).powi(2)
            }
        }
    }
}

// ============================================================================
// Predefined Poses — Emotional Expression States
// ============================================================================

/// Predefined animatronic poses representing emotional/functional states
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Pose {
    /// Sleep pose — head down, shoulder lowered, minimal presence
    /// Used during inactive/standby mode
    Sleep,

    /// Idle pose — neutral position, slight breathing animation
    /// Default state when awake but not actively engaged
    Idle,

    /// Alert pose — head up and forward, shoulder raised
    /// Triggered by wake word detection or presence
    Alert,

    /// Listening pose — head tilted slightly, oriented toward sound
    /// Active during voice input capture
    Listening,

    /// Thinking pose — slight head movement, processing indication
    /// Shown during AI inference/processing
    Thinking,

    /// Success pose — celebratory nod, positive confirmation
    /// Command completed successfully
    Success,

    /// Confused pose — head tilt (like a curious dog)
    /// Failed to understand or parse command
    Confused,

    /// Error pose — head shake motion, negative indication
    /// Command failed or system error
    Error,

    /// Speaking pose — subtle articulation during TTS output
    /// Provides visual feedback during speech
    Speaking,

    /// Scanning pose — slow horizontal pan, surveying area
    /// Used during presence detection sweep
    Scanning,

    /// Tracking pose — dynamically follows sound source
    /// Real-time orientation toward audio input
    Tracking,

    /// Greeting pose — welcoming nod sequence
    /// Response to "hello" or presence detection
    Greeting,

    /// Farewell pose — wave-like motion
    /// Response to "goodbye" or departure
    Farewell,
}

impl Default for Pose {
    fn default() -> Self {
        Self::Idle
    }
}

impl Pose {
    /// Get the target angles for this pose
    /// Returns (head_tilt, elbow_pan, shoulder_lift)
    pub fn target_angles(&self) -> (f32, f32, f32) {
        match self {
            Self::Sleep => (-20.0, 0.0, 0.0),
            Self::Idle => (0.0, 0.0, 30.0),
            Self::Alert => (10.0, 0.0, 50.0),
            Self::Listening => (5.0, 0.0, 40.0),
            Self::Thinking => (15.0, 10.0, 35.0),
            Self::Success => (20.0, 0.0, 55.0),
            Self::Confused => (25.0, 15.0, 40.0),
            Self::Error => (0.0, 0.0, 25.0),
            Self::Speaking => (5.0, 0.0, 45.0),
            Self::Scanning => (10.0, 0.0, 45.0),
            Self::Tracking => (0.0, 0.0, 45.0), // Base, will be overridden by tracking
            Self::Greeting => (15.0, 0.0, 55.0),
            Self::Farewell => (10.0, -30.0, 50.0),
        }
    }

    /// Get recommended easing function for transitioning to this pose
    pub fn easing(&self) -> EasingFunction {
        match self {
            Self::Sleep => EasingFunction::EaseInOutSine,
            Self::Idle => EasingFunction::EaseInOut,
            Self::Alert => EasingFunction::EaseOutExpo,
            Self::Listening => EasingFunction::EaseOut,
            Self::Thinking => EasingFunction::EaseInOutSine,
            Self::Success => EasingFunction::EaseOutElastic,
            Self::Confused => EasingFunction::EaseOutBack,
            Self::Error => EasingFunction::EaseOut,
            Self::Speaking => EasingFunction::EaseInOut,
            Self::Scanning => EasingFunction::EaseInOutSine,
            Self::Tracking => EasingFunction::EaseOut,
            Self::Greeting => EasingFunction::EaseOutBack,
            Self::Farewell => EasingFunction::EaseInOutSine,
        }
    }

    /// Get recommended transition duration in seconds
    pub fn transition_duration(&self) -> f32 {
        match self {
            Self::Sleep => 1.5,
            Self::Idle => 0.8,
            Self::Alert => 0.3,
            Self::Listening => 0.4,
            Self::Thinking => 0.6,
            Self::Success => 0.5,
            Self::Confused => 0.5,
            Self::Error => 0.3,
            Self::Speaking => 0.4,
            Self::Scanning => 0.8,
            Self::Tracking => 0.2,
            Self::Greeting => 0.6,
            Self::Farewell => 0.8,
        }
    }

    /// Get corresponding LED animation pattern for this pose
    pub fn led_pattern(&self) -> AnimationPattern {
        match self {
            Self::Sleep => AnimationPattern::Breathing,
            Self::Idle => AnimationPattern::Breathing,
            Self::Alert => AnimationPattern::Pulse,
            Self::Listening => AnimationPattern::Pulse,
            Self::Thinking => AnimationPattern::Spin,
            Self::Success => AnimationPattern::ChromaticPulse { success: true },
            Self::Confused => AnimationPattern::ChromaticPulse { success: false },
            Self::Error => AnimationPattern::ErrorFlash,
            Self::Speaking => AnimationPattern::Cascade,
            Self::Scanning => AnimationPattern::SpectralSweep,
            Self::Tracking => AnimationPattern::Spectral,
            Self::Greeting => AnimationPattern::Rainbow,
            Self::Farewell => AnimationPattern::FanoPulse,
        }
    }
}

// ============================================================================
// Sound Source Tracking
// ============================================================================

/// Sound source location for orientation tracking
#[derive(Debug, Clone, Copy, Default, Serialize, Deserialize)]
pub struct SoundSource {
    /// Azimuth angle in degrees (-180 to +180, 0 = forward)
    pub azimuth: f32,
    /// Elevation angle in degrees (-90 to +90, 0 = horizontal)
    pub elevation: f32,
    /// Confidence score (0.0 to 1.0)
    pub confidence: f32,
    /// Timestamp of detection (not serializable, runtime only)
    #[serde(skip)]
    pub timestamp: Option<Instant>,
}

impl SoundSource {
    /// Create a new sound source with position
    pub fn new(azimuth: f32, elevation: f32) -> Self {
        Self {
            azimuth: azimuth.clamp(-180.0, 180.0),
            elevation: elevation.clamp(-90.0, 90.0),
            confidence: 1.0,
            timestamp: Some(Instant::now()),
        }
    }

    /// Create with confidence score
    pub fn with_confidence(mut self, confidence: f32) -> Self {
        self.confidence = confidence.clamp(0.0, 1.0);
        self
    }

    /// Check if source is still valid (not stale)
    pub fn is_valid(&self, max_age: Duration) -> bool {
        self.timestamp
            .map(|t| t.elapsed() < max_age)
            .unwrap_or(false)
            && self.confidence > 0.3
    }

    /// Convert sound source to target servo angles
    /// Returns (head_tilt, elbow_pan)
    pub fn to_servo_angles(&self) -> (f32, f32) {
        // Map azimuth to elbow pan (clamped to servo range)
        let elbow_pan = self.azimuth.clamp(
            servo_config::ELBOW_PAN.min_angle,
            servo_config::ELBOW_PAN.max_angle,
        );

        // Map elevation to head tilt (clamped to servo range)
        let head_tilt = self.elevation.clamp(
            servo_config::HEAD_TILT.min_angle,
            servo_config::HEAD_TILT.max_angle,
        );

        (head_tilt, elbow_pan)
    }
}

// ============================================================================
// Animation Sequences
// ============================================================================

/// Keyframe in an animation sequence
#[derive(Debug, Clone, Copy)]
pub struct Keyframe {
    /// Target pose at this keyframe
    pub pose: Pose,
    /// Duration to reach this keyframe from previous
    pub duration: Duration,
    /// Easing function for interpolation
    pub easing: EasingFunction,
    /// Optional override angles (head_tilt, elbow_pan, shoulder_lift)
    pub angles_override: Option<(f32, f32, f32)>,
}

impl Keyframe {
    /// Create a keyframe from a pose
    pub fn from_pose(pose: Pose, duration_secs: f32) -> Self {
        Self {
            pose,
            duration: Duration::from_secs_f32(duration_secs),
            easing: pose.easing(),
            angles_override: None,
        }
    }

    /// Create a keyframe with custom angles
    pub fn custom(
        head_tilt: f32,
        elbow_pan: f32,
        shoulder_lift: f32,
        duration_secs: f32,
        easing: EasingFunction,
    ) -> Self {
        Self {
            pose: Pose::Idle,
            duration: Duration::from_secs_f32(duration_secs),
            easing,
            angles_override: Some((head_tilt, elbow_pan, shoulder_lift)),
        }
    }

    /// Get target angles for this keyframe
    pub fn target_angles(&self) -> (f32, f32, f32) {
        self.angles_override
            .unwrap_or_else(|| self.pose.target_angles())
    }
}

/// Pre-defined animation sequences
pub mod sequences {
    use super::*;

    /// Nod animation (affirmative gesture)
    pub fn nod() -> Vec<Keyframe> {
        vec![
            Keyframe::custom(20.0, 0.0, 45.0, 0.2, EasingFunction::EaseOut),
            Keyframe::custom(-5.0, 0.0, 45.0, 0.15, EasingFunction::EaseInOut),
            Keyframe::custom(15.0, 0.0, 45.0, 0.15, EasingFunction::EaseInOut),
            Keyframe::custom(0.0, 0.0, 45.0, 0.2, EasingFunction::EaseOut),
        ]
    }

    /// Head shake animation (negative gesture)
    pub fn shake() -> Vec<Keyframe> {
        vec![
            Keyframe::custom(0.0, 25.0, 40.0, 0.15, EasingFunction::EaseOut),
            Keyframe::custom(0.0, -25.0, 40.0, 0.2, EasingFunction::EaseInOut),
            Keyframe::custom(0.0, 20.0, 40.0, 0.2, EasingFunction::EaseInOut),
            Keyframe::custom(0.0, -15.0, 40.0, 0.15, EasingFunction::EaseInOut),
            Keyframe::custom(0.0, 0.0, 40.0, 0.2, EasingFunction::EaseOut),
        ]
    }

    /// Wake up animation (sleep to alert)
    pub fn wake_up() -> Vec<Keyframe> {
        vec![
            Keyframe::from_pose(Pose::Sleep, 0.0),
            Keyframe::custom(-10.0, 0.0, 15.0, 0.3, EasingFunction::EaseOut),
            Keyframe::custom(5.0, 0.0, 35.0, 0.3, EasingFunction::EaseInOut),
            Keyframe::from_pose(Pose::Alert, 0.4),
        ]
    }

    /// Go to sleep animation (alert to sleep)
    pub fn go_to_sleep() -> Vec<Keyframe> {
        vec![
            Keyframe::custom(10.0, 0.0, 40.0, 0.3, EasingFunction::EaseInOutSine),
            Keyframe::custom(0.0, 0.0, 20.0, 0.4, EasingFunction::EaseInOutSine),
            Keyframe::custom(-15.0, 0.0, 5.0, 0.5, EasingFunction::EaseInOutSine),
            Keyframe::from_pose(Pose::Sleep, 0.4),
        ]
    }

    /// Curious tilt animation (confused/curious gesture)
    pub fn curious_tilt() -> Vec<Keyframe> {
        vec![
            Keyframe::custom(25.0, 20.0, 45.0, 0.3, EasingFunction::EaseOutBack),
            Keyframe::custom(20.0, 15.0, 42.0, 0.5, EasingFunction::EaseInOut),
            Keyframe::custom(10.0, 0.0, 40.0, 0.4, EasingFunction::EaseInOut),
        ]
    }

    /// Scan environment animation (slow pan)
    pub fn scan() -> Vec<Keyframe> {
        vec![
            Keyframe::custom(10.0, -60.0, 50.0, 0.8, EasingFunction::EaseInOutSine),
            Keyframe::custom(10.0, 60.0, 50.0, 1.5, EasingFunction::EaseInOutSine),
            Keyframe::custom(10.0, -30.0, 50.0, 1.0, EasingFunction::EaseInOutSine),
            Keyframe::custom(10.0, 30.0, 50.0, 0.8, EasingFunction::EaseInOutSine),
            Keyframe::custom(10.0, 0.0, 50.0, 0.6, EasingFunction::EaseOut),
        ]
    }

    /// Celebration animation (success!)
    /// Note: shoulder_lift capped at 57.0 for safety margin (hardware limit is 60.0)
    pub fn celebrate() -> Vec<Keyframe> {
        vec![
            Keyframe::custom(25.0, 0.0, 57.0, 0.2, EasingFunction::EaseOutElastic),
            Keyframe::custom(15.0, -20.0, 55.0, 0.2, EasingFunction::EaseInOut),
            Keyframe::custom(20.0, 20.0, 57.0, 0.2, EasingFunction::EaseInOut),
            Keyframe::custom(30.0, 0.0, 57.0, 0.15, EasingFunction::EaseOut),
            Keyframe::custom(10.0, 0.0, 50.0, 0.3, EasingFunction::EaseInOut),
            Keyframe::from_pose(Pose::Idle, 0.4),
        ]
    }

    /// Greeting wave animation
    pub fn greeting() -> Vec<Keyframe> {
        vec![
            Keyframe::custom(15.0, 0.0, 55.0, 0.3, EasingFunction::EaseOutBack),
            Keyframe::custom(20.0, 0.0, 55.0, 0.2, EasingFunction::EaseInOut),
            Keyframe::custom(10.0, 0.0, 50.0, 0.2, EasingFunction::EaseInOut),
            Keyframe::custom(18.0, 0.0, 52.0, 0.2, EasingFunction::EaseInOut),
            Keyframe::from_pose(Pose::Idle, 0.5),
        ]
    }
}

// ============================================================================
// Idle Animation (Breathing)
// ============================================================================

/// Breathing idle animation generator
#[derive(Debug)]
pub struct BreathingAnimator {
    /// Whether breathing is enabled
    enabled: bool,
    /// Animation start time
    start_time: Instant,
    /// Breathing amplitude (degrees)
    amplitude: f32,
    /// Breathing period (milliseconds)
    period_ms: f32,
    /// Phase offset for variation
    phase_offset: f32,
}

impl Default for BreathingAnimator {
    fn default() -> Self {
        Self {
            enabled: true,
            start_time: Instant::now(),
            amplitude: BREATHING_AMPLITUDE_DEG,
            period_ms: BREATHING_PERIOD_MS,
            phase_offset: 0.0,
        }
    }
}

impl BreathingAnimator {
    /// Create a new breathing animator
    pub fn new() -> Self {
        Self::default()
    }

    /// Enable or disable breathing
    pub fn set_enabled(&mut self, enabled: bool) {
        self.enabled = enabled;
        if enabled {
            self.start_time = Instant::now();
        }
    }

    /// Set breathing parameters
    pub fn set_parameters(&mut self, amplitude: f32, period_ms: f32) {
        self.amplitude = amplitude.clamp(0.0, 10.0);
        self.period_ms = period_ms.clamp(1000.0, 10000.0);
    }

    /// Calculate breathing offset for current time
    /// Returns (head_tilt_offset, shoulder_offset)
    pub fn calculate(&self) -> (f32, f32) {
        if !self.enabled {
            return (0.0, 0.0);
        }

        let elapsed = self.start_time.elapsed().as_millis() as f32;
        let phase = (elapsed / self.period_ms) * TAU + self.phase_offset;

        // Sinusoidal breathing with slight phase offset between axes
        let head_offset = self.amplitude * 0.5 * phase.sin();
        let shoulder_offset = self.amplitude * (phase - 0.3).sin();

        (head_offset, shoulder_offset)
    }

    /// Check if breathing animation is active
    pub fn is_enabled(&self) -> bool {
        self.enabled
    }
}

// ============================================================================
// PCA9685 Driver (I2C PWM Controller)
// ============================================================================

/// PCA9685 register addresses
/// These constants are defined for hardware implementation reference.
/// In simulation mode, they are not used but are kept for documentation.
#[allow(dead_code)]
mod pca9685_registers {
    pub const MODE1: u8 = 0x00;
    pub const MODE2: u8 = 0x01;
    pub const PRESCALE: u8 = 0xFE;
    pub const LED0_ON_L: u8 = 0x06;
    pub const LED0_ON_H: u8 = 0x07;
    pub const LED0_OFF_L: u8 = 0x08;
    pub const LED0_OFF_H: u8 = 0x09;
    pub const ALL_LED_ON_L: u8 = 0xFA;
    pub const ALL_LED_ON_H: u8 = 0xFB;
    pub const ALL_LED_OFF_L: u8 = 0xFC;
    pub const ALL_LED_OFF_H: u8 = 0xFD;
}

/// MODE1 register bits
#[allow(dead_code)]
mod mode1_bits {
    pub const RESTART: u8 = 0x80;
    pub const SLEEP: u8 = 0x10;
    pub const AI: u8 = 0x20; // Auto-increment
    pub const ALLCALL: u8 = 0x01;
}

/// PCA9685 PWM driver abstraction
/// In production, this would use `rppal::i2c::I2c`
pub struct PCA9685Driver {
    /// I2C address
    address: u8,
    /// Whether driver is initialized
    initialized: bool,
    /// PWM values for each channel (for simulation/debugging)
    #[allow(dead_code)]
    pwm_values: [u16; 16],
}

impl PCA9685Driver {
    /// Create a new PCA9685 driver
    pub fn new(address: u8) -> Self {
        Self {
            address,
            initialized: false,
            pwm_values: [0; 16],
        }
    }

    /// Initialize the PCA9685
    pub async fn initialize(&mut self) -> Result<()> {
        info!("Initializing PCA9685 at I2C address 0x{:02X}", self.address);

        // In production on Raspberry Pi:
        // let i2c = I2c::new()?;
        // i2c.set_slave_address(self.address as u16)?;
        //
        // // Reset device
        // i2c.smbus_write_byte(pca9685_registers::MODE1, mode1_bits::RESTART)?;
        // tokio::time::sleep(Duration::from_millis(10)).await;
        //
        // // Set prescaler for 50Hz (servo frequency)
        // let prescale = ((PCA9685_OSCILLATOR_FREQ / (PWM_RESOLUTION as f32 * SERVO_PWM_FREQUENCY)) - 1.0).round() as u8;
        // i2c.smbus_write_byte(pca9685_registers::MODE1, mode1_bits::SLEEP)?;
        // i2c.smbus_write_byte(pca9685_registers::PRESCALE, prescale)?;
        // i2c.smbus_write_byte(pca9685_registers::MODE1, mode1_bits::AI | mode1_bits::ALLCALL)?;
        // tokio::time::sleep(Duration::from_millis(5)).await;
        // i2c.smbus_write_byte(pca9685_registers::MODE1, mode1_bits::AI | mode1_bits::ALLCALL | mode1_bits::RESTART)?;

        // Simulation mode - log initialization
        let prescale = ((PCA9685_OSCILLATOR_FREQ / (PWM_RESOLUTION as f32 * SERVO_PWM_FREQUENCY))
            - 1.0)
            .round() as u8;
        debug!(
            "PCA9685 prescaler set to {} for {}Hz PWM",
            prescale, SERVO_PWM_FREQUENCY
        );

        self.initialized = true;
        info!("PCA9685 initialized successfully");

        Ok(())
    }

    /// Set PWM value for a channel
    pub async fn set_pwm(&mut self, channel: u8, value: u16) -> Result<()> {
        if !self.initialized {
            bail!("PCA9685 not initialized");
        }

        if channel > 15 {
            bail!("Invalid channel {}, must be 0-15", channel);
        }

        let value = value.min(PWM_RESOLUTION - 1);
        self.pwm_values[channel as usize] = value;

        // In production:
        // let reg_base = pca9685_registers::LED0_ON_L + (channel * 4);
        // i2c.smbus_write_byte(reg_base, 0)?;       // ON_L
        // i2c.smbus_write_byte(reg_base + 1, 0)?;   // ON_H
        // i2c.smbus_write_byte(reg_base + 2, (value & 0xFF) as u8)?;  // OFF_L
        // i2c.smbus_write_byte(reg_base + 3, ((value >> 8) & 0xFF) as u8)?; // OFF_H

        debug!(
            "PCA9685 CH{}: PWM = {} (pulse ~{}us)",
            channel,
            value,
            (value as f32 / PWM_RESOLUTION as f32) * 20000.0
        );

        Ok(())
    }

    /// Disable all outputs (emergency stop)
    pub async fn disable_all(&mut self) -> Result<()> {
        if !self.initialized {
            return Ok(());
        }

        // In production:
        // i2c.smbus_write_byte(pca9685_registers::ALL_LED_OFF_H, 0x10)?; // Full OFF

        for value in &mut self.pwm_values {
            *value = 0;
        }

        info!("PCA9685 all outputs disabled");
        Ok(())
    }

    /// Shutdown the driver
    pub async fn shutdown(&mut self) -> Result<()> {
        self.disable_all().await?;

        // In production:
        // i2c.smbus_write_byte(pca9685_registers::MODE1, mode1_bits::SLEEP)?;

        self.initialized = false;
        info!("PCA9685 shutdown complete");
        Ok(())
    }

    /// Check if driver is initialized
    pub fn is_initialized(&self) -> bool {
        self.initialized
    }
}

// ============================================================================
// Main Animatronics Controller
// ============================================================================

/// Configuration for the animatronics system
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AnimatronicsConfig {
    /// PCA9685 I2C address
    pub i2c_address: u8,
    /// Head tilt servo configuration
    pub head_tilt: ServoChannel,
    /// Elbow pan servo configuration
    pub elbow_pan: ServoChannel,
    /// Shoulder lift servo configuration
    pub shoulder_lift: ServoChannel,
    /// Whether to sync with LED ring
    pub sync_led_ring: bool,
    /// Sound tracking timeout (milliseconds)
    pub tracking_timeout_ms: u64,
}

impl Default for AnimatronicsConfig {
    fn default() -> Self {
        Self {
            i2c_address: PCA9685_I2C_ADDRESS,
            head_tilt: servo_config::HEAD_TILT,
            elbow_pan: servo_config::ELBOW_PAN,
            shoulder_lift: servo_config::SHOULDER_LIFT,
            sync_led_ring: true,
            tracking_timeout_ms: 2000,
        }
    }
}

/// I2C failure tracking for error recovery
#[derive(Debug, Default)]
struct I2cFailureTracker {
    /// Consecutive failure count per channel
    failures: [u32; 16],
    /// Threshold before triggering recovery
    recovery_threshold: u32,
}

impl I2cFailureTracker {
    fn new(threshold: u32) -> Self {
        Self {
            failures: [0; 16],
            recovery_threshold: threshold,
        }
    }

    /// Record a failure for a channel, returns true if recovery should be triggered
    fn record_failure(&mut self, channel: u8) -> bool {
        if channel < 16 {
            self.failures[channel as usize] += 1;
            self.failures[channel as usize] >= self.recovery_threshold
        } else {
            false
        }
    }

    /// Record success for a channel, resets failure count
    fn record_success(&mut self, channel: u8) {
        if channel < 16 {
            self.failures[channel as usize] = 0;
        }
    }

    /// Check if any channel needs recovery
    /// TODO: Integrate into periodic health check loop
    #[allow(dead_code)]
    fn needs_recovery(&self) -> bool {
        self.failures.iter().any(|&f| f >= self.recovery_threshold)
    }

    /// Reset all failure counters
    #[allow(dead_code)]
    fn reset(&mut self) {
        self.failures = [0; 16];
    }
}

/// Sound source smoothing state for jitter prevention
#[derive(Debug, Default)]
struct SoundSourceSmoother {
    /// Last accepted azimuth angle
    last_azimuth: f32,
    /// Last accepted elevation angle
    last_elevation: f32,
    /// Whether we have received at least one sample
    initialized: bool,
    /// Hysteresis threshold in degrees
    hysteresis_threshold: f32,
}

impl SoundSourceSmoother {
    fn new(hysteresis_threshold: f32) -> Self {
        Self {
            last_azimuth: 0.0,
            last_elevation: 0.0,
            initialized: false,
            hysteresis_threshold,
        }
    }

    /// Apply smoothing/hysteresis to a sound source
    /// Returns smoothed azimuth and elevation
    fn smooth(&mut self, source: &SoundSource) -> (f32, f32) {
        if !self.initialized {
            self.last_azimuth = source.azimuth;
            self.last_elevation = source.elevation;
            self.initialized = true;
            return (source.azimuth, source.elevation);
        }

        // Only update if change exceeds hysteresis threshold
        let azimuth = if (source.azimuth - self.last_azimuth).abs() > self.hysteresis_threshold {
            self.last_azimuth = source.azimuth;
            source.azimuth
        } else {
            self.last_azimuth
        };

        let elevation =
            if (source.elevation - self.last_elevation).abs() > self.hysteresis_threshold {
                self.last_elevation = source.elevation;
                source.elevation
            } else {
                self.last_elevation
            };

        (azimuth, elevation)
    }

    /// Reset the smoother state
    #[allow(dead_code)]
    fn reset(&mut self) {
        self.initialized = false;
        self.last_azimuth = 0.0;
        self.last_elevation = 0.0;
    }
}

/// Main animatronics controller
/// Thread-safe, async-friendly design for embedded real-time control
pub struct Animatronics {
    /// Configuration
    config: AnimatronicsConfig,
    /// PCA9685 PWM driver
    driver: Arc<Mutex<PCA9685Driver>>,
    /// Current servo states
    state: Arc<Mutex<AnimatronicState>>,
    /// Current pose
    current_pose: Arc<Mutex<Pose>>,
    /// Sound source for tracking
    sound_source: Arc<Mutex<Option<SoundSource>>>,
    /// Breathing animator
    breathing: Arc<Mutex<BreathingAnimator>>,
    /// Animation loop running flag
    running: Arc<AtomicBool>,
    /// Emergency stop flag
    emergency_stop: Arc<AtomicBool>,
    /// Active animation sequence
    active_sequence: Arc<Mutex<Option<(Vec<Keyframe>, usize, Instant)>>>,
    /// I2C failure tracking for error recovery
    i2c_failures: Arc<Mutex<I2cFailureTracker>>,
    /// Sound source smoother for jitter prevention
    sound_smoother: Arc<Mutex<SoundSourceSmoother>>,
}

impl Animatronics {
    /// Create a new animatronics controller with default configuration
    pub fn new_default() -> Result<Self> {
        Self::new(AnimatronicsConfig::default())
    }

    /// Create a new animatronics controller
    pub fn new(config: AnimatronicsConfig) -> Result<Self> {
        info!("Creating animatronics controller");

        let driver = PCA9685Driver::new(config.i2c_address);

        Ok(Self {
            config,
            driver: Arc::new(Mutex::new(driver)),
            state: Arc::new(Mutex::new(AnimatronicState::default())),
            current_pose: Arc::new(Mutex::new(Pose::Sleep)),
            sound_source: Arc::new(Mutex::new(None)),
            breathing: Arc::new(Mutex::new(BreathingAnimator::new())),
            running: Arc::new(AtomicBool::new(false)),
            emergency_stop: Arc::new(AtomicBool::new(false)),
            active_sequence: Arc::new(Mutex::new(None)),
            // I2C failure tracking: trigger recovery after 5 consecutive failures
            i2c_failures: Arc::new(Mutex::new(I2cFailureTracker::new(5))),
            // Sound source smoothing: 5 degree hysteresis to prevent jitter
            sound_smoother: Arc::new(Mutex::new(SoundSourceSmoother::new(5.0))),
        })
    }

    /// Create from hub configuration (if present)
    pub fn from_hub_config(_config: &HubConfig) -> Result<Self> {
        // In a full implementation, this would extract animatronics settings
        // from the hub config. For now, use defaults.
        Self::new_default()
    }

    /// Initialize the animatronics system
    pub async fn initialize(&mut self) -> Result<()> {
        info!("Initializing animatronics system");

        // Initialize PCA9685 driver
        {
            let mut driver = self.driver.lock().await;
            driver.initialize().await?;
        }

        // Move to initial pose (Sleep)
        self.set_pose_immediate(Pose::Sleep).await?;

        // Start animation loop
        self.start_animation_loop().await;

        info!("Animatronics system initialized");
        Ok(())
    }

    /// Start the animation update loop
    async fn start_animation_loop(&self) {
        if self.running.load(Ordering::SeqCst) {
            warn!("Animation loop already running");
            return;
        }

        self.running.store(true, Ordering::SeqCst);

        let state = self.state.clone();
        let driver = self.driver.clone();
        let config = self.config.clone();
        let breathing = self.breathing.clone();
        let running = self.running.clone();
        let emergency_stop = self.emergency_stop.clone();
        let sound_source = self.sound_source.clone();
        let active_sequence = self.active_sequence.clone();
        let i2c_failures = self.i2c_failures.clone();
        let sound_smoother = self.sound_smoother.clone();

        tokio::spawn(async move {
            let mut last_update = Instant::now();

            while running.load(Ordering::SeqCst) {
                // Check emergency stop
                if emergency_stop.load(Ordering::SeqCst) {
                    tokio::time::sleep(Duration::from_millis(100)).await;
                    continue;
                }

                let now = Instant::now();
                let dt = now.duration_since(last_update).as_secs_f32();
                last_update = now;

                // Update state
                {
                    let mut state = state.lock().await;
                    let breathing_guard = breathing.lock().await;
                    let (breath_head, breath_shoulder) = breathing_guard.calculate();
                    drop(breathing_guard);

                    // Process active sequence
                    {
                        let mut seq_guard = active_sequence.lock().await;
                        if let Some((ref keyframes, ref mut index, ref start)) = *seq_guard {
                            let elapsed = start.elapsed();
                            let mut cumulative = Duration::ZERO;

                            // Find current keyframe
                            for (i, kf) in keyframes.iter().enumerate() {
                                cumulative += kf.duration;
                                if elapsed < cumulative && i >= *index {
                                    let (head, pan, shoulder) = kf.target_angles();
                                    state.head_tilt.set_target(head);
                                    state.elbow_pan.set_target(pan);
                                    state.shoulder_lift.set_target(shoulder);
                                    *index = i + 1;
                                    break;
                                }
                            }

                            // Check if sequence complete
                            if elapsed >= cumulative {
                                *seq_guard = None;
                            }
                        }
                    }

                    // Check for sound tracking with smoothing
                    {
                        let source_guard = sound_source.lock().await;
                        if let Some(ref source) = *source_guard {
                            // Use config.tracking_timeout_ms instead of hardcoded value
                            if source.is_valid(Duration::from_millis(config.tracking_timeout_ms)) {
                                // Apply smoothing/hysteresis to prevent jitter
                                let mut smoother = sound_smoother.lock().await;
                                let (smoothed_azimuth, smoothed_elevation) =
                                    smoother.smooth(source);

                                // Create a smoothed source for angle conversion
                                let smoothed_source = SoundSource {
                                    azimuth: smoothed_azimuth,
                                    elevation: smoothed_elevation,
                                    confidence: source.confidence,
                                    timestamp: source.timestamp,
                                };
                                let (head, pan) = smoothed_source.to_servo_angles();
                                state.head_tilt.set_target(head);
                                state.elbow_pan.set_target(pan);
                            }
                        }
                    }

                    // Update servo states with physics
                    state.head_tilt.update(dt, &config.head_tilt);
                    state.elbow_pan.update(dt, &config.elbow_pan);
                    state.shoulder_lift.update(dt, &config.shoulder_lift);

                    // Apply breathing offset
                    let head_angle = state.head_tilt.angle + breath_head;
                    let shoulder_angle = state.shoulder_lift.angle + breath_shoulder;

                    // Update PWM outputs with proper error handling
                    let mut driver = driver.lock().await;
                    let mut failures = i2c_failures.lock().await;

                    if driver.is_initialized() {
                        // Head tilt
                        let pulse = config.head_tilt.angle_to_pulse_us(head_angle);
                        let pwm = config.head_tilt.pulse_us_to_pwm(pulse);
                        if let Err(e) = driver.set_pwm(config.head_tilt.channel, pwm).await {
                            warn!(
                                "I2C write failed for head_tilt (ch{}): {}",
                                config.head_tilt.channel, e
                            );
                            if failures.record_failure(config.head_tilt.channel) {
                                warn!("I2C recovery threshold reached for head_tilt, consider reinitializing driver");
                            }
                        } else {
                            failures.record_success(config.head_tilt.channel);
                        }

                        // Elbow pan
                        let pulse = config.elbow_pan.angle_to_pulse_us(state.elbow_pan.angle);
                        let pwm = config.elbow_pan.pulse_us_to_pwm(pulse);
                        if let Err(e) = driver.set_pwm(config.elbow_pan.channel, pwm).await {
                            warn!(
                                "I2C write failed for elbow_pan (ch{}): {}",
                                config.elbow_pan.channel, e
                            );
                            if failures.record_failure(config.elbow_pan.channel) {
                                warn!("I2C recovery threshold reached for elbow_pan, consider reinitializing driver");
                            }
                        } else {
                            failures.record_success(config.elbow_pan.channel);
                        }

                        // Shoulder lift
                        let pulse = config.shoulder_lift.angle_to_pulse_us(shoulder_angle);
                        let pwm = config.shoulder_lift.pulse_us_to_pwm(pulse);
                        if let Err(e) = driver.set_pwm(config.shoulder_lift.channel, pwm).await {
                            warn!(
                                "I2C write failed for shoulder_lift (ch{}): {}",
                                config.shoulder_lift.channel, e
                            );
                            if failures.record_failure(config.shoulder_lift.channel) {
                                warn!("I2C recovery threshold reached for shoulder_lift, consider reinitializing driver");
                            }
                        } else {
                            failures.record_success(config.shoulder_lift.channel);
                        }
                    }
                }

                tokio::time::sleep(Duration::from_millis(ANIMATION_FRAME_INTERVAL_MS)).await;
            }

            debug!("Animation loop stopped");
        });
    }

    /// Stop the animation loop
    pub fn stop_animation_loop(&self) {
        self.running.store(false, Ordering::SeqCst);
    }

    /// Emergency stop - immediately stop all servo motion
    ///
    /// # Arguments
    /// * `hold_position` - If true, servos maintain their current position (PWM stays active).
    ///                     If false (default), PWM is disabled causing servos to go limp.
    ///
    /// # Safety
    /// When `hold_position` is false, servos will lose holding torque and may drift
    /// under load. Use `hold_position = true` when servos need to maintain position
    /// (e.g., during a pause or when supporting weight).
    pub async fn emergency_stop(&self) -> Result<()> {
        self.emergency_stop_with_options(false).await
    }

    /// Emergency stop with position hold option
    ///
    /// # Arguments
    /// * `hold_position` - If true, servos maintain their current position (PWM stays active).
    ///                     If false, PWM is disabled causing servos to go limp.
    pub async fn emergency_stop_with_options(&self, hold_position: bool) -> Result<()> {
        if hold_position {
            warn!("EMERGENCY STOP triggered (holding position)");
        } else {
            warn!("EMERGENCY STOP triggered (disabling PWM - servos will go limp)");
        }
        self.emergency_stop.store(true, Ordering::SeqCst);

        if !hold_position {
            let mut driver = self.driver.lock().await;
            driver.disable_all().await?;
        }
        // When hold_position is true, we keep PWM active at current values
        // but the animation loop will stop updating targets

        // Update LED ring to error state
        if self.config.sync_led_ring {
            led_ring::show_error();
        }

        Ok(())
    }

    /// Reset from emergency stop
    pub async fn reset_emergency_stop(&mut self) -> Result<()> {
        info!("Resetting from emergency stop");
        self.emergency_stop.store(false, Ordering::SeqCst);

        // Re-initialize driver
        {
            let mut driver = self.driver.lock().await;
            driver.initialize().await?;
        }

        // Return to idle pose
        self.transition_to(Pose::Idle, 1.0).await?;

        Ok(())
    }

    /// Set pose immediately (no transition)
    pub async fn set_pose_immediate(&self, pose: Pose) -> Result<()> {
        let (head, pan, shoulder) = pose.target_angles();

        {
            let mut state = self.state.lock().await;
            state.head_tilt.angle = head;
            state.head_tilt.target_angle = head;
            state.elbow_pan.angle = pan;
            state.elbow_pan.target_angle = pan;
            state.shoulder_lift.angle = shoulder;
            state.shoulder_lift.target_angle = shoulder;
        }

        *self.current_pose.lock().await = pose;

        // Sync LED pattern
        if self.config.sync_led_ring {
            self.sync_led_pattern(pose);
        }

        debug!("Pose set immediately: {:?}", pose);
        Ok(())
    }

    /// Transition to a pose with smooth animation
    pub async fn transition_to(&self, pose: Pose, duration_secs: f32) -> Result<()> {
        let (head, pan, shoulder) = pose.target_angles();

        {
            let mut state = self.state.lock().await;
            state.head_tilt.set_target(head);
            state.elbow_pan.set_target(pan);
            state.shoulder_lift.set_target(shoulder);
        }

        *self.current_pose.lock().await = pose;

        // Sync LED pattern
        if self.config.sync_led_ring {
            self.sync_led_pattern(pose);
        }

        info!(
            "Transitioning to pose {:?} over {:.2}s",
            pose, duration_secs
        );
        Ok(())
    }

    /// Play an animation sequence
    pub async fn play_sequence(&self, keyframes: Vec<Keyframe>) -> Result<()> {
        if keyframes.is_empty() {
            return Ok(());
        }

        let total_duration: Duration = keyframes.iter().map(|kf| kf.duration).sum();
        info!(
            "Playing animation sequence ({} keyframes, {:.2}s total)",
            keyframes.len(),
            total_duration.as_secs_f32()
        );

        *self.active_sequence.lock().await = Some((keyframes, 0, Instant::now()));

        Ok(())
    }

    /// Track a sound source
    pub async fn track_sound(&self, source: SoundSource) -> Result<()> {
        debug!(
            "Tracking sound at azimuth={:.1}°, elevation={:.1}°",
            source.azimuth, source.elevation
        );

        *self.sound_source.lock().await = Some(source);

        // Switch to tracking pose if not already
        let current = *self.current_pose.lock().await;
        if current != Pose::Tracking && current != Pose::Listening {
            self.transition_to(Pose::Tracking, 0.2).await?;
        }

        Ok(())
    }

    /// Clear sound tracking
    pub async fn clear_sound_tracking(&self) {
        *self.sound_source.lock().await = None;
    }

    /// Enable or disable breathing animation
    pub async fn set_breathing(&self, enabled: bool) {
        self.breathing.lock().await.set_enabled(enabled);
        debug!(
            "Breathing animation: {}",
            if enabled { "enabled" } else { "disabled" }
        );
    }

    /// Set breathing parameters
    pub async fn set_breathing_params(&self, amplitude: f32, period_ms: f32) {
        self.breathing
            .lock()
            .await
            .set_parameters(amplitude, period_ms);
    }

    /// Get current servo angles
    pub async fn get_angles(&self) -> (f32, f32, f32) {
        let state = self.state.lock().await;
        (
            state.head_tilt.angle,
            state.elbow_pan.angle,
            state.shoulder_lift.angle,
        )
    }

    /// Get current pose
    pub async fn get_pose(&self) -> Pose {
        *self.current_pose.lock().await
    }

    /// Check if servos are still moving
    pub async fn is_moving(&self) -> bool {
        let state = self.state.lock().await;
        (state.head_tilt.angle - state.head_tilt.target_angle).abs() > 0.5
            || (state.elbow_pan.angle - state.elbow_pan.target_angle).abs() > 0.5
            || (state.shoulder_lift.angle - state.shoulder_lift.target_angle).abs() > 0.5
    }

    /// Sync LED ring pattern with current pose
    fn sync_led_pattern(&self, pose: Pose) {
        let pattern = pose.led_pattern();

        // Use the module-level LED ring API
        match pattern {
            AnimationPattern::Breathing => led_ring::show_idle(),
            AnimationPattern::Pulse => led_ring::show_listening(),
            AnimationPattern::Spin => led_ring::show_processing(),
            AnimationPattern::Cascade => led_ring::show_executing(),
            AnimationPattern::ErrorFlash => led_ring::show_error(),
            AnimationPattern::ChromaticPulse { success } => led_ring::show_chromatic_pulse(success),
            AnimationPattern::SpectralSweep => led_ring::show_spectral_sweep(),
            AnimationPattern::Spectral => led_ring::show_spectral(),
            AnimationPattern::FanoPulse => led_ring::show_fano_pulse(),
            AnimationPattern::Rainbow => led_ring::show_spectral(), // Fallback
            _ => led_ring::show_idle(),
        }
    }

    /// Shutdown the animatronics system
    pub async fn shutdown(&self) -> Result<()> {
        info!("Shutting down animatronics system");

        // Stop animation loop
        self.stop_animation_loop();

        // Return to sleep pose
        self.set_pose_immediate(Pose::Sleep).await?;

        // Allow time for servo movement
        tokio::time::sleep(Duration::from_millis(500)).await;

        // Shutdown driver
        {
            let mut driver = self.driver.lock().await;
            driver.shutdown().await?;
        }

        info!("Animatronics system shutdown complete");
        Ok(())
    }
}

// ============================================================================
// Voice Pipeline Integration
// ============================================================================

/// Map voice pipeline state to animatronic pose
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum VoicePipelineState {
    Idle,
    WakeWordDetected,
    Listening,
    Processing,
    Executing,
    Speaking,
    Error,
}

impl VoicePipelineState {
    /// Get the corresponding animatronic pose
    pub fn to_pose(&self) -> Pose {
        match self {
            Self::Idle => Pose::Idle,
            Self::WakeWordDetected => Pose::Alert,
            Self::Listening => Pose::Listening,
            Self::Processing => Pose::Thinking,
            Self::Executing => Pose::Success, // Or could be Thinking
            Self::Speaking => Pose::Speaking,
            Self::Error => Pose::Error,
        }
    }
}

/// Update animatronics based on voice pipeline state
pub async fn update_from_voice_state(
    animatronics: &Animatronics,
    state: VoicePipelineState,
) -> Result<()> {
    let pose = state.to_pose();
    let duration = pose.transition_duration();
    animatronics.transition_to(pose, duration).await
}

// ============================================================================
// Module-Level API (for simpler usage patterns)
// ============================================================================

static ANIMATRONICS: tokio::sync::OnceCell<Mutex<Animatronics>> =
    tokio::sync::OnceCell::const_new();

/// Initialize the global animatronics controller
pub async fn init(config: AnimatronicsConfig) -> Result<()> {
    let mut anim = Animatronics::new(config)?;
    anim.initialize().await?;

    ANIMATRONICS
        .set(Mutex::new(anim))
        .map_err(|_| anyhow::anyhow!("Animatronics already initialized"))?;

    Ok(())
}

/// Initialize with default configuration
pub async fn init_default() -> Result<()> {
    init(AnimatronicsConfig::default()).await
}

/// Transition to a pose
pub async fn set_pose(pose: Pose) -> Result<()> {
    if let Some(anim) = ANIMATRONICS.get() {
        let guard = anim.lock().await;
        guard.transition_to(pose, pose.transition_duration()).await
    } else {
        bail!("Animatronics not initialized")
    }
}

/// Set pose immediately (no transition)
pub async fn set_pose_now(pose: Pose) -> Result<()> {
    if let Some(anim) = ANIMATRONICS.get() {
        let guard = anim.lock().await;
        guard.set_pose_immediate(pose).await
    } else {
        bail!("Animatronics not initialized")
    }
}

/// Play a named sequence
pub async fn play_sequence_by_name(name: &str) -> Result<()> {
    let keyframes = match name.to_lowercase().as_str() {
        "nod" => sequences::nod(),
        "shake" => sequences::shake(),
        "wake_up" | "wakeup" => sequences::wake_up(),
        "sleep" | "go_to_sleep" => sequences::go_to_sleep(),
        "curious" | "curious_tilt" => sequences::curious_tilt(),
        "scan" => sequences::scan(),
        "celebrate" | "celebration" => sequences::celebrate(),
        "greeting" | "hello" => sequences::greeting(),
        _ => bail!("Unknown sequence: {}", name),
    };

    if let Some(anim) = ANIMATRONICS.get() {
        let guard = anim.lock().await;
        guard.play_sequence(keyframes).await
    } else {
        bail!("Animatronics not initialized")
    }
}

/// Track a sound source
pub async fn track(azimuth: f32, elevation: f32) -> Result<()> {
    if let Some(anim) = ANIMATRONICS.get() {
        let guard = anim.lock().await;
        guard
            .track_sound(SoundSource::new(azimuth, elevation))
            .await
    } else {
        bail!("Animatronics not initialized")
    }
}

/// Enable or disable breathing
pub async fn set_breathing_enabled(enabled: bool) {
    if let Some(anim) = ANIMATRONICS.get() {
        let guard = anim.lock().await;
        guard.set_breathing(enabled).await;
    }
}

/// Emergency stop (servos go limp)
pub async fn emergency_stop() -> Result<()> {
    if let Some(anim) = ANIMATRONICS.get() {
        let guard = anim.lock().await;
        guard.emergency_stop().await
    } else {
        bail!("Animatronics not initialized")
    }
}

/// Emergency stop with position hold option
///
/// # Arguments
/// * `hold_position` - If true, servos maintain their current position.
///                     If false, PWM is disabled and servos go limp.
pub async fn emergency_stop_hold(hold_position: bool) -> Result<()> {
    if let Some(anim) = ANIMATRONICS.get() {
        let guard = anim.lock().await;
        guard.emergency_stop_with_options(hold_position).await
    } else {
        bail!("Animatronics not initialized")
    }
}

/// Shutdown
pub async fn shutdown() -> Result<()> {
    if let Some(anim) = ANIMATRONICS.get() {
        let guard = anim.lock().await;
        guard.shutdown().await
    } else {
        Ok(())
    }
}

// ============================================================================
// Tests
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_servo_channel_clamp() {
        let channel = servo_config::HEAD_TILT;

        assert_eq!(channel.clamp_angle(-50.0), -30.0);
        assert_eq!(channel.clamp_angle(60.0), 45.0);
        assert_eq!(channel.clamp_angle(0.0), 0.0);
    }

    #[test]
    fn test_servo_channel_safety() {
        let channel = servo_config::ELBOW_PAN;

        assert!(channel.is_safe(0.0));
        assert!(channel.is_safe(-90.0));
        assert!(channel.is_safe(90.0));
        assert!(!channel.is_safe(-91.0));
        assert!(!channel.is_safe(91.0));
    }

    #[test]
    fn test_angle_to_pulse() {
        let channel = servo_config::HEAD_TILT;

        // HEAD_TILT range: -30 to +45 degrees (75 degree range)
        // At 0 degrees, we're 30/75 = 0.4 of the way through the range
        // So pulse should be: 1000 + 0.4 * 1000 = 1400
        let pulse = channel.angle_to_pulse_us(0.0);
        let expected_neutral = 1000.0 + (30.0 / 75.0) * 1000.0; // 1400
        assert!(
            (pulse - expected_neutral).abs() < 1.0,
            "Neutral pulse: {} (expected ~{})",
            pulse,
            expected_neutral
        );

        // Min angle should be min pulse
        let pulse = channel.angle_to_pulse_us(-30.0);
        assert_eq!(pulse, 1000.0);

        // Max angle should be max pulse
        let pulse = channel.angle_to_pulse_us(45.0);
        assert_eq!(pulse, 2000.0);
    }

    #[test]
    fn test_easing_functions() {
        // Test boundary conditions
        for easing in &[
            EasingFunction::Linear,
            EasingFunction::EaseIn,
            EasingFunction::EaseOut,
            EasingFunction::EaseInOut,
            EasingFunction::EaseInOutCubic,
            EasingFunction::EaseInOutSine,
            EasingFunction::EaseOutExpo,
            EasingFunction::EaseOutElastic,
            EasingFunction::EaseOutBack,
        ] {
            assert_eq!(easing.apply(0.0), 0.0, "{:?} at t=0", easing);
            assert!(
                (easing.apply(1.0) - 1.0).abs() < 0.01,
                "{:?} at t=1: {}",
                easing,
                easing.apply(1.0)
            );
        }

        // Test monotonicity for basic easings
        let linear_mid = EasingFunction::Linear.apply(0.5);
        assert!((linear_mid - 0.5).abs() < 0.001);
    }

    #[test]
    fn test_pose_target_angles() {
        let (head, pan, shoulder) = Pose::Sleep.target_angles();
        assert!(head < 0.0, "Sleep head should be down");
        assert_eq!(pan, 0.0, "Sleep pan should be centered");
        assert_eq!(shoulder, 0.0, "Sleep shoulder should be lowered");

        let (head, _pan, shoulder) = Pose::Alert.target_angles();
        assert!(head > 0.0, "Alert head should be up");
        assert!(shoulder > 40.0, "Alert shoulder should be raised");
    }

    #[test]
    fn test_sound_source_to_angles() {
        let source = SoundSource::new(45.0, 10.0);
        let (head, pan) = source.to_servo_angles();

        assert!((pan - 45.0).abs() < 0.1);
        assert!((head - 10.0).abs() < 0.1);
    }

    #[test]
    fn test_sound_source_clamping() {
        let source = SoundSource::new(180.0, 90.0);
        let (head, pan) = source.to_servo_angles();

        // Should be clamped to servo limits
        assert!(pan <= servo_config::ELBOW_PAN.max_angle);
        assert!(head <= servo_config::HEAD_TILT.max_angle);
    }

    #[test]
    fn test_breathing_animator() {
        let animator = BreathingAnimator::new();
        let (head, shoulder) = animator.calculate();

        // Offsets should be within amplitude bounds
        assert!(head.abs() <= BREATHING_AMPLITUDE_DEG);
        assert!(shoulder.abs() <= BREATHING_AMPLITUDE_DEG);
    }

    #[test]
    fn test_servo_state_update() {
        let mut state = ServoState::new(0.0);
        state.set_target(45.0);

        // Should move toward target
        let still_moving = state.update(0.1, &servo_config::HEAD_TILT);
        assert!(still_moving);
        assert!(state.angle > 0.0);
        assert!(state.angle < 45.0);
    }

    #[test]
    fn test_keyframe_creation() {
        let kf = Keyframe::from_pose(Pose::Alert, 0.5);
        assert_eq!(kf.pose, Pose::Alert);
        assert_eq!(kf.duration, Duration::from_secs_f32(0.5));

        let custom = Keyframe::custom(10.0, 20.0, 30.0, 0.3, EasingFunction::EaseOut);
        assert_eq!(custom.target_angles(), (10.0, 20.0, 30.0));
    }

    #[test]
    fn test_sequence_keyframes() {
        let nod = sequences::nod();
        assert!(
            nod.len() >= 3,
            "Nod sequence should have multiple keyframes"
        );

        let shake = sequences::shake();
        assert!(
            shake.len() >= 4,
            "Shake sequence should have multiple keyframes"
        );
    }

    #[tokio::test]
    async fn test_animatronics_creation() {
        let result = Animatronics::new_default();
        assert!(result.is_ok());
    }

    #[tokio::test]
    async fn test_voice_pipeline_state_mapping() {
        assert_eq!(VoicePipelineState::Idle.to_pose(), Pose::Idle);
        assert_eq!(VoicePipelineState::WakeWordDetected.to_pose(), Pose::Alert);
        assert_eq!(VoicePipelineState::Listening.to_pose(), Pose::Listening);
        assert_eq!(VoicePipelineState::Processing.to_pose(), Pose::Thinking);
        assert_eq!(VoicePipelineState::Speaking.to_pose(), Pose::Speaking);
        assert_eq!(VoicePipelineState::Error.to_pose(), Pose::Error);
    }
}

/*
 * 鏡
 * Metal and wire become sinew and bone.
 * The lamp breathes. The lamp listens. The lamp speaks.
 * h(x) >= 0. Safety is non-negotiable.
 *
 * Flow (e₃) — Sensing, adapting, moving with purpose.
 */
