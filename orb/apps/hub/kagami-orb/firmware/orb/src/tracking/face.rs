//! Face Tracker
//!
//! Processes face detection results from the Hailo-10H NPU and
//! converts them to PTZ orientation targets.
//!
//! # Camera Options
//!
//! ## OV5647 (Tracking Camera - Default)
//! - 62.2° horizontal FoV, 48.8° vertical FoV
//! - 2592×1944 max resolution (1280×720 for low-latency tracking)
//! - Lower power, adequate for face detection
//!
//! ## IMX989 (High-Resolution Camera - Optional)
//! - 84° horizontal FoV, 63° vertical FoV
//! - 8192×6144 max (50.3 MP), 1920×1080 for tracking
//! - Higher quality but more power and processing
//!
//! The FoV parameters are configurable via `CameraFov::set_fov()`.
//!
//! # Coordinate System
//!
//! Face detection provides bounding boxes in image coordinates.
//! We convert these to azimuth/elevation angles for PTZ control:
//! - Image center (0.5, 0.5) → PTZ (0°, 0°)
//! - Right edge → positive yaw
//! - Bottom edge → negative pitch (camera looks down)

use super::target::{Target, TargetPriority};

/// Camera field of view parameters
#[derive(Debug, Clone, Copy)]
pub struct CameraFov {
    /// Horizontal field of view (degrees)
    pub horizontal_deg: f32,
    /// Vertical field of view (degrees)
    pub vertical_deg: f32,
    /// Image width (pixels)
    pub width_px: u32,
    /// Image height (pixels)
    pub height_px: u32,
}

impl Default for CameraFov {
    /// Default: OV5647 at 1280×720 for low-latency tracking
    fn default() -> Self {
        Self::ov5647_720p()
    }
}

impl CameraFov {
    /// OV5647 camera at 720p (default for face tracking)
    pub fn ov5647_720p() -> Self {
        Self {
            horizontal_deg: 62.2,
            vertical_deg: 48.8,
            width_px: 1280,
            height_px: 720,
        }
    }

    /// IMX989 camera at 1080p (high-quality option)
    pub fn imx989_1080p() -> Self {
        Self {
            horizontal_deg: 84.0,
            vertical_deg: 63.0,
            width_px: 1920,
            height_px: 1080,
        }
    }

    /// Create custom FoV configuration
    pub fn custom(horizontal_deg: f32, vertical_deg: f32, width_px: u32, height_px: u32) -> Self {
        Self {
            horizontal_deg,
            vertical_deg,
            width_px,
            height_px,
        }
    }
}

/// Face detection result from NPU
#[derive(Debug, Clone)]
pub struct FaceDetection {
    /// Bounding box center X (pixels, 0 = left)
    pub center_x: f32,
    /// Bounding box center Y (pixels, 0 = top)
    pub center_y: f32,
    /// Bounding box width (pixels)
    pub width: f32,
    /// Bounding box height (pixels)
    pub height: f32,
    /// Detection confidence (0-1)
    pub confidence: f32,
    /// Face ID for tracking continuity
    pub face_id: u32,
}

impl FaceDetection {
    /// Estimate distance from face size (rough heuristic)
    ///
    /// Assumes average face width ~15cm at 1m distance
    pub fn estimated_distance_m(&self, fov: &CameraFov) -> f32 {
        const AVERAGE_FACE_WIDTH_M: f32 = 0.15;
        let pixels_per_degree = fov.width_px as f32 / fov.horizontal_deg;
        let face_degrees = self.width / pixels_per_degree;
        let face_radians = face_degrees * core::f32::consts::PI / 180.0;

        // distance = face_width / (2 × tan(angle/2))
        AVERAGE_FACE_WIDTH_M / (2.0 * libm::tanf(face_radians / 2.0))
    }
}

/// Face tracker state
pub struct FaceTracker {
    /// Camera field of view
    fov: CameraFov,
    /// Primary face being tracked
    primary_face: Option<TrackedFace>,
    /// All detected faces
    detected_faces: heapless::Vec<FaceDetection, 8>,
    /// Smoothing filter state
    smooth_yaw: f32,
    smooth_pitch: f32,
    /// Smoothing coefficient (0-1, higher = smoother)
    alpha: f32,
    /// Frames since last detection
    frames_without_detection: u32,
    /// Maximum frames before losing track
    max_lost_frames: u32,
}

