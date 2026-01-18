//! Target Management
//!
//! Handles target selection and priority when multiple tracking
//! sources are active (face, sound, motion, manual).

/// Priority level for different target sources
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum TargetPriority {
    /// Lowest priority - return to center
    None = 0,
    /// Motion detection
    Motion = 1,
    /// Sound source localization
    Sound = 2,
    /// Face tracking
    Face = 3,
    /// Manual override (highest)
    Manual = 4,
}

impl Default for TargetPriority {
    fn default() -> Self {
        Self::None
    }
}

/// A tracking target with orientation and metadata
#[derive(Debug, Clone)]
pub struct Target {
    /// Target pitch (elevation) in degrees
    pub pitch: f32,
    /// Target yaw (azimuth) in degrees
    pub yaw: f32,
    /// Confidence in target (0-1)
    pub confidence: f32,
    /// Source of this target
    pub source: TargetPriority,
}

impl Target {
    /// Create a centered target
    pub fn center() -> Self {
        Self {
            pitch: 0.0,
            yaw: 0.0,
            confidence: 1.0,
            source: TargetPriority::None,
        }
    }

    /// Create a manual target
    pub fn manual(pitch: f32, yaw: f32) -> Self {
        Self {
            pitch,
            yaw,
            confidence: 1.0,
            source: TargetPriority::Manual,
        }
    }

    /// Check if this target should override another
    pub fn overrides(&self, other: &Target) -> bool {
        // Higher priority always wins
        if self.source > other.source {
            return true;
        }

        // Same priority: higher confidence wins
        if self.source == other.source && self.confidence > other.confidence {
            return true;
        }

        false
    }

    /// Calculate angular distance to another target
    pub fn distance_to(&self, other: &Target) -> f32 {
        let d_pitch = self.pitch - other.pitch;
        let d_yaw = angle_difference(self.yaw, other.yaw);

        libm::sqrtf(d_pitch * d_pitch + d_yaw * d_yaw)
    }

    /// Interpolate toward another target
    pub fn interpolate_to(&self, other: &Target, t: f32) -> Target {
        let t = t.clamp(0.0, 1.0);

        Target {
            pitch: self.pitch + (other.pitch - self.pitch) * t,
            yaw: interpolate_angle(self.yaw, other.yaw, t),
            confidence: self.confidence + (other.confidence - self.confidence) * t,
            source: other.source,
        }
    }
}

impl Default for Target {
    fn default() -> Self {
        Self::center()
    }
}

/// Target selector that manages multiple tracking sources
pub struct TargetSelector {
    /// Current active target
    current_target: Target,
    /// Face tracking target
    face_target: Option<Target>,
    /// Sound tracking target
    sound_target: Option<Target>,
    /// Motion tracking target
    motion_target: Option<Target>,
    /// Manual override target
    manual_target: Option<Target>,
    /// Time since each source last updated (ms)
    face_age_ms: u32,
    sound_age_ms: u32,
    motion_age_ms: u32,
    /// Timeout before source is considered stale (ms)
    stale_timeout_ms: u32,
    /// Smoothing for target transitions
    smooth_target: Target,
    smoothing_alpha: f32,
}

impl TargetSelector {
    /// Create a new target selector
    pub fn new() -> Self {
        Self {
            current_target: Target::center(),
            face_target: None,
            sound_target: None,
            motion_target: None,
            manual_target: None,
            face_age_ms: u32::MAX,
            sound_age_ms: u32::MAX,
            motion_age_ms: u32::MAX,
            stale_timeout_ms: 2000, // 2 seconds
            smooth_target: Target::center(),
            smoothing_alpha: 0.9,
        }
    }

    /// Update face target
    pub fn set_face_target(&mut self, target: Option<Target>) {
        self.face_target = target;
        self.face_age_ms = 0;
    }

    /// Update sound target
    pub fn set_sound_target(&mut self, target: Option<Target>) {
        self.sound_target = target;
        self.sound_age_ms = 0;
    }

    /// Update motion target
    pub fn set_motion_target(&mut self, target: Option<Target>) {
        self.motion_target = target;
        self.motion_age_ms = 0;
    }

    /// Set manual override (highest priority)
    pub fn set_manual_target(&mut self, pitch: f32, yaw: f32) {
        self.manual_target = Some(Target::manual(pitch, yaw));
    }

    /// Clear manual override
    pub fn clear_manual(&mut self) {
        self.manual_target = None;
    }

    /// Update and select best target
    ///
    /// Call this at regular intervals (e.g., 50Hz)
    pub fn update(&mut self, dt_ms: u32) -> Target {
        // Age all sources
        self.face_age_ms = self.face_age_ms.saturating_add(dt_ms);
        self.sound_age_ms = self.sound_age_ms.saturating_add(dt_ms);
        self.motion_age_ms = self.motion_age_ms.saturating_add(dt_ms);

        // Expire stale targets
        if self.face_age_ms > self.stale_timeout_ms {
            self.face_target = None;
        }
        if self.sound_age_ms > self.stale_timeout_ms {
            self.sound_target = None;
        }
        if self.motion_age_ms > self.stale_timeout_ms {
            self.motion_target = None;
        }

        // Select highest priority target
        let best = self.select_best_target();

        // Update current target
        self.current_target = best.clone();

        // Apply smoothing
        self.smooth_target = Target {
            pitch: self.smoothing_alpha * self.smooth_target.pitch
                + (1.0 - self.smoothing_alpha) * best.pitch,
            yaw: interpolate_angle(
                self.smooth_target.yaw,
                best.yaw,
                1.0 - self.smoothing_alpha,
            ),
            confidence: best.confidence,
            source: best.source,
        };

        self.smooth_target.clone()
    }

