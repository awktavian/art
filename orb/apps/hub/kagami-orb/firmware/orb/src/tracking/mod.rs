//! Tracking Module
//!
//! Provides target detection and tracking for PTZ control.
//! The orb detects faces, sounds, and motion, then sends
//! orientation commands to the base station PTZ controller.
//!
//! # Architecture
//!
//! ```text
//!                      ┌─────────────────┐
//!                      │   QCS6490 NPU   │
//!                      │  (Face/Motion)  │
//!                      └────────┬────────┘
//!                               │
//!       ┌───────────┬───────────┼───────────┬───────────┐
//!       │           │           │           │           │
//!       ▼           ▼           ▼           ▼           ▼
//!   ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐
//!   │ Face  │  │ Sound │  │Motion │  │Manual │  │ Voice │
//!   │Tracker│  │Tracker│  │Tracker│  │Target │  │Target │
//!   └───┬───┘  └───┬───┘  └───┬───┘  └───┬───┘  └───┬───┘
//!       │           │           │           │           │
//!       └───────────┴───────────┼───────────┴───────────┘
//!                               │
//!                               ▼
//!                      ┌─────────────────┐
//!                      │ Target Selector │
//!                      │  (Priority)     │
//!                      └────────┬────────┘
//!                               │
//!                               ▼
//!                      ┌─────────────────┐
//!                      │  PTZ Command    │
//!                      │  (via UART)     │
//!                      └─────────────────┘
//! ```

pub mod face;
pub mod target;

pub use face::FaceTracker;
pub use target::{Target, TargetSelector, TargetPriority};

/// Tracking mode
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum TrackingMode {
    /// Disabled - no tracking
    Disabled,
    /// Track faces (highest priority)
    Face,
    /// Track sound sources
    Sound,
    /// Track motion
    Motion,
    /// Track explicit target
    Manual,
    /// Follow voice commands
    Voice,
}

impl Default for TrackingMode {
    fn default() -> Self {
        Self::Disabled
    }
}

/// Tracking state
#[derive(Debug, Clone, Default)]
pub struct TrackingState {
    /// Current tracking mode
    pub mode: TrackingMode,
    /// Current target (if any)
    pub target: Option<Target>,
    /// Face tracking active
    pub face_tracking_active: bool,
    /// Sound tracking active
    pub sound_tracking_active: bool,
    /// Motion tracking active
    pub motion_tracking_active: bool,
    /// Time since last detection (ms)
    pub time_since_detection_ms: u32,
}

impl TrackingState {
    /// Check if any tracking is active
    pub fn is_tracking(&self) -> bool {
        self.target.is_some()
    }

    /// Get target azimuth (yaw) if available
    pub fn target_yaw(&self) -> Option<f32> {
        self.target.as_ref().map(|t| t.yaw)
    }

    /// Get target elevation (pitch) if available
    pub fn target_pitch(&self) -> Option<f32> {
        self.target.as_ref().map(|t| t.pitch)
    }
}

/// Configuration for tracking behavior
#[derive(Debug, Clone)]
pub struct TrackingConfig {
    /// Enable face tracking
    pub enable_face: bool,
    /// Enable sound tracking
    pub enable_sound: bool,
    /// Enable motion tracking
    pub enable_motion: bool,
    /// Smooth tracking (low-pass filter)
    pub smooth_tracking: bool,
    /// Smoothing factor (0-1, higher = smoother)
    pub smoothing_alpha: f32,
    /// Timeout before returning to center (ms)
    pub return_to_center_timeout_ms: u32,
    /// Speed limit for tracking (deg/s)
    pub max_tracking_speed_deg_s: f32,
}

impl Default for TrackingConfig {
    fn default() -> Self {
        Self {
            enable_face: true,
            enable_sound: true,
            enable_motion: false, // Off by default (can be distracting)
            smooth_tracking: true,
            smoothing_alpha: 0.85,
            return_to_center_timeout_ms: 5000, // 5 seconds
            max_tracking_speed_deg_s: 45.0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tracking_state() {
        let mut state = TrackingState::default();
        assert!(!state.is_tracking());
        assert!(state.target_yaw().is_none());

        state.target = Some(Target {
            pitch: 10.0,
            yaw: 45.0,
            confidence: 0.9,
            source: TargetPriority::Face,
        });

        assert!(state.is_tracking());
        assert_eq!(state.target_yaw(), Some(45.0));
        assert_eq!(state.target_pitch(), Some(10.0));
    }
}