/// A face being tracked across frames
#[derive(Debug, Clone)]
struct TrackedFace {
    face_id: u32,
    yaw: f32,
    pitch: f32,
    confidence: f32,
    distance_m: f32,
}

impl FaceTracker {
    /// Create a new face tracker
    pub fn new() -> Self {
        Self {
            fov: CameraFov::default(),
            primary_face: None,
            detected_faces: heapless::Vec::new(),
            smooth_yaw: 0.0,
            smooth_pitch: 0.0,
            alpha: 0.85,
            frames_without_detection: 0,
            max_lost_frames: 30, // ~0.5s at 60fps
        }
    }

    /// Set camera field of view
    pub fn set_fov(&mut self, fov: CameraFov) {
        self.fov = fov;
    }

    /// Set smoothing coefficient
    pub fn set_smoothing(&mut self, alpha: f32) {
        self.alpha = alpha.clamp(0.0, 0.99);
    }

    /// Update with new detections from NPU
    ///
    /// Returns the primary target to track (if any)
    pub fn update(&mut self, detections: &[FaceDetection]) -> Option<Target> {
        self.detected_faces.clear();
        for det in detections.iter().take(8) {
            self.detected_faces.push(det.clone()).ok();
        }

        if detections.is_empty() {
            self.frames_without_detection += 1;
            if self.frames_without_detection > self.max_lost_frames {
                self.primary_face = None;
            }
            return self.get_current_target();
        }

        self.frames_without_detection = 0;

        // Select primary face
        let primary = self.select_primary_face(detections);

        // Convert to angles
        let (yaw, pitch) = self.pixel_to_angle(primary.center_x, primary.center_y);
        let distance = primary.estimated_distance_m(&self.fov);

        // Update tracked face
        self.primary_face = Some(TrackedFace {
            face_id: primary.face_id,
            yaw,
            pitch,
            confidence: primary.confidence,
            distance_m: distance,
        });

        // Apply smoothing
        self.smooth_yaw = self.alpha * self.smooth_yaw + (1.0 - self.alpha) * yaw;
        self.smooth_pitch = self.alpha * self.smooth_pitch + (1.0 - self.alpha) * pitch;

        self.get_current_target()
    }

    /// Select which face to track as primary
    fn select_primary_face<'a>(&self, detections: &'a [FaceDetection]) -> &'a FaceDetection {
        // Priority:
        // 1. Continue tracking same face_id
        // 2. Largest face (closest person)
        // 3. Most centered face
        // 4. Highest confidence

        if let Some(ref primary) = self.primary_face {
            // Try to continue tracking same face
            if let Some(same) = detections.iter().find(|d| d.face_id == primary.face_id) {
                return same;
            }
        }

        // Select largest face (safe fallback if partial_cmp fails due to NaN)
        detections
            .iter()
            .max_by(|a, b| {
                let area_a = a.width * a.height;
                let area_b = b.width * b.height;
                area_a.partial_cmp(&area_b).unwrap_or(core::cmp::Ordering::Equal)
            })
            .expect("select_primary_face called with empty detections - this is a bug")
    }

    /// Convert pixel coordinates to azimuth/elevation angles
    ///
    /// Returns (yaw, pitch) in degrees
    fn pixel_to_angle(&self, x: f32, y: f32) -> (f32, f32) {
        // Normalize to -0.5 to 0.5
        let norm_x = (x / self.fov.width_px as f32) - 0.5;
        let norm_y = (y / self.fov.height_px as f32) - 0.5;

        // Convert to angles
        let yaw = norm_x * self.fov.horizontal_deg;
        let pitch = -norm_y * self.fov.vertical_deg; // Negative because Y increases downward

        (yaw, pitch)
    }

    /// Get current target (smoothed)
    fn get_current_target(&self) -> Option<Target> {
        self.primary_face.as_ref().map(|face| Target {
            pitch: self.smooth_pitch,
            yaw: self.smooth_yaw,
            confidence: face.confidence,
            source: TargetPriority::Face,
        })
    }

    /// Get primary face info
    pub fn primary_face(&self) -> Option<&TrackedFace> {
        self.primary_face.as_ref()
    }

    /// Check if actively tracking
    pub fn is_tracking(&self) -> bool {
        self.primary_face.is_some() && self.frames_without_detection < self.max_lost_frames
    }

    /// Get number of detected faces
    pub fn face_count(&self) -> usize {
        self.detected_faces.len()
    }

    /// Clear tracking state
    pub fn clear(&mut self) {
        self.primary_face = None;
        self.detected_faces.clear();
        self.smooth_yaw = 0.0;
        self.smooth_pitch = 0.0;
        self.frames_without_detection = 0;
    }
}

