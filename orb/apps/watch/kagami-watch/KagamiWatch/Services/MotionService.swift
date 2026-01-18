//
// MotionService.swift — Accelerometer & Motion Data for Activity Detection
//
// Colony: Flow (e₃) — Sensing physical movement
//
// Provides:
//   - Motion intensity (0-1 scale)
//   - Activity type detection (stationary, walking, running)
//   - Movement state (moving/stationary)
//
// This data feeds into Kagami's activity detection for:
//   - Presence inference (at desk vs moving around)
//   - Context-aware suggestions
//   - Automatic mode transitions
//

import Foundation
import CoreMotion
import Combine

@MainActor
class MotionService: ObservableObject {

    // MARK: - Published State

    @Published var motionIntensity: Double = 0.0  // 0-1 scale
    @Published var isMoving: Bool = false
    @Published var activityType: String = "stationary"
    @Published var isAvailable: Bool = false

    // Raw accelerometer data (for debugging)
    @Published var accelerometerX: Double = 0
    @Published var accelerometerY: Double = 0
    @Published var accelerometerZ: Double = 0

    // Smart Stack relevance integration
    // Per audit: Wire motion service to Smart Stack relevance calculation
    @Published var activityRelevanceScore: Double = 0.5

    // MARK: - Private

    private let motionManager = CMMotionManager()
    private let activityManager = CMMotionActivityManager()
    private let queue = OperationQueue()

    // Motion smoothing
    private var intensityBuffer: [Double] = []
    private let bufferSize = 10

    // Thresholds
    private let stationaryThreshold = 0.02  // Below this = stationary
    private let walkingThreshold = 0.1      // Above this = walking
    private let runningThreshold = 0.3      // Above this = running

    // MARK: - Initialization

    init() {
        queue.maxConcurrentOperationCount = 1
        checkAvailability()
    }

    private func checkAvailability() {
        isAvailable = motionManager.isAccelerometerAvailable
        print("📱 Motion available: \(isAvailable)")
    }

    // MARK: - Start/Stop

    func startMonitoring() {
        guard isAvailable else {
            print("⚠️ Motion not available on this device")
            return
        }

        // Start accelerometer updates
        startAccelerometer()

        // Start activity recognition (walking, running, etc.)
        startActivityRecognition()

        print("📱 Motion monitoring started")
    }

    func stopMonitoring() {
        motionManager.stopAccelerometerUpdates()
        activityManager.stopActivityUpdates()
        print("📱 Motion monitoring stopped")
    }

    // MARK: - Accelerometer

    private func startAccelerometer() {
        guard motionManager.isAccelerometerAvailable else { return }

        // Update at 10Hz (battery efficient for activity detection)
        motionManager.accelerometerUpdateInterval = 0.1

        motionManager.startAccelerometerUpdates(to: queue) { [weak self] data, error in
            guard let data = data, error == nil else { return }

            // Calculate magnitude of acceleration (excluding gravity ~1.0)
            let x = data.acceleration.x
            let y = data.acceleration.y
            let z = data.acceleration.z

            // Total acceleration magnitude
            let magnitude = sqrt(x*x + y*y + z*z)

            // Deviation from gravity (1.0) indicates motion
            let deviation = abs(magnitude - 1.0)

            // Normalize to 0-1 scale (clamp at 1.0 for very high motion)
            let normalizedIntensity = min(deviation * 5.0, 1.0)

            Task { @MainActor [weak self] in
                self?.updateMotionIntensity(normalizedIntensity)
                self?.accelerometerX = x
                self?.accelerometerY = y
                self?.accelerometerZ = z
            }
        }
    }

    private func updateMotionIntensity(_ newValue: Double) {
        // Smooth the intensity using a rolling average
        intensityBuffer.append(newValue)
        if intensityBuffer.count > bufferSize {
            intensityBuffer.removeFirst()
        }

        let smoothed = intensityBuffer.reduce(0, +) / Double(intensityBuffer.count)
        motionIntensity = smoothed

        // Determine if moving
        isMoving = smoothed > stationaryThreshold

        // Classify activity if not using CoreMotion activity recognition
        if smoothed < stationaryThreshold {
            activityType = "stationary"
        } else if smoothed < walkingThreshold {
            activityType = "light_movement"
        } else if smoothed < runningThreshold {
            activityType = "walking"
        } else {
            activityType = "running"
        }
    }