    /// Select highest priority active target
    fn select_best_target(&self) -> Target {
        // Priority order: Manual > Face > Sound > Motion > Center

        if let Some(ref manual) = self.manual_target {
            return manual.clone();
        }

        if let Some(ref face) = self.face_target {
            return face.clone();
        }

        if let Some(ref sound) = self.sound_target {
            return sound.clone();
        }

        if let Some(ref motion) = self.motion_target {
            return motion.clone();
        }

        Target::center()
    }

    /// Get current target
    pub fn current(&self) -> &Target {
        &self.smooth_target
    }

    /// Get active source
    pub fn active_source(&self) -> TargetPriority {
        self.current_target.source
    }

    /// Check if any tracking is active
    pub fn is_tracking(&self) -> bool {
        self.manual_target.is_some()
            || self.face_target.is_some()
            || self.sound_target.is_some()
            || self.motion_target.is_some()
    }

    /// Set smoothing factor
    pub fn set_smoothing(&mut self, alpha: f32) {
        self.smoothing_alpha = alpha.clamp(0.0, 0.99);
    }

    /// Set stale timeout
    pub fn set_stale_timeout(&mut self, timeout_ms: u32) {
        self.stale_timeout_ms = timeout_ms;
    }
}

impl Default for TargetSelector {
    fn default() -> Self {
        Self::new()
    }
}

/// Calculate shortest angular difference between two angles
fn angle_difference(a: f32, b: f32) -> f32 {
    let mut diff = b - a;
    while diff > 180.0 {
        diff -= 360.0;
    }
    while diff < -180.0 {
        diff += 360.0;
    }
    diff
}

/// Interpolate between angles, taking shortest path
fn interpolate_angle(a: f32, b: f32, t: f32) -> f32 {
    let diff = angle_difference(a, b);
    let mut result = a + diff * t;

    // Normalize to 0-360
    while result < 0.0 {
        result += 360.0;
    }
    while result >= 360.0 {
        result -= 360.0;
    }

    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_target_priority() {
        assert!(TargetPriority::Manual > TargetPriority::Face);
        assert!(TargetPriority::Face > TargetPriority::Sound);
        assert!(TargetPriority::Sound > TargetPriority::Motion);
        assert!(TargetPriority::Motion > TargetPriority::None);
    }

    #[test]
    fn test_target_override() {
        let face = Target {
            pitch: 10.0,
            yaw: 45.0,
            confidence: 0.9,
            source: TargetPriority::Face,
        };

        let manual = Target::manual(0.0, 0.0);
        let motion = Target {
            pitch: 5.0,
            yaw: 90.0,
            confidence: 0.5,
            source: TargetPriority::Motion,
        };

        assert!(manual.overrides(&face));
        assert!(face.overrides(&motion));
        assert!(!motion.overrides(&face));
    }

    #[test]
    fn test_angle_difference() {
        assert!((angle_difference(10.0, 20.0) - 10.0).abs() < 0.001);
        assert!((angle_difference(350.0, 10.0) - 20.0).abs() < 0.001);
        assert!((angle_difference(10.0, 350.0) - (-20.0)).abs() < 0.001);
    }

    #[test]
    fn test_angle_interpolation() {
        // Simple case
        let result = interpolate_angle(0.0, 90.0, 0.5);
        assert!((result - 45.0).abs() < 0.001);

        // Wraparound case (350 to 10 should go through 0)
        let result = interpolate_angle(350.0, 10.0, 0.5);
        assert!((result - 0.0).abs() < 0.001);
    }

    #[test]
    fn test_selector_priority() {
        let mut selector = TargetSelector::new();

        // Add motion target
        selector.set_motion_target(Some(Target {
            pitch: 5.0,
            yaw: 45.0,
            confidence: 0.8,
            source: TargetPriority::Motion,
        }));

        let target = selector.update(0);
        assert_eq!(target.source, TargetPriority::Motion);

        // Add face target (higher priority)
        selector.set_face_target(Some(Target {
            pitch: 10.0,
            yaw: 90.0,
            confidence: 0.9,
            source: TargetPriority::Face,
        }));

        let target = selector.update(0);
        assert_eq!(target.source, TargetPriority::Face);

        // Add manual override (highest)
        selector.set_manual_target(0.0, 0.0);

        let target = selector.update(0);
        assert_eq!(target.source, TargetPriority::Manual);

        // Clear manual
        selector.clear_manual();
        let target = selector.update(0);
        assert_eq!(target.source, TargetPriority::Face);
    }

    #[test]
    fn test_selector_expiration() {
        let mut selector = TargetSelector::new();
        selector.set_stale_timeout(100);

        // Add face target
        selector.set_face_target(Some(Target {
            pitch: 10.0,
            yaw: 90.0,
            confidence: 0.9,
            source: TargetPriority::Face,
        }));

        assert!(selector.is_tracking());

        // Age it past timeout
        selector.update(50);
        assert!(selector.is_tracking());

        selector.update(60); // Now past 100ms
        assert!(!selector.is_tracking());
    }

    #[test]
    fn test_target_distance() {
        let t1 = Target {
            pitch: 0.0,
            yaw: 0.0,
            confidence: 1.0,
            source: TargetPriority::Face,
        };

        let t2 = Target {
            pitch: 3.0,
            yaw: 4.0,
            confidence: 1.0,
            source: TargetPriority::Face,
        };

        // Distance should be 5 (3-4-5 triangle)
        let dist = t1.distance_to(&t2);
        assert!((dist - 5.0).abs() < 0.001);
    }
}