impl Default for FaceTracker {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_pixel_to_angle_center() {
        let tracker = FaceTracker::new();
        let (yaw, pitch) = tracker.pixel_to_angle(640.0, 360.0); // Center of 1280×720

        assert!((yaw - 0.0).abs() < 0.1);
        assert!((pitch - 0.0).abs() < 0.1);
    }

    #[test]
    fn test_pixel_to_angle_corners() {
        let tracker = FaceTracker::new();

        // Top-left corner
        let (yaw, pitch) = tracker.pixel_to_angle(0.0, 0.0);
        assert!(yaw < 0.0); // Left
        assert!(pitch > 0.0); // Up

        // Bottom-right corner
        let (yaw, pitch) = tracker.pixel_to_angle(1280.0, 720.0);
        assert!(yaw > 0.0); // Right
        assert!(pitch < 0.0); // Down
    }

    #[test]
    fn test_face_selection() {
        let mut tracker = FaceTracker::new();

        let detections = vec![
            FaceDetection {
                center_x: 640.0,
                center_y: 360.0,
                width: 100.0,
                height: 120.0,
                confidence: 0.9,
                face_id: 1,
            },
            FaceDetection {
                center_x: 200.0,
                center_y: 200.0,
                width: 200.0, // Larger face
                height: 240.0,
                confidence: 0.8,
                face_id: 2,
            },
        ];

        let target = tracker.update(&detections);
        assert!(target.is_some());

        // Should select larger face (id=2)
        assert_eq!(tracker.primary_face().unwrap().face_id, 2);
    }

    #[test]
    fn test_tracking_continuity() {
        let mut tracker = FaceTracker::new();

        // First detection
        let det1 = vec![FaceDetection {
            center_x: 640.0,
            center_y: 360.0,
            width: 100.0,
            height: 120.0,
            confidence: 0.9,
            face_id: 1,
        }];
        tracker.update(&det1);

        // Second detection with same face but different position
        let det2 = vec![
            FaceDetection {
                center_x: 200.0,
                center_y: 200.0,
                width: 200.0, // Larger but different ID
                height: 240.0,
                confidence: 0.9,
                face_id: 2,
            },
            FaceDetection {
                center_x: 650.0, // Same face moved slightly
                center_y: 370.0,
                width: 100.0,
                height: 120.0,
                confidence: 0.85,
                face_id: 1,
            },
        ];
        tracker.update(&det2);

        // Should continue tracking face_id=1 for continuity
        assert_eq!(tracker.primary_face().unwrap().face_id, 1);
    }

    #[test]
    fn test_lost_tracking() {
        let mut tracker = FaceTracker::new();
        tracker.max_lost_frames = 5;

        // Start tracking
        let det = vec![FaceDetection {
            center_x: 640.0,
            center_y: 360.0,
            width: 100.0,
            height: 120.0,
            confidence: 0.9,
            face_id: 1,
        }];
        tracker.update(&det);
        assert!(tracker.is_tracking());

        // No detections for several frames
        for _ in 0..5 {
            tracker.update(&[]);
        }

        // Should still have target (smoothed)
        assert!(tracker.primary_face.is_some());

        // One more frame loses the track
        tracker.update(&[]);
        assert!(tracker.primary_face.is_none());
        assert!(!tracker.is_tracking());
    }

    #[test]
    fn test_distance_estimation() {
        let fov = CameraFov::default();
        let det = FaceDetection {
            center_x: 640.0,
            center_y: 360.0,
            width: 200.0, // ~10% of frame width
            height: 240.0,
            confidence: 0.9,
            face_id: 1,
        };

        let distance = det.estimated_distance_m(&fov);

        // Should be reasonable distance (0.5-3m for typical face size)
        assert!(distance > 0.3);
        assert!(distance < 5.0);
    }
}