    // MARK: - Activity Recognition (CoreMotion)

    private func startActivityRecognition() {
        guard CMMotionActivityManager.isActivityAvailable() else {
            print("⚠️ Activity recognition not available")
            return
        }

        activityManager.startActivityUpdates(to: queue) { [weak self] activity in
            guard let activity = activity else { return }

            Task { @MainActor [weak self] in
                self?.handleActivityUpdate(activity)
            }
        }
    }

    private func handleActivityUpdate(_ activity: CMMotionActivity) {
        // CoreMotion provides high-level activity classification
        if activity.stationary {
            activityType = "stationary"
            isMoving = false
        } else if activity.walking {
            activityType = "walking"
            isMoving = true
        } else if activity.running {
            activityType = "running"
            isMoving = true
        } else if activity.cycling {
            activityType = "cycling"
            isMoving = true
        } else if activity.automotive {
            activityType = "driving"
            isMoving = true  // Vehicle is moving, person is stationary
        } else {
            activityType = "unknown"
        }

        // Update Smart Stack relevance score based on activity
        updateSmartStackRelevance(activity)
    }

    // MARK: - Smart Stack Relevance
    // Per audit: Wire motion service to Smart Stack relevance calculation

    private func updateSmartStackRelevance(_ activity: CMMotionActivity) {
        // Calculate relevance score based on activity type and confidence
        var relevance: Double = 0.5 // Base relevance

        // High-motion activities make home control more relevant
        // (user likely transitioning - coming home, leaving, starting workout)
        if activity.running {
            relevance = 0.8 // Workout mode highly relevant
        } else if activity.walking {
            relevance = 0.7 // May be arriving/leaving
        } else if activity.cycling {
            relevance = 0.75 // Outdoor activity
        } else if activity.automotive {
            relevance = 0.85 // Likely commuting - arrival/departure relevant
        } else if activity.stationary {
            // Stationary - context depends on time
            let hour = Calendar.current.component(.hour, from: Date())
            if hour >= 17 && hour <= 22 {
                relevance = 0.65 // Evening at home - movie mode, dinner relevant
            } else if hour >= 22 || hour < 6 {
                relevance = 0.6 // Night - goodnight relevant
            } else {
                relevance = 0.4 // Daytime stationary - less relevant
            }
        }

        // Apply confidence factor
        if activity.confidence == .high {
            relevance *= 1.0
        } else if activity.confidence == .medium {
            relevance *= 0.9
        } else {
            relevance *= 0.7
        }

        // Clamp to valid range
        activityRelevanceScore = min(max(relevance, 0.0), 1.0)

        // Store in shared container for Smart Stack widget
        let defaults = UserDefaults(suiteName: "group.com.kagami.watch")
        defaults?.set(activityRelevanceScore, forKey: "activityRelevance")
        defaults?.set(isMoving, forKey: "isMoving")
        defaults?.set(activityType, forKey: "activityType")
        defaults?.set(activity.running, forKey: "isWorkingOut")

        // Notify widget to update if relevance changed significantly
        if abs(activityRelevanceScore - (defaults?.double(forKey: "lastRelevance") ?? 0.5)) > 0.1 {
            defaults?.set(activityRelevanceScore, forKey: "lastRelevance")

            // Trigger widget refresh
            Task {
                ComplicationUpdateManager.shared.reloadKagamiWidgets()
            }
        }
    }

    // MARK: - Data Export (for API)

    /// Get current motion data for upload to Kagami
    func getMotionData() -> [String: Any] {
        return [
            "motion_intensity": motionIntensity,
            "is_moving": isMoving,
            "activity_type": activityType,
            "relevance_score": activityRelevanceScore,
        ]
    }

    /// Get Smart Stack relevance score
    /// Per audit: Used by Smart Stack widget for data-driven relevance
    func getSmartStackRelevance() -> Double {
        return activityRelevanceScore
    }
}

/*
 * 鏡
 *
 * Motion is presence manifest.
 * Stillness is attention focused.
 * The body speaks through movement.
 */
